import logging
import json
from hmac import compare_digest
from uuid import uuid4
from typing import Any

from celery.exceptions import CeleryError
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from kombu.exceptions import KombuError
from pydantic import ValidationError

from app.celery_app import celery_app
from app.config import Settings, get_settings
from app.database import get_pool
from app.logging import summarize_email, summarize_text
from app.repositories.leads import LeadRepository
from app.repositories.research import ResearchBriefRecord, ResearchRepository
from app.schemas import (
    AuditEventRead,
    DraftEditRequest,
    DraftResponse,
    FormWebhookLeadCreate,
    LeadActionRequest,
    LeadFieldEditRequest,
    LeadRead,
    LeadScoreResponse,
    LeadStatusUpdate,
    ManualConfirmedLeadCreate,
    ManualLeadAccepted,
    ManualLeadCreate,
    PersistDraftsRequest,
    PersistExtractedFieldsRequest,
    PersistLeadScoreRequest,
    PipelineQueuedResponse,
    PipelineTaskStatusResponse,
    ResearchBriefFields,
    ResearchBriefRead,
    ResearchQueuedResponse,
)
from app.services.lead_pipeline import deterministic_dnq_score, draft_model, draft_provider, draft_temperature
from app.services.llm_factory import get_triage_service
from app.services.qualification_rules import qualify_lead
from app.services.auth import CurrentUser, get_current_user, require_permission
from app.tasks import run_lead_pipeline as run_lead_pipeline_task, run_lead_research as run_lead_research_task

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])
logger = logging.getLogger("lead_triage.api.leads")


def settings_from_request(request: Request) -> Settings:
    return getattr(request.app.state, "settings", get_settings())


def to_research_read(record: ResearchBriefRecord) -> ResearchBriefRead:
    return ResearchBriefRead(
        lead_id=record.lead_id,
        status=record.status,
        task_id=record.task_id,
        brief=ResearchBriefFields.model_validate(record.brief) if record.brief else None,
        source_refs=record.source_refs,
        error_type=record.error_type,
        error_message=record.error_message,
        created_at=record.created_at,
        updated_at=record.updated_at,
        completed_at=record.completed_at,
    )


async def enqueue_pipeline(repo: LeadRepository, lead_id: str, actor: str, skip_extraction: bool = False) -> str:
    logger.info("[queue/pipeline] enter %s", {"lead_id": lead_id, "actor": actor, "skip_extraction": skip_extraction})
    try:
        task = run_lead_pipeline_task.apply_async(args=[lead_id, skip_extraction])
    except (CeleryError, KombuError) as exc:
        logger.exception("[queue/pipeline] fail %s", {"lead_id": lead_id, "error": exc.__class__.__name__})
        raise HTTPException(status_code=503, detail="Lead pipeline queue is unavailable") from exc

    await repo.append_audit_event(
        lead_id=lead_id,
        event_type="lead.pipeline.queued",
        actor=actor,
        metadata={"task_id": task.id, "skip_extraction": skip_extraction},
    )
    logger.info(
        "[queue/pipeline] success %s",
        {"lead_id": lead_id, "task_id": task.id, "actor": actor},
    )
    return task.id


async def enqueue_research(repo: LeadRepository, research_repo: ResearchRepository, lead_id: str) -> str:
    logger.info("[queue/research] enter %s", {"lead_id": lead_id})
    try:
        task = run_lead_research_task.apply_async(args=[lead_id])
    except (CeleryError, KombuError) as exc:
        logger.exception("[queue/research] fail %s", {"lead_id": lead_id, "error": exc.__class__.__name__})
        raise HTTPException(status_code=503, detail="Research queue is unavailable") from exc

    await research_repo.mark_queued(lead_id, task.id)
    await repo.append_audit_event(
        lead_id=lead_id,
        event_type="lead.research.queued",
        actor="research-api",
        metadata={"task_id": task.id},
    )
    logger.info("[queue/research] success %s", {"lead_id": lead_id, "task_id": task.id})
    return task.id


def _clean_form_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        parts = [part for item in value if (part := _clean_form_value(item))]
        return ", ".join(parts) if parts else None
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=True, sort_keys=True)[:1000]
    text = str(value).strip()
    return text or None


def _canonical_form_key(key: str) -> str:
    return key.lower().replace("-", "_").replace(" ", "_").strip()


