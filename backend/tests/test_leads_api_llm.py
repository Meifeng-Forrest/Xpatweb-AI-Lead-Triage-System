import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.api.leads import draft_lead_with_llm, score_lead_with_llm
from app.config import Settings
from app.schemas import DraftResult, LeadScoreResult


def lead_fixture(**overrides):
    values = {
        "lead_id": "lead-fixture",
        "source_box": "XP",
        "lead_source": None,
        "sender_name": "Jane Doe",
        "email_address": "jane@example.com",
        "email_domain": "corporate",
        "visa_category": "Retired Person Visa",
        "lead_type": "Individual",
        "current_visa": None,
        "pr_route": None,
        "nationality": "British",
        "is_first_world": True,
        "job_title": "Director",
        "net_worth_indicator": "Retirement income",
        "has_job_offer": None,
        "qualifying_work_visa_years": None,
        "annual_salary_zar": None,
        "pbs_total_score_below_100": None,
        "relationship_duration": None,
        "marriage_type": None,
        "rejection_date": None,
        "urgency_flag": False,
        "multi_visa_flag": False,
        "email_coherence": "high",
        "additional_info": "Retirement enquiry",
        "extracted_fields": {},
        "lead_score": None,
        "dnq_reason": None,
        "risk_flags": [],
        "score_confidence": None,
        "score_rationale": None,
        "soft_dnq_warning": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class FakeRepo:
    def __init__(self, lead) -> None:
        self.lead = lead
        self.persisted_score = None
        self.persisted_drafts = None

    async def get_lead(self, _lead_id):
        return self.lead

    async def persist_qualification(self, **kwargs):
        self.lead.dnq_reason = kwargs["dnq_reason"]
        self.lead.risk_flags = list(kwargs["risk_flags"])
        return self.lead

    async def persist_score(self, **kwargs):
        self.persisted_score = kwargs
        return self.lead

    async def persist_drafts(self, **kwargs):
        self.persisted_drafts = kwargs
        return self.lead


class FakeTriage:
    def __init__(self, draft_result: DraftResult | None = None) -> None:
        self.provider = "fake-llm"
        self.score_model = "fake-score-model"
        self.draft_model = "fake-draft-model"
        self.score_temperature = 0.33
        self.draft_temperature = 0.44
        self.draft_result = draft_result

    async def score_lead(self, _lead):
        return LeadScoreResult(
            lead_score="GD",
            score_confidence="high",
            score_rationale="Fixture score",
            escalation_flag=False,
            soft_dnq_warning=None,
        )

    async def draft_for_lead(self, _lead):
        if self.draft_result is None:
            return DraftResult(
                email_draft="Fixture draft",
                whatsapp_draft=None,
                phone_script=None,
                internal_whatsapp_post=None,
            )
        return self.draft_result


class LeadsApiLlmTest(unittest.IsolatedAsyncioTestCase):
    async def test_score_api_returns_selected_llm_provider_for_non_dnq(self) -> None:
        repo = FakeRepo(lead_fixture())
        triage = FakeTriage()

        with (
            patch("app.api.leads.LeadRepository", return_value=repo),
            patch("app.api.leads.get_triage_service", return_value=triage),
        ):
            response = await score_lead_with_llm("lead-fixture", pool=object(), settings=Settings())

        self.assertEqual(response.provider, "fake-llm")
        self.assertEqual(response.model, "fake-score-model")
        self.assertEqual(response.temperature, 0.33)
        self.assertEqual(repo.persisted_score["provider"], "fake-llm")

    async def test_draft_api_returns_template_provider_for_template_result(self) -> None:
        repo = FakeRepo(lead_fixture(lead_score="GD"))
        triage = FakeTriage(
            DraftResult(
                email_draft="Template draft",
                whatsapp_draft=None,
                phone_script=None,
                internal_whatsapp_post=None,
                template_id="TMPL_TEST",
            )
        )

        with (
            patch("app.api.leads.LeadRepository", return_value=repo),
            patch("app.api.leads.get_triage_service", return_value=triage),
        ):
            response = await draft_lead_with_llm("lead-fixture", pool=object(), settings=Settings())

        self.assertEqual(response.provider, "template")
        self.assertEqual(response.model, "TMPL_TEST")
        self.assertEqual(response.temperature, 0.0)
        self.assertEqual(repo.persisted_drafts["provider"], "template")


if __name__ == "__main__":
    unittest.main()
