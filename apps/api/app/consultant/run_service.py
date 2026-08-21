"""Production assembly for one source-first professional-consultant run."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from langchain_core.messages import HumanMessage
from deepagents.backends.utils import file_data_to_string

from app.adapters.langgraph.postgres import (
    PostgresConsultantRuntime,
    open_postgres_consultant_runtime,
)
from app.config import Settings
from app.consultant.agent import build_professional_consultant_agent
from app.consultant.candidate_publication import (
    CandidatePublicationStale,
    publish_checked_candidate as validate_checked_candidate,
)
from app.consultant.context import (
    ConsultantAgentRuntimeContext,
    ConsultantContextMiddleware,
    ContextRequest,
    DocumentSourceLookup,
)
from app.consultant.interview import VerifiedConsultantCommit
from app.consultant.model_output import (
    ConsultantModelOutput,
    map_consultant_model_output,
)
from app.consultant.model_runtime import (
    AttemptReceiptCallback,
    ConsultantModelProfile,
    OutputTokenParameter,
    ResolvedExecution,
    RunPolicy,
    classify_consultant_failure,
    resolve_execution,
)
from app.consultant.skill_backend import CONSULTANT_SKILL_IDS
from app.consultant.state import (
    CheckedCandidateReceipt,
    DocumentChangeSet,
    RunReceipt,
    RunExecutionEvidence,
    RunStatus,
    SourceProcessingStatus,
)
from app.consultant.workspace_backend import build_consultant_workspace_backend
from app.consultant.workspace_resources import WorkspaceCatalog
from app.consultant.workspace_tools import (
    CandidateCheckToolBinding,
)
from app.consultant.verification import (
    ConsultantVerificationError,
    verify_consultant_result,
    verify_context_selection,
    verify_model_attempts,
)


logger = logging.getLogger(__name__)


def _run_execution_evidence(
    execution: ResolvedExecution,
    *,
    runtime_context: ConsultantAgentRuntimeContext | None = None,
    callback: AttemptReceiptCallback | None = None,
) -> RunExecutionEvidence:
    return RunExecutionEvidence(
        resolved_execution=execution.model_dump(mode="json"),
        context_selection_receipts=tuple(
            receipt.model_dump(mode="json")
            for receipt in (
                runtime_context.context_receipts
                if runtime_context is not None
                else ()
            )
        ),
        attempt_receipts=tuple(
            receipt.model_dump(mode="json")
            for receipt in (callback.receipts if callback is not None else ())
        ),
    )


def build_configured_execution(config: Settings) -> ResolvedExecution:
    """Resolve one immutable model/profile/policy snapshot for this run."""

    profile = ConsultantModelProfile(
        profile_id=config.consultant_profile_id,
        revision=config.consultant_profile_revision,
        requested_model=config.consultant_model,
        provider_allowlist=(config.consultant_provider,),
        temperature=config.consultant_temperature,
        top_p=config.consultant_top_p,
        max_output_tokens=config.consultant_max_output_tokens,
        output_token_parameter=OutputTokenParameter(
            config.consultant_output_token_parameter
        ),
        reasoning_effort=config.consultant_reasoning_effort,
        timeout_seconds=config.consultant_timeout_seconds,
    )
    policy = RunPolicy(
        policy_id="interactive-consultation",
        revision=config.consultant_policy_revision,
        run_kind="interactive_consultation",
        allowed_skill_ids=CONSULTANT_SKILL_IDS,
        allowed_tool_ids=(
            "ls",
            "read_file",
            "grep",
            "write_file",
            "edit_file",
            "delete",
            "check_candidate_document",
        ),
        max_context_tokens=config.consultant_max_context_tokens,
        max_model_calls=config.consultant_max_model_calls,
        max_lookup_waves=config.consultant_max_lookup_waves,
        max_total_tool_calls=config.consultant_max_total_tool_calls,
        model_retry_count=config.consultant_model_retry_count,
        tool_retry_count=config.consultant_tool_retry_count,
        max_elapsed_seconds=config.consultant_max_elapsed_seconds,
        max_total_tokens=config.consultant_max_total_tokens,
        max_cost_usd=config.consultant_max_cost_usd,
    )
    return resolve_execution(profile, policy)


def _candidate_files_from_response(
    response: Mapping[str, Any],
    workspace,
) -> dict[str, str]:
    raw_files = response.get("files")
    if not isinstance(raw_files, Mapping):
        raise CandidatePublicationStale(
            "candidate publication requires the current workspace files"
        )
    files: dict[str, str] = {}
    for raw_path, raw_file in raw_files.items():
        if not isinstance(raw_path, str):
            raise CandidatePublicationStale(
                "candidate publication found a non-text workspace path"
            )
        try:
            canonical_path = workspace.candidate_backend.validate_candidate_file_path(
                raw_path
            )
        except ValueError as error:
            raise CandidatePublicationStale(
                f"candidate publication found an invalid workspace path: {raw_path!r}"
            ) from error
        if canonical_path != raw_path:
            raise CandidatePublicationStale(
                f"candidate publication requires canonical workspace paths: {raw_path!r}"
            )
        if isinstance(raw_file, str):
            files[canonical_path] = raw_file
        elif isinstance(raw_file, bytes):
            files[canonical_path] = raw_file.decode("utf-8")
        elif isinstance(raw_file, Mapping):
            files[canonical_path] = file_data_to_string(raw_file)
        else:
            raise CandidatePublicationStale(
                f"candidate publication found an unsupported file value: {raw_path!r}"
            )
    return dict(sorted(files.items()))


async def execute_admitted_consultant_turn(
    *,
    runtime: PostgresConsultantRuntime,
    document_id: UUID,
    run_id: UUID,
    source_id: UUID,
    execution: ResolvedExecution,
    model: Any,
    agent_factory: Callable[..., Any] = build_professional_consultant_agent,
):
    """Execute and verify one already-admitted answer, then commit semantically."""

    runtime_context: ConsultantAgentRuntimeContext | None = None
    callback: AttemptReceiptCallback | None = None
    try:
        snapshot = await runtime.reopen_document(document_id)
        latest = (
            RunReceipt.model_validate(snapshot.latest_run)
            if snapshot.latest_run is not None
            else None
        )
        if (
            latest is None
            or latest.status is not RunStatus.SOURCE_SAVED
            or latest.run_id != run_id
            or latest.source_id != source_id
        ):
            raise ValueError("consultant run is not the admitted source-saved run")
        current_source = await runtime.get_source(document_id, source_id)
        if current_source.processing_status is not SourceProcessingStatus.COMMITTED:
            raise ValueError("admitted employee source is not durable")

        all_sources = await runtime.list_sources(document_id)
        current_sources = tuple(
            source for source in all_sources if source.validity.value == "current"
        )
        recent_source_ids = tuple(source.source_id for source in current_sources[-24:])
        current_work_id = (
            snapshot.current_interview.work_id
            if snapshot.current_interview is not None
            else None
        )
        focus_subject_id = None
        if current_work_id is not None:
            focus_subject = snapshot.interview_work.get(str(current_work_id), {}).get(
                "subject_id"
            )
            if focus_subject is not None:
                focus_subject_id = UUID(str(focus_subject))
        request = ContextRequest(
            run_id=run_id,
            current_source_id=source_id,
            current_work_id=current_work_id,
            focus_subject_id=focus_subject_id,
            recent_source_ids=recent_source_ids,
            selected_skill_ids=CONSULTANT_SKILL_IDS,
        )
        runtime_context = ConsultantAgentRuntimeContext(
            runtime=runtime,
            snapshot=snapshot,
            execution=execution,
            request=request,
        )
        pending = tuple(
            DocumentChangeSet.model_validate(value)
            for value in snapshot.review_queue.values()
        )
        catalog = WorkspaceCatalog.from_snapshot(
            snapshot.approved_document,
            pending=pending,
            sources=all_sources,
        )
        workspace = build_consultant_workspace_backend(
            runtime=runtime,
            document_id=document_id,
            run_id=run_id,
            catalog=catalog,
            selected_skill_ids=CONSULTANT_SKILL_IDS,
            source_lookup=DocumentSourceLookup(runtime),
        )
        agent = agent_factory(
            model=model,
            execution=execution,
            selected_skill_ids=CONSULTANT_SKILL_IDS,
            workspace_binding=workspace,
            candidate_check_binding=CandidateCheckToolBinding(
                runtime=runtime,
                workspace=workspace,
            ),
            context_middleware=ConsultantContextMiddleware(),
            context_schema=ConsultantAgentRuntimeContext,
        )
        callback = AttemptReceiptCallback(
            product_run_id=run_id,
            execution=execution,
        )
        elapsed_seconds = max(
            0.0,
            (datetime.now(UTC) - latest.started_at).total_seconds(),
        )
        remaining_seconds = execution.max_elapsed_seconds - elapsed_seconds
        if remaining_seconds <= 0:
            raise TimeoutError("consultant run exceeded elapsed-time budget")
        async with asyncio.timeout(remaining_seconds):
            response = await agent.ainvoke(
                {
                    "messages": [
                        HumanMessage(
                            content=current_source.text,
                            additional_kwargs={
                                "employee_source_id": str(source_id),
                            },
                        )
                    ],
                    "files": dict(workspace.initial_files),
                },
                context=runtime_context,
                config={
                    "callbacks": [callback],
                    "metadata": {
                        "consultant_run_id": str(run_id),
                        "consultant_document_id": str(document_id),
                        "profile_id": execution.profile_id,
                        "profile_revision": execution.profile_revision,
                    },
                },
            )
        if (
            datetime.now(UTC) - latest.started_at
        ).total_seconds() > execution.max_elapsed_seconds:
            raise TimeoutError("consultant run exceeded elapsed-time budget")
        model_output = ConsultantModelOutput.model_validate(
            response["structured_response"]
        )
        result = map_consultant_model_output(model_output, catalog=catalog)
        candidate_source_ids: tuple[UUID, ...] = ()
        candidate_files: dict[str, str] | None = None
        if result.candidate_publication is not None:
            raw_state = await runtime.raw_state(document_id)
            checked_payload = raw_state.get("checked_candidate")
            if checked_payload is None:
                raise ConsultantVerificationError(
                    "candidate publication has no checked candidate receipt"
                )
            checked = CheckedCandidateReceipt.model_validate(checked_payload)
            if checked.run_id != run_id:
                raise ConsultantVerificationError(
                    "candidate publication belongs to another consultant run"
                )
            publication = result.candidate_publication
            if (
                checked.candidate_revision != publication.candidate_revision
                or checked.resource_digest != publication.revision_digest
                or tuple(action.action_id for action in checked.changeset.actions)
                != publication.action_ids
            ):
                raise ConsultantVerificationError(
                    "candidate publication does not exactly match the checked receipt"
                )
            if not set(checked.used_skill_ids) <= set(result.used_skill_ids):
                raise ConsultantVerificationError(
                    "candidate publication used Skills missing from final result"
                )
            candidate_files = _candidate_files_from_response(response, workspace)
            current_source_ids = tuple(
                source.source_id
                for source in all_sources
                if (
                    source.processing_status is SourceProcessingStatus.COMMITTED
                    and source.validity.value == "current"
                )
            )
            validate_checked_candidate(
                checked,
                current_run_id=run_id,
                current_baseline_revision=snapshot.revision,
                current_document=snapshot.approved_document,
                current_files=candidate_files,
                current_source_ids=current_source_ids,
            )
            candidate_source_ids = checked.changeset.source_ids
        if not runtime_context.context_receipts:
            raise ValueError("consultant run emitted no context-selection receipt")
        for receipt in runtime_context.context_receipts:
            verify_context_selection(execution, receipt)
        verify_model_attempts(execution, callback.receipts)
        referenced_source_ids = tuple(
            dict.fromkeys(
                source_id
                for basis in result.analysis_bases()
                for source_id in basis.source_ids
                if source_id is not None
            )
        )
        referenced_source_ids = tuple(
            dict.fromkeys((*referenced_source_ids, *candidate_source_ids))
        )
        evidence = tuple(
            [
                await runtime.get_source(document_id, referenced_source_id)
                for referenced_source_id in referenced_source_ids
            ]
        )
        known_work_ids = tuple(UUID(key) for key in snapshot.interview_work)
        document = snapshot.approved_document
        known_subject_ids = (
            *known_work_ids,
            *(item.duty_id for item in document.duties),
            *(item.task_id for item in document.tasks),
            *(item.item_id for item in document.opks),
        )
        verify_consultant_result(
            result,
            execution=execution,
            document_id=document_id,
            selected_skill_ids=CONSULTANT_SKILL_IDS,
            loaded_skill_ids=agent.skill_backend.loaded_skill_ids,
            employee_sources=evidence,
            known_work_ids=known_work_ids,
            known_subject_ids=known_subject_ids,
        )
        commit = VerifiedConsultantCommit(
            run_id=run_id,
            answer_source_id=source_id,
            started_at=latest.started_at,
            completed_at=datetime.now(UTC),
            execution_evidence=_run_execution_evidence(
                execution,
                runtime_context=runtime_context,
                callback=callback,
            ),
            result=result,
        )
        return await runtime.commit_verified_consultant_result(
            document_id=document_id,
            expected_revision=snapshot.revision,
            commit=commit,
            candidate_files=candidate_files,
        )
    except BaseException as error:
        if isinstance(error, (KeyboardInterrupt, SystemExit, asyncio.CancelledError)):
            raise
        try:
            if callback is not None:
                await callback.close_open_attempts(error)
            await runtime.mark_consultant_run_failed(
                document_id=document_id,
                run_id=run_id,
                error_code=classify_consultant_failure(error),
                execution_evidence=_run_execution_evidence(
                    execution,
                    runtime_context=runtime_context,
                    callback=callback,
                ),
            )
        except Exception:
            # Preserve the original model/verification/commit failure. A later replay
            # reconciles a still-source-saved run from the durable checkpoint.
            pass
        raise


class ConsultantTurnProcessor:
    """Process-local duplicate suppression over durable LangGraph run state."""

    def __init__(
        self,
        config: Settings,
        *,
        model_factory: Callable[[ResolvedExecution], Any],
    ) -> None:
        self.config = config
        self.model_factory = model_factory
        self._claims: set[tuple[UUID, UUID]] = set()
        self._lock = asyncio.Lock()

    async def claim(self, document_id: UUID, run_id: UUID) -> bool:
        key = (document_id, run_id)
        async with self._lock:
            if key in self._claims:
                return False
            self._claims.add(key)
            return True

    async def process_claimed(
        self,
        document_id: UUID,
        run_id: UUID,
        source_id: UUID,
        runtime: PostgresConsultantRuntime | None = None,
    ) -> None:
        try:
            execution = build_configured_execution(self.config)
            if runtime is not None:
                await self._execute_with_runtime(
                    runtime,
                    document_id=document_id,
                    run_id=run_id,
                    source_id=source_id,
                    execution=execution,
                )
            else:
                async with open_postgres_consultant_runtime(
                    self.config.database_url
                ) as opened_runtime:
                    await self._execute_with_runtime(
                        opened_runtime,
                        document_id=document_id,
                        run_id=run_id,
                        source_id=source_id,
                        execution=execution,
                    )
        except Exception as error:
            logger.warning(
                "consultant background run failed document_id=%s run_id=%s type=%s",
                document_id,
                run_id,
                type(error).__name__,
            )
        finally:
            async with self._lock:
                self._claims.discard((document_id, run_id))

    async def _execute_with_runtime(
        self,
        runtime: PostgresConsultantRuntime,
        *,
        document_id: UUID,
        run_id: UUID,
        source_id: UUID,
        execution: ResolvedExecution,
    ) -> None:
        try:
            model = self.model_factory(execution)
        except Exception as error:
            await runtime.mark_consultant_run_failed(
                document_id=document_id,
                run_id=run_id,
                error_code=classify_consultant_failure(error),
                execution_evidence=_run_execution_evidence(execution),
            )
            raise
        await execute_admitted_consultant_turn(
            runtime=runtime,
            document_id=document_id,
            run_id=run_id,
            source_id=source_id,
            execution=execution,
            model=model,
        )


__all__ = [
    "ConsultantTurnProcessor",
    "build_configured_execution",
    "execute_admitted_consultant_turn",
]
