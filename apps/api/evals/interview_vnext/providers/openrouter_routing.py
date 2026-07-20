"""Pure OpenRouter router-metadata normalizer (V3-5A R4 §6).

Deterministically maps one raw ``openrouter_metadata`` value plus the response
cache header onto provider-neutral execution facts: selected route, pipeline
stages, cache status and stable limitations. This module never decides
eligibility — no ``eligible``/``clean``/failure verdicts, no
``evaluate_conformance()`` call — and it performs no I/O: no network, no env,
no executor/scheduler/DB imports.

Shape sources (checked 2026-07-19): OpenRouter Router Metadata (canonical
nested ``endpoints.available[]`` with a ``selected`` entry; additive schema
evolution; no-op pipeline stages omitted; cache hits drop the metadata) and
Response Caching (``X-OpenRouter-Cache-Status: HIT|MISS``). Legacy flat
``endpoints`` arrays already captured in fixtures stay readable.

規格:docs/plans/2026-07-19-interview-vnext-v3-5a-r4-provider-evidence-conformance-plan.md
"""

from __future__ import annotations

from collections.abc import Collection
from dataclasses import dataclass
from typing import Any

from app.interview_vnext.domain.hashing import canonical_hash, canonical_json
from app.interview_vnext.llm.execution import (
    CacheStatus,
    ProviderPipelineStage,
    TransformationStatus,
    derive_transformation_status,
)


CACHE_STATUS_HEADER = "x-openrouter-cache-status"
CACHE_AGE_HEADER = "x-openrouter-cache-age"
CACHE_TTL_HEADER = "x-openrouter-cache-ttl"

# Stable limitation strings; consumers persist them sorted + unique.
LIMITATION_METADATA_MISSING = "openrouter router metadata was missing"
LIMITATION_ENDPOINTS_MALFORMED = (
    "openrouter endpoints metadata was not a recognized shape"
)
LIMITATION_SELECTED_NOT_UNIQUE = (
    "openrouter metadata did not identify exactly one selected endpoint"
)
LIMITATION_PIPELINE_MALFORMED = "openrouter pipeline metadata was not an array"
LIMITATION_ATTEMPTS_CONTRADICTORY = (
    "openrouter attempt count contradicts the recorded attempts"
)
LIMITATION_CACHE_HEADER_UNRECOGNIZED = (
    "openrouter cache status header value was not recognized"
)
LIMITATION_CACHE_UNKNOWN = "openrouter cache status could not be determined"
LIMITATION_ENDPOINT_NOT_ATTESTED = (
    "openrouter route facts could not attest the configured endpoint slug"
)

# §6.5: pipeline classification. Tokens are canonicalized (lowercase, '-'→'_')
# so documented spellings like `message-transform` match. Anything else —
# including a `plugin` stage with an unknown name — stays `unknown` (fail
# closed downstream); never guess a new stage type clean or inspected.
_INSPECTED_STAGE_TYPES = frozenset({"guardrail", "moderation", "content_filter"})
_MUTATED_STAGE_TYPES = frozenset(
    {
        "context_compression",
        "response_healing",
        "server_tools",
        "rewrite",
        "redaction",
        "message_transform",
    }
)
_MUTATING_PLUGIN_NAMES = frozenset({"web", "web_search", "file_parser"})


@dataclass(frozen=True)
class OpenRouterRoutingFacts:
    """Normalized execution facts for exactly one OpenRouter response."""

    metadata_present: bool
    metadata_requested_model: str | None
    route_strategy: str | None
    router_attempt: int | None
    selected_provider: str | None
    selected_model: str | None
    selected_count: int | None
    attempts: tuple[object, ...]
    raw_pipeline: tuple[object, ...]
    pipeline_stages: tuple[ProviderPipelineStage, ...]
    transformation_status: TransformationStatus
    cache_status: CacheStatus
    region: object | None
    is_byok: bool | None
    limitations: tuple[str, ...]


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    try:
        canonical_json(value)
    except (TypeError, ValueError):
        return str(value)
    return value


def _fact_text(value: Any) -> str | None:
    """A usable text fact: a non-blank string, kept verbatim (never stripped).

    Blank-only strings are not facts — downstream typed evidence uses
    ``NonEmptyText`` and must receive null instead of a value that would raise
    inside the adapter (R4-C blocker 3).
    """

    if isinstance(value, str) and value.strip():
        return value
    return None


def _canonical_token(value: str) -> str:
    return value.strip().lower().replace("-", "_")


def _scalar_text(container: dict[str, Any], key: str) -> str | None:
    """§6.5: only read the same-name top-level scalar; never mine `data`."""

    value = container.get(key)
    if isinstance(value, str) and value.strip():
        return value
    return None


