import json
import logging
import time
from typing import Any

import httpx
from pydantic import ValidationError

from app.config import Settings
from app.repositories.leads import LeadRecord
from app.schemas import DraftResult, LeadScoreResult
from app.services.gemini_http import gemini_error_summary

logger = logging.getLogger("lead_triage.services.gemini_triage")


SCORE_TEMPERATURE = 0.0
DRAFT_TEMPERATURE = 0.2


SCORE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "lead_score": {"type": "string", "enum": ["GD", "MF", "MD", "BD"]},
        "score_confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "score_rationale": {
            "type": "string",
            "description": "One or two plain-language sentences for consultants.",
        },
        "escalation_flag": {"type": "boolean"},
        "soft_dnq_warning": {"type": ["string", "null"]},
    },
    "required": [
        "lead_score",
        "score_confidence",
        "score_rationale",
        "escalation_flag",
        "soft_dnq_warning",
    ],
}


DRAFT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "email_draft": {
            "type": "string",
            "description": "Client-facing email draft. Do not invent facts or unverified fees.",
        },
        "whatsapp_draft": {"type": ["string", "null"]},
        "phone_script": {"type": ["string", "null"]},
        "internal_whatsapp_post": {
            "type": ["string", "null"],
            "description": "Internal team post using Box-Quality-Action format where possible.",
        },
    },
    "required": ["email_draft", "whatsapp_draft", "phone_script", "internal_whatsapp_post"],
}


def gemini_endpoint(settings: Settings, model: str) -> str:
    return f"{settings.gemini_base_url.rstrip('/')}/v1beta/models/{model}:generateContent"


def extract_text_from_gemini_response(data: dict[str, Any]) -> str:
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Gemini response did not contain generated JSON text") from exc


def lead_context(lead: LeadRecord) -> dict[str, Any]:
    return {
        "lead_id": lead.lead_id,
        "source_box": lead.source_box,
        "lead_source": lead.lead_source,
        "sender_name": lead.sender_name,
        "email_domain": lead.email_domain,
        "visa_category": lead.visa_category,
        "lead_type": lead.lead_type,
        "current_visa": lead.current_visa,
        "pr_route": lead.pr_route,
        "nationality": lead.nationality,
        "is_first_world": lead.is_first_world,
        "job_title": lead.job_title,
        "net_worth_indicator": lead.net_worth_indicator,
        "has_job_offer": lead.has_job_offer,
        "qualifying_work_visa_years": lead.qualifying_work_visa_years,
        "annual_salary_zar": lead.annual_salary_zar,
        "pbs_total_score_below_100": lead.pbs_total_score_below_100,
        "relationship_duration": lead.relationship_duration,
        "marriage_type": lead.marriage_type,
        "rejection_date": lead.rejection_date,
        "urgency_flag": lead.urgency_flag,
        "multi_visa_flag": lead.multi_visa_flag,
        "email_coherence": lead.email_coherence,
        "additional_info": lead.additional_info,
        "extracted_fields": lead.extracted_fields,
        "lead_score": lead.lead_score,
        "dnq_reason": lead.dnq_reason,
        "risk_flags": lead.risk_flags,
        "score_confidence": lead.score_confidence,
        "score_rationale": lead.score_rationale,
        "soft_dnq_warning": lead.soft_dnq_warning,
    }


def build_score_prompt(lead: LeadRecord) -> str:
    return f"""
You are a lead qualification scorer for Xpatweb, a South African immigration consultancy.
A field extraction step has already produced the structured JSON below.
Your job is to assign lead_score and explain why. Do not draft a reply.

EXTRACTED FIELDS:
{json.dumps(lead_context(lead), ensure_ascii=False, indent=2)}

INDIVIDUAL LEADS RUBRIC:
- GD: strong visa signal such as Retired Person Visa, Remote Work Visa, PR Financially Independent, or high net worth; senior title, first-world nationality, urgency, multi-visa, and coherent message strengthen GD.
- MF: coherent enquiry with some value signal but missing important wealth/title details.
- MD: coherent enquiry but limited value signal or singular low-detail visa request.
- BD: incoherent, low-value, unsupported, or likely bad-fit enquiry.

CORPORATE LEADS RUBRIC:
- GD: corporate domain + Director/HR/PA + non-verification multi-visa.
- MF: company email + unspecified department + verification/assessment only.
- MD: personal email + small/unspecified company + verification/assessment only.

Rules:
- The deterministic hard-DNQ check has already passed. Never invent a DNQ reason.
- Treat risk_flags as prompts for human review, not automatic rejection.
- Retired Person Visa is usually strong unless facts contradict it.
- score_confidence is low if nationality, job_title, and net_worth_indicator are mostly missing.
- escalation_flag is true if extracted facts suggest frustration, complaint posture, deadline pressure, or urgent escalation.
- Never fabricate facts. Cite only fields in the JSON.
""".strip()


