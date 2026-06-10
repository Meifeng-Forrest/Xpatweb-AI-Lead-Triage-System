import unittest

from scripts.run_scoring_regression import calculate_metrics, run_regression


class ScoringRegressionRunnerTest(unittest.IsolatedAsyncioTestCase):
    def test_calculate_metrics(self) -> None:
        metrics = calculate_metrics(
            [
                {"expected_score": "GD", "actual_score": "GD"},
                {"expected_score": "GD", "actual_score": "MD"},
                {"expected_score": "BD", "actual_score": "BD"},
            ]
        )

        self.assertEqual(metrics["total"], 3)
        self.assertEqual(metrics["correct"], 2)
        self.assertEqual(metrics["accuracy"], 0.6667)
        self.assertEqual(metrics["recall"], {"BD": 1.0, "GD": 0.5})

    async def test_dry_run_uses_expected_scores_without_model_call(self) -> None:
        report = await run_regression(limit=3, dry_run=True, service_name="native-gemini")

        self.assertEqual(report["metrics"]["total"], 3)
        self.assertEqual(report["metrics"]["accuracy"], 1.0)
        self.assertEqual(len(report["results"]), 3)
        self.assertTrue(all(row["score_confidence"] == "dry_run" for row in report["results"]))

    async def test_row_ids_filter_cases_for_targeted_runs(self) -> None:
        report = await run_regression(row_ids={190, 144}, dry_run=True, service_name="shengsuanyun-openai")

        self.assertEqual(report["metrics"]["total"], 2)
        self.assertEqual({row["row_id"] for row in report["results"]}, {190, 144})
        self.assertEqual(report["metrics"]["accuracy"], 1.0)


if __name__ == "__main__":
    unittest.main()
