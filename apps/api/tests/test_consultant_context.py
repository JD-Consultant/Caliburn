from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.consultant.context import (
    ContextRequest,
    ConsultantContextMiddleware,
    DocumentSourceLookup,
    SourceLookupMode,
    build_consultant_context,
)
from app.consultant.model_runtime import (
    ConsultantModelProfile,
    RunPolicy,
    resolve_execution,
)
from app.consultant.state import (
    ApprovedDuty,
    ApprovedJobDocument,
    ApprovedTask,
    EmployeeSource,
    EmployeeSourceKind,
    SourceProcessingStatus,
    SourceValidity,
    UnderstandingItem,
    initial_thread_state,
)
from app.consultant.views import (
    ConsultantTurnProjection,
    document_review_projection_from_workspace,
    snapshot_from_state,
)
from app.consultant.workspace_review import WorkspaceReviewProjection
from app.consultant.workspace_state import (
    WorkspaceDiagnostic,
    WorkspaceValidationStatus,
)
from app.consultant.workspace_validation import WorkspaceValidationSummary


DOCUMENT_ID = UUID("00000000-0000-0000-0000-000000000701")
SOURCE_ID = UUID("00000000-0000-0000-0000-000000000702")
RUN_ID = UUID("00000000-0000-0000-0000-000000000703")


class InMemorySourceRuntime:
    def __init__(self, sources: tuple[EmployeeSource, ...]) -> None:
        self.sources = sources
        self.get_calls: list[UUID] = []

    async def get_source(self, document_id: UUID, source_id: UUID) -> EmployeeSource:
        assert document_id == DOCUMENT_ID
        self.get_calls.append(source_id)
        for source in self.sources:
            if source.source_id == source_id:
                return source
        raise KeyError(source_id)

    async def list_sources(self, document_id: UUID) -> tuple[EmployeeSource, ...]:
        assert document_id == DOCUMENT_ID
        return self.sources


def _document() -> ApprovedJobDocument:
    duty_id = uuid4()
    return ApprovedJobDocument(
        document_id=DOCUMENT_ID,
        job_title="採購管理專員",
        work_description="管理物料供應並彙整採購資訊",
        duties=(
            ApprovedDuty(
                duty_id=duty_id,
                statement="物料供應管理",
                display_order=0,
            ),
        ),
        tasks=(
            ApprovedTask(
                task_id=uuid4(),
                duty_id=duty_id,
                statement="檢查缺料並安排採購",
                action="檢查並安排",
                object="缺料與採購",
                purpose_result="確保物料按期供應",
                display_order=0,
            ),
        ),
    )


def _source(
    *,
    source_id: UUID = SOURCE_ID,
    text: str = "我會先檢查缺料，再依交期安排採購。",
    validity: SourceValidity = SourceValidity.CURRENT,
    created_at: datetime | None = None,
) -> EmployeeSource:
    return EmployeeSource.pending(
        source_id=source_id,
        document_id=DOCUMENT_ID,
        kind=EmployeeSourceKind.EMPLOYEE_TURN,
        text=text,
    ).model_copy(
        update={
            "processing_status": SourceProcessingStatus.COMMITTED,
            "validity": validity,
            **({"created_at": created_at} if created_at is not None else {}),
        }
    )


def _execution(*, max_context_tokens: int = 24_000):
    return resolve_execution(
        ConsultantModelProfile(
            profile_id="primary-consultant",
            revision=1,
            requested_model="anthropic/claude-opus-5",
            provider_allowlist=("Anthropic",),
            max_output_tokens=4096,
        ),
        RunPolicy(
            policy_id="interactive-consultation",
            revision=1,
            run_kind="interactive_consultation",
            allowed_skill_ids=("task-boundary",),
            allowed_tool_ids=(
                "ls",
                "read_file",
                "grep",
                "write_file",
                "edit_file",
                "delete",
            ),
            max_context_tokens=max_context_tokens,
            max_model_calls=8,
            max_total_tool_calls=12,
            model_retry_count=0,
            tool_retry_count=0,
            max_elapsed_seconds=180,
            max_total_tokens=32_000,
            max_cost_usd=Decimal("2.00"),
        ),
    )


