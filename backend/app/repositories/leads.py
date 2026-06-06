from dataclasses import dataclass
from datetime import datetime
import json
from typing import Any

import asyncpg

from app.schemas import (
    DraftResult,
    ExtractedEmailFields,
    LeadScoreResult,
    LeadStatus,
    ManualConfirmedLeadCreate,
    ManualLeadCreate,
)


@dataclass(frozen=True)
class LeadRecord:
    lead_id: str
    sender_name: str
    email_address: str
    contact_number: str | None
    email_domain: str
    visa_category: str | None
    lead_type: str | None
    current_visa: str | None
    pr_route: str | None
    nationality: str | None
    is_first_world: bool | None
    job_title: str | None
    net_worth_indicator: str | None
    has_job_offer: bool | None
    qualifying_work_visa_years: float | None
    annual_salary_zar: float | None
    pbs_total_score_below_100: bool | None
    relationship_duration: str | None
    marriage_type: str | None
    rejection_date: str | None
    urgency_flag: bool | None
    multi_visa_flag: bool | None
    email_coherence: str | None
    additional_info: str | None
    extracted_fields: dict[str, Any]
    extracted_at: datetime | None
    extraction_provider: str | None
    extraction_model: str | None
    extraction_temperature: float | None
    lead_score: str | None
    dnq_reason: str | None
    risk_flags: list[str]
    score_confidence: str | None
    score_rationale: str | None
    escalation_flag: bool
    soft_dnq_warning: str | None
    score_provider: str | None
    score_model: str | None
    score_temperature: float | None
    scored_at: datetime | None
    email_draft: str | None
    whatsapp_draft: str | None
    phone_script: str | None
    internal_whatsapp_post: str | None
    draft_fields: dict[str, Any]
    draft_provider: str | None
    draft_model: str | None
    draft_temperature: float | None
    drafted_at: datetime | None
    source_box: str
    lead_source: str | None
    assigned_consultant: str | None
    raw_message: str
    status: LeadStatus
    created_at: datetime
    updated_at: datetime


def email_domain(email: str) -> str:
    return email.split("@", 1)[1].lower() if "@" in email else ""


