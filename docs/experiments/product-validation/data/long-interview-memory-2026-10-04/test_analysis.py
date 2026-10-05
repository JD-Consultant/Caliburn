"""Offline measurements must not score generated words as semantic correctness."""

import pytest
from analysis import (
    aggregate_grades,
    aggregate_usage,
    audit_tool_document,
    check_report_tables,
)


def test_count_responses_do_not_enter_generation_usage():
    events = [
        {
            "event": "response",
            "phase": "recall",
            "arm": "full_history",
            "repeat": 1,
            "path": "/v1/responses/input_tokens",
            "payload": {"input_tokens": 3000},
        },
        {
            "event": "response",
            "phase": "recall",
            "arm": "full_history",
            "repeat": 1,
            "path": "/v1/responses",
            "payload": {
                "usage": {
                    "input_tokens": 3000,
                    "output_tokens": 200,
                    "input_tokens_details": {
                        "cached_tokens": 1000,
                        "cache_write_tokens": 200,
                    },
                }
            },
        },
    ]
    result = aggregate_usage(events)[0]
    assert result["generation_calls"] == 1
    assert result["initial_input_tokens"] == 3000
    assert result["input_tokens"] == 3000
    assert result["cached_tokens"] == 1000
    assert result["cache_write_tokens"] == 200
    assert result["estimated_cost_usd"] == pytest.approx(0.000315)


@pytest.mark.parametrize(
    "code", ["scope_not_allowed", "source_not_available", "target_stale"]
)
def test_infrastructure_failures_cannot_be_valid_recall(code):
    with pytest.raises(ValueError, match=code):
        audit_tool_document({"status": "rejected", "code": code})


def test_model_target_error_remains_a_recall_behavior():
    audit_tool_document({"status": "rejected", "code": "target_not_found"})


def test_compaction_is_not_hidden_by_generation_only_metrics():
    with pytest.raises(ValueError, match="compaction"):
        aggregate_usage(
            [
                {
                    "event": "request",
                    "phase": "memory_capture",
                    "path": "/v1/responses/compact",
                }
            ]
        )


def test_semantic_decisions_and_source_support_remain_separate():
    cases = [{"case_id": "one", "range": "前段", "facts": ["first", "second"]}]
    grades = [
        {
            "arm": "hierarchical_memory",
            "repeat": 1,
            "cases": [
                {
                    "case_id": "one",
                    "facts_pass": [1, 2],
                    "citation_support": "partial",
                    "invalid_sequences": [],
                }
            ],
        }
    ]
    result = aggregate_grades(grades, cases)[0]
    assert result["fact_pass"] == 2
    assert result["fact_total"] == 2
    assert result["case_pass"] == 1
    assert result["early_fact_pass"] == 2
    assert result["fully_supported_cases"] == 0


def test_duplicate_fact_votes_cannot_raise_the_score():
    cases = [{"case_id": "one", "range": "前段", "facts": ["first"]}]
    grades = [
        {
            "arm": "hierarchical_memory",
            "repeat": 1,
            "cases": [
                {
                    "case_id": "one",
                    "facts_pass": [1, 1],
                    "citation_support": "complete",
                    "invalid_sequences": [],
                }
            ],
        }
    ]
    with pytest.raises(ValueError, match="fact indices"):
        aggregate_grades(grades, cases)


def test_report_cannot_promote_semantic_score_or_hide_tool_roundtrips():
    measurements = {
        "semantic_grades": [
            {
                "arm": "hierarchical_memory",
                "repeat": 1,
                "fact_pass": 26,
                "fact_total": 27,
                "early_fact_pass": 10,
                "early_fact_total": 11,
                "fully_supported_cases": 3,
                "case_total": 8,
            }
        ],
        "usage": [
            {
                "phase": "recall",
                "arm": "hierarchical_memory",
                "repeat": 1,
                "initial_input_tokens": 2562,
                "input_tokens": 11204,
                "generation_calls": 2,
            }
        ],
        "trials": [{"arm": "hierarchical_memory", "repeat": 1, "read_calls": 8}],
    }
    report = (
        "| 三層 Memory | 1 | 26／27 | 10／11 | 3／8 |\n"
        "| 三層 Memory | 1 | 2,562 | 11,204 | 2 | 8 |\n"
    )
    check_report_tables(report, measurements)
    with pytest.raises(ValueError, match="report table"):
        check_report_tables(report.replace("26／27", "27／27"), measurements)
    with pytest.raises(ValueError, match="report table"):
        check_report_tables(report.replace("11,204", "2,562"), measurements)