def _form_field(payload: FormWebhookLeadCreate, *names: str) -> str | None:
    direct_values = payload.model_dump()
    for name in names:
        value = _clean_form_value(direct_values.get(name))
        if value:
            return value

    folded_fields = {_canonical_form_key(key): value for key, value in payload.fields.items()}
    for name in names:
        value = _clean_form_value(folded_fields.get(_canonical_form_key(name)))
        if value:
            return value
    return None


def _form_lead_source(payload: FormWebhookLeadCreate) -> str | None:
    for value in (
        payload.lead_source,
        payload.campaign_code,
        payload.utm_campaign,
        payload.utm_source,
        _form_field(payload, "lead_source", "source", "campaign", "campaign_code", "utm_campaign", "utm_source"),
    ):
        cleaned = _clean_form_value(value)
        if cleaned:
            return cleaned[:80]
    return None


def _form_raw_message(payload: FormWebhookLeadCreate) -> str:
    explicit = _clean_form_value(payload.raw_message) or _form_field(
        payload,
        "raw_message",
        "message",
        "enquiry",
        "enquiry_message",
        "comments",
        "notes",
    )
    if explicit:
        return explicit[:12000]

    lines: list[str] = []
    if payload.form_name:
        lines.append(f"Form: {payload.form_name}")
    for key in sorted(payload.fields):
        value = _clean_form_value(payload.fields[key])
        if value:
            lines.append(f"{key}: {value}")
    raw_message = "\n".join(lines).strip() or "Form webhook submission"
    return raw_message[:12000]


def form_webhook_to_manual_lead(payload: FormWebhookLeadCreate) -> ManualLeadCreate:
    email_address = _form_field(payload, "email_address", "email", "emailaddress", "e-mail")
    if not email_address:
        raise HTTPException(status_code=422, detail="Form webhook email address is required")

    try:
        return ManualLeadCreate(
            sender_name=_form_field(payload, "sender_name", "name", "full_name", "fullname") or "Not Provided",
            email_address=email_address,
            contact_number=_form_field(payload, "contact_number", "phone", "mobile", "telephone", "contact"),
            visa_category=_form_field(payload, "visa_category", "visa_type", "visa", "service"),
            source_box=payload.source_box,
            lead_source=_form_lead_source(payload),
            raw_message=_form_raw_message(payload),
        )
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc


