import logging
import re
from dataclasses import dataclass

from app.repositories.leads import LeadRecord
from app.schemas import DraftResult

logger = logging.getLogger("lead_triage.services.visa_templates")


@dataclass(frozen=True)
class VisaDraftTemplate:
    template_id: str
    canonical_name: str
    aliases: tuple[str, ...]
    bucket: str
    professional_fee_zar: str
    admin_fee_zar: str | None
    materials: tuple[str, ...]


@dataclass(frozen=True)
class DnqDraftTemplate:
    template_id: str
    dnq_reason: str
    client_reason: str
    review_note: str
    alternative_suggestions: tuple[str, ...]


TOP_10_TEMPLATES: tuple[VisaDraftTemplate, ...] = (
    VisaDraftTemplate(
        template_id="TMPL_POSITIVE_RETIRED_PERSON_VISA",
        canonical_name="Retired Person Visa",
        aliases=("retired person", "retirement visa"),
        bucket="A",
        professional_fee_zar="R42,280",
        admin_fee_zar="R2,480",
        materials=("Proof of retirement income", "Valid passport", "Medical and radiological reports"),
    ),
    VisaDraftTemplate(
        template_id="TMPL_POSITIVE_PR_FINANCIALLY_INDEPENDENT",
        canonical_name="Permanent Residence, Financially Independent",
        aliases=("financially independent", "pr financially independent", "permanent residence financial"),
        bucket="A",
        professional_fee_zar="R42,860",
        admin_fee_zar="R4,020",
        materials=("Proof of net worth", "Valid passport", "Permanent residence supporting documents"),
    ),
    VisaDraftTemplate(
        template_id="TMPL_POSITIVE_CRITICAL_SKILLS_WORK_VISA",
        canonical_name="Critical Skills Work Visa",
        aliases=("critical skills",),
        bucket="A",
        professional_fee_zar="R36,120",
        admin_fee_zar="R4,020",
        materials=("SAQA evaluation", "Professional registration where applicable", "Employment or offer documentation"),
    ),
    VisaDraftTemplate(
        template_id="TMPL_POSITIVE_REMOTE_WORK_VISA",
        canonical_name="Remote Work Visa",
        aliases=("remote work", "digital nomad"),
        bucket="A",
        professional_fee_zar="R26,860",
        admin_fee_zar="R2,500",
        materials=("Foreign employment or contract proof", "Income proof", "Valid passport"),
    ),
    VisaDraftTemplate(
        template_id="TMPL_POSITIVE_INTRA_COMPANY_TRANSFER",
        canonical_name="Intra-Company Transfer",
        aliases=("intra-company", "intra company", "ict visa"),
        bucket="B",
        professional_fee_zar="R30,820",
        admin_fee_zar="R2,500",
        materials=("Foreign employer confirmation", "South African host company letter", "Transfer assignment details"),
    ),
    VisaDraftTemplate(
        template_id="TMPL_POSITIVE_GENERAL_WORK_VISA",
        canonical_name="General Work Visa",
        aliases=("general work",),
        bucket="B",
        professional_fee_zar="R28,860",
        admin_fee_zar="R2,685",
        materials=("Employment offer", "Department of Labour process documents", "Employer supporting documents"),
    ),
    VisaDraftTemplate(
        template_id="TMPL_POSITIVE_VISITOR_11_6_SPOUSAL",
        canonical_name="Visitor Visa 11(6) Spousal",
        aliases=("visitor visa 11(6)", "visitors visa section 11(6)", "spousal visitor"),
        bucket="B",
        professional_fee_zar="R22,620",
        admin_fee_zar="R2,500",
        materials=("Relationship evidence", "South African spouse or partner documents", "Valid passport"),
    ),
    VisaDraftTemplate(
        template_id="TMPL_POSITIVE_APPEAL_APPLICATION",
        canonical_name="Appeal Application",
        aliases=("appeal", "appeal application"),
        bucket="C",
        professional_fee_zar="R24,890-R30,612",
        admin_fee_zar=None,
        materials=("Rejection letter", "Submitted application pack", "Supporting evidence for appeal grounds"),
    ),
    VisaDraftTemplate(
        template_id="TMPL_POSITIVE_STUDY_VISA",
        canonical_name="Study Visa",
        aliases=("study visa", "student visa"),
        bucket="C",
        professional_fee_zar="R18,280",
        admin_fee_zar="R2,685",
        materials=("Institution acceptance letter", "Proof of accommodation", "Medical cover proof"),
    ),
    VisaDraftTemplate(
        template_id="TMPL_POSITIVE_RELATIVES_VISA",
        canonical_name="Relative's Visa",
        aliases=("relative's visa", "relatives visa", "relative visa"),
        bucket="C",
        professional_fee_zar="R18,280",
        admin_fee_zar=None,
        materials=("Relationship proof", "South African relative documentation", "Valid passport"),
    ),
)


