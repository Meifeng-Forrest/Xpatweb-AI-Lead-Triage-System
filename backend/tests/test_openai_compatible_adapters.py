import unittest
from unittest.mock import AsyncMock

from pydantic import ValidationError

from app.services.openai_compatible_adapters import OpenAICompatibleExtractionAdapter


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


class OpenAICompatibleAdaptersTest(unittest.IsolatedAsyncioTestCase):
    async def test_valid_extraction_response_is_parsed(self) -> None:
        service = extraction_adapter()
        service.client.generate_json = AsyncMock(return_value=valid_extracted())

        result = await service.extract_manual_text("Retirement enquiry")

        self.assertEqual(result.sender_name, "Jane Doe")
        self.assertEqual(result.visa_category, "Retired Person Visa")

    async def test_invalid_extraction_response_is_rejected(self) -> None:
        service = extraction_adapter()
        service.client.generate_json = AsyncMock(return_value={"sender_name": "Jane"})

        with self.assertRaises(ValidationError):
            await service.extract_manual_text("Incomplete response")


if __name__ == "__main__":
    unittest.main()
