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
    """單一固定路由。model slug 必須是 Models API 的精確 ID。

    `provider_order` 恰好一個:OpenRouter 的 `order` 會**依序嘗試清單內**的 providers,
    `allow_fallbacks: false` 只擋清單外的 provider。清單放兩個就等於還有 fallback,
    只是換了個位置——那輪實際跑在誰身上會不可知。

    **已知限制**:同一個 provider base slug 仍可能對應該 provider 的多個 endpoint
    variant。真正付費呼叫前需要 catalog／live preflight 確認落點,那不在本 task。
    """

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
        if len(self.provider_order) != 1:
            raise ValueError("provider_order must pin exactly one provider endpoint")
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
    PROVIDER_ERROR = "provider_error"
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


def _error_envelope(payload: Any) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    error = payload.get("error")
    return error if isinstance(error, dict) else None


def _from_error_envelope(error: dict[str, Any]) -> ProviderOutcome:
    """OpenRouter 的 error envelope。

    refusal 在官方文件裡是一種 **typed error**,不是只出現在 `message.refusal`;
    讀漏就會把「模型拒答」錯報成 provider 故障,呼叫端因此以為重試有用。
    """
    metadata = error.get("metadata")
    error_type = metadata.get("error_type") if isinstance(metadata, dict) else None
    message = str(error.get("message") or "").strip()
    if error_type == "refusal":
        return ProviderRefusal(message=message)
    return ProviderFailure(
        kind=ProviderFailureKind.PROVIDER_ERROR,
        detail=f"{error_type or 'provider error'}: {message or '(no message)'}",
    )


def _interpret(response: TransportResponse) -> ProviderOutcome:
    body = response.body
    if response.status_code != 200:
        error = _error_envelope(body)
        if error is not None:
            return _from_error_envelope(error)
        return ProviderFailure(
            kind=ProviderFailureKind.HTTP_STATUS,
            detail=f"openrouter returned HTTP {response.status_code}",
        )
    if not isinstance(body, dict):
        return ProviderFailure(
            kind=ProviderFailureKind.MALFORMED_RESPONSE,
            detail="response body was not a JSON object",
        )
    # 非串流的 provider 錯誤可能維持 HTTP 200,錯誤只出現在 envelope 或 choice 上,
    # 而且**同時帶著 partial content**。所以錯誤一律先看,晚一步就會把半截輸出
    # 當成成功——只要那半截恰好是合法 JSON,它就會一路走到 verifier。
    top_level_error = _error_envelope(body)
    if top_level_error is not None:
        return _from_error_envelope(top_level_error)
    choices = body.get("choices")
    if not isinstance(choices, list) or not choices:
        return ProviderFailure(
            kind=ProviderFailureKind.MALFORMED_RESPONSE,
            detail="response carried no choices",
        )
    choice = choices[0]
    if not isinstance(choice, dict):
        return ProviderFailure(
            kind=ProviderFailureKind.MALFORMED_RESPONSE,
            detail="first choice was not an object",
        )
    choice_error = _error_envelope(choice)
    if choice_error is not None:
        return _from_error_envelope(choice_error)
    if choice.get("finish_reason") == "error":
        return ProviderFailure(
            kind=ProviderFailureKind.PROVIDER_ERROR,
            detail="choice finished with finish_reason=error",
        )
    message = choice.get("message")
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