def _classify_stage(stage_type: str, name: str | None) -> TransformationStatus:
    token = _canonical_token(stage_type)
    if token in _INSPECTED_STAGE_TYPES:
        return TransformationStatus.INSPECTED
    if token in _MUTATED_STAGE_TYPES:
        return TransformationStatus.MUTATED
    if token == "plugin" and name is not None and (
        _canonical_token(name) in _MUTATING_PLUGIN_NAMES
    ):
        return TransformationStatus.MUTATED
    return TransformationStatus.UNKNOWN


def _normalize_stage(index: int, raw_stage: object) -> ProviderPipelineStage:
    if isinstance(raw_stage, dict):
        raw_type = raw_stage.get("type")
        stage_type = (
            raw_type if isinstance(raw_type, str) and raw_type.strip() else "unknown"
        )
        name = _scalar_text(raw_stage, "name")
        status = _scalar_text(raw_stage, "status")
    else:
        stage_type, name, status = "unknown", None, None
    return ProviderPipelineStage(
        index=index,
        stage_type=stage_type,
        name=name,
        status=status,
        transformation_status=_classify_stage(stage_type, name),
        details_hash=canonical_hash(_json_safe(raw_stage)),
    )


def _selected_endpoint(
    metadata: dict[str, Any],
) -> tuple[str | None, str | None, int | None, tuple[str, ...]]:
    """Extract the unique selected {provider, model} from `endpoints`.

    Prefers the official nested ``{available: [...], selected: {...}}`` object
    and keeps the legacy flat array readable (§6.3). A nested ``selected``
    entry repeated in ``available`` counts once. Returns
    ``(provider, model, selected_count, limitations)``; provider/model are
    null unless exactly one selection is present.
    """

    endpoints = metadata.get("endpoints")
    selected: list[dict[str, Any]] = []
    if isinstance(endpoints, dict):
        one = endpoints.get("selected")
        if isinstance(one, dict):
            selected.append(one)
        candidates = endpoints.get("available")
        if isinstance(candidates, list):
            selected.extend(
                item
                for item in candidates
                if isinstance(item, dict) and item.get("selected") is True
            )
    elif isinstance(endpoints, list):
        selected.extend(
            item
            for item in endpoints
            if isinstance(item, dict) and item.get("selected") is True
        )
    elif endpoints is not None:
        return None, None, None, (LIMITATION_ENDPOINTS_MALFORMED,)

    unique: list[dict[str, Any]] = []
    seen: set[tuple[Any, Any]] = set()
    for item in selected:
        key = (item.get("provider"), item.get("model"))
        if key not in seen:
            seen.add(key)
            unique.append(item)
    if len(unique) != 1:
        return None, None, len(unique), (LIMITATION_SELECTED_NOT_UNIQUE,)
    entry = unique[0]
    return _fact_text(entry.get("provider")), _fact_text(entry.get("model")), 1, ()


def _normalize_cache(
    cache_header_value: str | None, *, metadata_present: bool
) -> tuple[CacheStatus, tuple[str, ...]]:
    """§6.6: only the official header (or full metadata presence) is authority.

    Zero token counters, zero cost, low latency or a lone missing metadata
    object never count as cache evidence.
    """

    header = cache_header_value.strip() if cache_header_value is not None else ""
    if header:
        token = header.upper()
        if token == "HIT":
            return CacheStatus.HIT, ()
        if token == "MISS":
            return CacheStatus.MISS, ()
        return CacheStatus.UNKNOWN, (LIMITATION_CACHE_HEADER_UNRECOGNIZED,)
    if metadata_present:
        return CacheStatus.ABSENT, ()
    return CacheStatus.UNKNOWN, (LIMITATION_CACHE_UNKNOWN,)


