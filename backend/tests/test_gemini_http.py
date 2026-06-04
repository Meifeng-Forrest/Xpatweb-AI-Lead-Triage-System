import unittest

import httpx

from app.services.gemini_http import gemini_error_summary


class GeminiHttpTest(unittest.TestCase):
    def test_extracts_safe_google_error_codes(self) -> None:
        request = httpx.Request("POST", "https://generativelanguage.googleapis.com/test")
        response = httpx.Response(
            400,
            request=request,
            json={
                "error": {
                    "status": "INVALID_ARGUMENT",
                    "details": [{"reason": "API_KEY_INVALID"}],
                }
            },
        )
        error = httpx.HTTPStatusError("bad request", request=request, response=response)

        self.assertEqual(
            gemini_error_summary(error),
            {
                "status_code": 400,
                "error_status": "INVALID_ARGUMENT",
                "error_reason": "API_KEY_INVALID",
            },
        )


if __name__ == "__main__":
    unittest.main()
