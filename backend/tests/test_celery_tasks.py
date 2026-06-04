import unittest
from unittest.mock import AsyncMock, patch

from app.tasks import _run_lead_pipeline


class CeleryPipelineTaskTest(unittest.IsolatedAsyncioTestCase):
    async def test_task_runs_pipeline_and_writes_lifecycle_audit(self) -> None:
        lead = object()
        pipeline_result = type(
            "PipelineResult",
            (),
            {
                "lead": type("Lead", (), {"status": type("Status", (), {"value": "drafted"})()})(),
                "qualification": type("Qualification", (), {"is_dnq": False})(),
                "scoring_skipped": False,
            },
        )()
        repo = type(
            "Repo",
            (),
            {
                "get_lead": AsyncMock(return_value=lead),
                "append_audit_event": AsyncMock(return_value=True),
            },
        )()
        pool = type("Pool", (), {"close": AsyncMock()})()

        with (
            patch("app.tasks.create_pool", AsyncMock(return_value=pool)),
            patch("app.tasks.init_schema", AsyncMock()),
            patch("app.tasks.LeadRepository", return_value=repo),
            patch("app.tasks.LeadPipelineService") as service_class,
        ):
            service_class.return_value.run = AsyncMock(return_value=pipeline_result)
            result = await _run_lead_pipeline("lead-fixture", "task-fixture", 0)

        self.assertEqual(result["status"], "drafted")
        self.assertEqual(repo.append_audit_event.await_count, 2)
        self.assertEqual(
            [call.kwargs["event_type"] for call in repo.append_audit_event.await_args_list],
            ["lead.pipeline.started", "lead.pipeline.succeeded"],
        )
        pool.close.assert_awaited_once()

    async def test_task_writes_failed_audit_before_reraising(self) -> None:
        repo = type(
            "Repo",
            (),
            {
                "get_lead": AsyncMock(side_effect=RuntimeError("database read failed")),
                "append_audit_event": AsyncMock(return_value=True),
            },
        )()
        pool = type("Pool", (), {"close": AsyncMock()})()

        with (
            patch("app.tasks.create_pool", AsyncMock(return_value=pool)),
            patch("app.tasks.init_schema", AsyncMock()),
            patch("app.tasks.LeadRepository", return_value=repo),
        ):
            with self.assertRaises(RuntimeError):
                await _run_lead_pipeline("lead-fixture", "task-fixture", 1)

        self.assertEqual(repo.append_audit_event.await_args.kwargs["event_type"], "lead.pipeline.failed")
        self.assertEqual(repo.append_audit_event.await_args.kwargs["metadata"]["error_type"], "RuntimeError")
        pool.close.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
