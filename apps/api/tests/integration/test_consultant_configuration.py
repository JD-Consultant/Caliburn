"""提示／工具候選走正式 Runner，已保存回合保留原配置及能力。"""

from dataclasses import replace

import pytest

from caliburn.agents.job_consultant.configuration import (
    ConsultantConfiguration,
    ConsultantPrompts,
    ToolDescriptionOverride,
)
from caliburn.agents.job_consultant.context_binding import read_saved_turn_context
from caliburn.agents.job_consultant.runner import ConsultantRunner
from caliburn.features.executions import history
from caliburn.features.executions.models import ExecutionStatus
from caliburn.settings import ModelSettings
from caliburn.transport.model_tools.jd_reads import JdReadTools
from caliburn.workflows.consultant_turns.completion import ConsultantCompletionWorkflow
from caliburn.workflows.executions.context_history import RoleContextHistory
from tests.integration.test_occupation_reference_runners import (
    ReferenceTransport,
    ScriptedModel,
    native_clients,
)
from tests.integration.test_occupation_reference_workflow import new_writer

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("original_plans", [False, True])
@pytest.mark.parametrize("boundary", ["preparation", "tool", "reused_capture"])
def test_saved_turn_keeps_original_configuration_after_candidate_change(
    client, database_settings, monkeypatch, original_plans, boundary
):
    writer = new_writer(client)
    script = ScriptedModel(
        [([("read_jd", {"view": "map", "read_ref": None})], None), ([], "原回合完成。")]
    )
    old = ConsultantConfiguration(
        jd_read_max_result_characters=1,
        prompts=replace(ConsultantPrompts(), professional_method="原候選：先核對真實事件。"),
        tool_descriptions=(
            ToolDescriptionOverride("read_jd", "原候選的讀取說明"),
            *(
                (ToolDescriptionOverride("edit_interview_plan", "原計畫說明"),)
                if original_plans
                else ()
            ),
        ),
    )
    changed = replace(
        old,
        jd_read_max_result_characters=1_000_000,
        prompts=replace(old.prompts, professional_method="新候選：改問另一個重點。"),
        tool_descriptions=(
            ToolDescriptionOverride("read_jd", "新候選的讀取說明"),
            *old.tool_descriptions[1:],
        ),
    )

    async def interrupt(*args, **kwargs):
        raise RuntimeError("synthetic saved boundary interruption")

    if boundary == "reused_capture":
        cancelled_writer = writer

        async def cancel_after_preparation():
            sessions = client.app.state.database.sessions
            async with native_clients(database_settings, script, ReferenceTransport()) as (
                saver,
                sdk,
                _provider,
            ):
                runner = ConsultantRunner(sessions, saver, sdk, ModelSettings(api_key="synthetic"))
                prepare = RoleContextHistory.prepare_history

                async def interrupt_after_preparation(*args, **kwargs):
                    await prepare(*args, **kwargs)
                    await interrupt()

                with monkeypatch.context() as crash:
                    crash.setattr(
                        RoleContextHistory, "prepare_history", interrupt_after_preparation
                    )
                    with pytest.raises(RuntimeError, match="saved boundary"):
                        await runner.run(cancelled_writer)
                await ConsultantCompletionWorkflow(sessions).stop(
                    cancelled_writer, ExecutionStatus.CANCELLED
                )

        client.portal.call(cancel_after_preparation)
        writer = new_writer(client, cancelled_writer.scope.job_file_id)

    async def scenario():
        sessions = client.app.state.database.sessions
        async with native_clients(database_settings, script, ReferenceTransport()) as (
            saver,
            sdk,
            _provider,
        ):
            runner = ConsultantRunner(
                sessions,
                saver,
                sdk,
                ModelSettings(api_key="synthetic"),
                interview_plans_enabled=original_plans,
                configuration=old,
            )
            with monkeypatch.context() as crash:
                if boundary == "preparation":
                    crash.setattr(history, "adopt_prepared_context", interrupt)
                else:
                    crash.setattr(JdReadTools, "invoke", interrupt)
                with pytest.raises(RuntimeError, match="saved boundary"):
                    await runner.run(writer)
            await replace(
                runner,
                configuration=changed,
                interview_plans_enabled=not original_plans,
            ).run(writer)
            captured = await read_saved_turn_context(saver, writer.scope)
            assert (captured.plan_position is not None) == original_plans
            assert len(script.sent) == 2
            for payload in script.sent:
                assert "原候選：先核對真實事件。" in payload["instructions"]
                assert "新候選：" not in payload["instructions"]
                tools = {tool["name"]: tool for tool in payload["tools"]}
                assert tools["read_jd"]["description"] == "原候選的讀取說明"
                assert ("edit_interview_plan" in tools) == original_plans
            assert captured.request.create_payload()["tools"] == script.sent[0]["tools"]
            # Initial capture now fixes tool policy before history preparation can suspend.
            assert captured.jd_read_max_result_characters == 1
            tool_output = script.sent[1]["input"][-1]["output"]
            assert "read_limit_exceeded" in tool_output

    client.portal.call(scenario)
