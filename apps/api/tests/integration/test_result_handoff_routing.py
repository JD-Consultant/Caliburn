"""Real execution owners + native graphs route held originals; SDK traffic is synthetic."""

import json
from copy import deepcopy
from dataclasses import replace
from uuid import uuid4

import httpx2
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from psycopg.errors import UndefinedTable

from caliburn.adapters.openai_responses import create_responses_client
from caliburn.agent_execution.context_compaction import (
    CompactionSaveError,
    PreparationCountSaveError,
)
from caliburn.agent_execution.tool_steps import InputCountSaveError, ResponseStepSaveError
from caliburn.agents.job_consultant.runner import ConsultantRunner
from caliburn.agents.memory_analysis.dispatch import MemoryRoleDispatch
from caliburn.agents.work_situation_analyst.runner import WorkSituationAnalystRunner
from caliburn.agents.work_understanding_analyst.instructions import UNDERSTANDING_INSTRUCTIONS
from caliburn.agents.work_understanding_analyst.runner import WorkUnderstandingAnalystRunner
from caliburn.features.executions import budgets
from caliburn.features.executions.models import ExecutionStateError
from caliburn.features.job_description import service as jd_service
from caliburn.settings import ModelSettings
from caliburn.workflows.memory_batch import MemoryBatchWorkflow
from caliburn.workflows.memory_consolidation import MemoryConsolidationWorkflow
from tests.integration.test_memory_batch_orchestration import complete_turn, start_turn
from tests.unit.test_context_compaction import COMPACTED
from tests.unit.test_response_loop import response_at
from tests.unit.test_result_save_retries import TransientResultFault

pytestmark = pytest.mark.postgres


class RoleResultFault(TransientResultFault):
    """A B2 fault must not accidentally exercise B1's dispatch branch instead."""

    def __init__(self, channel, role):
        super().__init__(channel, error_type=UndefinedTable)
        self.role = role

    def is_target(self, config):
        return (
            self.role != "b2" or "work_understanding_analyst" in config["configurable"]["thread_id"]
        )

    async def aput(self, config, checkpoint, metadata, new_versions):
        if self.is_target(config):
            return await super().aput(config, checkpoint, metadata, new_versions)
        return await InMemorySaver.aput(self, config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path=""):
        if self.is_target(config):
            await super().aput_writes(config, writes, task_id, task_path)
        else:
            await InMemorySaver.aput_writes(self, config, writes, task_id, task_path)


@pytest.mark.parametrize("role", ["a", "b", "b2"])
@pytest.mark.parametrize(
    "kind", ["response", "step_count", "preparation_count", "compaction", "in_loop_compaction"]
)
def test_roles_reuse_all_four_originals_without_reissuing_or_resetting_budget(client, role, kind):
    async def scenario():
        database = client.app.state.database
        paths = []
        large_next = False
        generations = 0

        def respond(request):
            nonlocal large_next, generations
            paths.append(request.url.path)
            target = (
                role != "b2"
                or json.loads(request.content).get("instructions") == UNDERSTANDING_INSTRUCTIONS
            )
            if request.url.path.endswith("/input_tokens"):
                count = 512_000 if large_next and target else 500
                if target:
                    large_next = False
                return httpx2.Response(
                    200, json={"object": "response.input_tokens", "input_tokens": count}
                )
            if request.url.path.endswith("/compact"):
                raw = deepcopy(COMPACTED)
                raw["usage"]["input_tokens_details"]["cache_write_tokens"] = 0
                return httpx2.Response(200, json=raw)
            if target:
                generations += 1
            final = not target or kind != "in_loop_compaction" or generations > 1
            if not final:
                large_next = True
            raw = response_at(generations, final=final, tools=0).model_dump(mode="json")
            raw["service_tier"] = "default"
            raw["output"][1]["content"][0]["text"] = (
                '{"status":"complete"}' if role != "a" else "原回應"
            )
            return httpx2.Response(200, json=raw)

        saver = RoleResultFault(
            "response_snapshot"
            if kind == "response"
            else "compaction_snapshot"
            if kind in ("compaction", "in_loop_compaction")
            else "input_count",
            role,
        )
        saver.available = True
        sdk = create_responses_client(
            api_key="synthetic",
            timeout_seconds=5,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(respond)),
        )
        settings = ModelSettings(api_key="synthetic")
        a = ConsultantRunner(database.sessions, saver, sdk, settings)
        requests = MemoryConsolidationWorkflow(database.sessions)
        b = MemoryBatchWorkflow(
            database.sessions,
            run_role=MemoryRoleDispatch(
                WorkSituationAnalystRunner(database.sessions, saver, sdk, settings),
                WorkUnderstandingAnalystRunner(database.sessions, saver, sdk, settings),
            ),
        )
        runner = a if role == "a" else b

        async def new_work(file_id=None):
            turn = await start_turn(database, file_id)
            if file_id is None:
                async with database.sessions.begin() as session:
                    await jd_service.create_empty_jd(session, turn.scope.job_file_id)
            if role == "a":
                return turn
            await requests.request(turn, uuid4())
            await complete_turn(database, turn)
            work = await requests.claim((await requests.discover())[0], writer_id=uuid4())
            assert work is not None
            return work.writer

        try:
            writer = await new_work()
            if kind in ("preparation_count", "compaction"):
                await runner.run_supervised(writer)
                writer = await new_work(writer.scope.job_file_id)
                large_next = kind == "compaction"
            saver.available = False
            failure_type = {
                "response": ResponseStepSaveError,
                "step_count": InputCountSaveError,
                "preparation_count": PreparationCountSaveError,
                "compaction": CompactionSaveError,
                "in_loop_compaction": CompactionSaveError,
            }[kind]
            with pytest.raises(failure_type) as failed:
                await runner.run_supervised(writer)
            before = tuple(paths)
            async with database.sessions() as session:
                policy = await budgets.read_execution_budget(session, writer.scope)
            with pytest.raises(ValueError):
                await runner.run_supervised(
                    writer, recovery=replace(failed.value.recovery, thread_id="foreign-scope")
                )
            assert tuple(paths) == before
            with pytest.raises(ExecutionStateError):
                await runner.run_supervised(
                    replace(writer, writer_id=uuid4()), recovery=failed.value.recovery
                )
            assert tuple(paths) == before
            await runner.run_supervised(writer, recovery=failed.value.recovery)
            async with database.sessions() as session:
                assert await budgets.read_execution_budget(session, writer.scope) == policy
            # Only work after the held boundary is allowed; the original call is never repeated.
            remaining = paths[len(before) :]
            if role in ("a", "b2"):
                assert (
                    remaining
                    == {
                        "response": [],
                        "step_count": ["/v1/responses"],
                        "preparation_count": ["/v1/responses/input_tokens", "/v1/responses"],
                        "compaction": ["/v1/responses/input_tokens", "/v1/responses"],
                        "in_loop_compaction": ["/v1/responses/input_tokens", "/v1/responses"],
                    }[kind]
                )
            else:
                # B1 finishes from the original, then B2 executes its distinct stage once.
                assert remaining.count("/v1/responses") == (1 if kind == "response" else 2)
                assert "/v1/responses/compact" not in remaining
        finally:
            await sdk.close()

    client.portal.call(scenario)