DNQ_TEMPLATES: dict[str, DnqDraftTemplate] = {
    "DNQ-01": DnqDraftTemplate(
        template_id="TMPL_DNQ_01_CRITICAL_SKILLS_NO_JOB_OFFER",
        dnq_reason="DNQ-01",
        client_reason="a Critical Skills Work Visa application requires a formal job offer or qualifying employment basis before we can assess the route properly",
        review_note="Critical Skills enquiry without a confirmed job offer. Route should be reviewed before any rejection is sent.",
        alternative_suggestions=(
            "Ask the lead to revert once a formal job offer is secured.",
            "If the lead already has another employment basis, assess General Work Visa or Points-Based System as a separate route.",
        ),
    ),
    "DNQ-02": DnqDraftTemplate(
        template_id="TMPL_DNQ_02_PR_NO_CURRENT_SA_VISA",
        dnq_reason="DNQ-02",
        client_reason="Permanent Residence generally requires the applicant to hold a valid South African temporary residence status at the relevant stage",
        review_note="PR enquiry without current valid South African visa evidence.",
        alternative_suggestions=(
            "Assess whether a temporary residence visa route should be pursued first.",
            "If the lead has a valid visa that was not captured, request proof before confirming the rejection.",
        ),
    ),
    "DNQ-03": DnqDraftTemplate(
        template_id="TMPL_DNQ_03_PR_WORK_ROUTE_UNDER_FOUR_YEARS",
        dnq_reason="DNQ-03",
        client_reason="the work-visa Permanent Residence route requires four qualifying years on the relevant work visa path",
        review_note="PR work route under four qualifying years.",
        alternative_suggestions=(
            "Advise the lead to revisit PR once the four-year requirement is met.",
            "Check whether another PR category, such as financially independent, is genuinely applicable before sending.",
        ),
    ),
    "DNQ-04": DnqDraftTemplate(
        template_id="TMPL_DNQ_04_UNREGISTERED_RELATIONSHIP",
        dnq_reason="DNQ-04",
        client_reason="the relatives or spousal pathway requires a formally registered marriage or qualifying relationship evidence",
        review_note="Relative/spousal pathway where marriage type is traditional or unregistered.",
        alternative_suggestions=(
            "Request evidence of a formally registered marriage if available.",
            "If the relationship evidence is incomplete rather than absent, keep the lead in human review instead of sending a rejection.",
        ),
    ),
    "DNQ-05": DnqDraftTemplate(
        template_id="TMPL_DNQ_05_APPEAL_OUT_OF_TIME",
        dnq_reason="DNQ-05",
        client_reason="appeals must be lodged within the required 10-working-day period from the decision date",
        review_note="Appeal appears outside the 10-working-day window.",
        alternative_suggestions=(
            "Assess whether a fresh application is more appropriate.",
            "Escalate to a consultant if there are exceptional facts before confirming the response.",
        ),
    ),
    "DNQ-06": DnqDraftTemplate(
        template_id="TMPL_DNQ_06_VISITOR_11_1_VISA_EXEMPT",
        dnq_reason="DNQ-06",
        client_reason="Visitor Visa Section 11(1) is generally not applicable where the nationality is visa-exempt for short visits",
        review_note="Visitor 11(1) with visa-exempt nationality.",
        alternative_suggestions=(
            "If the intended activity is work, study, business, or a longer stay, assess the correct visa category instead.",
            "If nationality or travel purpose was extracted incorrectly, correct the fields before responding.",
        ),
    ),
}


