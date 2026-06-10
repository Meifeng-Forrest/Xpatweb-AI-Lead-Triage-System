import json
import logging
import time
from typing import Any

import httpx

from app.logging import summarize_text


class OpenAICompatibleJsonClient:
    def __init__(
        self,
        *,
        provider: str,
        base_url: str,
        api_key: str,
        model: str,
        logger: logging.Logger,
        thinking_disabled: bool = False,
    ) -> None:
        self.provider = provider
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.logger = logger
        self.thinking_disabled = thinking_disabled

    async def generate_json(
        self,
        *,
        tag: str,
        prompt: str,
        temperature: float,
        summary: dict[str, Any],
        max_tokens: int = 1600,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError(f"{self.provider} API key is not configured")

        reasoning_disabled = self.thinking_disabled and self.provider == "shengsuanyun"
        request_summary = {
            **summary,
            "provider": self.provider,
            "model": self.model,
            "temperature": temperature,
            "reasoning_disabled": reasoning_disabled,
            "prompt": summarize_text(prompt),
        }
        self.logger.info("%s enter %s", tag, request_summary)
        started_at = time.perf_counter()

        try:
            # 部分推理模型在较长草稿输出时常超过一分钟，读取超时放宽到两分钟，
            # 由 Celery 继续负责网络失败后的重试。
            async with httpx.AsyncClient(timeout=120) as client:
                request_body = {
                    "model": self.model,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "response_format": {"type": "json_object"},
                    "messages": [{"role": "user", "content": prompt}],
                }
                if reasoning_disabled:
                    # 实测 Shengsuanyun 的 Gemini 路由会忽略 thinking.type=disabled；
                    # reasoning.enabled=false 才会停止 reasoning token 消耗。
                    request_body["reasoning"] = {"enabled": False}
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json=request_body,
                )
            response.raise_for_status()
            response_data = response.json()
            choice = response_data["choices"][0]
            content = choice["message"]["content"]
            if not content:
                finish_reason = choice.get("finish_reason")
                usage = response_data.get("usage")
                raise ValueError(f"Model response content is empty; finish_reason={finish_reason}; usage={usage}")
            data = json.loads(content)
            if not isinstance(data, dict):
                raise ValueError("Model response JSON must be an object")
        except (httpx.HTTPError, KeyError, IndexError, TypeError, json.JSONDecodeError, ValueError) as exc:
            response_status = None
            response_body = None
            if isinstance(exc, httpx.HTTPStatusError):
                response_status = exc.response.status_code
                response_body = exc.response.text[:500]
            self.logger.exception(
                "%s fail %s",
                tag,
                {
                    **request_summary,
                    "ms": round((time.perf_counter() - started_at) * 1000),
                    "error_type": exc.__class__.__name__,
                    "error": str(exc)[:300],
                    "response_status": response_status,
                    "response_body": response_body,
                },
            )
            raise

        self.logger.info(
            "%s success %s",
            tag,
            {
                **request_summary,
                "ms": round((time.perf_counter() - started_at) * 1000),
                "field_count": len(data),
            },
        )
        return data
