"""用 Node 的 ECMAScript Unicode 模式核對導出字串限制與 Python 入口。"""

import json
import shutil
import subprocess
import sys
import unicodedata
from typing import Any

import pytest
from fastapi import FastAPI
from pydantic import BaseModel, TypeAdapter, ValidationError

from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.presentation.api.router import build_workspace_router
from caliburn.modules.workspace.presentation.api.schemas import (
    CreateWorkspaceRequest,
    RenameWorkspaceRequest,
)
from caliburn.shared.presentation.api.values import HttpId

from ...application.fakes import FakeUnitOfWorkFactory

_STRING_SCHEMA_CHECK = """
const fs = require('node:fs');
const { schema, values } = JSON.parse(fs.readFileSync(0, 'utf8'));
const pattern = new RegExp(schema.pattern ?? '', 'u');
const outcomes = values.map(value => {
    if (typeof value !== 'string') return false;
    const length = [...value].length;
    return (schema.minLength === undefined || length >= schema.minLength)
        && (schema.maxLength === undefined || length <= schema.maxLength)
        && pattern.test(value);
});
process.stdout.write(JSON.stringify(outcomes));
"""


@pytest.fixture(scope="module")
def node_executable() -> str:
    """跨語言 wire 契約驗證需要根專案指定的 Node.js。"""
    executable = shutil.which("node")
    if executable is None:
        pytest.fail("ECMAScript Unicode 契約測試需要根專案指定的 Node.js")
    return executable


def _schema_accepts(
    node_executable: str, schema: dict[str, Any], values: list[object]
) -> list[bool]:
    """驗證本欄位使用的字串 assertion；format 與 title 是 annotation。"""
    assert schema["type"] == "string"
    assert set(schema) <= {
        "type",
        "title",
        "format",
        "pattern",
        "minLength",
        "maxLength",
    }
    result = subprocess.run(
        [node_executable, "-e", _STRING_SCHEMA_CHECK],
        input=json.dumps({"schema": schema, "values": values}, ensure_ascii=True),
        capture_output=True,
        text=True,
        check=True,
        timeout=10,
    )
    outcomes = json.loads(result.stdout)
    assert isinstance(outcomes, list)
    assert all(isinstance(outcome, bool) for outcome in outcomes)
    return [bool(outcome) for outcome in outcomes]


@pytest.fixture(scope="module")
def openapi() -> dict[str, Any]:
    """從真路由導出 OpenAPI，避免只核對未被入口採用的模型。"""
    app = FastAPI()
    app.include_router(
        build_workspace_router(WorkspaceService(FakeUnitOfWorkFactory()))
    )
    return app.openapi()


def _name_schema(
    openapi: dict[str, Any], request_model: type[BaseModel]
) -> dict[str, Any]:
    if request_model is CreateWorkspaceRequest:
        path, method = "/workspaces", "post"
    else:
        path, method = "/workspaces/{workspace_id}", "patch"
    request_schema = openapi["paths"][path][method]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    model_name = request_schema["$ref"].rsplit("/", 1)[-1]
    schema: dict[str, Any] = openapi["components"]["schemas"][model_name]["properties"][
        "interviewee_name"
    ]
    return schema


def _runtime_accepts(request_model: type[BaseModel], value: object) -> bool:
    try:
        request_model.model_validate({"interviewee_name": value})
    except ValidationError:
        return False
    return True


@pytest.mark.parametrize(
    "request_model", [CreateWorkspaceRequest, RenameWorkspaceRequest]
)
def test_name_schema_matches_runtime_representative_values(
    node_executable: str,
    openapi: dict[str, Any],
    request_model: type[BaseModel],
) -> None:
    """非空白、儲存字元與 emoji 規則須同時存在於 OpenAPI 與輸入驗證。"""
    cases: list[tuple[object, bool]] = [
        ("王小明", True),
        ("  王小明  ", True),
        ("👩🏽‍💻", True),
        ("\ufeff", True),
        ("\u200b", True),
        ("\u200d", True),
        ("\x01", True),
        ("\n名字\r\n", True),
        ("", False),
        ("\t\n\u3000", False),
        ("\u0085", False),
        ("\x1c\x1d\x1e\x1f", False),
        ("\x00", False),
        ("名字\x00", False),
        ("名字\x00\n", False),
        ("\ud800", False),
        ("名字\udfff\n", False),
        (None, False),
        (123, False),
        (True, False),
        (["名字"], False),
    ]
    values = [value for value, _ in cases]
    expected = [accepted for _, accepted in cases]

    assert (
        _schema_accepts(node_executable, _name_schema(openapi, request_model), values)
        == expected
    )
    assert [_runtime_accepts(request_model, value) for value in values] == expected


