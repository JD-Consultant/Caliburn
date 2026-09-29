"""Fault injection at native saver boundaries; no provider requests or product publication."""

import asyncio
import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from openai.types.responses import Response, ResponseFunctionToolCall
from psycopg.conninfo import make_conninfo

from caliburn.adapters.response_serialization import snapshot_response
from caliburn.agent_execution.tool_steps import (
    ResponseStepRuntime,
    _build_response_step,
    run_response_step,
)
from caliburn.settings import DatabaseSettings

pytestmark = pytest.mark.postgres


class ModelCheckpointFault(AsyncPostgresSaver):
    fail_after_commit = False
    failed = False

    async def aput(self, config, checkpoint, metadata, new_versions):
        if checkpoint["channel_values"].get("response_snapshot") and not self.failed:
            self.failed = True
            if self.fail_after_commit:
                await super().aput(config, checkpoint, metadata, new_versions)
            raise ConnectionError("synthetic checkpoint confirmation failure")
        return await super().aput(config, checkpoint, metadata, new_versions)


class EntireModelSaveFault(ModelCheckpointFault):
    async def aput_writes(self, config, writes, task_id, task_path=""):
        if any(name == "response_snapshot" for name, _ in writes):
            raise ConnectionError("synthetic pending writes unavailable")
        await super().aput_writes(config, writes, task_id, task_path)


@pytest.mark.parametrize("fail_after_commit", [False, True])
def test_model_checkpoint_failure_does_not_dispatch_and_pending_writes_recover_original(
    empty_database_settings: DatabaseSettings, fail_after_commit: bool
) -> None:
    settings = empty_database_settings

    async def scenario() -> None:
        response = Response.model_validate_json(
            (Path(__file__).parents[1] / "fixtures/native-response.json").read_text(
                encoding="utf-8"
            )
        )
        events = []
        config = {"configurable": {"thread_id": "model-checkpoint-fault"}}
        dsn = make_conninfo(settings.url, options=f"-c search_path={settings.schema}")
        serde = JsonPlusSerializer(pickle_fallback=False, allowed_msgpack_modules=None)

        async def request(items: list) -> Response:
            events.append("model")
            return response

        async def prepare(call: ResponseFunctionToolCall, operation_id: UUID) -> object:
            events.append("prepare")
            return {"operation_id": str(operation_id)}

        async def execute(prepared: object) -> str:
            events.append("execute")
            return "original observation"

        runtime = ResponseStepRuntime(request, prepare, execute)
        async with ModelCheckpointFault.from_conn_string(dsn, serde=serde) as saver:
            await saver.setup()
            saver.fail_after_commit = fail_after_commit
            with pytest.raises(ConnectionError, match="checkpoint confirmation"):
                await run_response_step(
                    saver,
                    input_items=[],
                    thread_id=config["configurable"]["thread_id"],
                    runtime=runtime,
                    max_tool_calls=16,
                )
            assert events == ["model"]

        # New connection/runner; no checkpoint_id, which would explicitly replay work.
        async with AsyncPostgresSaver.from_conn_string(dsn, serde=serde) as saver:
            result = await run_response_step(
                saver,
                input_items=None,
                thread_id=config["configurable"]["thread_id"],
                runtime=runtime,
                max_tool_calls=16,
            )
            assert result["tool_results"] == [
                {
                    "type": "function_call_output",
                    "call_id": "call_synthetic",
                    "output": "original observation",
                }
            ]
            assert events == ["model", "prepare", "execute"]

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())


