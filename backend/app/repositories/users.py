from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any
from uuid import uuid4

import asyncpg


@dataclass(frozen=True)
class UserRecord:
    user_id: str
    email: str
    display_name: str
    password_hash: str
    is_active: bool
    roles: tuple[str, ...]
    created_at: datetime
    updated_at: datetime


def row_to_user(row: asyncpg.Record, roles: list[str]) -> UserRecord:
    return UserRecord(
        user_id=row["user_id"],
        email=row["email"],
        display_name=row["display_name"],
        password_hash=row["password_hash"],
        is_active=bool(row["is_active"]),
        roles=tuple(roles),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class UserRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def create_user(
        self,
        *,
        email: str,
        display_name: str,
        password_hash: str,
        roles: tuple[str, ...],
        user_id: str | None = None,
        is_active: bool = True,
    ) -> UserRecord:
        normalized_email = email.strip().lower()
        new_user_id = user_id or f"usr-{uuid4()}"
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    INSERT INTO users (user_id, email, display_name, password_hash, is_active)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (email) DO UPDATE
                    SET display_name = EXCLUDED.display_name,
                        password_hash = EXCLUDED.password_hash,
                        is_active = EXCLUDED.is_active,
                        updated_at = NOW()
                    RETURNING *
                    """,
                    new_user_id,
                    normalized_email,
                    display_name,
                    password_hash,
                    is_active,
                )
                await conn.execute("DELETE FROM user_roles WHERE user_id = $1", row["user_id"])
                for role in roles:
                    await conn.execute(
                        """
                        INSERT INTO user_roles (user_id, role)
                        VALUES ($1, $2)
                        ON CONFLICT DO NOTHING
                        """,
                        row["user_id"],
                        role,
                    )
        return await self.get_by_id(row["user_id"])  # type: ignore[return-value]

    async def get_by_email(self, email: str) -> UserRecord | None:
        normalized_email = email.strip().lower()
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE email = $1", normalized_email)
            if row is None:
                return None
            roles = await conn.fetch("SELECT role FROM user_roles WHERE user_id = $1 ORDER BY role", row["user_id"])
        return row_to_user(row, [role["role"] for role in roles])

    async def get_by_id(self, user_id: str) -> UserRecord | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
            if row is None:
                return None
            roles = await conn.fetch("SELECT role FROM user_roles WHERE user_id = $1 ORDER BY role", user_id)
        return row_to_user(row, [role["role"] for role in roles])

    async def list_users(self) -> list[UserRecord]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM users ORDER BY display_name ASC, email ASC")
            result: list[UserRecord] = []
            for row in rows:
                roles = await conn.fetch("SELECT role FROM user_roles WHERE user_id = $1 ORDER BY role", row["user_id"])
                result.append(row_to_user(row, [role["role"] for role in roles]))
        return result

    async def update_user(
        self,
        user_id: str,
        *,
        display_name: str | None = None,
        roles: tuple[str, ...] | None = None,
        is_active: bool | None = None,
    ) -> UserRecord | None:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
                if row is None:
                    return None

                next_display_name = display_name if display_name is not None else row["display_name"]
                next_is_active = is_active if is_active is not None else bool(row["is_active"])
                await conn.execute(
                    """
                    UPDATE users
                    SET display_name = $2,
                        is_active = $3,
                        updated_at = NOW()
                    WHERE user_id = $1
                    """,
                    user_id,
                    next_display_name,
                    next_is_active,
                )

                if roles is not None:
                    await conn.execute("DELETE FROM user_roles WHERE user_id = $1", user_id)
                    for role in roles:
                        await conn.execute(
                            """
                            INSERT INTO user_roles (user_id, role)
                            VALUES ($1, $2)
                            ON CONFLICT DO NOTHING
                            """,
                            user_id,
                            role,
                        )
        return await self.get_by_id(user_id)

    async def update_password(self, user_id: str, password_hash: str) -> UserRecord | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE users
                SET password_hash = $2,
                    updated_at = NOW()
                WHERE user_id = $1
                RETURNING *
                """,
                user_id,
                password_hash,
            )
            if row is None:
                return None
        return await self.get_by_id(user_id)

    async def count_active_superadmins(self) -> int:
        async with self.pool.acquire() as conn:
            return int(
                await conn.fetchval(
                    """
                    SELECT COUNT(*)
                    FROM users u
                    JOIN user_roles ur ON ur.user_id = u.user_id
                    WHERE u.is_active = TRUE AND ur.role = 'superadmin'
                    """
                )
                or 0
            )

    async def append_user_audit_event(
        self,
        *,
        target_user_id: str | None,
        event_type: str,
        actor: str,
        metadata: dict[str, Any],
    ) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_audit_events (target_user_id, event_type, actor, metadata)
                VALUES ($1, $2, $3, $4::jsonb)
                """,
                target_user_id,
                event_type,
                actor,
                json.dumps(metadata),
            )

    async def list_routing_targets(self, role: str) -> list[UserRecord]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT u.*
                FROM users u
                JOIN user_roles ur ON ur.user_id = u.user_id
                WHERE ur.role = $1 AND u.is_active = TRUE
                ORDER BY u.display_name ASC
                """,
                role,
            )
            result: list[UserRecord] = []
            for row in rows:
                roles = await conn.fetch(
                    "SELECT role FROM user_roles WHERE user_id = $1 ORDER BY role",
                    row["user_id"],
                )
                result.append(row_to_user(row, [item["role"] for item in roles]))
        return result


class RoutingRuleRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def list_configured_user_ids(self, category: str) -> list[str]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT user_id FROM routing_rules WHERE category = $1 ORDER BY user_id",
                category,
            )
        return [row["user_id"] for row in rows]

    async def list_recipients(self, category: str) -> list[UserRecord]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT u.*
                FROM routing_rules rr
                JOIN users u ON u.user_id = rr.user_id
                WHERE rr.category = $1 AND u.is_active = TRUE
                ORDER BY u.display_name ASC, u.email ASC
                """,
                category,
            )
            result: list[UserRecord] = []
            for row in rows:
                roles = await conn.fetch(
                    "SELECT role FROM user_roles WHERE user_id = $1 ORDER BY role",
                    row["user_id"],
                )
                result.append(row_to_user(row, [item["role"] for item in roles]))

        # 路由配置为空或只剩停用用户时，必须兜底到所有在职 superadmin，防止通知漏发。
        if result:
            return result
        return await UserRepository(self.pool).list_routing_targets("superadmin")

    async def set_recipients(self, category: str, user_ids: tuple[str, ...]) -> list[UserRecord]:
        unique_user_ids = tuple(dict.fromkeys(user_id.strip() for user_id in user_ids if user_id.strip()))
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                if unique_user_ids:
                    existing_rows = await conn.fetch(
                        "SELECT user_id FROM users WHERE user_id = ANY($1::text[])",
                        list(unique_user_ids),
                    )
                    existing_ids = {row["user_id"] for row in existing_rows}
                    missing = [user_id for user_id in unique_user_ids if user_id not in existing_ids]
                    if missing:
                        raise ValueError(f"Unknown user_id: {missing[0]}")

                await conn.execute("DELETE FROM routing_rules WHERE category = $1", category)
                for user_id in unique_user_ids:
                    await conn.execute(
                        """
                        INSERT INTO routing_rules (category, user_id)
                        VALUES ($1, $2)
                        ON CONFLICT DO NOTHING
                        """,
                        category,
                        user_id,
                    )

        return await self.list_recipients(category)

    async def list_categories_for_user(self, user_id: str) -> list[str]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT category FROM routing_rules WHERE user_id = $1 ORDER BY category",
                user_id,
            )
        return [row["category"] for row in rows]

    async def set_categories_for_user(self, user_id: str, categories: tuple[str, ...]) -> list[str]:
        unique_categories = tuple(dict.fromkeys(category.strip() for category in categories if category.strip()))
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                exists = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM users WHERE user_id = $1)", user_id)
                if not exists:
                    raise ValueError(f"Unknown user_id: {user_id}")

                await conn.execute("DELETE FROM routing_rules WHERE user_id = $1", user_id)
                for category in unique_categories:
                    await conn.execute(
                        """
                        INSERT INTO routing_rules (category, user_id)
                        VALUES ($1, $2)
                        ON CONFLICT DO NOTHING
                        """,
                        category,
                        user_id,
                    )

        return await self.list_categories_for_user(user_id)
