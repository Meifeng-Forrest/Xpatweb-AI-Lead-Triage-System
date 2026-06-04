import json
import logging

from pydantic import ValidationError

from app.config import Settings
from app.repositories.leads import LeadRecord
from app.schemas import DraftResult, LeadScoreResult
from app.services.gemini_triage import DRAFT_SCHEMA, SCORE_SCHEMA, build_draft_prompt, build_score_prompt
from app.services.openai_compatible import OpenAICompatibleJsonClient

logger = logging.getLogger("lead_triage.services.kimi_triage")

KIMI_TEMPERATURE = 0.6


def with_schema(prompt: str, schema: dict) -> str:
    return f"{prompt}\n\nReturn one JSON object matching this JSON Schema:\n{json.dumps(schema, ensure_ascii=False)}"


class KimiTriageService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = OpenAICompatibleJsonClient(
            provider="kimi",
            base_url=settings.kimi_base_url,
            api_key=settings.kimi_api_key,
            model=settings.kimi_model,
            logger=logger,
            thinking_disabled=True,
        )

    async def score_lead(self, lead: LeadRecord) -> LeadScoreResult:
        data = await self.client.generate_json(
            tag="[llm/kimi/score]",
            prompt=with_schema(build_score_prompt(lead), SCORE_SCHEMA),
            temperature=KIMI_TEMPERATURE,
            summary={"lead_id": lead.lead_id, "source_box": lead.source_box},
            max_tokens=700,
        )
        try:
            return LeadScoreResult.model_validate(data)
        except ValidationError:
            logger.exception("[llm/kimi/score] validation_fail %s", {"lead_id": lead.lead_id})
            raise

    async def draft_for_lead(self, lead: LeadRecord) -> DraftResult:
        data = await self.client.generate_json(
            tag="[llm/kimi/draft]",
            prompt=with_schema(build_draft_prompt(lead), DRAFT_SCHEMA),
            temperature=KIMI_TEMPERATURE,
            summary={"lead_id": lead.lead_id, "source_box": lead.source_box, "lead_score": lead.lead_score},
            max_tokens=1200,
        )
        try:
            return DraftResult.model_validate(data)
        except ValidationError:
            logger.exception("[llm/kimi/draft] validation_fail %s", {"lead_id": lead.lead_id})
            raise
