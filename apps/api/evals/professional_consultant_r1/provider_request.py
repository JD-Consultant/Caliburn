"""R1 experiment-only OpenRouter 請求契約（設計 §8.3／§9.2 方案 B）。

**這是 R1 自己的契約，不是既有實作的移植。** 不 import `app.interview_vnext`，
也不把它的政策當規則 —— 舊實作可能有多餘或錯誤的決定。這裡只保留兩種東西：

1. 設計 §8.3 明文要求的條件；
2. OpenRouter 的 wire 形狀（欄位名與巢狀結構）——這是 provider 的事實，
   但**仍待 Segment 4 的 live preflight 實測確認**，標 `PROVISIONAL` 者尤然。

本模組只負責「要送出去的東西長什麼樣」，不碰網路。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from .contracts import Result, canonical_hash

# 設計 §8.3：禁止任何會讓路由浮動的 slug 形式。
FORBIDDEN_SLUG_TOKENS = ("auto", "latest", "free", "nitro", "floor")

# 設計 §8.3：會改寫內容或重放快取的 plugin 一律停用。
# **PROVISIONAL**：plugin id 字串必須在 Segment 4 的 live preflight 對 OpenRouter
# 實際 catalog 核對後才算確認。現在的清單是「已知會改寫內容」的候選，寧可多停用；
# 停用一個不存在的 id 是無害的，漏停一個會改寫內容的才致命。
DISABLED_PLUGINS = ("web", "file-parser", "cache")

# 請求體不得出現的 key（tools／provider 端會談狀態／preset／自動路由）。
FORBIDDEN_BODY_KEYS = frozenset(
    {"tools", "tool_choice", "functions", "preset", "route", "models", "transforms",
     "conversation", "conversation_id", "previous_response_id", "store"}
)

_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._-]*$")


@dataclass(frozen=True)
class ProviderConfig:
    """凍結的 provider 綁定。任何欄位改動都要重跑 preflight 並升 batch。"""

    requested_model: str
    provider_only: tuple[str, ...]
    provider_order: tuple[str, ...]
    base_url: str = "https://openrouter.ai/api/v1"
    data_collection: str = "deny"
    reasoning_effort: str | None = None
    disabled_plugins: tuple[str, ...] = DISABLED_PLUGINS
    timeout_seconds: float = 120.0

    @property
    def config_hash(self) -> str:
        return canonical_hash(
            {
                "requested_model": self.requested_model,
                "provider_only": list(self.provider_only),
                "provider_order": list(self.provider_order),
                "base_url": self.base_url,
                "data_collection": self.data_collection,
                "reasoning_effort": self.reasoning_effort,
                "disabled_plugins": list(self.disabled_plugins),
            }
        )


def validate_config(config: ProviderConfig) -> Result:
    """凍結前檢查：slug 精確、單一 upstream、無浮動路由。"""
    result = Result()
    slug = config.requested_model

    if not _SLUG_RE.match(slug):
        result.error("model_slug", f"model slug 形式不合法：{slug!r}", "requested_model")
    tail = slug.rsplit("/", 1)[-1] if "/" in slug else slug
    for token in FORBIDDEN_SLUG_TOKENS:
        # `:free`／`:nitro`／`:floor` 是 OpenRouter 的變體後綴；`auto`／`latest` 是浮動別名。
        if tail == token or tail.endswith(f":{token}") or tail.endswith(f"-{token}"):
            result.error(
                "model_slug",
                f"不得使用浮動或變體 slug（含 {token!r}）：{slug!r}",
                "requested_model",
            )

    if len(config.provider_only) != 1:
        result.error(
            "provider_pinning",
            f"provider.only 必須恰好固定一個 upstream，實得 {config.provider_only}",
            "provider_only",
        )
    if list(config.provider_order) != list(config.provider_only):
        result.error(
            "provider_pinning",
            "provider.order 必須與 provider.only 相同，避免第二順位被靜默採用",
            "provider_order",
        )
    # 註：`data_collection` 不是設計 §8.3 的要求，只是本實驗的預設值（構造語料，
    # 沒有真實員工資料，但沒理由讓 provider 拿去訓練）。這裡不當硬性條件擋。
    for plugin in DISABLED_PLUGINS:
        if plugin not in config.disabled_plugins:
            result.error("plugins", f"必須明確停用 plugin：{plugin}", "disabled_plugins")
    return result


@dataclass(frozen=True)
class ChatRequest:
    """一次 attempt 要送出的完整內容。`body` 已可直接 JSON 序列化。"""

    url: str
    body: dict[str, Any]
    config_hash: str
    schema_hash: str
    headers_without_secrets: dict[str, str] = field(default_factory=dict)

    @property
    def body_hash(self) -> str:
        return canonical_hash(self.body)


def build_chat_request(
    config: ProviderConfig,
    *,
    system_instruction: str,
    user_content: str,
    output_schema: dict[str, Any],
    schema_name: str,
    max_output_tokens: int,
) -> ChatRequest:
    """組出 §8.3 要求的精確請求體。

    固定：`allow_fallbacks: false`、`require_parameters: true`、單一 upstream、
    `stream: false`、`response_format.json_schema.strict: true`、plugins 全部停用、
    reasoning 不回傳（`exclude: true`）。**不放 tools／preset／conversation state。**
    """
    provider_block: dict[str, Any] = {
        "only": list(config.provider_only),
        "order": list(config.provider_order),
        "allow_fallbacks": False,
        "require_parameters": True,
        "data_collection": config.data_collection,
    }
    body: dict[str, Any] = {
        "model": config.requested_model,
        "messages": [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": user_content},
        ],
        "max_tokens": max_output_tokens,
        "stream": False,
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "strict": True, "schema": output_schema},
        },
        "provider": provider_block,
        "plugins": [{"id": pid, "enabled": False} for pid in config.disabled_plugins],
    }
    if config.reasoning_effort is not None:
        # exclude=True：我們不索取也不保存 reasoning（設計 §10 禁止保存項）。
        body["reasoning"] = {"effort": config.reasoning_effort, "exclude": True}

    return ChatRequest(
        url=f"{config.base_url.rstrip('/')}/chat/completions",
        body=body,
        config_hash=config.config_hash,
        schema_hash=canonical_hash(output_schema),
        headers_without_secrets={"Content-Type": "application/json"},
    )


def verify_request_is_exact(body: Any) -> Result:
    """對已組好的請求體重跑 §8.3 的硬性條件。

    transport 送出前會呼叫一次；測試也直接用它，確保條件不是只寫在文件裡。
    """
    result = Result()
    if not isinstance(body, dict):
        result.error("request_shape", "請求體必須是物件", "body")
        return result

    for key in sorted(set(body) & FORBIDDEN_BODY_KEYS):
        result.error("request_shape", f"請求體不得包含 {key}", "body")

    if body.get("stream") is not False:
        result.error("request_shape", "stream 必須明確為 false", "body.stream")

    provider = body.get("provider")
    if not isinstance(provider, dict):
        result.error("provider_pinning", "缺少 provider 區塊", "body.provider")
    else:
        if provider.get("allow_fallbacks") is not False:
            result.error("provider_pinning", "allow_fallbacks 必須為 false", "body.provider")
        if provider.get("require_parameters") is not True:
            result.error("provider_pinning", "require_parameters 必須為 true", "body.provider")
        only = provider.get("only")
        order = provider.get("order")
        if not isinstance(only, list) or len(only) != 1:
            result.error("provider_pinning", "provider.only 必須恰好一個 upstream", "body.provider")
        if only != order:
            result.error("provider_pinning", "provider.order 必須與 only 相同", "body.provider")

    fmt = body.get("response_format")
    if not isinstance(fmt, dict) or fmt.get("type") != "json_schema":
        result.error("structured_output", "response_format 必須是 json_schema", "body.response_format")
    else:
        js = fmt.get("json_schema")
        if not isinstance(js, dict) or js.get("strict") is not True:
            result.error(
                "structured_output", "json_schema.strict 必須為 true", "body.response_format"
            )

    plugins = body.get("plugins")
    if not isinstance(plugins, list):
        result.error("plugins", "plugins 必須是陣列（即使全部停用）", "body.plugins")
    else:
        enabled = [p for p in plugins if isinstance(p, dict) and p.get("enabled") is not False]
        if enabled:
            result.error("plugins", f"不得啟用任何 plugin：{enabled}", "body.plugins")
        declared = {p.get("id") for p in plugins if isinstance(p, dict)}
        for pid in DISABLED_PLUGINS:
            if pid not in declared:
                result.error("plugins", f"必須明確停用 plugin：{pid}", "body.plugins")

    reasoning = body.get("reasoning")
    if reasoning is not None:
        if not isinstance(reasoning, dict) or reasoning.get("exclude") is not True:
            result.error(
                "reasoning", "若設定 reasoning，必須帶 exclude=true（不索取推理內容）", "body.reasoning"
            )
    return result
