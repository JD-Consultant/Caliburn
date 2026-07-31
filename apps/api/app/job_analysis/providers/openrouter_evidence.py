"""OpenRouter catalog 與 route evidence 的純解析(attributed live smoke)。

**這兩個函式不是 runtime 路徑。** 產品回合仍只靠回應的 `model`、parse 與 verifier
判斷可否提交(ADR 0040);這裡的輸出只給一次性 live smoke 用來回答「這次結果能不能
拿來評 prompt 品質」。任何內容都不得寫進 PostgreSQL、Work Model、JD 或 Journal。

兩個方向刻意相反:

- `select_catalog_endpoint()` 是**付費前的門**,看不懂就 raise
  `OpenRouterCatalogError`。價格與能力是會變的外部狀態,拿舊值估預算等於在盲花錢。
- `inspect_openrouter_execution()` 是**付費後的歸因**,永遠不 raise。缺 metadata
  只讓該次 trial 失去品質歸因資格,不能倒過來讓員工的回合失敗(研究紀錄 §4.1)。

fail-closed 的界線只有一條:**不確定就是沒資格**。未知的 pipeline stage 不猜成無害,
但未知的 additive 欄位一律忽略——後者是 provider 正常演進,前者是它動過這次請求。
"""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal, InvalidOperation
from typing import Any

from app.job_analysis.domain import DomainModel, NonEmptyText


MODEL_DETAIL_URL_TEMPLATE = "https://openrouter.ai/api/v1/models/{author}/{slug}"

# 本產品這一版 request 實際用到的能力。`require_parameters: true` 只保證路由到宣稱
# 支援的 endpoint,不保證這份清單永遠存在——所以每次付費前都要重查。
REQUIRED_ENDPOINT_PARAMETERS = frozenset(
    {
        "max_tokens",
        "reasoning",
        "reasoning_effort",
        "response_format",
        "structured_outputs",
    }
)

# 只有這種 stage 有機會保住資格:它宣稱只做檢查,而且資料自證沒有作用。
_INSPECTION_STAGE_TYPE = "guardrail"
# 任一為 true 就代表 guardrail 動作了;全部缺席則代表無從證明,同樣沒資格。
_INSPECTION_PROOF_KEYS = ("flagged", "blocked", "detected")

LIMITATION_METADATA_MISSING = "openrouter router metadata was missing"
LIMITATION_REQUESTED_MISMATCH = "router metadata requested a different model"
LIMITATION_RESPONSE_MODEL_MISMATCH = "response model did not match the configured model"
LIMITATION_STRATEGY_NOT_DIRECT = "router strategy was not a direct route"
LIMITATION_ROUTER_RETRIED = "router did not succeed on the first attempt"
LIMITATION_SELECTED_NOT_UNIQUE = (
    "router metadata did not identify exactly one selected endpoint"
)
LIMITATION_SELECTED_PROVIDER_MISMATCH = (
    "selected provider did not match the preflight catalog endpoint"
)
LIMITATION_SELECTED_MODEL_MISMATCH = (
    "selected model did not match the preflight catalog endpoint"
)
LIMITATION_COST_UNUSABLE = "response usage did not carry a usable cost"


class OpenRouterCatalogError(ValueError):
    """catalog 無法唯一、明確地選中設定的 endpoint。付費前一律停線。"""


class OpenRouterEndpointSnapshot(DomainModel):
    """一次 preflight 當下的單一 endpoint 事實。價格是**每 token** 美元。"""

    model_id: NonEmptyText
    provider_name: NonEmptyText
    tag: NonEmptyText
    prompt_price_per_token: Decimal
    completion_price_per_token: Decimal
    supported_parameters: frozenset[NonEmptyText]


class OpenRouterExecutionEvidence(DomainModel):
    """一次呼叫的路由事實。欄位全可空——這是證據,不是產品真相。"""

    response_id: str | None = None
    requested_model: str | None = None
    response_model: str | None = None
    strategy: str | None = None
    attempt: int | None = None
    selected_provider: str | None = None
    selected_model: str | None = None
    pipeline_stage_names: tuple[str, ...] = ()
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    reasoning_tokens: int | None = None
    cost_usd: Decimal | None = None
    attribution_limitations: tuple[NonEmptyText, ...] = ()

    @property
    def quality_eligible(self) -> bool:
        """這次輸出可不可以用來判 prompt／rubric 品質。"""
        return not self.attribution_limitations


