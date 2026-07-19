"""Shared v2 resolved-call fixtures for interview vNext adapter/executor tests.

V3-5A: a provider adapter or scripted port consumes a ``ResolvedModelCall``
(request + resolved ``ProviderBinding`` + schema projection), not a bare
``ModelCallRequest``. Building a valid call by hand is delicate because the
request, binding and projection are cross-hashed (the request carries the
binding/config/projection artifact refs whose content hashes must match the
canonical hash of each object). These helpers centralise the turn output
projection and the three binding-derived artifact refs so every test builds a
consistent call without duplicating that hash wiring.

Not a test module (no ``test_`` prefix); imported as ``tests.interview_vnext_llm_fixtures``.
"""

from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from typing import Any
from uuid import uuid4

from app.interview_vnext.domain.hashing import canonical_hash, canonical_json
from app.interview_vnext.llm.binding import ProviderBinding
from app.interview_vnext.llm.execution import (
    CacheStatus,
    ProviderExecutionEvidence,
    TransformationStatus,
    define_provider_execution_evidence,
)
from app.interview_vnext.llm.port import ModelCallRequest, ResolvedModelCall
from app.interview_vnext.llm.result import TokenUsage
from app.interview_vnext.llm.portable_schema import (
    PORTABLE_STRICT_OUTPUT_POLICY_V2,
    ProjectedSchema,
    SchemaProjectionReport,
    project_portable_strict_output_schema,
)
from app.interview_vnext.llm.schema_exports import SCHEMA_EXPORTS
from app.interview_vnext.llm.turn_interpret import TurnInterpretOutput
from app.interview_vnext.observability.artifacts import ArtifactRef


TURN_OUTPUT_SCHEMA_ID = (
    "https://caliburn.local/schemas/turn-interpret-output.v1.schema.json"
)


@lru_cache(maxsize=1)
def turn_output_projection() -> ProjectedSchema:
    """The active turn output projection the executor builds for every request.

    Byte-identical to the published ``turn-interpret-output.v1`` portable schema,
    so a request whose ``output_schema_artifact`` hashes the published schema is
    consistent with this projection's ``projected_schema_hash``.
    """

    schema_id, title, _factory = SCHEMA_EXPORTS["turn-interpret-output.v1.schema.json"]
    source = {**TurnInterpretOutput.model_json_schema(), "$id": schema_id, "title": title}
    return project_portable_strict_output_schema(
        source,
        source_schema_id=schema_id,
        target_profile=PORTABLE_STRICT_OUTPUT_POLICY_V2.target_profile,
    )


def turn_output_schema() -> dict[str, Any]:
    return deepcopy(turn_output_projection().schema)


def _ref(payload: Any, *, kind: str, schema_id: str | None = None) -> ArtifactRef:
    content = canonical_json(payload)
    return ArtifactRef(
        artifact_id=uuid4(),
        kind=kind,
        media_type="application/json",
        schema_id=schema_id,
        content_hash=canonical_hash(payload),
        byte_size=len(content.encode("utf-8")),
    )


def output_schema_artifact_ref(schema: dict[str, Any] | None = None) -> ArtifactRef:
    return _ref(
        schema if schema is not None else turn_output_schema(),
        kind="model.output_schema",
        schema_id=TURN_OUTPUT_SCHEMA_ID,
    )


def binding_artifact_ref(binding: ProviderBinding) -> ArtifactRef:
    """Ref whose content hash equals ``canonical_hash(binding)`` (ResolvedModelCall gate)."""

    return _ref(binding, kind="model.provider_binding")


def config_artifact_ref(provider_config: Any) -> ArtifactRef:
    """Ref whose content hash equals ``binding.provider_config_hash``.

    Pass the exact config object (dict or Pydantic model) whose canonical hash the
    binding was built from.
    """

    return _ref(provider_config, kind="provider.config")


def projection_artifact_ref(report: SchemaProjectionReport | None = None) -> ArtifactRef:
    return _ref(
        report if report is not None else turn_output_projection().report,
        kind="model.schema_projection",
    )


def unknown_execution_evidence(
    binding: ProviderBinding, *, usage: TokenUsage | None = None
) -> ProviderExecutionEvidence:
    """Minimal, route-less execution evidence bound to ``binding``.

    ``gateway_resolved_model`` and ``raw_routing_artifact`` are null, so an
    envelope can carry it without also carrying a routing artifact. Attribution
    conformance would reject it (transformation/cache ``unknown``), but the
    envelope shape validators only check binding/provider identity.
    """

    return define_provider_execution_evidence(
        binding_id=binding.binding_id,
        binding_hash=binding.binding_hash,
        adapter_id=binding.adapter_id,
        adapter_version=binding.adapter_version,
        gateway_provider=binding.gateway_provider,
        requested_model=binding.requested_model,
        gateway_resolved_model=None,
        upstream_provider=None,
        upstream_model=None,
        upstream_endpoint=None,
        route_strategy=None,
        upstream_attempt_count=None,
        transformation_status=TransformationStatus.UNKNOWN,
        pipeline_stages=(),
        cache_status=CacheStatus.UNKNOWN,
        provider_request_id=None,
        generation_id=None,
        usage=usage or TokenUsage(limitations=("scripted evidence has no usage",)),
        cost_decimal=None,
        limitations=("scripted evidence has no route metadata",),
        raw_routing_artifact=None,
    )


def resolved_call(
    request: ModelCallRequest,
    binding: ProviderBinding,
    *,
    projection: SchemaProjectionReport | None = None,
) -> ResolvedModelCall:
    """Wrap a v2 request and its binding into a consistent ``ResolvedModelCall``."""

    return ResolvedModelCall(
        request=request,
        binding=binding,
        schema_projection=projection or turn_output_projection().report,
    )
