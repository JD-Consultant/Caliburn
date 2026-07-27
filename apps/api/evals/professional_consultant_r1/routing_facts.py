"""從 OpenRouter 回應正規化出 route facts（設計 §8.3、§10）。

**resolved model／provider 只能取自回應，不得由請求推斷**（ADR 0040 決定 22）。
拿不到就 fail closed 記 limitation，絕不回填請求裡的值。

**這是 R1 自己的正規化器，不是既有實作的移植**，不 import `app.interview_vnext`。
所依賴的只有 OpenRouter 的 wire 形狀：router metadata 可能是巢狀
`endpoints.{selected, available[]}` 或扁平 `endpoints[]`；cache 狀態只由官方 header 表示。

**PROVISIONAL**：上述形狀必須在 Segment 4 的 live preflight 用真實回應核對。
在那之前，任何讀不懂的形狀一律 fail closed（記 limitation、resolved 留 null），
寧可作廢一個 trial，也不要猜一個 resolved route 出來。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

CACHE_STATUS_HEADER = "x-openrouter-cache-status"

LIMITATION_METADATA_MISSING = "openrouter router metadata was missing"
LIMITATION_ENDPOINTS_MALFORMED = "openrouter endpoints metadata was not a recognized shape"
LIMITATION_SELECTED_NOT_UNIQUE = (
    "openrouter metadata did not identify exactly one selected endpoint"
)
LIMITATION_CACHE_HEADER_UNRECOGNIZED = "openrouter cache status header value was not recognized"
LIMITATION_CACHE_UNKNOWN = "openrouter cache status could not be determined"
LIMITATION_CACHE_REPLAY = "openrouter served a cached response; the trial is not a fresh sample"
LIMITATION_ROUTER_RETRIED = "openrouter router attempted more than one upstream"
LIMITATION_MODEL_MISMATCH = "resolved model does not match the requested model"

CACHE_HIT = "hit"
CACHE_MISS = "miss"
CACHE_ABSENT = "absent"
CACHE_UNKNOWN = "unknown"


@dataclass(frozen=True)
class RouteFacts:
    metadata_present: bool
    resolved_model: str | None
    resolved_provider: str | None
    selected_count: int | None
    router_attempt: int | None
    cache_status: str
    limitations: tuple[str, ...]

    @property
    def usable(self) -> bool:
        """能不能拿這次回應當一個有效的品質樣本。"""
        return not self.limitations and self.resolved_model is not None


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _selected_endpoint(metadata: dict[str, Any]) -> tuple[str | None, str | None, int | None, list[str]]:
    endpoints = metadata.get("endpoints")
    selected: list[dict[str, Any]] = []

    if isinstance(endpoints, dict):
        one = endpoints.get("selected")
        if isinstance(one, dict):
            selected.append(one)
        available = endpoints.get("available")
        if isinstance(available, list):
            selected.extend(
                item for item in available if isinstance(item, dict) and item.get("selected") is True
            )
    elif isinstance(endpoints, list):
        selected.extend(
            item for item in endpoints if isinstance(item, dict) and item.get("selected") is True
        )
    elif endpoints is not None:
        return None, None, None, [LIMITATION_ENDPOINTS_MALFORMED]

    unique: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any]] = set()
    for item in selected:
        key = (item.get("provider"), item.get("model"))
        if key not in seen:
            seen.add(key)
            unique.append(item)

    if len(unique) != 1:
        return None, None, len(unique), [LIMITATION_SELECTED_NOT_UNIQUE]
    entry = unique[0]
    return _text(entry.get("provider")), _text(entry.get("model")), 1, []


def _cache_status(header_value: str | None, *, metadata_present: bool) -> tuple[str, list[str]]:
    """只有官方 header（或完整 metadata 存在）算數。
    零 token、零成本、低 latency 都不是快取證據。"""
    header = header_value.strip() if isinstance(header_value, str) else ""
    if header:
        token = header.upper()
        if token == "HIT":
            return CACHE_HIT, []
        if token == "MISS":
            return CACHE_MISS, []
        return CACHE_UNKNOWN, [LIMITATION_CACHE_HEADER_UNRECOGNIZED]
    if metadata_present:
        return CACHE_ABSENT, []
    return CACHE_UNKNOWN, [LIMITATION_CACHE_UNKNOWN]


def normalize_route_facts(
    metadata: Any,
    *,
    headers: dict[str, str] | None = None,
    requested_model: str | None = None,
) -> RouteFacts:
    """把一次回應的 router metadata ＋ header 正規化成 route facts。

    `requested_model` 只用來**比對**，永遠不用來填 `resolved_model`。
    """
    header_map = {k.lower(): v for k, v in (headers or {}).items()}
    cache_header = header_map.get(CACHE_STATUS_HEADER)

    if not isinstance(metadata, dict):
        status, cache_limits = _cache_status(cache_header, metadata_present=False)
        limits = sorted({LIMITATION_METADATA_MISSING, *cache_limits})
        if status == CACHE_HIT:
            limits = sorted({*limits, LIMITATION_CACHE_REPLAY})
        return RouteFacts(
            metadata_present=False,
            resolved_model=None,
            resolved_provider=None,
            selected_count=None,
            router_attempt=None,
            cache_status=status,
            limitations=tuple(limits),
        )

    limitations: set[str] = set()
    provider, model, selected_count, endpoint_limits = _selected_endpoint(metadata)
    limitations.update(endpoint_limits)

    attempt = metadata.get("attempt")
    router_attempt = (
        attempt if isinstance(attempt, int) and not isinstance(attempt, bool) and attempt >= 0 else None
    )
    # 設計 §8.3：adapter 不 retry，router 也不該換 upstream。attempt>1 代表發生了 fallback。
    if router_attempt is not None and router_attempt > 1:
        limitations.add(LIMITATION_ROUTER_RETRIED)

    status, cache_limits = _cache_status(cache_header, metadata_present=True)
    limitations.update(cache_limits)
    if status == CACHE_HIT:
        limitations.add(LIMITATION_CACHE_REPLAY)

    if requested_model is not None and model is not None and model != requested_model:
        limitations.add(LIMITATION_MODEL_MISMATCH)

    return RouteFacts(
        metadata_present=True,
        resolved_model=model,
        resolved_provider=provider,
        selected_count=selected_count,
        router_attempt=router_attempt,
        cache_status=status,
        limitations=tuple(sorted(limitations)),
    )
