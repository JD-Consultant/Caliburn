"""Independent counterexamples for the experiment's graders and public trace."""

import json

import experiment
import pytest
from experiment import context_window, read_fixture
from fixtures import locator_cases, make_corpus, make_locators
from measurements import public_items, score_context, score_locator


def test_old_frequency_and_missing_original_source_do_not_pass():
    expected = {"frequency": "每月2次", "actor": "本人"}
    checks = score_context(
        expected,
        [2, 4],
        {
            "facts": {"frequency": "每季1次", "actor": "本人"},
            "interview_sequences": [4],
        },
    )
    assert checks == {"frequency": False, "actor": True, "sources": False}


def test_source_order_is_irrelevant_but_unrelated_sources_fail():
    assert score_context({}, [2, 4], {"facts": {}, "interview_sequences": [4, 2]}) == {
        "sources": True
    }
    assert score_context(
        {}, [2, 4], {"facts": {}, "interview_sequences": [2, 4, 6]}
    ) == {"sources": False}


def test_wrong_target_or_order_does_not_pass_even_when_format_is_valid():
    assert score_locator([12, 3], [3, 12]) is False
    assert score_locator([12, 3], [12, 3]) is True


def test_reasoning_ciphertext_is_not_written_to_public_trace():
    original = [
        {"type": "reasoning", "encrypted_content": "opaque-test", "summary": []},
        {"type": "message", "phase": "commentary", "content": []},
    ]
    projected = public_items(original)
    assert "encrypted_content" not in projected[0]
    assert projected[0]["encrypted_length"] == 11
    assert len(projected[0]["encrypted_sha256"]) == 64
    assert original[0]["encrypted_content"] == "opaque-test"
    assert projected[1] == original[1]


def test_public_trace_excludes_raw_reasoning_but_preserves_readable_summary():
    result = public_items(
        [
            {
                "type": "reasoning",
                "content": [{"type": "reasoning_text", "text": "private-test"}],
                "summary": [{"type": "summary_text", "text": "public-test"}],
            }
        ]
    )
    assert "content" not in result[0]
    assert result[0]["summary"][0]["text"] == "public-test"


def test_oversized_interview_range_is_rejected_before_it_is_expanded(monkeypatch):
    def no_expand(*args):
        raise AssertionError("An out-of-bounds interval must not be expanded")

    monkeypatch.setattr(experiment, "range", no_expand, raising=False)
    payload = json.loads(
        read_fixture(
            make_corpus(),
            "read_interview",
            '{"query":{"kind":"range","start_sequence":1,"end_sequence":1000000000000}}',
        )
    )
    assert payload["status"] == "rejected"
    assert payload["code"] == "source_not_available"


@pytest.mark.parametrize(
    "value", [None, {}, {"facts": []}, {"interview_sequences": "2,4"}]
)
def test_malformed_answer_does_not_pass(value):
    assert not all(score_context({"frequency": "每月2次"}, [2, 4], value).values())


def test_selective_initial_window_does_not_expose_answers_or_fulltext():
    corpus = make_corpus()
    payload = json.loads(
        context_window(corpus, corpus["cases"][0], "selective")[0]["content"]
    )
    assert set(payload) == {"data_kind", "work_situation_map"}
    assert "expected" not in json.dumps(payload)
    assert "每月1次" not in json.dumps(payload, ensure_ascii=False)
    assert len(corpus["interviews"]["messages"]) == 144
    assert len(corpus["objects"]) == 36


def test_read_returns_only_requested_original_messages_without_renumbering():
    corpus = make_corpus()
    answer = json.loads(
        read_fixture(
            corpus,
            "read_interview",
            '{"query":{"kind":"messages","sequences":[4,2,4]}}',
        )
    )
    assert [message["interview_sequence"] for message in answer["messages"]] == [2, 4]
    assert answer["messages"][0]["speaker"] == "employee"
    assert "之前每季1次" in answer["messages"][0]["text"]
    assert "目前是每月1次" in answer["messages"][1]["text"]


def test_out_of_bound_read_is_rejected_without_partial_content():
    payload = json.loads(
        read_fixture(
            make_corpus(),
            "read_interview",
            '{"query":{"kind":"messages","sequences":[2,145]}}',
        )
    )
    assert "messages" not in payload
    assert "source_not_available" in json.dumps(payload)


def test_locator_arms_resolve_the_same_targets_and_differ_only_in_reference_strings():
    long = make_locators("uuid")
    short = make_locators("short")
    assert [item["title"] for item in long["items"]] == [
        item["title"] for item in short["items"]
    ]
    assert len(set(long["targets"])) == len(set(short["targets"])) == 48
    assert (
        long["targets"][long["items"][18]["read_ref"]]
        == short["targets"]["task_19"]
        == 19
    )
    assert short["citations"]["citation_93"] == 45
    assert [case["indices"] for case in locator_cases()] == [
        [19],
        [36, 2, 29],
        [37, 1],
        [24],
        [45, 9],
        [11],
    ]
