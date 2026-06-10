import argparse
import asyncio
import json
import logging
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import get_settings
from app.services.llm_factory import get_native_json_triage_service, get_triage_service
from app.services.openai_compatible_adapters import OpenAICompatibleTriageAdapter
from app.services.scoring_examples import SCORING_REGRESSION_CASES


logger = logging.getLogger("lead_triage.scripts.scoring_regression")


def lead_from_case(case: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(
        lead_id=f"regression-row-{case['row_id']}",
        source_box="XP",
        lead_source=case["lead_source"],
        sender_name="Regression Fixture",
        email_domain="other_personal",
        visa_category=case["visa_category"],
        lead_type="Individual",
        current_visa=None,
        pr_route=None,
        nationality=None,
        is_first_world=None,
        job_title=None,
        net_worth_indicator=None,
        has_job_offer=None,
        qualifying_work_visa_years=None,
        annual_salary_zar=None,
        pbs_total_score_below_100=None,
        relationship_duration=None,
        marriage_type=None,
        rejection_date=None,
        urgency_flag=False,
        multi_visa_flag=False,
        email_coherence="high",
        additional_info=case["additional_info"],
        extracted_fields={
            "fixture_row_id": case["row_id"],
            "expected_reason": case["reason"],
        },
        lead_score=None,
        dnq_reason=None,
        risk_flags=[],
        score_confidence=None,
        score_rationale=None,
        soft_dnq_warning=None,
    )


def calculate_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    correct = sum(1 for row in results if row["expected_score"] == row["actual_score"])
    expected_counts = Counter(row["expected_score"] for row in results)
    correct_by_score = Counter(
        row["expected_score"] for row in results if row["expected_score"] == row["actual_score"]
    )
    recall = {
        score: round(correct_by_score[score] / expected_counts[score], 4)
        for score in sorted(expected_counts)
    }
    return {
        "total": total,
        "correct": correct,
        "accuracy": round(correct / total, 4) if total else 0.0,
        "recall": recall,
    }


async def run_regression(
    *,
    limit: int | None = None,
    row_ids: set[int] | None = None,
    dry_run: bool = False,
    service_name: str = "configured",
) -> dict[str, Any]:
    selected_cases = [
        case for case in SCORING_REGRESSION_CASES
        if row_ids is None or int(case["row_id"]) in row_ids
    ]
    cases = list(selected_cases[:limit] if limit else selected_cases)
    logger.info(
        "[scoring-regression] enter %s",
        {"case_count": len(cases), "dry_run": dry_run, "service": service_name, "row_ids": sorted(row_ids) if row_ids else None},
    )

    if dry_run:
        results = [
            {
                "row_id": case["row_id"],
                "visa_category": case["visa_category"],
                "expected_score": case["expected_score"],
                "actual_score": case["expected_score"],
                "score_confidence": "dry_run",
                "score_rationale": "Dry run uses expected score without model call.",
            }
            for case in cases
        ]
    else:
        settings = get_settings()
        if service_name == "native-gemini":
            triage = get_native_json_triage_service(settings)
        elif service_name == "shengsuanyun-openai":
            triage = OpenAICompatibleTriageAdapter(
                provider="shengsuanyun",
                base_url=settings.shengsuanyun_base_url,
                api_key=settings.shengsuanyun_api_key,
                model=settings.shengsuanyun_model,
                thinking_disabled=True,
            )
        else:
            triage = get_triage_service(settings)
        results = []
        for case in cases:
            lead = lead_from_case(case)
            score = await triage.score_lead(lead)
            row = {
                "row_id": case["row_id"],
                "visa_category": case["visa_category"],
                "expected_score": case["expected_score"],
                "actual_score": score.lead_score,
                "score_confidence": score.score_confidence,
                "score_rationale": score.score_rationale,
            }
            results.append(row)
            logger.info(
                "[scoring-regression] case_result %s",
                {
                    "row_id": row["row_id"],
                    "expected_score": row["expected_score"],
                    "actual_score": row["actual_score"],
                    "score_confidence": row["score_confidence"],
                },
            )

    metrics = calculate_metrics(results)
    report = {"metrics": metrics, "results": results}
    logger.info("[scoring-regression] success %s", metrics)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run §13.4 scoring regression without exposing secrets.")
    parser.add_argument("--limit", type=int, default=None, help="Optional number of cases to run.")
    parser.add_argument(
        "--row-ids",
        default=None,
        help="Comma-separated §13.4 row ids to run, for targeted boundary tuning.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate runner plumbing without model calls.")
    parser.add_argument(
        "--service",
        choices=("configured", "native-gemini", "shengsuanyun-openai"),
        default="configured",
        help="Triage service to use for real model calls.",
    )
    args = parser.parse_args()
    row_ids = None
    if args.row_ids:
        row_ids = {int(row_id.strip()) for row_id in args.row_ids.split(",") if row_id.strip()}

    logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
    report = asyncio.run(
        run_regression(
            limit=args.limit,
            row_ids=row_ids,
            dry_run=args.dry_run,
            service_name=args.service,
        )
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
