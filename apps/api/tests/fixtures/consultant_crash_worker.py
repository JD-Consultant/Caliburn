"""Hard-exit a synthetic A journey at real saver/transaction boundaries."""

import asyncio
import json
import os
import sys
from collections.abc import Sequence
from hashlib import sha256
from typing import Any
from uuid import UUID

import httpx2
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import ChannelVersions, Checkpoint, CheckpointMetadata
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row

from caliburn.adapters.database import Database
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import create_responses_client
from caliburn.agents.job_consultant.runner import ConsultantRunner
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionWriter
from caliburn.features.interviews.models import FormalInterviewExchange
from caliburn.settings import DatabaseSettings, ModelSettings
from caliburn.workflows.consultant_controls import run_consultant_with_controls
from caliburn.workflows.memory_analysis.tools import MEMORY_CHECKPOINT_TYPES
from tests.unit.test_response_loop import response_at

ORIGINAL_REPLY = "已記下職務名稱。最近一個頁面你親自做到哪裡？"


def require_original_tool_exchange(items: list[dict[str, Any]]) -> None:
    """Check the outgoing boundary independently of the production item serializer."""
    assert [item.get("type") for item in items[-4:]] == [
        "reasoning",
        "message",
        "function_call",
        "function_call_output",
    ], "The resumed request must retain the original ordered model/tool exchange"
    reasoning, message, call, result = items[-4:]
    assert reasoning["id"] == "reasoning_1"
    assert reasoning["encrypted_content"] == "synthetic-opaque-1"
    assert reasoning["provider_extension"] == {"must_survive": True}
    assert message["id"] == "message_1"
    assert message["role"] == "assistant"
    assert message["phase"] == "commentary"
    assert message["content"][0]["text"] == "正在讀取測試資料。"
    assert call["id"] == "function_1_0"
    assert call["call_id"] == result["call_id"] == "call_1_0"
    assert call["name"] == "revise_jd_profile"
    assert json.loads(call["arguments"]) == {
        "changes": [
            {"action": "set_field", "field": "job_title", "value": "前端工程師"},
            {"action": "add_source", "field": "job_title", "source": {"kind": "current_input"}},
        ]
    }
    assert result["output"] == "updated"


def stop_process(boundary: str) -> None:
    print(json.dumps({"event": "crash", "boundary": boundary}), flush=True)
    os._exit(19)  # Only this isolated probe; deliberately bypass async/finally cleanup.


class CrashSaver(AsyncPostgresSaver):
    boundary: str

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        values = checkpoint["channel_values"]
        if self.boundary == "tool_committed" and values.get("tool_results"):
            # Never let the full checkpoint race ahead of the killed task-write.
            await asyncio.Event().wait()
        saved = await super().aput(config, checkpoint, metadata, new_versions)
        response = values.get("response_snapshot", {})
        if (
            (self.boundary == "count_saved" and values.get("input_count") is not None)
            or (self.boundary == "response_saved" and response.get("id") == "response_1")
            or (self.boundary == "final_saved" and response.get("id") == "response_2")
        ):
            stop_process(self.boundary)
        return saved

    async def aput_writes(
        self,
        config: RunnableConfig,
        writes: Sequence[tuple[str, Any]],
        task_id: str,
        task_path: str = "",
    ) -> None:
        if self.boundary == "tool_committed" and any(
            channel == "tool_results" and value for channel, value in writes
        ):
            # execute_tool has returned only after the actual JD transaction committed.
            # Kill before persisting that observation: restart must reconcile the command.
            stop_process(self.boundary)
        await super().aput_writes(config, writes, task_id, task_path)


async def run(boundary: str, schema: str, job_file: str, execution: str, writer: str) -> None:
    settings = DatabaseSettings(url=os.environ["CALIBURN_TEST_DATABASE_URL"], schema=schema)
    database = Database(settings)
    scope = ExecutionScope(UUID(job_file), UUID(execution), ExecutionKind.CONSULTANT_TURN)
    identity = ExecutionWriter(scope, UUID(writer))

    def respond(request: httpx2.Request) -> httpx2.Response:
        payload = json.loads(request.content)
        counting = request.url.path.endswith("/input_tokens")
        after_tool = any(item.get("type") == "function_call_output" for item in payload["input"])
        if after_tool:
            require_original_tool_exchange(payload["input"])
        print(
            json.dumps(
                {
                    "event": "request",
                    "kind": "count" if counting else "model",
                    "step": 2 if after_tool else 1,
                    "input_hash": sha256(
                        json.dumps(payload["input"], sort_keys=True).encode()
                    ).hexdigest(),
                }
            ),
            flush=True,
        )
        if counting:
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 500}
            )
        assert request.url.path.endswith("/responses")
        raw = response_at(
            2 if after_tool else 1, final=after_tool, tools=0 if after_tool else 1
        ).model_dump(mode="json")
        raw["service_tier"] = "default"
        if after_tool:
            raw["output"][1]["content"][0]["text"] = ORIGINAL_REPLY
        else:
            raw["output"][-1].update(
                name="revise_jd_profile",
                arguments=json.dumps(
                    {
                        "changes": [
                            {"action": "set_field", "field": "job_title", "value": "前端工程師"},
                            {
                                "action": "add_source",
                                "field": "job_title",
                                "source": {"kind": "current_input"},
                            },
                        ]
                    }
                ),
            )
        return httpx2.Response(200, json=raw)

    sdk = create_responses_client(
        api_key="synthetic-not-a-real-key",
        timeout_seconds=5,
        http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
    )
    try:
        dsn = make_conninfo(settings.url, options=f"-c search_path={schema}")
        async with await AsyncConnection.connect(
            dsn, autocommit=True, prepare_threshold=0, row_factory=dict_row
        ) as connection:
            serializer = create_graph_serializer(allowed_types=MEMORY_CHECKPOINT_TYPES)
            if boundary == "resume":
                saver = AsyncPostgresSaver(connection, serde=serializer)
            else:
                saver = CrashSaver(connection, serde=serializer)
                saver.boundary = boundary
            await saver.setup()
            runner = ConsultantRunner(
                database.sessions, saver, sdk, ModelSettings(api_key="synthetic")
            )
            result = await run_consultant_with_controls(
                identity,
                sessions=database.sessions,
                checkpointer=saver,
                run=runner.run_supervised,
            )
            assert isinstance(result, FormalInterviewExchange)
            print(
                json.dumps({"event": "completed", "reply": result.consultant_reply.interview_text}),
                flush=True,
            )
    finally:
        await sdk.close()
        await database.close()


if __name__ == "__main__":
    asyncio.run(run(*sys.argv[1:]), loop_factory=asyncio.SelectorEventLoop)
