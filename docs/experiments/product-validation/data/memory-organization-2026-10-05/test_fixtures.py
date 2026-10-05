"""Guard source boundaries and independent starting material, not prompt wording."""

import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "organization_fixtures", Path(__file__).with_name("fixtures.py")
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def material():
    return {
        "snapshot": {"covered_through_sequence": 2},
        "messages": [
            {"interview_sequence": 1, "speaker": "app", "text": "何時交表？"},
            {"interview_sequence": 2, "speaker": "employee", "text": "週二14:20。"},
            {"interview_sequence": 3, "speaker": "consultant", "text": "收到。"},
        ],
        "maps": {"work_situation": {"items": []}},
        "objects": {
            "work_situation:交表": {"body": "週二14:20。", "interview_references": [2]}
        },
    }


def test_projection_keeps_only_original_fixed_memory_boundary():
    result = module.bounded_material(material())
    assert [item["interview_sequence"] for item in result["messages"]] == [1, 2]
    assert result["objects"]["work_situation:交表"]["body"] == "週二14:20。"


def test_arms_cannot_mutate_each_other_or_the_saved_source():
    original = material()
    before = deepcopy(original)
    first = module.bounded_material(original)
    second = module.bounded_material(original)
    first["objects"]["work_situation:交表"]["body"] = "錯誤改動"
    assert second["objects"]["work_situation:交表"]["body"] == "週二14:20。"
    assert original == before


@pytest.mark.parametrize(
    "invalid", ["future_reference", "non_employee_frontier", "sequence_gap"]
)
def test_bad_material_is_rejected_instead_of_silently_repaired(invalid):
    value = material()
    if invalid == "future_reference":
        value["objects"]["work_situation:交表"]["interview_references"] = [3]
    elif invalid == "non_employee_frontier":
        value["snapshot"]["covered_through_sequence"] = 3
    else:
        value["messages"][0]["interview_sequence"] = 9
    with pytest.raises(ValueError):
        module.bounded_material(value)
