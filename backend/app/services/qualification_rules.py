from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Mapping


DNQ_REASONS = {
    "DNQ-01": "Critical Skills Work Visa requires a formal job offer.",
    "DNQ-02": "Permanent Residence requires a current valid South African visa.",
    "DNQ-03": "Permanent Residence via the work visa route requires four qualifying years.",
    "DNQ-04": "The relative or spousal pathway requires a formally registered marriage.",
    "DNQ-05": "The appeal was submitted beyond the 10-working-day window.",
    "DNQ-06": "Visitor Visa Section 11(1) is not applicable to visa-exempt nationalities.",
}


@dataclass(frozen=True)
class QualificationResult:
    is_dnq: bool
    dnq_reason: str | None
    risk_flags: tuple[str, ...]


def _value(extracted: Mapping[str, Any] | Any, field: str) -> Any:
    if isinstance(extracted, Mapping):
        return extracted.get(field)
    return getattr(extracted, field, None)


def _parse_date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _is_explicit_negative(value: Any) -> bool:
    if value is False:
        return True
    if value is None or value is True:
        return False
    normalized = str(value).strip().lower()
    if not normalized:
        return False
    return normalized in {
        "no",
        "none",
        "no visa",
        "no current visa",
        "no valid visa",
        "no valid south african visa",
        "expired",
        "expired visa",
        "not valid",
    }


def is_beyond_10_working_days(rejection_date: Any, *, as_of: date | None = None) -> bool:
    rejected_on = _parse_date(rejection_date)
    today = as_of or date.today()
    if rejected_on is None or rejected_on >= today:
        return False

    # 决定日不计入上诉窗口；只计算之后经过的周一至周五。
    elapsed_working_days = sum(
        1
        for offset in range(1, (today - rejected_on).days + 1)
        if date.fromordinal(rejected_on.toordinal() + offset).weekday() < 5
    )
    return elapsed_working_days > 10


def apply_dnq_rules(
    extracted: Mapping[str, Any] | Any,
    *,
    as_of: date | None = None,
) -> tuple[bool, str | None]:
    """Apply only the six deterministic hard-DNQ rules from 业务规格 §4.1."""
    visa = _value(extracted, "visa_category")

    if visa == "Critical Skills Work Visa" and _value(extracted, "has_job_offer") is False:
        return True, "DNQ-01"

    if visa in ("Permanent Residence Permit", "PR (Financially Independent)") and _is_explicit_negative(
        _value(extracted, "current_visa")
    ):
        return True, "DNQ-02"

    if (
        visa == "Permanent Residence Permit"
        and _value(extracted, "pr_route") == "work_visa"
        and (_value(extracted, "qualifying_work_visa_years") or 0) < 4
    ):
        return True, "DNQ-03"

    if visa in ("Relative's Visa", "Relative's Spouse Visa", "Visitors Visa Section 11(6)") and _value(
        extracted, "marriage_type"
    ) in ("traditional", "unregistered"):
        return True, "DNQ-04"

    if visa == "Appeal Application" and is_beyond_10_working_days(
        _value(extracted, "rejection_date"), as_of=as_of
    ):
        return True, "DNQ-05"

    if visa == "Visitors Visa Section 11(1)" and _value(extracted, "is_first_world") is True:
        return True, "DNQ-06"

    return False, None


def apply_risk_flags(extracted: Mapping[str, Any] | Any) -> tuple[str, ...]:
    """Return soft-risk flags without rejecting the lead."""
    flags: list[str] = []
    visa = _value(extracted, "visa_category")
    salary = _value(extracted, "annual_salary_zar")

    if visa == "Points-Based System" and (
        (salary is not None and salary < 650_976)
        or _value(extracted, "pbs_total_score_below_100") is True
    ):
        flags.append("RISK-01")

    if visa == "Visitors Visa Section 11(6)" and _value(extracted, "relationship_duration") in (
        "less_than_1_month",
        "newly_married",
        "weak_evidence",
        "unspecified",
    ):
        flags.append("RISK-02")

    return tuple(flags)


def qualify_lead(extracted: Mapping[str, Any] | Any, *, as_of: date | None = None) -> QualificationResult:
    is_dnq, dnq_reason = apply_dnq_rules(extracted, as_of=as_of)
    return QualificationResult(
        is_dnq=is_dnq,
        dnq_reason=dnq_reason,
        risk_flags=apply_risk_flags(extracted),
    )
