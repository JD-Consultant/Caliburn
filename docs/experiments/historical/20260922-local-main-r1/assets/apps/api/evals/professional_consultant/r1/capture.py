"""Immutable, runtime-external trial capture for R1 evaluation."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, TypeVar

from pydantic import BaseModel, Field, model_validator

from app.professional_consultant.contracts import (
    Identifier,
    ShortText,
    TaskDiscoveryOutput,
)
from app.professional_consultant.runner import (
    OperationFailure,
    StructuredOperationRequest,
    StructuredOperationResponse,
)

from .ablation import AblationArm, ArmId
from .contracts import R1EvalModel, R1RuntimeCase, SourceType
from .minimal_harness import MinimalTaskDiscoveryOutput


class CaptureIntegrityError(ValueError):
    pass


class TrialStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class CaptureArtifactKind(StrEnum):
    SOURCE_STATE_SNAPSHOT = "source_state_snapshot"
    CONTEXT_OPERATION_INPUT = "context_operation_input"
    TRIAL_EVIDENCE = "trial_evidence"


class ResolvedResponseFacts(R1EvalModel):
    """Facts supplied by response/generation evidence, never request defaults."""

    evidence_source: Literal["response", "generation"]
    generation_id: Identifier
    resolved_model: ShortText
    resolved_provider: ShortText
    resolved_endpoint: ShortText | None


class CapturedOperationInput(R1EvalModel):
    call_index: int = Field(ge=1)
    requested_model: ShortText
    request: StructuredOperationRequest


class ProviderAttemptEvidence(R1EvalModel):
    call_index: int = Field(ge=1)
    status: Literal["succeeded", "provider_failed"]
    response: StructuredOperationResponse | None
    resolved: ResolvedResponseFacts | None

    @model_validator(mode="after")
    def response_matches_status(self) -> "ProviderAttemptEvidence":
        if self.status == "succeeded":
            if self.response is None or self.resolved is None:
                raise ValueError("successful attempt requires response evidence")
        elif self.response is not None or self.resolved is not None:
            raise ValueError("provider failure cannot invent response evidence")
        return self


class SourceStateSnapshot(R1EvalModel):
    schema_version: Literal["r1_source_state_snapshot.v1"]
    trial_id: Identifier
    case_id: Identifier
    arm_id: ArmId
    runtime_case: R1RuntimeCase

    @model_validator(mode="after")
    def metadata_matches_case(self) -> "SourceStateSnapshot":
        if self.runtime_case.metadata.case_id != self.case_id:
            raise ValueError("source-state case relation is inconsistent")
        return self


class ContextOperationInputCapture(R1EvalModel):
    schema_version: Literal["r1_context_operation_input.v1"]
    trial_id: Identifier
    case_id: Identifier
    arm_id: ArmId
    calls: tuple[CapturedOperationInput, ...]

    @model_validator(mode="after")
    def call_indices_are_contiguous(self) -> "ContextOperationInputCapture":
        actual = tuple(call.call_index for call in self.calls)
        expected = tuple(range(1, len(self.calls) + 1))
        if actual != expected:
            raise ValueError("operation call indices must be contiguous")
        return self


class TrialEvidence(R1EvalModel):
    schema_version: Literal["r1_trial_evidence.v1"]
    trial_id: Identifier
    case_id: Identifier
    arm_id: ArmId
    status: TrialStatus
    attempts: tuple[ProviderAttemptEvidence, ...]
    result: TaskDiscoveryOutput | MinimalTaskDiscoveryOutput | None
    failure: OperationFailure | None

    @model_validator(mode="after")
    def terminal_outcome_is_exclusive(self) -> "TrialEvidence":
        actual = tuple(attempt.call_index for attempt in self.attempts)
        expected = tuple(range(1, len(self.attempts) + 1))
        if actual != expected:
            raise ValueError("provider attempt indices must be contiguous")
        if self.status is TrialStatus.SUCCEEDED:
            if self.result is None or self.failure is not None:
                raise ValueError("successful trial requires only a result")
        elif self.result is not None or self.failure is None:
            raise ValueError("failed trial requires only a typed failure")
        return self


class TrialCaptureBundle(R1EvalModel):
    arm: AblationArm
    source_state: SourceStateSnapshot
    context_operation_input: ContextOperationInputCapture
    trial_evidence: TrialEvidence

    @model_validator(mode="after")
    def layers_refer_to_one_trial(self) -> "TrialCaptureBundle":
        identities = {
            (
                layer.trial_id,
                layer.case_id,
                layer.arm_id,
            )
            for layer in (
                self.source_state,
                self.context_operation_input,
                self.trial_evidence,
            )
        }
        if len(identities) != 1:
            raise ValueError("capture layers must refer to one trial")
        if self.source_state.arm_id is not self.arm.arm_id:
            raise ValueError("capture arm snapshot does not match layer identity")
        if len(self.context_operation_input.calls) != len(
            self.trial_evidence.attempts
        ):
            raise ValueError("operation inputs and attempt evidence must align")
        return self


Sha256Hex = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


_ARTIFACT_FILENAMES = {
    CaptureArtifactKind.SOURCE_STATE_SNAPSHOT: "source-state.json",
    CaptureArtifactKind.CONTEXT_OPERATION_INPUT: "context-operation-input.json",
    CaptureArtifactKind.TRIAL_EVIDENCE: "trial-evidence.json",
}


class ArtifactReference(R1EvalModel):
    artifact_id: Identifier
    kind: CaptureArtifactKind
    relative_path: ShortText
    sha256: Sha256Hex

    @model_validator(mode="after")
    def path_matches_kind(self) -> "ArtifactReference":
        if self.relative_path != _ARTIFACT_FILENAMES[self.kind]:
            raise ValueError("artifact path does not match its kind")
        return self


class TrialManifest(R1EvalModel):
    schema_version: Literal["r1_trial_manifest.v1"]
    trial_id: Identifier
    case_id: Identifier
    case_family_id: Identifier
    source_type: SourceType
    arm: AblationArm
    expected_generator_calls: Literal[1, 2]
    source_state: ArtifactReference
    context_operation_input: ArtifactReference
    trial_evidence: ArtifactReference

    @model_validator(mode="after")
    def references_cover_the_three_layers(self) -> "TrialManifest":
        refs = (
            self.source_state,
            self.context_operation_input,
            self.trial_evidence,
        )
        expected_kinds = tuple(CaptureArtifactKind)
        if tuple(ref.kind for ref in refs) != expected_kinds:
            raise ValueError("manifest must reference all three capture layers")
        if self.expected_generator_calls != self.arm.expected_generator_calls:
            raise ValueError("manifest call budget must match arm snapshot")
        return self


class LoadedTrialCapture(R1EvalModel):
    manifest: TrialManifest
    source_state: SourceStateSnapshot
    context_operation_input: ContextOperationInputCapture
    trial_evidence: TrialEvidence


def _canonical_bytes(model: BaseModel) -> bytes:
    text = json.dumps(
        model.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    return (text + "\n").encode("utf-8")


def _artifact_reference(
    trial_id: str,
    kind: CaptureArtifactKind,
    data: bytes,
) -> ArtifactReference:
    return ArtifactReference(
        artifact_id=f"{trial_id}:{kind.value}",
        kind=kind,
        relative_path=_ARTIFACT_FILENAMES[kind],
        sha256=hashlib.sha256(data).hexdigest(),
    )


def _trial_directory(root: Path, trial_id: str) -> Path:
    if any(character in trial_id for character in ("/", "\\", ":")):
        raise CaptureIntegrityError("trial ID is not safe as a directory name")
    return root / trial_id


def write_trial_capture(root: Path, bundle: TrialCaptureBundle) -> TrialManifest:
    """Publish one trial once; the manifest is the final publication marker."""

    bundle = TrialCaptureBundle.model_validate_json(bundle.model_dump_json())
    trial_id = bundle.source_state.trial_id
    trial_dir = _trial_directory(root, trial_id)
    root.mkdir(parents=True, exist_ok=True)
    trial_dir.mkdir(exist_ok=False)

    artifacts: tuple[tuple[CaptureArtifactKind, BaseModel], ...] = (
        (CaptureArtifactKind.SOURCE_STATE_SNAPSHOT, bundle.source_state),
        (
            CaptureArtifactKind.CONTEXT_OPERATION_INPUT,
            bundle.context_operation_input,
        ),
        (CaptureArtifactKind.TRIAL_EVIDENCE, bundle.trial_evidence),
    )
    artifact_bytes = tuple(
        (kind, _canonical_bytes(artifact)) for kind, artifact in artifacts
    )
    references = tuple(
        _artifact_reference(trial_id, kind, data)
        for kind, data in artifact_bytes
    )
    metadata = bundle.source_state.runtime_case.metadata
    manifest = TrialManifest(
        schema_version="r1_trial_manifest.v1",
        trial_id=trial_id,
        case_id=metadata.case_id,
        case_family_id=metadata.case_family_id,
        source_type=metadata.source_type,
        arm=bundle.arm,
        expected_generator_calls=bundle.arm.expected_generator_calls,
        source_state=references[0],
        context_operation_input=references[1],
        trial_evidence=references[2],
    )

    for reference, (_, data) in zip(references, artifact_bytes, strict=True):
        with (trial_dir / reference.relative_path).open("xb") as handle:
            handle.write(data)
    with (trial_dir / "manifest.json").open("xb") as handle:
        handle.write(_canonical_bytes(manifest))
    return manifest


_ModelT = TypeVar("_ModelT", bound=BaseModel)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CaptureIntegrityError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise CaptureIntegrityError(f"non-standard JSON constant: {value}")


def _parse_model(data: bytes, model: type[_ModelT]) -> _ModelT:
    if data.startswith(b"\xef\xbb\xbf"):
        raise CaptureIntegrityError("capture JSON must not contain a BOM")
    try:
        text = data.decode("utf-8")
        payload = json.loads(
            text,
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
        normalized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
            separators=(",", ":"),
        )
        return model.model_validate_json(normalized)
    except CaptureIntegrityError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise CaptureIntegrityError("capture JSON failed validation") from exc


def _read_artifact(
    trial_dir: Path,
    reference: ArtifactReference,
    model: type[_ModelT],
) -> _ModelT:
    path = trial_dir / reference.relative_path
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise CaptureIntegrityError("referenced capture artifact is missing") from exc
    actual_digest = hashlib.sha256(data).hexdigest()
    if actual_digest != reference.sha256:
        raise CaptureIntegrityError("capture artifact digest mismatch")
    return _parse_model(data, model)


def read_trial_capture(root: Path, trial_id: str) -> LoadedTrialCapture:
    """Read a published trial and fail closed on any integrity drift."""

    trial_dir = _trial_directory(root, trial_id)
    expected_files = {*_ARTIFACT_FILENAMES.values(), "manifest.json"}
    try:
        actual_files = {path.name for path in trial_dir.iterdir()}
    except OSError as exc:
        raise CaptureIntegrityError("trial capture directory is missing") from exc
    if actual_files != expected_files:
        raise CaptureIntegrityError("trial capture file set is incomplete or unlisted")

    manifest = _parse_model(
        (trial_dir / "manifest.json").read_bytes(), TrialManifest
    )
    if manifest.trial_id != trial_id:
        raise CaptureIntegrityError("manifest trial identity mismatch")
    source_state = _read_artifact(
        trial_dir, manifest.source_state, SourceStateSnapshot
    )
    context = _read_artifact(
        trial_dir,
        manifest.context_operation_input,
        ContextOperationInputCapture,
    )
    evidence = _read_artifact(
        trial_dir, manifest.trial_evidence, TrialEvidence
    )
    try:
        bundle = TrialCaptureBundle(
            arm=manifest.arm,
            source_state=source_state,
            context_operation_input=context,
            trial_evidence=evidence,
        )
    except ValueError as exc:
        raise CaptureIntegrityError("capture layer relation mismatch") from exc
    metadata = source_state.runtime_case.metadata
    if (
        manifest.case_id != metadata.case_id
        or manifest.case_family_id != metadata.case_family_id
        or manifest.source_type is not metadata.source_type
        or manifest.arm.arm_id is not source_state.arm_id
    ):
        raise CaptureIntegrityError("manifest metadata relation mismatch")
    return LoadedTrialCapture(
        manifest=manifest,
        source_state=bundle.source_state,
        context_operation_input=bundle.context_operation_input,
        trial_evidence=bundle.trial_evidence,
    )
