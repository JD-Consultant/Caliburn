"""當前模型宣告的輸入界線；不依賴舊 App 或凍結提示及結果全文。"""

import pytest
from jsonschema import Draft202012Validator, ValidationError
from langchain_core.utils.function_calling import convert_to_openai_function

from caliburn.bundles.job_reference import create_bundle


def test_search_declaration_limits_query_and_rejects_host_fields() -> None:
    search, _ = create_bundle({}).plugins[0].tools
    declaration = convert_to_openai_function(search, strict=True)
    validator = Draft202012Validator(declaration["parameters"])

    validator.validate({"query": "工作"})
    validator.validate({"query": "工" * 12_000})
    for arguments in (
        {"query": ""},
        {"query": " \u001c\u3000"},
        {"query": "工" * 12_001},
        {"query": "工作", "limit": 1},
        {"query": "工作", "runtime": {}},
    ):
        with pytest.raises(ValidationError):
            validator.validate(arguments)


def test_read_tool_declaration_requires_task_scope_and_occupation_reference() -> None:
    _, read = create_bundle({}).plugins[0].tools
    declaration = convert_to_openai_function(read, strict=True)
    validator = Draft202012Validator(declaration["parameters"])

    validator.validate({"reference_id": "occupation_101", "task_id": None})
    validator.validate({"reference_id": "occupation_101", "task_id": "u2-t3"})
    for arguments in (
        {"reference_id": "occupation_101"},
        {"reference_id": "task_101", "task_id": None},
        {"reference_id": "occupation_01", "task_id": None},
        {"reference_id": "occupation_101", "task_id": "T1.1"},
        {"reference_id": "occupation_101", "task_id": "u1-t0"},
        {"reference_id": "occupation_101", "task_id": None, "workspace_id": "other"},
    ):
        with pytest.raises(ValidationError):
            validator.validate(arguments)
