import logging
import time
from dataclasses import dataclass

from app.config import Settings
from app.repositories.leads import LeadRecord, LeadRepository
from app.schemas import LeadScoreResult
from app.services.llm_factory import TriageService, get_extraction_service, get_triage_service
from app.services.routing import LeadRoutingService
from app.services.qualification_rules import DNQ_REASONS, QualificationResult, qualify_lead

logger = logging.getLogger("lead_triage.services.lead_pipeline")


@dataclass(frozen=True)
class PipelineRun:
    lead: LeadRecord
    qualification: QualificationResult
    scoring_skipped: bool


def deterministic_dnq_score(reason: str, risk_flags: tuple[str, ...]) -> LeadScoreResult:
    warning = f"Human review required: {', '.join(risk_flags)}" if risk_flags else None
    return LeadScoreResult(
        lead_score="BD",
        score_confidence="high",
        score_rationale=f"{reason}: {DNQ_REASONS[reason]}",
        escalation_flag=False,
        soft_dnq_warning=warning,
    )


def draft_provider(result, triage: TriageService | None = None) -> str:
    return "template" if getattr(result, "template_id", None) else (triage.provider if triage else "llm")


def draft_model(result, triage: TriageService) -> str:
    return getattr(result, "template_id", None) or triage.draft_model


def draft_temperature(result, triage: TriageService) -> float:
    return 0.0 if draft_provider(result, triage) == "template" else triage.draft_temperature


class LeadPipelineService:
    def __init__(self, repo: LeadRepository, settings: Settings) -> None:
        self.repo = repo
        self.settings = settings
        self.extraction = get_extraction_service(settings)
        self.triage = get_triage_service(settings)
        self.routing = LeadRoutingService(repo.pool) if hasattr(repo, "pool") else None

    async def run(self, lead: LeadRecord, *, skip_extraction: bool = False) -> PipelineRun:
        started_at = time.perf_counter()
        logger.info(
            "[pipeline/lead] enter %s",
            {
                "lead_id": lead.lead_id,
                "source_box": lead.source_box,
                "raw_message_length": len(lead.raw_message),
                "skip_extraction": skip_extraction,
            },
        )

        if skip_extraction:
            current = lead
            extracted = lead
            logger.info("[pipeline/lead] extraction_skipped %s", {"lead_id": lead.lead_id})
        else:
            extracted = await self.extraction.extract_manual_text(lead.raw_message)
            current = await self.repo.persist_extracted_fields(
                lead_id=lead.lead_id,
                extracted=extracted,
                provider=self.extraction.provider,
                model=self.extraction.model,
                temperature=self.extraction.temperature,
                actor="pipeline",
            )
            if current is None:
                raise LookupError("Lead disappeared while persisting extraction")
            logger.info("[pipeline/lead] extracted %s", {"lead_id": lead.lead_id})

        qualification = qualify_lead(extracted)
        current = await self.repo.persist_qualification(
            lead_id=lead.lead_id,
            dnq_reason=qualification.dnq_reason,
            risk_flags=qualification.risk_flags,
            actor="pipeline",
        )
        if current is None:
            raise LookupError("Lead disappeared while persisting qualification")
        logger.info(
            "[pipeline/lead] qualified %s",
            {
                "lead_id": lead.lead_id,
                "is_dnq": qualification.is_dnq,
                "dnq_reason": qualification.dnq_reason,
                "risk_flags": list(qualification.risk_flags),
            },
        )

        scoring_skipped = qualification.is_dnq
        score_already_persisted = bool(
            getattr(current, "lead_score", None)
            and getattr(current, "score_confidence", None)
            and getattr(current, "score_rationale", None)
        )
        if score_already_persisted:
            logger.info(
                "[pipeline/lead] score_already_persisted %s",
                {"lead_id": lead.lead_id, "lead_score": current.lead_score},
            )
        elif scoring_skipped:
            if qualification.dnq_reason is None:
                raise RuntimeError("DNQ qualification did not include a reason")
            score = deterministic_dnq_score(qualification.dnq_reason, qualification.risk_flags)
            score_provider = "rules"
            score_model = "dnq-hard-rules-v1"
        else:
            score = await self.triage.score_lead(current)
            score_provider = self.triage.provider
            score_model = self.triage.score_model

        if not score_already_persisted:
            current = await self.repo.persist_score(
                lead_id=lead.lead_id,
                result=score,
                provider=score_provider,
                model=score_model,
                temperature=0.0 if scoring_skipped else self.triage.score_temperature,
                actor="pipeline",
            )
            if current is None:
                raise LookupError("Lead disappeared while persisting score")
            logger.info(
                "[pipeline/lead] scored %s",
                {
                    "lead_id": lead.lead_id,
                    "lead_score": score.lead_score,
                    "scoring_skipped": scoring_skipped,
                },
            )

        drafts = await self.triage.draft_for_lead(current)
        current = await self.repo.persist_drafts(
            lead_id=lead.lead_id,
            result=drafts,
            provider=draft_provider(drafts, self.triage),
            model=draft_model(drafts, self.triage),
            temperature=draft_temperature(drafts, self.triage),
            actor="pipeline",
        )
        if current is None:
            raise LookupError("Lead disappeared while persisting drafts")

        if self.routing is not None:
            await self.routing.route_after_draft(current)

        logger.info(
            "[pipeline/lead] success %s",
            {
                "lead_id": lead.lead_id,
                "status": current.status,
                "is_dnq": qualification.is_dnq,
                "ms": round((time.perf_counter() - started_at) * 1000),
            },
        )
        return PipelineRun(lead=current, qualification=qualification, scoring_skipped=scoring_skipped)
