"""Executable prompt examples and role tool access; no natural-language quality grading."""

import json
import re
from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from caliburn.adapters.memory_cpu import MemoryCpu
from caliburn.agents.job_consultant import runner as consultant_runner
from caliburn.agents.job_consultant.instructions import CONSULTANT_INSTRUCTIONS
from caliburn.agents.job_consultant.planning_instructions import (
    INTERVIEW_PLAN_INSTRUCTIONS,
)
from caliburn.agents.job_consultant.runner import ConsultantRunner
from caliburn.agents.job_consultant.tools import consultant_tool_definitions
from caliburn.agents.memory_analysis import runner as analysis_runner
from caliburn.agents.memory_analysis.tools import memory_analysis_tool_definitions
from caliburn.agents.work_situation_analyst.instructions import SITUATION_INSTRUCTIONS
from caliburn.agents.work_situation_analyst.runner import WorkSituationAnalystRunner
from caliburn.agents.work_understanding_analyst.instructions import UNDERSTANDING_INSTRUCTIONS
from caliburn.agents.work_understanding_analyst.runner import WorkUnderstandingAnalystRunner
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionWriter
from caliburn.features.work_memory.candidates import MemoryBatchPosition
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.settings import ModelSettings
from caliburn.workflows.executions.context_history import RoleContextHistory
from caliburn.workflows.work_memory.results import AnalysisComplete, parse_outcome


class CapturedPreparationError(Exception):
    """Stop before history preparation, database work, or network requests."""

    def __init__(self, payload):
        self.payload = payload


@pytest.mark.parametrize(
    ("runner_class", "instructions", "layer", "plans_enabled"),
    [
        (ConsultantRunner, CONSULTANT_INSTRUCTIONS, None, True),
        (ConsultantRunner, CONSULTANT_INSTRUCTIONS, None, False),
        (WorkSituationAnalystRunner, SITUATION_INSTRUCTIONS, MemoryLayer.WORK_SITUATION, False),
        (
            WorkUnderstandingAnalystRunner,
            UNDERSTANDING_INSTRUCTIONS,
            MemoryLayer.WORK_UNDERSTANDING,
            False,
        ),
    ],
    ids=[
        "consultant_with_plan",
        "consultant_guidance_only",
        "work_situation",
        "work_understanding",
    ],
)
@pytest.mark.asyncio
@pytest.mark.parametrize("effort", [None, "low"], ids=["calibrated_default", "explicit_override"])
async def test_real_role_assembly_passes_its_prompt_to_history_template(
    runner_class, instructions, layer, plans_enabled, effort, monkeypatch
) -> None:
    async def capture(self, *, template, **kwargs):
        raise CapturedPreparationError(template.create_payload())

    # Only database/history I/O is replaced. Actual role assembly and definitions run.
    monkeypatch.setattr(RoleContextHistory, "prepare_history", capture)
    monkeypatch.setattr(consultant_runner, "capture_turn_context", capture)
    monkeypatch.setattr(consultant_runner, "fix_execution_policy", AsyncMock())
    monkeypatch.setattr(ConsultantRunner, "_recover_completed", AsyncMock(return_value=None))
    monkeypatch.setattr(analysis_runner, "fix_execution_policy", AsyncMock())
    monkeypatch.setattr(analysis_runner.executions, "lock_active_writer", AsyncMock())
    monkeypatch.setattr(analysis_runner.candidate_queries, "require_stage", AsyncMock())
    sessions = Mock()
    sessions.begin.return_value = MagicMock()
    scope = ExecutionScope(
        uuid4(),
        uuid4(),
        ExecutionKind.CONSULTANT_TURN if layer is None else ExecutionKind.MEMORY_BATCH,
    )
    writer = ExecutionWriter(scope, uuid4())
    settings = (
        ModelSettings(api_key="synthetic-never-sent")
        if effort is None
        else ModelSettings(api_key="synthetic-never-sent", reasoning_effort=effort)
    )
    runner_options = (
        {"interview_plans_enabled": plans_enabled} if layer is None else {"cpu": MemoryCpu()}
    )
    runner = runner_class(sessions, InMemorySaver(), Mock(), settings, **runner_options)
    with pytest.raises(CapturedPreparationError) as captured:
        if layer is None:
            await runner.run(writer)
        else:
            stage = MemoryBatchPosition(
                scope.job_file_id, scope.execution_id, uuid4(), layer, uuid4()
            )
            kwargs = {"situation_changes": []} if layer == MemoryLayer.WORK_UNDERSTANDING else {}
            await runner.run(writer, stage, **kwargs)
    payload = captured.value.payload
    expected = instructions
    if layer is None:
        if plans_enabled:
            expected += "\n\n" + INTERVIEW_PLAN_INSTRUCTIONS
    assert payload["instructions"] == expected
    assert payload["reasoning"]["effort"] == ("high" if effort is None else "low")
    assert payload["input"] == []
    assert payload["tools"]
    assert all(definition["strict"] for definition in payload["tools"])
    if layer is None:
        names = {definition["name"] for definition in payload["tools"]}
        assert ("read_interview_plan" in names) == plans_enabled
        assert ("edit_interview_plan" in names) == plans_enabled
    if layer is not None:
        # Required analysis boundary reaches the real role assembly. Natural adherence
        # is evaluated separately; these literals do not grade employee facts.
        assert "更正只套用明確涉及的範圍" in payload["instructions"]
        assert "不能自動採信最後一句" in payload["instructions"]


@pytest.mark.parametrize(
    ("instructions", "layer", "expected_statuses"),
    [
        (SITUATION_INSTRUCTIONS, MemoryLayer.WORK_SITUATION, ["complete"]),
        (
            UNDERSTANDING_INSTRUCTIONS,
            MemoryLayer.WORK_UNDERSTANDING,
            ["complete"],
        ),
    ],
)
def test_model_copying_prompt_json_examples_will_satisfy_actual_outcome_parser(
    instructions, layer, expected_statuses
) -> None:
    examples = re.findall(r'\{"status":.*\}', instructions)
    assert [json.loads(example)["status"] for example in examples] == expected_statuses
    for example in examples:
        assert isinstance(parse_outcome(example), AnalysisComplete)


@pytest.mark.parametrize("layer", list(MemoryLayer))
def test_analysis_prompt_roles_only_offer_their_permitted_write_layer(layer) -> None:
    definitions = memory_analysis_tool_definitions(layer)
    names = {definition["name"] for definition in definitions}
    assert {name for name in names if not name.startswith("read_")} == {
        f"create_{layer.value}",
        f"update_{layer.value}",
        f"delete_{layer.value}",
    }
    assert ("read_work_understanding" in names) == (layer == MemoryLayer.WORK_UNDERSTANDING)
    assert ("read_work_understanding_map" in names) == (layer == MemoryLayer.WORK_UNDERSTANDING)
    assert "read_interview" in names
    assert all(definition["strict"] for definition in definitions)


def test_consultant_can_read_both_layers_but_cannot_write_private_memory() -> None:
    definitions = consultant_tool_definitions()
    names = {definition["name"] for definition in definitions}
    assert {
        "read_work_situation",
        "read_work_understanding",
        "read_interview",
        "read_jd",
        "revise_jd_profile",
        "revise_jd_item",
        "request_memory_consolidation",
    } <= names
    assert not any(
        name.startswith(("create_work_", "update_work_", "delete_work_")) for name in names
    )
    assert all(definition["strict"] for definition in definitions)
