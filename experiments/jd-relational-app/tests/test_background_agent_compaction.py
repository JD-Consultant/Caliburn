"""Real B1/B2 graph compaction lifecycle with canonical sources and no provider."""

from copy import deepcopy
import json
from typing import Any
from uuid import uuid4

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from pydantic import Field

from caliburn_memory import (
    CaseArtifact,
    CaseMaintenanceSession,
    CaseMaintenanceWorkflow,
    MemoryArtifacts,
    UnderstandingMaintenanceSession,
    UnderstandingMaintenanceWorkflow,
    WorkUnderstandingArtifact,
)
from jd_relational.continuation_compaction import (
    B1_COMPACTION_PROFILE,
    B2_COMPACTION_PROFILE,
    SUMMARY_SYSTEM_PROMPT,
    ContinuationCompactionMiddleware,
)
from jd_relational.extraction_app import ExtractionSourceAdapter
from jd_relational.memory_sources import MemorySourceReader

from test_chat_history import native  # noqa: F401
from test_conversation_sources import service as source_service
from test_interview_window_source import settled


class RoleAwareModel(BaseChatModel):
    """One synthetic boundary for both main and summary requests."""

    main_replies: list[Any]
    summary_replies: list[Any]
    main_requests: list[Any] = Field(default_factory=list)
    summary_requests: list[Any] = Field(default_factory=list)

    @property
    def _llm_type(self):
        return "background-compaction-offline-test"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        is_summary = bool(
            messages
            and isinstance(messages[0], SystemMessage)
            and messages[0].content == SUMMARY_SYSTEM_PROMPT
        )
        target = self.summary_requests if is_summary else self.main_requests
        replies = self.summary_replies if is_summary else self.main_replies
        target.append(deepcopy(messages))
        if not replies:
            raise AssertionError("synthetic model received an unexpected request")
        reply = replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return ChatResult(generations=[ChatGeneration(message=reply)])


def _call(name: str, arguments: dict[str, Any], identity: str) -> AIMessage:
    return AIMessage(
        "",
        id=f"message-{identity}",
        tool_calls=[{
            "name": name,
            "args": arguments,
            "id": identity,
            "type": "tool_call",
        }],
        response_metadata={"status": "completed", "finish_reason": "tool_calls"},
    )


def _completed(text: str, identity: str) -> AIMessage:
    return AIMessage(
        text,
        id=identity,
        response_metadata={"status": "completed", "finish_reason": "stop"},
    )


def _always_over_trigger(_request, _view) -> int:
    return 100


def _two_exchange_source(native, *, first_text: str, second_text: str):
    first = settled(
        native,
        [AIMessage(id=f"source-ai-{uuid4()}", content="請繼續說明。")],
        text=first_text,
    )
    second = settled(
        native,
        [AIMessage(id=f"source-ai-{uuid4()}", content="謝謝，資料完整。")],
        text=second_text,
    )
    sources = source_service(native)
    document_id = native[2]
    batch = sources.capture_window(
        document_id,
        first_run_id=first.record.run_id,
        last_run_id=second.record.run_id,
    )
    expected = {
        "second_window_reference": sources.capture_window(
            document_id,
            first_run_id=second.record.run_id,
            last_run_id=second.record.run_id,
        ),
        "source_references": (
            sources.capture(document_id, first.record.run_id).source_ref,
            sources.capture(document_id, second.record.run_id).source_ref,
        ),
        "second_run_id": second.record.run_id,
        "second_last_message_id": second.messages[-1].id,
    }
    return sources, ExtractionSourceAdapter(sources, document_id), batch, expected


def _one_exchange_source(native, *, text: str):
    turn = settled(
        native,
        [AIMessage(id=f"source-ai-{uuid4()}", content="謝謝，資料完整。")],
        text=text,
    )
    sources = source_service(native)
    document_id = native[2]
    batch = sources.capture_window(
        document_id,
        first_run_id=turn.record.run_id,
        last_run_id=turn.record.run_id,
    )
    return sources, ExtractionSourceAdapter(sources, document_id), batch


