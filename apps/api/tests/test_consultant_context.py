from __future__ import annotations

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from langchain_core.messages import HumanMessage

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
    initial_thread_state,
)
from app.consultant.views import ConsultantTurnProjection, snapshot_from_state


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
                "check_candidate_document",
            ),
            max_context_tokens=max_context_tokens,
            max_model_calls=8,
            max_lookup_waves=2,
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
    return snapshot_from_state(state)


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
    assert "/pending" in prompt
    assert f"/candidate/{RUN_ID}" in prompt
    assert document.work_description not in prompt
    assert str(source.source_id) not in prompt


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
                selected_skill_ids=("task-boundary",),
            ),
        )


@pytest.mark.asyncio
async def test_context_does_not_fetch_or_claim_recent_source_payloads() -> None:
    current = _source()
    recent_sources = (
        _source(source_id=uuid4(), text="歷史來源一：曾經負責月度盤點。"),
        _source(source_id=uuid4(), text="歷史來源二：曾經協助供應商評估。"),
    )
    runtime = InMemorySourceRuntime((current, *recent_sources))

    bundle = await build_consultant_context(
        runtime=runtime,  # type: ignore[arg-type]
        snapshot=_snapshot(_document(), current),
        execution=_execution(),
        request=ContextRequest(
            run_id=RUN_ID,
            current_source_id=current.source_id,
            selected_skill_ids=("task-boundary",),
        ),
    )

    assert runtime.get_calls == [current.source_id]
    assert [item.source_id for item in bundle.receipt.loaded_sources] == [
        current.source_id
    ]
    assert "omitted_sources" not in bundle.receipt.model_dump(mode="json")
    assert bundle.messages[0].content == current.text
    assert recent_sources[0].text not in bundle.system_prompt
    assert recent_sources[1].text not in bundle.system_prompt


@pytest.mark.asyncio
async def test_context_drops_only_oldest_recent_turn_when_budget_requires() -> None:
    document = _document()
    source = _source()
    older = ConsultantTurnProjection(
        run_id=uuid4(),
        answer_source_id=uuid4(),
        text="較早顧問回覆：先整理職務範圍與責任邊界。",
        used_skill_ids=(),
    )
    latest = ConsultantTurnProjection(
        run_id=uuid4(),
        answer_source_id=uuid4(),
        text="最新顧問回覆：請確認缺料處理的決策責任。",
        used_skill_ids=(),
    )
    one_turn = _snapshot(document, source).model_copy(update={"messages": (latest,)})
    two_turns = _snapshot(document, source).model_copy(
        update={"messages": (older, latest)}
    )
    runtime = InMemorySourceRuntime((source,))

    one_turn_bundle = await build_consultant_context(
        runtime=runtime,  # type: ignore[arg-type]
        snapshot=one_turn,
        execution=_execution(),
        request=ContextRequest(
            run_id=RUN_ID,
            current_source_id=source.source_id,
            selected_skill_ids=("task-boundary",),
        ),
    )
    two_turn_bundle = await build_consultant_context(
        runtime=runtime,  # type: ignore[arg-type]
        snapshot=two_turns,
        execution=_execution(),
        request=ContextRequest(
            run_id=RUN_ID,
            current_source_id=source.source_id,
            selected_skill_ids=("task-boundary",),
        ),
    )
    budget = one_turn_bundle.receipt.total_input_tokens
    assert one_turn_bundle.receipt.total_input_tokens <= budget
    assert two_turn_bundle.receipt.total_input_tokens > budget

    compacted = await build_consultant_context(
        runtime=runtime,  # type: ignore[arg-type]
        snapshot=two_turns,
        execution=_execution(max_context_tokens=budget),
        request=ContextRequest(
            run_id=RUN_ID,
            current_source_id=source.source_id,
            selected_skill_ids=("task-boundary",),
        ),
    )

    assert "recent_consultant_turns" in compacted.receipt.degraded_sections
    assert latest.text in compacted.system_prompt
    assert older.text not in compacted.system_prompt
    assert compacted.messages[0].content == source.text


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