BRAND_NAMES = {
    "XP": "Xpatweb",
    "RISA": "Retire In South Africa",
    "VLS": "Visa Litigation Services",
    "SMV": "Sable Migration Visa",
}


def _normalize(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").lower()).strip()


def find_template(visa_category: str | None) -> VisaDraftTemplate | None:
    normalized = _normalize(visa_category)
    if not normalized:
        return None
    for template in TOP_10_TEMPLATES:
        candidates = (template.canonical_name, *template.aliases)
        if any(_normalize(candidate) in normalized or normalized in _normalize(candidate) for candidate in candidates):
            return template
    return None


def _first_name(name: str | None) -> str:
    clean = (name or "").strip()
    if not clean or clean == "Not Provided":
        return "there"
    return clean.split()[0]


def _brand(source_box: str | None) -> str:
    return BRAND_NAMES.get(str(source_box or "").upper(), "Xpatweb")


def _fee_sentence(template: VisaDraftTemplate) -> str:
    admin = f" and the current administrative fee is {template.admin_fee_zar}" if template.admin_fee_zar else ""
    return (
        f"For this route, our professional fee is {template.professional_fee_zar} excluding VAT{admin}. "
        "These fee amounts are pulled from the approved internal template configuration and should be reviewed before sending."
    )


def _materials_sentence(template: VisaDraftTemplate) -> str:
    return "\n".join(f"- {item}" for item in template.materials)


def _alternative_sentence(suggestions: tuple[str, ...]) -> str:
    return "\n".join(f"- {suggestion}" for suggestion in suggestions)


def build_dnq_draft(lead: LeadRecord) -> DraftResult | None:
    dnq_reason = getattr(lead, "dnq_reason", None)
    template = DNQ_TEMPLATES.get(dnq_reason or "")
    if template is None:
        logger.info("[draft/dnq-template] no_match %s", {"lead_id": lead.lead_id, "dnq_reason": dnq_reason})
        return None

    first_name = _first_name(lead.sender_name)
    brand = _brand(lead.source_box)
    visa_category = lead.visa_category or "the requested immigration route"
    alternatives = _alternative_sentence(template.alternative_suggestions)

    # DNQ 草稿仍然只是“拒绝审核路径”的预填文案；外发前必须由 Marisa/指定审核人确认。
    email = (
        f"Dear {first_name},\n\n"
        "Trust this email finds you well.\n\n"
        f"Thank you for your valued enquiry to {brand} regarding {visa_category}.\n\n"
        f"Based on the information currently available, this matter requires review before we can proceed, as {template.client_reason}.\n\n"
        "Possible next steps for review:\n"
        f"{alternatives}\n\n"
        "Our team will review the available facts and confirm the appropriate response before any final communication is sent.\n\n"
        f"Kind regards,\n{brand}"
    )
    internal_post = (
        f"Box: {lead.source_box} | {visa_category}\n"
        f"Quality: BD | DNQ: {template.dnq_reason} | Template: {template.template_id}\n"
        f"Action: Route to Marisa/QA for refusal review. {template.review_note}"
    )
    logger.info(
        "[draft/dnq-template] match %s",
        {"lead_id": lead.lead_id, "dnq_reason": template.dnq_reason, "template_id": template.template_id},
    )
    return DraftResult(
        email_draft=email,
        whatsapp_draft=None,
        phone_script=None,
        internal_whatsapp_post=internal_post,
        template_id=template.template_id,
        visa_bucket="DNQ",
        fee_source="doc/业务规格.md §4.1",
        dnq_reason=template.dnq_reason,
        alternative_suggestions=list(template.alternative_suggestions),
    )


def build_template_draft(lead: LeadRecord) -> DraftResult | None:
    dnq_draft = build_dnq_draft(lead)
    if dnq_draft is not None:
        return dnq_draft

    template = find_template(lead.visa_category)
    if template is None:
        logger.info(
            "[draft/template] no_match %s",
            {"lead_id": lead.lead_id, "visa_category_present": bool(lead.visa_category)},
        )
        return None

    first_name = _first_name(lead.sender_name)
    brand = _brand(lead.source_box)
    fee_sentence = _fee_sentence(template)
    materials = _materials_sentence(template)
    score = lead.lead_score or "MD"

    # 第一版草稿必须从批准模板生成，费用只来自配置；LLM 后续只能生成研究增强版，不能决定金额。
    if lead.dnq_reason:
        email = (
            f"Dear {first_name},\n\n"
            f"Thank you for your valued enquiry to {brand} regarding {template.canonical_name}.\n\n"
            "Based on the information available, this enquiry requires internal review before we can confirm whether we may assist. "
            "Our team will review the facts and revert with the appropriate next step.\n\n"
            "We look forward to assisting you where possible.\n\n"
            f"Kind regards,\n{brand}"
        )
        phone_script = None
    elif score == "GD":
        email = (
            f"Dear {first_name},\n\n"
            "Trust this email finds you well.\n\n"
            f"Thank you for your valued enquiry to {brand} regarding {template.canonical_name}. "
            "We would like to schedule a brief consultation with one of our Immigration Consultants to assist further.\n\n"
            f"{fee_sentence}\n\n"
            "Please let us know your availability for a call today in South African Standard Time.\n\n"
            "We look forward to assisting you.\n\n"
            f"Kind regards,\n{brand}"
        )
        phone_script = (
            f"Dear {first_name}, my name is [Full Name] from {brand}. "
            f"We received your enquiry regarding {template.canonical_name}. "
            "We would like to schedule a brief consultation with one of our Immigration Consultants. "
            "Would you have availability today in South African Standard Time?"
        )
    else:
        email = (
            f"Dear {first_name},\n\n"
            "Trust this email finds you well.\n\n"
            f"Thank you for your valued enquiry to {brand} regarding {template.canonical_name}. "
            "Our standard immigration service for this route includes:\n"
            "- A complete list of required documents\n"
            "- Required letter templates\n"
            "- Document compliance review\n"
            "- Preparation of the application pack\n"
            "- A call to review the application\n"
            "- Appointment or submission guidance\n"
            "- Tracking after submission\n\n"
            f"{fee_sentence}\n\n"
            "At a high level, the usual supporting documents include:\n"
            f"{materials}\n\n"
            "Please confirm if you would like us to proceed with the next step or schedule a call.\n\n"
            "We look forward to assisting you.\n\n"
            f"Kind regards,\n{brand}"
        )
        phone_script = (
            f"Dear {first_name}, my name is [Full Name] from {brand}. "
            f"We received your enquiry regarding {template.canonical_name}. "
            "I am calling to confirm the key facts and explain the next step in the process."
        )

    whatsapp = (
        f"Dear {first_name}, my name is [Full Name] from {brand}. "
        f"We received your enquiry regarding {template.canonical_name}. "
        "Please let me know if we may provide availability to discuss the next step."
    )
    internal_post = (
        f"Box: {lead.source_box} | {template.canonical_name}\n"
        f"Quality: {score} | Template: {template.template_id} | Fee: {template.professional_fee_zar}"
        f"{' + admin ' + template.admin_fee_zar if template.admin_fee_zar else ''}\n"
        "Action: Review the template draft and confirm before any external response is sent."
    )

    logger.info(
        "[draft/template] match %s",
        {
            "lead_id": lead.lead_id,
            "template_id": template.template_id,
            "visa_bucket": template.bucket,
            "fee_source": "doc/业务规格.md §3.3",
        },
    )
    return DraftResult(
        email_draft=email,
        whatsapp_draft=whatsapp,
        phone_script=phone_script,
        internal_whatsapp_post=internal_post,
        template_id=template.template_id,
        visa_bucket=template.bucket,
        professional_fee_zar=template.professional_fee_zar,
        admin_fee_zar=template.admin_fee_zar,
        fee_source="doc/业务规格.md §3.3",
        materials_checklist=list(template.materials),
    )
