"""歷史欄位差異的整數含引用旗標與發布版號，不等同職能級別。"""

from uuid import uuid7

import pytest
from pydantic import TypeAdapter, ValidationError

from caliburn.modules.job_description.application.history.results import (
    FieldDifference,
    ItemDifference,
    JobDescriptionDifference,
)
from caliburn.modules.job_description.presentation.api.schemas.common import (
    CompetencyLevelInput,
)
from caliburn.modules.job_description.presentation.api.schemas.history import (
    FieldDifferenceResponse,
    JobDescriptionDifferenceResponse,
)


@pytest.mark.parametrize(
    ("field", "value"), [("jd_changed", 0), ("published_version", 10)]
)
def test_citation_integer_difference_keeps_integer_on_json_wire(
    field: str, value: int
) -> None:
    difference = JobDescriptionDifference(
        job_description_id=uuid7(),
        before_version=1,
        after_version=2,
        items=(
            ItemDifference(
                kind="citation",
                id=uuid7(),
                change="modified",
                fields=(FieldDifference(field=field, before=value, after=value + 1),),
            ),
        ),
        collections=(),
    )
    response = JobDescriptionDifferenceResponse.model_validate(difference)
    payload = response.model_dump(mode="json")["items"][0]["fields"][0]
    assert payload == {"field": field, "before": value, "after": value + 1}
    assert type(payload["before"]) is int
    assert type(payload["after"]) is int


@pytest.mark.parametrize("side", ["before", "after"])
def test_difference_schema_declares_general_content_integer(side: str) -> None:
    schema = FieldDifferenceResponse.model_json_schema()
    value_schema = schema["properties"][side]
    if "$ref" in value_schema:
        value_schema = schema["$defs"][value_schema["$ref"].rsplit("/", 1)[1]]
    integer = next(
        alternative
        for alternative in value_schema["anyOf"]
        if alternative.get("type") == "integer"
    )
    assert integer == {"type": "integer"}


@pytest.mark.parametrize("value", [0, 10])
def test_actual_competency_level_still_rejects_out_of_range(value: int) -> None:
    adapter = TypeAdapter(CompetencyLevelInput)
    with pytest.raises(ValidationError):
        adapter.validate_python(value)
    schema = adapter.json_schema()
    assert schema["minimum"] == 1
    assert schema["maximum"] == 6
