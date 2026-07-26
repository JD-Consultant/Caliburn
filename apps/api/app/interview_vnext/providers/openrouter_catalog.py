"""OpenRouter model/endpoints snapshot acquisition and production preflight.

One batch/run fetches the model and endpoints documents once, stores them as
immutable raw snapshots, and every hard capability/routing decision is made
locally against those snapshots — never per `generate_structured()` call and
never against live network state. Catalog HTTP calls are not durable model
attempts: a catalog failure must prevent inference entirely.

規格:docs/plans/2026-07-17-interview-vnext-v3-4r-openrouter-first-adapter-plan.md
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Callable
from uuid import UUID, uuid5

import httpx

from app.interview_vnext.domain.base import DomainModel
from app.interview_vnext.domain.hashing import canonical_hash
from app.interview_vnext.domain.identifiers import NonEmptyText, UtcDatetime
from app.interview_vnext.observability.artifacts import (
    ArtifactRecord,
    RedactionStatus,
    build_inline_artifact,
)


OPENROUTER_API_ROOT = "https://openrouter.ai/api/v1"

CATALOG_ARTIFACT_KIND = "provider.openrouter.model_catalog_snapshot"
MODEL_SNAPSHOT_LABEL = "artifact/openrouter-chat/model-catalog/v1"
ENDPOINT_SNAPSHOT_LABEL = "artifact/openrouter-chat/endpoint-catalog/v1"

# §6.2 gate 5: the model must explicitly list every parameter this request uses.
REQUIRED_MODEL_PARAMETERS = ("max_tokens", "response_format", "structured_outputs")


class CatalogProbeError(Exception):
    """Catalog GET failed (HTTP/transport/decode); inference must not run."""

    def __init__(
        self,
        detail: str,
        *,
        url_path: str,
        http_status: int | None = None,
        request_id: str | None = None,
        body: Any = None,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.reason_code = "openrouter.catalog_probe_failed"
        self.url_path = url_path
        self.http_status = http_status
        self.request_id = request_id
        self.body = body


class PreflightError(Exception):
    """A §6.2 hard gate failed locally; inference must not run."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


class OpenRouterModelSnapshot(DomainModel):
    schema_version: str = "openrouter_model_snapshot.v1"
    requested_model: NonEmptyText
    fetched_at: UtcDatetime
    url_path: NonEmptyText
    http_request_id: str | None = None
    raw: dict[str, Any]

    @property
    def snapshot_hash(self) -> str:
        return canonical_hash(self)

    @property
    def data(self) -> dict[str, Any]:
        data = self.raw.get("data")
        return data if isinstance(data, dict) else {}


class OpenRouterEndpointSnapshot(DomainModel):
    schema_version: str = "openrouter_endpoint_snapshot.v1"
    requested_model: NonEmptyText
    fetched_at: UtcDatetime
    url_path: NonEmptyText
    http_request_id: str | None = None
    raw: dict[str, Any]

    @property
    def snapshot_hash(self) -> str:
        return canonical_hash(self)

    @property
    def data(self) -> dict[str, Any]:
        data = self.raw.get("data")
        return data if isinstance(data, dict) else {}

    @property
    def endpoints(self) -> tuple[dict[str, Any], ...]:
        endpoints = self.data.get("endpoints")
        if not isinstance(endpoints, list):
            return ()
        return tuple(item for item in endpoints if isinstance(item, dict))


class EndpointFacts(DomainModel):
    """Documented endpoint fields promoted from the raw snapshot entry."""

    tag: NonEmptyText
    provider_name: str | None = None
    supported_parameters: tuple[str, ...] = ()
    context_length: int | None = None
    max_completion_tokens: int | None = None
    status: int | str | None = None


def _endpoint_facts(entry: dict[str, Any]) -> EndpointFacts | None:
    tag = entry.get("tag")
    if not isinstance(tag, str) or not tag.strip():
        return None
    provider_name = entry.get("provider_name")
    supported = entry.get("supported_parameters")
    context_length = entry.get("context_length")
    max_completion = entry.get("max_completion_tokens")
    return EndpointFacts(
        tag=tag,
        provider_name=provider_name if isinstance(provider_name, str) else None,
        supported_parameters=tuple(
            item for item in supported if isinstance(item, str)
        )
        if isinstance(supported, list)
        else (),
        context_length=context_length if isinstance(context_length, int) else None,
        max_completion_tokens=(
            max_completion if isinstance(max_completion, int) else None
        ),
        status=entry.get("status")
        if isinstance(entry.get("status"), (int, str))
        else None,
    )