def _mapping(value: Any) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, Mapping) else None


def _text(value: Any) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _int(value: Any) -> int | None:
    """bool 是 int 的子類;放它過去會讓 `True` 變成 1 個 token。"""
    return None if isinstance(value, bool) or not isinstance(value, int) else value


def _finite_decimal(value: Any) -> Decimal | None:
    """`Decimal(str(...))` 保留 provider 寫的十進位字面值,不經過二進位浮點。"""
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _price(pricing: Mapping[str, Any], key: str) -> Decimal:
    parsed = _finite_decimal(pricing.get(key))
    if parsed is None or parsed < 0:
        raise OpenRouterCatalogError(
            f"endpoint {key} price was not a usable non-negative decimal: "
            f"{pricing.get(key)!r}"
        )
    return parsed


def select_catalog_endpoint(
    payload: Mapping[str, Any], *, expected_model: str, expected_tag: str
) -> OpenRouterEndpointSnapshot:
    """從 model detail 選出設定的那一個 active endpoint。

    只認 `status == 0`。缺欄位或其他值都當不可用——付費前多停一次的代價,遠低於
    在不知道落到哪個 endpoint 的情況下送出請求。
    """
    data = _mapping(payload.get("data"))
    if data is None:
        raise OpenRouterCatalogError("catalog payload carried no data object")
    if data.get("id") != expected_model:
        raise OpenRouterCatalogError(
            f"catalog model id {data.get('id')!r} did not match the configured "
            f"model {expected_model!r}"
        )

    endpoints = data.get("endpoints")
    if not isinstance(endpoints, list):
        raise OpenRouterCatalogError("catalog data carried no endpoints array")
    matches = [
        item
        for item in endpoints
        if isinstance(item, Mapping) and item.get("tag") == expected_tag
    ]
    if len(matches) != 1:
        raise OpenRouterCatalogError(
            f"endpoint tag {expected_tag!r} matched {len(matches)} catalog entries"
        )
    endpoint = matches[0]

    if endpoint.get("status") != 0 or isinstance(endpoint.get("status"), bool):
        raise OpenRouterCatalogError(
            f"endpoint status {endpoint.get('status')!r} is not the active value 0"
        )

    provider_name = _text(endpoint.get("provider_name"))
    if provider_name is None:
        raise OpenRouterCatalogError("endpoint carried no provider_name")

    supported = {
        parameter
        for parameter in (endpoint.get("supported_parameters") or [])
        if isinstance(parameter, str)
    }
    missing = REQUIRED_ENDPOINT_PARAMETERS - supported
    if missing:
        raise OpenRouterCatalogError(
            f"endpoint no longer supports required parameters: {sorted(missing)}"
        )

    pricing = _mapping(endpoint.get("pricing"))
    if pricing is None:
        raise OpenRouterCatalogError("endpoint carried no pricing object")

    return OpenRouterEndpointSnapshot(
        model_id=expected_model,
        provider_name=provider_name,
        tag=expected_tag,
        prompt_price_per_token=_price(pricing, "prompt"),
        completion_price_per_token=_price(pricing, "completion"),
        supported_parameters=frozenset(supported),
    )


def _selected_entries(metadata: Mapping[str, Any]) -> list[dict[str, Any]]:
    """metadata 的 endpoints 有巢狀 `{total, available[]}` 與扁平 `[]` 兩種形狀。"""
    endpoints = metadata.get("endpoints")
    candidates: list[Any] = []
    if isinstance(endpoints, Mapping):
        selected = endpoints.get("selected")
        if isinstance(selected, Mapping):
            candidates.append(selected)
        available = endpoints.get("available")
        if isinstance(available, list):
            candidates.extend(available)
    elif isinstance(endpoints, list):
        candidates.extend(endpoints)

    chosen: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any]] = set()
    for item in candidates:
        if not isinstance(item, Mapping) or item.get("selected") is not True:
            continue
        key = (item.get("provider"), item.get("model"))
        if key not in seen:
            seen.add(key)
            chosen.append(dict(item))
    return chosen


def _stage_label(stage: Any) -> str:
    if not isinstance(stage, Mapping):
        return f"unreadable:{type(stage).__name__}"
    return f"{_text(stage.get('type')) or 'unknown'}:{_text(stage.get('name')) or 'unnamed'}"