def _case_workflow(reader, model, *, max_chars: int, context_chars: int):
    artifacts = MemoryArtifacts(
        InMemoryStore(),
        reader.document_id,
        source=MemorySourceReader(
            reader.service,
            reader.document_id,
            window_references=True,
        ),
    )
    session = CaseMaintenanceSession(artifacts)
    middleware = ContinuationCompactionMiddleware(
        summary_model=model,
        profile=B1_COMPACTION_PROFILE.model_copy(update={
            "trigger_input_tokens": 1,
            "keep_messages": 1,
        }),
        token_counter=_always_over_trigger,
    )
    workflow = CaseMaintenanceWorkflow(
        reader,
        session,
        model,
        InMemorySaver(),
        max_model_steps=12,
        max_tool_calls=8,
        max_chars=max_chars,
        context_chars=context_chars,
        max_windows=4,
        context_middleware=middleware,
    )
    return artifacts, session, workflow


def _request_summary(request) -> AIMessage:
    summaries = [
        message
        for message in request
        if isinstance(message, AIMessage)
        and isinstance(message.id, str)
        and message.id.startswith("continuation-summary:")
    ]
    assert len(summaries) == 1
    return summaries[0]


def _only_human(request) -> HumanMessage:
    humans = [message for message in request if isinstance(message, HumanMessage)]
    assert len(humans) == 1
    return humans[0]


def _user_text_from_window(reader, reference: str) -> str:
    offset = 0
    fragments: list[str] = []
    while True:
        page = reader.read(reference, offset)
        fragments.extend(
            segment["text"] for segment in page["segments"]
            if segment["role"] == "user"
        )
        if page["next_offset"] is None:
            return "".join(fragments)
        offset = page["next_offset"]


def _user_text_from_source(reader, reference: str) -> str:
    offset = 0
    fragments: list[str] = []
    while True:
        page = reader.read_source_page(reference, offset)
        fragments.extend(
            segment.text for segment in page.segments if segment.role == "user"
        )
        if page.next_offset is None:
            return "".join(fragments)
        offset = page.next_offset


def test_b1_compacts_only_the_processed_window_and_preserves_canonical_sources(native):
    first_text = "第一段：本人先完成設備異常初判。"
    second_text = "第二段：本人再把異常紀錄交給主管。"
    _sources, reader, batch, expected = _two_exchange_source(
        native,
        first_text=first_text,
        second_text=second_text,
    )
    model = RoleAwareModel(
        main_replies=[
            _completed("第一個來源窗口已處理。", "b1-first-window-done"),
            _call("finish_case_maintenance", {}, "b1-finish"),
            _completed("案例整理完成。", "b1-done"),
        ],
        summary_replies=[
            _completed("第一段已完成判讀，準備處理下一個窗口。", "b1-summary"),
        ],
    )
    _artifacts, session, workflow = _case_workflow(
        reader,
        model,
        max_chars=36,
        context_chars=10,
    )

    result = workflow.start(
        batch,
        base_publication_revision=0,
        base_version=None,
    )

    assert len(model.summary_requests) == 1
    assert "第一段" in model.summary_requests[0][-1].content
    assert "第二段" not in model.summary_requests[0][-1].content
    second_request = model.main_requests[1]
    summary = _request_summary(second_request)
    assert "對話延續摘要" in summary.content
    second_payload_message = next(
        message for message in second_request if isinstance(message, HumanMessage)
    )
    second_payload = json.loads(second_payload_message.content)
    assert second_payload["WINDOW"] == {"position": 2, "count": 2, "final": True}
    second_window = second_payload["NEW_SOURCE"]["window"]
    assert second_window["turns"] == [{
        "input_id": expected["second_run_id"],
        "status": "completed",
        "answer_succeeded": True,
        "first": expected["second_run_id"],
        "last": expected["second_last_message_id"],
    }]
    assert [
        segment for segment in second_window["segments"]
        if segment["role"] == "user"
    ] == [{
        "message_id": expected["second_run_id"],
        "role": "user",
        "text": second_text,
        "text_offset": 0,
    }]
    second_evidence = second_payload["NEW_SOURCE"]["evidence"]
    assert second_evidence["order"] == "oldest_to_newest"
    assert [block["evidence_key"] for block in second_evidence["blocks"]] == ["E2"]
    assert [
        message
        for block in second_evidence["blocks"]
        for message in block["messages"]
        if message["role"] == "user"
    ] == [{"role": "user", "text": second_text}]
    summary_position = second_request.index(summary)
    assert summary_position == 1  # Static role instructions remain first.
    assert not any(
        "第一段" in str(message.content)
        for message in second_request[summary_position + 1:]
    )

    canonical = result["messages"]
    canonical_humans = [
        message for message in canonical if isinstance(message, HumanMessage)
    ]
    request_humans = [
        next(message for message in request if isinstance(message, HumanMessage))
        for request in model.main_requests[:2]
    ]
    assert [message.model_dump() for message in canonical_humans] == [
        message.model_dump() for message in request_humans
    ]
    assert any("第一段" in str(message.content) for message in canonical)
    assert any("第二段" in str(message.content) for message in canonical)
    assert not any(
        isinstance(message.id, str)
        and message.id.startswith("continuation-summary:")
        for message in canonical
    )
    assert result["continuation_compaction"] is not None

    window_references = [
        item["source_reference"] for item in result["source_windows"]
    ]
    assert len(window_references) == 2
    assert window_references[1] == expected["second_window_reference"]
    assert [
        _user_text_from_window(reader, reference)
        for reference in window_references
    ] == [first_text, second_text]

    stage = session.load(result["case_stage"])
    assert stage.completed and stage.outcome == "no_op"
    assert [item.evidence_key for item in stage.evidence] == ["E1", "E2"]
    assert [
        item.source_reference for item in stage.evidence
    ] == list(expected["source_references"])
    assert [
        _user_text_from_source(reader, item.source_reference)
        for item in stage.evidence
    ] == [first_text, second_text]
    checkpointed_stage = json.dumps(stage.to_dict(), ensure_ascii=False)
    assert first_text not in checkpointed_stage and second_text not in checkpointed_stage


