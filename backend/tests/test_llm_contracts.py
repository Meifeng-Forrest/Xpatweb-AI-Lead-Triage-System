import unittest
from pathlib import Path
from types import SimpleNamespace

from app.schemas import EmailExtractionRequest, SourceBox
from app.services.extraction_contract import (
    EXTRACTION_SCHEMA,
    build_email_extraction_prompt,
    build_manual_extraction_prompt,
)
from app.services.lead_pipeline import draft_model, draft_provider, draft_temperature
from app.services.triage_contract import (
    DRAFT_SCHEMA,
    SCORE_SCHEMA,
    build_draft_prompt,
    build_score_prompt,
    with_schema,
)


ROOT = Path(__file__).resolve().parents[1]


def lead_fixture(**overrides):
    values = {
        "lead_id": "lead-fixture",
        "source_box": "XP",
        "lead_source": None,
        "sender_name": "Jane Doe",
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
        "lead_score": "GD",
        "dnq_reason": None,
        "risk_flags": [],
        "score_confidence": "high",
        "score_rationale": "Strong retirement signal",
        "soft_dnq_warning": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class LlmContractsTest(unittest.TestCase):
    def test_extraction_prompts_share_contract_schema(self) -> None:
        manual_prompt = build_manual_extraction_prompt("Jane asks about retirement.")
        email_prompt = build_email_extraction_prompt(
            EmailExtractionRequest(
                source_box=SourceBox.XP,
                email_subject="Retirement visa",
                email_from="Jane <jane@example.com>",
                email_body="I want to retire in South Africa.",
            )
        )

        self.assertIn("sender_name", EXTRACTION_SCHEMA["required"])
        self.assertIn("Do NOT score", manual_prompt)
        self.assertIn("XP", email_prompt)
        self.assertIn("Retirement visa", email_prompt)
        self.assertIn("JSON Schema", manual_prompt)
        self.assertIn("domestic worker", manual_prompt)
        self.assertIn("General Work Visa", manual_prompt)
        self.assertIn("Visa Assessment", email_prompt)
        self.assertIn("email_domain: classify", manual_prompt)
        self.assertIn("lead_type: Individual", manual_prompt)
        self.assertIn("annual_salary_zar", manual_prompt)
        self.assertIn("marriage_type", manual_prompt)

    def test_triage_prompts_share_contract_schema(self) -> None:
        lead = lead_fixture()

        score_prompt = build_score_prompt(lead)
        draft_prompt = build_draft_prompt(lead)
        schema_prompt = with_schema("Return data", SCORE_SCHEMA)

        self.assertIn("lead_score", SCORE_SCHEMA["required"])
        self.assertIn("email_draft", DRAFT_SCHEMA["required"])
        self.assertIn("Retired Person Visa", score_prompt)
        self.assertIn("doc/业务规格.md §10.3", score_prompt)
        self.assertIn("FEW-SHOT EXAMPLES FROM doc/业务规格.md §13.3", score_prompt)
        self.assertEqual(score_prompt.count("INPUT:"), 30)
        self.assertEqual(score_prompt.count("OUTPUT:"), 30)
        self.assertIn("domestic worker", score_prompt)
        self.assertIn("score BD with medium confidence", score_prompt)
        self.assertIn("one-employee or two-employee assessment", score_prompt)
        self.assertIn("High-volume corporate assessment", score_prompt)
        self.assertIn("expiring/expired visa", score_prompt)
        self.assertIn("Visitor 11(1)(b)(iii)", score_prompt)
        self.assertIn("premium value signal before lifting", score_prompt)
        self.assertIn("Do not invent prices", draft_prompt)
        self.assertIn("South African formal English", draft_prompt)
        self.assertIn("Do not use contractions", draft_prompt)
        self.assertIn("BD email_draft", draft_prompt)
        self.assertIn("JSON Schema", schema_prompt)

    def test_services_do_not_use_supplier_named_business_modules(self) -> None:
        service_files = {path.name for path in (ROOT / "app/services").glob("*.py")}

        self.assertFalse({"gemini_extraction.py", "gemini_triage.py", "kimi_triage.py"} & service_files)
        self.assertFalse({"shengsuanyun_extraction.py", "gemini_http.py"} & service_files)
        factory_source = (ROOT / "app/services/llm_factory.py").read_text()
        self.assertIn("OpenAICompatibleExtractionAdapter", factory_source)
        self.assertIn("NativeJsonExtractionAdapter", factory_source)

    def test_draft_metadata_uses_template_or_triage_provider(self) -> None:
        triage = SimpleNamespace(provider="fake-llm", draft_model="fake-draft", draft_temperature=0.7)

        llm_result = SimpleNamespace(template_id=None)
        template_result = SimpleNamespace(template_id="TMPL_TEST")

        self.assertEqual(draft_provider(llm_result, triage), "fake-llm")
        self.assertEqual(draft_model(llm_result, triage), "fake-draft")
        self.assertEqual(draft_temperature(llm_result, triage), 0.7)
        self.assertEqual(draft_provider(template_result, triage), "template")
        self.assertEqual(draft_model(template_result, triage), "TMPL_TEST")
        self.assertEqual(draft_temperature(template_result, triage), 0.0)


if __name__ == "__main__":
    unittest.main()
