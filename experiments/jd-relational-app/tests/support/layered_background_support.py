"""Zero-provider fixtures for the layered background workflow on real PG."""

from contextlib import contextmanager
from copy import deepcopy
import json
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

from jd_relational.background_memory_app import build_background_memory_workflow

from test_consolidation_postgres import opened_b2


def call(name, arguments, identity):
    return AIMessage("", id=f"message-{identity}", tool_calls=[{
        "name": name,
        "args": arguments,
        "id": identity,
        "type": "tool_call",
    }], response_metadata={"status": "completed", "finish_reason": "tool_calls"})


def done(identity):
    return AIMessage(
        "完成。",
        id=identity,
        response_metadata={"status": "completed", "finish_reason": "stop"},
    )


def _tool_names(messages):
    return [tool["name"] for message in messages if isinstance(message, AIMessage)
            for tool in message.tool_calls]


def _payload(messages, field):
    for message in reversed(messages):
        if not isinstance(message, HumanMessage) or not isinstance(message.content, str):
            continue
        try:
            value = json.loads(message.content)
        except json.JSONDecodeError:
            continue
        if field in value:
            return value
    raise AssertionError(f"Runtime payload {field} was not supplied")


class LayeredModel(BaseChatModel):
    """Derive the next deterministic tool from durable messages, not process state."""

    role: str
    fail_first: bool = False
    requests: list[Any] = Field(default_factory=list)

    @property
    def _llm_type(self):
        return "layered-background-postgres-test"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.requests.append(deepcopy(messages))
        if self.fail_first:
            self.fail_first = False
            raise ConnectionError(f"synthetic {self.role} transport failure")
        names = _tool_names(messages)
        identity = f"{self.role}-{len(names) + 1}"
        if self.role == "b1":
            if "create_case" not in names:
                payload = _payload(messages, "NEW_SOURCE")
                evidence = payload["NEW_SOURCE"]["evidence"]["blocks"]
                return ChatResult(generations=[ChatGeneration(message=call(
                    "create_case",
                    {
                        "content": "## 告警處理\n本人先確認告警並記錄結果。",
                        "route_note": "告警確認與結果記錄",
                        "evidence_keys": [evidence[0]["evidence_key"]],
                    },
                    identity,
                ))])
            if "finish_case_maintenance" not in names:
                return ChatResult(generations=[ChatGeneration(message=call(
                    "finish_case_maintenance", {}, identity,
                ))])
            return ChatResult(generations=[ChatGeneration(message=done(identity))])

        payload = _payload(messages, "REQUIRED_CASE_IDS")
        case_id = payload["REQUIRED_CASE_IDS"][0]
        if "read_case" not in names:
            reply = call("read_case", {"case_id": case_id}, identity)
        elif "create_work_understanding" not in names:
            reply = call("create_work_understanding", {
                "content": "本人穩定負責告警確認與結果記錄。",
                "supporting_case_ids": [case_id],
                "route_note": "告警確認與結果記錄",
            }, identity)
        elif "finish_understanding_maintenance" not in names:
            reply = call("finish_understanding_maintenance", {}, identity)
        else:
            reply = done(identity)
        return ChatResult(generations=[ChatGeneration(message=reply)])


@contextmanager
def opened_layered(dataset, document, *, b2_fails_first=False):
    """Rebuild every workflow object from durable resource identities."""
    with opened_b2(dataset, document) as (
        native, windows, store, saver, store_connection, _legacy_artifacts, publication,
    ):
        case_model = LayeredModel(role="b1")
        understanding_model = LayeredModel(role="b2", fail_first=b2_fails_first)
        workflow = build_background_memory_workflow(
            service=windows,
            document_id=document,
            store=store,
            checkpointer=saver,
            memory_engine=publication.engine,
            case_model=case_model,
            understanding_model=understanding_model,
            case_max_output_tokens=8192,
            understanding_max_output_tokens=8192,
            case_max_model_steps=12,
            case_max_tool_calls=12,
            case_max_chars=24000,
            case_context_chars=1500,
            case_max_windows=16,
            understanding_max_model_steps=12,
            understanding_max_tool_calls=12,
            max_stale_retries=2,
        )
        yield {
            "native": native,
            "windows": windows,
            "store": store,
            "saver": saver,
            "store_connection": store_connection,
            "workflow": workflow,
            "publication": workflow.publication,
            "case_model": case_model,
            "understanding_model": understanding_model,
        }
