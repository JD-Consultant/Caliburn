"""Grader capture, published under its own root and never mixed with trials.

ADR 0040 §15/§17 separates generator and grader capture. This module writes two
layers — the exact request the grader saw and the terminal grader evidence —
plus a create-only manifest that is the *only* place where ``submission_id`` is
mapped back to ``trial_id``. The blind input artifact therefore stays free of
arm identity even after the run is over.

Nothing here writes into the generator capture root: grading reads a published
trial and produces new evidence beside it.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal, TypeVar

from pydantic import BaseModel, Field, model_validator

from app.professional_consultant.contracts import Identifier, ShortText

from .blind_projection import submission_id_for
from .capture import ResolvedResponseFacts, read_trial_capture
from .contracts import JobAnalysisQualityRubric, R1EvalModel
from .grader import (
    GRADER_ID,
    GRADER_VERSION,
    BlindGraderVerdict,
    GraderFailure,
    GraderModelBinding,
    GraderOperationRequest,
    GraderOperationResponse,
    GraderProvider,
    GraderRunError,
    blind_grader_output_schema,
    blind_grader_prompt,
    build_blind_grader_request,
    build_grader_operation_request,
    run_blind_grading,
)


class GraderCaptureIntegrityError(ValueError):
    pass


class GraderTrialStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class GraderArtifactKind(StrEnum):
    GRADER_INPUT = "grader_input"
    GRADER_EVIDENCE = "grader_evidence"


_GRADER_ARTIFACT_FILENAMES = {
    GraderArtifactKind.GRADER_INPUT: "grader-input.json",
    GraderArtifactKind.GRADER_EVIDENCE: "grader-evidence.json",
}

Sha256Hex = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class GraderAttemptEvidence(R1EvalModel):
    call_index: int = Field(ge=1)
    status: Literal["succeeded", "provider_failed"]
    response: GraderOperationResponse | None
    resolved: ResolvedResponseFacts | None

    @model_validator(mode="after")
    def response_matches_status(self) -> "GraderAttemptEvidence":
        if self.status == "succeeded":
            if self.response is None:
                raise ValueError("successful grader attempt requires a response")
        elif self.response is not None or self.resolved is not None:
            raise ValueError("grader failure cannot invent response evidence")
        return self


class GraderInputCapture(R1EvalModel):
    """Exactly what the grader model received; no arm, model, or trial ID."""

    schema_version: Literal["r1_grader_input.v1"]
    submission_id: Identifier
    request: GraderOperationRequest


class GraderEvidence(R1EvalModel):
    schema_version: Literal["r1_grader_evidence.v1"]
    submission_id: Identifier
    status: GraderTrialStatus
    attempts: tuple[GraderAttemptEvidence, ...]
    verdict: BlindGraderVerdict | None
    failure: GraderFailure | None

    @model_validator(mode="after")
    def terminal_outcome_is_exclusive(self) -> "GraderEvidence":
        actual = tuple(attempt.call_index for attempt in self.attempts)
        expected = tuple(range(1, len(self.attempts) + 1))
        if actual != expected:
            raise ValueError("grader attempt indices must be contiguous")
        if self.status is GraderTrialStatus.SUCCEEDED:
            if self.verdict is None or self.failure is not None:
                raise ValueError("successful grading requires only a verdict")
        elif self.verdict is not None or self.failure is None:
            raise ValueError("failed grading requires only a typed failure")
        return self


class GraderCaptureBundle(R1EvalModel):
    """The correlation to ``trial_id`` lives only here and in the manifest —
    never inside the two artifacts the grader model actually saw."""

    grading_id: Identifier
    trial_id: Identifier
    case_id: Identifier
    binding: GraderModelBinding
    grader_input: GraderInputCapture
    grader_evidence: GraderEvidence

    @model_validator(mode="after")
    def layers_refer_to_one_grading(self) -> "GraderCaptureBundle":
        if self.grading_id != grading_id_for(self.trial_id):
            raise ValueError("grading ID does not belong to the trial")
        if self.grader_input.submission_id != self.grader_evidence.submission_id:
            raise ValueError("grader capture layers must share one submission")
        if self.grader_input.submission_id != submission_id_for(self.trial_id):
            raise ValueError("submission ID does not belong to the trial")
        return self


class GraderArtifactReference(R1EvalModel):
    artifact_id: Identifier
    kind: GraderArtifactKind
    relative_path: ShortText
    sha256: Sha256Hex

    @model_validator(mode="after")
    def path_matches_kind(self) -> "GraderArtifactReference":
        if self.relative_path != _GRADER_ARTIFACT_FILENAMES[self.kind]:
            raise ValueError("grader artifact path does not match its kind")
        return self


class GraderManifest(R1EvalModel):
    """The only place the blind submission is linked back to its trial."""

    schema_version: Literal["r1_grader_manifest.v1"]
    grading_id: Identifier
    trial_id: Identifier
    case_id: Identifier
    submission_id: Identifier
    grader_id: Literal["r1.blind_grade"]
    grader_version: Annotated[
        str, Field(pattern=r"^[1-9][0-9]*\.[0-9]+\.[0-9]+$")
    ]
    grader_prompt_id: Identifier
    grader_schema_id: Identifier
    requested_model: ShortText
    counted_in_generator_budget: Literal[False]
    grader_input: GraderArtifactReference
    grader_evidence: GraderArtifactReference

    @model_validator(mode="after")
    def references_cover_both_layers(self) -> "GraderManifest":
        refs = (self.grader_input, self.grader_evidence)
        if tuple(ref.kind for ref in refs) != tuple(GraderArtifactKind):
            raise ValueError("manifest must reference both grader layers")
        if self.submission_id != submission_id_for(self.trial_id):
            raise ValueError("manifest submission ID does not belong to the trial")
        return self


class LoadedGraderCapture(R1EvalModel):
    manifest: GraderManifest
    grader_input: GraderInputCapture
    grader_evidence: GraderEvidence


def _canonical_bytes(model: BaseModel) -> bytes:
    text = json.dumps(
        model.model_dump(mode="json"),
        ensure_ascii=False,
        sort_keys=True,
        allow_nan=False,
        separators=(",", ":"),
    )
    return (text + "\n").encode("utf-8")


def _grading_directory(root: Path, grading_id: str) -> Path:
    if any(character in grading_id for character in ("/", "\\", ":")):
        raise GraderCaptureIntegrityError(
            "grading ID is not safe as a directory name"
        )
    return root / grading_id


def grading_id_for(trial_id: str) -> str:
    return f"grade-{trial_id}"


def write_grader_capture(root: Path, bundle: GraderCaptureBundle) -> GraderManifest:
    """Publish one grading once; the manifest is the publication marker."""

    bundle = GraderCaptureBundle.model_validate_json(bundle.model_dump_json())
    grading_id = bundle.grading_id
    grading_dir = _grading_directory(root, grading_id)
    root.mkdir(parents=True, exist_ok=True)
    grading_dir.mkdir(exist_ok=False)

    artifacts: tuple[tuple[GraderArtifactKind, BaseModel], ...] = (
        (GraderArtifactKind.GRADER_INPUT, bundle.grader_input),
        (GraderArtifactKind.GRADER_EVIDENCE, bundle.grader_evidence),
    )
    artifact_bytes = tuple(
        (kind, _canonical_bytes(artifact)) for kind, artifact in artifacts
    )
    references = tuple(
        GraderArtifactReference(
            artifact_id=f"{grading_id}:{kind.value}",
            kind=kind,
            relative_path=_GRADER_ARTIFACT_FILENAMES[kind],
            sha256=hashlib.sha256(data).hexdigest(),
        )
        for kind, data in artifact_bytes
    )
    manifest = GraderManifest(
        schema_version="r1_grader_manifest.v1",
        grading_id=grading_id,
        trial_id=bundle.trial_id,
        case_id=bundle.case_id,
        submission_id=bundle.grader_input.submission_id,
        grader_id=GRADER_ID,
        grader_version=GRADER_VERSION,
        grader_prompt_id=bundle.grader_input.request.prompt.prompt_id,
        grader_schema_id=bundle.grader_input.request.output_schema.schema_id,
        requested_model=bundle.binding.requested_model,
        counted_in_generator_budget=False,
        grader_input=references[0],
        grader_evidence=references[1],
    )

    for reference, (_, data) in zip(references, artifact_bytes, strict=True):
        with (grading_dir / reference.relative_path).open("xb") as handle:
            handle.write(data)
    with (grading_dir / "manifest.json").open("xb") as handle:
        handle.write(_canonical_bytes(manifest))
    return manifest


_ModelT = TypeVar("_ModelT", bound=BaseModel)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise GraderCaptureIntegrityError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    raise GraderCaptureIntegrityError(f"non-standard JSON constant: {value}")


def _parse_model(data: bytes, model: type[_ModelT]) -> _ModelT:
    if data.startswith(b"\xef\xbb\xbf"):
        raise GraderCaptureIntegrityError("capture JSON must not contain a BOM")
    try:
        payload = json.loads(
            data.decode("utf-8"),
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
    except GraderCaptureIntegrityError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise GraderCaptureIntegrityError(
            "grader capture JSON failed validation"
        ) from exc


def _read_artifact(
    grading_dir: Path,
    reference: GraderArtifactReference,
    model: type[_ModelT],
) -> _ModelT:
    path = grading_dir / reference.relative_path
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise GraderCaptureIntegrityError(
            "referenced grader artifact is missing"
        ) from exc
    if hashlib.sha256(data).hexdigest() != reference.sha256:
        raise GraderCaptureIntegrityError("grader artifact digest mismatch")
    return _parse_model(data, model)


def read_grader_capture(root: Path, grading_id: str) -> LoadedGraderCapture:
    """Read a published grading and fail closed on any integrity drift."""

    grading_dir = _grading_directory(root, grading_id)
    expected_files = {*_GRADER_ARTIFACT_FILENAMES.values(), "manifest.json"}
    try:
        actual_files = {path.name for path in grading_dir.iterdir()}
    except OSError as exc:
        raise GraderCaptureIntegrityError(
            "grader capture directory is missing"
        ) from exc
    if actual_files != expected_files:
        raise GraderCaptureIntegrityError(
            "grader capture file set is incomplete or unlisted"
        )

    manifest = _parse_model(
        (grading_dir / "manifest.json").read_bytes(), GraderManifest
    )
    if manifest.grading_id != grading_id:
        raise GraderCaptureIntegrityError("manifest grading identity mismatch")
    grader_input = _read_artifact(
        grading_dir, manifest.grader_input, GraderInputCapture
    )
    grader_evidence = _read_artifact(
        grading_dir, manifest.grader_evidence, GraderEvidence
    )
    if (
        grader_input.submission_id != manifest.submission_id
        or grader_evidence.submission_id != manifest.submission_id
        or grader_input.request.prompt.prompt_id != manifest.grader_prompt_id
        or grader_input.request.output_schema.schema_id
        != manifest.grader_schema_id
    ):
        raise GraderCaptureIntegrityError("grader manifest relation mismatch")
    return LoadedGraderCapture(
        manifest=manifest,
        grader_input=grader_input,
        grader_evidence=grader_evidence,
    )


class _RecordingGraderProvider:
    """Wraps the caller's provider to keep terminal attempt evidence."""

    def __init__(self, provider: GraderProvider) -> None:
        self._provider = provider
        self.attempts: list[GraderAttemptEvidence] = []
        self.requests: list[GraderOperationRequest] = []

    async def grade(
        self, request: GraderOperationRequest
    ) -> GraderOperationResponse:
        call_index = len(self.requests) + 1
        self.requests.append(request)
        try:
            response = await self._provider.grade(request)
        except Exception:
            self.attempts.append(
                GraderAttemptEvidence(
                    call_index=call_index,
                    status="provider_failed",
                    response=None,
                    resolved=None,
                )
            )
            raise
        self.attempts.append(
            GraderAttemptEvidence(
                call_index=call_index,
                status="succeeded",
                response=response,
                resolved=None,
            )
        )
        return response


