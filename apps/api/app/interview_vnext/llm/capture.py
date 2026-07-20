"""Provider-neutral Capture closure rules for model calls.

The request JSON contains immutable binding/config/projection references, but
those nested references are not part of the Capture graph by themselves.  This
module defines the one deterministic event-input order and validates that a
terminal manifest keeps direct roots for the authoritative provider artifacts.
"""

from __future__ import annotations

from collections.abc import Iterable
from uuid import UUID

from pydantic import ValidationError

from app.interview_vnext.observability.artifacts import ArtifactRef, ArtifactStore
from app.interview_vnext.observability.events import ExecutionEvent, RunManifest

from .port import ModelCallRequest


MODEL_RESULT_KIND = "model.result"
PROVIDER_EVIDENCE_KIND = "model.provider_execution_evidence"
PROVIDER_CONFORMANCE_KIND = "model.provider_conformance"
_MODEL_RESULT_EVENTS = frozenset({"model.call.completed", "model.call.failed"})


class ModelCallCaptureError(ValueError):
    """A model-call event graph or terminal manifest is not closed."""


def model_call_input_artifacts(
    request_artifact: ArtifactRef, request: ModelCallRequest
) -> tuple[ArtifactRef, ...]:
    """Return the normative, deterministic model-call input order (§5.7)."""

    refs = (
        request_artifact,
        request.binding_artifact,
        request.provider_config_artifact,
        request.schema_projection_artifact,
    )
    if len({ref.artifact_id for ref in refs}) != len(refs):
        raise ModelCallCaptureError("model-call authority artifact IDs must be unique")
    return refs


def _request_from_ref(
    ref: ArtifactRef, *, artifact_store: ArtifactStore
) -> ModelCallRequest:
    if ref.kind != "model.request":
        raise ModelCallCaptureError("model-call inputs must start with model.request")
    record = artifact_store.get(ref.artifact_id)
    if record.ref != ref:
        raise ModelCallCaptureError(
            f"model-call request reference mismatch: {ref.artifact_id}"
        )
    try:
        return ModelCallRequest.model_validate_json(record.inline_content or "")
    except ValidationError as exc:
        raise ModelCallCaptureError(
            f"model-call request artifact is invalid: {ref.artifact_id}"
        ) from exc


def _one_ref_of_kind(
    refs: Iterable[ArtifactRef], *, kind: str, required: bool
) -> ArtifactRef | None:
    matches = tuple(ref for ref in refs if ref.kind == kind)
    if len(matches) > 1 or (required and not matches):
        qualifier = "exactly one" if required else "at most one"
        raise ModelCallCaptureError(f"model event requires {qualifier} {kind} artifact")
    return matches[0] if matches else None


