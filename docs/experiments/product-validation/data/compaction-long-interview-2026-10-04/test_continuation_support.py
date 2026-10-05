"""Resume only a verified prefix, keeping the cumulative study allowance."""

import json
from decimal import Decimal
from pathlib import Path

import pytest
from continuation_support import ContinuedAllowance, validate_prefix
from main_support import StudyStop


def write_prefix(folder: Path) -> None:
    folder.mkdir()
    for index in range(1, 52):
        (folder / f"exchange-{index:03d}.json").write_text(
            json.dumps({"event_id": f"e{index:03d}"}), encoding="utf-8"
        )
        (folder / f"product-{index:03d}.json").write_text("{}", encoding="utf-8")
    for event in ("e012", "e028", "e044"):
        (folder / f"memory-{event}.json").write_text("{}", encoding="utf-8")


def test_prefix_requires_every_completed_exchange_and_product(tmp_path):
    write_prefix(tmp_path / "prefix")
    (tmp_path / "prefix/product-029.json").unlink()
    with pytest.raises(ValueError, match="prefix"):
        validate_prefix(tmp_path / "prefix")


def test_prefix_rejects_a_success_record_for_the_failed_event(tmp_path):
    write_prefix(tmp_path / "prefix")
    (tmp_path / "prefix/exchange-052.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="prefix"):
        validate_prefix(tmp_path / "prefix")


def test_prefix_checks_event_identity_not_just_file_count(tmp_path):
    write_prefix(tmp_path / "prefix")
    (tmp_path / "prefix/exchange-025.json").write_text(
        '{"event_id":"e024"}', encoding="utf-8"
    )
    with pytest.raises(ValueError, match="prefix"):
        validate_prefix(tmp_path / "prefix")


def test_verified_prefix_returns_hashes_without_rewriting(tmp_path):
    write_prefix(tmp_path / "prefix")
    hashes = validate_prefix(tmp_path / "prefix")
    assert len(hashes) == 105
    assert len(hashes["exchange-001.json"]) == 64


def test_budget_includes_previous_run_and_retained_reserve():
    allowance = ContinuedAllowance(
        {
            "estimated_occupation_usd": "0.483808190",
            "generation_calls": 208,
            "compaction_calls": 6,
            "outbound_calls": 478,
            "admitted_input_tokens": 17_112_156,
        }
    )
    assert allowance.occupied_usd == Decimal("0.583808190")
    assert allowance.max_estimated_usd == Decimal(2)
    assert allowance.generation_calls == 208
    assert allowance.compaction_calls == 6
    assert allowance.outbound_calls == 478
    assert allowance.input_tokens == 17_112_156


def test_cumulative_budget_cannot_be_reset_by_a_new_phase():
    allowance = ContinuedAllowance(
        {
            "estimated_occupation_usd": "1.89995",
            "generation_calls": 1,
            "compaction_calls": 0,
            "outbound_calls": 2,
            "admitted_input_tokens": 10,
        }
    )
    with pytest.raises(StudyStop, match="budget"):
        allowance.admit("/v1/responses/input_tokens", {"model": "gpt-6-luna"})
