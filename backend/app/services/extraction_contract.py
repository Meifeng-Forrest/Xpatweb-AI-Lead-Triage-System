import json
from typing import Any

from pydantic import ValidationError

from app.schemas import EmailExtractionRequest, ExtractedEmailFields


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


def schema_instruction(schema: dict[str, Any]) -> str:
    return f"Return one JSON object matching this JSON Schema:\n{json.dumps(schema, ensure_ascii=False)}"


def build_manual_extraction_prompt(raw_text: str) -> str:
    # 业务合同只描述“要提取什么”，具体用哪家模型由 adapter 决定。
    return f"""
You are a field extraction assistant for Xpatweb, a South African immigration consultancy.
Extract the structured fields from the pasted inquiry below.
Do NOT score, qualify, reject, draft a reply, or infer the receiving brand.
Do not invent facts. If a field is absent, output null, except:
- sender_name must be "Not Provided" when absent
- urgency_flag and multi_visa_flag must be false when absent
- email_coherence must be high, medium, or low

{schema_instruction(EXTRACTION_SCHEMA)}

PASTED INQUIRY:
{raw_text}
""".strip()


def build_email_extraction_prompt(payload: EmailExtractionRequest) -> str:
    # 邮件入口保留 source_box 线索；手动粘贴入口不推断品牌，避免覆盖用户选择。
    return f"""
You are a field extraction assistant for Xpatweb, a South African immigration consultancy.
The brand receiving this lead is: {payload.source_box.value} (XP / RISA / VLS / SMV).

Extract fields from the incoming inquiry. Do NOT score, qualify, reject, or draft a reply.
If a field is not present, output null, except sender_name should be "Not Provided".
Do not invent facts. Use only the subject, from header, and body below.

{schema_instruction(EXTRACTION_SCHEMA)}

Email subject:
{payload.email_subject or ""}

Email from header:
{payload.email_from or ""}

Email body:
{payload.email_body}
""".strip()


def validate_extracted_fields(data: dict[str, Any]) -> ExtractedEmailFields:
    try:
        return ExtractedEmailFields.model_validate(data)
    except ValidationError:
        raise
