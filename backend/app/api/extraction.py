import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.config import Settings, get_settings
from app.logging import summarize_text
from app.schemas import EmailExtractionRequest, EmailExtractionResponse, ManualExtractionRequest
from app.services.llm_factory import get_email_extraction_service, get_extraction_service

router = APIRouter(prefix="/api/v1/extraction", tags=["extraction"])
logger = logging.getLogger("lead_triage.api.extraction")


def settings_from_request(request: Request) -> Settings:
    return getattr(request.app.state, "settings", get_settings())


@router.post("/manual", response_model=EmailExtractionResponse)
async def extract_manual_text(
    payload: ManualExtractionRequest,
    settings: Settings = Depends(settings_from_request),
) -> EmailExtractionResponse:
    service = get_extraction_service(settings)
    logger.info(
        "[api/extraction/manual] enter %s",
        {
            "raw_text": summarize_text(payload.raw_text),
            "provider": service.provider,
            "model": service.model,
            "temperature": service.temperature,
        },
    )
    try:
        extracted = await service.extract_manual_text(payload.raw_text)
    except RuntimeError as exc:
        logger.error("[api/extraction/manual] config_error %s", {"error": str(exc)})
        raise HTTPException(status_code=503, detail="LLM extraction is not configured") from exc
    except Exception as exc:
        logger.error(
            "[api/extraction/manual] fail %s",
            {"error": exc.__class__.__name__, "raw_text_length": len(payload.raw_text)},
        )
        raise HTTPException(status_code=502, detail="LLM extraction failed") from exc

    logger.info(
        "[api/extraction/manual] success %s",
        {
            "provider": service.provider,
            "model": service.model,
            "visa_category_present": bool(extracted.visa_category),
            "email_present": bool(extracted.email_address),
        },
    )
    return EmailExtractionResponse(
        provider=service.provider,
        model=service.model,
        temperature=service.temperature,
        extracted=extracted,
    )


@router.post("/email", response_model=EmailExtractionResponse)
async def extract_email_fields(
    payload: EmailExtractionRequest,
    settings: Settings = Depends(settings_from_request),
) -> EmailExtractionResponse:
    service = get_email_extraction_service(settings)
    logger.info(
        "[api/extraction/email] enter %s",
        {
            "source_box": payload.source_box,
            "subject": summarize_text(payload.email_subject),
            "body": summarize_text(payload.email_body),
            "provider": service.provider,
            "model": service.model,
            "temperature": service.temperature,
        },
    )

    try:
        extracted = await service.extract_email_fields(payload)
    except RuntimeError as exc:
        logger.error("[api/extraction/email] config_error %s", {"error": str(exc)})
        raise HTTPException(status_code=503, detail="LLM extraction is not configured") from exc
    except Exception as exc:
        logger.error(
            "[api/extraction/email] fail %s",
            {"source_box": payload.source_box, "error": exc.__class__.__name__},
        )
        raise HTTPException(status_code=502, detail="LLM extraction failed") from exc

    logger.info(
        "[api/extraction/email] success %s",
        {
            "source_box": payload.source_box,
            "provider": service.provider,
            "model": service.model,
            "visa_category_present": bool(extracted.visa_category),
        },
    )
    return EmailExtractionResponse(
        provider=service.provider,
        model=service.model,
        temperature=service.temperature,
        extracted=extracted,
    )