def test_create_and_rename_publish_the_same_name_constraints(
    openapi: dict[str, Any],
) -> None:
    """建立與改名共用相同的公開姓名限制。"""
    assert _name_schema(openapi, CreateWorkspaceRequest) == _name_schema(
        openapi, RenameWorkspaceRequest
    )


def test_name_schema_covers_complete_python_whitespace_set(
    node_executable: str,
    openapi: dict[str, Any],
) -> None:
    """共用姓名限制完整核對一次：純空白拒絕、姓名兩側則保留。"""
    whitespace = [
        character
        for codepoint in range(sys.maxunicode + 1)
        if unicodedata.category(character := chr(codepoint)) == "Zs"
        or unicodedata.bidirectional(character) in {"WS", "B", "S"}
    ]
    assert whitespace
    values: list[object] = [*whitespace, "".join(whitespace)]
    expected = [False] * len(values)
    values.extend(f"{character}甲{character}" for character in whitespace)
    expected.extend([True] * len(whitespace))

    assert (
        _schema_accepts(
            node_executable, _name_schema(openapi, CreateWorkspaceRequest), values
        )
        == expected
    )
    assert [
        _runtime_accepts(CreateWorkspaceRequest, value) for value in values
    ] == expected


def test_name_schema_rejects_all_surrogates_and_accepts_scalar_boundaries(
    node_executable: str,
    openapi: dict[str, Any],
) -> None:
    """全部孤立 surrogate 被拒，鄰接與補充平面的 Unicode 碼點仍合法。"""
    values: list[object] = [chr(codepoint) for codepoint in range(0xD800, 0xE000)]
    expected = [False] * len(values)
    values.extend(["\ud7ff", "\ue000", "\U00010000", "\U0010ffff", "😀"])
    expected.extend([True] * 5)

    assert (
        _schema_accepts(
            node_executable, _name_schema(openapi, CreateWorkspaceRequest), values
        )
        == expected
    )
    assert [
        _runtime_accepts(CreateWorkspaceRequest, value) for value in values
    ] == expected


@pytest.mark.parametrize("location", ["path", "query"])
def test_uuid_schema_matches_runtime_without_trailing_newline(
    node_executable: str, openapi: dict[str, Any], location: str
) -> None:
    """UUID 固定 36 字元，不能因 ECMAScript 結尾錨點而接受末尾換行。"""
    identity = "019cda1a-7aa9-7000-8000-000000000001"
    path = "/workspaces/{workspace_id}" if location == "path" else "/workspaces"
    parameter = next(
        parameter
        for parameter in openapi["paths"][path]["get"]["parameters"]
        if parameter["name"] == ("workspace_id" if location == "path" else "after")
    )
    schema = parameter["schema"]
    if location == "query":
        schema = next(
            option for option in schema["anyOf"] if option["type"] == "string"
        )
    values: list[object] = [
        identity,
        identity.upper(),
        identity + "\n",
        identity + "\r",
        identity + "\r\n",
        identity.replace("-", ""),
        "urn:uuid:" + identity,
    ]
    expected = [True, True, False, False, False, False, False]

    assert _schema_accepts(node_executable, schema, values) == expected
    adapter = TypeAdapter(HttpId)
    actual = []
    for value in values:
        try:
            adapter.validate_python(value)
        except ValidationError:
            actual.append(False)
        else:
            actual.append(True)
    assert actual == expected
