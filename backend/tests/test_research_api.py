import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.api.leads import get_research_brief, queue_research_brief
from app.repositories.research import ResearchBriefRecord
from app.services.research import LeadResearchService, WebSearchNotConfigured
from app.config import Settings


def lead_record():
    return SimpleNamespace(
        lead_id="lead-research",
        sender_name="Research Lead",
        email_address="lead@example.com",
        email_domain="example.com",
        source_box="XP",
        raw_message="Research fixture",
    )


def research_record(status="queued"):
    now = datetime.now(UTC)
    return ResearchBriefRecord(
        lead_id="lead-research",
        status=status,
        task_id="task-research",
        brief=None,
        source_refs=[],
        error_type=None,
        error_message=None,
        created_at=now,
        updated_at=now,
        completed_at=None,
    )


class FakeLeadRepo:
    async def get_lead(self, lead_id):
        return lead_record() if lead_id == "lead-research" else None

    async def append_audit_event(self, **_kwargs):
        return True


class FakeResearchRepo:
    def __init__(self, record=None) -> None:
        self.record = record or research_record()

    async def get(self, _lead_id):
        return self.record

    async def mark_queued(self, lead_id, task_id):
        self.record = research_record()
        self.record = ResearchBriefRecord(
            lead_id=lead_id,
            status="queued",
            task_id=task_id,
            brief=None,
            source_refs=[],
            error_type=None,
            error_message=None,
            created_at=self.record.created_at,
            updated_at=self.record.updated_at,
            completed_at=None,
        )
        return self.record


class ResearchApiTest(unittest.IsolatedAsyncioTestCase):
    async def test_queue_research_uses_existing_async_task(self) -> None:
        with (
            patch("app.api.leads.LeadRepository", return_value=FakeLeadRepo()),
            patch("app.api.leads.ResearchRepository", return_value=FakeResearchRepo()),
            patch("app.api.leads.enqueue_research", new=AsyncMock(return_value="task-research")),
        ):
            response = await queue_research_brief("lead-research", pool=object())

        self.assertEqual(response.lead_id, "lead-research")
        self.assertEqual(response.task_id, "task-research")

    async def test_get_research_returns_stored_status(self) -> None:
        with (
            patch("app.api.leads.LeadRepository", return_value=FakeLeadRepo()),
            patch("app.api.leads.ResearchRepository", return_value=FakeResearchRepo(research_record("failed"))),
        ):
            response = await get_research_brief("lead-research", pool=object())

        self.assertEqual(response.status, "failed")
        self.assertEqual(response.task_id, "task-research")

    async def test_research_service_refuses_to_fabricate_without_web_search(self) -> None:
        service = LeadResearchService(Settings(WEB_SEARCH_PROVIDER="", WEB_SEARCH_API_KEY=""))

        with self.assertRaises(WebSearchNotConfigured):
            await service.research_lead(lead_record())


if __name__ == "__main__":
    unittest.main()
