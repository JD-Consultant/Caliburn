"""正式角色經 create_agent 與 SDK 送出完整契約；provider 替身搭配隔離 PostgreSQL。"""

import json
from uuid import uuid4

import pytest

from caliburn.adapters.memory_cpu import MemoryCpu
from caliburn.agents.job_consultant.instructions import CONSULTANT_INSTRUCTIONS
from caliburn.agents.job_consultant.planning_instructions import INTERVIEW_PLAN_INSTRUCTIONS
from caliburn.agents.job_consultant.reference_instructions import OCCUPATION_REFERENCE_INSTRUCTIONS
from caliburn.agents.job_consultant.runner import ConsultantRunner
from caliburn.agents.job_consultant.tools import consultant_tool_definitions
from caliburn.agents.work_situation_analyst.instructions import SITUATION_INSTRUCTIONS
from caliburn.agents.work_situation_analyst.runner import WorkSituationAnalystRunner
from caliburn.agents.work_understanding_analyst.instructions import UNDERSTANDING_INSTRUCTIONS
from caliburn.agents.work_understanding_analyst.runner import WorkUnderstandingAnalystRunner
from caliburn.features.executions import service as executions
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.settings import ModelSettings
from caliburn.workflows.work_memory.candidates import MemoryCandidateWorkflow
from tests.integration.test_occupation_reference_runners import (
    ReferenceTransport,
    ScriptedModel,
    native_clients,
)
from tests.integration.test_occupation_reference_workflow import new_writer

pytestmark = pytest.mark.postgres


def assert_tool_results_reach_next_request(first, following, expected_names):
    """核對 HTTP 邊界的原生歷史、工具呼叫與實際結果配對。"""
    assert following["input"][: len(first["input"])] == first["input"]
    calls = [item for item in following["input"] if item.get("type") == "function_call"]
    results = [item for item in following["input"] if item.get("type") == "function_call_output"]
    assert [call["name"] for call in calls] == expected_names
    assert [item["call_id"] for item in results] == [call["call_id"] for call in calls]
    assert all("rejected" not in item["output"] for item in results)
    assert following["tools"] == first["tools"]
    assert following["instructions"] == first["instructions"]
    return [json.loads(item["output"]) for item in results]


@pytest.mark.parametrize("plans", [False, True])
@pytest.mark.parametrize("references", [False, True])
def test_consultant_provider_receives_complete_enabled_bundle_and_tool_results(
    client, database_settings, tmp_path, plans, references
):
    writer = new_writer(client)
    calls = [
        ("read_jd", {"view": "map", "read_ref": None}),
        ("read_work_situation_map", {}),
        ("read_work_understanding_map", {}),
    ]
    if plans:
        calls.append(("read_interview_plan", {}))
    script = ScriptedModel([(calls, None), ([], "已核對目前導覽，請說明具體工作。")])
    transport = ReferenceTransport()

    async def scenario():
        async with native_clients(database_settings, script, transport) as (saver, sdk, provider):
            runner = ConsultantRunner(
                client.app.state.database.sessions,
                saver,
                sdk,
                ModelSettings(api_key="synthetic-no-network"),
                interview_plans_enabled=plans,
                occupation_references=provider if references else None,
            )
            await runner.run(writer)

    client.portal.call(scenario)
    assert len(script.sent) == 2
    initial, following = script.sent
    sections = [CONSULTANT_INSTRUCTIONS]
    if plans:
        sections.append(INTERVIEW_PLAN_INSTRUCTIONS)
    if references:
        sections.append(OCCUPATION_REFERENCE_INSTRUCTIONS)
    assert initial["instructions"] == "\n\n".join(sections)
    assert all(initial["instructions"].count(section) == 1 for section in sections)
    # 比對完整 SDK JSON，涵蓋欄位說明、enum 及巢狀 $defs；
    # provider 定義來自固定請求，不能以 StructuredTool registry 代替。
    assert initial["tools"] == consultant_tool_definitions(
        interview_plans_enabled=plans, occupation_references_enabled=references
    )
    results = assert_tool_results_reach_next_request(
        initial, following, [name for name, _ in calls]
    )
    assert results[1:3] == [{"items": []}, {"items": []}]
    if plans:
        assert results[-1] == {"plan": None}
    assert transport.requests == []
    (tmp_path / "provider-payloads.json").write_text(
        json.dumps(script.sent, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def test_background_provider_receives_shared_read_contracts_with_its_role_permissions(
    client, database_settings, tmp_path
):
    writer = new_writer(client)
    script = ScriptedModel(
        [
            ([], "已了解工作範圍。"),
            ([("read_work_situation_map", {})], None),
            ([], '{"status":"complete"}'),
            ([("read_work_situation_map", {}), ("read_work_understanding_map", {})], None),
            ([], '{"status":"complete"}'),
        ]
    )

    async def scenario():
        sessions = client.app.state.database.sessions
        async with native_clients(database_settings, script, ReferenceTransport()) as (
            saver,
            sdk,
            _provider,
        ):
            settings = ModelSettings(api_key="synthetic-no-network")
            exchange = await ConsultantRunner(sessions, saver, sdk, settings).run(writer)
            scope = ExecutionScope(writer.scope.job_file_id, uuid4(), ExecutionKind.MEMORY_BATCH)
            async with sessions.begin() as session:
                await executions.admit_execution(session, scope)
                memory_writer = await executions.claim_writer(session, scope, writer_id=uuid4())
            candidates = MemoryCandidateWorkflow(sessions)
            stage = await candidates.start(memory_writer, exchange.employee_input.source_id)
            assert stage is not None
            await WorkSituationAnalystRunner(sessions, saver, sdk, settings, cpu=MemoryCpu()).run(
                memory_writer, stage
            )
            stage2 = await candidates.handoff(memory_writer, stage, uuid4())
            await WorkUnderstandingAnalystRunner(
                sessions, saver, sdk, settings, cpu=MemoryCpu()
            ).run(memory_writer, stage2, situation_changes=[])

    client.portal.call(scenario)
    assert len(script.sent) == 5
    consultant = {tool["name"]: tool for tool in script.sent[0]["tools"]}
    for index, instructions, layer, reads in [
        (1, SITUATION_INSTRUCTIONS, MemoryLayer.WORK_SITUATION, ["read_work_situation_map"]),
        (
            3,
            UNDERSTANDING_INSTRUCTIONS,
            MemoryLayer.WORK_UNDERSTANDING,
            ["read_work_situation_map", "read_work_understanding_map"],
        ),
    ]:
        payload, following = script.sent[index : index + 2]
        assert payload["instructions"] == instructions
        tools = {tool["name"]: tool for tool in payload["tools"]}
        shared = {name for name in tools if name in consultant}
        assert shared
        assert all(tools[name] == consultant[name] for name in shared)
        assert {name for name in tools if not name.startswith("read_")} == {
            f"create_{layer.value}",
            f"update_{layer.value}",
            f"delete_{layer.value}",
        }
        assert ("read_work_understanding" in tools) == (layer == MemoryLayer.WORK_UNDERSTANDING)
        assert assert_tool_results_reach_next_request(payload, following, reads) == [
            {"items": []} for _ in reads
        ]
    (tmp_path / "provider-payloads.json").write_text(
        json.dumps(script.sent, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
