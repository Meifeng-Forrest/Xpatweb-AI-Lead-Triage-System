import logging
from dataclasses import dataclass

from app.config import Settings
from app.repositories.leads import LeadRecord
from app.schemas import ResearchBriefFields

logger = logging.getLogger("lead_triage.services.research")


class WebSearchNotConfigured(RuntimeError):
    pass


@dataclass(frozen=True)
class ResearchRunResult:
    brief: ResearchBriefFields
    source_refs: list[dict[str, str]]


class LeadResearchService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def research_lead(self, lead: LeadRecord) -> ResearchRunResult:
        logger.info(
            "[research/lead] enter %s",
            {
                "lead_id": lead.lead_id,
                "source_box": lead.source_box,
                "email_domain": lead.email_domain,
                "provider_configured": bool(self.settings.web_search_provider),
                "api_key_configured": bool(self.settings.web_search_api_key),
            },
        )

        if not self.settings.web_search_provider or not self.settings.web_search_api_key:
            logger.info(
                "[research/lead] skipped %s",
                {"lead_id": lead.lead_id, "reason": "web_search_not_configured"},
            )
            raise WebSearchNotConfigured("Web Search provider is not configured.")

        # 这里暂不接具体供应商，避免在无真实搜索来源时生成看似真实的背景。
        # 接 Tavily/SerpAPI/Google CSE 时，应在这里写入来源 URL，再交给 LLM 总结。
        raise WebSearchNotConfigured(f"Unsupported Web Search provider: {self.settings.web_search_provider}")
