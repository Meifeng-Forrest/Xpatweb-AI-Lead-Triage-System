import unittest
from types import SimpleNamespace

from app.services.visa_templates import (
    ADDITIONAL_SERVICE_TEMPLATES,
    ALL_DRAFT_TEMPLATES,
    DNQ_TEMPLATES,
    TOP_10_TEMPLATES,
    build_template_draft,
    find_template,
)


def lead(**overrides):
    values = {
        "lead_id": "lead-template-fixture",
        "sender_name": "Alex Client",
        "source_box": "XP",
        "visa_category": "Retired Person Visa",
        "lead_score": "MF",
        "dnq_reason": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class VisaTemplatesTest(unittest.TestCase):
    def test_top_10_template_catalog_has_approved_fee_source(self) -> None:
        self.assertEqual(len(TOP_10_TEMPLATES), 10)
        template_ids = {template.template_id for template in TOP_10_TEMPLATES}
        self.assertEqual(len(template_ids), 10)
        for template in TOP_10_TEMPLATES:
            self.assertTrue(template.professional_fee_zar.startswith("R"))

    def test_template_catalog_covers_business_spec_fee_items(self) -> None:
        self.assertGreaterEqual(len(ADDITIONAL_SERVICE_TEMPLATES), 18)
        self.assertGreaterEqual(len(ALL_DRAFT_TEMPLATES), 28)

        expected_templates = {
            "TMPL_POSITIVE_BUSINESS_VISA",
            "TMPL_POSITIVE_CORPORATE_VISA",
            "TMPL_POSITIVE_IMMIGRATION_AUDIT",
            "TMPL_POSITIVE_VISITOR_11_1",
            "TMPL_POSITIVE_MEDICAL_TREATMENT_VISA",
            "TMPL_SERVICE_VISA_ASSESSMENT",
            "TMPL_SERVICE_FORMAL_VERIFICATION",
            "TMPL_SERVICE_INFORMAL_VERIFICATION",
            "TMPL_SERVICE_POLICE_CLEARANCE",
            "TMPL_SERVICE_SAQA_CERTIFICATE",
            "TMPL_SERVICE_ESCALATORY_LETTERS",
            "TMPL_SERVICE_COURT_APPLICATION",
        }
        self.assertTrue(expected_templates <= {template.template_id for template in ALL_DRAFT_TEMPLATES})

    def test_template_draft_uses_hardcoded_retired_person_fees(self) -> None:
        result = build_template_draft(lead())

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.template_id, "TMPL_POSITIVE_RETIRED_PERSON_VISA")
        self.assertEqual(result.professional_fee_zar, "R42,280")
        self.assertEqual(result.admin_fee_zar, "R2,480")
        self.assertEqual(result.fee_source, "doc/业务规格.md §3.3")
        self.assertIn("R42,280", result.email_draft)
        self.assertIn("R2,480", result.email_draft)

    def test_unknown_visa_does_not_generate_a_fee_quote(self) -> None:
        self.assertIsNone(find_template("Unlisted experimental visa"))
        self.assertIsNone(build_template_draft(lead(visa_category="Unlisted experimental visa")))

    def test_additional_service_templates_use_hardcoded_fees(self) -> None:
        result = build_template_draft(lead(visa_category="Visa Assessment"))

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.template_id, "TMPL_SERVICE_VISA_ASSESSMENT")
        self.assertEqual(result.professional_fee_zar, "R4,280")
        self.assertEqual(result.fee_source, "doc/业务规格.md §3.3")
        self.assertIn("R4,280", result.email_draft)

    def test_court_application_template_preserves_range_without_llm_quote(self) -> None:
        result = build_template_draft(lead(visa_category="Urgent Court Application"))

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.template_id, "TMPL_SERVICE_COURT_APPLICATION")
        self.assertIn("R114,500-R167,200", result.professional_fee_zar or "")
        self.assertIn("R114,500-R167,200", result.email_draft)

    def test_gd_template_prefers_consultation_booking(self) -> None:
        result = build_template_draft(lead(lead_score="GD", visa_category="Remote Work Visa", source_box="RISA"))

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.template_id, "TMPL_POSITIVE_REMOTE_WORK_VISA")
        self.assertIn("Retire In South Africa", result.email_draft)
        self.assertIn("schedule a brief consultation", result.email_draft)
        self.assertIsNotNone(result.phone_script)

    def test_all_dnq_reasons_have_refusal_templates(self) -> None:
        self.assertEqual(set(DNQ_TEMPLATES), {"DNQ-01", "DNQ-02", "DNQ-03", "DNQ-04", "DNQ-05", "DNQ-06"})
        for reason, template in DNQ_TEMPLATES.items():
            self.assertEqual(template.dnq_reason, reason)
            self.assertTrue(template.template_id.startswith("TMPL_DNQ_"))
            self.assertGreaterEqual(len(template.alternative_suggestions), 1)

    def test_dnq_template_takes_priority_over_positive_template(self) -> None:
        result = build_template_draft(
            lead(
                visa_category="Critical Skills Work Visa",
                lead_score="BD",
                dnq_reason="DNQ-01",
            )
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.template_id, "TMPL_DNQ_01_CRITICAL_SKILLS_NO_JOB_OFFER")
        self.assertEqual(result.visa_bucket, "DNQ")
        self.assertEqual(result.dnq_reason, "DNQ-01")
        self.assertIsNone(result.professional_fee_zar)
        self.assertIn("formal job offer", result.email_draft)
        self.assertIn("Route to Marisa/QA", result.internal_whatsapp_post or "")
        self.assertIn("reviewed before any final communication is sent", result.email_draft)
        self.assertNotIn("professional fee", result.email_draft.lower())
        self.assertIsNone(result.phone_script)
        self.assertGreaterEqual(len(result.alternative_suggestions), 1)

    def test_dnq_template_covers_visitor_11_1_without_positive_template(self) -> None:
        result = build_template_draft(
            lead(
                visa_category="Visitors Visa Section 11(1)",
                lead_score="BD",
                dnq_reason="DNQ-06",
            )
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.template_id, "TMPL_DNQ_06_VISITOR_11_1_VISA_EXEMPT")
        self.assertIn("visa-exempt", result.email_draft)
        self.assertIn("correct visa category", "\n".join(result.alternative_suggestions))


if __name__ == "__main__":
    unittest.main()
