import logging
import time
from collections.abc import Callable
from typing import Any


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def summarize_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    domain = email.split("@", 1)[1]
    return f"***@{domain}"


def summarize_text(value: str | None) -> dict[str, int | bool]:
    text = value or ""
    return {"present": bool(text), "length": len(text)}


async def log_async_call(
    logger: logging.Logger,
    tag: str,
    summary: dict[str, Any],
    call: Callable[[], Any],
) -> Any:
    logger.info("%s enter %s", tag, summary)
    start = time.perf_counter()
    try:
        result = await call()
        logger.info("%s success %s", tag, {"ms": round((time.perf_counter() - start) * 1000)})
        return result
    except Exception as exc:
        logger.exception(
            "%s fail %s",
            tag,
            {"ms": round((time.perf_counter() - start) * 1000), "error": str(exc)},
        )
        raise