def test_saved_step_reopens_without_repeating_window_items(
    empty_database_settings: DatabaseSettings,
) -> None:
    settings = empty_database_settings

    async def scenario() -> None:
        payload = json.loads(
            (Path(__file__).parents[1] / "fixtures/native-response.json").read_text(
                encoding="utf-8"
            )
        )
        payload["output"] = payload["output"][:2]
        payload["output"][1]["phase"] = "final_answer"
        response = Response.model_validate(payload)
        requests = 0

        async def request(items: list) -> Response:
            nonlocal requests
            requests += 1
            return response

        async def prepare(call: ResponseFunctionToolCall, operation_id: UUID) -> object:
            pytest.fail("No tools in final response")

        async def execute(prepared: object) -> str:
            pytest.fail("No tools in final response")

        dsn = make_conninfo(settings.url, options=f"-c search_path={settings.schema}")
        config = {"configurable": {"thread_id": "completed-step"}}
        runtime = ResponseStepRuntime(request, prepare, execute)
        serde = JsonPlusSerializer(pickle_fallback=False, allowed_msgpack_modules=None)
        async with AsyncPostgresSaver.from_conn_string(dsn, serde=serde) as saver:
            await saver.setup()
            result = await _build_response_step(saver, max_tool_calls=16).ainvoke(
                {"input_items": [{"role": "user", "content": "synthetic"}]},
                config,
                context=runtime,
                durability="sync",
            )
        async with AsyncPostgresSaver.from_conn_string(dsn, serde=serde) as saver:
            restored = await _build_response_step(saver, max_tool_calls=16).ainvoke(
                None, config, context=runtime, durability="sync"
            )
            assert restored == result
            assert restored["next_action"] == "deliver_answer"
            assert len(restored["input_items"]) == 3
            assert requests == 1

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())


def test_held_model_update_can_be_saved_with_native_update_state_after_both_writes_fail(
    empty_database_settings: DatabaseSettings,
) -> None:
    """Capability proof only: the supervisor must verify eligibility before adopting this update."""
    settings = empty_database_settings

    async def scenario() -> None:
        response = Response.model_validate_json(
            (Path(__file__).parents[1] / "fixtures/native-response.json").read_text(
                encoding="utf-8"
            )
        )
        calls = []
        retained_response = None

        async def request(items: list) -> Response:
            nonlocal retained_response
            calls.append("model")
            retained_response = snapshot_response(response)
            return response

        async def prepare(call: ResponseFunctionToolCall, operation_id: UUID) -> object:
            calls.append("read")
            return "original observation"

        async def execute(prepared: object) -> str:
            pytest.fail("Read-only test")

        dsn = make_conninfo(settings.url, options=f"-c search_path={settings.schema}")
        config = {"configurable": {"thread_id": "no-durable-response"}}
        runtime = ResponseStepRuntime(request, prepare, execute)
        serde = JsonPlusSerializer(pickle_fallback=False, allowed_msgpack_modules=None)
        streamed_update = None
        async with EntireModelSaveFault.from_conn_string(dsn, serde=serde) as saver:
            await saver.setup()
            graph = _build_response_step(saver, max_tool_calls=16)
            with pytest.raises(ConnectionError):
                async for update in graph.astream(
                    {"input_items": []},
                    config,
                    context=runtime,
                    durability="sync",
                    stream_mode="updates",
                ):
                    if "request_model" in update:
                        streamed_update = update["request_model"]
            # Graph updates are not guaranteed to reach the caller if persistence fails.
            assert streamed_update is None
            assert retained_response is not None
            assert calls == ["model"]

        async with AsyncPostgresSaver.from_conn_string(dsn, serde=serde) as saver:
            graph = _build_response_step(saver, max_tool_calls=16)
            saved = await graph.aget_state(config)
            assert "response_snapshot" not in saved.values
            # Known isolated work, no later effect, original update still held in this process.
            retained_update = {
                "response_snapshot": retained_response,
                "operation_seed": uuid4(),
                "prepared_tool": None,
                "tool_results": [],
                "next_action": None,
            }
            await graph.aupdate_state(config, retained_update, as_node="request_model")
            result = await graph.ainvoke(None, config, context=runtime, durability="sync")
            assert result["response_snapshot"] == retained_update["response_snapshot"]
            assert result["operation_seed"] == retained_update["operation_seed"]
            assert calls == ["model", "read"]

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())