def test_b1_single_window_never_compacts_even_across_multiple_tool_waves(native):
    source_text = "目前完整批次：本人負責設備告警初判。"
    _sources, reader, batch = _one_exchange_source(native, text=source_text)
    model = RoleAwareModel(
        main_replies=[
            _call("create_case", {
                "content": "## 設備告警初判\n本人負責設備告警初判。",
                "route_note": "設備告警初判",
                "evidence_keys": ["E1"],
            }, "b1-create"),
            _call("finish_case_maintenance", {}, "b1-finish"),
            _completed("案例整理完成。", "b1-done"),
        ],
        summary_replies=[],
    )
    _artifacts, session, workflow = _case_workflow(
        reader,
        model,
        max_chars=36,
        context_chars=10,
    )

    result = workflow.start(
        batch,
        base_publication_revision=0,
        base_version=None,
    )

    assert model.summary_requests == []
    assert result["continuation_compaction"] is None
    assert sum(isinstance(message, ToolMessage) for message in result["messages"]) == 2
    assert any(source_text in str(message.content) for message in result["messages"])
    stage = session.load(result["case_stage"])
    assert stage.completed and stage.outcome == "changed"
    assert _user_text_from_source(
        reader,
        stage.evidence[0].source_reference,
    ) == source_text


def _completed_b1_stage(native):
    base_text = "基準原話：本人先完成設備異常初判。"
    batch_text = "本批補充：本人也把異常紀錄交給主管。"
    sources, reader, through, _expected = _two_exchange_source(
        native,
        first_text=base_text,
        second_text=batch_text,
    )
    records = reader.history_exchanges(through).exchanges
    assert len(records) == 2
    base_source, batch_source = (
        records[0].source_reference,
        records[1].source_reference,
    )
    second_run_id = records[1].messages[-1].message_id
    batch_window = sources.capture_window(
        reader.document_id,
        first_run_id=second_run_id,
        last_run_id=second_run_id,
    )
    artifacts = MemoryArtifacts(
        InMemoryStore(),
        reader.document_id,
        source=MemorySourceReader(
            sources,
            reader.document_id,
            window_references=True,
        ),
    )
    case_id, understanding_id = str(uuid4()), str(uuid4())
    base_case_content = "## 設備異常處理\n本人先完成設備異常初判。"
    base_understanding_content = "本人穩定負責設備異常初判。"
    version = artifacts.save_bundle(
        base_publication_revision=0,
        evidence_through_reference=through,
        case_guide=(
            f"- [設備異常處理](/memory/cases/items/{case_id}.md) — 異常初判與交接"
        ),
        cases=(CaseArtifact(case_id, base_case_content, (base_source,)),),
        understanding_guide=(
            f"- [設備異常處理](/memory/understanding/items/{understanding_id}.md)"
        ),
        understandings=(WorkUnderstandingArtifact(
            understanding_id,
            base_understanding_content,
            (case_id,),
        ),),
    )
    case_session = CaseMaintenanceSession(artifacts)
    stage = case_session.open(
        base_publication_revision=1,
        base_version=version,
        source_reference=batch_window,
    )
    for index, exchange in enumerate(reader.history_exchanges(batch_window).exchanges):
        page = reader.read_source_page(exchange.source_reference, 0)
        stage, _evidence = case_session.register_evidence(
            stage,
            exchange,
            order_key=(0, index, 0),
            next_offset=page.next_offset,
        )
    stage, _case = case_session.observe_case(stage, case_id)
    stage = case_session.revise_case(
        stage,
        case_id=case_id,
        diff=(
            "@@\n"
            "-本人先完成設備異常初判。\n"
            "+本人先完成設備異常初判，也把異常紀錄交給主管。"
        ),
        route_note=None,
        add_evidence_keys=["E2"],
        remove_evidence_keys=[],
    )
    stage = case_session.finish(stage)
    return {
        "reader": reader,
        "artifacts": artifacts,
        "case_session": case_session,
        "case_stage": stage,
        "case_id": case_id,
        "understanding_id": understanding_id,
        "version": version,
        "base_source": base_source,
        "base_case_content": base_case_content,
        "base_understanding_content": base_understanding_content,
    }