def normalize_openrouter_routing(
    metadata: object, *, cache_header_value: str | None = None
) -> OpenRouterRoutingFacts:
    """Normalize one raw ``openrouter_metadata`` value into routing facts.

    Unknown additive keys are ignored here and preserved by the caller's raw
    routing artifact; malformed shapes fill null/unknown plus a stable
    limitation instead of raising (§6.3).
    """

    if not isinstance(metadata, dict):
        cache_status, cache_limitations = _normalize_cache(
            cache_header_value, metadata_present=False
        )
        return OpenRouterRoutingFacts(
            metadata_present=False,
            metadata_requested_model=None,
            route_strategy=None,
            router_attempt=None,
            selected_provider=None,
            selected_model=None,
            selected_count=None,
            attempts=(),
            raw_pipeline=(),
            pipeline_stages=(),
            transformation_status=TransformationStatus.UNKNOWN,
            cache_status=cache_status,
            region=None,
            is_byok=None,
            limitations=tuple(
                sorted({LIMITATION_METADATA_MISSING, *cache_limitations})
            ),
        )

    limitations: set[str] = set()

    metadata_requested_model = _fact_text(metadata.get("requested"))
    route_strategy = _fact_text(metadata.get("strategy"))
    attempt = metadata.get("attempt")
    router_attempt = (
        attempt
        if isinstance(attempt, int) and not isinstance(attempt, bool) and attempt >= 0
        else None
    )

    provider, model, selected_count, endpoint_limitations = _selected_endpoint(metadata)
    limitations.update(endpoint_limitations)

    raw_attempts = metadata.get("attempts")
    attempts = (
        tuple(_json_safe(item) for item in raw_attempts)
        if isinstance(raw_attempts, list)
        else ()
    )
    # R4-C blocker 2 (§6.4 condition 8): the attempt counter and the recorded
    # attempts must not contradict each other. When they do, a single direct
    # execution cannot be attested — the attempt fact becomes unknown and the
    # strict policy fails closed on the missing route metadata.
    if router_attempt is not None and attempts and len(attempts) != router_attempt:
        router_attempt = None
        limitations.add(LIMITATION_ATTEMPTS_CONTRADICTORY)

    # R4-C blocker 1: only an *absent* key (official "no-op stages are
    # omitted" semantics) or an explicit empty array attests a clean
    # pass-through. An explicit ``"pipeline": null`` is an unrecognized shape
    # and fails closed to unknown.
    raw_pipeline_value = metadata.get("pipeline")
    if "pipeline" not in metadata or (
        isinstance(raw_pipeline_value, list) and not raw_pipeline_value
    ):
        raw_pipeline: tuple[object, ...] = ()
        pipeline_stages: tuple[ProviderPipelineStage, ...] = ()
        transformation_status = TransformationStatus.CLEAN
    elif isinstance(raw_pipeline_value, list):
        raw_pipeline = tuple(_json_safe(item) for item in raw_pipeline_value)
        pipeline_stages = tuple(
            _normalize_stage(index, raw_stage)
            for index, raw_stage in enumerate(raw_pipeline_value, start=1)
        )
        transformation_status = derive_transformation_status(pipeline_stages)
    else:
        raw_pipeline = ()
        pipeline_stages = ()
        transformation_status = TransformationStatus.UNKNOWN
        limitations.add(LIMITATION_PIPELINE_MALFORMED)

    cache_status, cache_limitations = _normalize_cache(
        cache_header_value, metadata_present=True
    )
    limitations.update(cache_limitations)

    is_byok_value = metadata.get("is_byok")
    return OpenRouterRoutingFacts(
        metadata_present=True,
        metadata_requested_model=metadata_requested_model,
        route_strategy=route_strategy,
        router_attempt=router_attempt,
        selected_provider=provider,
        selected_model=model,
        selected_count=selected_count,
        attempts=attempts,
        raw_pipeline=raw_pipeline,
        pipeline_stages=pipeline_stages,
        transformation_status=transformation_status,
        cache_status=cache_status,
        region=_json_safe(metadata.get("region")),
        is_byok=is_byok_value if isinstance(is_byok_value, bool) else None,
        limitations=tuple(sorted(limitations)),
    )


def attest_upstream_endpoint(
    facts: OpenRouterRoutingFacts,
    *,
    outbound_requested_model: str,
    configured_endpoint_slug: str,
    expected_upstream_provider: str,
    accepted_upstream_models: Collection[str],
) -> str | None:
    """§6.4: return the exact endpoint slug only when outbound constraints and
    response facts jointly attest it; otherwise ``None``.

    Router metadata reports the selected provider/model, not the request-time
    endpoint slug, so the slug is only an execution fact when the caller's
    outbound request pinned exactly this slug (`order == only == one endpoint`,
    fallbacks off — the caller's preflight, §6.4 conditions 1–3) AND the
    response metadata is uniquely consistent with it (conditions 4–8). This is
    fact attestation, not an eligibility verdict: on failure the actual
    selected provider/model stay recorded and conformance fails closed on the
    missing endpoint.
    """

    if not facts.metadata_present:
        return None
    if facts.metadata_requested_model != outbound_requested_model:
        return None
    if facts.selected_count != 1:
        return None
    if facts.selected_provider != expected_upstream_provider:
        return None
    if facts.selected_model is None or (
        facts.selected_model not in accepted_upstream_models
    ):
        return None
    for entry in facts.attempts:
        if not isinstance(entry, dict):
            return None
        entry_provider = entry.get("provider")
        if entry_provider is not None and entry_provider != expected_upstream_provider:
            return None
        entry_model = entry.get("model")
        if entry_model is not None and entry_model not in accepted_upstream_models:
            return None
    return configured_endpoint_slug