def _snapshot(document: ApprovedJobDocument, source: EmployeeSource):
    state = initial_thread_state(document.document_id)
    state.update(
        {
            "revision": 4,
            "source_count": 1,
            "latest_source_id": str(source.source_id),
            "approved_document": document.model_dump(mode="json"),
        }
    )
    snapshot = snapshot_from_state(state)
    review = document_review_projection_from_workspace(
        state,
        workspace_generation=1,
        validation_status=WorkspaceValidationStatus.VALID,
        workspace_review=WorkspaceReviewProjection(workspace_digest="a" * 64),
    )
    return snapshot.model_copy(update={"document_review": review})


@pytest.mark.asyncio
async def test_context_keeps_current_employee_turn_and_compact_workspace_orientation() -> None:
    document = _document()
    source = _source()
    runtime = InMemorySourceRuntime((source,))
    bundle = await build_consultant_context(
        runtime=runtime,  # type: ignore[arg-type]
        snapshot=_snapshot(document, source),
        execution=_execution(),
        request=ContextRequest(
            run_id=RUN_ID,
            current_source_id=source.source_id,
            current_source_handle="source-001",
            selected_skill_ids=("task-boundary",),
        ),
    )

    assert len(bundle.messages) == 1
    message = bundle.messages[0]
    assert isinstance(message, HumanMessage)
    assert message.content == source.text
    assert message.additional_kwargs == {"employee_source_id": str(source.source_id)}
    assert bundle.receipt.loaded_sources[0].source_id == source.source_id
    assert bundle.receipt.loaded_sources[0].reason.value == "current_input"

    prompt = bundle.system_prompt
    assert "<global_orientation>" in prompt
    assert "<revisable_understanding>" in prompt
    assert "<visible_gaps>" in prompt
    assert "<progress>" in prompt
    assert "<workspace_index>" in prompt
    assert "/skills" in prompt
    assert "/sources" in prompt
    assert "/approved" in prompt
    assert "/review" in prompt
    assert "/sources/current/source-001.txt" in prompt
    assert "already supplied as the current HumanMessage" in prompt
    assert "do not reread that path" in prompt
    assert "only when their details are needed" in prompt
    assert "do not reread a path whose result is still in context" in prompt
    assert "Read the exact approved and review index paths directly" not in prompt
    assert '"approved_index_path":"/approved/index.json"' in prompt
    assert '"review_index_path":"/review/index.json"' in prompt
    assert '"workspace_root":"/workspace"' in prompt
    candidate_root_field = '"candidate_' + 'root"'
    candidate_path = "/" + "candidate/"
    assert candidate_root_field not in prompt
    assert candidate_path not in prompt
    assert document.work_description not in prompt
    assert str(source.source_id) not in prompt


@pytest.mark.asyncio
async def test_context_injects_only_compact_workspace_validation_navigation() -> None:
    document = _document()
    source = _source()
    runtime = InMemorySourceRuntime((source,))
    summary = WorkspaceValidationSummary(
        generation=4,
        status=WorkspaceValidationStatus.INVALID,
        resource_digest="a" * 64,
        diagnostics=(
            WorkspaceDiagnostic(
                code="json-syntax",
                path="/workspace/tasks/task-001.json",
                message="Resource is not valid JSON.",
            ),
        ),
    )

    bundle = await build_consultant_context(
        runtime=runtime,  # type: ignore[arg-type]
        snapshot=_snapshot(document, source),
        execution=_execution(),
        request=ContextRequest(
            run_id=RUN_ID,
            current_source_id=source.source_id,
            current_source_handle="source-001",
            selected_skill_ids=("task-boundary",),
        ),
        workspace_validation=summary,
    )

    prompt = bundle.system_prompt
    assert '<workspace_validation>{"diagnostics":[' in prompt
    assert '"generation":4' in prompt
    assert '"status":"invalid"' in prompt
    assert '"workspace_root":"/workspace"' in prompt
    assert '"review_root":"/review"' in prompt
    assert "json-syntax" in prompt
    assert "/workspace/tasks/task-001.json" in prompt
    assert summary.resource_digest not in prompt
    assert document.work_description not in prompt