def verify_form_webhook_secret(request: Request, settings: Settings) -> None:
    if not settings.form_webhook_secret:
        return
    provided = request.headers.get("X-Webhook-Secret", "")
    if not compare_digest(provided, settings.form_webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid form webhook secret")


@router.post("/webhook/form", response_model=ManualLeadAccepted, status_code=202)
async def create_form_webhook_lead(
    payload: FormWebhookLeadCreate,
    request: Request,
    pool=Depends(get_pool),
    settings: Settings = Depends(settings_from_request),
) -> ManualLeadAccepted:
    verify_form_webhook_secret(request, settings)
    manual_payload = form_webhook_to_manual_lead(payload)
    lead_id = f"lead-{uuid4()}"
    logger.info(
        "[api/leads/webhook/form] enter %s",
        {
            "lead_id": lead_id,
            "source_box": manual_payload.source_box,
            "email": summarize_email(str(manual_payload.email_address)),
            "lead_source": manual_payload.lead_source,
            "field_count": len(payload.fields),
            "form_name_present": bool(payload.form_name),
            "raw_message": summarize_text(manual_payload.raw_message),
            "secret_required": bool(settings.form_webhook_secret),
        },
    )

    repo = LeadRepository(pool)
    record = await repo.create_form_webhook_lead(
        lead_id,
        manual_payload,
        form_name=payload.form_name,
        field_count=len(payload.fields),
    )
    logger.info(
        "[api/leads/webhook/form] persisted %s",
        {"lead_id": record.lead_id, "status": record.status, "source_box": record.source_box},
    )
    task_id = await enqueue_pipeline(repo, record.lead_id, "form-webhook-api")
    return ManualLeadAccepted(
        lead_id=record.lead_id,
        status=record.status,
        source_box=record.source_box,
        message="Form webhook lead persisted. AI triage pipeline queued.",
        created_at=record.created_at,
        pipeline_task_id=task_id,
    )


@router.post("/manual-confirmed", response_model=ManualLeadAccepted, status_code=202)
async def create_confirmed_manual_lead(
    payload: ManualConfirmedLeadCreate,
    pool=Depends(get_pool),
) -> ManualLeadAccepted:
    if not payload.extracted.email_address:
        raise HTTPException(status_code=422, detail="Confirmed email address is required")
    if payload.extracted.sender_name == "Not Provided" or not payload.extracted.sender_name.strip():
        raise HTTPException(status_code=422, detail="Confirmed sender name is required")
    if not payload.extracted.visa_category:
        raise HTTPException(status_code=422, detail="Confirmed visa category is required")

    lead_id = f"lead-{uuid4()}"
    logger.info(
        "[api/leads/manual-confirmed] enter %s",
        {
            "lead_id": lead_id,
            "source_box": payload.source_box,
            "raw_message": summarize_text(payload.raw_message),
            "provider": payload.extraction_provider,
            "model": payload.extraction_model,
        },
    )
    repo = LeadRepository(pool)
    record = await repo.create_confirmed_manual_lead(lead_id, payload)
    task_id = await enqueue_pipeline(repo, lead_id, "manual-confirmed-api", skip_extraction=True)
    logger.info(
        "[api/leads/manual-confirmed] success %s",
        {"lead_id": lead_id, "task_id": task_id, "source_box": payload.source_box},
    )
    return ManualLeadAccepted(
        lead_id=record.lead_id,
        status=record.status,
        source_box=record.source_box,
        message="Confirmed lead persisted. Qualification pipeline queued.",
        created_at=record.created_at,
        pipeline_task_id=task_id,
    )


@router.post("/manual", response_model=ManualLeadAccepted, status_code=202)
async def create_manual_lead(
    payload: ManualLeadCreate,
    pool=Depends(get_pool),
) -> ManualLeadAccepted:
    lead_id = f"lead-{uuid4()}"
    summary = {
        "lead_id": lead_id,
        "source_box": payload.source_box,
        "email": summarize_email(payload.email_address),
        "visa_category_present": bool(payload.visa_category),
        "raw_message": summarize_text(payload.raw_message),
    }
    logger.info("[api/leads/manual] enter %s", summary)

    repo = LeadRepository(pool)
    record = await repo.create_manual_lead(lead_id, payload)
    logger.info(
        "[api/leads/manual] persisted %s",
        {"lead_id": record.lead_id, "status": record.status, "source_box": record.source_box},
    )
    task_id = await enqueue_pipeline(repo, record.lead_id, "manual-api")
    return ManualLeadAccepted(
        lead_id=record.lead_id,
        status=record.status,
        source_box=record.source_box,
        message="Lead persisted. AI triage pipeline queued.",
        created_at=record.created_at,
        pipeline_task_id=task_id,
    )


def to_lead_read(record) -> LeadRead:
    return LeadRead(
        lead_id=record.lead_id,
        sender_name=record.sender_name,
        email_address=record.email_address,
        raw_message=record.raw_message,
        contact_number=record.contact_number,
        email_domain=record.email_domain,
        visa_category=record.visa_category,
        lead_type=record.lead_type,
        current_visa=record.current_visa,
        pr_route=record.pr_route,
        nationality=record.nationality,
        is_first_world=record.is_first_world,
        job_title=record.job_title,
        net_worth_indicator=record.net_worth_indicator,
        has_job_offer=record.has_job_offer,
        qualifying_work_visa_years=record.qualifying_work_visa_years,
        annual_salary_zar=record.annual_salary_zar,
        pbs_total_score_below_100=record.pbs_total_score_below_100,
        relationship_duration=record.relationship_duration,
        marriage_type=record.marriage_type,
        rejection_date=record.rejection_date,
        urgency_flag=record.urgency_flag,
        multi_visa_flag=record.multi_visa_flag,
        email_coherence=record.email_coherence,
        additional_info=record.additional_info,
        extracted_fields=record.extracted_fields,
        extracted_at=record.extracted_at,
        extraction_provider=record.extraction_provider,
        extraction_model=record.extraction_model,
        extraction_temperature=record.extraction_temperature,
        lead_score=record.lead_score,
        dnq_reason=record.dnq_reason,
        risk_flags=record.risk_flags,
        score_confidence=record.score_confidence,
        score_rationale=record.score_rationale,
        escalation_flag=record.escalation_flag,
        soft_dnq_warning=record.soft_dnq_warning,
        score_provider=record.score_provider,
        score_model=record.score_model,
        score_temperature=record.score_temperature,
        scored_at=record.scored_at,
        email_draft=record.email_draft,
        whatsapp_draft=record.whatsapp_draft,
        phone_script=record.phone_script,
        internal_whatsapp_post=record.internal_whatsapp_post,
        draft_fields=record.draft_fields,
        draft_provider=record.draft_provider,
        draft_model=record.draft_model,
        draft_temperature=record.draft_temperature,
        drafted_at=record.drafted_at,
        source_box=record.source_box,
        lead_source=record.lead_source,
        assigned_consultant=record.assigned_consultant,
        status=record.status,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def normalize_audit_metadata(value: Any) -> dict[str, Any]:
    # asyncpg 在部分环境会把 jsonb 返回为字符串；这里统一转成 dict，避免接口序列化 500。
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def to_audit_event_read(record) -> AuditEventRead:
    return AuditEventRead(
        event_id=record["event_id"],
        lead_id=record["lead_id"],
        event_type=record["event_type"],
        actor=record["actor"],
        metadata=normalize_audit_metadata(record["metadata"]),
        created_at=record["created_at"],
    )


@router.get("", response_model=list[LeadRead])
async def list_leads(
    limit: int = Query(default=100, ge=1, le=500),
    pool=Depends(get_pool),
) -> list[LeadRead]:
    logger.info("[api/leads/list] enter %s", {"limit": limit})
    records = await LeadRepository(pool).list_leads(limit=limit)
    logger.info("[api/leads/list] success %s", {"count": len(records)})
    return [to_lead_read(record) for record in records]


@router.get("/pipeline-tasks/{task_id}", response_model=PipelineTaskStatusResponse)
async def get_pipeline_task_status(task_id: str) -> PipelineTaskStatusResponse:
    logger.info("[api/leads/pipeline-task] enter %s", {"task_id": task_id})
    try:
        task = celery_app.AsyncResult(task_id)
        result = task.result if task.successful() and isinstance(task.result, dict) else None
        error_type = task.result.__class__.__name__ if task.failed() else None
        status = task.status
    except Exception as exc:
        logger.exception(
            "[api/leads/pipeline-task] fail %s",
            {"task_id": task_id, "error": exc.__class__.__name__},
        )
        raise HTTPException(status_code=503, detail="Lead pipeline result backend is unavailable") from exc
    logger.info(
        "[api/leads/pipeline-task] success %s",
        {"task_id": task_id, "status": status, "error_type": error_type},
    )
    return PipelineTaskStatusResponse(
        task_id=task_id,
        status=status,
        result=result,
        error_type=error_type,
    )


@router.get("/{lead_id}/audit-events", response_model=list[AuditEventRead])
async def list_audit_events(lead_id: str, pool=Depends(get_pool)) -> list[AuditEventRead]:
    logger.info("[api/leads/audit] enter %s", {"lead_id": lead_id})
    repo = LeadRepository(pool)
    lead = await repo.get_lead(lead_id)
    if lead is None:
        logger.info("[api/leads/audit] not_found %s", {"lead_id": lead_id})
        raise HTTPException(status_code=404, detail="Lead not found")

    records = await repo.list_audit_events(lead_id)
    logger.info("[api/leads/audit] success %s", {"lead_id": lead_id, "count": len(records)})
    return [to_audit_event_read(record) for record in records]


@router.get("/{lead_id}/research", response_model=ResearchBriefRead)
async def get_research_brief(lead_id: str, pool=Depends(get_pool)) -> ResearchBriefRead:
    logger.info("[api/leads/research-get] enter %s", {"lead_id": lead_id})
    lead = await LeadRepository(pool).get_lead(lead_id)
    if lead is None:
        logger.info("[api/leads/research-get] not_found %s", {"lead_id": lead_id})
        raise HTTPException(status_code=404, detail="Lead not found")

    record = await ResearchRepository(pool).get(lead_id)
    if record is None:
        logger.info("[api/leads/research-get] no_record %s", {"lead_id": lead_id})
        raise HTTPException(status_code=404, detail="Research brief not found")

    logger.info(
        "[api/leads/research-get] success %s",
        {"lead_id": lead_id, "status": record.status, "source_count": len(record.source_refs)},
    )
    return to_research_read(record)


@router.post("/{lead_id}/research", response_model=ResearchQueuedResponse, status_code=202)
async def queue_research_brief(lead_id: str, pool=Depends(get_pool)) -> ResearchQueuedResponse:
    logger.info("[api/leads/research-queue] enter %s", {"lead_id": lead_id})
    repo = LeadRepository(pool)
    lead = await repo.get_lead(lead_id)
    if lead is None:
        logger.info("[api/leads/research-queue] not_found %s", {"lead_id": lead_id})
        raise HTTPException(status_code=404, detail="Lead not found")

    task_id = await enqueue_research(repo, ResearchRepository(pool), lead_id)
    logger.info("[api/leads/research-queue] success %s", {"lead_id": lead_id, "task_id": task_id})
    return ResearchQueuedResponse(lead_id=lead_id, task_id=task_id)


@router.put("/{lead_id}/extracted-fields", response_model=LeadRead)
async def persist_extracted_fields(
    lead_id: str,
    payload: PersistExtractedFieldsRequest,
    pool=Depends(get_pool),
) -> LeadRead:
    logger.info(
        "[api/leads/extracted-fields] enter %s",
        {
            "lead_id": lead_id,
            "provider": payload.provider,
            "model": payload.model,
            "temperature": payload.temperature,
            "email_coherence": payload.extracted.email_coherence,
            "visa_category_present": bool(payload.extracted.visa_category),
            "actor": payload.actor,
        },
    )
    record = await LeadRepository(pool).persist_extracted_fields(
        lead_id=lead_id,
        extracted=payload.extracted,
        provider=payload.provider,
        model=payload.model,
        temperature=payload.temperature,
        actor=payload.actor,
    )
    if record is None:
        logger.info("[api/leads/extracted-fields] not_found %s", {"lead_id": lead_id})
        raise HTTPException(status_code=404, detail="Lead not found")
    logger.info(
        "[api/leads/extracted-fields] success %s",
        {
            "lead_id": lead_id,
            "extracted_at": record.extracted_at.isoformat() if record.extracted_at else None,
            "email_coherence": record.email_coherence,
        },
    )
    return to_lead_read(record)


@router.post("/{lead_id}/score", response_model=LeadScoreResponse)
async def score_lead_with_llm(
    lead_id: str,
    pool=Depends(get_pool),
    settings: Settings = Depends(settings_from_request),
) -> LeadScoreResponse:
    triage = get_triage_service(settings)
    logger.info(
        "[api/leads/score] enter %s",
        {
            "lead_id": lead_id,
            "strategy": "dnq_precheck_then_llm",
            "provider": triage.provider,
            "model": triage.score_model,
        },
    )
    repo = LeadRepository(pool)
    lead = await repo.get_lead(lead_id)
    if lead is None:
        logger.info("[api/leads/score] not_found %s", {"lead_id": lead_id})
        raise HTTPException(status_code=404, detail="Lead not found")

    qualification = qualify_lead(lead)
    qualified_lead = await repo.persist_qualification(
        lead_id=lead_id,
        dnq_reason=qualification.dnq_reason,
        risk_flags=qualification.risk_flags,
        actor="score-api",
    )
    if qualified_lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")
    provider = "rules" if qualification.is_dnq else triage.provider
    model = "dnq-hard-rules-v1" if qualification.is_dnq else triage.score_model
    temperature = 0.0 if qualification.is_dnq else triage.score_temperature

    try:
        if qualification.is_dnq:
            if qualification.dnq_reason is None:
                raise RuntimeError("DNQ qualification did not include a reason")
            result = deterministic_dnq_score(qualification.dnq_reason, qualification.risk_flags)
        else:
            result = await triage.score_lead(qualified_lead)
    except RuntimeError as exc:
        logger.error("[api/leads/score] config_error %s", {"error": str(exc)})
        raise HTTPException(status_code=503, detail="LLM scoring is not configured") from exc
    except Exception as exc:
        logger.error("[api/leads/score] fail %s", {"lead_id": lead_id, "error": exc.__class__.__name__})
        raise HTTPException(status_code=502, detail="LLM scoring failed") from exc

    record = await repo.persist_score(
        lead_id=lead_id,
        result=result,
        provider=provider,
        model=model,
        temperature=temperature,
        actor=provider,
    )
    if record is None:
        logger.info("[api/leads/score] not_found_after_llm %s", {"lead_id": lead_id})
        raise HTTPException(status_code=404, detail="Lead not found")

    logger.info(
        "[api/leads/score] success %s",
        {
            "lead_id": lead_id,
            "lead_score": result.lead_score,
            "score_confidence": result.score_confidence,
            "escalation_flag": result.escalation_flag,
            "dnq_reason": qualification.dnq_reason,
            "llm_skipped": qualification.is_dnq,
        },
    )
    return LeadScoreResponse(
        provider=provider,
        model=model,
        temperature=temperature,
        result=result,
    )


@router.put("/{lead_id}/score", response_model=LeadRead)
async def persist_score(
    lead_id: str,
    payload: PersistLeadScoreRequest,
    pool=Depends(get_pool),
) -> LeadRead:
    logger.info(
        "[api/leads/score-persist] enter %s",
        {
            "lead_id": lead_id,
            "provider": payload.provider,
            "model": payload.model,
            "temperature": payload.temperature,
            "lead_score": payload.result.lead_score,
            "score_confidence": payload.result.score_confidence,
            "actor": payload.actor,
        },
    )
    record = await LeadRepository(pool).persist_score(
        lead_id=lead_id,
        result=payload.result,
        provider=payload.provider,
        model=payload.model,
        temperature=payload.temperature,
        actor=payload.actor,
    )
    if record is None:
        logger.info("[api/leads/score-persist] not_found %s", {"lead_id": lead_id})
        raise HTTPException(status_code=404, detail="Lead not found")
    logger.info(
        "[api/leads/score-persist] success %s",
        {"lead_id": lead_id, "lead_score": record.lead_score, "status": record.status},
    )
    return to_lead_read(record)


@router.post("/{lead_id}/drafts", response_model=DraftResponse)
async def draft_lead_with_llm(
    lead_id: str,
    pool=Depends(get_pool),
    settings: Settings = Depends(settings_from_request),
) -> DraftResponse:
    triage = get_triage_service(settings)
    logger.info(
        "[api/leads/drafts] enter %s",
        {"lead_id": lead_id, "provider": triage.provider, "model": triage.draft_model},
    )
    repo = LeadRepository(pool)
    lead = await repo.get_lead(lead_id)
    if lead is None:
        logger.info("[api/leads/drafts] not_found %s", {"lead_id": lead_id})
        raise HTTPException(status_code=404, detail="Lead not found")

    try:
        result = await triage.draft_for_lead(lead)
    except RuntimeError as exc:
        logger.error("[api/leads/drafts] config_error %s", {"error": str(exc)})
        raise HTTPException(status_code=503, detail="LLM drafting is not configured") from exc
    except Exception as exc:
        logger.error("[api/leads/drafts] fail %s", {"lead_id": lead_id, "error": exc.__class__.__name__})
        raise HTTPException(status_code=502, detail="LLM drafting failed") from exc

    record = await repo.persist_drafts(
        lead_id=lead_id,
        result=result,
        provider=draft_provider(result, triage),
        model=draft_model(result, triage),
        temperature=draft_temperature(result, triage),
        actor=draft_provider(result, triage),
    )
    if record is None:
        logger.info("[api/leads/drafts] not_found_after_llm %s", {"lead_id": lead_id})
        raise HTTPException(status_code=404, detail="Lead not found")

    logger.info(
        "[api/leads/drafts] success %s",
        {
            "lead_id": lead_id,
            "provider": draft_provider(result, triage),
            "template_id": result.template_id,
            "has_whatsapp": bool(result.whatsapp_draft),
            "has_phone_script": bool(result.phone_script),
        },
    )
    return DraftResponse(
        provider=draft_provider(result, triage),
        model=draft_model(result, triage),
        temperature=draft_temperature(result, triage),
        result=result,
    )


@router.put("/{lead_id}/drafts", response_model=LeadRead)
async def persist_drafts(
    lead_id: str,
    payload: PersistDraftsRequest,
    pool=Depends(get_pool),
) -> LeadRead:
    logger.info(
        "[api/leads/drafts-persist] enter %s",
        {
            "lead_id": lead_id,
            "provider": payload.provider,
            "model": payload.model,
            "temperature": payload.temperature,
            "has_whatsapp": bool(payload.result.whatsapp_draft),
            "has_phone_script": bool(payload.result.phone_script),
            "actor": payload.actor,
        },
    )
    record = await LeadRepository(pool).persist_drafts(
        lead_id=lead_id,
        result=payload.result,
        provider=payload.provider,
        model=payload.model,
        temperature=payload.temperature,
        actor=payload.actor,
    )
    if record is None:
        logger.info("[api/leads/drafts-persist] not_found %s", {"lead_id": lead_id})
        raise HTTPException(status_code=404, detail="Lead not found")
    logger.info(
        "[api/leads/drafts-persist] success %s",
        {"lead_id": lead_id, "drafted_at": record.drafted_at.isoformat() if record.drafted_at else None},
    )
    return to_lead_read(record)


@router.post("/{lead_id}/pipeline", response_model=PipelineQueuedResponse, status_code=202)
async def enqueue_lead_pipeline_run(
    lead_id: str,
    pool=Depends(get_pool),
) -> PipelineQueuedResponse:
    logger.info(
        "[api/leads/pipeline] enter %s",
        {"lead_id": lead_id, "mode": "celery_enqueue"},
    )
    repo = LeadRepository(pool)
    lead = await repo.get_lead(lead_id)
    if lead is None:
        logger.info("[api/leads/pipeline] not_found %s", {"lead_id": lead_id})
        raise HTTPException(status_code=404, detail="Lead not found")

    task_id = await enqueue_pipeline(repo, lead_id, "pipeline-api")
    logger.info(
        "[api/leads/pipeline] success %s",
        {"lead_id": lead_id, "task_id": task_id, "status": "queued"},
    )
    return PipelineQueuedResponse(lead_id=lead_id, task_id=task_id)


@router.post("/{lead_id}/approve", response_model=LeadRead)
async def approve_lead(
    lead_id: str,
    pool=Depends(get_pool),
    current_user: CurrentUser = Depends(require_permission("lead.approve")),
) -> LeadRead:
    logger.info(
        "[api/leads/approve] enter %s",
        {"lead_id": lead_id, "actor": current_user.user_id, "auth_disabled": current_user.is_auth_disabled},
    )
    record, blocked_reason = await LeadRepository(pool).approve_for_send(lead_id, current_user.user_id)
    if blocked_reason == "same_actor":
        logger.info("[api/leads/approve] denied %s", {"lead_id": lead_id, "reason": blocked_reason})
        raise HTTPException(status_code=409, detail="Second reviewer must be different from draft editor")
    if record is None:
        logger.info("[api/leads/approve] not_found %s", {"lead_id": lead_id})
        raise HTTPException(status_code=404, detail="Lead not found")
    logger.info("[api/leads/approve] success %s", {"lead_id": lead_id, "status": record.status})
    return to_lead_read(record)


@router.post("/{lead_id}/reject", response_model=LeadRead)
async def reject_lead(
    lead_id: str,
    payload: LeadActionRequest | None = None,
    pool=Depends(get_pool),
    current_user: CurrentUser = Depends(require_permission("lead.reject")),
) -> LeadRead:
    logger.info(
        "[api/leads/reject] enter %s",
        {
            "lead_id": lead_id,
            "actor": current_user.user_id,
            "reason_present": bool(payload and payload.reason),
        },
    )
    record = await LeadRepository(pool).reject_review(
        lead_id,
        current_user.user_id,
        payload.reason if payload else None,
    )
    if record is None:
        logger.info("[api/leads/reject] not_found %s", {"lead_id": lead_id})
        raise HTTPException(status_code=404, detail="Lead not found")
    logger.info("[api/leads/reject] success %s", {"lead_id": lead_id, "status": record.status})
    return to_lead_read(record)


@router.post("/{lead_id}/reject-confirm", response_model=LeadRead)
async def confirm_lead_rejection(
    lead_id: str,
    payload: LeadActionRequest | None = None,
    pool=Depends(get_pool),
    current_user: CurrentUser = Depends(require_permission("lead.reject.confirm")),
) -> LeadRead:
    logger.info(
        "[api/leads/reject-confirm] enter %s",
        {
            "lead_id": lead_id,
            "actor": current_user.user_id,
            "reason_present": bool(payload and payload.reason),
        },
    )
    record = await LeadRepository(pool).confirm_rejection(
        lead_id,
        current_user.user_id,
        payload.reason if payload else None,
    )
    if record is None:
        logger.info("[api/leads/reject-confirm] not_found %s", {"lead_id": lead_id})
        raise HTTPException(status_code=404, detail="Lead not found")
    logger.info("[api/leads/reject-confirm] success %s", {"lead_id": lead_id, "status": record.status})
    return to_lead_read(record)


@router.post("/{lead_id}/edit-draft", response_model=LeadRead)
async def edit_lead_draft(
    lead_id: str,
    payload: DraftEditRequest,
    pool=Depends(get_pool),
    current_user: CurrentUser = Depends(require_permission("lead.draft.edit")),
) -> LeadRead:
    logger.info(
        "[api/leads/edit-draft] enter %s",
        {
            "lead_id": lead_id,
            "actor": current_user.user_id,
            "email_draft_changed": payload.email_draft is not None,
            "whatsapp_changed": payload.whatsapp_draft is not None,
            "phone_script_changed": payload.phone_script is not None,
            "internal_post_changed": payload.internal_whatsapp_post is not None,
            "reason_present": bool(payload.reason),
        },
    )
    record = await LeadRepository(pool).edit_draft(
        lead_id,
        current_user.user_id,
        email_draft=payload.email_draft,
        whatsapp_draft=payload.whatsapp_draft,
        phone_script=payload.phone_script,
        internal_whatsapp_post=payload.internal_whatsapp_post,
        reason=payload.reason,
    )
    if record is None:
        logger.info("[api/leads/edit-draft] not_found %s", {"lead_id": lead_id})
        raise HTTPException(status_code=404, detail="Lead not found")
    logger.info("[api/leads/edit-draft] success %s", {"lead_id": lead_id, "status": record.status})
    return to_lead_read(record)


@router.patch("/{lead_id}/fields", response_model=LeadRead)
async def edit_lead_fields(
    lead_id: str,
    payload: LeadFieldEditRequest,
    pool=Depends(get_pool),
    current_user: CurrentUser = Depends(require_permission("lead.draft.edit")),
) -> LeadRead:
    fields = {
        field: getattr(payload, field)
        for field in payload.model_fields_set
    }
    logger.info(
        "[api/leads/edit-fields] enter %s",
        {
            "lead_id": lead_id,
            "actor": current_user.user_id,
            "fields": sorted(fields),
            "contains_private_fields": bool({"name", "email", "phone"} & set(fields)),
        },
    )
    try:
        record = await LeadRepository(pool).edit_fields(
            lead_id=lead_id,
            actor=current_user.user_id,
            fields={
                key: str(value) if key == "email" and value is not None else value.value if key == "brand" and value is not None else value
                for key, value in fields.items()
            },
        )
    except ValueError as exc:
        logger.info("[api/leads/edit-fields] invalid %s", {"lead_id": lead_id, "reason": str(exc)})
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    if record is None:
        logger.info("[api/leads/edit-fields] not_found %s", {"lead_id": lead_id})
        raise HTTPException(status_code=404, detail="Lead not found")
    logger.info(
        "[api/leads/edit-fields] success %s",
        {"lead_id": lead_id, "status": record.status, "field_count": len(fields)},
    )
    return to_lead_read(record)


@router.get("/{lead_id}", response_model=LeadRead)
async def get_lead(lead_id: str, pool=Depends(get_pool)) -> LeadRead:
    logger.info("[api/leads/get] enter %s", {"lead_id": lead_id})
    record = await LeadRepository(pool).get_lead(lead_id)
    if record is None:
        logger.info("[api/leads/get] not_found %s", {"lead_id": lead_id})
        raise HTTPException(status_code=404, detail="Lead not found")
    logger.info("[api/leads/get] success %s", {"lead_id": lead_id, "status": record.status})
    return to_lead_read(record)


@router.patch("/{lead_id}/status", response_model=LeadRead)
async def update_lead_status(
    lead_id: str,
    payload: LeadStatusUpdate,
    pool=Depends(get_pool),
    current_user: CurrentUser = Depends(get_current_user),
) -> LeadRead:
    logger.info(
        "[api/leads/status] enter %s",
        {"lead_id": lead_id, "status": payload.status, "actor": current_user.user_id},
    )
    record = await LeadRepository(pool).update_status(
        lead_id=lead_id,
        status=payload.status,
        actor=current_user.user_id,
    )
    if record is None:
        logger.info("[api/leads/status] not_found %s", {"lead_id": lead_id})
        raise HTTPException(status_code=404, detail="Lead not found")
    logger.info(
        "[api/leads/status] success %s",
        {"lead_id": lead_id, "status": record.status},
    )
    return to_lead_read(record)
