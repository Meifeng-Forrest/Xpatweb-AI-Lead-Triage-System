import json
import unittest
from datetime import date
from pathlib import Path

from app.services.lead_pipeline import deterministic_dnq_score
from app.services.qualification_rules import qualify_lead


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "lead_regression_cases.json"


class LeadRegressionCasesTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cases = json.loads(FIXTURE_PATH.read_text())

    def test_fixture_contains_minimum_mvp_coverage(self) -> None:
        ids = {case["id"] for case in self.cases}

        for reason in ("DNQ-01", "DNQ-02", "DNQ-03", "DNQ-04", "DNQ-05", "DNQ-06"):
            self.assertTrue(
                any(case["expected"]["dnq_reason"] == reason for case in self.cases),
                f"missing fixture for {reason}",
            )
        self.assertIn("risk_01_pbs_low_salary_soft_only", ids)
        self.assertIn("risk_02_weak_visitor_11_6_soft_only", ids)
        self.assertIn("unknown_job_offer_not_auto_dnq", ids)

    def test_deterministic_qualification_regression_cases(self) -> None:
        matches = 0
        failures: list[dict[str, object]] = []
        for case in self.cases:
            as_of = date.fromisoformat(case["as_of"])
            result = qualify_lead(case["input"], as_of=as_of)
            actual = {
                "is_dnq": result.is_dnq,
                "dnq_reason": result.dnq_reason,
                "risk_flags": list(result.risk_flags),
            }
            expected = case["expected"]
            if actual == expected:
                matches += 1
            else:
                failures.append({"id": case["id"], "expected": expected, "actual": actual})

        consistency = matches / len(self.cases)
        self.assertGreaterEqual(consistency, 0.85, failures)
        self.assertEqual(failures, [])

    def test_dnq_cases_persist_as_deterministic_bd_scores(self) -> None:
        for case in self.cases:
            expected = case["expected"]
            if expected["dnq_reason"] is None:
                continue

            score = deterministic_dnq_score(expected["dnq_reason"], tuple(expected["risk_flags"]))

            self.assertEqual(score.lead_score, "BD", case["id"])
            self.assertEqual(score.score_confidence, "high", case["id"])
            self.assertFalse(score.escalation_flag, case["id"])


if __name__ == "__main__":
    unittest.main()
