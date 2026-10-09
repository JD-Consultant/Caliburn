"""Opt-in references through real role runners, native checkpoints and isolated PostgreSQL."""

import json
from contextlib import asynccontextmanager
from dataclasses import replace
from uuid import uuid4

import httpx2
import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.memory_cpu import MemoryCpu
from caliburn.adapters.occupation_references import OccupationReferenceClient
from caliburn.adapters.openai_responses import create_responses_client
from caliburn.agents.job_consultant import runner as consultant_runner_module
from caliburn.agents.job_consultant.runner import ConsultantRunner
from caliburn.agents.work_situation_analyst.runner import WorkSituationAnalystRunner
from caliburn.agents.work_understanding_analyst.runner import WorkUnderstandingAnalystRunner
from caliburn.features.executions import history
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionStatus,
)
from caliburn.features.occupation_references import service as references
from caliburn.settings import ModelSettings
from caliburn.transport.model_tools.memory_analysis import MEMORY_CHECKPOINT_TYPES
from caliburn.transport.model_tools.occupation_references import (
    OccupationReferenceTools,
    occupation_reference_definitions,
)
from caliburn.workflows.consultant_completion import ConsultantCompletionWorkflow
from caliburn.workflows.memory_candidates import MemoryCandidateWorkflow
from tests.fixtures.response_loop import response_at
from tests.integration.test_occupation_reference_workflow import new_writer
from tests.unit.test_occupation_reference_client import (
    REFERENCE_ID,
    reference_payload,
    search_payload,
    task_payload,
)

pytestmark = pytest.mark.postgres

EXCLUSION = "正式環境部署由維運負責，本人不執行部署"
QUERY = "本人負責網站功能開發，處理畫面與資料介接"
REFERENCE_NAMES = set(OccupationReferenceTools.names)


class ScriptedModel:
    def __init__(self, scripts):
        self.scripts = scripts
        self.sent = []

    def respond(self, request):
        payload = json.loads(request.content)
        if request.url.path.endswith("/input_tokens"):
            return httpx2.Response(
                200, json={"object": "response.input_tokens", "input_tokens": 500}
            )
        assert request.url.path.endswith("/responses")
        self.sent.append(payload)
        calls, final = self.scripts[len(self.sent) - 1]
        raw = response_at(len(self.sent), final=final is not None, tools=0).model_dump(mode="json")
        raw["service_tier"] = "default"
        for index, (name, arguments) in enumerate(calls):
            raw["output"].append(
                {
                    "type": "function_call",
                    "id": f"fc_{len(self.sent)}_{index}",
                    "call_id": f"call_{len(self.sent)}_{index}",
                    "name": name,
                    "arguments": json.dumps(arguments, ensure_ascii=False),
                }
            )
        if final is not None:
            raw["output"][1]["content"][0]["text"] = final
        return httpx2.Response(200, json=raw)


class ReferenceTransport:
    def __init__(self):
        self.requests = []
        self.offline = False

    def respond(self, request):
        self.requests.append((request.method, request.url.path))
        assert not self.offline, "Saved reference operations must replay without HTTP"
        if request.method == "POST":
            assert json.loads(request.content) == {"query": QUERY, "limit": 5}
            return httpx2.Response(200, json=search_payload())
        if request.url.path.endswith("/tasks/u1-t1"):
            return httpx2.Response(200, json=task_payload())
        assert request.url.path == f"/occupation-references/{REFERENCE_ID}"
        return httpx2.Response(200, json=reference_payload())


@asynccontextmanager
async def native_clients(settings, script, transport):
    dsn = make_conninfo(settings.url, options=f"-c search_path={settings.schema}")
    async with (
        AsyncPostgresSaver.from_conn_string(
            dsn, serde=create_graph_serializer(allowed_types=MEMORY_CHECKPOINT_TYPES)
        ) as saver,
        httpx2.AsyncClient(
            base_url="http://references.invalid", transport=httpx2.MockTransport(transport.respond)
        ) as http,
    ):
        await saver.setup()
        sdk = create_responses_client(
            api_key="synthetic-no-network",
            timeout_seconds=5,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(script.respond)),
        )
        try:
            yield saver, sdk, OccupationReferenceClient(http)
        finally:
            await sdk.close()


def observations(payload):
    return [
        json.loads(item["output"])
        for item in payload["input"]
        if item.get("type") == "function_call_output"
    ]