def validate_model_call_capture_closure(
    events: tuple[ExecutionEvent, ...],
    *,
    manifest: RunManifest,
    artifact_store: ArtifactStore,
) -> None:
    """Validate direct event edges and terminal roots for every model attempt.

    This deliberately does not infer graph edges from arbitrary nested JSON.
    Instead, each model event must carry the exact direct references, and every
    rooted ``model.request`` must have its binding/config/projection references
    rooted alongside it.  Every persisted attempt's result and gate artifacts
    are provider authority and therefore must also be roots.
    """

    started: dict[tuple[UUID, UUID], tuple[ArtifactRef, ...]] = {}
    result_authority: dict[
        tuple[UUID, UUID], tuple[ArtifactRef, ArtifactRef | None]
    ] = {}
    conformance_by_attempt: dict[tuple[UUID, UUID], ArtifactRef] = {}

    for event in events:
        if event.event_type not in {
            "model.call.started",
            *_MODEL_RESULT_EVENTS,
            "provider.conformance.completed",
        }:
            continue
        if event.operation_id is None or event.attempt_id is None:
            raise ModelCallCaptureError("model-call events require operation and attempt IDs")
        key = (event.operation_id, event.attempt_id)

        if event.event_type == "model.call.started":
            if key in started:
                raise ModelCallCaptureError("duplicate model.call.started for one attempt")
            if not event.input_artifacts:
                raise ModelCallCaptureError("model.call.started has no input artifacts")
            request = _request_from_ref(
                event.input_artifacts[0], artifact_store=artifact_store
            )
            if (
                request.run_id != event.run_id
                or request.session_id != event.session_id
                or request.turn_id != event.turn_id
                or request.operation_id != event.operation_id
                or request.attempt_id != event.attempt_id
                or request.attempt != event.attempt
            ):
                raise ModelCallCaptureError(
                    "model.call.started identity does not match its request"
                )
            expected = model_call_input_artifacts(event.input_artifacts[0], request)
            if event.input_artifacts != expected:
                raise ModelCallCaptureError(
                    "model.call.started input artifacts do not match request authority"
                )
            started[key] = expected
            continue

        expected = started.get(key)
        if expected is None:
            raise ModelCallCaptureError("model result/conformance event has no started event")

        if event.event_type in _MODEL_RESULT_EVENTS:
            if key in result_authority:
                raise ModelCallCaptureError("duplicate model result event for one attempt")
            if event.input_artifacts != expected:
                raise ModelCallCaptureError(
                    "model result input artifacts do not match started authority"
                )
            result_ref = _one_ref_of_kind(
                event.output_artifacts, kind=MODEL_RESULT_KIND, required=True
            )
            assert result_ref is not None
            evidence_ref = _one_ref_of_kind(
                event.output_artifacts, kind=PROVIDER_EVIDENCE_KIND, required=False
            )
            required_tail = (
                (result_ref, evidence_ref) if evidence_ref is not None else (result_ref,)
            )
            if event.output_artifacts[-len(required_tail) :] != required_tail:
                raise ModelCallCaptureError(
                    "model result authority artifacts are not in deterministic tail order"
                )
            result_authority[key] = (result_ref, evidence_ref)
            continue

        if key in conformance_by_attempt:
            raise ModelCallCaptureError(
                "duplicate provider conformance event for one attempt"
            )
        result = result_authority.get(key)
        if result is None or result[1] is None:
            raise ModelCallCaptureError(
                "provider conformance event has no execution-evidence result"
            )
        evidence_ref = result[1]
        assert evidence_ref is not None
        expected_inputs = (expected[1], evidence_ref)
        if event.input_artifacts != expected_inputs:
            raise ModelCallCaptureError(
                "provider conformance inputs must be binding then execution evidence"
            )
        conformance_ref = _one_ref_of_kind(
            event.output_artifacts, kind=PROVIDER_CONFORMANCE_KIND, required=True
        )
        assert conformance_ref is not None
        if event.output_artifacts != (conformance_ref,):
            raise ModelCallCaptureError(
                "provider conformance event must output only its report"
            )
        conformance_by_attempt[key] = conformance_ref

    if not started:
        return

    roots_by_id = {ref.artifact_id: ref for ref in manifest.root_artifacts}
    rooted_requests = tuple(
        ref for ref in manifest.root_artifacts if ref.kind == "model.request"
    )
    if not rooted_requests:
        raise ModelCallCaptureError("terminal model run has no rooted model.request")
    for request_ref in rooted_requests:
        request = _request_from_ref(request_ref, artifact_store=artifact_store)
        for required_ref in model_call_input_artifacts(request_ref, request):
            if roots_by_id.get(required_ref.artifact_id) != required_ref:
                raise ModelCallCaptureError(
                    "terminal manifest omits a request authority root: "
                    f"{required_ref.artifact_id}"
                )

    if not result_authority:
        raise ModelCallCaptureError("terminal model run has no model result event")
    provider_roots: list[ArtifactRef] = []
    for key, (result_ref, evidence_ref) in result_authority.items():
        provider_roots.append(result_ref)
        if evidence_ref is None:
            continue
        provider_roots.append(evidence_ref)
        conformance_ref = conformance_by_attempt.get(key)
        if conformance_ref is None:
            raise ModelCallCaptureError(
                "execution-evidence result has no provider conformance event"
            )
        provider_roots.append(conformance_ref)
    for required_ref in provider_roots:
        if roots_by_id.get(required_ref.artifact_id) != required_ref:
            raise ModelCallCaptureError(
                f"terminal manifest omits provider authority root: {required_ref.artifact_id}"
            )
