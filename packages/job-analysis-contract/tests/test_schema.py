"""Executable checks for the Local Web wire contract."""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from job_analysis_contract import JdTaskWrite, ProblemDetail


PACKAGE_ROOT = Path(__file__).parents[1]
SCHEMA_PATH = PACKAGE_ROOT / "schema" / "job-analysis-workspace.schema.json"
PROBLEM_TYPES = {
    "https://caliburn.dev/problems/job-analysis/document-not-found",
    "https://caliburn.dev/problems/job-analysis/task-not-found",
    "https://caliburn.dev/problems/job-analysis/idempotency-conflict",
    "https://caliburn.dev/problems/job-analysis/authority-conflict",
    "https://caliburn.dev/problems/job-analysis/invalid-task-order",
    "https://caliburn.dev/problems/job-analysis/invalid-request",
}


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_schema_owns_only_the_workspace_wire_contract():
    """Replacing the schema with an old OCS/user contract must fail."""

    schema = _schema()

    assert schema["$id"] == (
        "https://caliburn.dev/schema/job-analysis-workspace.schema.json"
    )
    assert set(schema["$defs"]) == {
        "DocumentMetadataWrite",
        "DocumentMetadataView",
        "DocumentSummary",
        "DocumentView",
        "Enabler",
        "JdTaskWrite",
        "JdTaskView",
        "ProblemDetail",
        "ProblemFieldError",
        "TaskOrderWrite",
    }


def test_problem_type_is_the_six_value_machine_identifier():
    """Adding an untyped error branch must change the generated consumers."""

    problem = _schema()["$defs"]["ProblemDetail"]

    assert set(problem["properties"]["type"]["enum"]) == PROBLEM_TYPES
    assert problem["additionalProperties"] is True


def test_optional_task_text_can_reach_the_mapper_as_blank_or_null():
    """Schema-level minLength would reject a value the mapper must normalize."""

    task = _schema()["$defs"]["JdTaskWrite"]

    for field in (
        "purpose_result",
        "context",
        "frequency_text",
        "responsibility_role",
    ):
        assert set(task["properties"][field]["type"]) == {"string", "null"}
        assert "minLength" not in task["properties"][field]

    assert "" in task["properties"]["responsibility_role"]["enum"]
    assert "" not in _schema()["$defs"]["JdTaskView"]["properties"][
        "responsibility_role"
    ]["enum"]


def test_document_view_accepts_one_complete_task_without_extra_fields():
    """A closed allOf branch must not reject fields inherited by JdTaskView."""

    validator = Draft202012Validator(_schema())
    document = {
        "document_id": "00000000-0000-0000-0000-000000000045",
        "title": "門市營運專員",
        "updated_at": "2026-07-30T09:00:00Z",
        "tasks": [
            {
                "task_id": "task-1",
                "statement": "每週彙整營運週報",
                "purpose_result": None,
                "context": "每週",
                "frequency_text": "每週一次",
                "responsibility_role": "primary",
                "enablers": [{"kind": "tool_system", "name": "Excel"}],
                "display_order": 0,
            }
        ],
    }

    assert list(
        validator.evolve(schema={"$ref": "#/$defs/DocumentView"}).iter_errors(
            document
        )
    ) == []


def test_generated_models_keep_normalization_and_problem_extension_boundaries():
    task = JdTaskWrite(
        statement="每週彙整營運週報",
        purpose_result="",
        context=None,
        frequency_text="",
        responsibility_role="",
        enablers=[],
    )
    problem = ProblemDetail.model_validate(
        {
            "type": "https://caliburn.dev/problems/job-analysis/invalid-request",
            "title": "Request failed",
            "status": 422,
            "future_extension": {"ignored_by_old_consumers": True},
        }
    )

    assert task.responsibility_role.value == ""
    assert problem.model_extra == {
        "future_extension": {"ignored_by_old_consumers": True}
    }
