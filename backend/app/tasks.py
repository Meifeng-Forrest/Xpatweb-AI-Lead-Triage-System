import asyncio
import logging
import time

import asyncpg
import httpx

from app.celery_app import celery_app
from app.config import get_settings
from app.database import create_pool, init_schema
from app.repositories.leads import LeadRepository
from app.repositories.research import ResearchRepository
from app.services.lead_pipeline import LeadPipelineService
from app.services.research import LeadResearchService, WebSearchNotConfigured

logger = logging.getLogger("lead_triage.tasks")


async def _run_lead_pipeline(
    lead_id: str,
    task_id: str,
    retry_count: int,
    skip_extraction: bool = False,
) -> dict[str, object]:
    settings = get_settings()
    pool = await create_pool(settings)
    repo = LeadRepository(pool)
    started_at = time.perf_counter()
    try:
        await init_schema(pool)
        lead = await repo.get_lead(lead_id)
        if lead is None:
            logger.error("[task/pipeline] not_found %s", {"lead_id": lead_id, "task_id": task_id})
            raise LookupError(f"Lead not found: {lead_id}")

        await repo.append_audit_event(
            lead_id=lead_id,
            event_type="lead.pipeline.started",
            actor="celery",
            metadata={"task_id": task_id, "retry_count": retry_count},
        )
        logger.info(
            "[task/pipeline] enter %s",
            {"lead_id": lead_id, "task_id": task_id, "retry_count": retry_count, "skip_extraction": skip_extraction},
        )

        result = await LeadPipelineService(repo, settings).run(lead, skip_extraction=skip_extraction)
        elapsed_ms = round((time.perf_counter() - started_at) * 1000)
        await repo.append_audit_event(
            lead_id=lead_id,
            event_type="lead.pipeline.succeeded",
            actor="celery",
            metadata={
                "task_id": task_id,
                "retry_count": retry_count,
                "status": result.lead.status.value,
                "is_dnq": result.qualification.is_dnq,
                "scoring_skipped": result.scoring_skipped,
                "ms": elapsed_ms,
                "skip_extraction": skip_extraction,
            },
        )
        logger.info(
            "[task/pipeline] success %s",
            {
                "lead_id": lead_id,
                "task_id": task_id,
                "status": result.lead.status,
                "is_dnq": result.qualification.is_dnq,
                "ms": elapsed_ms,
            },
        )
        return {
            "lead_id": lead_id,
            "status": result.lead.status.value,
            "is_dnq": result.qualification.is_dnq,
            "scoring_skipped": result.scoring_skipped,
        }
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started_at) * 1000)
        await repo.append_audit_event(
            lead_id=lead_id,
            event_type="lead.pipeline.failed",
            actor="celery",
            metadata={
                "task_id": task_id,
                "retry_count": retry_count,
                "error_type": exc.__class__.__name__,
                "ms": elapsed_ms,
            },
            require_lead=False,
        )
        logger.exception(
            "[task/pipeline] fail %s",
            {
                "lead_id": lead_id,
                "task_id": task_id,
                "retry_count": retry_count,
                "error": exc.__class__.__name__,
                "ms": elapsed_ms,
            },
        )
        raise
    finally:
        await pool.close()


@celery_app.task(
    bind=True,
    name="app.tasks.run_lead_pipeline",
    max_retries=3,
)
def run_lead_pipeline(self, lead_id: str, skip_extraction: bool = False) -> dict[str, object]:
    task_id = self.request.id or "unknown"
    retry_count = int(self.request.retries or 0)
    try:
        return asyncio.run(_run_lead_pipeline(lead_id, task_id, retry_count, skip_extraction))
    except httpx.HTTPStatusError as exc:
        status_code = exc.response.status_code
        if status_code == 429 or status_code >= 500:
            raise self.retry(exc=exc, countdown=min(2**retry_count, 60)) from exc
        raise
    except (httpx.TransportError, asyncpg.PostgresError) as exc:
        raise self.retry(exc=exc, countdown=min(2**retry_count, 60)) from exc


async def _run_lead_research(lead_id: str, task_id: str, retry_count: int) -> dict[str, object]:
    settings = get_settings()
    pool = await create_pool(settings)
    leads = LeadRepository(pool)
    research = ResearchRepository(pool)
    started_at = time.perf_counter()
    try:
        await init_schema(pool)
        lead = await leads.get_lead(lead_id)
        if lead is None:
            logger.error("[task/research] not_found %s", {"lead_id": lead_id, "task_id": task_id})
            raise LookupError(f"Lead not found: {lead_id}")

        await research.mark_running(lead_id, task_id)
        await leads.append_audit_event(
            lead_id=lead_id,
            event_type="lead.research.started",
            actor="celery",
            metadata={"task_id": task_id, "retry_count": retry_count},
        )
        logger.info("[task/research] enter %s", {"lead_id": lead_id, "task_id": task_id, "retry_count": retry_count})

        result = await LeadResearchService(settings).research_lead(lead)
        record = await research.mark_succeeded(lead_id, brief=result.brief, source_refs=result.source_refs)
        elapsed_ms = round((time.perf_counter() - started_at) * 1000)
        await leads.append_audit_event(
            lead_id=lead_id,
            event_type="lead.research.succeeded",
            actor="celery",
            metadata={"task_id": task_id, "source_count": len(record.source_refs), "ms": elapsed_ms},
        )
        logger.info("[task/research] success %s", {"lead_id": lead_id, "task_id": task_id, "ms": elapsed_ms})
        return {"lead_id": lead_id, "status": record.status, "source_count": len(record.source_refs)}
    except WebSearchNotConfigured as exc:
        record = await research.mark_failed(lead_id, error_type=exc.__class__.__name__, error_message=str(exc))
        await leads.append_audit_event(
            lead_id=lead_id,
            event_type="lead.research.failed",
            actor="celery",
            metadata={"task_id": task_id, "error_type": exc.__class__.__name__, "retry_count": retry_count},
            require_lead=False,
        )
        logger.info("[task/research] not_configured %s", {"lead_id": lead_id, "task_id": task_id})
        return {"lead_id": lead_id, "status": record.status, "error_type": record.error_type}
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - started_at) * 1000)
        await research.mark_failed(lead_id, error_type=exc.__class__.__name__, error_message="Research task failed")
        await leads.append_audit_event(
            lead_id=lead_id,
            event_type="lead.research.failed",
            actor="celery",
            metadata={"task_id": task_id, "error_type": exc.__class__.__name__, "retry_count": retry_count, "ms": elapsed_ms},
            require_lead=False,
        )
        logger.exception("[task/research] fail %s", {"lead_id": lead_id, "task_id": task_id, "error": exc.__class__.__name__})
        raise
    finally:
        await pool.close()


@celery_app.task(
    bind=True,
    name="app.tasks.run_lead_research",
    max_retries=2,
)
def run_lead_research(self, lead_id: str) -> dict[str, object]:
    task_id = self.request.id or "unknown"
    retry_count = int(self.request.retries or 0)
    try:
        return asyncio.run(_run_lead_research(lead_id, task_id, retry_count))
    except (httpx.TransportError, asyncpg.PostgresError) as exc:
        raise self.retry(exc=exc, countdown=min(2**retry_count, 60)) from exc
