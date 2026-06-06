import unittest
from datetime import UTC, datetime
from types import SimpleNamespace

from app.repositories.users import UserRecord
from app.services.routing import LeadRoutingService


class FakeRoutingRules:
    def __init__(self, targets):
        self.targets = targets
        self.categories = []

    async def list_recipients(self, category):
        self.categories.append(category)
        return self.targets


class FakeNotifier:
    def __init__(self):
        self.payloads = []

    async def send_call_alert(self, payload):
        self.payloads.append(payload)


def user_record(user_id="usr-target"):
    now = datetime.now(UTC)
    return UserRecord(
        user_id=user_id,
        email=f"{user_id}@example.com",
        display_name="Target",
        password_hash="hash",
        is_active=True,
        roles=("superadmin",),
        created_at=now,
        updated_at=now,
    )


class RoutingServiceTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.service = LeadRoutingService.__new__(LeadRoutingService)

    def lead(self, **overrides):
        values = {
            "escalation_flag": False,
            "dnq_reason": None,
            "lead_score": "GD",
            "visa_category": "Retired Person Visa",
            "current_visa": None,
            "pr_route": None,
            "additional_info": None,
        }
        values.update(overrides)
        return SimpleNamespace(**values)

    def test_routes_regular_drafts_to_standard_review_category(self) -> None:
        self.assertEqual(self.service._target_category(self.lead(lead_score="GD")), "standard_review")
        self.assertEqual(self.service._target_category(self.lead(lead_score="MD")), "standard_review")

    def test_routes_exception_cases_to_specific_categories(self) -> None:
        self.assertEqual(self.service._target_category(self.lead(escalation_flag=True)), "escalation")
        self.assertEqual(self.service._target_category(self.lead(dnq_reason="DNQ-01", lead_score="BD")), "dnq_reject")
        self.assertEqual(self.service._target_category(self.lead(additional_info="Needs visa verification")), "visa_verification")

    async def test_route_after_draft_uses_category_recipients(self) -> None:
        service = LeadRoutingService.__new__(LeadRoutingService)
        service.routing_rules = FakeRoutingRules([user_record("usr-willem")])
        service.notifier = FakeNotifier()
        lead = self.lead(additional_info="Needs visa verification")
        lead.lead_id = "lead-1"
        lead.source_box = "XP"

        await service.route_after_draft(lead)

        self.assertEqual(service.routing_rules.categories, ["visa_verification"])
        self.assertEqual(len(service.notifier.payloads), 1)
        self.assertIn("category:visa_verification", service.notifier.payloads[0].reason)


if __name__ == "__main__":
    unittest.main()
