import json
from typing import Any

from app.repositories.leads import LeadRecord


SCORE_TEMPERATURE = 0.0
DRAFT_TEMPERATURE = 0.2
OPENAI_COMPATIBLE_TRIAGE_TEMPERATURE = 0.6


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


def with_schema(prompt: str, schema: dict[str, Any]) -> str:
    return f"{prompt}\n\nReturn one JSON object matching this JSON Schema:\n{json.dumps(schema, ensure_ascii=False)}"


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
