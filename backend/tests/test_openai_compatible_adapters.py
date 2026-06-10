import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from pydantic import ValidationError

from app.services.openai_compatible_adapters import OpenAICompatibleExtractionAdapter, OpenAICompatibleTriageAdapter


def valid_extracted() -> dict:
    return {
        "sender_name": "Jane Doe",
        "email_address": "jane@example.com",
        "contact_number": None,
        "email_domain": "other_personal",
        "lead_type": "Individual",
        "visa_category": "Retired Person Visa",
        "current_visa": None,
        "pr_route": None,
        "nationality": None,
        "is_first_world": None,
        "job_title": None,
        "net_worth_indicator": None,
        "has_job_offer": None,
        "qualifying_work_visa_years": None,
        "annual_salary_zar": None,
        "pbs_total_score_below_100": None,
        "relationship_duration": None,
        "marriage_type": None,
        "rejection_date": None,
        "urgency_flag": False,
        "multi_visa_flag": False,
        "email_coherence": "high",
        "additional_info": "Retirement enquiry",
    }


def extraction_adapter() -> OpenAICompatibleExtractionAdapter:
    return OpenAICompatibleExtractionAdapter(
        provider="fixture-provider",
        base_url="https://provider.example/v1",
        api_key="test-key",
        model="fixture-model",
    )


def triage_adapter() -> OpenAICompatibleTriageAdapter:
    return OpenAICompatibleTriageAdapter(
        provider="fixture-provider",
        base_url="https://provider.example/v1",
        api_key="test-key",
        model="fixture-model",
    )


def kimi_triage_adapter() -> OpenAICompatibleTriageAdapter:
    return OpenAICompatibleTriageAdapter(
        provider="kimi",
        base_url="https://provider.example/v1",
        api_key="test-key",
        model="kimi-k2.6",
    )


class OpenAICompatibleAdaptersTest(unittest.IsolatedAsyncioTestCase):
    async def test_valid_extraction_response_is_parsed(self) -> None:
        service = extraction_adapter()
        self.assertTrue(service.client.thinking_disabled)
        service.client.generate_json = AsyncMock(return_value=valid_extracted())

        result = await service.extract_manual_text("Retirement enquiry")

        self.assertEqual(result.sender_name, "Jane Doe")
        self.assertEqual(result.visa_category, "Retired Person Visa")
        self.assertEqual(service.client.generate_json.await_args.kwargs["max_tokens"], 1400)

    async def test_invalid_extraction_response_is_rejected(self) -> None:
        service = extraction_adapter()
        service.client.generate_json = AsyncMock(return_value={"sender_name": "Jane"})

        with self.assertRaises(ValidationError):
            await service.extract_manual_text("Incomplete response")

    async def test_score_uses_deterministic_temperature_and_domestic_worker_guardrail(self) -> None:
        service = triage_adapter()
        service.client.generate_json = AsyncMock(
            return_value={
                "lead_score": "BD",
                "score_confidence": "medium",
                "score_rationale": "Domestic worker work-visa assessment is a low-fit lead.",
                "escalation_flag": False,
                "soft_dnq_warning": None,
            }
        )

        await service.score_lead(
            SimpleNamespace(
                lead_id="lead-domestic-worker",
                source_box="XP",
                lead_source="Manual",
                sender_name="Lida Neveling",
                email_domain="other_personal",
                visa_category="Unknown",
                lead_type="Individual",
                current_visa=None,
                pr_route=None,
                nationality="Kenyan",
                is_first_world=False,
                job_title="Domestic worker",
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
                additional_info="Employer-sponsored domestic worker visa enquiry for a Kenyan housekeeper.",
                extracted_fields={},
                lead_score=None,
                dnq_reason=None,
                risk_flags=[],
                score_confidence=None,
                score_rationale=None,
                soft_dnq_warning=None,
            )
        )

        self.assertEqual(service.client.generate_json.await_args.kwargs["temperature"], 0.0)
        prompt = service.client.generate_json.await_args.kwargs["prompt"]
        self.assertIn("domestic worker", prompt)
        self.assertIn("score BD with medium confidence", prompt)

    async def test_kimi_score_temperature_uses_provider_supported_value(self) -> None:
        service = kimi_triage_adapter()

        self.assertEqual(service.score_temperature, 1.0)


if __name__ == "__main__":
    unittest.main()
