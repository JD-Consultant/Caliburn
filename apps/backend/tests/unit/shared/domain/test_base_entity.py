"""共用 Entity 身分、比較與驗證契約測試。"""

import pytest
from pydantic import ValidationError

from caliburn.shared.domain.base_entity import BaseEntity

ENTITY_ID = 42
OTHER_ENTITY_ID = 43


class NamedEntity(BaseEntity[int]):
    name: str


class OtherEntity(BaseEntity[int]):
    name: str


class ChildEntity(NamedEntity):
    pass


def test_supports_integer_identity() -> None:
    """指定整數 ID 時，基底保留整數身分。"""
    entity = BaseEntity[int](id=42)

    assert entity.id == 42


def test_supports_string_identity() -> None:
    """指定字串 ID 時，基底保留字串身分。"""
    entity = BaseEntity[str](id="entity-42")

    assert entity.id == "entity-42"


def test_requires_identity() -> None:
    """建立 Entity 必須提供 ID，不由基底自行生成。"""
    with pytest.raises(ValidationError) as error:
        BaseEntity[int].model_validate({})

    detail = error.value.errors()[0]
    assert detail["loc"] == ("id",)
    assert detail["type"] == "missing"


@pytest.mark.parametrize("identity", [None, "42", True, 42.0])
def test_integer_identity_rejects_other_types(identity: object) -> None:
    """整數 ID 不接受其他型別，也不將字串、布林或浮點數轉型。"""
    with pytest.raises(ValidationError) as error:
        BaseEntity[int].model_validate({"id": identity})

    detail = error.value.errors()[0]
    assert detail["loc"] == ("id",)
    assert detail["type"] == "int_type"


@pytest.mark.parametrize("identity", [None, 42, b"entity-42"])
def test_string_identity_rejects_other_types(identity: object) -> None:
    """字串 ID 不接受其他型別，不自動轉型。"""
    with pytest.raises(ValidationError) as error:
        BaseEntity[str].model_validate({"id": identity})

    detail = error.value.errors()[0]
    assert detail["loc"] == ("id",)
    assert detail["type"] == "string_type"


def test_identity_cannot_be_reassigned() -> None:
    """合法的新 ID 也不能替換既有身分。"""
    entity = BaseEntity[int](id=ENTITY_ID)

    with pytest.raises(ValidationError) as error:
        entity.__setattr__("id", OTHER_ENTITY_ID)

    assert error.value.errors()[0]["type"] == "frozen_field"
    assert entity.id == ENTITY_ID


def test_identity_cannot_be_deleted() -> None:
    """刪除 ID 被拒絕，Entity 仍保有原身分。"""
    entity = BaseEntity[int](id=ENTITY_ID)

    with pytest.raises(ValidationError) as error:
        del entity.id

    assert error.value.errors()[0]["type"] == "frozen_field"
    assert entity.id == ENTITY_ID


def test_equality_ignores_non_identity_fields() -> None:
    """同型別同 ID 的 Entity 不因其他欄位不同而不相等。"""
    first = NamedEntity(id=ENTITY_ID, name="修改前")
    second = NamedEntity(id=ENTITY_ID, name="修改後")

    assert first == second
    assert second == first


def test_different_identities_are_not_equal() -> None:
    """其他欄位相同也不會合併不同 ID 的身分。"""
    first = NamedEntity(id=ENTITY_ID, name="同名")
    second = NamedEntity(id=OTHER_ENTITY_ID, name="同名")

    assert first != second


@pytest.mark.parametrize(
    "other",
    [
        BaseEntity[int](id=ENTITY_ID),
        OtherEntity(id=ENTITY_ID, name="同名"),
        ChildEntity(id=ENTITY_ID, name="同名"),
    ],
    ids=["base", "sibling", "child"],
)
def test_different_concrete_types_are_not_equal(other: BaseEntity[int]) -> None:
    """基底、其他 Entity 與子類不因 ID 相同而雙向相等。"""
    entity = NamedEntity(id=ENTITY_ID, name="同名")

    assert entity != other
    assert other != entity


def test_unrelated_comparison_returns_not_implemented() -> None:
    """不支援的型別交回 Python 比較協定處理。"""
    entity = BaseEntity[int](id=ENTITY_ID)

    assert entity.__eq__(object()) is NotImplemented


def test_equal_entities_have_the_same_hash() -> None:
    """同身分的 Entity 即使其他欄位不同，hash 仍一致。"""
    first = NamedEntity(id=ENTITY_ID, name="修改前")
    second = NamedEntity(id=ENTITY_ID, name="修改後")

    assert first == second
    assert hash(first) == hash(second)


def test_set_deduplicates_entities_by_identity() -> None:
    """set 合併同身分實例，保留不同 ID 的 Entity。"""
    first = NamedEntity(id=ENTITY_ID, name="修改前")
    same_identity = NamedEntity(id=ENTITY_ID, name="修改後")
    other_identity = NamedEntity(id=OTHER_ENTITY_ID, name="修改前")

    assert len({first, same_identity, other_identity}) == 2


def test_dictionary_lookup_supports_string_identity() -> None:
    """字串 ID 的另一個同身分實例能查到原 dict 項目。"""
    original = BaseEntity[str](id="entity-42")
    reloaded = BaseEntity[str](id="entity-42")
    entries = {original: "已保存"}

    assert entries[reloaded] == "已保存"


def test_non_identity_changes_preserve_hash_and_lookup() -> None:
    """修改非 ID 欄位不改變 hash，也不破壞 set 與 dict 查找。"""
    entity = NamedEntity(id=ENTITY_ID, name="修改前")
    original_hash = hash(entity)
    members = {entity}
    entries = {entity: "已保存"}

    entity.name = "修改後"
    reloaded = NamedEntity(id=ENTITY_ID, name="另一份狀態")

    assert hash(entity) == original_hash
    assert reloaded in members
    assert entries[reloaded] == "已保存"


def test_hash_collisions_do_not_merge_entity_types() -> None:
    """不同 Entity 型別即使 ID 相同，仍保留各自的 dict 項目。"""
    first = NamedEntity(id=ENTITY_ID, name="同名")
    second = OtherEntity(id=ENTITY_ID, name="同名")
    entries = {first: "第一種", second: "第二種"}

    assert len(entries) == 2
    assert entries[first] == "第一種"
    assert entries[second] == "第二種"


def test_unfrozen_fields_validate_assignment() -> None:
    """可變欄位允許合法更新，拒絕錯誤型別且保留原值。"""
    entity = NamedEntity(id=ENTITY_ID, name="修改前")
    entity.name = "修改後"

    with pytest.raises(ValidationError) as error:
        entity.name = 123  # type: ignore[assignment]

    assert error.value.errors()[0]["type"] == "string_type"
    assert entity.name == "修改後"
