import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.api.leads import enqueue_pipeline


class PipelineEnqueueTest(unittest.IsolatedAsyncioTestCase):
    async def test_enqueue_uses_celery_task_and_writes_audit(self) -> None:
        repo = SimpleNamespace(append_audit_event=AsyncMock(return_value=True))
        celery_result = SimpleNamespace(id="task-fixture")

        with patch("app.api.leads.run_lead_pipeline_task.apply_async", return_value=celery_result) as apply_async:
            task_id = await enqueue_pipeline(repo, "lead-fixture", "test")

        self.assertEqual(task_id, "task-fixture")
        apply_async.assert_called_once_with(args=["lead-fixture", False])
        repo.append_audit_event.assert_awaited_once()
        self.assertEqual(repo.append_audit_event.await_args.kwargs["event_type"], "lead.pipeline.queued")
        self.assertFalse(repo.append_audit_event.await_args.kwargs["metadata"]["skip_extraction"])


if __name__ == "__main__":
    unittest.main()
