import logging

import asyncpg

from app.repositories.leads import LeadRecord
from app.repositories.users import RoutingRuleRepository
from app.services.ports import ConsoleNotifier, NotificationPayload, Notifier

logger = logging.getLogger("lead_triage.services.routing")

ROUTING_CATEGORIES = ("escalation", "dnq_reject", "visa_verification", "standard_review")


class LeadRoutingService:
    def __init__(self, pool: asyncpg.Pool, notifier: Notifier | None = None) -> None:
        self.routing_rules = RoutingRuleRepository(pool)
        self.notifier = notifier or ConsoleNotifier()

    async def route_after_draft(self, lead: LeadRecord) -> None:
        category = self._target_category(lead)
        if category is None:
            logger.info(
                "[routing/lead] skipped %s",
                {"lead_id": lead.lead_id, "reason": "no_route_category", "lead_score": lead.lead_score},
            )
            return

        targets = await self.routing_rules.list_recipients(category)
        logger.info(
            "[routing/lead] enter %s",
            {
                "lead_id": lead.lead_id,
                "category": category,
                "target_count": len(targets),
                "lead_score": lead.lead_score,
                "dnq": bool(lead.dnq_reason),
                "escalation": lead.escalation_flag,
            },
        )
        for target in targets:
            await self.notifier.send_call_alert(
                NotificationPayload(
                    lead_id=lead.lead_id,
                    source_box=lead.source_box,
                    rating=lead.lead_score or "unscored",
                    reason=f"category:{category};user:{target.user_id}",
                )
            )
        logger.info(
            "[routing/lead] success %s",
            {"lead_id": lead.lead_id, "category": category, "target_count": len(targets)},
        )

    def _target_category(self, lead: LeadRecord) -> str | None:
        # category 只表达“这条线索属于哪类路由场景”；具体通知谁由 routing_rules 配置决定。
        if lead.escalation_flag:
            return "escalation"
        if lead.dnq_reason:
            return "dnq_reject"
        if self._needs_visa_verification(lead):
            return "visa_verification"
        if lead.lead_score in {"GD", "MF", "MD", "BD"}:
            return "standard_review"
        return None

    def _needs_visa_verification(self, lead: LeadRecord) -> bool:
        fields = [lead.visa_category, lead.current_visa, lead.pr_route, lead.additional_info]
        return any("verify" in (value or "").lower() or "verification" in (value or "").lower() for value in fields)
