import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from app.api.routing import list_routing_rules, update_routing_rule
from app.repositories.users import UserRecord
from app.services.auth import CurrentUser, permissions_for_roles


def user_record(user_id="usr-superadmin", roles=("superadmin",)):
    now = datetime.now(UTC)
    return UserRecord(
        user_id=user_id,
        email=f"{user_id}@example.com",
        display_name=user_id,
        password_hash="hash",
        is_active=True,
        roles=roles,
        created_at=now,
        updated_at=now,
    )


def superadmin_user() -> CurrentUser:
    return CurrentUser(
        user_id="usr-actor",
        email="actor@example.com",
        display_name="Actor",
        roles=("superadmin",),
        permissions=permissions_for_roles(("superadmin",)),
    )


class FakeRoutingRuleRepo:
    def __init__(self, pool):
        self.configured = {"standard_review": ["usr-agent"]}

    async def list_configured_user_ids(self, category):
        return self.configured.get(category, [])

    async def list_recipients(self, category):
        if category == "standard_review":
            return [user_record("usr-agent", ("agent",))]
        return [user_record("usr-superadmin", ("superadmin",))]

    async def list_categories_for_user(self, user_id):
        if user_id == "usr-agent":
            return ["standard_review"]
        return []

    async def set_recipients(self, category, user_ids):
        if "usr-missing" in user_ids:
            raise ValueError("Unknown user_id: usr-missing")
        self.configured[category] = list(user_ids)
        return [user_record(user_id, ("reviewer",)) for user_id in user_ids] or [user_record("usr-superadmin", ("superadmin",))]


class FakeUserRepo:
    def __init__(self, pool):
        self.audit_events = []

    async def append_user_audit_event(self, **kwargs):
        self.audit_events.append(kwargs)


class RoutingRulesApiTest(unittest.IsolatedAsyncioTestCase):
    async def test_list_rules_returns_all_categories_with_fallback_flag(self) -> None:
        with patch("app.api.routing.RoutingRuleRepository", FakeRoutingRuleRepo):
            rules = await list_routing_rules(pool=object(), current_user=superadmin_user())

        self.assertEqual({rule.category for rule in rules}, {"escalation", "dnq_reject", "visa_verification", "standard_review"})
        standard = next(rule for rule in rules if rule.category == "standard_review")
        escalation = next(rule for rule in rules if rule.category == "escalation")
        self.assertFalse(standard.fallback_to_superadmin)
        self.assertTrue(escalation.fallback_to_superadmin)

    async def test_update_rule_rejects_unknown_category(self) -> None:
        with self.assertRaises(Exception) as caught:
            await update_routing_rule(
                "unknown",
                current_user=superadmin_user(),
            )

        self.assertEqual(getattr(caught.exception, "status_code", None), 404)

    async def test_update_rule_is_deprecated(self) -> None:
        with patch("app.api.routing.RoutingRuleRepository", FakeRoutingRuleRepo):
            with self.assertRaises(Exception) as caught:
                await update_routing_rule(
                    "standard_review",
                    current_user=superadmin_user(),
                )

        self.assertEqual(getattr(caught.exception, "status_code", None), 410)


if __name__ == "__main__":
    unittest.main()
