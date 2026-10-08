"""對照輸入預檢與候選凍結，沒有資料庫或模型請求。"""

import json

import pytest
from pydantic import ValidationError

from evaluations.consultant_cases import ConsultantComparison


def document():
    return {
        "case": {"name": "synthetic", "inputs": ["公開輸入"], "criteria": ["保留評閱材料"]},
        "candidates": [
            {"name": "current"},
            {"name": "candidate", "prompts": {"focus": "候選重點"}},
        ],
    }


def test_manifest_records_effective_prompt_and_tools_without_evaluator_material():
    comparison = ConsultantComparison.model_validate_json(json.dumps(document()))
    old, changed = [candidate.manifest() for candidate in comparison.candidates]
    assert old["instructions"] != changed["instructions"]
    assert old["tools"] == changed["tools"]
    assert "保留評閱材料" not in json.dumps(changed, ensure_ascii=False)


def test_candidate_configuration_is_detached_from_input_dictionaries():
    candidate = ConsultantComparison.model_validate(document()).candidates[1]
    configuration = candidate.configuration()
    candidate.prompts["focus"] = "在邊界之外改 DTO"
    assert configuration.prompts.focus == "候選重點"


@pytest.mark.parametrize("invalid", ["unknown_prompt", "unknown_tool", "duplicate_candidate"])
def test_invalid_comparison_is_rejected_before_constructing_an_app(invalid):
    raw = document()
    if invalid == "unknown_prompt":
        raw["candidates"][1]["prompts"] = {"undocumented": "不可默默忽略"}
    elif invalid == "unknown_tool":
        raw["candidates"][1]["tool_descriptions"] = {"invented_tool": "不可默默忽略"}
    else:
        raw["candidates"][1]["name"] = "current"
    with pytest.raises(ValidationError):
        ConsultantComparison.model_validate(raw)
