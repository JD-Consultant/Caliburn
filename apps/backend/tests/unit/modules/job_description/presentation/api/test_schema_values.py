"""JD 的 wire 值與公開 schema 必須接受同一組邊界值。"""

import json

import pytest
from pydantic import TypeAdapter, ValidationError

from caliburn.modules.job_description.presentation.api.schemas.common import (
    CorrelationIdInput,
    ExpectedVersion,
    ExpectedVersionQuery,
    HistoryPageSizeQuery,
    NameInput,
    NonBlankText,
    StorableText,
    WriteRequest,
)


@pytest.mark.parametrize("value", [1, 1.0, 9007199254740991])
def test_expected_version_accepts_json_mathematical_integer(value: object) -> None:
    parsed = WriteRequest.model_validate_json(json.dumps({"expected_version": value}))
    assert type(parsed.expected_version) is int
    assert parsed.expected_version == value


@pytest.mark.parametrize("value", [True, False, "1", 0, -1, 1.5, 9007199254740992])
def test_expected_version_rejects_non_integer_or_unsafe_number(value: object) -> None:
    with pytest.raises(ValidationError):
        WriteRequest.model_validate_json(json.dumps({"expected_version": value}))


@pytest.mark.parametrize(
    "value", ["0", "01", "+1", "1.0", "1e1", "-1", "9007199254740992"]
)
def test_version_query_rejects_non_canonical_or_unsafe_input(value: str) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(ExpectedVersionQuery).validate_python(value)


def test_page_size_query_accepts_zero_and_defers_cap_to_application() -> None:
    adapter = TypeAdapter(HistoryPageSizeQuery)
    assert adapter.validate_python("0") == 0
    assert adapter.validate_python("101") == 101


@pytest.mark.parametrize("value", ["\x00", "before\ud800after", "\udfff"])
def test_text_rejects_values_postgres_utf8_cannot_store(value: str) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(StorableText).validate_python(value)


@pytest.mark.parametrize("value", ["", " \t\n", "\x1c\u0085\u3000"])
def test_nonblank_text_uses_python_whitespace_policy(value: str) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(NonBlankText).validate_python(value)


def test_text_preserves_whitespace_and_feff_and_counts_unicode_codepoints() -> None:
    assert TypeAdapter(StorableText).validate_python("") == ""
    assert TypeAdapter(NonBlankText).validate_python(" \ufeff ") == " \ufeff "
    assert TypeAdapter(NameInput).validate_python("😀" * 255) == "😀" * 255
    with pytest.raises(ValidationError):
        TypeAdapter(NameInput).validate_python("😀" * 256)
    with pytest.raises(ValidationError):
        TypeAdapter(CorrelationIdInput).validate_python("a" * 201)


def test_name_input_trims_before_checking_length() -> None:
    """只有名稱清洗；255字元外加Python空白仍合法，FEFF不清除。"""
    adapter = TypeAdapter(NameInput)
    name = "😀" * 255
    assert adapter.validate_python("\u001c " + name + "\u3000\n") == name
    assert adapter.validate_python(" \ufeff ") == "\ufeff"
    with pytest.raises(ValidationError):
        adapter.validate_python(" " + name + "界 ")


def test_numeric_schema_declares_safe_integer_bounds() -> None:
    schema = TypeAdapter(ExpectedVersion).json_schema()
    assert schema["type"] == "integer"
    assert schema["minimum"] == 1
    assert schema["maximum"] == 9007199254740991


def test_write_request_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        WriteRequest.model_validate({"expected_version": 1, "unknown": "secret"})
