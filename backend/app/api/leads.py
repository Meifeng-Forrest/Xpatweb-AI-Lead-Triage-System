import logging
import json
from uuid import uuid4
from typing import Any

from celery.exceptions import CeleryError
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from kombu.exceptions import KombuError

from app.celery_app import celery_app
from app.config import Settings, get_settings
from app.database import get_pool
from app.logging import summarize_email, summarize_text
from app.repositories.leads import LeadRepository
from app.schemas import (
    AuditEventRead,
    DraftResponse,
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
)
from app.services.kimi_triage import KIMI_TEMPERATURE, KimiTriageService
from app.services.lead_pipeline import deterministic_dnq_score
from app.services.qualification_rules import qualify_lead
from app.tasks import run_lead_pipeline as run_lead_pipeline_task

router = APIRouter(prefix="/api/v1/leads", tags=["leads"])
logger = logging.getLogger("lead_triage.api.leads")


def settings_from_request(request: Request) -> Settings:
    return getattr(request.app.state, "settings", get_settings())


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
async def score_lead_with_kimi(
    lead_id: str,
    pool=Depends(get_pool),
    settings: Settings = Depends(settings_from_request),
) -> LeadScoreResponse:
    logger.info(
        "[api/leads/score] enter %s",
        {
            "lead_id": lead_id,
            "strategy": "dnq_precheck_then_kimi",
            "model": settings.kimi_model,
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
    provider = "rules" if qualification.is_dnq else "kimi"
    model = "dnq-hard-rules-v1" if qualification.is_dnq else settings.kimi_model

    try:
        if qualification.is_dnq:
            if qualification.dnq_reason is None:
                raise RuntimeError("DNQ qualification did not include a reason")
            result = deterministic_dnq_score(qualification.dnq_reason, qualification.risk_flags)
        else:
            result = await KimiTriageService(settings).score_lead(qualified_lead)
    except RuntimeError as exc:
        logger.error("[api/leads/score] config_error %s", {"error": str(exc)})
        raise HTTPException(status_code=503, detail="Kimi scoring is not configured") from exc
    except Exception as exc:
        logger.error("[api/leads/score] fail %s", {"lead_id": lead_id, "error": exc.__class__.__name__})
        raise HTTPException(status_code=502, detail="Kimi scoring failed") from exc

    record = await repo.persist_score(
        lead_id=lead_id,
        result=result,
        provider=provider,
        model=model,
        temperature=KIMI_TEMPERATURE,
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
        temperature=KIMI_TEMPERATURE,
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
async def draft_lead_with_kimi(
    lead_id: str,
    pool=Depends(get_pool),
    settings: Settings = Depends(settings_from_request),
) -> DraftResponse:
    logger.info(
        "[api/leads/drafts] enter %s",
        {"lead_id": lead_id, "provider": "kimi", "model": settings.kimi_model},
    )
    repo = LeadRepository(pool)
    lead = await repo.get_lead(lead_id)
    if lead is None:
        logger.info("[api/leads/drafts] not_found %s", {"lead_id": lead_id})
        raise HTTPException(status_code=404, detail="Lead not found")

    try:
        result = await KimiTriageService(settings).draft_for_lead(lead)
    except RuntimeError as exc:
        logger.error("[api/leads/drafts] config_error %s", {"error": str(exc)})
        raise HTTPException(status_code=503, detail="Kimi drafting is not configured") from exc
    except Exception as exc:
        logger.error("[api/leads/drafts] fail %s", {"lead_id": lead_id, "error": exc.__class__.__name__})
        raise HTTPException(status_code=502, detail="Kimi drafting failed") from exc

    record = await repo.persist_drafts(
        lead_id=lead_id,
        result=result,
        provider="kimi",
        model=settings.kimi_model,
        temperature=KIMI_TEMPERATURE,
        actor="kimi",
    )
    if record is None:
        logger.info("[api/leads/drafts] not_found_after_llm %s", {"lead_id": lead_id})
        raise HTTPException(status_code=404, detail="Lead not found")

    logger.info(
        "[api/leads/drafts] success %s",
        {
            "lead_id": lead_id,
            "has_whatsapp": bool(result.whatsapp_draft),
            "has_phone_script": bool(result.phone_script),
        },
    )
    return DraftResponse(
        provider="kimi",
        model=settings.kimi_model,
        temperature=KIMI_TEMPERATURE,
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
) -> LeadRead:
    logger.info(
        "[api/leads/status] enter %s",
        {"lead_id": lead_id, "status": payload.status, "actor": payload.actor},
    )
    record = await LeadRepository(pool).update_status(
        lead_id=lead_id,
        status=payload.status,
        actor=payload.actor,
    )
    if record is None:
        logger.info("[api/leads/status] not_found %s", {"lead_id": lead_id})
        raise HTTPException(status_code=404, detail="Lead not found")
    logger.info(
        "[api/leads/status] success %s",
        {"lead_id": lead_id, "status": record.status},
    )
    return to_lead_read(record)
