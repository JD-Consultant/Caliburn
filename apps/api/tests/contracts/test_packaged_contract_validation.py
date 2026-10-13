"""Runtime admission remains available and fail-closed in a deployed package."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

import caliburn
from caliburn.contracts import validation
from caliburn.contracts.generated.tools.read_interview_arguments import ReadInterviewArguments
from caliburn.transport.http.models.job_files import JobFileList


def test_tool_resources_and_shared_http_plan_work_outside_checkout(tmp_path: Path):
    package = tmp_path / "caliburn"
    shutil.copytree(
        Path(caliburn.__file__).parent,
        package,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-B",
            "-c",
            "import sys; from pathlib import Path; "
            "sys.path.insert(0, sys.argv[1]); "
            "import caliburn; "
            "assert Path(caliburn.__file__).parent == Path(sys.argv[1]) / 'caliburn'; "
            "from caliburn.contracts.validation import validate_contract; "
            "from caliburn.contracts.generated.tools.read_interview_arguments "
            "import ReadInterviewArguments; "
            "arguments = validate_contract(ReadInterviewArguments, "
            "{'query': {'kind': 'messages', 'sequences': [1.0]}}); "
            "assert arguments.query.sequences[0].root == 1; "
            "from caliburn.transport.http.models.consultant import InterviewPlanView; "
            "view = InterviewPlanView.model_validate("
            "{'job_file_id':'12345678-1234-4234-8234-1234567890ab', 'plan':'訪談計畫'}); "
            "assert view.plan == '訪談計畫'",
            str(tmp_path),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("created_at", ["2026-10-09T00:00:00Z", "invalid private date"])
def test_date_time_format_is_asserted(created_at):
    value = {
        "job_files": [
            {
                "job_file_id": "12345678-1234-4234-8234-1234567890ab",
                "display_name": "工作",
                "name_revision": 1,
                "employee_name": "員工",
                "created_at": created_at,
            }
        ]
    }
    if created_at.startswith("2026"):
        assert JobFileList.model_validate(value).job_files[0].created_at.year == 2026
    else:
        with pytest.raises(ValidationError) as failure:
            JobFileList.model_validate(value)
        assert failure.value.errors()[0]["type"] == "datetime_from_date_parsing"


@pytest.mark.parametrize("value", ['{"private text":', '{"query": NaN}'])
def test_tool_json_syntax_errors_are_safe(value):
    with pytest.raises(ValidationError) as failure:
        validation.parse_contract(ReadInterviewArguments, value)
    assert failure.value.errors()[0]["ctx"]["kind"] == "json"
    assert value not in str(failure.value)


def test_registry_cannot_retrieve_unlisted_external_resources():
    from referencing.exceptions import NoSuchResource

    _, registry = validation._resources()
    with pytest.raises(NoSuchResource):
        registry.get_or_retrieve("https://example.invalid/private-schema.json")
