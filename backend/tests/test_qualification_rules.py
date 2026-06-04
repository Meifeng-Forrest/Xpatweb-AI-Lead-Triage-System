import unittest
from datetime import date

from app.services.qualification_rules import apply_dnq_rules, apply_risk_flags


class QualificationRulesTest(unittest.TestCase):
    def test_dnq_01_critical_skills_without_offer(self) -> None:
        self.assertEqual(
            apply_dnq_rules({"visa_category": "Critical Skills Work Visa", "has_job_offer": False}),
            (True, "DNQ-01"),
        )

    def test_dnq_02_pr_without_current_visa(self) -> None:
        self.assertEqual(
            apply_dnq_rules({"visa_category": "PR (Financially Independent)", "current_visa": None}),
            (True, "DNQ-02"),
        )

    def test_dnq_03_work_route_under_four_years(self) -> None:
        self.assertEqual(
            apply_dnq_rules(
                {
                    "visa_category": "Permanent Residence Permit",
                    "current_visa": "General Work Visa",
                    "pr_route": "work_visa",
                    "qualifying_work_visa_years": 3.9,
                }
            ),
            (True, "DNQ-03"),
        )

    def test_dnq_04_traditional_marriage(self) -> None:
        self.assertEqual(
            apply_dnq_rules(
                {"visa_category": "Visitors Visa Section 11(6)", "marriage_type": "traditional"}
            ),
            (True, "DNQ-04"),
        )

    def test_dnq_05_appeal_beyond_ten_working_days(self) -> None:
        self.assertEqual(
            apply_dnq_rules(
                {"visa_category": "Appeal Application", "rejection_date": "2026-05-15"},
                as_of=date(2026, 6, 1),
            ),
            (True, "DNQ-05"),
        )

    def test_dnq_06_visitor_11_1_first_world(self) -> None:
        self.assertEqual(
            apply_dnq_rules(
                {"visa_category": "Visitors Visa Section 11(1)", "is_first_world": True}
            ),
            (True, "DNQ-06"),
        )

    def test_unknown_facts_do_not_trigger_hard_dnq(self) -> None:
        self.assertEqual(
            apply_dnq_rules({"visa_category": "Critical Skills Work Visa", "has_job_offer": None}),
            (False, None),
        )

    def test_soft_rules_never_become_hard_dnq(self) -> None:
        extracted = {
            "visa_category": "Points-Based System",
            "annual_salary_zar": 600_000,
            "pbs_total_score_below_100": True,
        }
        self.assertEqual(apply_dnq_rules(extracted), (False, None))
        self.assertEqual(apply_risk_flags(extracted), ("RISK-01",))


if __name__ == "__main__":
    unittest.main()
