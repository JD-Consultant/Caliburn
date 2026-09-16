"""Deterministic B1 -> B2 -> bundle -> publication workflow; zero provider."""

from copy import deepcopy
import json
from types import MethodType
from typing import Any
from uuid import uuid4

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore
from pydantic import Field
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from caliburn_memory import (
    BackgroundMemoryWorkflow,
    CaseArtifact,
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


def harness(*, changed: bool = True, b1_replies=None, b2_replies=None,
            case_ids=None, understanding_ids=None, evidence_text=None,
            published_base: bool = False):
    source = WindowSource()
    case_ids = list(case_ids or [str(uuid4())])
    understanding_ids = list(understanding_ids or [str(uuid4())])
    case_id, understanding_id = case_ids[0], understanding_ids[0]
    base_evidence = None
    base_batch = None
    if published_base:
        base_evidence = source.evidence("baseevidence", [("user", "本人不負責跨部門通知。")])
        base_batch = source.window("basebatch", "既有已發布訪談批次")
    evidence = source.evidence(
        "evidence", [("user", evidence_text or "本人先確認告警並記錄結果。")])
    batch = source.window("batch", "固定 canonical 批次")
    window = source.window("window", "本人先確認告警並記錄結果。")
    source.set_window_evidence(window, evidence)
    source.set_history(*((base_evidence, evidence) if base_evidence else (evidence,)))
    source.plan(batch, [{"source_reference": window, "context_reference": None}])

    artifacts = MemoryArtifacts(InMemoryStore(), source.document_id, source=source)
    base = None
    if published_base:
        base = artifacts.save_bundle(
            base_publication_revision=0,
            evidence_through_reference=base_batch,
            case_guide=f"- [告警處理](/memory/cases/items/{case_id}.md) — 告警與責任邊界",
            cases=(CaseArtifact(
                case_id,
                "## 告警處理\n本人確認告警並負責跨部門通知。",
                (base_evidence,),
            ),),
            understanding_guide="",
            understandings=(),
        )
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
    case_id_iter = iter(case_ids)
    case_session = CaseMaintenanceSession(artifacts, id_factory=lambda: next(case_id_iter))
    case_workflow = CaseMaintenanceWorkflow(
        source, case_session, case_model, InMemorySaver(),
        max_model_steps=12, max_tool_calls=12,
    )

    default_understanding_replies = ([
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
    understanding_model = FixedModel(
        replies=list(b2_replies if b2_replies is not None else default_understanding_replies))
    understanding_id_iter = iter(understanding_ids)
    understanding_session = UnderstandingMaintenanceSession(
        artifacts, case_session, id_factory=lambda: next(understanding_id_iter),
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
    if base is not None:
        publication.publish(publication.prepare(
            base,
            expected_revision=0,
            kind="consolidation",
            processed_source=base_batch,
        ))
    workflow = BackgroundMemoryWorkflow(
        case_workflow, understanding_workflow, publication, InMemorySaver(),
        max_stale_retries=2,
    )
    return {
        "source": source,
        "base_evidence": base_evidence,
        "evidence": evidence,
        "batch": batch,
        "artifacts": artifacts,
        "case_id": case_id,
        "case_ids": case_ids,
        "understanding_id": understanding_id,
        "understanding_ids": understanding_ids,
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


def runtime_review_payloads(model):
    payloads = []
    for request in model.requests:
        for message in request:
            if not isinstance(message, HumanMessage) or not isinstance(message.content, str):
                continue
            try:
                payload = json.loads(message.content)
            except json.JSONDecodeError:
                continue
            if payload.get("RUNTIME_REVIEW"):
                payloads.append(payload["RUNTIME_REVIEW"])
    return payloads


def test_base_case_rework_revises_the_published_identity_from_exact_source():
    case_id, understanding_id = str(uuid4()), str(uuid4())
    built = harness(
        published_base=True,
        case_ids=[case_id],
        understanding_ids=[understanding_id],
        b1_replies=[
            call("finish_case_maintenance", {}, "first-finish"),
            done("first-done"),
            call("read_more_evidence", {"evidence_key": "E1"}, "review-source"),
            call("read_case", {"case_id": case_id}, "read-base-case"),
            call("revise_case", {
                "case_id": case_id,
                "diff": ("@@\n ## 告警處理\n"
                         "-本人確認告警並負責跨部門通知。\n"
                         "+本人只確認告警；跨部門通知由主管負責。"),
                "route_note": None,
                "add_evidence_keys": [],
                "remove_evidence_keys": [],
            }, "revise-base-case"),
            call("finish_case_maintenance", {}, "second-finish"),
            done("second-done"),
        ],
        b2_replies=[
            call("read_case", {"case_id": case_id}, "first-read-case"),
            call("read_case_source", {"evidence_key": "E1"}, "first-read-source"),
            call("request_case_rework", {"issues": [{
                "evidence_key": "E1",
                "reason": "原話明確排除跨部門通知責任。",
            }]}, "first-rework"),
            done("first-rework-done"),
            call("read_case", {"case_id": case_id}, "second-read-case"),
            call("create_work_understanding", {
                "content": "本人負責告警確認；跨部門通知由主管負責。",
                "supporting_case_ids": [case_id],
                "route_note": "告警確認與通知責任邊界",
            }, "create-understanding"),
            call("finish_understanding_maintenance", {}, "understanding-finish"),
            done("understanding-done"),
        ],
    )
    try:
        result = built["workflow"].start(built["batch"])
        head = built["publication"].current()
        manifest = built["artifacts"].bundle_manifest(head.memory)
        review = runtime_review_payloads(built["case_model"])

        assert result["status"] == "completed" and result["case_rework_count"] == 1
        assert head.revision == 2
        assert [item.case_id for item in manifest.cases] == [case_id]
        assert "跨部門通知由主管負責" in built["artifacts"].case(
            head.memory, case_id).content
        assert review[0][0]["case_locator"] == case_id
        assert review[0][0]["case_origin"] == "base"
        assert (built["base_evidence"], 0) in built["source"].source_reads
    finally:
        built["engine"].dispose()


def test_candidate_only_rework_starts_fresh_b1_and_allocates_a_new_case_identity():
    rejected_id, replacement_id, understanding_id = (
        str(uuid4()), str(uuid4()), str(uuid4()))
    built = harness(
        case_ids=[rejected_id, replacement_id],
        understanding_ids=[understanding_id],
        evidence_text="本人只確認告警。",
        b1_replies=[
            call("create_case", {
                "content": "## 告警處理\n本人確認告警並通知其他單位。",
                "route_note": "告警確認與外部通知",
                "evidence_keys": ["E1"],
            }, "create-rejected"),
            call("finish_case_maintenance", {}, "first-finish"),
            done("first-done"),
            call("read_more_evidence", {"evidence_key": "E1"}, "review-source"),
            call("create_case", {
                "content": "## 告警處理\n本人只確認告警。",
                "route_note": "告警確認",
                "evidence_keys": ["E1"],
            }, "create-replacement"),
            call("finish_case_maintenance", {}, "second-finish"),
            done("second-done"),
        ],
        b2_replies=[
            call("read_case", {"case_id": rejected_id}, "first-read-case"),
            call("read_case_source", {"evidence_key": "E1"}, "first-read-source"),
            call("request_case_rework", {"issues": [{
                "evidence_key": "E1",
                "reason": "原話只支持確認告警，不支持通知其他單位。",
            }]}, "first-rework"),
            done("first-rework-done"),
            call("read_case", {"case_id": replacement_id}, "second-read-case"),
            call("create_work_understanding", {
                "content": "本人穩定負責告警確認。",
                "supporting_case_ids": [replacement_id],
                "route_note": "告警確認",
            }, "create-understanding"),
            call("finish_understanding_maintenance", {}, "understanding-finish"),
            done("understanding-done"),
        ],
    )
    try:
        result = built["workflow"].start(built["batch"])
        head = built["publication"].current()
        manifest = built["artifacts"].bundle_manifest(head.memory)
        review = runtime_review_payloads(built["case_model"])

        assert result["status"] == "completed" and result["case_rework_count"] == 1
        assert [item.case_id for item in manifest.cases] == [replacement_id]
        assert rejected_id not in {item.case_id for item in manifest.cases}
        assert review[0][0]["case_locator"] == rejected_id
        assert review[0][0]["case_origin"] == "candidate"
        assert review[0][0]["candidate_content"].endswith("本人確認告警並通知其他單位。")
        assert (built["evidence"], 0) in built["source"].source_reads
    finally:
        built["engine"].dispose()


def test_second_case_rework_is_bounded_and_never_publishes():
    rejected_id, replacement_id = str(uuid4()), str(uuid4())
    built = harness(
        case_ids=[rejected_id, replacement_id],
        evidence_text="本人只確認告警。",
        b1_replies=[
            call("create_case", {
                "content": "## 告警處理\n本人確認告警並通知其他單位。",
                "route_note": "告警確認與外部通知",
                "evidence_keys": ["E1"],
            }, "create-rejected"),
            call("finish_case_maintenance", {}, "first-finish"),
            done("first-done"),
            call("read_more_evidence", {"evidence_key": "E1"}, "review-source"),
            call("create_case", {
                "content": "## 告警處理\n本人只確認告警。",
                "route_note": "告警確認",
                "evidence_keys": ["E1"],
            }, "create-replacement"),
            call("finish_case_maintenance", {}, "second-finish"),
            done("second-done"),
        ],
        b2_replies=[
            call("read_case", {"case_id": rejected_id}, "first-read-case"),
            call("read_case_source", {"evidence_key": "E1"}, "first-read-source"),
            call("request_case_rework", {"issues": [{
                "evidence_key": "E1", "reason": "第一版案例責任錯誤。",
            }]}, "first-rework"),
            done("first-rework-done"),
            call("read_case", {"case_id": replacement_id}, "second-read-case"),
            call("read_case_source", {"evidence_key": "E1"}, "second-read-source"),
            call("request_case_rework", {"issues": [{
                "evidence_key": "E1", "reason": "重做後仍有實質案例問題。",
            }]}, "second-rework"),
            done("second-rework-done"),
        ],
    )
    try:
        result = built["workflow"].start(built["batch"])

        assert result["status"] == "blocked"
        assert result["error_code"] == "case_rework_limit_reached"
        assert result["case_rework_count"] == 1
        assert built["publication"].current() is None
        assert built["case_model"].replies == []
        assert built["understanding_model"].replies == []
    finally:
        built["engine"].dispose()
