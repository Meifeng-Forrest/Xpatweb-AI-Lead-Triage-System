import unittest
from datetime import UTC, datetime
from app.config import Settings
from app.repositories.users import UserRecord
from app.services.auth import (
    create_access_token,
    decode_access_token,
    password_hash,
    permissions_for_roles,
    verify_password,
)


def user_record(**overrides):
    values = {
        "user_id": "usr-fixture",
        "email": "agent@example.com",
        "display_name": "Agent",
        "password_hash": "unused",
        "is_active": True,
        "roles": ("agent",),
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    values.update(overrides)
    return UserRecord(**values)


class AuthServiceTest(unittest.TestCase):
    def test_role_permissions_merge_multiple_roles(self) -> None:
        permissions = permissions_for_roles(("agent", "quality_lead"))

        self.assertNotIn("lead.approve", permissions)
        self.assertIn("lead.draft.edit", permissions)
        self.assertIn("lead.reject.confirm", permissions)

    def test_superadmin_has_all_permissions(self) -> None:
        permissions = permissions_for_roles(("superadmin",))

        self.assertIn("lead.approve", permissions)
        self.assertIn("routing.config", permissions)
        self.assertIn("user.manage", permissions)

    def test_approver_can_approve_without_system_management(self) -> None:
        approver_permissions = permissions_for_roles(("approver",))
        agent_permissions = permissions_for_roles(("agent",))

        self.assertIn("lead.approve", approver_permissions)
        self.assertNotIn("user.manage", approver_permissions)
        self.assertNotIn("routing.config", approver_permissions)
        self.assertNotIn("lead.approve", agent_permissions)

    def test_password_hash_roundtrip(self) -> None:
        hashed = password_hash("secret-password")

        self.assertTrue(verify_password("secret-password", hashed))
        self.assertFalse(verify_password("wrong-password", hashed))

    def test_hmac_jwt_roundtrip(self) -> None:
        settings = Settings(AUTH_JWT_SECRET="test-secret")
        token = create_access_token(user_record(), settings)

        payload = decode_access_token(token, settings)

        self.assertEqual(payload["sub"], "usr-fixture")
        self.assertEqual(payload["email"], "agent@example.com")
        self.assertIn("lead.view", payload["permissions"])


if __name__ == "__main__":
    unittest.main()
