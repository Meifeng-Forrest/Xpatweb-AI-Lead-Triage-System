import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.leads import approve_lead, edit_lead_draft, edit_lead_fields, reject_lead, router as leads_router
from app.database import get_pool
from app.repositories.leads import LeadRepository
from app.schemas import DraftEditRequest, LeadActionRequest, LeadFieldEditRequest, LeadStatus
from app.services.auth import CurrentUser, get_current_user, permissions_for_roles


def current_user(user_id: str = "usr-reviewer", roles: tuple[str, ...] = ("approver",)) -> CurrentUser:
    return CurrentUser(
        user_id=user_id,
        email="reviewer@example.com",
        display_name="Reviewer",
        roles=roles,
        permissions=permissions_for_roles(roles),
    )


def lead_record(status: LeadStatus = LeadStatus.IN_REVIEW):
    return SimpleNamespace(
        lead_id="lead-fixture",
        sender_name="Jane",
        email_address="jane@example.com",
        raw_message="Original fixture message",
        contact_number=None,
        email_domain="example.com",
        visa_category="Retired Person Visa",
        lead_type=None,
        current_visa=None,
        pr_route=None,
        nationality=None,
        is_first_world=None,
        job_title=None,
        net_worth_indicator=None,
        has_job_offer=None,
        qualifying_work_visa_years=None,
        annual_salary_zar=None,
        pbs_total_score_below_100=None,
        relationship_duration=None,
        marriage_type=None,
        rejection_date=None,
        urgency_flag=None,
        multi_visa_flag=None,
        email_coherence=None,
        additional_info=None,
        extracted_fields={},
        extracted_at=None,
        extraction_provider=None,
        extraction_model=None,
        extraction_temperature=None,
        lead_score="GD",
        dnq_reason=None,
        risk_flags=[],
        score_confidence="high",
        score_rationale="Fixture",
        escalation_flag=False,
        soft_dnq_warning=None,
        score_provider=None,
        score_model=None,
        score_temperature=None,
        scored_at=None,
        email_draft="Draft",
        whatsapp_draft=None,
        phone_script=None,
        internal_whatsapp_post=None,
        draft_fields={},
        draft_provider=None,
        draft_model=None,
        draft_temperature=None,
        drafted_at=None,
        source_box="XP",
        lead_source=None,
        assigned_consultant=None,
        status=status,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


class FakeReviewRepo:
    def __init__(self) -> None:
        self.calls = []

    async def approve_for_send(self, lead_id, actor):
        self.calls.append(("approve", lead_id, actor))
        return lead_record(LeadStatus.SENT), None

    async def reject_review(self, lead_id, actor, reason):
        self.calls.append(("reject", lead_id, actor, reason))
        return lead_record(LeadStatus.DRAFTED)

    async def edit_draft(self, lead_id, actor, **kwargs):
        self.calls.append(("edit", lead_id, actor, kwargs))
        return lead_record(LeadStatus.IN_REVIEW)

    async def edit_fields(self, lead_id, actor, fields):
        self.calls.append(("edit_fields", lead_id, actor, fields))
        return lead_record(LeadStatus.IN_REVIEW)


class BlockedReviewRepo(FakeReviewRepo):
    async def approve_for_send(self, lead_id, actor):
        self.calls.append(("approve", lead_id, actor))
        return None, "same_actor"


class FakeTransaction:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeLeadConn:
    def __init__(self) -> None:
        self.executed = []
        self.fetch_count = 0

    def transaction(self):
        return FakeTransaction()

    async def fetchrow(self, query, *args):
        self.fetch_count += 1
        if "SELECT sender_name" in query:
            return {
                "sender_name": "Jane",
                "email_address": "jane@example.com",
                "contact_number": None,
                "visa_category": "Retired Person Visa",
                "lead_source": None,
                "assigned_consultant": None,
                "source_box": "XP",
            }
        return vars(lead_record())

    async def execute(self, query, *args):
        self.executed.append((query, args))


class FakeAcquire:
    def __init__(self, conn: FakeLeadConn) -> None:
        self.conn = conn

    async def __aenter__(self):
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeLeadPool:
    def __init__(self) -> None:
        self.conn = FakeLeadConn()

    def acquire(self):
        return FakeAcquire(self.conn)


class LeadReviewApiTest(unittest.IsolatedAsyncioTestCase):
    async def test_approve_uses_current_user_as_actor(self) -> None:
        repo = FakeReviewRepo()
        with patch("app.api.leads.LeadRepository", return_value=repo):
            response = await approve_lead("lead-fixture", pool=object(), current_user=current_user())

        self.assertEqual(response.status, LeadStatus.SENT)
        self.assertEqual(repo.calls, [("approve", "lead-fixture", "usr-reviewer")])

    async def test_approve_blocks_same_reviewer(self) -> None:
        repo = BlockedReviewRepo()
        with patch("app.api.leads.LeadRepository", return_value=repo):
            with self.assertRaises(Exception) as caught:
                await approve_lead("lead-fixture", pool=object(), current_user=current_user())

        self.assertEqual(getattr(caught.exception, "status_code", None), 409)

    async def test_reject_and_edit_do_not_log_or_require_raw_draft_content(self) -> None:
        repo = FakeReviewRepo()
        with patch("app.api.leads.LeadRepository", return_value=repo):
            await reject_lead(
                "lead-fixture",
                payload=LeadActionRequest(reason="Needs correction"),
                pool=object(),
                current_user=current_user(),
            )
            await edit_lead_draft(
                "lead-fixture",
                payload=DraftEditRequest(email_draft="Edited draft"),
                pool=object(),
                current_user=current_user(),
            )

        self.assertEqual(repo.calls[0], ("reject", "lead-fixture", "usr-reviewer", "Needs correction"))
        self.assertEqual(repo.calls[1][0:3], ("edit", "lead-fixture", "usr-reviewer"))
        self.assertEqual(repo.calls[1][3]["email_draft"], "Edited draft")

    async def test_edit_fields_uses_current_user_and_passes_only_requested_fields(self) -> None:
        repo = FakeReviewRepo()
        with patch("app.api.leads.LeadRepository", return_value=repo):
            response = await edit_lead_fields(
                "lead-fixture",
                payload=LeadFieldEditRequest(name="Jane Edited", phone="+27 82 000 0000"),
                pool=object(),
                current_user=current_user(),
            )

        self.assertEqual(response.status, LeadStatus.IN_REVIEW)
        self.assertEqual(
            repo.calls,
            [("edit_fields", "lead-fixture", "usr-reviewer", {"name": "Jane Edited", "phone": "+27 82 000 0000"})],
        )

    def test_edit_fields_http_rejects_roles_without_draft_edit_permission(self) -> None:
        for role in ("reviewer", "approver", "quality_lead"):
            app = FastAPI()
            app.include_router(leads_router)
            app.dependency_overrides[get_current_user] = lambda role=role: current_user(f"usr-{role}", (role,))
            app.dependency_overrides[get_pool] = lambda: object()
            client = TestClient(app)

            response = client.patch("/api/v1/leads/lead-fixture/fields", json={"name": "Jane Edited"})

            self.assertEqual(response.status_code, 403, role)

    def test_edit_fields_http_allows_agent_and_superadmin(self) -> None:
        for role in ("agent", "superadmin"):
            app = FastAPI()
            app.include_router(leads_router)
            app.dependency_overrides[get_current_user] = lambda role=role: current_user(f"usr-{role}", (role,))
            app.dependency_overrides[get_pool] = lambda: object()
            repo = FakeReviewRepo()
            client = TestClient(app)

            with patch("app.api.leads.LeadRepository", return_value=repo):
                response = client.patch("/api/v1/leads/lead-fixture/fields", json={"name": "Jane Edited"})

            self.assertEqual(response.status_code, 200, role)
            self.assertEqual(repo.calls, [("edit_fields", "lead-fixture", f"usr-{role}", {"name": "Jane Edited"})])

    async def test_edit_fields_without_changes_does_not_write_audit(self) -> None:
        pool = FakeLeadPool()
        record = await LeadRepository(pool).edit_fields(
            "lead-fixture",
            "usr-agent",
            {"name": "Jane"},
        )

        self.assertEqual(record.lead_id, "lead-fixture")
        self.assertEqual(pool.conn.executed, [])


if __name__ == "__main__":
    unittest.main()
