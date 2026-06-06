import json
import logging
import time
from typing import Any

import httpx
from pydantic import ValidationError

from app.repositories.leads import LeadRecord
from app.schemas import DraftResult, EmailExtractionRequest, ExtractedEmailFields, LeadScoreResult
from app.services.extraction_contract import (
    EXTRACTION_SCHEMA,
    EXTRACTION_TEMPERATURE,
    build_email_extraction_prompt,
    build_manual_extraction_prompt,
)
from app.services.triage_contract import (
    DRAFT_SCHEMA,
    DRAFT_TEMPERATURE,
    SCORE_SCHEMA,
    SCORE_TEMPERATURE,
    build_draft_prompt,
    build_score_prompt,
)

logger = logging.getLogger("lead_triage.services.native_json_adapters")


def provider_error_summary(exc: Exception) -> dict[str, Any]:
    if not isinstance(exc, httpx.HTTPStatusError):
        return {"status_code": None, "error_status": None, "error_reason": exc.__class__.__name__}

    error_status = None
    error_reason = None
    try:
        payload = exc.response.json()
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        error_status = error.get("status")
        for detail in error.get("details", []):
            if isinstance(detail, dict) and detail.get("reason"):
                error_reason = detail["reason"]
                break
    except ValueError:
        pass

    return {
        "status_code": exc.response.status_code,
        "error_status": error_status,
        "error_reason": error_reason,
    }


def extract_text_from_native_json_response(data: dict[str, Any]) -> str:
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError("Native JSON response did not contain generated JSON text") from exc


class NativeJsonClient:
    def __init__(
        self,
        *,
        provider: str,
        base_url: str,
        api_key: str,
    ) -> None:
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key

    def endpoint(self, model: str) -> str:
        return f"{self.base_url}/v1beta/models/{model}:generateContent"

    async def generate_json(
        self,
        *,
        tag: str,
        model: str,
        prompt: str,
        schema: dict[str, Any],
        temperature: float,
        summary: dict[str, Any],
    ) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError(f"{self.provider} API key is not configured")

        request_summary = {
            **summary,
            "provider": self.provider,
            "model": model,
            "temperature": temperature,
        }
        logger.info("%s enter %s", tag, request_summary)
        started_at = time.perf_counter()
        request_body = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": temperature,
                "responseMimeType": "application/json",
                "responseJsonSchema": schema,
            },
        }

        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.post(
                    self.endpoint(model),
                    headers={
                        "Content-Type": "application/json",
                        "x-goog-api-key": self.api_key,
                    },
                    json=request_body,
                )
            response.raise_for_status()
            text = extract_text_from_native_json_response(response.json())
            data = json.loads(text)
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
            logger.exception(
                "%s fail %s",
                tag,
                {
                    **request_summary,
                    "ms": round((time.perf_counter() - started_at) * 1000),
                    **provider_error_summary(exc),
                    "error": str(exc)[:300],
                },
            )
            raise

        logger.info(
            "%s success %s",
            tag,
            {**request_summary, "ms": round((time.perf_counter() - started_at) * 1000)},
        )
        return data


class NativeJsonExtractionAdapter:
    def __init__(
        self,
        *,
        provider: str,
        base_url: str,
        api_key: str,
        model: str,
    ) -> None:
        self.provider = provider
        self.model = model
        self.temperature = EXTRACTION_TEMPERATURE
        self.client = NativeJsonClient(provider=provider, base_url=base_url, api_key=api_key)

    async def extract_manual_text(self, raw_text: str) -> ExtractedEmailFields:
        return await self._generate_extraction(
            prompt=build_manual_extraction_prompt(raw_text),
            summary={"raw_text_length": len(raw_text)},
        )

    async def extract_email_fields(self, payload: EmailExtractionRequest) -> ExtractedEmailFields:
        return await self._generate_extraction(
            prompt=build_email_extraction_prompt(payload),
            summary={
                "source_box": payload.source_box.value,
                "subject_present": bool(payload.email_subject),
                "from_present": bool(payload.email_from),
                "body_length": len(payload.email_body),
            },
        )

    async def _generate_extraction(self, *, prompt: str, summary: dict[str, Any]) -> ExtractedEmailFields:
        tag = f"[llm/{self.provider}/extract]"
        data = await self.client.generate_json(
            tag=tag,
            model=self.model,
            prompt=prompt,
            schema=EXTRACTION_SCHEMA,
            temperature=self.temperature,
            summary=summary,
        )
        try:
            return ExtractedEmailFields.model_validate(data)
        except ValidationError:
            logger.exception("%s validation_fail %s", tag, {"field_count": len(data)})
            raise


class NativeJsonTriageAdapter:
    def __init__(
        self,
        *,
        provider: str,
        base_url: str,
        api_key: str,
        score_model: str,
        draft_model: str,
    ) -> None:
        self.provider = provider
        self.score_model = score_model
        self.draft_model = draft_model
        self.score_temperature = SCORE_TEMPERATURE
        self.draft_temperature = DRAFT_TEMPERATURE
        self.client = NativeJsonClient(provider=provider, base_url=base_url, api_key=api_key)

    async def score_lead(self, lead: LeadRecord) -> LeadScoreResult:
        tag = f"[llm/{self.provider}/score]"
        data = await self.client.generate_json(
            tag=tag,
            model=self.score_model,
            prompt=build_score_prompt(lead),
            schema=SCORE_SCHEMA,
            temperature=self.score_temperature,
            summary={
                "lead_id": lead.lead_id,
                "source_box": lead.source_box,
                "visa_category_present": bool(lead.visa_category),
                "email_coherence": lead.email_coherence,
            },
        )
        try:
            return LeadScoreResult.model_validate(data)
        except ValidationError:
            logger.exception("%s validation_fail %s", tag, {"lead_id": lead.lead_id})
            raise

    async def draft_for_lead(self, lead: LeadRecord) -> DraftResult:
        tag = f"[llm/{self.provider}/draft]"
        data = await self.client.generate_json(
            tag=tag,
            model=self.draft_model,
            prompt=build_draft_prompt(lead),
            schema=DRAFT_SCHEMA,
            temperature=self.draft_temperature,
            summary={
                "lead_id": lead.lead_id,
                "source_box": lead.source_box,
                "lead_score": lead.lead_score,
                "visa_category_present": bool(lead.visa_category),
            },
        )
        try:
            return DraftResult.model_validate(data)
        except ValidationError:
            logger.exception("%s validation_fail %s", tag, {"lead_id": lead.lead_id})
            raise
