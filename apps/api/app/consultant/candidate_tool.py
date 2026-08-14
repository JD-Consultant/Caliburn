"""The one model-facing candidate-document edit Tool."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Protocol
from uuid import UUID

from langchain.tools import ToolRuntime
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import ConfigDict, Field

from app.consultant.candidate_wire import (
    CandidateEditBatch,
    CandidateWireMappingError,
    OutputDocumentChange,
)
from app.consultant.candidate_workspace import (
    CandidateDependencyError,
    CandidateEditReceipt,
    CandidateEditRejected,
    CandidateRevisionConflict,
    CandidateStageRequest,
    CandidateToolCallConflict,
)
from app.consultant.document_authority import DocumentAuthorityError
from app.consultant.document_review import DocumentReviewError
from app.consultant.provider_wire import OutputAnalysisBasis
from app.consultant.results import SkillId
from app.consultant.verification import ConsultantVerificationError


class CandidateStagePort(Protocol):
    async def stage_candidate_revision(
        self,
        *,
        document_id: UUID,
        request: CandidateStageRequest,
    ) -> CandidateEditReceipt: ...


@dataclass(frozen=True)
class CandidateEditToolBinding:
    runtime: CandidateStagePort
    document_id: UUID
    run_id: UUID
    baseline_revision: int
    selected_skill_ids: tuple[SkillId, ...]


class _CandidateEditToolInput(CandidateEditBatch):
    """Strict provider batch plus LangChain's hidden ToolRuntime injection slot."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        arbitrary_types_allowed=True,
    )
    runtime: ToolRuntime


class _CandidateEditStructuredTool(StructuredTool):
    """Keep ToolRuntime validation internal while exposing the exact batch schema."""

    @property
    def tool_call_schema(self) -> type[CandidateEditBatch]:
        return CandidateEditBatch


_REPAIRABLE_STAGE_ERRORS = (
    CandidateDependencyError,
    CandidateRevisionConflict,
    CandidateToolCallConflict,
    CandidateWireMappingError,
    ConsultantVerificationError,
    DocumentAuthorityError,
    DocumentReviewError,
)


def _rejected_payload(
    error: BaseException,
    *,
    binding: CandidateEditToolBinding,
    batch: CandidateEditBatch,
) -> str:
    if isinstance(error, CandidateEditRejected):
        baseline_revision = error.baseline_revision
        candidate_revision = error.candidate_revision
        issues = error.issues
    else:
        baseline_revision = binding.baseline_revision
        candidate_revision = batch.base_candidate_revision
        issues = (str(error),)
    return CandidateEditRejectedPayload(
        baseline_revision=baseline_revision,
        candidate_revision=candidate_revision,
        issues=issues,
    ).model_dump_json()


@dataclass(frozen=True)
class CandidateEditRejectedPayload:
    baseline_revision: int
    candidate_revision: int
    issues: tuple[str, ...]

    def model_dump_json(self) -> str:
        from json import dumps

        return dumps(
            {
                "status": "rejected",
                "baseline_revision": self.baseline_revision,
                "candidate_revision": self.candidate_revision,
                "issues": list(self.issues),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )


def build_job_document_candidate_edit_tool(
    *,
    binding: CandidateEditToolBinding,
    loaded_skill_ids: Callable[[], tuple[SkillId, ...]],
) -> BaseTool:
    """Build a strict batch Tool with all authority data injected by the application."""

    async def job_document_candidate_edit(
        base_candidate_revision: Annotated[int, Field(ge=0)],
        summary: Annotated[str, Field(min_length=1, max_length=240)],
        analysis_bases: Annotated[
            tuple[OutputAnalysisBasis, ...], Field(min_length=1, max_length=32)
        ],
        replacement_changes: Annotated[
            tuple[OutputDocumentChange, ...], Field(min_length=1, max_length=32)
        ],
        runtime: ToolRuntime,
    ) -> str:
        if runtime.tool_call_id is None:
            raise RuntimeError("candidate Tool call is missing its provider call ID")
        batch = CandidateEditBatch(
            base_candidate_revision=base_candidate_revision,
            summary=summary,
            analysis_bases=analysis_bases,
            replacement_changes=replacement_changes,
        )
        request = CandidateStageRequest(
            run_id=binding.run_id,
            baseline_revision=binding.baseline_revision,
            tool_call_id=runtime.tool_call_id,
            batch=batch,
            selected_skill_ids=binding.selected_skill_ids,
            loaded_skill_ids=loaded_skill_ids(),
        )
        try:
            receipt = await binding.runtime.stage_candidate_revision(
                document_id=binding.document_id,
                request=request,
            )
        except CandidateEditRejected as error:
            return _rejected_payload(error, binding=binding, batch=batch)
        except _REPAIRABLE_STAGE_ERRORS as error:
            return _rejected_payload(error, binding=binding, batch=batch)
        return receipt.model_dump_json()

    return _CandidateEditStructuredTool(
        name="job_document_candidate_edit",
        description=(
            "Stage one complete replacement batch in the isolated candidate "
            "workspace. The result reports the persisted semantic diff or a "
            "repairable rejection; it never changes the approved document."
        ),
        args_schema=_CandidateEditToolInput,
        coroutine=job_document_candidate_edit,
    )
