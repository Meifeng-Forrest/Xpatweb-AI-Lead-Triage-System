from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class NotificationPayload:
    lead_id: str
    source_box: str
    rating: str
    reason: str


class Notifier(ABC):
    @abstractmethod
    async def send_call_alert(self, payload: NotificationPayload) -> None:
        """发送 60 秒致电提醒；真实 Slack/Push 后续替换这里。"""


class ConsoleNotifier(Notifier):
    async def send_call_alert(self, payload: NotificationPayload) -> None:
        # 这里先只记录脱敏摘要，避免在未确认通知渠道前把业务逻辑卡住。
        print(
            "[notifier/console] call_alert",
            {
                "lead_id": payload.lead_id,
                "source_box": payload.source_box,
                "rating": payload.rating,
                "reason": payload.reason,
            },
        )


class CrmSink(ABC):
    @abstractmethod
    async def upsert_lead(self, lead_id: str) -> None:
        """写入 CRM/OneSheet/HubSpot 的统一入口；Phase 2 可替换实现。"""


class NoopCrmSink(CrmSink):
    async def upsert_lead(self, lead_id: str) -> None:
        print("[crm/noop] upsert_lead", {"lead_id": lead_id})
