"""The model map is compact output, not strict function arguments or another JD owner."""

import json
from importlib.resources import files
from pathlib import Path
from uuid import UUID

from jsonschema import Draft202012Validator

from caliburn.features.job_description.models import JdProfile
from caliburn.features.job_description.work_models import JdWorkRevision
from caliburn.transport.model_tools.jd_navigation import project_jd_map


def test_map_serialization_keeps_empty_collections_without_unused_preview_nulls() -> None:
    work = JdWorkRevision(UUID(int=1), (), (), (), (), (), ())
    output = project_jd_map(JdProfile(), work).model_dump_json(exclude_unset=True)
    payload = json.loads(output)
    source = Path(__file__).parents[2] / "contracts/tools/jd-map.schema.json"
    schema = json.loads(source.read_text(encoding="utf-8"))
    packaged = files("caliburn.contracts.generated.tools").joinpath("jd-map.schema.json")
    assert json.loads(packaged.read_text(encoding="utf-8")) == schema
    validator = Draft202012Validator(schema)
    validator.validate(payload)
    assert len(payload) == 7
    assert "job_purpose_preview" not in payload["profile"]
    assert not validator.is_valid({**payload, "employee_name": "不屬於 JD 導覽"})
    payload["required_skills"] = [
        {"read_ref": "skill_example", "name": "技能", "description_preview": "不應展開"}
    ]
    assert not validator.is_valid(payload)
