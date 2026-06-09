import unittest

from app.services.scoring_examples import (
    SCORING_FEW_SHOT_CASES,
    SCORING_REGRESSION_CASES,
    render_few_shot_examples,
    score_distribution,
)


class ScoringExamplesTest(unittest.TestCase):
    def test_few_shot_distribution_matches_business_spec(self) -> None:
        self.assertEqual(len(SCORING_FEW_SHOT_CASES), 30)
        self.assertEqual(
            score_distribution(SCORING_FEW_SHOT_CASES, "lead_score"),
            {"GD": 10, "MF": 8, "MD": 6, "BD": 6},
        )

    def test_regression_distribution_matches_business_spec(self) -> None:
        self.assertEqual(len(SCORING_REGRESSION_CASES), 40)
        self.assertEqual(
            score_distribution(SCORING_REGRESSION_CASES, "expected_score"),
            {"GD": 12, "MF": 6, "MD": 10, "BD": 12},
        )

    def test_few_shot_and_regression_rows_do_not_overlap(self) -> None:
        few_shot_rows = {case["row_id"] for case in SCORING_FEW_SHOT_CASES}
        regression_rows = {case["row_id"] for case in SCORING_REGRESSION_CASES}

        self.assertEqual(few_shot_rows & regression_rows, set())

    def test_bad_labels_are_mapped_to_bd_enum(self) -> None:
        self.assertNotIn("Bad", score_distribution(SCORING_FEW_SHOT_CASES, "lead_score"))
        self.assertNotIn("Bad", score_distribution(SCORING_REGRESSION_CASES, "expected_score"))

    def test_rendered_few_shots_are_prompt_ready(self) -> None:
        rendered = render_few_shot_examples()

        self.assertEqual(rendered.count("INPUT:"), 30)
        self.assertEqual(rendered.count("OUTPUT:"), 30)
        self.assertIn("OUTPUT: BD", rendered)


if __name__ == "__main__":
    unittest.main()
