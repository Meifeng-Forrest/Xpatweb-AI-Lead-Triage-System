import unittest

import httpx

from app.services.native_json_adapters import provider_error_summary


class NativeJsonAdaptersTest(unittest.TestCase):
    def test_extracts_safe_provider_error_codes(self) -> None:
        request = httpx.Request("POST", "https://provider.example/test")
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
            provider_error_summary(error),
            {
                "status_code": 400,
                "error_status": "INVALID_ARGUMENT",
                "error_reason": "API_KEY_INVALID",
            },
        )


if __name__ == "__main__":
    unittest.main()
