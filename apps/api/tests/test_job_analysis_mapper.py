"""Domain/wire mapping at the greenfield job-analysis transport seam."""

from job_analysis_contract import JdTaskWrite

from app.api.job_analysis_mapper import to_jd_task_fields
from app.job_analysis.domain import EnablerKind, ResponsibilityRole


def test_write_mapper_covers_and_normalizes_every_employee_editable_field():
    body = JdTaskWrite.model_validate(
        {
            "statement": " 每週彙整營運週報 ",
            "purpose_result": " 讓主管掌握營運狀況 ",
            "context": "   ",
            "frequency_text": " 每週一次 ",
            "responsibility_role": "primary",
            "enablers": [
                {"kind": "tool_system", "name": " Excel "},
                {"kind": "method", "name": " 交叉檢查 "},
            ],
        }
    )

    fields = to_jd_task_fields(body)

    assert fields.statement == "每週彙整營運週報"
    assert fields.purpose_result == "讓主管掌握營運狀況"
    assert fields.context is None
    assert fields.frequency_text == "每週一次"
    assert fields.responsibility_role is ResponsibilityRole.PRIMARY
    assert [(item.kind, item.name) for item in fields.enablers] == [
        (EnablerKind.TOOL_SYSTEM, "Excel"),
        (EnablerKind.METHOD, "交叉檢查"),
    ]


def test_empty_responsibility_role_normalizes_to_none():
    body = JdTaskWrite.model_validate(
        {
            "statement": "盤點耗材",
            "purpose_result": None,
            "context": None,
            "frequency_text": None,
            "responsibility_role": "",
            "enablers": [],
        }
    )

    assert to_jd_task_fields(body).responsibility_role is None
