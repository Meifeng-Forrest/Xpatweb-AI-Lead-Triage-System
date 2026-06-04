import asyncio
import logging
import time

import asyncpg
import httpx

from app.celery_app import celery_app
from app.config import get_settings
from app.database import create_pool, init_schema
from app.repositories.leads import LeadRepository
from app.services.lead_pipeline import LeadPipelineService

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
