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

from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.adapters.response_serialization import NativeItems
from caliburn.agent_execution.tool_steps import (
    ReceivedModelResponse,
    ResponseStepRuntime,
    ResponseStepSaveError,
    _build_response_step,
    run_response_step,
)
from caliburn.settings import DatabaseSettings

pytestmark = pytest.mark.postgres


async def ensure_active() -> None:
    """Storage-only cases; product fencing is exercised by the execution tests."""


async def account_response(received: ReceivedModelResponse) -> None:
    """Storage-only cases, without execution cost persistence."""


def make_request(input_items: NativeItems) -> ResponseRequest:
    return ResponseRequest(
        model="gpt-6-luna",
        instructions="synthetic",
        input_items=input_items,
        tools=[],
        reasoning_effort="low",
        max_output_tokens=512,
    )


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

        async def request(
            model_request: ResponseRequest, request_id: UUID
        ) -> ReceivedModelResponse:
            events.append("model")
            return ReceivedModelResponse(response=response, attempt_id=uuid4())

        async def prepare(call: ResponseFunctionToolCall, operation_id: UUID) -> object:
            events.append("prepare")
            return {"operation_id": str(operation_id)}

        async def execute(prepared: object) -> str:
            events.append("execute")
            return "original observation"

        runtime = ResponseStepRuntime(
            request_model=request,
            prepare_tool=prepare,
            execute_tool=execute,
            ensure_active=ensure_active,
            account_response=account_response,
        )
        async with ModelCheckpointFault.from_conn_string(dsn, serde=serde) as saver:
            await saver.setup()
            saver.fail_after_commit = fail_after_commit
            with pytest.raises(ResponseStepSaveError) as failure:
                await run_response_step(
                    saver,
                    request=make_request([]),
                    thread_id=config["configurable"]["thread_id"],
                    runtime=runtime,
                    max_tool_calls=16,
                )
            assert isinstance(failure.value.__cause__, ConnectionError)
            assert events == ["model"]

        # New connection/runner; no checkpoint_id, which would explicitly replay work.
        async with AsyncPostgresSaver.from_conn_string(dsn, serde=serde) as saver:
            result = await run_response_step(
                saver,
                request=None,
                recovery=failure.value.recovery,
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

        async def request(
            model_request: ResponseRequest, request_id: UUID
        ) -> ReceivedModelResponse:
            nonlocal requests
            requests += 1
            return ReceivedModelResponse(response=response, attempt_id=uuid4())

        async def prepare(call: ResponseFunctionToolCall, operation_id: UUID) -> object:
            pytest.fail("No tools in final response")

        async def execute(prepared: object) -> str:
            pytest.fail("No tools in final response")

        dsn = make_conninfo(settings.url, options=f"-c search_path={settings.schema}")
        config = {"configurable": {"thread_id": "completed-step"}}
        runtime = ResponseStepRuntime(
            request_model=request,
            prepare_tool=prepare,
            execute_tool=execute,
            ensure_active=ensure_active,
            account_response=account_response,
        )
        serde = JsonPlusSerializer(pickle_fallback=False, allowed_msgpack_modules=None)
        async with AsyncPostgresSaver.from_conn_string(dsn, serde=serde) as saver:
            await saver.setup()
            result = await _build_response_step(saver, max_tool_calls=16).ainvoke(
                {
                    "request_snapshot": make_request(
                        [{"role": "user", "content": "synthetic"}]
                    ).create_payload(),
                    "request_id": uuid4(),
                },
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


def test_public_step_recovery_saves_held_model_result_after_both_writes_fail(
    empty_database_settings: DatabaseSettings,
) -> None:
    """The caller retains the public recovery handoff; no hand-written graph state repair."""
    settings = empty_database_settings

    async def scenario() -> None:
        response = Response.model_validate_json(
            (Path(__file__).parents[1] / "fixtures/native-response.json").read_text(
                encoding="utf-8"
            )
        )
        calls = []

        async def request(
            model_request: ResponseRequest, request_id: UUID
        ) -> ReceivedModelResponse:
            calls.append("model")
            return ReceivedModelResponse(response=response, attempt_id=uuid4())

        async def prepare(call: ResponseFunctionToolCall, operation_id: UUID) -> object:
            calls.append("read")
            return "original observation"

        async def execute(prepared: object) -> str:
            pytest.fail("Read-only test")

        dsn = make_conninfo(settings.url, options=f"-c search_path={settings.schema}")
        config = {"configurable": {"thread_id": "no-durable-response"}}
        runtime = ResponseStepRuntime(
            request_model=request,
            prepare_tool=prepare,
            execute_tool=execute,
            ensure_active=ensure_active,
            account_response=account_response,
        )
        serde = JsonPlusSerializer(pickle_fallback=False, allowed_msgpack_modules=None)
        async with EntireModelSaveFault.from_conn_string(dsn, serde=serde) as saver:
            await saver.setup()
            with pytest.raises(ResponseStepSaveError) as failure:
                await run_response_step(
                    saver,
                    thread_id=config["configurable"]["thread_id"],
                    request=make_request([]),
                    runtime=runtime,
                    max_tool_calls=16,
                )
            assert calls == ["model"]

        async with AsyncPostgresSaver.from_conn_string(dsn, serde=serde) as saver:
            graph = _build_response_step(saver, max_tool_calls=16)
            saved = await graph.aget_state(config)
            assert "response_snapshot" not in saved.values
            result = await run_response_step(
                saver,
                thread_id=config["configurable"]["thread_id"],
                request=None,
                recovery=failure.value.recovery,
                runtime=runtime,
                max_tool_calls=16,
            )
            assert result["response_snapshot"] == failure.value.recovery.update["response_snapshot"]
            assert result["operation_seed"] == failure.value.recovery.update["operation_seed"]
            assert calls == ["model", "read"]

    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(scenario())
