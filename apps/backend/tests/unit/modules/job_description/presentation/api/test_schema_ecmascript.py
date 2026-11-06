"""使用 ECMAScript 核對 JD 導出的 scalar assertion，不另定一份 wire 規格。"""

import json
import random
import shutil
import subprocess
from typing import Any

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
)
from caliburn.shared.presentation.api.values import HttpId

_CHECK_SCALAR_SCHEMA = """
const fs = require('node:fs');
const {schema, values} = JSON.parse(fs.readFileSync(0, 'utf8'));
const accepted = values.map(value => {
    if (schema.type === 'integer') {
        return typeof value === 'number' && Number.isInteger(value)
            && value >= schema.minimum && value <= schema.maximum;
    }
    if (typeof value !== 'string') return false;
    const length = [...value].length;
    return (schema.minLength === undefined || length >= schema.minLength)
        && (schema.maxLength === undefined || length <= schema.maxLength)
        && new RegExp(schema.pattern, 'u').test(value);
});
process.stdout.write(JSON.stringify(accepted));
"""


@pytest.fixture(scope="module")
def node_executable() -> str:
    executable = shutil.which("node")
    if executable is None:
        pytest.fail("JD wire 契約測試需要專案指定的 Node.js")
    return executable


@pytest.mark.parametrize(
    "adapter, cases",
    [
        (
            TypeAdapter(ExpectedVersion),
            [
                (1, True),
                (1.0, True),
                (1.5, False),
                (True, False),
                ("1", False),
                (0, False),
                (9007199254740991, True),
                (9007199254740992, False),
            ],
        ),
        (
            TypeAdapter(NameInput),
            [
                (" 名稱 ", True),
                ("😀" * 255, True),
                ("😀" * 256, False),
                ("\u001c " + "😀" * 255 + "\u3000\n", True),
                (" " + "😀" * 256 + "\n", False),
                ("a" + " " * 253 + "b", True),
                ("a" + " " * 254 + "b", False),
                ("\ufeff" + "😀" * 255, False),
                ("\ufeff", True),
                ("", False),
                ("\x1c\u0085\u3000", False),
                ("a\x00\n", False),
                ("\ud800", False),
                ("a\udfff\n", False),
            ],
        ),
        (
            TypeAdapter(NonBlankText),
            [
                ("😀" * 201, True),
                ("\ufeff", True),
                ("\t\n", False),
                ("\x00", False),
                (None, False),
            ],
        ),
        (
            TypeAdapter(StorableText),
            [("", True), (" \t\n", True), ("\x00\n", False), ("\udfff\n", False)],
        ),
        (
            TypeAdapter(CorrelationIdInput),
            [
                ("a" * 200, True),
                ("a" * 201, False),
                ("", False),
                ("\u0085", False),
                ("x\x00", False),
            ],
        ),
        (
            TypeAdapter(HttpId),
            [
                ("00112233-4455-6677-8899-AABBCCDDEEFF", True),
                ("00112233-4455-6677-8899-aabbccddeeff\n", False),
                ("00112233445566778899aabbccddeeff", False),
                ("urn:uuid:00112233-4455-6677-8899-aabbccddeeff", False),
            ],
        ),
        (
            TypeAdapter(ExpectedVersionQuery),
            [
                ("1", True),
                ("9007199254740991", True),
                ("9007199254740992", False),
                ("0", False),
                ("01", False),
                ("1\n", False),
                ("1.0", False),
            ],
        ),
        (
            TypeAdapter(HistoryPageSizeQuery),
            [
                ("0", True),
                ("101", True),
                ("01", False),
                ("-1", False),
                ("9007199254740992", False),
            ],
        ),
    ],
)
def test_scalar_schema_and_python_accept_the_same_representative_values(
    node_executable: str,
    adapter: TypeAdapter[Any],
    cases: list[tuple[object, bool]],
) -> None:
    schema = adapter.json_schema()
    assert set(schema) <= {
        "type",
        "format",
        "pattern",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
    }
    values = [value for value, _ in cases]
    expected = [accepted for _, accepted in cases]
    result = subprocess.run(
        [node_executable, "-e", _CHECK_SCALAR_SCHEMA],
        input=json.dumps({"schema": schema, "values": values}, ensure_ascii=True),
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    assert json.loads(result.stdout) == expected
    actual = []
    for value in values:
        try:
            adapter.validate_python(value)
        except ValidationError:
            actual.append(False)
        else:
            actual.append(True)
    assert actual == expected


def test_version_pattern_covers_decimal_prefix_boundaries(
    node_executable: str,
) -> None:
    random_values = random.Random(20261026)
    numbers = [random_values.randrange(1, 10**20) for _ in range(300)]
    numbers.extend(
        10**exponent + offset for exponent in range(1, 20) for offset in (-1, 0, 1)
    )
    numbers.extend(range(9007199254740981, 9007199254741002))
    result = subprocess.run(
        [node_executable, "-e", _CHECK_SCALAR_SCHEMA],
        input=json.dumps(
            {
                "schema": TypeAdapter(ExpectedVersionQuery).json_schema(),
                "values": [str(value) for value in numbers],
            }
        ),
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    assert json.loads(result.stdout) == [
        1 <= value <= 9007199254740991 for value in numbers
    ]
