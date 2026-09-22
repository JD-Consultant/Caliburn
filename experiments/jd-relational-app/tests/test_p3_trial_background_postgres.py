"""P3 test-only role ledger against the formal layered background PG workflow.

Only the external OpenRouter HTTP boundary is synthetic.  The dispatcher,
admission, B1/B2 agents, Saver, Store and publication are the current App's.
"""

import json
import os
from decimal import Decimal
from uuid import uuid4

import httpx
from langchain_core.messages import AIMessage
from langsmith import tracing_context
import pytest

from jd_relational.background_admission import BackgroundAdmissions
from jd_relational.background_dispatch import BackgroundDispatcher
from jd_relational.background_memory_app import build_background_memory_workflow
from support.openrouter_replies import reply
from support.p3_spend_gate import P3SpendGate
from support.p3_trial_server import open_trial_runtime
from test_background_admission_postgres import catalogued
from test_consolidation_postgres import opened_b2
from test_extraction_postgres import interviewed
from test_layered_background_dispatch_postgres import DirectWorker, requested
from test_storage_postgres import engine  # noqa: F401


pytestmark = pytest.mark.skipif(
    os.environ.get("JD_RELATIONAL_TEST_DB") != "1",
    reason="explicit isolated PostgreSQL test opt-in required",
)


def _payload(messages, field):
    for message in reversed(messages):
        if message.get("role") != "user":
            continue
        content = message.get("content")
        if not isinstance(content, str):
            continue
        try:
            value = json.loads(content)
        except json.JSONDecodeError:
            continue
        if field in value:
            return value
    raise AssertionError(f"formal {field} context was missing")


def _saved_generations(workflow, config):
    snapshot = workflow.graph.get_state(config)
    assert not snapshot.next
    return [message.response_metadata["id"] for message in snapshot.values["messages"]
            if isinstance(message, AIMessage)]


def test_formal_b1_b2_requests_match_durable_checkpoints_and_publication(engine, tmp_path):
    """Would fail if a role, provider response, checkpoint or publication is lost."""
    dataset, document = str(uuid4()), str(uuid4())
    catalogued(engine, document)
    spend = P3SpendGate(tmp_path / "spend.json", trial_id="p3-c-w-offline",
                        authorized=True, usd_cap=Decimal("1.00"), request_cap=20,
                        wait_timeout_seconds=5)
    sent = []

    def respond(request):
        payload = json.loads(request.content)
        sent.append(payload)
        tools = {item["function"]["name"] for item in payload["tools"]}
        called = [call["function"]["name"] for message in payload["messages"]
                  for call in message.get("tool_calls", [])]
        if "create_case" in tools:
            if "create_case" not in called:
                evidence = _payload(payload["messages"], "NEW_SOURCE")["NEW_SOURCE"]["evidence"]["blocks"]
                name, arguments = "create_case", {
                    "content": "## 告警處理\n本人先確認告警並記錄結果。",
                    "route_note": "告警確認與結果記錄",
                    "evidence_keys": [evidence[0]["evidence_key"]],
                }
            elif "finish_case_maintenance" not in called:
                name, arguments = "finish_case_maintenance", {}
            else:
                name, arguments = None, None
        else:
            assert "create_work_understanding" in tools
            case_id = _payload(payload["messages"], "REQUIRED_CASE_IDS")["REQUIRED_CASE_IDS"][0]
            if "read_case" not in called:
                name, arguments = "read_case", {"case_id": case_id}
            elif "create_work_understanding" not in called:
                name, arguments = "create_work_understanding", {
                    "content": "本人穩定負責告警確認與結果記錄。",
                    "supporting_case_ids": [case_id],
                    "route_note": "告警確認與結果記錄",
                }
            elif "finish_understanding_maintenance" not in called:
                name, arguments = "finish_understanding_maintenance", {}
            else:
                name, arguments = None, None
        body = reply(f"gen-p3-background-{len(sent)}", name, arguments, text="完成。")
        body["usage"]["cost"] = "0.001"
        return httpx.Response(200, json=body, request=request)

    with opened_b2(dataset, document) as (native, windows, store, saver, _, _, publication):
        interviewed(native, 1)
        requested(native)
        with open_trial_runtime(spend, "synthetic-not-a-secret",
                                transport=httpx.MockTransport(respond)) as runtime:
            workflow = build_background_memory_workflow(
                service=windows, document_id=document, store=store, checkpointer=saver,
                memory_engine=publication.engine, case_model=runtime.role_models.case,
                understanding_model=runtime.role_models.understanding,
            )
            worker = DirectWorker()
            dispatcher = BackgroundDispatcher(worker, BackgroundAdmissions(engine),
                windows, document, workflow=workflow, publication=workflow.publication,
                max_windows=2, max_chars=24000)
            with tracing_context(enabled=False):
                assert dispatcher.wake() == "next_batch"
            assert worker.futures[0].exception() is None

            outer = workflow.graph.get_state(workflow.config)
            head = workflow.publication.current()
            assert outer.values["status"] == "completed" and not outer.next
            assert head is not None and head.revision == 1
            assert head.processed_source == outer.values["source_reference"]
            assert BackgroundAdmissions(engine).read(document).status == "idle"
            bundle = workflow.artifacts.bundle_manifest(head.memory)
            assert len(bundle.cases) == len(bundle.understandings) == 1

            attempt_id = outer.values["case_attempt_id"]
            b1 = _saved_generations(workflow.case_workflow,
                                    workflow.case_workflow._attempt_config(attempt_id))
            b2 = _saved_generations(workflow.understanding_workflow,
                                    workflow.understanding_workflow._attempt_config(attempt_id))
            ledger = spend.snapshot()
            rows = ledger["attempts"]
            assert len(rows) == len(sent) == len(b1) + len(b2)
            assert [row["generation_id"] for row in rows if row["role"] == "background-case-maintainer"] == b1
            assert [row["generation_id"] for row in rows if row["role"] == "background-understanding-maintainer"] == b2
            assert b1 and b2 and all(row["outcome"] == "settled" for row in rows)
            assert "synthetic-not-a-secret" not in (tmp_path / "spend.json").read_text(encoding="utf-8")