def initial_calls():
    return [
        ("search_occupation_references", {"query": QUERY}),
        ("read_occupation_reference", {"reference_id": REFERENCE_ID, "task_id": "u1-t1"}),
        ("select_occupation_references", {"reference_ids": [REFERENCE_ID]}),
        ("update_excluded_work", {"add": [EXCLUSION], "remove": []}),
        ("read_occupation_reference_state", {}),
    ]


def test_enabled_consultant_persists_references_and_both_memory_roles_read_only(
    client, database_settings
):
    writer = new_writer(client)
    script = ScriptedModel(
        [
            (initial_calls(), None),
            ([], "已確認本人工作與部署分工。"),
            (
                [
                    ("read_excluded_work", {}),
                    ("update_excluded_work", {"add": [], "remove": [EXCLUSION]}),
                ],
                None,
            ),
            ([], '{"status":"complete"}'),
            (
                [
                    ("read_excluded_work", {}),
                    ("select_occupation_references", {"reference_ids": []}),
                ],
                None,
            ),
            ([], '{"status":"complete"}'),
            ([("read_occupation_reference_state", {})], None),
            ([], "沿用既有參考。"),
        ]
    )
    transport = ReferenceTransport()

    async def scenario():
        sessions = client.app.state.database.sessions
        settings = ModelSettings(api_key="synthetic")
        async with native_clients(database_settings, script, transport) as (saver, sdk, provider):
            runner = ConsultantRunner(
                sessions, saver, sdk, settings, occupation_references=provider
            )
            exchange = await runner.run(writer)
            assert REFERENCE_NAMES <= {tool["name"] for tool in script.sent[0]["tools"]}
            assert observations(script.sent[1])[-1] == {
                "selected_reference_ids": [REFERENCE_ID],
                "excluded_work": [EXCLUSION],
            }
            scope = ExecutionScope(writer.scope.job_file_id, uuid4(), ExecutionKind.MEMORY_BATCH)
            async with sessions.begin() as session:
                await executions.admit_execution(session, scope)
                memory_writer = await executions.claim_writer(session, scope, writer_id=uuid4())
            candidates = MemoryCandidateWorkflow(sessions)
            stage = await candidates.start(memory_writer, exchange.employee_input.source_id)
            assert stage is not None
            b1 = WorkSituationAnalystRunner(
                sessions, saver, sdk, settings, excluded_work_enabled=True, cpu=MemoryCpu()
            )
            first = await b1.run(memory_writer, stage)
            second_stage = await candidates.handoff(memory_writer, first.stage, uuid4())
            b2 = WorkUnderstandingAnalystRunner(
                sessions, saver, sdk, settings, excluded_work_enabled=True, cpu=MemoryCpu()
            )
            await b2.run(memory_writer, second_stage, situation_changes=[])
            for index in (2, 4):
                names = {tool["name"] for tool in script.sent[index]["tools"]}
                assert "read_excluded_work" in names
                assert names.isdisjoint(REFERENCE_NAMES)
                results = observations(script.sent[index + 1])
                assert results[-2] == {"excluded_work": [EXCLUSION]}
                assert results[-1]["code"] == "scope_not_allowed"

    # A later consultant Turn is driven in a new native-client lifetime below.
    # This also proves storage, rather than Python object retention, carries the state.
    client.portal.call(scenario)
    next_writer = new_writer(client, writer.scope.job_file_id)

    async def next_turn():
        async with native_clients(database_settings, script, transport) as (saver, sdk, provider):
            runner = ConsultantRunner(
                client.app.state.database.sessions,
                saver,
                sdk,
                ModelSettings(api_key="synthetic"),
                occupation_references=provider,
            )
            await runner.run(next_writer)

    client.portal.call(next_turn)
    assert observations(script.sent[7])[-1] == {
        "selected_reference_ids": [REFERENCE_ID],
        "excluded_work": [EXCLUSION],
    }
    assert len(transport.requests) == 3


