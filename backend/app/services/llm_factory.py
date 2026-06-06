from typing import Protocol

from app.config import Settings
from app.repositories.leads import LeadRecord
from app.schemas import DraftResult, EmailExtractionRequest, ExtractedEmailFields, LeadScoreResult
from app.services.native_json_adapters import NativeJsonExtractionAdapter, NativeJsonTriageAdapter
from app.services.openai_compatible_adapters import (
    OpenAICompatibleExtractionAdapter,
    OpenAICompatibleTriageAdapter,
)


class ExtractionService(Protocol):
    provider: str
    model: str
    temperature: float

    async def extract_manual_text(self, raw_text: str) -> ExtractedEmailFields: ...

    async def extract_email_fields(self, payload: EmailExtractionRequest) -> ExtractedEmailFields: ...


class TriageService(Protocol):
    provider: str
    score_model: str
    draft_model: str
    score_temperature: float
    draft_temperature: float

    async def score_lead(self, lead: LeadRecord) -> LeadScoreResult: ...

    async def draft_for_lead(self, lead: LeadRecord) -> DraftResult: ...


def get_extraction_service(settings: Settings) -> ExtractionService:
    # 默认沿用当前主链路；未来切换模型时只需要扩展这里和配置读取。
    return OpenAICompatibleExtractionAdapter(
        provider="shengsuanyun",
        base_url=settings.shengsuanyun_base_url,
        api_key=settings.shengsuanyun_api_key,
        model=settings.shengsuanyun_model,
    )


def get_email_extraction_service(settings: Settings) -> ExtractionService:
    return get_extraction_service(settings)


def get_native_json_extraction_service(settings: Settings) -> ExtractionService:
    return NativeJsonExtractionAdapter(
        provider="gemini",
        base_url=settings.gemini_base_url,
        api_key=settings.gemini_api_key,
        model=settings.gemini_model_extract,
    )


def get_triage_service(settings: Settings) -> TriageService:
    return OpenAICompatibleTriageAdapter(
        provider="kimi",
        base_url=settings.kimi_base_url,
        api_key=settings.kimi_api_key,
        model=settings.kimi_model,
        thinking_disabled=True,
    )


def get_native_json_triage_service(settings: Settings) -> TriageService:
    return NativeJsonTriageAdapter(
        provider="gemini",
        base_url=settings.gemini_base_url,
        api_key=settings.gemini_api_key,
        score_model=settings.gemini_model_score,
        draft_model=settings.gemini_model_draft,
    )
