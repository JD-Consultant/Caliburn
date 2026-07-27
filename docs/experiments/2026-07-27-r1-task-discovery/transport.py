"""R1 experiment-only thin transport：一次 attempt 一次 HTTP，永不 retry。

設計 §8.3／§9.2。責任邊界刻意很窄：
送出、收回、正規化 wire facts。**不碰 Task 語意、不碰 grader、不碰 Current Work Model、
不做 production retry／fallback／queue。**

§3.2：provider／transport 失敗不算模型品質結果。本模組把它們標成獨立 outcome，
由上層決定要不要在修好環境後補一個**新的** attempt —— 絕不在同一個 attempt 內偷偷重試。
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx

from provider_request import ChatRequest, verify_request_is_exact

# 只保留判讀路由與快取需要的回應 header，避免把不相干內容寫進 capture。
CAPTURED_RESPONSE_HEADERS = (
    "x-openrouter-cache-status",
    "x-openrouter-cache-age",
    "x-openrouter-cache-ttl",
    "x-request-id",
    "content-type",
)

OUTCOME_OK = "ok"
OUTCOME_HTTP_ERROR = "http_error"
OUTCOME_TRANSPORT_ERROR = "transport_error"
OUTCOME_INVALID_JSON = "invalid_json"
OUTCOME_REQUEST_REJECTED = "request_rejected"

# 這些 outcome 是環境問題，不是模型品質結果（設計 §3.2）。
NON_QUALITY_OUTCOMES = frozenset(
    {OUTCOME_HTTP_ERROR, OUTCOME_TRANSPORT_ERROR, OUTCOME_REQUEST_REJECTED}
)


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    cost: str | None = None
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True)
class WireResult:
    """單次 attempt 的 wire facts。`attempt_count` 恆為 1 —— 這是契約，不是統計。"""

    outcome: str
    status_code: int | None
    headers: dict[str, str]
    body: Any
    raw_text: str | None
    latency_ms: int
    usage: TokenUsage
    error_message: str | None = None
    attempt_count: int = 1
    limitations: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_quality_sample(self) -> bool:
        """environment 失敗不得被當成模型答錯。"""
        return self.outcome == OUTCOME_OK


def _int_or_none(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _normalize_usage(body: Any) -> TokenUsage:
    if not isinstance(body, dict):
        return TokenUsage(limitations=("response body was not an object",))
    usage = body.get("usage")
    if not isinstance(usage, dict):
        return TokenUsage(limitations=("openrouter response did not include usage",))

    cost_text: str | None = None
    limitations: list[str] = []
    raw_cost = usage.get("cost")
    if raw_cost is not None:
        try:
            # 用 Decimal 正規化，避免浮點誤差進 manifest；存成字串保持 canonical JSON 穩定。
            cost_text = str(Decimal(str(raw_cost)))
        except (InvalidOperation, ValueError):
            limitations.append("openrouter usage cost was not a number")

    return TokenUsage(
        prompt_tokens=_int_or_none(usage.get("prompt_tokens")),
        completion_tokens=_int_or_none(usage.get("completion_tokens")),
        total_tokens=_int_or_none(usage.get("total_tokens")),
        cost=cost_text,
        limitations=tuple(limitations),
    )


def _captured_headers(response: httpx.Response) -> dict[str, str]:
    lowered = {k.lower(): v for k, v in response.headers.items()}
    return {name: lowered[name] for name in CAPTURED_RESPONSE_HEADERS if name in lowered}


async def send_once(
    client: httpx.AsyncClient,
    request: ChatRequest,
    *,
    api_key: str,
) -> WireResult:
    """送出**恰好一次** HTTP。任何失敗都直接回傳，不重試、不換 provider。

    `api_key` 只進 Authorization header，永遠不進回傳值 —— capture 層也就無從保存它。
    """
    exactness = verify_request_is_exact(request.body)
    if not exactness.ok:
        return WireResult(
            outcome=OUTCOME_REQUEST_REJECTED,
            status_code=None,
            headers={},
            body=None,
            raw_text=None,
            latency_ms=0,
            usage=TokenUsage(),
            error_message="; ".join(f.message for f in exactness.findings),
            limitations=tuple(f"request rejected: {f.check}" for f in exactness.findings),
        )

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    started = time.monotonic()
    try:
        response = await client.post(request.url, json=request.body, headers=headers)
    except httpx.HTTPError as exc:
        return WireResult(
            outcome=OUTCOME_TRANSPORT_ERROR,
            status_code=None,
            headers={},
            body=None,
            raw_text=None,
            latency_ms=int((time.monotonic() - started) * 1000),
            usage=TokenUsage(),
            error_message=f"{type(exc).__name__}: {exc}",
        )

    latency_ms = int((time.monotonic() - started) * 1000)
    captured = _captured_headers(response)
    raw_text = response.text

    if response.status_code >= 400:
        # 429／5xx 都在這裡結束。要重跑就由上層開一個新的 attempt。
        return WireResult(
            outcome=OUTCOME_HTTP_ERROR,
            status_code=response.status_code,
            headers=captured,
            body=None,
            raw_text=raw_text,
            latency_ms=latency_ms,
            usage=TokenUsage(),
            error_message=f"HTTP {response.status_code}",
        )

    try:
        body = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        return WireResult(
            outcome=OUTCOME_INVALID_JSON,
            status_code=response.status_code,
            headers=captured,
            body=None,
            raw_text=raw_text,
            latency_ms=latency_ms,
            usage=TokenUsage(),
            error_message=f"response was not valid JSON: {exc}",
        )

    return WireResult(
        outcome=OUTCOME_OK,
        status_code=response.status_code,
        headers=captured,
        body=body,
        raw_text=raw_text,
        latency_ms=latency_ms,
        usage=_normalize_usage(body),
    )


def build_client(timeout_seconds: float) -> httpx.AsyncClient:
    """建立不會自動重試的 client。

    `httpx.AsyncHTTPTransport(retries=0)` 是明寫的，不靠預設值 ——
    預設值哪天改了，我們的「單次 HTTP」保證不能跟著壞。
    """
    return httpx.AsyncClient(
        timeout=httpx.Timeout(timeout_seconds),
        transport=httpx.AsyncHTTPTransport(retries=0),
        follow_redirects=False,
    )
