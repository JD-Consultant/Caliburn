"""候選提示及工具說明可獨立組裝，不改共享模板或正式工具契約。"""

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace

import pytest

from caliburn.agents.job_consultant.configuration import (
    ConsultantConfiguration,
    ConsultantPrompts,
    ToolDescriptionOverride,
)
from caliburn.agents.job_consultant.instructions import CONSULTANT_INSTRUCTIONS
from caliburn.agents.job_consultant.planning_instructions import (
    FOCUS_INSTRUCTIONS,
    INTERVIEW_PLAN_INSTRUCTIONS,
)
from caliburn.agents.job_consultant.reference_instructions import OCCUPATION_REFERENCE_INSTRUCTIONS
from caliburn.agents.job_consultant.tools import consultant_tool_definitions


@pytest.mark.parametrize("plans", [False, True])
@pytest.mark.parametrize("references", [False, True])
def test_default_configuration_preserves_current_instruction_bundle(plans, references):
    expected = CONSULTANT_INSTRUCTIONS + "\n\n" + FOCUS_INSTRUCTIONS
    if plans:
        expected += "\n\n" + INTERVIEW_PLAN_INSTRUCTIONS
    if references:
        expected += "\n\n" + OCCUPATION_REFERENCE_INSTRUCTIONS
    assert (
        ConsultantConfiguration().instructions(
            interview_plans_enabled=plans, occupation_references_enabled=references
        )
        == expected
    )


def test_two_candidates_keep_prompts_and_nested_tool_contracts_independent():
    defaults = ConsultantConfiguration()
    left = replace(
        defaults,
        prompts=replace(ConsultantPrompts(), focus="候選甲：先問具體事件。"),
        tool_descriptions=(ToolDescriptionOverride("read_jd", "候選甲：讀取現行 JD。"),),
    )
    right = replace(defaults, prompts=replace(ConsultantPrompts(), focus="候選乙：先核對範圍。"))
    original = consultant_tool_definitions()
    first = left.describe_tools(original)
    second = right.describe_tools(original)
    changed = next(tool for tool in first if tool["name"] == "read_jd")
    changed["parameters"]["properties"]["synthetic_mutation"] = {"type": "string"}
    assert next(tool for tool in original if tool["name"] == "read_jd") == next(
        tool for tool in second if tool["name"] == "read_jd"
    )
    assert first != second
    assert right.prompts.focus == "候選乙：先核對範圍。"
    assert defaults.prompts.focus == FOCUS_INSTRUCTIONS
    with pytest.raises(FrozenInstanceError):
        left.prompts.focus = "不可修改"


def test_tool_variant_cannot_silently_target_a_missing_or_duplicate_tool():
    with pytest.raises(ValueError, match="Duplicate"):
        ConsultantConfiguration(
            tool_descriptions=(
                ToolDescriptionOverride("read_jd", "甲"),
                ToolDescriptionOverride("read_jd", "乙"),
            )
        )
    config = ConsultantConfiguration(
        tool_descriptions=(ToolDescriptionOverride("edit_interview_plan", "候選說明"),)
    )
    with pytest.raises(ValueError, match="not enabled"):
        config.describe_tools(consultant_tool_definitions(interview_plans_enabled=False))


@pytest.mark.parametrize(
    "description",
    [
        "候選讀取說明",
        '候選讀取說明。成功只回 {"status":"updated"}；需要完整 state 時再按需讀取。',
    ],
)
def test_tool_description_override_preserves_every_other_contract_field(description):
    original = consultant_tool_definitions()
    config = ConsultantConfiguration(
        tool_descriptions=(ToolDescriptionOverride("read_jd", description),)
    )
    changed = config.describe_tools(original)
    for before, after in zip(original, changed, strict=True):
        assert after == (
            {**before, "description": description} if before["name"] == "read_jd" else before
        )


@pytest.mark.parametrize(
    "names",
    [
        ("update_excluded_work",),
        ("select_occupation_references", "update_excluded_work"),
    ],
)
def test_reference_description_overrides_preserve_status_result_contract(names):
    original = consultant_tool_definitions(occupation_references_enabled=True)
    baseline = deepcopy(original)
    config = ConsultantConfiguration(
        tool_descriptions=tuple(ToolDescriptionOverride(name, "候選寫入說明") for name in names),
    )
    changed = config.describe_tools(original)
    assert original == baseline
    for before, after in zip(original, changed, strict=True):
        if before["name"] in names:
            assert after["description"] == "候選寫入說明"
            assert {key: value for key, value in before.items() if key != "description"} == {
                key: value for key, value in after.items() if key != "description"
            }
        else:
            assert after == before
