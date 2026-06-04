import json
import logging

from pydantic import ValidationError

from app.config import Settings
from app.schemas import ExtractedEmailFields
from app.services.gemini_extraction import EXTRACTION_SCHEMA, EXTRACTION_TEMPERATURE
from app.services.openai_compatible import OpenAICompatibleJsonClient

logger = logging.getLogger("lead_triage.services.shengsuanyun_extraction")


def build_manual_extraction_prompt(raw_text: str) -> str:
    return f"""
You are a field extraction assistant for Xpatweb, a South African immigration consultancy.
Extract the structured fields from the pasted inquiry below.
Do NOT score, qualify, reject, draft a reply, or infer the receiving brand.
Do not invent facts. If a field is absent, output null, except:
- sender_name must be "Not Provided" when absent
- urgency_flag and multi_visa_flag must be false when absent
- email_coherence must be high, medium, or low

Return one JSON object matching this JSON Schema:
{json.dumps(EXTRACTION_SCHEMA, ensure_ascii=False)}

PASTED INQUIRY:
{raw_text}
""".strip()


class ShengSuanYunExtractionService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = OpenAICompatibleJsonClient(
            provider="shengsuanyun",
            base_url=settings.shengsuanyun_base_url,
            api_key=settings.shengsuanyun_api_key,
            model=settings.shengsuanyun_model,
            logger=logger,
        )

    async def extract_manual_text(self, raw_text: str) -> ExtractedEmailFields:
        data = await self.client.generate_json(
            tag="[llm/shengsuanyun/extract]",
            prompt=build_manual_extraction_prompt(raw_text),
            temperature=EXTRACTION_TEMPERATURE,
            summary={"raw_text_length": len(raw_text)},
            max_tokens=1400,
        )
        try:
            return ExtractedEmailFields.model_validate(data)
        except ValidationError:
            logger.exception(
                "[llm/shengsuanyun/extract] validation_fail %s",
                {"field_count": len(data)},
            )
            raise