@pytest.mark.asyncio
async def test_valid_workspace_status_is_trusted_without_becoming_a_completion_signal() -> None:
    document = _document()
    source = _source()
    summary = WorkspaceValidationSummary(
        generation=5,
        status=WorkspaceValidationStatus.VALID,
        resource_digest="b" * 64,
        diagnostics=(),
    )

    bundle = await build_consultant_context(
        runtime=InMemorySourceRuntime((source,)),  # type: ignore[arg-type]
        snapshot=_snapshot(document, source),
        execution=_execution(),
        request=ContextRequest(
            run_id=RUN_ID,
            current_source_id=source.source_id,
            current_source_handle="source-001",
            selected_skill_ids=("task-boundary",),
        ),
        workspace_validation=summary,
    )

    prompt = bundle.system_prompt
    assert "application-owned validation result" in prompt
    assert "do not reread files merely to reconfirm it" in prompt
    assert "valid does not mean the current employee turn was already processed" in prompt


@pytest.mark.asyncio
async def test_context_rejects_superseded_current_employee_turn() -> None:
    document = _document()
    source = _source(validity=SourceValidity.SUPERSEDED)
    with pytest.raises(ValueError, match="superseded"):
        await build_consultant_context(
            runtime=InMemorySourceRuntime((source,)),  # type: ignore[arg-type]
            snapshot=_snapshot(document, source),
            execution=_execution(),
            request=ContextRequest(
                run_id=RUN_ID,
                current_source_id=source.source_id,
                current_source_handle="source-001",
                selected_skill_ids=("task-boundary",),
            ),
        )


@pytest.mark.asyncio
async def test_context_keeps_ordinary_correction_as_immutable_recent_dialogue() -> None:
    started = datetime(2026, 8, 27, tzinfo=UTC)
    older = _source(
        source_id=uuid4(),
        text="我每月整理採購需求。",
        created_at=started,
    )
    current = _source(
        text="我剛才說錯，是每週整理。",
        created_at=started + timedelta(minutes=1),
    )
    consultant_turn = ConsultantTurnProjection(
        run_id=uuid4(),
        answer_source_id=older.source_id,
        text="了解，目前先記為每月整理。",
        used_skill_ids=(),
    )
    understanding = UnderstandingItem(
        understanding_id=uuid4(),
        version_id=uuid4(),
        kind="work_story",
        text="員工會定期整理採購需求。",
        source_ids=(older.source_id,),
        created_revision=2,
    )
    snapshot = _snapshot(_document(), current).model_copy(
        update={
            "source_count": 2,
            "messages": (consultant_turn,),
            "understanding": {
                str(understanding.version_id): understanding.model_dump(mode="json")
            },
        }
    )
    runtime = InMemorySourceRuntime((older, current))

    bundle = await build_consultant_context(
        runtime=runtime,  # type: ignore[arg-type]
        snapshot=snapshot,
        execution=_execution(),
        request=ContextRequest(
            run_id=RUN_ID,
            current_source_id=current.source_id,
            current_source_handle="source-001",
            selected_skill_ids=("task-boundary",),
        ),
    )

    assert runtime.get_calls == [current.source_id]
    assert [item.source_id for item in bundle.receipt.loaded_sources] == [
        current.source_id
    ]
    assert [type(message) for message in bundle.messages] == [
        HumanMessage,
        AIMessage,
        HumanMessage,
    ]
    assert [message.content for message in bundle.messages] == [
        older.text,
        consultant_turn.text,
        current.text,
    ]
    assert sum(message.content == current.text for message in bundle.messages) == 1
    assert older.validity is SourceValidity.CURRENT
    assert older.superseded_by_source_id is None
    assert current.supersedes_source_id is None
    assert understanding.text in bundle.system_prompt


