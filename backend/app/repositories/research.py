from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any

import asyncpg

from app.schemas import ResearchBriefFields


@dataclass(frozen=True)
class ResearchBriefRecord:
    lead_id: str
    status: str
    task_id: str | None
    brief: dict[str, Any] | None
    source_refs: list[dict[str, Any]]
    error_type: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None


def _dict_or_none(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else None
    return None


def _list_of_dicts(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if isinstance(value, str):
        parsed = json.loads(value)
        return [item for item in parsed if isinstance(item, dict)] if isinstance(parsed, list) else []
    return []


def row_to_research(row: asyncpg.Record) -> ResearchBriefRecord:
    return ResearchBriefRecord(
        lead_id=row["lead_id"],
        status=row["status"],
        task_id=row["task_id"],
        brief=_dict_or_none(row["brief"]),
        source_refs=_list_of_dicts(row["source_refs"]),
        error_type=row["error_type"],
        error_message=row["error_message"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        completed_at=row["completed_at"],
    )


class ResearchRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def get(self, lead_id: str) -> ResearchBriefRecord | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM research_briefs WHERE lead_id = $1", lead_id)
        return row_to_research(row) if row else None

    async def mark_queued(self, lead_id: str, task_id: str) -> ResearchBriefRecord:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO research_briefs (lead_id, status, task_id, brief, source_refs, error_type, error_message)
                VALUES ($1, 'queued', $2, NULL, '[]'::jsonb, NULL, NULL)
                ON CONFLICT (lead_id) DO UPDATE
                SET status = 'queued',
                    task_id = EXCLUDED.task_id,
                    brief = NULL,
                    source_refs = '[]'::jsonb,
                    error_type = NULL,
                    error_message = NULL,
                    updated_at = NOW(),
                    completed_at = NULL
                RETURNING *
                """,
                lead_id,
                task_id,
            )
        return row_to_research(row)

    async def mark_running(self, lead_id: str, task_id: str) -> ResearchBriefRecord:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE research_briefs
                SET status = 'running',
                    task_id = $2,
                    updated_at = NOW()
                WHERE lead_id = $1
                RETURNING *
                """,
                lead_id,
                task_id,
            )
        if row is None:
            return await self.mark_queued(lead_id, task_id)
        return row_to_research(row)

    async def mark_succeeded(
        self,
        lead_id: str,
        *,
        brief: ResearchBriefFields,
        source_refs: list[dict[str, Any]],
    ) -> ResearchBriefRecord:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE research_briefs
                SET status = 'succeeded',
                    brief = $2::jsonb,
                    source_refs = $3::jsonb,
                    error_type = NULL,
                    error_message = NULL,
                    updated_at = NOW(),
                    completed_at = NOW()
                WHERE lead_id = $1
                RETURNING *
                """,
                lead_id,
                json.dumps(brief.model_dump()),
                json.dumps(source_refs),
            )
        return row_to_research(row)

    async def mark_failed(self, lead_id: str, *, error_type: str, error_message: str) -> ResearchBriefRecord:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE research_briefs
                SET status = 'failed',
                    error_type = $2,
                    error_message = $3,
                    updated_at = NOW(),
                    completed_at = NOW()
                WHERE lead_id = $1
                RETURNING *
                """,
                lead_id,
                error_type,
                error_message[:500],
            )
        return row_to_research(row)
