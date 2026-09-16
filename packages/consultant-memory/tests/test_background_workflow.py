"""Deterministic B1 -> B2 -> bundle -> publication workflow; zero provider."""

from copy import deepcopy
from types import MethodType
from typing import Any
from uuid import uuid4

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from pydantic import Field
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from caliburn_memory import (
    BackgroundMemoryWorkflow,
    CaseMaintenanceSession,
    CaseMaintenanceWorkflow,
    MemoryArtifacts,
    PublicationStore,
    UnderstandingMaintenanceSession,
    UnderstandingMaintenanceWorkflow,
)
from test_extraction import WindowSource


class FixedModel(BaseChatModel):
    replies: list[Any]
    requests: list[Any] = Field(default_factory=list)

    @property
    def _llm_type(self):
        return "layered-background-offline-test"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.requests.append(deepcopy(messages))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return ChatResult(generations=[ChatGeneration(message=reply)])


def call(name, arguments, identity):
    return AIMessage("", id=f"message-{identity}", tool_calls=[{
        "name": name, "args": arguments, "id": identity, "type": "tool_call",
    }], response_metadata={"status": "completed", "finish_reason": "tool_calls"})


def done(identity):
    return AIMessage("完成。", id=identity,
                     response_metadata={"status": "completed", "finish_reason": "stop"})


def harness(*, changed: bool = True, b1_replies=None):
    source = WindowSource()
    evidence = source.evidence("evidence", [("user", "本人先確認告警並記錄結果。")])
    batch = source.window("batch", "固定 canonical 批次")
    window = source.window("window", "本人先確認告警並記錄結果。")
    source.set_window_evidence(window, evidence)
    source.set_history(evidence)
    source.plan(batch, [{"source_reference": window, "context_reference": None}])

    artifacts = MemoryArtifacts(InMemoryStore(), source.document_id, source=source)
    case_id, understanding_id = str(uuid4()), str(uuid4())
    if b1_replies is not None:
        case_replies = b1_replies
    elif changed:
        case_replies = [
            call("create_case", {
                "content": "## 告警處理\n本人先確認告警並記錄結果。",
                "route_note": "告警確認與結果記錄",
                "evidence_keys": ["E1"],
            }, "create-case"),
            call("finish_case_maintenance", {}, "finish-case"),
            done("case-done"),
        ]
    else:
        case_replies = [
            call("finish_case_maintenance", {}, "finish-case"),
            done("case-done"),
        ]
    case_model = FixedModel(replies=list(case_replies))
    case_session = CaseMaintenanceSession(artifacts, id_factory=lambda: case_id)
    case_workflow = CaseMaintenanceWorkflow(
        source, case_session, case_model, InMemorySaver(),
        max_model_steps=12, max_tool_calls=12,
    )

    understanding_replies = ([
        call("read_case", {"case_id": case_id}, "read-case"),
        call("create_work_understanding", {
            "content": "本人穩定負責告警確認與結果記錄。",
            "supporting_case_ids": [case_id],
            "route_note": "告警確認與結果記錄",
        }, "create-understanding"),
        call("finish_understanding_maintenance", {}, "finish-understanding"),
        done("understanding-done"),
    ] if changed else [
        call("finish_understanding_maintenance", {}, "finish-understanding"),
        done("understanding-done"),
    ])
    understanding_model = FixedModel(replies=understanding_replies)
    understanding_session = UnderstandingMaintenanceSession(
        artifacts, case_session, id_factory=lambda: understanding_id,
    )
    understanding_workflow = UnderstandingMaintenanceWorkflow(
        source, understanding_session, understanding_model, InMemorySaver(),
        max_model_steps=12, max_tool_calls=12,
    )

    engine = create_engine(
        "sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    publication = PublicationStore(engine, artifacts)
    publication.setup()
    workflow = BackgroundMemoryWorkflow(
        case_workflow, understanding_workflow, publication, InMemorySaver(),
        max_stale_retries=2,
    )
    return {
        "source": source,
        "batch": batch,
        "artifacts": artifacts,
        "case_id": case_id,
        "understanding_id": understanding_id,
        "case_model": case_model,
        "understanding_model": understanding_model,
        "publication": publication,
        "engine": engine,
        "workflow": workflow,
    }


@pytest.mark.parametrize("changed", [True, False])
def test_normal_layered_job_publishes_one_complete_bundle_and_replays_by_source(changed):
    built = harness(changed=changed)
    publication = built["publication"]
    observed_heads = []
    original_publish = publication.publish

    def recording_publish(_self, request):
        observed_heads.append(publication.current())
        return original_publish(request)

    publication.publish = MethodType(recording_publish, publication)
    try:
        result = built["workflow"].start(built["batch"])
        head = publication.current()
        manifest = built["artifacts"].bundle_manifest(head.memory)
        calls = (len(built["case_model"].requests),
                 len(built["understanding_model"].requests))

        assert result["status"] == "completed"
        assert result["result"] == {
            "revision": 1,
            "memory_version_id": head.memory.version_id,
            "processed_source": built["batch"],
        }
        assert observed_heads == [None]
        assert head.revision == 1 and head.processed_source == built["batch"]
        assert manifest.base_publication_revision == 0
        assert result["publish_request"]["expected_revision"] == 0
        assert publication.receipt(result["publish_request"]["operation_id"]).result == head
        if changed:
            assert [item.case_id for item in manifest.cases] == [built["case_id"]]
            assert [item.understanding_id for item in manifest.understandings] == [
                built["understanding_id"]]
            assert [(item.understanding_id, item.case_id)
                    for item in manifest.understanding_case_bindings] == [
                (built["understanding_id"], built["case_id"])]
        else:
            assert manifest.cases == () and manifest.understandings == ()
            assert manifest.understanding_case_bindings == ()

        assert built["workflow"].start(built["batch"]) == result
        assert publication.current().revision == 1
        assert calls == (len(built["case_model"].requests),
                         len(built["understanding_model"].requests))
    finally:
        built["engine"].dispose()


def test_pending_background_job_cannot_be_replaced_by_another_source():
    built = harness(b1_replies=[RuntimeError("synthetic B1 transport fault")])
    other = built["source"].window("otherbatch", "另一批")
    other_window = built["source"].window("otherwindow", "另一批")
    built["source"].plan(other, [{
        "source_reference": other_window, "context_reference": None,
    }])
    try:
        with pytest.raises(RuntimeError, match="synthetic B1 transport fault"):
            built["workflow"].start(built["batch"])
        with pytest.raises(ValueError, match="pending job"):
            built["workflow"].start(other)
        assert built["publication"].current() is None
    finally:
        built["engine"].dispose()
