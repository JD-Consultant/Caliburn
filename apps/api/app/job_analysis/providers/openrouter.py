"""最小 OpenRouter Chat Completions adapter(T5)。

一次 operation ＝ **一次 HTTP**。沒有 fallback、沒有隱藏 retry、沒有 provider registry:
每一種失敗都以 typed 結果回傳,呼叫端自己決定要不要再來一次。

沿用已驗證的 wire invariants(ADR 0040 決定 26、ADR 0035):固定 exact model slug 與
provider endpoint、`allow_fallbacks: false`、`require_parameters: true`、
portable structured output(`response_format.json_schema`,`strict: true`)。

**config 不放 secret**:API key 由建構子傳入,不進任何會被 dump 的模型。

`complete()` 只收**已 render 的文字**:packet 的內部模型(以及裡面的 task_id／turn_id)
沒有路徑可以送到 provider。這是刻意的簽章設計,不是靠自律。
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Protocol

import httpx
from pydantic import Field, model_validator

from app.job_analysis.domain import DomainModel, NonEmptyText


CHAT_COMPLETIONS_URL = "https://openrouter.ai/api/v1/chat/completions"

_FORBIDDEN_MODELS = frozenset({"openrouter/auto", "openrouter/free"})


class OpenRouterConfig(DomainModel):
    """單一固定路由。model slug 必須是 Models API 的精確 ID。"""

    model: NonEmptyText
    provider_order: tuple[NonEmptyText, ...]
    max_output_tokens: int = Field(gt=0)
    timeout_seconds: float = Field(gt=0)

    @model_validator(mode="after")
    def route_is_exact(self):
        """別名／變體會讓「這輪跑的是哪個模型」變成不可知,連帶讓任何品質判斷失效。"""
        if self.model in _FORBIDDEN_MODELS:
            raise ValueError(f"{self.model!r} is a router alias, not an exact model ID")
        if ":" in self.model or self.model.startswith("~"):
            raise ValueError("model slug must not use a variant or alias shortcut")
        author, separator, slug = self.model.partition("/")
        if not (separator and author and slug) or "/" in slug:
            raise ValueError("model slug must be exactly 'author/slug'")
        if not self.provider_order:
            raise ValueError("provider_order must pin at least one endpoint")
        return self


class TransportResponse(DomainModel):
    status_code: int
    body: dict[str, Any] | None = None
    text: str = ""


class ChatTransport(Protocol):
    """一次 HTTP。adapter 不會呼叫第二次,實作也不得自行重試。"""

    async def __call__(
        self,
        *,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, Any],
        timeout: float,
    ) -> TransportResponse: ...


class ProviderFailureKind(StrEnum):
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    HTTP_STATUS = "http_status"
    MALFORMED_RESPONSE = "malformed_response"
    TRUNCATED = "truncated"


class ProviderText(DomainModel):
    text: NonEmptyText


class ProviderRefusal(DomainModel):
    """模型拒答。這不是錯誤,也不得被當成可重試的失敗。"""

    message: str = ""


class ProviderFailure(DomainModel):
    kind: ProviderFailureKind
    detail: NonEmptyText


ProviderOutcome = ProviderText | ProviderRefusal | ProviderFailure


class OpenRouterAdapter:
    def __init__(
        self, *, config: OpenRouterConfig, api_key: str, transport: ChatTransport
    ) -> None:
        self._config = config
        self._api_key = api_key
        self._transport = transport

    def build_body(
        self,
        *,
        instructions: str,
        packet_text: str,
        schema_name: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """送出去的 body。抽成公開方法,測試才驗得到 wire invariants。"""
        return {
            "model": self._config.model,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": packet_text},
            ],
            "max_tokens": self._config.max_output_tokens,
            "stream": False,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                },
            },
            "provider": {
                "order": list(self._config.provider_order),
                "only": list(self._config.provider_order),
                "allow_fallbacks": False,
                "require_parameters": True,
            },
        }

    async def complete(
        self,
        *,
        instructions: str,
        packet_text: str,
        schema_name: str,
        schema: dict[str, Any],
    ) -> ProviderOutcome:
        body = self.build_body(
            instructions=instructions,
            packet_text=packet_text,
            schema_name=schema_name,
            schema=schema,
        )
        try:
            response = await self._transport(
                url=CHAT_COMPLETIONS_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                body=body,
                timeout=self._config.timeout_seconds,
            )
        except httpx.TimeoutException as error:
            return ProviderFailure(
                kind=ProviderFailureKind.TIMEOUT, detail=str(error) or "timed out"
            )
        except httpx.TransportError as error:
            return ProviderFailure(
                kind=ProviderFailureKind.CONNECTION, detail=str(error) or "transport error"
            )
        return _interpret(response)


def _interpret(response: TransportResponse) -> ProviderOutcome:
    if response.status_code != 200:
        return ProviderFailure(
            kind=ProviderFailureKind.HTTP_STATUS,
            detail=f"openrouter returned HTTP {response.status_code}",
        )
    body = response.body
    if not isinstance(body, dict):
        return ProviderFailure(
            kind=ProviderFailureKind.MALFORMED_RESPONSE,
            detail="response body was not a JSON object",
        )
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        return ProviderFailure(
            kind=ProviderFailureKind.MALFORMED_RESPONSE,
            detail="response carried no choices",
        )
    choice = choices[0]
    message = choice.get("message") if isinstance(choice, dict) else None
    if not isinstance(message, dict):
        return ProviderFailure(
            kind=ProviderFailureKind.MALFORMED_RESPONSE,
            detail="first choice carried no message",
        )
    refusal = message.get("refusal")
    if refusal:
        return ProviderRefusal(message=str(refusal))
    if choice.get("finish_reason") == "length":
        # 截斷的 JSON 一定 parse 不起來;讓它變成明確的 truncated,而不是看不懂的
        # schema 失敗——兩者的處置完全不同(調 max_tokens vs 改 prompt)。
        return ProviderFailure(
            kind=ProviderFailureKind.TRUNCATED,
            detail="response hit the output token limit",
        )
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        return ProviderFailure(
            kind=ProviderFailureKind.MALFORMED_RESPONSE,
            detail="message carried no content",
        )
    return ProviderText(text=content)


def httpx_chat_transport(client: httpx.AsyncClient) -> ChatTransport:
    """真正的 transport。這裡不做任何 retry——httpx 預設也不重試。"""

    async def transport(
        *,
        url: str,
        headers: Mapping[str, str],
        body: Mapping[str, Any],
        timeout: float,
    ) -> TransportResponse:
        response = await client.post(
            url, headers=dict(headers), json=dict(body), timeout=timeout
        )
        try:
            parsed = response.json()
        except ValueError:
            parsed = None
        return TransportResponse(
            status_code=response.status_code,
            body=parsed if isinstance(parsed, dict) else None,
            text=response.text,
        )

    return transport
