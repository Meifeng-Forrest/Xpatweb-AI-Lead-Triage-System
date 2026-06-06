from enum import StrEnum
from datetime import datetime

from typing import Any

from pydantic import BaseModel, EmailStr, Field


class SourceBox(StrEnum):
    XP = "XP"
    RISA = "RISA"
    VLS = "VLS"
    SMV = "SMV"


class LeadStatus(StrEnum):
    RECEIVED = "received"
    CONTACTED = "contacted"
    SCORED = "scored"
    DRAFTED = "drafted"
    IN_REVIEW = "in_review"
    SENT = "sent"
    DNQ = "dnq"
    ARCHIVED = "archived"


class ManualLeadCreate(BaseModel):
    sender_name: str = Field(default="Not Provided", max_length=200)
    email_address: EmailStr
    contact_number: str | None = Field(default=None, max_length=80)
    visa_category: str | None = Field(default=None, max_length=200)
    source_box: SourceBox
    lead_source: str | None = Field(default=None, max_length=80)
    raw_message: str = Field(min_length=1, max_length=12000)


class FormWebhookLeadCreate(BaseModel):
    source_box: SourceBox
    fields: dict[str, Any] = Field(default_factory=dict)
    form_name: str | None = Field(default=None, max_length=200)
    sender_name: str | None = Field(default=None, max_length=200)
    email_address: str | None = Field(default=None, max_length=320)
    contact_number: str | None = Field(default=None, max_length=80)
    visa_category: str | None = Field(default=None, max_length=200)
    lead_source: str | None = Field(default=None, max_length=80)
    utm_source: str | None = Field(default=None, max_length=120)
    utm_campaign: str | None = Field(default=None, max_length=120)
    campaign_code: str | None = Field(default=None, max_length=120)
    raw_message: str | None = Field(default=None, max_length=12000)


class ManualLeadAccepted(BaseModel):
    lead_id: str
    status: LeadStatus
    source_box: SourceBox
    message: str
    created_at: datetime
    pipeline_task_id: str | None = None


class LeadRead(BaseModel):
    lead_id: str
    sender_name: str
    email_address: EmailStr
    raw_message: str
    contact_number: str | None
    email_domain: str
    visa_category: str | None
    lead_type: str | None = None
    current_visa: str | None = None
    pr_route: str | None = None
    nationality: str | None = None
    is_first_world: bool | None = None
    job_title: str | None = None
    net_worth_indicator: str | None = None
    has_job_offer: bool | None = None
    qualifying_work_visa_years: float | None = None
    annual_salary_zar: float | None = None
    pbs_total_score_below_100: bool | None = None
    relationship_duration: str | None = None
    marriage_type: str | None = None
    rejection_date: str | None = None
    urgency_flag: bool | None = None
    multi_visa_flag: bool | None = None
    email_coherence: str | None = None
    additional_info: str | None = None
    extracted_fields: dict[str, Any] = Field(default_factory=dict)
    extracted_at: datetime | None = None
    extraction_provider: str | None = None
    extraction_model: str | None = None
    extraction_temperature: float | None = None
    lead_score: str | None = None
    dnq_reason: str | None = None
    risk_flags: list[str] = Field(default_factory=list)
    score_confidence: str | None = None
    score_rationale: str | None = None
    escalation_flag: bool = False
    soft_dnq_warning: str | None = None
    score_provider: str | None = None
    score_model: str | None = None
    score_temperature: float | None = None
    scored_at: datetime | None = None
    email_draft: str | None = None
    whatsapp_draft: str | None = None
    phone_script: str | None = None
    internal_whatsapp_post: str | None = None
    draft_fields: dict[str, Any] = Field(default_factory=dict)
    draft_provider: str | None = None
    draft_model: str | None = None
    draft_temperature: float | None = None
    drafted_at: datetime | None = None
    source_box: SourceBox
    lead_source: str | None
    assigned_consultant: str | None = None
    status: LeadStatus
    created_at: datetime
    updated_at: datetime


class LeadStatusUpdate(BaseModel):
    status: LeadStatus


class LeadFieldEditRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=80)
    visa_category: str | None = Field(default=None, max_length=200)
    source: str | None = Field(default=None, max_length=80)
    assigned_consultant: str | None = Field(default=None, max_length=120)
    brand: SourceBox | None = None


class LeadActionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)


class DraftEditRequest(BaseModel):
    email_draft: str | None = Field(default=None, max_length=12000)
    whatsapp_draft: str | None = Field(default=None, max_length=4000)
    phone_script: str | None = Field(default=None, max_length=4000)
    internal_whatsapp_post: str | None = Field(default=None, max_length=4000)
    reason: str | None = Field(default=None, max_length=1000)


class AuthLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class AuthUserRead(BaseModel):
    user_id: str
    email: EmailStr
    display_name: str
    roles: list[str]
    permissions: list[str]


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    user: AuthUserRead


class UserRead(BaseModel):
    user_id: str
    email: str
    display_name: str
    roles: list[str]
    permissions: list[str]
    routing_categories: list[str] = Field(default_factory=list)
    is_active: bool
    created_at: datetime
    updated_at: datetime


class UserCreateRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=8, max_length=200)
    roles: list[str] = Field(min_length=1, max_length=1)
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    roles: list[str] | None = Field(default=None, min_length=1, max_length=1)
    is_active: bool | None = None


