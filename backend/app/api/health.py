from fastapi import APIRouter, Depends

from app.config import Settings, get_settings
from app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=HealthResponse)
async def healthz(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        environment=settings.environment,
        configured_mailboxes=settings.configured_mailbox_count,
        database_configured=bool(settings.database_url),
        redis_configured=bool(settings.redis_url),
        llm_configured=settings.llm_api_key_configured,
        graph_configured=bool(
            settings.ms_tenant_id and settings.ms_client_id and settings.ms_client_secret
        ),
    )
