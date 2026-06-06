import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.api.leads import create_form_webhook_lead, form_webhook_to_manual_lead, verify_form_webhook_secret
from app.config import Settings
from app.schemas import FormWebhookLeadCreate, LeadStatus


def request(headers=None):
    return SimpleNamespace(headers=headers or {})


def lead_record(**overrides):
    values = {
        "lead_id": "lead-form",
        "sender_name": "Jane Form",
        "email_address": "jane@example.com",
        "contact_number": "+27000000000",
        "email_domain": "example.com",
        "visa_category": "Retired Person Visa",
        "lead_type": None,
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
        "urgency_flag": None,
        "multi_visa_flag": None,
        "email_coherence": None,
        "additional_info": None,
        "extracted_fields": {},
        "extracted_at": None,
        "extraction_provider": None,
        "extraction_model": None,
        "extraction_temperature": None,
        "lead_score": None,
        "dnq_reason": None,
        "risk_flags": [],
        "score_confidence": None,
        "score_rationale": None,
        "escalation_flag": False,
        "soft_dnq_warning": None,
        "score_provider": None,
        "score_model": None,
        "score_temperature": None,
        "scored_at": None,
        "email_draft": None,
        "whatsapp_draft": None,
        "phone_script": None,
        "internal_whatsapp_post": None,
        "draft_fields": {},
        "draft_provider": None,
        "draft_model": None,
        "draft_temperature": None,
        "drafted_at": None,
        "source_box": "XP",
        "lead_source": "XP349",
        "raw_message": "Fixture",
        "status": LeadStatus.RECEIVED,
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class FakeFormRepo:
    def __init__(self) -> None:
        self.created = None

    async def create_form_webhook_lead(self, lead_id, payload, *, form_name, field_count):
        self.created = {
            "lead_id": lead_id,
            "payload": payload,
            "form_name": form_name,
            "field_count": field_count,
        }
        return lead_record(lead_id=lead_id, source_box=payload.source_box.value, lead_source=payload.lead_source)


class FormWebhookApiTest(unittest.IsolatedAsyncioTestCase):
    def test_maps_common_form_fields_to_manual_lead_payload(self) -> None:
        payload = FormWebhookLeadCreate(
            source_box="XP",
            form_name="Xpatweb Contact",
            fields={
                "Name": "Jane Form",
                "Email": "jane@example.com",
                "Phone": "+27000000000",
                "Visa Type": "Retired Person Visa",
                "utm_campaign": "XP349",
                "Message": "Please help with a retired person visa.",
            },
        )

        manual = form_webhook_to_manual_lead(payload)

        self.assertEqual(manual.sender_name, "Jane Form")
        self.assertEqual(str(manual.email_address), "jane@example.com")
        self.assertEqual(manual.contact_number, "+27000000000")
        self.assertEqual(manual.visa_category, "Retired Person Visa")
        self.assertEqual(manual.lead_source, "XP349")
        self.assertIn("retired person visa", manual.raw_message)

    def test_secret_header_is_required_when_configured(self) -> None:
        settings = Settings(FORM_WEBHOOK_SECRET="secret")

        verify_form_webhook_secret(request({"X-Webhook-Secret": "secret"}), settings)
        with self.assertRaises(Exception) as caught:
            verify_form_webhook_secret(request({"X-Webhook-Secret": "wrong"}), settings)

        self.assertEqual(getattr(caught.exception, "status_code", None), 401)

    async def test_endpoint_persists_and_queues_existing_pipeline(self) -> None:
        repo = FakeFormRepo()
        payload = FormWebhookLeadCreate(
            source_box="XP",
            fields={"name": "Jane Form", "email": "jane@example.com", "message": "Need visa help"},
        )

        with (
            patch("app.api.leads.LeadRepository", return_value=repo),
            patch("app.api.leads.enqueue_pipeline", new=AsyncMock(return_value="task-form")),
        ):
            response = await create_form_webhook_lead(
                payload,
                request({}),
                pool=object(),
                settings=Settings(FORM_WEBHOOK_SECRET=""),
            )

        self.assertEqual(response.lead_id, repo.created["lead_id"])
        self.assertEqual(response.pipeline_task_id, "task-form")
        self.assertEqual(repo.created["field_count"], 3)
        self.assertEqual(str(repo.created["payload"].email_address), "jane@example.com")


if __name__ == "__main__":
    unittest.main()