def matched_endpoints(
    configured_slug: str, snapshot: OpenRouterEndpointSnapshot
) -> tuple[EndpointFacts, ...]:
    """Official base-slug matching semantics (§6.2 gate 10).

    A configured slug matches an endpoint whose routing tag is either exactly
    the slug or a variant under it (`slug/...`); the benchmark requires the
    match set to contain exactly one endpoint.
    """

    matches: list[EndpointFacts] = []
    for entry in snapshot.endpoints:
        facts = _endpoint_facts(entry)
        if facts is None:
            continue
        if facts.tag == configured_slug or facts.tag.startswith(
            configured_slug + "/"
        ):
            matches.append(facts)
    return tuple(matches)


class PreflightFacts(DomainModel):
    """Deterministic local decisions derived from the two snapshots."""

    requested_model: NonEmptyText
    canonical_slug: NonEmptyText
    endpoint: EndpointFacts
    model_context_length: int | None = None
    top_provider_max_completion_tokens: int | None = None
    limitations: tuple[str, ...] = ()


def _expiration(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def preflight(
    *,
    model_snapshot: OpenRouterModelSnapshot,
    endpoint_snapshot: OpenRouterEndpointSnapshot,
    requested_model: str,
    upstream_endpoint_slug: str,
    reasoning_effort: str | None,
    reasoning_max_tokens: int | None,
    required_output_tokens: int,
    now: datetime,
) -> PreflightFacts:
    """§6.2 hard gates; raises `PreflightError` before any inference HTTP."""

    limitations: list[str] = []
    data = model_snapshot.data
    model_id = data.get("id")
    if model_id != requested_model:
        raise PreflightError(
            "openrouter.preflight.model_id_mismatch",
            f"model lookup returned id {model_id!r} for {requested_model!r}",
        )
    canonical_slug = data.get("canonical_slug")
    if not isinstance(canonical_slug, str) or not canonical_slug.strip():
        raise PreflightError(
            "openrouter.preflight.canonical_slug_missing",
            "model lookup did not expose a non-empty permanent canonical_slug",
        )
    expiration = _expiration(data.get("expiration_date"))
    if data.get("expiration_date") is not None and expiration is None:
        raise PreflightError(
            "openrouter.preflight.model_expired",
            f"model expiration_date {data.get('expiration_date')!r} is unparseable",
        )
    if expiration is not None and expiration <= now:
        raise PreflightError(
            "openrouter.preflight.model_expired",
            f"model expired at {expiration.isoformat()}",
        )
    architecture = data.get("architecture")
    architecture = architecture if isinstance(architecture, dict) else {}
    input_modalities = architecture.get("input_modalities")
    output_modalities = architecture.get("output_modalities")
    if (
        not isinstance(input_modalities, list)
        or not isinstance(output_modalities, list)
        or "text" not in input_modalities
        or "text" not in output_modalities
    ):
        raise PreflightError(
            "openrouter.preflight.modalities_missing_text",
            "model input/output modalities do not both include text",
        )
    supported_parameters = data.get("supported_parameters")
    supported_parameters = (
        tuple(item for item in supported_parameters if isinstance(item, str))
        if isinstance(supported_parameters, list)
        else ()
    )
    missing = [
        name for name in REQUIRED_MODEL_PARAMETERS if name not in supported_parameters
    ]
    if missing:
        raise PreflightError(
            "openrouter.preflight.model_parameters_missing",
            f"model does not list required parameters: {', '.join(missing)}",
        )

    reasoning_requested = reasoning_effort is not None or reasoning_max_tokens is not None
    if reasoning_requested:
        reasoning = data.get("reasoning")
        if not isinstance(reasoning, dict):
            raise PreflightError(
                "openrouter.preflight.reasoning_unsupported",
                "config requests reasoning but the model snapshot does not "
                "explicitly list reasoning capability",
            )
        if reasoning_effort is not None:
            if "supported_efforts" not in reasoning:
                raise PreflightError(
                    "openrouter.preflight.reasoning_effort_unsupported",
                    "model snapshot does not support effort selection "
                    "(supported_efforts field is absent)",
                )
            supported_efforts = reasoning.get("supported_efforts")
            if supported_efforts is not None and (
                not isinstance(supported_efforts, list)
                or reasoning_effort not in supported_efforts
            ):
                raise PreflightError(
                    "openrouter.preflight.reasoning_effort_unsupported",
                    f"requested effort {reasoning_effort!r} is not in the model "
                    "snapshot supported_efforts; nearest-value mapping is not "
                    "acceptable for the benchmark",
                )
        if reasoning_max_tokens is not None and reasoning.get(
            "supports_max_tokens"
        ) is not True:
            raise PreflightError(
                "openrouter.preflight.reasoning_max_tokens_unsupported",
                "model snapshot does not explicitly support a reasoning max_tokens budget",
            )
        if reasoning_max_tokens is not None and required_output_tokens <= reasoning_max_tokens:
            raise PreflightError(
                "openrouter.preflight.reasoning_budget_exceeds_output",
                "request max_output_tokens must exceed the reasoning token budget",
            )

    context_length = data.get("context_length")
    context_length = context_length if isinstance(context_length, int) else None
    top_provider = data.get("top_provider")
    top_provider = top_provider if isinstance(top_provider, dict) else {}
    max_completion = top_provider.get("max_completion_tokens")
    max_completion = max_completion if isinstance(max_completion, int) else None
    if context_length is not None and context_length < required_output_tokens:
        raise PreflightError(
            "openrouter.preflight.context_budget_exceeded",
            f"model context_length {context_length} cannot hold the "
            f"required output budget {required_output_tokens}",
        )
    if max_completion is not None and max_completion < required_output_tokens:
        raise PreflightError(
            "openrouter.preflight.context_budget_exceeded",
            f"top provider max_completion_tokens {max_completion} cannot hold "
            f"the required output budget {required_output_tokens}",
        )
    if context_length is None:
        limitations.append("model snapshot did not include context_length")
    if max_completion is None:
        limitations.append(
            "model snapshot did not include top_provider.max_completion_tokens"
        )
    limitations.append(
        "input-token context preflight uses declared budgets only; no local tokenizer"
    )

    endpoints_model = endpoint_snapshot.data.get("id")
    if not endpoint_snapshot.endpoints:
        raise PreflightError(
            "openrouter.preflight.endpoints_empty",
            "endpoint snapshot contains no endpoints for the model",
        )
    if endpoints_model is not None and endpoints_model != requested_model:
        raise PreflightError(
            "openrouter.preflight.endpoints_model_mismatch",
            f"endpoint snapshot belongs to {endpoints_model!r}",
        )

    matches = matched_endpoints(upstream_endpoint_slug, endpoint_snapshot)
    if len(matches) == 0:
        raise PreflightError(
            "openrouter.preflight.endpoint_match_none",
            f"configured slug {upstream_endpoint_slug!r} matches no endpoint "
            "in the snapshot",
        )
    if len(matches) > 1:
        raise PreflightError(
            "openrouter.preflight.endpoint_match_ambiguous",
            f"configured slug {upstream_endpoint_slug!r} matches "
            f"{len(matches)} endpoints "
            f"({', '.join(item.tag for item in matches)}); pick the unique "
            "full variant slug",
        )
    endpoint = matches[0]
    if endpoint.provider_name is None:
        raise PreflightError(
            "openrouter.preflight.endpoint_missing_identity",
            f"endpoint {endpoint.tag!r} does not expose provider_name",
        )
    required_endpoint_parameters = list(REQUIRED_MODEL_PARAMETERS)
    if reasoning_requested:
        required_endpoint_parameters.append("reasoning")
    missing_endpoint = [
        name
        for name in required_endpoint_parameters
        if name not in endpoint.supported_parameters
    ]
    if missing_endpoint:
        raise PreflightError(
            "openrouter.preflight.endpoint_parameters_missing",
            f"endpoint {endpoint.tag!r} does not list required parameters: "
            f"{', '.join(missing_endpoint)}; model-level support does not prove "
            "endpoint-level support",
        )
    return PreflightFacts(
        requested_model=requested_model,
        canonical_slug=canonical_slug,
        endpoint=endpoint,
        model_context_length=context_length,
        top_provider_max_completion_tokens=max_completion,
        limitations=tuple(limitations),
    )


class OpenRouterModelCatalogClient:
    """Direct HTTP catalog reader; owns no retry and never follows redirects."""

    def __init__(
        self,
        *,
        api_key: str,
        http_client: httpx.AsyncClient | None = None,
        connect_timeout_seconds: float = 10.0,
        read_timeout_seconds: float = 30.0,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._api_key = api_key
        self._owns_http_client = http_client is None
        self._client = http_client or httpx.AsyncClient(follow_redirects=False)
        self._timeout = httpx.Timeout(
            read_timeout_seconds, connect=connect_timeout_seconds
        )
        self._now = now or (lambda: datetime.now(UTC))

    async def __aenter__(self) -> "OpenRouterModelCatalogClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_http_client:
            await self._client.aclose()

    async def fetch_model(self, requested_model: str) -> OpenRouterModelSnapshot:
        url_path = f"/model/{requested_model}"
        raw, request_id = await self._get(url_path)
        return OpenRouterModelSnapshot(
            requested_model=requested_model,
            fetched_at=self._now(),
            url_path=url_path,
            http_request_id=request_id,
            raw=raw,
        )

    async def fetch_endpoints(
        self, requested_model: str
    ) -> OpenRouterEndpointSnapshot:
        url_path = f"/models/{requested_model}/endpoints"
        raw, request_id = await self._get(url_path)
        return OpenRouterEndpointSnapshot(
            requested_model=requested_model,
            fetched_at=self._now(),
            url_path=url_path,
            http_request_id=request_id,
            raw=raw,
        )

    async def _get(self, url_path: str) -> tuple[dict[str, Any], str | None]:
        url = f"{OPENROUTER_API_ROOT}{url_path}"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Accept": "application/json",
        }
        try:
            response = await self._client.get(
                url, headers=headers, timeout=self._timeout
            )
        except httpx.HTTPError as exc:
            raise CatalogProbeError(
                f"catalog transport failure: {type(exc).__name__}",
                url_path=url_path,
            ) from exc
        request_id = response.headers.get("x-request-id")
        if response.status_code != 200:
            try:
                body: Any = response.json()
            except ValueError:
                body = response.text[:2000]
            raise CatalogProbeError(
                f"catalog GET {url_path} returned HTTP {response.status_code}",
                url_path=url_path,
                http_status=response.status_code,
                request_id=request_id,
                body=body,
            )
        try:
            raw = response.json()
        except ValueError as exc:
            raise CatalogProbeError(
                f"catalog GET {url_path} returned a non-JSON body",
                url_path=url_path,
                http_status=response.status_code,
                request_id=request_id,
            ) from exc
        if not isinstance(raw, dict):
            raise CatalogProbeError(
                f"catalog GET {url_path} returned a non-object JSON root",
                url_path=url_path,
                http_status=response.status_code,
                request_id=request_id,
            )
        return raw, request_id


def build_catalog_snapshot_artifact(
    snapshot: OpenRouterModelSnapshot | OpenRouterEndpointSnapshot,
    *,
    run_id: UUID,
    session_id: UUID | None,
    created_at: datetime,
) -> ArtifactRecord:
    """Run-scoped snapshot artifact (§12): `attempt_id=None`, deterministic ID."""

    label = (
        MODEL_SNAPSHOT_LABEL
        if isinstance(snapshot, OpenRouterModelSnapshot)
        else ENDPOINT_SNAPSHOT_LABEL
    )
    return build_inline_artifact(
        artifact_id=uuid5(run_id, f"{label}/{snapshot.requested_model}"),
        kind=CATALOG_ARTIFACT_KIND,
        media_type="application/json",
        payload=snapshot.model_dump(mode="json"),
        run_id=run_id,
        session_id=session_id,
        created_at=created_at,
        retention_class="eval",
        redaction_status=RedactionStatus.NOT_REQUIRED,
        contains_test_data=True,
    )
