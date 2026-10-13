"""真 create_agent／JD codec 分辨模型輸入拒絕與注入的內部故障。"""

import json
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from pydantic import TypeAdapter, ValidationError

from caliburn.agents.job_consultant.tools import ConsultantTools
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionWriter
from caliburn.features.job_description.candidates import JdCandidateScope
from caliburn.features.job_description.compound_edits import (
    JdCompoundEditResult,
    ReviseProfileWithSources,
)
from caliburn.transport.model_tools import jd_writes
from caliburn.transport.model_tools.jd_changes import JdChangesTools
from caliburn.transport.model_tools.jd_writes import JdWriteTools
from caliburn.workflows.job_description.compound_writes import PreparedJdEdit
from caliburn.workflows.work_memory.reads import PublishedMemoryRead
from tests.fixtures.response_loop import LoopProbe, initial_request, response_at
from tests.unit.test_occupation_reference_tools import bound_tools


def internal_fault():
    TypeAdapter(int).validate_python("injected internal validation fault")


def jd_owner(phase=None):
    scope = ExecutionScope(uuid4(), uuid4(), ExecutionKind.CONSULTANT_TURN)
    writer = ExecutionWriter(scope, uuid4())
    binding = PublishedMemoryRead(scope, None, 1)
    effects = []

    async def resolve(refs):
        if phase == "references":
            internal_fault()
        return {ref: ref for ref in refs}

    async def prepare(binding, *, command_id, changes, sources):
        if phase == "prepare":
            internal_fault()
        return PreparedJdEdit(
            JdCandidateScope(scope.execution_id),
            ReviseProfileWithSources(command_id, uuid4(), changes, sources),
        )

    async def execute(writer, prepared):
        effects.append(prepared.command.command_id)
        if phase == "execute":
            internal_fault()
        return JdCompoundEditResult(uuid4(), "updated")

    tools = JdWriteTools(
        SimpleNamespace(prepare=prepare),
        None,
        binding,
        writer,
        references=SimpleNamespace(resolve=resolve),
        execute_edit=execute,
        creations=None,
        revisions=None,
        deletions=None,
        movements=None,
    )
    return tools, effects


async def run_jd(tools, arguments, *, corrupt_restore=False):
    # ConsultantTools 使用正式 snapshot／restore；其餘角色工具不參與本案。
    async def unused(*args):
        raise AssertionError("unexpected unrelated tool")

    empty = SimpleNamespace(definitions=lambda: [], invoke=unused, execute=unused)
    consultant = ConsultantTools(empty, empty, tools, empty, empty, empty)
    first = response_at(1, tools=1)
    first.output[-1].name = "revise_jd_profile"
    first.output[-1].arguments = arguments
    probe = LoopProbe([first, response_at(2, final=True)])
    native = consultant.standard_tools(probe.guard)
    if corrupt_restore:
        # 故障注入只改 codec 的保存原件，不冒充自然 DB 損毀。
        from caliburn.agents.job_consultant import tools as composition

        original = composition.snapshot_jd_write
        with pytest.MonkeyPatch.context() as patch:

            def corrupt(prepared):
                saved = original(prepared)
                saved["payload"] = "{}"
                return saved

            patch.setattr(composition, "snapshot_jd_write", corrupt)
            return await invoke(probe, native), probe
    return await invoke(probe, native), probe


async def invoke(probe, native):
    from caliburn.agent_execution.native_agent import run_native_agent

    return await run_native_agent(
        InMemorySaver(),
        thread_id=str(uuid4()),
        request=initial_request(),
        runtime=probe.runtime(),
        tools=native,
        unknown_tool_output="unknown",
        max_tool_calls=2,
        max_model_steps=2,
    )


VALID_PROFILE = '{"changes":[{"action":"set_field","field":"job_title","value":"工程師"}]}'


@pytest.mark.parametrize("arguments", ["{", "{}", '{"changes":[]}'])
async def test_jd_invalid_input_reaches_next_model_without_effect(arguments):
    tools, effects = jd_owner()
    result, probe = await run_jd(tools, arguments)
    assert result["completed_steps"] == 2
    assert effects == []
    outputs = [
        item for item in probe.requests[1]["input"] if item.get("type") == "function_call_output"
    ]
    assert json.loads(outputs[0]["output"])["code"] == "invalid_arguments"


@pytest.mark.parametrize("phase", ["references", "prepare", "execute", "render", "restore"])
async def test_jd_internal_validation_stops_create_agent(phase, monkeypatch):
    tools, effects = jd_owner(phase)
    if phase == "render":

        async def render(*args):
            internal_fault()

        monkeypatch.setattr(jd_writes, "render_jd_write_result", render)
    requests = []
    original = LoopProbe.request

    async def observe(self, *args):
        requests.append(args[1])
        return await original(self, *args)

    monkeypatch.setattr(LoopProbe, "request", observe)
    with pytest.raises(RuntimeError, match="Internal tool validation failed") as error:
        await run_jd(tools, VALID_PROFILE, corrupt_restore=phase == "restore")
    assert isinstance(error.value.__cause__, ValidationError)
    assert len(requests) == 1
    assert len(effects) == (1 if phase in ("execute", "render") else 0)


async def test_reference_workflow_validation_is_internal():
    tools, workflow, _ = bound_tools()

    async def prepare(*args):
        internal_fault()

    workflow.prepare_select = prepare
    with pytest.raises(ValidationError):
        await tools.prepare("select_occupation_references", '{"reference_ids":[]}', uuid4())


async def test_jd_changes_reference_validation_is_internal():
    tools, _ = jd_owner("references")
    changes = JdChangesTools(
        None,
        tools.binding,
        references=tools.references,
    )
    with pytest.raises(ValidationError):
        await changes.invoke(
            "read_jd_changes", '{"query":{"kind":"source","citation_ref":"citation_known"}}'
        )
