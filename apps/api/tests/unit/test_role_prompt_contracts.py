"""Executable prompt examples and role tool access; no natural-language quality grading."""

import json
import re
from unittest.mock import AsyncMock, MagicMock, Mock
from uuid import uuid4

import pytest

from caliburn.agents.job_consultant import runner as consultant_runner
from caliburn.agents.job_consultant.instructions import CONSULTANT_INSTRUCTIONS
from caliburn.agents.job_consultant.runner import ConsultantRunner
from caliburn.agents.job_consultant.tools import consultant_tool_definitions
from caliburn.agents.memory_analysis import runner as analysis_runner
from caliburn.agents.work_situation_analyst.instructions import SITUATION_INSTRUCTIONS
from caliburn.agents.work_situation_analyst.runner import WorkSituationAnalystRunner
from caliburn.agents.work_understanding_analyst.instructions import UNDERSTANDING_INSTRUCTIONS
from caliburn.agents.work_understanding_analyst.runner import WorkUnderstandingAnalystRunner
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionWriter
from caliburn.features.work_memory.candidates import MemoryBatchPosition
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.settings import ModelSettings
from caliburn.transport.model_tools.memory_analysis import memory_analysis_tool_definitions
from caliburn.workflows.context_history import RoleContextHistory
from caliburn.workflows.memory_analysis.results import AnalysisComplete, parse_outcome


class CapturedPreparationError(Exception):
    """Stop at the first history I/O boundary, before any network or checkpoint work."""

    def __init__(self, payload):
        self.payload = payload


@pytest.mark.parametrize(
    ("runner_class", "instructions", "layer"),
    [
        (ConsultantRunner, CONSULTANT_INSTRUCTIONS, None),
        (WorkSituationAnalystRunner, SITUATION_INSTRUCTIONS, MemoryLayer.WORK_SITUATION),
        (
            WorkUnderstandingAnalystRunner,
            UNDERSTANDING_INSTRUCTIONS,
            MemoryLayer.WORK_UNDERSTANDING,
        ),
    ],
    ids=["consultant", "work_situation", "work_understanding"],
)
@pytest.mark.asyncio
@pytest.mark.parametrize("effort", [None, "low"], ids=["calibrated_default", "explicit_override"])
async def test_real_role_assembly_passes_its_prompt_to_history_template(
    runner_class, instructions, layer, effort, monkeypatch
) -> None:
    async def capture(self, *, template, **kwargs):
        raise CapturedPreparationError(template.create_payload())

    # Only database/history I/O is replaced. Actual role assembly and definitions run.
    monkeypatch.setattr(RoleContextHistory, "prepare_history", capture)
    monkeypatch.setattr(consultant_runner, "fix_execution_policy", AsyncMock())
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
    runner = runner_class(sessions, Mock(), Mock(), settings)
    with pytest.raises(CapturedPreparationError) as captured:
        if layer is None:
            await runner.run(writer)
        else:
            stage = MemoryBatchPosition(
                scope.job_file_id, scope.execution_id, uuid4(), uuid4(), layer, uuid4()
            )
            kwargs = {"situation_changes": []} if layer == MemoryLayer.WORK_UNDERSTANDING else {}
            await runner.run(writer, stage, **kwargs)
    payload = captured.value.payload
    assert payload["instructions"] == instructions
    assert payload["reasoning"]["effort"] == ("high" if effort is None else "low")
    assert payload["input"] == []
    assert payload["tools"]
    assert all(definition["strict"] for definition in payload["tools"])
    if layer == MemoryLayer.WORK_SITUATION:
        # Literal input contract at the real consumer boundary, not a quality grader.
        # Dropping either selection or anti-duplication guidance must be visible here.
        assert "保留有助辨認本人角色、服務範圍或責任界線的已知工作背景" in payload["instructions"]
        assert "共用背景不必每案重複完整職務資料" in payload["instructions"]
        assert "未說明的背景仍是未知，不為填滿職務資料而補造" in payload["instructions"]
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
            ["complete", "needs_situation"],
        ),
    ],
)
def test_model_copying_prompt_json_examples_will_satisfy_actual_outcome_parser(
    instructions, layer, expected_statuses
) -> None:
    examples = re.findall(r'\{"status":.*\}', instructions)
    assert [json.loads(example)["status"] for example in examples] == expected_statuses
    for example in examples:
        outcome = parse_outcome(example, layer)
        if not isinstance(outcome, AnalysisComplete):
            assert outcome.gaps
            for gap in outcome.gaps:
                assert gap.model_dump().keys() == {
                    "target_title",
                    "question",
                    "needed_clarification",
                    "interview_sequences",
                }


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
