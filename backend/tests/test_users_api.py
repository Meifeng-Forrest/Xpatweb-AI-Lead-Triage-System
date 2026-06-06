import unittest
from datetime import UTC, datetime
from unittest.mock import patch

from app.api.users import create_user, update_user, update_user_routing_categories, validate_roles
from app.repositories.users import UserRecord
from app.schemas import UserCreateRequest, UserRoutingCategoriesUpdateRequest, UserUpdateRequest
from app.services.auth import CurrentUser, permissions_for_roles


def user_record(**overrides):
    values = {
        "user_id": "usr-admin",
        "email": "admin@example.com",
        "display_name": "Admin",
        "password_hash": "hash",
        "is_active": True,
        "roles": ("superadmin",),
        "created_at": datetime.now(UTC),
        "updated_at": datetime.now(UTC),
    }
    values.update(overrides)
    return UserRecord(**values)


def superadmin_user() -> CurrentUser:
    return CurrentUser(
        user_id="usr-actor",
        email="actor@example.com",
        display_name="Actor",
        roles=("superadmin",),
        permissions=permissions_for_roles(("superadmin",)),
    )


class FakeUserRepo:
    def __init__(self, existing=None, active_superadmin_count=2) -> None:
        self.existing = existing
        self.active_superadmin_count = active_superadmin_count
        self.audit_events = []

    async def get_by_email(self, email):
        return self.existing if email == "admin@example.com" else None

    async def get_by_id(self, user_id):
        return self.existing

    async def count_active_superadmins(self):
        return self.active_superadmin_count

    async def create_user(self, **kwargs):
        return user_record(
            user_id="usr-created",
            email=kwargs["email"],
            display_name=kwargs["display_name"],
            roles=kwargs["roles"],
            is_active=kwargs["is_active"],
            password_hash=kwargs["password_hash"],
        )

    async def update_user(self, user_id, **kwargs):
        roles = kwargs.get("roles") or self.existing.roles
        is_active = kwargs.get("is_active") if kwargs.get("is_active") is not None else self.existing.is_active
        return user_record(user_id=user_id, roles=roles, is_active=is_active)

    async def append_user_audit_event(self, **kwargs):
        self.audit_events.append(kwargs)


class FakeRoutingRepo:
    def __init__(self, pool) -> None:
        self.categories_by_user = {}

    async def list_categories_for_user(self, user_id):
        return self.categories_by_user.get(user_id, [])

    async def set_categories_for_user(self, user_id, categories):
        self.categories_by_user[user_id] = list(categories)
        return list(categories)


class UsersApiTest(unittest.IsolatedAsyncioTestCase):
    def test_validate_roles_rejects_unknown_role(self) -> None:
        with self.assertRaises(Exception) as caught:
            validate_roles(["superadmin", "unknown"])

        self.assertEqual(getattr(caught.exception, "status_code", None), 422)

    def test_validate_roles_requires_single_role(self) -> None:
        with self.assertRaises(Exception) as caught:
            validate_roles(["agent", "reviewer"])

        self.assertEqual(getattr(caught.exception, "status_code", None), 422)

    async def test_create_rejects_duplicate_email(self) -> None:
        repo = FakeUserRepo(existing=user_record())
        with patch("app.api.users.UserRepository", return_value=repo):
            with self.assertRaises(Exception) as caught:
                await create_user(
                    UserCreateRequest(
                        email="admin@example.com",
                        display_name="Admin",
                        password="password123",
                        roles=["superadmin"],
                    ),
                    pool=object(),
                    current_user=superadmin_user(),
                )

        self.assertEqual(getattr(caught.exception, "status_code", None), 409)

    async def test_update_blocks_removing_last_active_superadmin(self) -> None:
        repo = FakeUserRepo(existing=user_record(), active_superadmin_count=1)
        with patch("app.api.users.UserRepository", return_value=repo):
            with self.assertRaises(Exception) as caught:
                await update_user(
                    "usr-admin",
                    UserUpdateRequest(roles=["agent"]),
                    pool=object(),
                    current_user=superadmin_user(),
                )

        self.assertEqual(getattr(caught.exception, "status_code", None), 409)

    async def test_create_records_user_audit_event_without_password(self) -> None:
        repo = FakeUserRepo(existing=None)
        with patch("app.api.users.UserRepository", return_value=repo):
            with patch("app.api.users.RoutingRuleRepository", FakeRoutingRepo):
                created = await create_user(
                    UserCreateRequest(
                        email="new@example.com",
                        display_name="New User",
                        password="password123",
                        roles=["agent"],
                    ),
                    pool=object(),
                    current_user=superadmin_user(),
                )

        self.assertEqual(created.email, "new@example.com")
        self.assertEqual(repo.audit_events[0]["event_type"], "user.created")
        self.assertNotIn("password", repo.audit_events[0]["metadata"])

    async def test_update_routing_categories_writes_audit_without_private_data(self) -> None:
        user_repo = FakeUserRepo(existing=user_record(user_id="usr-target"))
        routing_repo = FakeRoutingRepo(object())
        with patch("app.api.users.UserRepository", return_value=user_repo):
            with patch("app.api.users.RoutingRuleRepository", return_value=routing_repo):
                updated = await update_user_routing_categories(
                    "usr-target",
                    UserRoutingCategoriesUpdateRequest(categories=["visa_verification"]),
                    pool=object(),
                    current_user=superadmin_user(),
                )

        self.assertEqual(updated.routing_categories, ["visa_verification"])
        self.assertEqual(user_repo.audit_events[0]["event_type"], "user.routing_categories.updated")
        self.assertEqual(user_repo.audit_events[0]["metadata"], {"category_count": 1})

    async def test_update_routing_categories_rejects_unknown_category(self) -> None:
        with self.assertRaises(Exception) as caught:
            await update_user_routing_categories(
                "usr-target",
                UserRoutingCategoriesUpdateRequest(categories=["unknown"]),
                pool=object(),
                current_user=superadmin_user(),
            )

        self.assertEqual(getattr(caught.exception, "status_code", None), 422)


if __name__ == "__main__":
    unittest.main()