def _stage_is_proven_non_mutating(stage: Mapping[str, Any]) -> bool:
    if _text(stage.get("type")) != _INSPECTION_STAGE_TYPE:
        return False
    data = _mapping(stage.get("data"))
    if data is None:
        return False
    proofs = [data[key] for key in _INSPECTION_PROOF_KEYS if key in data]
    # 全部缺席 → 無從證明;非布林 → 讀不懂。兩者都不猜。
    return bool(proofs) and all(proof is False for proof in proofs)


def _pipeline_limitations(
    metadata: Mapping[str, Any],
) -> tuple[tuple[str, ...], list[str]]:
    pipeline = metadata.get("pipeline")
    if pipeline in (None, []):
        return (), []
    if not isinstance(pipeline, list):
        return ("unreadable-pipeline",), [
            f"router pipeline metadata was not a list: {type(pipeline).__name__}"
        ]

    names: list[str] = []
    limitations: list[str] = []
    for stage in pipeline:
        label = _stage_label(stage)
        names.append(label)
        if isinstance(stage, Mapping) and _stage_is_proven_non_mutating(stage):
            continue
        limitations.append(
            f"router pipeline stage {label!r} may have altered this request"
        )
    return tuple(names), limitations


def _usage_facts(payload: Mapping[str, Any]) -> tuple[dict[str, Any], list[str]]:
    usage = _mapping(payload.get("usage")) or {}
    details = _mapping(usage.get("completion_tokens_details")) or {}
    cost = _finite_decimal(usage.get("cost")) if "cost" in usage else None
    limitations: list[str] = []
    if cost is None or cost < 0:
        cost = None
        limitations.append(LIMITATION_COST_UNUSABLE)
    return (
        {
            "prompt_tokens": _int(usage.get("prompt_tokens")),
            "completion_tokens": _int(usage.get("completion_tokens")),
            "reasoning_tokens": _int(details.get("reasoning_tokens")),
            "cost_usd": cost,
        },
        limitations,
    )


def inspect_openrouter_execution(
    payload: Mapping[str, Any],
    *,
    expected_model: str,
    expected_endpoint: OpenRouterEndpointSnapshot,
) -> OpenRouterExecutionEvidence:
    """把一次回應正規化成路由證據。**不 raise**;讀不懂就記 limitation。"""
    facts, limitations = _usage_facts(payload)
    response_model = _text(payload.get("model"))
    if response_model != expected_model:
        limitations.append(LIMITATION_RESPONSE_MODEL_MISMATCH)

    metadata = _mapping(payload.get("openrouter_metadata"))
    if metadata is None:
        return OpenRouterExecutionEvidence(
            response_id=_text(payload.get("id")),
            response_model=response_model,
            attribution_limitations=tuple(
                dict.fromkeys([*limitations, LIMITATION_METADATA_MISSING])
            ),
            **facts,
        )

    requested = _text(metadata.get("requested"))
    if requested != expected_model:
        limitations.append(LIMITATION_REQUESTED_MISMATCH)
    strategy = _text(metadata.get("strategy"))
    if strategy != "direct":
        limitations.append(LIMITATION_STRATEGY_NOT_DIRECT)
    attempt = _int(metadata.get("attempt"))
    if attempt != 1:
        limitations.append(LIMITATION_ROUTER_RETRIED)

    selected_provider: str | None = None
    selected_model: str | None = None
    selected = _selected_entries(metadata)
    if len(selected) != 1:
        limitations.append(LIMITATION_SELECTED_NOT_UNIQUE)
    else:
        selected_provider = _text(selected[0].get("provider"))
        selected_model = _text(selected[0].get("model"))
        if (selected_provider or "").casefold() != (
            expected_endpoint.provider_name.casefold()
        ):
            limitations.append(LIMITATION_SELECTED_PROVIDER_MISMATCH)
        if selected_model != expected_endpoint.model_id:
            limitations.append(LIMITATION_SELECTED_MODEL_MISMATCH)

    stage_names, pipeline_limitations = _pipeline_limitations(metadata)
    limitations.extend(pipeline_limitations)

    return OpenRouterExecutionEvidence(
        response_id=_text(payload.get("id")),
        requested_model=requested,
        response_model=response_model,
        strategy=strategy,
        attempt=attempt,
        selected_provider=selected_provider,
        selected_model=selected_model,
        pipeline_stage_names=stage_names,
        attribution_limitations=tuple(dict.fromkeys(limitations)),
        **facts,
    )