@pytest.mark.parametrize("outcome", ["resume", "cancel", "fail"])
@pytest.mark.parametrize("description", ["候選工具說明", "直接保存這次已確認的參考选择"])
def test_committed_reference_command_recovers_or_stays_out_of_formal_state(
    client, database_settings, monkeypatch, outcome, description
):
    writer = new_writer(client)
    script = ScriptedModel([(initial_calls(), None), ([], "已確認。")])
    transport = ReferenceTransport()
    original_execute = OccupationReferenceTools.execute
    interrupted = False

    async def commit_then_interrupt(self, prepared):
        nonlocal interrupted
        result = await original_execute(self, prepared)
        if prepared["change"]["state"]["excluded_work"] == [EXCLUSION] and not interrupted:
            interrupted = True
            raise RuntimeError("synthetic interruption after state commit")
        return result

    monkeypatch.setattr(OccupationReferenceTools, "execute", commit_then_interrupt)

    async def scenario():
        sessions = client.app.state.database.sessions
        async with native_clients(database_settings, script, transport) as (saver, sdk, provider):
            runner = ConsultantRunner(
                sessions,
                saver,
                sdk,
                ModelSettings(api_key="synthetic"),
                occupation_references=provider,
            )
            original_definitions = consultant_runner_module.consultant_tool_definitions

            def captured_definitions(
                *, occupation_references_enabled=False, interview_plans_enabled=True
            ):
                definitions = original_definitions(interview_plans_enabled=interview_plans_enabled)
                if occupation_references_enabled:
                    references = occupation_reference_definitions()
                    for definition in references:
                        definition["description"] = description
                    definitions += references
                return definitions

            # Resume with today's descriptions after capturing this new request's wording.
            with monkeypatch.context() as patch:
                patch.setattr(
                    consultant_runner_module,
                    "consultant_tool_definitions",
                    captured_definitions,
                )
                with pytest.raises(RuntimeError, match="after state commit"):
                    await runner.run(writer)
            assert len(script.sent) == 1
            assert len(transport.requests) == 3
            async with sessions() as session:
                saved = await references.read_candidate(
                    session, writer.scope.job_file_id, writer.scope.execution_id
                )
                assert saved is not None and saved.state.excluded_work == (EXCLUSION,)
            transport.offline = True
            if outcome == "resume":
                # A missing provider cannot resume a request that previously exposed its tools.
                with pytest.raises(ExecutionStateError, match="reference client"):
                    await replace(runner, occupation_references=None).run(writer)
                assert len(script.sent) == 1
                await runner.run(writer)
                assert len(script.sent) == 2
                assert script.sent[1]["tools"] == script.sent[0]["tools"]
                # Selection finished and its native output was saved before interruption.
                # Today's handler must not reproject that historical output.
                expected_selection = {"status": "updated"}
                assert observations(script.sent[1])[2] == expected_selection
                expected_write = {"status": "updated"}
                assert observations(script.sent[1])[-2] == expected_write
                assert observations(script.sent[1])[-1]["excluded_work"] == [EXCLUSION]
            else:
                status = (
                    ExecutionStatus.CANCELLED if outcome == "cancel" else ExecutionStatus.FAILED
                )
                await ConsultantCompletionWorkflow(sessions).stop(writer, status)
        assert len(transport.requests) == 3

    client.portal.call(scenario)
    next_writer = new_writer(client, writer.scope.job_file_id)
    followup = ScriptedModel([([("read_occupation_reference_state", {})], None), ([], "已讀取。")])

    async def verify_next():
        async with native_clients(database_settings, followup, transport) as (saver, sdk, provider):
            runner = ConsultantRunner(
                client.app.state.database.sessions,
                saver,
                sdk,
                ModelSettings(api_key="synthetic"),
                occupation_references=provider,
            )
            await runner.run(next_writer)

    client.portal.call(verify_next)
    expected = (
        {"selected_reference_ids": [REFERENCE_ID], "excluded_work": [EXCLUSION]}
        if outcome == "resume"
        else {"selected_reference_ids": None, "excluded_work": []}
    )
    assert observations(followup.sent[1])[-1] == expected


def test_enabling_references_does_not_change_an_interrupted_old_preparation(
    client, database_settings, monkeypatch
):
    writer = new_writer(client)
    script = ScriptedModel([([], "依原有工具完成。")])
    transport = ReferenceTransport()

    async def interrupt_adoption(*args, **kwargs):
        raise RuntimeError("synthetic interruption before preparation adoption")

    async def scenario():
        sessions = client.app.state.database.sessions
        async with native_clients(database_settings, script, transport) as (saver, sdk, provider):
            old_runner = ConsultantRunner(sessions, saver, sdk, ModelSettings(api_key="synthetic"))
            with monkeypatch.context() as interruption:
                interruption.setattr(history, "adopt_prepared_context", interrupt_adoption)
                with pytest.raises(RuntimeError, match="before preparation adoption"):
                    await old_runner.run(writer)
            assert script.sent == []
            await replace(old_runner, occupation_references=provider).run(writer)
            assert len(script.sent) == 1
            assert REFERENCE_NAMES.isdisjoint(tool["name"] for tool in script.sent[0]["tools"])
            async with sessions() as session:
                assert (
                    await references.read_candidate(
                        session, writer.scope.job_file_id, writer.scope.execution_id
                    )
                    is None
                )
            assert transport.requests == []

    client.portal.call(scenario)
