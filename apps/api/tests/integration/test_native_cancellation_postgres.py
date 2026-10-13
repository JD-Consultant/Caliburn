"""取消後重開正式 runner，仍沿用真實提交的原件。"""

import asyncio
import gc
from dataclasses import replace

import httpx2
import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.job_file_checkpointer import JobFilePostgresSaver
from caliburn.adapters.openai_responses import create_responses_client
from caliburn.agent_execution.native_cleanup import await_native_cleanup
from caliburn.agent_execution.response_runtime import InputCountSaveError, ResponseStepSaveError
from caliburn.agent_execution.result_save_retries import ResultSaveCancelledError
from caliburn.agents.job_consultant.runner import ConsultantRunner
from caliburn.features.executions import service as executions
from caliburn.features.executions.history_models import (
    AgentRole,
    HistoryWindowKind,
    context_thread_id,
)
from caliburn.features.executions.models import ExecutionStatus
from caliburn.features.interviews.models import FormalInterviewExchange
from caliburn.settings import ModelSettings
from tests.fixtures.consultant_turn import start_consultant_turn
from tests.fixtures.response_loop import response_at

pytestmark = pytest.mark.postgres


class DelayedResultAcknowledgement(JobFilePostgresSaver):
    def __init__(self, native, thread_id, channel):
        super().__init__(native)
        self.thread_id = thread_id
        self.channel = channel
        self.committed = asyncio.Event()
        self.release = asyncio.Event()
        self.original_writes = []

    async def aput(self, config, checkpoint, metadata, new_versions):
        saved = await super().aput(config, checkpoint, metadata, new_versions)
        if (
            config["configurable"]["thread_id"] == self.thread_id
            and checkpoint["channel_values"].get(self.channel) is not None
        ):
            await self.release.wait()
        return saved

    async def aput_writes(self, config, writes, task_id, task_path=""):
        await super().aput_writes(config, writes, task_id, task_path)
        if config["configurable"]["thread_id"] == self.thread_id:
            for channel, original in writes:
                if channel == self.channel:
                    self.original_writes.append((config, original))
                    self.committed.set()
                    await self.release.wait()


@pytest.mark.parametrize("channel", ["response_snapshot", "input_count"])
@pytest.mark.parametrize("return_handoff", [False, True])
def test_committed_original_survives_cancellation_and_saver_reopen(
    client, database_settings, channel, return_handoff, recwarn
):
    writer = start_consultant_turn(client)
    thread_id = context_thread_id(
        writer.scope, AgentRole.JOB_CONSULTANT, HistoryWindowKind.COMPLETED_WORK
    )

    async def scenario():
        calls = []

        def respond(request):
            calls.append(request.url.path)
            if request.url.path.endswith("/input_tokens"):
                return httpx2.Response(
                    200, json={"object": "response.input_tokens", "input_tokens": 500}
                )
            raw = response_at(1, final=True, tools=0).model_dump(mode="json")
            raw["service_tier"] = "default"
            raw["output"][1]["content"][0]["text"] = "已提交的原回應。"
            return httpx2.Response(200, json=raw)

        sdk = create_responses_client(
            api_key="synthetic-not-a-real-key",
            timeout_seconds=5,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
        )
        dsn = make_conninfo(
            database_settings.url, options=f"-c search_path={database_settings.schema}"
        )
        try:
            async with AsyncPostgresSaver.from_conn_string(
                dsn, serde=create_graph_serializer()
            ) as native:
                await native.setup()
                saver = DelayedResultAcknowledgement(native, thread_id, channel)
                runner = ConsultantRunner(
                    client.app.state.database.sessions,
                    saver,
                    sdk,
                    ModelSettings(api_key="synthetic"),
                )
                task = asyncio.create_task(runner.run(writer))
                try:
                    await asyncio.wait_for(saver.committed.wait(), timeout=10)
                finally:
                    task.cancel()
                    saver.release.set()
                with pytest.raises(ResultSaveCancelledError) as stopped:
                    await task
                await await_native_cleanup(stopped.value)
                failure = stopped.value.save_error
                expected = (
                    ResponseStepSaveError if channel == "response_snapshot" else InputCountSaveError
                )
                assert isinstance(failure, expected)
                assert failure.recovery.thread_id == thread_id
                assert saver.original_writes
                assert calls == ["/v1/responses/input_tokens"] + (
                    ["/v1/responses"] if channel == "response_snapshot" else []
                )

            async with AsyncPostgresSaver.from_conn_string(
                dsn, serde=create_graph_serializer()
            ) as reopened:
                # 以新連線讀取同一 checkpoint 的原 pending writes。
                for config, original in saver.original_writes:
                    saved = await reopened.aget_tuple(config)
                    assert saved is not None
                    assert any(
                        key == channel and value == original
                        for _, key, value in saved.pending_writes or []
                    )
                resumed = replace(runner, checkpointer=JobFilePostgresSaver(reopened))
                result = await resumed.run(
                    writer, recovery=failure.recovery if return_handoff else None
                )
                assert isinstance(result, FormalInterviewExchange)
                assert result.consultant_reply.interview_text == "已提交的原回應。"
                assert calls == ["/v1/responses/input_tokens", "/v1/responses"]
                # 正式完成回執也阻止 runner 返回後重送。
                assert await resumed.run(writer) == result
                assert calls == ["/v1/responses/input_tokens", "/v1/responses"]
                async with runner.sessions() as session:
                    assert (
                        await executions.read_execution(session, writer.scope)
                    ).status == ExecutionStatus.COMPLETED
        finally:
            await sdk.close()

    client.portal.call(scenario)
    gc.collect()
    assert [warning.message for warning in recwarn if warning.category is RuntimeWarning] == []