class UserPasswordResetRequest(BaseModel):
    password: str = Field(min_length=8, max_length=200)


class UserRoutingCategoriesUpdateRequest(BaseModel):
    categories: list[str] = Field(default_factory=list, max_length=20)


class RoutingRuleRead(BaseModel):
    category: str
    recipients: list[UserRead]
    fallback_to_superadmin: bool = False


class RoutingRuleUpdateRequest(BaseModel):
    user_ids: list[str] = Field(default_factory=list, max_length=100)


class AuditEventRead(BaseModel):
    event_id: int
    lead_id: str
    event_type: str
    actor: str
    metadata: dict[str, Any]
    created_at: datetime


class ResearchBriefFields(BaseModel):
    personalProfile: str = ""
    employer: str = ""
    immigrationAnalysis: str = ""
    news: str = ""
    consultantTips: str = ""


class ResearchBriefRead(BaseModel):
    lead_id: str
    status: str
    task_id: str | None = None
    brief: ResearchBriefFields | None = None
    source_refs: list[dict[str, Any]] = Field(default_factory=list)
    error_type: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


class ResearchQueuedResponse(BaseModel):
    lead_id: str
    task_id: str
    status: str = "queued"


class EmailExtractionRequest(BaseModel):
    source_box: SourceBox
    email_subject: str | None = Field(default=None, max_length=500)
    email_from: str | None = Field(default=None, max_length=500)
    email_body: str = Field(min_length=1, max_length=30000)


class ExtractedEmailFields(BaseModel):
    sender_name: str
    email_address: str | None
    contact_number: str | None
    email_domain: str | None
    lead_type: str | None
    visa_category: str | None
    current_visa: str | None
    pr_route: str | None
    nationality: str | None
    is_first_world: bool | None
    job_title: str | None
    net_worth_indicator: str | None
    has_job_offer: bool | None
    qualifying_work_visa_years: float | None
    annual_salary_zar: float | None
    pbs_total_score_below_100: bool | None
    relationship_duration: str | None
    marriage_type: str | None
    rejection_date: str | None
    urgency_flag: bool
    multi_visa_flag: bool
    email_coherence: str
    additional_info: str | None


class EmailExtractionResponse(BaseModel):
    provider: str
    model: str
    temperature: float
    extracted: ExtractedEmailFields


class ManualExtractionRequest(BaseModel):
    raw_text: str = Field(min_length=1, max_length=30000)


class ManualConfirmedLeadCreate(BaseModel):
    raw_message: str = Field(min_length=1, max_length=30000)
    source_box: SourceBox
    extracted: ExtractedEmailFields
    extraction_provider: str = Field(default="llm", max_length=80)
    extraction_model: str = Field(max_length=120)
    extraction_temperature: float = 0.0


class PersistExtractedFieldsRequest(BaseModel):
    extracted: ExtractedEmailFields
    provider: str = Field(default="manual", max_length=80)
    model: str = Field(default="unknown", max_length=120)
    temperature: float = 0.0
    actor: str = Field(default="system", max_length=120)


class LeadScoreResult(BaseModel):
    lead_score: str = Field(pattern="^(GD|MF|MD|BD)$")
    score_confidence: str = Field(pattern="^(high|medium|low)$")
    score_rationale: str = Field(min_length=1, max_length=1000)
    escalation_flag: bool
    soft_dnq_warning: str | None = Field(default=None, max_length=500)


class LeadScoreResponse(BaseModel):
    provider: str
    model: str
    temperature: float
    result: LeadScoreResult


class PersistLeadScoreRequest(BaseModel):
    result: LeadScoreResult
    provider: str = Field(default="manual", max_length=80)
    model: str = Field(default="unknown", max_length=120)
    temperature: float = 0.0
    actor: str = Field(default="system", max_length=120)


class PipelineQueuedResponse(BaseModel):
    lead_id: str
    task_id: str
    status: str = "queued"


class PipelineTaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: dict[str, Any] | None = None
    error_type: str | None = None


class DraftResult(BaseModel):
    email_draft: str = Field(min_length=1, max_length=12000)
    whatsapp_draft: str | None = Field(default=None, max_length=4000)
    phone_script: str | None = Field(default=None, max_length=4000)
    internal_whatsapp_post: str | None = Field(default=None, max_length=4000)
    template_id: str | None = Field(default=None, max_length=120)
    visa_bucket: str | None = Field(default=None, max_length=20)
    professional_fee_zar: str | None = Field(default=None, max_length=80)
    admin_fee_zar: str | None = Field(default=None, max_length=80)
    fee_source: str | None = Field(default=None, max_length=200)
    materials_checklist: list[str] = Field(default_factory=list, max_length=20)
    dnq_reason: str | None = Field(default=None, max_length=40)
    alternative_suggestions: list[str] = Field(default_factory=list, max_length=10)


class DraftResponse(BaseModel):
    provider: str
    model: str
    temperature: float
    result: DraftResult


class PersistDraftsRequest(BaseModel):
    result: DraftResult
    provider: str = Field(default="manual", max_length=80)
    model: str = Field(default="unknown", max_length=120)
    temperature: float = 0.0
    actor: str = Field(default="system", max_length=120)


class HealthResponse(BaseModel):
    status: str
    app: str
    environment: str
    configured_mailboxes: int
    database_configured: bool
    redis_configured: bool
    llm_configured: bool
    graph_configured: bool
