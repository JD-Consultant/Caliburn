"""HTTP UUID 字串接受集合不因 Python／JSON 模式而放寬。"""

import json
from uuid import UUID

import pytest
from pydantic import TypeAdapter, ValidationError

from caliburn.shared.presentation.api.values import HttpId


@pytest.mark.parametrize(
    "value",
    [
        "00112233-4455-6677-8899-aabbccddeeff",
        "00112233-4455-6677-8899-AABBCCDDEEFF",
    ],
)
def test_http_id_preserves_identity_and_canonical_output(value: str) -> None:
    adapter = TypeAdapter(HttpId)
    identity = UUID("00112233-4455-6677-8899-aabbccddeeff")

    assert adapter.validate_python(value, strict=True) == identity
    assert adapter.validate_json(json.dumps(value), strict=True) == identity
    assert adapter.dump_json(identity) == b'"00112233-4455-6677-8899-aabbccddeeff"'


@pytest.mark.parametrize(
    "value",
    [
        "00112233445566778899aabbccddeeff",
        "urn:uuid:00112233-4455-6677-8899-aabbccddeeff",
        "{00112233-4455-6677-8899-aabbccddeeff}",
        "00112233-4455-6677-8899-aabbccddeeff\n",
        "00112233-4455-6677-8899-aabbccddeeff\r\n",
        "00112233-4455-6677-8899-aabbccddeefg",
        None,
        True,
        1,
    ],
)
def test_http_id_rejects_non_wire_values_in_both_input_modes(value: object) -> None:
    adapter = TypeAdapter(HttpId)
    with pytest.raises(ValidationError):
        adapter.validate_python(value, strict=True)
    with pytest.raises(ValidationError):
        adapter.validate_json(json.dumps(value), strict=True)


def test_http_id_requires_external_text_even_for_python_uuid_instances() -> None:
    with pytest.raises(ValidationError):
        TypeAdapter(HttpId).validate_python(UUID(int=1))
