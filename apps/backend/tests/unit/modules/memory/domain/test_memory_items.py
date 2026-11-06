"""Memory 內容與兩層來源圖的領域行為。"""

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from caliburn.modules.memory.domain.content import MemoryContent
from caliburn.modules.memory.domain.errors import (
    DuplicateMemoryTitleError,
    InvalidMemoryContentError,
    InvalidMemorySnapshotError,
    InvalidMemorySourceError,
    MemoryItemNotFoundError,
    MemoryVersionExhaustedError,
)
from caliburn.modules.memory.domain.items import WorkSituation, WorkUnderstanding
from caliburn.modules.memory.domain.snapshot import MAX_MEMORY_VERSION
from caliburn.modules.memory.domain.work_memory import WorkMemory


def content(title: str, body: str = "依工單核對數量") -> MemoryContent:
    return MemoryContent(title=title, description="工作摘要", body=body)


@pytest.mark.parametrize("field", ["title", "description", "body"])
@pytest.mark.parametrize("invalid", ["", " \n\t", "原話\x00", "\ud800原話"])
def test_memory_content_rejects_unstorable_text_without_echoing_it(
    field: str, invalid: str
) -> None:
    values = dict.fromkeys(("title", "description", "body"), "工作")
    values[field] = invalid
    with pytest.raises(InvalidMemoryContentError) as rejected:
        MemoryContent.model_validate(values)
    assert "原話" not in str(rejected.value)


def test_content_preserves_exact_text_and_root_fields_are_frozen() -> None:
    text = MemoryContent(title=" 件數 ", description="摘要\n", body="\t🚚\n")
    memory = WorkMemory.create(workspace_id=uuid4())

    assert (text.title, text.description, text.body) == (" 件數 ", "摘要\n", "\t🚚\n")
    assert memory.workspace_id == memory.id
    assert memory.version == 0
    assert memory.published_version is None
    assert memory.items == ()
    # 故意從執行時入口違規賦值，確認凍結不只靠靜態型別檢查。
    with pytest.raises(ValidationError):
        memory.__setattr__("version", 8)


def test_situation_identity_is_stable_and_sources_are_sorted_before_noop() -> None:
    memory = WorkMemory.create(workspace_id=uuid4())
    later, earlier = UUID(int=9), UUID(int=3)
    item_id = memory.create_situation(
        content=content("盤點"), interview_message_ids=(later, earlier)
    )
    item = memory.get_situation(item_id=item_id)

    assert item_id.version == 7
    assert item.kind == "situation"
    assert item.workspace_id == memory.id
    assert item.interview_message_ids == (earlier, later)
    assert item.changed_version == memory.version == 1
    assert memory.situations == (item,)
    assert memory.understandings == ()
    with pytest.raises(ValidationError):
        item.__setattr__("content", content("變更"))
    assert not memory.revise_situation(
        item_id=item_id,
        content=item.content,
        interview_message_ids=(later, earlier),
    )
    assert memory.version == 1


def test_title_is_unique_only_within_the_same_kind_and_exact_spelling() -> None:
    memory = WorkMemory.create(workspace_id=uuid4())
    item_id = memory.create_situation(content=content("Picking"))
    other_id = memory.create_situation(content=content("picking"))
    memory.create_situation(content=content(" Picking "))
    memory.create_understanding(content=content("Picking"), situation_ids=(item_id,))
    before = memory.model_dump()

    with pytest.raises(DuplicateMemoryTitleError):
        memory.create_situation(content=content("Picking"))
    with pytest.raises(DuplicateMemoryTitleError):
        memory.revise_situation(
            item_id=other_id,
            content=content("Picking"),
            interview_message_ids=(),
        )
    assert memory.model_dump() == before


def test_duplicate_dangling_and_wrong_kind_sources_are_atomic_rejections() -> None:
    memory = WorkMemory.create(workspace_id=uuid4())
    source_id = uuid4()
    situation_id = memory.create_situation(content=content("情境"))
    understanding_id = memory.create_understanding(
        content=content("理解"), situation_ids=(situation_id,)
    )
    before = memory.model_dump()

    with pytest.raises(InvalidMemorySourceError):
        memory.revise_situation(
            item_id=situation_id,
            content=content("新情境"),
            interview_message_ids=(source_id, source_id),
        )
    for bad_sources in ((uuid4(),), (understanding_id,), (situation_id, situation_id)):
        with pytest.raises(InvalidMemorySourceError):
            memory.revise_understanding(
                item_id=understanding_id,
                content=content("新理解"),
                situation_ids=bad_sources,
            )
    with pytest.raises(MemoryItemNotFoundError):
        memory.remove_situation(item_id=understanding_id)
    assert memory.model_dump() == before


def test_revise_situation_retains_identity_and_marks_direct_dependants() -> None:
    memory = WorkMemory.create(workspace_id=uuid4())
    situation_id = memory.create_situation(content=content("情境"))
    understanding_id = memory.create_understanding(
        content=content("理解"), situation_ids=(situation_id,)
    )
    unrelated_id = memory.create_understanding(content=content("未引用"))
    before = memory.get_situation(item_id=situation_id)

    assert memory.revise_situation(
        item_id=situation_id, content=before.content, interview_message_ids=(uuid4(),)
    )
    revised = memory.get_situation(item_id=situation_id)

    assert revised == before
    assert revised.interview_message_ids != before.interview_message_ids
    assert revised.changed_version == memory.version == 4
    assert memory.get_understanding(item_id=understanding_id).changed_version == 4
    assert memory.get_understanding(item_id=unrelated_id).changed_version == 3


def test_remove_situation_unlinks_dependants_and_recreating_title_uses_new_id() -> None:
    memory = WorkMemory.create(workspace_id=uuid4())
    situation_id = memory.create_situation(content=content("情境"))
    retained_id = memory.create_situation(content=content("其他情境"))
    understanding_id = memory.create_understanding(
        content=content("理解"), situation_ids=(retained_id, situation_id)
    )

    memory.remove_situation(item_id=situation_id)

    revised = memory.get_understanding(item_id=understanding_id)
    assert revised.situation_ids == (retained_id,)
    assert revised.changed_version == memory.version == 4
    assert memory.create_situation(content=content("情境")) != situation_id
    memory.remove_understanding(item_id=understanding_id)
    assert memory.understandings == ()
    assert memory.version == 6


def test_noop_is_allowed_at_version_limit_but_change_is_atomic_rejection() -> None:
    workspace_id = uuid4()
    item = WorkUnderstanding(
        id=uuid4(),
        workspace_id=workspace_id,
        content=content("理解"),
        situation_ids=(),
        changed_version=MAX_MEMORY_VERSION,
    )
    memory = WorkMemory(id=workspace_id, version=MAX_MEMORY_VERSION, items=(item,))
    before = memory.model_dump()

    assert not memory.revise_understanding(
        item_id=item.id, content=item.content, situation_ids=()
    )
    with pytest.raises(MemoryVersionExhaustedError):
        memory.remove_understanding(item_id=item.id)
    assert memory.model_dump() == before


def test_rehydration_checks_item_workspace_and_stamp() -> None:
    workspace_id = uuid4()
    item = WorkSituation(
        id=uuid4(),
        workspace_id=workspace_id,
        content=content("情境"),
        interview_message_ids=(),
        changed_version=2,
    )
    with pytest.raises(InvalidMemorySnapshotError):
        WorkMemory(id=uuid4(), version=2, items=(item,))
    with pytest.raises(InvalidMemorySnapshotError):
        WorkMemory(id=workspace_id, version=1, items=(item,))
