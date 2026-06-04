import unittest
from types import SimpleNamespace

from app.config import Settings
from app.schemas import DraftResult, ExtractedEmailFields, LeadScoreResult
from app.services.lead_pipeline import LeadPipelineService


def extracted_fields(**overrides):
    values = {
        "sender_name": "Fixture",
        "email_address": "fixture@example.com",
        "contact_number": None,
        "email_domain": "other_personal",
        "lead_type": "Individual",
        "visa_category": "Retired Person Visa",
        "current_visa": None,
        "pr_route": None,
        "nationality": None,
        "is_first_world": None,
        "job_title": None,
        "net_worth_indicator": None,
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
        "additional_info": "Fixture",
    }
    values.update(overrides)
    return ExtractedEmailFields(**values)


class FakeExtraction:
    def __init__(self, extracted: ExtractedEmailFields) -> None:
        self.extracted = extracted

    async def extract_manual_text(self, _raw_text):
        return self.extracted


class FakeTriage:
    def __init__(self) -> None:
        self.score_calls = 0

    async def score_lead(self, _lead):
        self.score_calls += 1
        return LeadScoreResult(
            lead_score="GD",
            score_confidence="high",
            score_rationale="Fixture score",
            escalation_flag=False,
            soft_dnq_warning=None,
        )

    async def draft_for_lead(self, _lead):
        return DraftResult(
            email_draft="Fixture draft",
            whatsapp_draft=None,
            phone_script=None,
            internal_whatsapp_post=None,
        )


class FakeRepo:
    def __init__(self, lead) -> None:
        self.lead = lead
        self.steps: list[str] = []

    async def persist_extracted_fields(self, **_kwargs):
        self.steps.append("extract")
        return self.lead

    async def persist_qualification(self, **kwargs):
        self.steps.append("dnq")
        self.lead.dnq_reason = kwargs["dnq_reason"]
        self.lead.risk_flags = list(kwargs["risk_flags"])
        return self.lead

    async def persist_score(self, **kwargs):
        self.steps.append("score")
        self.lead.lead_score = kwargs["result"].lead_score
        return self.lead

    async def persist_drafts(self, **_kwargs):
        self.steps.append("draft")
        self.lead.status = "dnq" if self.lead.dnq_reason else "drafted"
        return self.lead


class LeadPipelineTest(unittest.IsolatedAsyncioTestCase):
    async def test_pipeline_runs_in_order_and_skips_llm_score_for_dnq(self) -> None:
        lead = SimpleNamespace(
            lead_id="lead-fixture",
            source_box="XP",
            email_address="fixture@example.com",
            raw_message="Critical Skills without a job offer",
            dnq_reason=None,
            risk_flags=[],
        )
        repo = FakeRepo(lead)
        service = LeadPipelineService(repo, Settings())
        service.extraction = FakeExtraction(
            extracted_fields(visa_category="Critical Skills Work Visa", has_job_offer=False)
        )
        triage = FakeTriage()
        service.triage = triage

        result = await service.run(lead)

        self.assertEqual(repo.steps, ["extract", "dnq", "score", "draft"])
        self.assertTrue(result.scoring_skipped)
        self.assertEqual(result.qualification.dnq_reason, "DNQ-01")
        self.assertEqual(triage.score_calls, 0)

    async def test_pipeline_calls_llm_score_when_no_dnq_matches(self) -> None:
        lead = SimpleNamespace(
            lead_id="lead-fixture",
            source_box="XP",
            email_address="fixture@example.com",
            raw_message="Retired Person Visa enquiry",
            dnq_reason=None,
            risk_flags=[],
        )
        repo = FakeRepo(lead)
        service = LeadPipelineService(repo, Settings())
        service.extraction = FakeExtraction(extracted_fields())
        triage = FakeTriage()
        service.triage = triage

        result = await service.run(lead)

        self.assertEqual(repo.steps, ["extract", "dnq", "score", "draft"])
        self.assertFalse(result.scoring_skipped)
        self.assertEqual(triage.score_calls, 1)

    async def test_confirmed_manual_pipeline_skips_extraction(self) -> None:
        lead = SimpleNamespace(
            lead_id="lead-confirmed",
            source_box="RISA",
            email_address="fixture@example.com",
            raw_message="Original pasted text",
            visa_category="Retired Person Visa",
            has_job_offer=None,
            dnq_reason=None,
            risk_flags=[],
        )
        repo = FakeRepo(lead)
        service = LeadPipelineService(repo, Settings())
        triage = FakeTriage()
        service.triage = triage

        result = await service.run(lead, skip_extraction=True)

        self.assertEqual(repo.steps, ["dnq", "score", "draft"])
        self.assertFalse(result.scoring_skipped)
        self.assertEqual(triage.score_calls, 1)


if __name__ == "__main__":
    unittest.main()