def build_draft_prompt(lead: LeadRecord) -> str:
    return f"""
You are drafting first-response communication for Xpatweb leads.
Use the structured lead JSON below. Do not mention that AI or background research was used.
Do not invent prices, government fees, missing documents, dates, or consultant names.
If fees are not supplied in the JSON, ask the lead to book/confirm details rather than quoting exact fees.

LEAD JSON:
{json.dumps(lead_context(lead), ensure_ascii=False, indent=2)}

Draft requirements:
- Keep the combined JSON response concise and under 700 words.
- Do not add phone numbers, email addresses, calendar links, signatures, or consultant names unless they are explicitly present in the lead JSON.
- If dnq_reason is present, write a concise refusal draft for human review and set phone_script to null.
- email_draft: concise professional email aligned to the lead score and visa category.
- whatsapp_draft: short WhatsApp version, or null if inappropriate.
- phone_script: short opening call script for GD/MF/MD leads, or null if inappropriate.
- internal_whatsapp_post: internal Box-Quality-Action style note for the team.
""".strip()


class GeminiTriageService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def _generate_json(
        self,
        *,
        tag: str,
        model: str,
        prompt: str,
        schema: dict[str, Any],
        temperature: float,
        summary: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured")

        logger.info("%s enter %s", tag, {**summary, "model": model, "temperature": temperature})
        started_at = time.perf_counter()
        request_body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
                "responseJsonSchema": schema,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.post(
                    gemini_endpoint(self.settings, model),
                    headers={
                        "Content-Type": "application/json",
                        "x-goog-api-key": self.settings.gemini_api_key,
                    },
                    json=request_body,
                )
            response.raise_for_status()
            text = extract_text_from_gemini_response(response.json())
            data = json.loads(text)
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
            logger.exception(
                "%s fail %s",
                tag,
                {
                    **summary,
                    "model": model,
                    "ms": round((time.perf_counter() - started_at) * 1000),
                    **gemini_error_summary(exc),
                    "error": str(exc)[:300],
                },
            )
            raise

        logger.info(
            "%s success %s",
            tag,
            {**summary, "model": model, "ms": round((time.perf_counter() - started_at) * 1000)},
        )
        return data

    async def score_lead(self, lead: LeadRecord) -> LeadScoreResult:
        data = await self._generate_json(
            tag="[llm/gemini/score]",
            model=self.settings.gemini_model_score,
            prompt=build_score_prompt(lead),
            schema=SCORE_SCHEMA,
            temperature=SCORE_TEMPERATURE,
            summary={
                "lead_id": lead.lead_id,
                "source_box": lead.source_box,
                "visa_category_present": bool(lead.visa_category),
                "email_coherence": lead.email_coherence,
            },
        )
        try:
            return LeadScoreResult.model_validate(data)
        except ValidationError:
            logger.exception("[llm/gemini/score] validation_fail %s", {"lead_id": lead.lead_id})
            raise

    async def draft_for_lead(self, lead: LeadRecord) -> DraftResult:
        data = await self._generate_json(
            tag="[llm/gemini/draft]",
            model=self.settings.gemini_model_draft,
            prompt=build_draft_prompt(lead),
            schema=DRAFT_SCHEMA,
            temperature=DRAFT_TEMPERATURE,
            summary={
                "lead_id": lead.lead_id,
                "source_box": lead.source_box,
                "lead_score": lead.lead_score,
                "visa_category_present": bool(lead.visa_category),
            },
        )
        try:
            return DraftResult.model_validate(data)
        except ValidationError:
            logger.exception("[llm/gemini/draft] validation_fail %s", {"lead_id": lead.lead_id})
            raise