def normalize_jsonb(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def normalize_jsonb_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return [item for item in parsed if isinstance(item, str)] if isinstance(parsed, list) else []
    return []


def row_to_lead(row: asyncpg.Record) -> LeadRecord:
    return LeadRecord(
        lead_id=row["lead_id"],
        sender_name=row["sender_name"],
        email_address=row["email_address"],
        contact_number=row["contact_number"],
        email_domain=row["email_domain"],
        visa_category=row["visa_category"],
        lead_type=row["lead_type"],
        current_visa=row["current_visa"],
        pr_route=row["pr_route"],
        nationality=row["nationality"],
        is_first_world=row["is_first_world"],
        job_title=row["job_title"],
        net_worth_indicator=row["net_worth_indicator"],
        has_job_offer=row["has_job_offer"],
        qualifying_work_visa_years=float(row["qualifying_work_visa_years"]) if row["qualifying_work_visa_years"] is not None else None,
        annual_salary_zar=float(row["annual_salary_zar"]) if row["annual_salary_zar"] is not None else None,
        pbs_total_score_below_100=row["pbs_total_score_below_100"],
        relationship_duration=row["relationship_duration"],
        marriage_type=row["marriage_type"],
        rejection_date=row["rejection_date"],
        urgency_flag=row["urgency_flag"],
        multi_visa_flag=row["multi_visa_flag"],
        email_coherence=row["email_coherence"],
        additional_info=row["additional_info"],
        extracted_fields=normalize_jsonb(row["extracted_fields"]),
        extracted_at=row["extracted_at"],
        extraction_provider=row["extraction_provider"],
        extraction_model=row["extraction_model"],
        extraction_temperature=float(row["extraction_temperature"]) if row["extraction_temperature"] is not None else None,
        lead_score=row["lead_score"],
        dnq_reason=row["dnq_reason"],
        risk_flags=normalize_jsonb_list(row["risk_flags"]),
        score_confidence=row["score_confidence"],
        score_rationale=row["score_rationale"],
        escalation_flag=bool(row["escalation_flag"]),
        soft_dnq_warning=row["soft_dnq_warning"],
        score_provider=row["score_provider"],
        score_model=row["score_model"],
        score_temperature=float(row["score_temperature"]) if row["score_temperature"] is not None else None,
        scored_at=row["scored_at"],
        email_draft=row["email_draft"],
        whatsapp_draft=row["whatsapp_draft"],
        phone_script=row["phone_script"],
        internal_whatsapp_post=row["internal_whatsapp_post"],
        draft_fields=normalize_jsonb(row["draft_fields"]),
        draft_provider=row["draft_provider"],
        draft_model=row["draft_model"],
        draft_temperature=float(row["draft_temperature"]) if row["draft_temperature"] is not None else None,
        drafted_at=row["drafted_at"],
        source_box=row["source_box"],
        lead_source=row["lead_source"],
        assigned_consultant=row["assigned_consultant"],
        raw_message=row["raw_message"],
        status=LeadStatus(row["status"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class LeadRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def create_manual_lead(self, lead_id: str, payload: ManualLeadCreate) -> LeadRecord:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    INSERT INTO leads (
                        lead_id,
                        sender_name,
                        email_address,
                        contact_number,
                        email_domain,
                        visa_category,
                        source_box,
                        lead_source,
                        raw_message,
                        status
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    RETURNING *
                    """,
                    lead_id,
                    payload.sender_name,
                    str(payload.email_address),
                    payload.contact_number,
                    email_domain(str(payload.email_address)),
                    payload.visa_category,
                    payload.source_box.value,
                    payload.lead_source,
                    payload.raw_message,
                    LeadStatus.RECEIVED.value,
                )
                await conn.execute(
                    """
                    INSERT INTO audit_events (lead_id, event_type, actor, metadata)
                    VALUES ($1, $2, $3, $4::jsonb)
                    """,
                    lead_id,
                    "lead.received.manual",
                    "system",
                    '{"source":"manual_api"}',
                )
        return row_to_lead(row)

    async def create_form_webhook_lead(
        self,
        lead_id: str,
        payload: ManualLeadCreate,
        *,
        form_name: str | None,
        field_count: int,
    ) -> LeadRecord:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    INSERT INTO leads (
                        lead_id,
                        sender_name,
                        email_address,
                        contact_number,
                        email_domain,
                        visa_category,
                        source_box,
                        lead_source,
                        raw_message,
                        status
                    )
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    RETURNING *
                    """,
                    lead_id,
                    payload.sender_name,
                    str(payload.email_address),
                    payload.contact_number,
                    email_domain(str(payload.email_address)),
                    payload.visa_category,
                    payload.source_box.value,
                    payload.lead_source,
                    payload.raw_message,
                    LeadStatus.RECEIVED.value,
                )
                await conn.execute(
                    """
                    INSERT INTO audit_events (lead_id, event_type, actor, metadata)
                    VALUES ($1, $2, $3, $4::jsonb)
                    """,
                    lead_id,
                    "lead.received.form_webhook",
                    "form_webhook",
                    json.dumps(
                        {
                            "source": "form_webhook",
                            "form_name": form_name,
                            "field_count": field_count,
                            "lead_source_present": bool(payload.lead_source),
                        }
                    ),
                )
        return row_to_lead(row)

    async def create_confirmed_manual_lead(
        self,
        lead_id: str,
        payload: ManualConfirmedLeadCreate,
    ) -> LeadRecord:
        extracted = payload.extracted
        extracted_data = extracted.model_dump(mode="json")
        email_address = extracted.email_address or ""
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                row = await conn.fetchrow(
                    """
                    INSERT INTO leads (
                        lead_id, sender_name, email_address, contact_number, email_domain,
                        visa_category, lead_type, current_visa, pr_route, nationality,
                        is_first_world, job_title, net_worth_indicator, has_job_offer,
                        qualifying_work_visa_years, annual_salary_zar, pbs_total_score_below_100,
                        relationship_duration, marriage_type, rejection_date, urgency_flag,
                        multi_visa_flag, email_coherence, additional_info, extracted_fields,
                        extracted_at, extraction_provider, extraction_model, extraction_temperature,
                        source_box, lead_source, raw_message, status
                    )
                    VALUES (
                        $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14,
                        $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25::jsonb,
                        NOW(), $26, $27, $28, $29, 'Manual', $30, 'received'
                    )
                    RETURNING *
                    """,
                    lead_id,
                    extracted.sender_name,
                    email_address,
                    extracted.contact_number,
                    email_domain(email_address),
                    extracted.visa_category,
                    extracted.lead_type,
                    extracted.current_visa,
                    extracted.pr_route,
                    extracted.nationality,
                    extracted.is_first_world,
                    extracted.job_title,
                    extracted.net_worth_indicator,
                    extracted.has_job_offer,
                    extracted.qualifying_work_visa_years,
                    extracted.annual_salary_zar,
                    extracted.pbs_total_score_below_100,
                    extracted.relationship_duration,
                    extracted.marriage_type,
                    extracted.rejection_date,
                    extracted.urgency_flag,
                    extracted.multi_visa_flag,
                    extracted.email_coherence,
                    extracted.additional_info,
                    json.dumps(extracted_data),
                    payload.extraction_provider,
                    payload.extraction_model,
                    payload.extraction_temperature,
                    payload.source_box.value,
                    payload.raw_message,
                )
                await conn.execute(
                    """
                    INSERT INTO audit_events (lead_id, event_type, actor, metadata)
                    VALUES
                        ($1, 'lead.received.manual', 'system', $2::jsonb),
                        ($1, 'lead.extracted_fields.confirmed', 'frontend', $3::jsonb)
                    """,
                    lead_id,
                    '{"source":"manual_confirmed_api"}',
                    json.dumps(
                        {
                            "provider": payload.extraction_provider,
                            "model": payload.extraction_model,
                            "temperature": payload.extraction_temperature,
                            "field_count": len(extracted_data),
                        }
                    ),
                )
        return row_to_lead(row)

    async def get_lead(self, lead_id: str) -> LeadRecord | None:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow("SELECT * FROM leads WHERE lead_id = $1", lead_id)
        return row_to_lead(row) if row else None

    async def append_audit_event(
        self,
        lead_id: str,
        event_type: str,
        actor: str,
        metadata: dict[str, Any],
        *,
        require_lead: bool = True,
    ) -> bool:
        async with self.pool.acquire() as conn:
            if require_lead:
                exists = await conn.fetchval("SELECT EXISTS(SELECT 1 FROM leads WHERE lead_id = $1)", lead_id)
                if not exists:
                    return False
            try:
                await conn.execute(
                    """
                    INSERT INTO audit_events (lead_id, event_type, actor, metadata)
                    VALUES ($1, $2, $3, $4::jsonb)
                    """,
                    lead_id,
                    event_type,
                    actor,
                    json.dumps(metadata),
                )
            except asyncpg.ForeignKeyViolationError:
                return False
        return True

    async def list_leads(self, limit: int = 100) -> list[LeadRecord]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT *
                FROM leads
                ORDER BY created_at DESC
                LIMIT $1
                """,
                limit,
            )
        return [row_to_lead(row) for row in rows]

    async def persist_extracted_fields(
        self,
        lead_id: str,
        extracted: ExtractedEmailFields,
        provider: str,
        model: str,
        temperature: float,
        actor: str,
    ) -> LeadRecord | None:
        extracted_data = extracted.model_dump(mode="json")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                current = await conn.fetchrow(
                    "SELECT lead_id FROM leads WHERE lead_id = $1 FOR UPDATE",
                    lead_id,
                )
                if current is None:
                    return None

                # 同时保存独立列和 JSON 快照：独立列方便列表/筛选，JSON 快照方便回放模型结果。
                row = await conn.fetchrow(
                    """
                    UPDATE leads
                    SET
                        sender_name = COALESCE(NULLIF($2, ''), sender_name),
                        contact_number = COALESCE($3, contact_number),
                        visa_category = COALESCE($4, visa_category),
                        lead_type = $5,
                        current_visa = $6,
                        pr_route = $7,
                        nationality = $8,
                        is_first_world = $9,
                        job_title = $10,
                        net_worth_indicator = $11,
                        has_job_offer = $12,
                        qualifying_work_visa_years = $13,
                        annual_salary_zar = $14,
                        pbs_total_score_below_100 = $15,
                        relationship_duration = $16,
                        marriage_type = $17,
                        rejection_date = $18,
                        urgency_flag = $19,
                        multi_visa_flag = $20,
                        email_coherence = $21,
                        additional_info = $22,
                        extracted_fields = $23::jsonb,
                        extracted_at = NOW(),
                        extraction_provider = $24,
                        extraction_model = $25,
                        extraction_temperature = $26,
                        updated_at = NOW()
                    WHERE lead_id = $1
                    RETURNING *
                    """,
                    lead_id,
                    extracted.sender_name if extracted.sender_name != "Not Provided" else None,
                    extracted.contact_number,
                    extracted.visa_category,
                    extracted.lead_type,
                    extracted.current_visa,
                    extracted.pr_route,
                    extracted.nationality,
                    extracted.is_first_world,
                    extracted.job_title,
                    extracted.net_worth_indicator,
                    extracted.has_job_offer,
                    extracted.qualifying_work_visa_years,
                    extracted.annual_salary_zar,
                    extracted.pbs_total_score_below_100,
                    extracted.relationship_duration,
                    extracted.marriage_type,
                    extracted.rejection_date,
                    extracted.urgency_flag,
                    extracted.multi_visa_flag,
                    extracted.email_coherence,
                    extracted.additional_info,
                    json.dumps(extracted_data),
                    provider,
                    model,
                    temperature,
                )
                await conn.execute(
                    """
                    INSERT INTO audit_events (lead_id, event_type, actor, metadata)
                    VALUES ($1, $2, $3, $4::jsonb)
                    """,
                    lead_id,
                    "lead.extracted_fields.persisted",
                    actor,
                    json.dumps(
                        {
                            "provider": provider,
                            "model": model,
                            "temperature": temperature,
                            "email_coherence": extracted.email_coherence,
                            "visa_category_present": bool(extracted.visa_category),
                        }
                    ),
                )
        return row_to_lead(row)

    async def update_status(
        self,
        lead_id: str,
        status: LeadStatus,
        actor: str,
    ) -> LeadRecord | None:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                current = await conn.fetchrow(
                    "SELECT status FROM leads WHERE lead_id = $1 FOR UPDATE",
                    lead_id,
                )
                if current is None:
                    return None

                previous_status = current["status"]
                row = await conn.fetchrow(
                    """
                    UPDATE leads
                    SET status = $2, updated_at = NOW()
                    WHERE lead_id = $1
                    RETURNING *
                    """,
                    lead_id,
                    status.value,
                )
                await conn.execute(
                    """
                    INSERT INTO audit_events (lead_id, event_type, actor, metadata)
                    VALUES ($1, $2, $3, $4::jsonb)
                    """,
                    lead_id,
                    "lead.status_changed",
                    actor,
                    json.dumps(
                        {
                            "previous_status": previous_status,
                            "new_status": status.value,
                        }
                    ),
                )
        return row_to_lead(row)

    async def edit_fields(
        self,
        lead_id: str,
        actor: str,
        fields: dict[str, Any],
    ) -> LeadRecord | None:
        column_map = {
            "name": "sender_name",
            "email": "email_address",
            "phone": "contact_number",
            "visa_category": "visa_category",
            "source": "lead_source",
            "assigned_consultant": "assigned_consultant",
            "brand": "source_box",
        }
        editable_keys = set(column_map)
        unknown_keys = sorted(set(fields) - editable_keys)
        if unknown_keys:
            raise ValueError(f"Unsupported lead edit fields: {', '.join(unknown_keys)}")

        async with self.pool.acquire() as conn:
            async with conn.transaction():
                current = await conn.fetchrow(
                    """
                    SELECT sender_name, email_address, contact_number, visa_category,
                           lead_source, assigned_consultant, source_box
                    FROM leads
                    WHERE lead_id = $1
                    FOR UPDATE
                    """,
                    lead_id,
                )
                if current is None:
                    return None

                updates: dict[str, Any] = {}
                changed_fields: list[str] = []
                for key, value in fields.items():
                    column = column_map[key]
                    normalized = value
                    if isinstance(normalized, str):
                        normalized = normalized.strip()
                    if key in {"phone", "visa_category", "source", "assigned_consultant"} and normalized == "":
                        normalized = None
                    if key in {"name", "email", "brand"} and not normalized:
                        continue
                    if current[column] != normalized:
                        updates[column] = normalized
                        changed_fields.append(key)

                if not updates:
                    row = await conn.fetchrow("SELECT * FROM leads WHERE lead_id = $1", lead_id)
                    return row_to_lead(row)

                set_clauses: list[str] = []
                values: list[Any] = [lead_id]
                for column, value in updates.items():
                    values.append(value)
                    set_clauses.append(f"{column} = ${len(values)}")
                if "email_address" in updates:
                    values.append(email_domain(str(updates["email_address"])))
                    set_clauses.append(f"email_domain = ${len(values)}")
                set_clauses.append("updated_at = NOW()")

                row = await conn.fetchrow(
                    f"""
                    UPDATE leads
                    SET {", ".join(set_clauses)}
                    WHERE lead_id = $1
                    RETURNING *
                    """,
                    *values,
                )

                for field in changed_fields:
                    await conn.execute(
                        """
                        INSERT INTO audit_events (lead_id, event_type, actor, metadata)
                        VALUES ($1, $2, $3, $4::jsonb)
                        """,
                        lead_id,
                        "lead.fields.edited",
                        actor,
                        json.dumps({"field": field, "changed": True}),
                    )
        return row_to_lead(row)

    async def approve_for_send(self, lead_id: str, actor: str) -> tuple[LeadRecord | None, str | None]:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                current = await conn.fetchrow(
                    "SELECT status FROM leads WHERE lead_id = $1 FOR UPDATE",
                    lead_id,
                )
                if current is None:
                    return None, None

                previous_actor = await conn.fetchval(
                    """
                    SELECT actor
                    FROM audit_events
                    WHERE lead_id = $1
                      AND event_type IN ('lead.review.submitted', 'lead.drafts.edited')
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    lead_id,
                )
                if previous_actor == actor:
                    return None, "same_actor"

                row = await conn.fetchrow(
                    """
                    UPDATE leads
                    SET status = 'sent', updated_at = NOW()
                    WHERE lead_id = $1
                    RETURNING *
                    """,
                    lead_id,
                )
                await conn.execute(
                    """
                    INSERT INTO audit_events (lead_id, event_type, actor, metadata)
                    VALUES ($1, $2, $3, $4::jsonb)
                    """,
                    lead_id,
                    "lead.approved",
                    actor,
                    json.dumps(
                        {
                            "previous_status": current["status"],
                            "four_eye_source_actor": previous_actor,
                        }
                    ),
                )
        return row_to_lead(row), None

    async def reject_review(self, lead_id: str, actor: str, reason: str | None) -> LeadRecord | None:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                current = await conn.fetchrow(
                    "SELECT status FROM leads WHERE lead_id = $1 FOR UPDATE",
                    lead_id,
                )
                if current is None:
                    return None

                row = await conn.fetchrow(
                    """
                    UPDATE leads
                    SET status = 'drafted', updated_at = NOW()
                    WHERE lead_id = $1
                    RETURNING *
                    """,
                    lead_id,
                )
                await conn.execute(
                    """
                    INSERT INTO audit_events (lead_id, event_type, actor, metadata)
                    VALUES ($1, $2, $3, $4::jsonb)
                    """,
                    lead_id,
                    "lead.review.rejected",
                    actor,
                    json.dumps(
                        {
                            "previous_status": current["status"],
                            "reason_present": bool(reason),
                            "reason_length": len(reason or ""),
                        }
                    ),
                )
        return row_to_lead(row)

    async def confirm_rejection(self, lead_id: str, actor: str, reason: str | None) -> LeadRecord | None:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                current = await conn.fetchrow(
                    "SELECT status, dnq_reason FROM leads WHERE lead_id = $1 FOR UPDATE",
                    lead_id,
                )
                if current is None:
                    return None

                row = await conn.fetchrow(
                    """
                    UPDATE leads
                    SET status = 'dnq', updated_at = NOW()
                    WHERE lead_id = $1
                    RETURNING *
                    """,
                    lead_id,
                )
                await conn.execute(
                    """
                    INSERT INTO audit_events (lead_id, event_type, actor, metadata)
                    VALUES ($1, $2, $3, $4::jsonb)
                    """,
                    lead_id,
                    "lead.reject.confirmed",
                    actor,
                    json.dumps(
                        {
                            "previous_status": current["status"],
                            "dnq_reason": current["dnq_reason"],
                            "reason_present": bool(reason),
                            "reason_length": len(reason or ""),
                        }
                    ),
                )
        return row_to_lead(row)

    async def edit_draft(
        self,
        lead_id: str,
        actor: str,
        *,
        email_draft: str | None,
        whatsapp_draft: str | None,
        phone_script: str | None,
        internal_whatsapp_post: str | None,
        reason: str | None,
    ) -> LeadRecord | None:
        changed_fields = [
            name
            for name, value in [
                ("email_draft", email_draft),
                ("whatsapp_draft", whatsapp_draft),
                ("phone_script", phone_script),
                ("internal_whatsapp_post", internal_whatsapp_post),
            ]
            if value is not None
        ]
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                current = await conn.fetchrow(
                    "SELECT status FROM leads WHERE lead_id = $1 FOR UPDATE",
                    lead_id,
                )
                if current is None:
                    return None

                row = await conn.fetchrow(
                    """
                    UPDATE leads
                    SET
                        email_draft = COALESCE($2, email_draft),
                        whatsapp_draft = COALESCE($3, whatsapp_draft),
                        phone_script = COALESCE($4, phone_script),
                        internal_whatsapp_post = COALESCE($5, internal_whatsapp_post),
                        status = 'in_review',
                        updated_at = NOW()
                    WHERE lead_id = $1
                    RETURNING *
                    """,
                    lead_id,
                    email_draft,
                    whatsapp_draft,
                    phone_script,
                    internal_whatsapp_post,
                )
                await conn.execute(
                    """
                    INSERT INTO audit_events (lead_id, event_type, actor, metadata)
                    VALUES ($1, $2, $3, $4::jsonb)
                    """,
                    lead_id,
                    "lead.drafts.edited",
                    actor,
                    json.dumps(
                        {
                            "previous_status": current["status"],
                            "changed_fields": changed_fields,
                            "reason_present": bool(reason),
                            "reason_length": len(reason or ""),
                        }
                    ),
                )
        return row_to_lead(row)

    async def persist_qualification(
        self,
        lead_id: str,
        *,
        dnq_reason: str | None,
        risk_flags: tuple[str, ...],
        actor: str,
    ) -> LeadRecord | None:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                current = await conn.fetchrow(
                    "SELECT lead_id, status FROM leads WHERE lead_id = $1 FOR UPDATE",
                    lead_id,
                )
                if current is None:
                    return None

                row = await conn.fetchrow(
                    """
                    UPDATE leads
                    SET
                        dnq_reason = $2::text,
                        risk_flags = $3::jsonb,
                        status = CASE
                            WHEN $2::text IS NOT NULL THEN 'dnq'
                            WHEN status = 'dnq' THEN 'received'
                            ELSE status
                        END,
                        updated_at = NOW()
                    WHERE lead_id = $1
                    RETURNING *
                    """,
                    lead_id,
                    dnq_reason,
                    json.dumps(list(risk_flags)),
                )
                await conn.execute(
                    """
                    INSERT INTO audit_events (lead_id, event_type, actor, metadata)
                    VALUES ($1, $2, $3, $4::jsonb)
                    """,
                    lead_id,
                    "lead.qualification.persisted",
                    actor,
                    json.dumps(
                        {
                            "is_dnq": dnq_reason is not None,
                            "dnq_reason": dnq_reason,
                            "risk_flags": list(risk_flags),
                        }
                    ),
                )
        return row_to_lead(row)

    async def persist_score(
        self,
        lead_id: str,
        result: LeadScoreResult,
        provider: str,
        model: str,
        temperature: float,
        actor: str,
    ) -> LeadRecord | None:
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                current = await conn.fetchrow(
                    "SELECT lead_id, status FROM leads WHERE lead_id = $1 FOR UPDATE",
                    lead_id,
                )
                if current is None:
                    return None

                row = await conn.fetchrow(
                    """
                    UPDATE leads
                    SET
                        lead_score = $2,
                        score_confidence = $3,
                        score_rationale = $4,
                        escalation_flag = $5,
                        soft_dnq_warning = $6,
                        score_provider = $7,
                        score_model = $8,
                        score_temperature = $9,
                        scored_at = NOW(),
                        status = CASE
                            WHEN $3 = 'low' THEN 'in_review'
                            WHEN status IN ('received', 'contacted') THEN 'scored'
                            ELSE status
                        END,
                        updated_at = NOW()
                    WHERE lead_id = $1
                    RETURNING *
                    """,
                    lead_id,
                    result.lead_score,
                    result.score_confidence,
                    result.score_rationale,
                    result.escalation_flag,
                    result.soft_dnq_warning,
                    provider,
                    model,
                    temperature,
                )
                await conn.execute(
                    """
                    INSERT INTO audit_events (lead_id, event_type, actor, metadata)
                    VALUES ($1, $2, $3, $4::jsonb)
                    """,
                    lead_id,
                    "lead.score.persisted",
                    actor,
                    json.dumps(
                        {
                            "provider": provider,
                            "model": model,
                            "temperature": temperature,
                            "lead_score": result.lead_score,
                            "score_confidence": result.score_confidence,
                            "escalation_flag": result.escalation_flag,
                        }
                    ),
                )
        return row_to_lead(row)

    async def persist_drafts(
        self,
        lead_id: str,
        result: DraftResult,
        provider: str,
        model: str,
        temperature: float,
        actor: str,
    ) -> LeadRecord | None:
        draft_data = result.model_dump(mode="json")
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                current = await conn.fetchrow(
                    "SELECT lead_id, status FROM leads WHERE lead_id = $1 FOR UPDATE",
                    lead_id,
                )
                if current is None:
                    return None

                row = await conn.fetchrow(
                    """
                    UPDATE leads
                    SET
                        email_draft = $2,
                        whatsapp_draft = $3,
                        phone_script = $4,
                        internal_whatsapp_post = $5,
                        draft_fields = $6::jsonb,
                        draft_provider = $7,
                        draft_model = $8,
                        draft_temperature = $9,
                        drafted_at = NOW(),
                        status = CASE
                            WHEN status IN ('received', 'contacted', 'scored') THEN 'drafted'
                            ELSE status
                        END,
                        updated_at = NOW()
                    WHERE lead_id = $1
                    RETURNING *
                    """,
                    lead_id,
                    result.email_draft,
                    result.whatsapp_draft,
                    result.phone_script,
                    result.internal_whatsapp_post,
                    json.dumps(draft_data),
                    provider,
                    model,
                    temperature,
                )
                await conn.execute(
                    """
                    INSERT INTO audit_events (lead_id, event_type, actor, metadata)
                    VALUES ($1, $2, $3, $4::jsonb)
                    """,
                    lead_id,
                    "lead.drafts.persisted",
                    actor,
                    json.dumps(
                        {
                            "provider": provider,
                            "model": model,
                            "temperature": temperature,
                            "template_id": result.template_id,
                            "fee_source": result.fee_source,
                            "professional_fee_zar": result.professional_fee_zar,
                            "admin_fee_zar": result.admin_fee_zar,
                            "dnq_reason": result.dnq_reason,
                            "alternative_suggestions": result.alternative_suggestions,
                            "has_whatsapp": bool(result.whatsapp_draft),
                            "has_phone_script": bool(result.phone_script),
                            "has_internal_post": bool(result.internal_whatsapp_post),
                        }
                    ),
                )
        return row_to_lead(row)

    async def list_audit_events(self, lead_id: str) -> list[dict[str, Any]]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT event_id, lead_id, event_type, actor, metadata, created_at
                FROM audit_events
                WHERE lead_id = $1
                ORDER BY created_at ASC
                """,
                lead_id,
            )
        return [dict(row) for row in rows]
