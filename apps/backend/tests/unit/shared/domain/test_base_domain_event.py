"""Domain Event 的必要資訊、嚴格驗證與不可變契約測試。"""

from datetime import UTC, datetime, timedelta, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from caliburn.shared.domain.base_domain_event import BaseDomainEvent

EVENT_ID = UUID("0199a000-0000-7000-8000-000000000001")
OCCURRED_AT = datetime(2026, 10, 19, 8, 30, tzinfo=UTC)


class NameRecorded(BaseDomainEvent[UUID]):
    name: str


class NumberRecorded(BaseDomainEvent[int]):
    number: int


def test_preserves_supplied_identity_time_and_fact() -> None:
    """事件保留呼叫端提供的身分、發生時間與事實資料。"""
    event = NameRecorded(event_id=EVENT_ID, occurred_at=OCCURRED_AT, name="王小明")

    assert event.event_id == EVENT_ID
    assert event.occurred_at == OCCURRED_AT
    assert event.name == "王小明"
    assert NumberRecorded(event_id=42, occurred_at=OCCURRED_AT, number=7).event_id == 42


@pytest.mark.parametrize("missing", ["event_id", "occurred_at"])
def test_requires_identity_and_time(missing: str) -> None:
    """重建事件必須提供原身分與發生時間，不隱式生成新事件。"""
    data: dict[str, object] = {
        "event_id": EVENT_ID,
        "occurred_at": OCCURRED_AT,
        "name": "王小明",
    }
    del data[missing]

    with pytest.raises(ValidationError) as error:
        NameRecorded.model_validate(data)

    assert error.value.errors()[0]["loc"] == (missing,)
    assert error.value.errors()[0]["type"] == "missing"


def test_rejects_naive_occurrence_time() -> None:
    """拒絕沒有時區的發生時間，避免同一事件被解讀為不同時刻。"""
    with pytest.raises(ValidationError) as error:
        NameRecorded(
            event_id=EVENT_ID,
            occurred_at=datetime(2026, 10, 19, 8, 30),
            name="王小明",
        )

    assert error.value.errors()[0]["type"] == "timezone_aware"


def test_accepts_an_explicit_non_utc_timezone() -> None:
    """帶時區時間可明確表示同一時刻，不要求呼叫端只能提供 UTC。"""
    local_time = datetime(2026, 10, 19, 16, 30, tzinfo=timezone(timedelta(hours=8)))
    event = NameRecorded(event_id=EVENT_ID, occurred_at=local_time, name="王小明")

    assert event.occurred_at == OCCURRED_AT
    assert event.occurred_at.utcoffset() == timedelta(hours=8)


@pytest.mark.parametrize(
    ("field", "value"),
    [("event_id", str(EVENT_ID)), ("occurred_at", OCCURRED_AT.isoformat())],
)
def test_python_input_does_not_coerce_metadata(field: str, value: object) -> None:
    """Python 呼叫必須提供正確 ID 與時間型別，不靠隱式解析。"""
    data: dict[str, object] = {
        "event_id": EVENT_ID,
        "occurred_at": OCCURRED_AT,
        "name": "王小明",
    }
    data[field] = value

    with pytest.raises(ValidationError) as error:
        NameRecorded.model_validate(data)

    assert error.value.errors()[0]["loc"] == (field,)


def test_rejects_undeclared_event_data() -> None:
    """未宣告的資料不能靜默丟失，事件形狀由具體型別定義。"""
    with pytest.raises(ValidationError) as error:
        NameRecorded.model_validate(
            {
                "event_id": EVENT_ID,
                "occurred_at": OCCURRED_AT,
                "name": "王小明",
                "status": "processing",
            }
        )

    assert error.value.errors()[0]["type"] == "extra_forbidden"


@pytest.mark.parametrize("field", ["event_id", "occurred_at", "name"])
@pytest.mark.parametrize("action", ["assign", "delete"])
def test_event_metadata_and_fact_cannot_be_changed(field: str, action: str) -> None:
    """事件建立後，metadata 與業務事實都不可直接修改或刪除。"""
    event = NameRecorded(event_id=EVENT_ID, occurred_at=OCCURRED_AT, name="王小明")

    with pytest.raises(ValidationError) as error:
        if action == "assign":
            setattr(event, field, getattr(event, field))
        else:
            delattr(event, field)

    assert error.value.errors()[0]["type"] == "frozen_instance"


def test_serialization_reconstructs_the_same_event() -> None:
    """JSON 還原保留原事件 ID、時間及事實，不重新生成 metadata。"""
    event = NameRecorded(event_id=EVENT_ID, occurred_at=OCCURRED_AT, name="王小明")

    restored = NameRecorded.model_validate_json(event.model_dump_json())

    assert restored.event_id == EVENT_ID
    assert restored.occurred_at == OCCURRED_AT
    assert restored.name == "王小明"
