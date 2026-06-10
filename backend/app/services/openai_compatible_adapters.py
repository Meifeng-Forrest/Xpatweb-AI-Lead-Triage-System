import logging

from pydantic import ValidationError

from app.repositories.leads import LeadRecord
from app.schemas import DraftResult, EmailExtractionRequest, ExtractedEmailFields, LeadScoreResult
from app.services.extraction_contract import (
    EXTRACTION_TEMPERATURE,
    build_email_extraction_prompt,
    build_manual_extraction_prompt,
)
from app.services.openai_compatible import OpenAICompatibleJsonClient
from app.services.triage_contract import (
    DRAFT_SCHEMA,
    OPENAI_COMPATIBLE_TRIAGE_TEMPERATURE,
    SCORE_TEMPERATURE,
    SCORE_SCHEMA,
    build_draft_prompt,
    build_score_prompt,
    with_schema,
)
from app.services.visa_templates import build_template_draft

logger = logging.getLogger("lead_triage.services.openai_compatible_adapters")


class OpenAICompatibleExtractionAdapter:
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
        self.client = OpenAICompatibleJsonClient(
            provider=provider,
            base_url=base_url,
            api_key=api_key,
            model=model,
            logger=logger,
            thinking_disabled=True,
        )

    async def extract_manual_text(self, raw_text: str) -> ExtractedEmailFields:
        return await self._extract(
            prompt=build_manual_extraction_prompt(raw_text),
            summary={"raw_text_length": len(raw_text)},
        )

    async def extract_email_fields(self, payload: EmailExtractionRequest) -> ExtractedEmailFields:
        return await self._extract(
            prompt=build_email_extraction_prompt(payload),
            summary={
                "source_box": payload.source_box.value,
                "subject_present": bool(payload.email_subject),
                "from_present": bool(payload.email_from),
                "body_length": len(payload.email_body),
            },
        )

    async def _extract(self, *, prompt: str, summary: dict) -> ExtractedEmailFields:
        tag = f"[llm/{self.provider}/extract]"
        data = await self.client.generate_json(
            tag=tag,
            prompt=prompt,
            temperature=self.temperature,
            summary=summary,
            max_tokens=1400,
        )
        try:
            return ExtractedEmailFields.model_validate(data)
        except ValidationError:
            logger.exception("%s validation_fail %s", tag, {"field_count": len(data)})
            raise


class OpenAICompatibleTriageAdapter:
    def __init__(
        self,
        *,
        provider: str,
        base_url: str,
        api_key: str,
        model: str,
        thinking_disabled: bool = False,
    ) -> None:
        self.provider = provider
        self.score_model = model
        self.draft_model = model
        # Kimi k2.6 当前只接受 temperature=1.0；其他 provider 仍保持评分温度 0，
        # 这样既能通过 Kimi 兼容性限制，也不牺牲 Shengsuanyun/Gemini 路径的确定性。
        self.score_temperature = 1.0 if provider == "kimi" else SCORE_TEMPERATURE
        self.draft_temperature = OPENAI_COMPATIBLE_TRIAGE_TEMPERATURE
        self.client = OpenAICompatibleJsonClient(
            provider=provider,
            base_url=base_url,
            api_key=api_key,
            model=model,
            logger=logger,
            thinking_disabled=thinking_disabled,
        )

    async def score_lead(self, lead: LeadRecord) -> LeadScoreResult:
        tag = f"[llm/{self.provider}/score]"
        data = await self.client.generate_json(
            tag=tag,
            prompt=with_schema(build_score_prompt(lead), SCORE_SCHEMA),
            temperature=self.score_temperature,
            summary={"lead_id": lead.lead_id, "source_box": lead.source_box},
            max_tokens=1800,
        )
        try:
            return LeadScoreResult.model_validate(data)
        except ValidationError:
            logger.exception("%s validation_fail %s", tag, {"lead_id": lead.lead_id})
            raise

    async def draft_for_lead(self, lead: LeadRecord) -> DraftResult:
        template_draft = build_template_draft(lead)
        if template_draft is not None:
            logger.info(
                "[llm/template/draft] skipped_llm_template_match %s",
                {
                    "lead_id": lead.lead_id,
                    "source_box": lead.source_box,
                    "lead_score": lead.lead_score,
                    "template_id": template_draft.template_id,
                },
            )
            return template_draft

        tag = f"[llm/{self.provider}/draft]"
        data = await self.client.generate_json(
            tag=tag,
            prompt=with_schema(build_draft_prompt(lead), DRAFT_SCHEMA),
            temperature=self.draft_temperature,
            summary={"lead_id": lead.lead_id, "source_box": lead.source_box, "lead_score": lead.lead_score},
            max_tokens=1200,
        )
        try:
            return DraftResult.model_validate(data)
        except ValidationError:
            logger.exception("%s validation_fail %s", tag, {"lead_id": lead.lead_id})
            raise
