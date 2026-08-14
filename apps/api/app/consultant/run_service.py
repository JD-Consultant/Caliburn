"""Production assembly for one source-first professional-consultant run."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from langchain_core.messages import HumanMessage

from app.adapters.langgraph.postgres import (
    PostgresConsultantRuntime,
    open_postgres_consultant_runtime,
)
from app.config import Settings
from app.consultant.agent import build_professional_consultant_agent
from app.consultant.context import (
    ConsultantAgentRuntimeContext,
    ConsultantContextMiddleware,
    ContextRequest,
    DocumentSourceLookup,
    build_source_lookup_tools,
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
    RunReceipt,
    RunExecutionEvidence,
    RunStatus,
    SourceProcessingStatus,
)
from app.consultant.verification import (
    verify_consultant_result,
    verify_context_selection,
    verify_model_attempts,
)


SOURCE_TOOL_IDS = (
    "source_by_id",
    "source_lineage",
    "source_lexical_search",
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
        allowed_tool_ids=("read_file", *SOURCE_TOOL_IDS),
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
        source_tools = build_source_lookup_tools(
            DocumentSourceLookup(runtime),
            document_id=document_id,
        )
        agent = agent_factory(
            model=model,
            execution=execution,
            selected_skill_ids=CONSULTANT_SKILL_IDS,
            source_tools=source_tools,
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
                            content=f"[employee source {source_id}]",
                            additional_kwargs={
                                "employee_source_id": str(source_id),
                            },
                        )
                    ]
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
        result = map_consultant_model_output(model_output)
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
            )
        )
        evidence = tuple(
            [
                await runtime.get_source(document_id, referenced_source_id)
                for referenced_source_id in referenced_source_ids
            ]
        )
        verify_consultant_result(
            result,
            execution=execution,
            document_id=document_id,
            selected_skill_ids=CONSULTANT_SKILL_IDS,
            loaded_skill_ids=agent.skill_backend.loaded_skill_ids,
            employee_sources=evidence,
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