async def grade_published_trial(
    *,
    capture_root: Path,
    grading_root: Path,
    trial_id: str,
    rubric: JobAnalysisQualityRubric,
    provider: GraderProvider,
    binding: GraderModelBinding,
) -> GraderManifest:
    """Grade one published trial and publish the grading beside it, not in it."""

    trial = read_trial_capture(capture_root, trial_id)
    result = trial.trial_evidence.result
    if result is None:
        raise GraderCaptureIntegrityError(
            "a failed trial has no generator product to grade"
        )
    request = build_blind_grader_request(
        trial_id=trial_id,
        source=trial.source_state.runtime_case.runtime_input,
        result=result,
        rubric=rubric,
    )
    grading_id = grading_id_for(trial_id)
    recorder = _RecordingGraderProvider(provider)
    verdict: BlindGraderVerdict | None = None
    failure: GraderFailure | None = None
    try:
        verdict = await run_blind_grading(request, provider=recorder)
    except GraderRunError as exc:
        failure = exc.failure

    grader_input = GraderInputCapture(
        schema_version="r1_grader_input.v1",
        submission_id=request.submission_id,
        request=(
            recorder.requests[0]
            if recorder.requests
            else build_grader_operation_request(request)
        ),
    )
    evidence = GraderEvidence(
        schema_version="r1_grader_evidence.v1",
        submission_id=request.submission_id,
        status=(
            GraderTrialStatus.SUCCEEDED
            if failure is None
            else GraderTrialStatus.FAILED
        ),
        attempts=tuple(recorder.attempts),
        verdict=verdict,
        failure=failure,
    )
    return write_grader_capture(
        grading_root,
        GraderCaptureBundle(
            grading_id=grading_id,
            trial_id=trial_id,
            case_id=trial.manifest.case_id,
            binding=binding,
            grader_input=grader_input,
            grader_evidence=evidence,
        ),
    )


__all__ = [
    "GraderArtifactKind",
    "GraderArtifactReference",
    "GraderAttemptEvidence",
    "GraderCaptureBundle",
    "GraderCaptureIntegrityError",
    "GraderEvidence",
    "GraderInputCapture",
    "GraderManifest",
    "GraderTrialStatus",
    "LoadedGraderCapture",
    "blind_grader_output_schema",
    "blind_grader_prompt",
    "grade_published_trial",
    "grading_id_for",
    "read_grader_capture",
    "write_grader_capture",
]
