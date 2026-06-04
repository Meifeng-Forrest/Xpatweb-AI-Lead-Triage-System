from typing import Any

import httpx


def gemini_error_summary(exc: Exception) -> dict[str, Any]:
    if not isinstance(exc, httpx.HTTPStatusError):
        return {"status_code": None, "error_status": None, "error_reason": exc.__class__.__name__}

    error_status = None
    error_reason = None
    try:
        payload = exc.response.json()
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        error_status = error.get("status")
        for detail in error.get("details", []):
            if isinstance(detail, dict) and detail.get("reason"):
                error_reason = detail["reason"]
                break
    except ValueError:
        pass

    return {
        "status_code": exc.response.status_code,
        "error_status": error_status,
        "error_reason": error_reason,
    }