def test_b2_restores_same_attempt_compaction_and_new_attempt_starts_clean(native):
    built = _completed_b1_stage(native)
    case_id = built["case_id"]
    understanding_id = built["understanding_id"]
    first_summary = "first-attempt-summary-marker：已讀案例，仍需核對工作理解。"
    model = RoleAwareModel(
        main_replies=[
            _call("read_case", {"case_id": case_id}, "first-read-case"),
            _completed("案例已讀，繼續整理。", "first-progress"),
            _completed("摘要已落盤，繼續核對工作理解。", "first-checkpointed-progress"),
            _call("read_work_understanding", {
                "understanding_id": understanding_id,
            }, "first-read-understanding"),
            RuntimeError("synthetic B2 transport failure"),
            _call("revalidate_work_understanding", {
                "understanding_id": understanding_id,
                "supporting_case_ids": [case_id],
            }, "first-revalidate"),
            _call("finish_understanding_maintenance", {}, "first-finish"),
            _completed("工作理解整理完成。", "first-done"),
            _call("read_case", {"case_id": case_id}, "fresh-read-case"),
            _call("read_work_understanding", {
                "understanding_id": understanding_id,
            }, "fresh-read-understanding"),
            _call("revalidate_work_understanding", {
                "understanding_id": understanding_id,
                "supporting_case_ids": [case_id],
            }, "fresh-revalidate"),
            _call("finish_understanding_maintenance", {}, "fresh-finish"),
            _completed("新 attempt 工作理解整理完成。", "fresh-done"),
        ],
        summary_replies=[
            _completed(first_summary, "summary-1"),
            *(
                _completed(f"same-boundary-summary-{index}", f"summary-{index}")
                for index in range(2, 9)
            ),
        ],
    )
    session = UnderstandingMaintenanceSession(
        built["artifacts"],
        built["case_session"],
    )
    middleware = ContinuationCompactionMiddleware(
        summary_model=model,
        profile=B2_COMPACTION_PROFILE.model_copy(update={
            "trigger_input_tokens": 1,
            "keep_messages": 1,
        }),
        token_counter=_always_over_trigger,
    )
    workflow = UnderstandingMaintenanceWorkflow(
        built["reader"],
        session,
        model,
        InMemorySaver(),
        max_model_steps=20,
        max_tool_calls=12,
        max_completion_corrections=3,
        context_middleware=middleware,
    )
    first_attempt = str(uuid4())

    with pytest.raises(RuntimeError, match="synthetic B2 transport failure"):
        workflow.run_attempt(
            built["case_stage"],
            case_attempt_id=first_attempt,
        )

    initial_task = deepcopy(_only_human(model.main_requests[0]))
    for request in model.main_requests:
        assert _only_human(request).model_dump() == initial_task.model_dump()

    saved = workflow.graph.get_state(workflow._attempt_config(first_attempt)).values
    assert saved["continuation_compaction"] is not None
    assert saved["continuation_compaction"]["summary_text"] == first_summary
    assert sum(isinstance(message, HumanMessage) for message in saved["messages"]) == 1
    assert isinstance(saved["messages"][0], HumanMessage)
    assert saved["messages"][0].model_dump() == initial_task.model_dump()
    assert not any(
        isinstance(message.id, str)
        and message.id.startswith("continuation-summary:")
        for message in saved["messages"]
    )
    resume_request_index = len(model.main_requests)
    assert first_summary in model.summary_requests[-1][-1].content

    resumed = workflow.run_attempt(
        built["case_stage"],
        case_attempt_id=first_attempt,
    )

    assert resumed["case_attempt_id"] == first_attempt
    assert resumed["messages"][0].model_dump() == initial_task.model_dump()
    assert sum(isinstance(message, HumanMessage) for message in resumed["messages"]) == 1
    for request in model.main_requests:
        assert _only_human(request).model_dump() == initial_task.model_dump()
    resumed_saved = workflow.graph.get_state(
        workflow._attempt_config(first_attempt)
    ).values
    assert resumed_saved["messages"][0].model_dump() == initial_task.model_dump()
    assert sum(
        isinstance(message, HumanMessage)
        for message in resumed_saved["messages"]
    ) == 1
    first_resume_request = model.main_requests[resume_request_index]
    resume_task = next(
        message for message in first_resume_request if isinstance(message, HumanMessage)
    )
    assert isinstance(first_resume_request[0], SystemMessage)
    assert first_resume_request[1].model_dump() == initial_task.model_dump()
    assert resume_task.model_dump() == initial_task.model_dump()
    assert "same-boundary-summary-2" in _request_summary(first_resume_request).content
    final_resume_task = next(
        message for message in model.main_requests[-1]
        if isinstance(message, HumanMessage)
    )
    assert model.main_requests[-1][1].model_dump() == initial_task.model_dump()
    assert final_resume_task.model_dump() == initial_task.model_dump()

    fresh_attempt = str(uuid4())
    fresh_main_index = len(model.main_requests)
    fresh_summary_index = len(model.summary_requests)
    fresh = workflow.run_attempt(
        built["case_stage"],
        case_attempt_id=fresh_attempt,
    )

    assert fresh["case_attempt_id"] == fresh_attempt
    first_fresh_request = model.main_requests[fresh_main_index]
    fresh_task = next(
        message for message in first_fresh_request if isinstance(message, HumanMessage)
    )
    assert json.loads(fresh_task.content) == json.loads(initial_task.content)
    assert not any(
        isinstance(message.id, str)
        and message.id.startswith("continuation-summary:")
        for message in first_fresh_request
    )
    assert not any(
        isinstance(message, (AIMessage, ToolMessage))
        for message in first_fresh_request
    )
    assert first_summary not in "".join(
        str(message.content) for message in first_fresh_request
    )
    first_fresh_summary_request = model.summary_requests[fresh_summary_index]
    assert first_summary not in first_fresh_summary_request[-1].content
    _prompt, fresh_summary_json = first_fresh_summary_request[-1].content.split(
        "\n", maxsplit=1,
    )
    fresh_summary_payload = json.loads(fresh_summary_json)
    assert fresh_summary_payload["existing_summary"] is None

    base_case = built["artifacts"].case(built["version"], case_id)
    base_understanding = built["artifacts"].understanding(
        built["version"], understanding_id,
    )
    assert (
        base_case.content,
        base_case.source_references,
    ) == (built["base_case_content"], (built["base_source"],))
    assert base_understanding.content == built["base_understanding_content"]
    assert [binding.case_id for binding in base_understanding.case_bindings] == [case_id]
