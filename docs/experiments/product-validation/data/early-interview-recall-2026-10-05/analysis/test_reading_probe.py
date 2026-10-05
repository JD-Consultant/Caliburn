"""Validate cold-start pairs and the frozen read-only fixture before model use."""

from copy import deepcopy

import pytest
from reading_probe_materials import build_materials, invoke, probe_request


@pytest.fixture(scope="module")
def materials():
    return build_materials()


def test_navigation_pair_changes_only_descriptions(materials):
    old = probe_request(materials, "control", "map_present")
    new = probe_request(materials, "navigation", "map_present")
    assert {key for key in old if old[key] != new[key]} == {"tools"}
    assert len(old["input"]) == 2
    assert all(item.get("role") == "user" for item in old["input"])


def test_precision_pair_changes_only_instructions(materials):
    old = probe_request(materials, "control", "detail")
    new = probe_request(materials, "precision", "detail")
    assert {key for key in old if old[key] != new[key]} == {"instructions"}
    assert len(old["input"]) == 3  # Shared full understanding, no old opaque history.
    assert "一箱" in str(old["input"])


def test_missing_map_is_not_secretly_retained(materials):
    missing = probe_request(materials, "navigation", "map_absent")
    assert "target_title" not in missing["input"][0]["content"]
    assert "庫存與物流行政的作業核對、追蹤與支援" not in str(missing["input"])
    assert len(invoke(materials, "read_work_understanding_map", "{}")["items"]) == 1


def test_fixture_preserves_all_sources_and_order(materials):
    result = invoke(
        materials,
        "read_interview",
        '{"query":{"kind":"messages","sequences":[56,54,54]}}',
    )
    assert [m["interview_sequence"] for m in result["messages"]] == [54, 56]
    assert result["messages"][0] == materials["interviews"][53]
    assert result["messages"][1] == materials["interviews"][55]
    invalid = invoke(
        materials,
        "read_interview",
        '{"query":{"kind":"messages","sequences":[54,106]}}',
    )
    assert "messages" not in invalid
    assert invalid["code"] == "source_not_available"


def test_reversed_range_is_rejected(materials):
    result = invoke(
        materials,
        "read_interview",
        '{"query":{"kind":"range","start_sequence":9,"end_sequence":2}}',
    )
    assert result["code"] == "invalid_arguments"


def test_pair_does_not_mutate_frozen_materials(materials):
    before = deepcopy(materials)
    probe_request(materials, "navigation", "map_absent")["input"].clear()
    assert materials == before
