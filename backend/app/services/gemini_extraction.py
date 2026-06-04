import json
import logging
import time
from typing import Any

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.logging import summarize_text
from app.schemas import EmailExtractionRequest, ExtractedEmailFields
from app.services.gemini_http import gemini_error_summary

logger = logging.getLogger("lead_triage.services.gemini_extraction")


EXTRACTION_TEMPERATURE = 0.0


EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "sender_name": {
            "type": "string",
            "description": 'Full sender name. Use "Not Provided" when absent.',
        },
        "email_address": {"type": ["string", "null"], "description": "Sender or inquiry email address."},
        "contact_number": {"type": ["string", "null"], "description": "Phone or WhatsApp number."},
        "email_domain": {
            "type": ["string", "null"],
            "enum": ["corporate", "gmail", "other_personal", None],
            "description": "Classify the email domain, not the literal domain string.",
        },
        "lead_type": {
            "type": ["string", "null"],
            "enum": ["Individual", "Corporate Individual", "Corporate", None],
        },
        "visa_category": {
            "type": ["string", "null"],
            "description": 'Best matching Xpatweb service list visa category, else "Unknown".',
        },
        "current_visa": {"type": ["string", "null"]},
        "pr_route": {
            "type": ["string", "null"],
            "enum": ["work_visa", "financially_independent", "relative", "other", None],
        },
        "nationality": {"type": ["string", "null"]},
        "is_first_world": {"type": ["boolean", "null"]},
        "job_title": {"type": ["string", "null"]},
        "net_worth_indicator": {
            "type": ["string", "null"],
            "description": "Income, assets, salary, investment, or net-worth signals quoted in the message.",
        },
        "has_job_offer": {"type": ["boolean", "null"]},
        "qualifying_work_visa_years": {"type": ["number", "null"]},
        "annual_salary_zar": {"type": ["number", "null"]},
        "pbs_total_score_below_100": {"type": ["boolean", "null"]},
        "relationship_duration": {"type": ["string", "null"]},
        "marriage_type": {
            "type": ["string", "null"],
            "enum": ["registered", "traditional", "unregistered", "common-law", None],
        },
        "rejection_date": {"type": ["string", "null"], "format": "date"},
        "urgency_flag": {"type": "boolean"},
        "multi_visa_flag": {"type": "boolean"},
        "email_coherence": {"type": "string", "enum": ["high", "medium", "low"]},
        "additional_info": {
            "type": ["string", "null"],
            "description": "One or two sentence factual summary. Do not score or judge.",
        },
    },
    "required": [
        "sender_name",
        "email_address",
        "contact_number",
        "email_domain",
        "lead_type",
        "visa_category",
        "current_visa",
        "pr_route",
        "nationality",
        "is_first_world",
        "job_title",
        "net_worth_indicator",
        "has_job_offer",
        "qualifying_work_visa_years",
        "annual_salary_zar",
        "pbs_total_score_below_100",
        "relationship_duration",
        "marriage_type",
        "rejection_date",
        "urgency_flag",
        "multi_visa_flag",
        "email_coherence",
        "additional_info",
    ],
}


def build_extraction_prompt(payload: EmailExtractionRequest) -> str:
    # 提取 Prompt 只让模型填字段，不允许它顺手评分；评分会在后续独立步骤处理。
    return f"""
You are a field extraction assistant for Xpatweb, a South African immigration consultancy.
The brand receiving this lead is: {payload.source_box.value} (XP / RISA / VLS / SMV).

Extract fields from the incoming inquiry. Do NOT score, qualify, reject, or draft a reply.
If a field is not present, output null, except sender_name should be "Not Provided".
Do not invent facts. Use only the subject, from header, and body below.

Email subject:
{payload.email_subject or ""}

Email from header:
{payload.email_from or ""}

Email body:
{payload.email_body}
""".strip()


def gemini_endpoint(settings: Settings) -> str:
    return f"{settings.gemini_base_url.rstrip('/')}/v1beta/models/{settings.gemini_model_extract}:generateContent"


def extract_text_from_gemini_response(data: dict[str, Any]) -> str:
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Gemini response did not contain generated JSON text") from exc


class GeminiExtractionService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def extract_email_fields(self, payload: EmailExtractionRequest) -> ExtractedEmailFields:
        if not self.settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        prompt = build_extraction_prompt(payload)
        summary = {
            "source_box": payload.source_box.value,
            "model": self.settings.gemini_model_extract,
            "temperature": EXTRACTION_TEMPERATURE,
            "subject": summarize_text(payload.email_subject),
            "body": summarize_text(payload.email_body),
        }
        logger.info("[llm/gemini/extract] enter %s", summary)
        started_at = time.perf_counter()

        request_body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": EXTRACTION_TEMPERATURE,
                "responseMimeType": "application/json",
                "responseJsonSchema": EXTRACTION_SCHEMA,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.post(
                    gemini_endpoint(self.settings),
                    headers={
                        "Content-Type": "application/json",
                        "x-goog-api-key": self.settings.gemini_api_key,
                    },
                    json=request_body,
                )
            response.raise_for_status()
            text = extract_text_from_gemini_response(response.json())
            extracted = ExtractedEmailFields.model_validate(json.loads(text))
        except (httpx.HTTPError, json.JSONDecodeError, ValidationError, ValueError) as exc:
            logger.exception(
                "[llm/gemini/extract] fail %s",
                {
                    "source_box": payload.source_box.value,
                    "model": self.settings.gemini_model_extract,
                    "ms": round((time.perf_counter() - started_at) * 1000),
                    **gemini_error_summary(exc),
                    "error": str(exc)[:300],
                },
            )
            raise

        logger.info(
            "[llm/gemini/extract] success %s",
            {
                "source_box": payload.source_box.value,
                "model": self.settings.gemini_model_extract,
                "ms": round((time.perf_counter() - started_at) * 1000),
                "visa_category_present": bool(extracted.visa_category),
                "email_coherence": extracted.email_coherence,
            },
        )
        return extracted
