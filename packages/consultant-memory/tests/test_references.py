"""CommonMark address extraction, not an alternate source codec."""
import pytest

from caliburn_memory.references import controlled_references


@pytest.mark.parametrize("text", [
    "原話 conversation:opaque-token.。",
    "[原話](conversation:opaque-token)",
    "[原話][source]\n\n[source]: conversation:opaque-token",
    "`conversation:opaque-token`",
    "```text\nconversation:opaque-token\n```",
    "![原話](conversation:opaque-token)",
])
def test_controlled_source_keeps_opaque_address_across_markdown_forms(text):
    assert controlled_references(text) == {"conversation:opaque-token"}


def test_duplicate_definition_cannot_hide_second_controlled_address():
    value = "[原話][source]\n\n[source]: conversation:valid\n[source]: conversation:invalid"
    assert controlled_references(value) == {"conversation:valid", "conversation:invalid"}


def test_external_url_suffix_does_not_become_local_reference():
    assert controlled_references("https://example.test/path/interviews/a/summary.md") == set()
    assert controlled_references("[外站](https://example.test/conversation:opaque)") == set()


def test_code_literal_punctuation_is_not_repaired_into_another_address():
    assert controlled_references("`conversation:opaque.`") == {"conversation:opaque."}
    assert controlled_references("[原話](conversation:opaque.)") == {"conversation:opaque."}


def test_interview_paths_remain_controlled():
    target = "/interviews/00000000-0000-0000-0000-000000000001/summary.md"
    assert controlled_references(f"[案例]({target})") == {target}


def test_layered_memory_paths_are_controlled():
    target = "/memory/cases/items/00000000-0000-0000-0000-000000000001.md"
    assert controlled_references(f"案例 `{target}`") == {target}
