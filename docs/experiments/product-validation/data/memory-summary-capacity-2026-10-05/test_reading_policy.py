"""Keep the paired reading-policy study factual and description-only."""

import copy

import pytest
from reading_policy import prepare_inputs, validate_frozen_inputs


def test_pair_shares_cases_materials_and_submission_contract():
    frozen = prepare_inputs()
    validate_frozen_inputs(frozen)
    assert frozen["tools"]["control"][-1] == frozen["tools"]["candidate"][-1]
    assert len(frozen["manifest"]["schedule"]) == 8
    assert frozen["manifest"]["grading_items"] == 19


def test_shape_change_cannot_masquerade_as_description_comparison():
    frozen = prepare_inputs()
    frozen["tools"]["candidate"][0]["parameters"]["properties"]["forged_scope"] = {}
    with pytest.raises(ValueError, match="tool_structure_changed"):
        validate_frozen_inputs(frozen)


def test_modified_material_is_rejected_before_live_phase():
    frozen = copy.deepcopy(prepare_inputs())
    frozen["materials"]["messages"][0]["interview_text"] = "modified"
    with pytest.raises(ValueError, match="frozen_input_changed"):
        validate_frozen_inputs(frozen)