@pytest.mark.asyncio
async def test_context_drops_only_oldest_recent_turn_when_budget_requires() -> None:
    document = _document()
    started = datetime(2026, 8, 27, tzinfo=UTC)
    old_source = _source(
        source_id=uuid4(),
        text="較早員工回答：我先整理職務範圍與責任邊界。",
        created_at=started,
    )
    latest_source = _source(
        source_id=uuid4(),
        text="近期員工回答：缺料時由我判斷是否先採購。",
        created_at=started + timedelta(minutes=1),
    )
    source = _source(
        text="本輪補充：重大缺料會通知主管。",
        created_at=started + timedelta(minutes=2),
    )
    older = ConsultantTurnProjection(
        run_id=uuid4(),
        answer_source_id=old_source.source_id,
        text="較早顧問回覆：先整理職務範圍與責任邊界。",
        used_skill_ids=(),
    )
    latest = ConsultantTurnProjection(
        run_id=uuid4(),
        answer_source_id=latest_source.source_id,
        text="最新顧問回覆：請確認缺料處理的決策責任。",
        used_skill_ids=(),
    )
    one_turn = _snapshot(document, source).model_copy(update={"messages": (latest,)})
    two_turns = _snapshot(document, source).model_copy(
        update={"messages": (older, latest)}
    )
    one_turn_bundle = await build_consultant_context(
        runtime=InMemorySourceRuntime((latest_source, source)),  # type: ignore[arg-type]
        snapshot=one_turn,
        execution=_execution(),
        request=ContextRequest(
            run_id=RUN_ID,
            current_source_id=source.source_id,
            current_source_handle="source-001",
            selected_skill_ids=("task-boundary",),
        ),
    )
    two_turn_bundle = await build_consultant_context(
        runtime=InMemorySourceRuntime((old_source, latest_source, source)),  # type: ignore[arg-type]
        snapshot=two_turns,
        execution=_execution(),
        request=ContextRequest(
            run_id=RUN_ID,
            current_source_id=source.source_id,
            current_source_handle="source-001",
            selected_skill_ids=("task-boundary",),
        ),
    )
    budget = one_turn_bundle.receipt.total_input_tokens
    assert one_turn_bundle.receipt.total_input_tokens <= budget
    assert two_turn_bundle.receipt.total_input_tokens > budget

    compacted = await build_consultant_context(
        runtime=InMemorySourceRuntime((old_source, latest_source, source)),  # type: ignore[arg-type]
        snapshot=two_turns,
        execution=_execution(max_context_tokens=budget),
        request=ContextRequest(
            run_id=RUN_ID,
            current_source_id=source.source_id,
            current_source_handle="source-001",
            selected_skill_ids=("task-boundary",),
        ),
    )

    assert "recent_dialogue" in compacted.receipt.degraded_sections
    assert [message.content for message in compacted.messages] == [
        latest_source.text,
        latest.text,
        source.text,
    ]


@pytest.mark.asyncio
async def test_document_source_lookup_is_current_and_document_scoped() -> None:
    current = _source()
    superseded = _source().model_copy(
        update={"source_id": uuid4(), "validity": SourceValidity.SUPERSEDED}
    )
    runtime = InMemorySourceRuntime((current, superseded))
    lookup = DocumentSourceLookup(runtime)  # type: ignore[arg-type]

    assert await lookup.by_id(DOCUMENT_ID, current.source_id) == current
    assert await lookup.current_sources(DOCUMENT_ID) == (current,)
    assert await lookup.search(
        DOCUMENT_ID,
        query="缺料 採購",
        mode=SourceLookupMode.LEXICAL,
        limit=5,
    ) == (current,)


def test_context_middleware_is_an_async_only_model_boundary() -> None:
    assert hasattr(ConsultantContextMiddleware, "awrap_model_call")
    assert "wrap_model_call" not in ConsultantContextMiddleware.__dict__
