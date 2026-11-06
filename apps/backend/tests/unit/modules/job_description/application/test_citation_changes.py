"""正式來源引用只比較固定 UUID 與同版來源鏈，不以Entity身分相等判正文。"""

from datetime import UTC, datetime
from typing import Never
from uuid import UUID

import pytest

from caliburn.modules.job_description.application.citation_changes import (
    compare_memory_citation,
)
from caliburn.modules.job_description.application.errors import CitationSourceDataError
from caliburn.modules.job_description.domain.models.citation import MemoryReference
from caliburn.modules.memory.domain.content import MemoryContent
from caliburn.modules.memory.domain.items import WorkSituation, WorkUnderstanding
from caliburn.modules.memory.domain.snapshot import MemorySnapshot


def published(
    version: int, *, stamp: int = 1, text: str = "固定原文"
) -> MemorySnapshot:
    situation = WorkSituation(
        id=UUID(int=3),
        workspace_id=UUID(int=1),
        content=MemoryContent(title="收貨", description="工作情境", body=text),
        interview_message_ids=(UUID(int=2),),
        changed_version=stamp,
    )
    understanding = WorkUnderstanding(
        id=UUID(int=4),
        workspace_id=UUID(int=1),
        content=MemoryContent(
            title="查驗判斷", description="工作理解", body="既有理解"
        ),
        situation_ids=(UUID(int=3),),
        changed_version=stamp,
    )
    return MemorySnapshot(
        workspace_id=UUID(int=1),
        version=version,
        covered_through_message_id=UUID(int=2),
        published_at=datetime.now(UTC),
        items=(situation, understanding),
    )


class PublishedQueries:
    def __init__(self, *snapshots: MemorySnapshot):
        self.snapshots = {snapshot.version: snapshot for snapshot in snapshots}

    def get_published(
        self, *, workspace_id: UUID, published_version: int | None
    ) -> MemorySnapshot | None:
        assert workspace_id == UUID(int=1)
        assert published_version is not None
        return self.snapshots.get(published_version)

    def get_current(self, *, workspace_id: UUID) -> Never:
        raise AssertionError("來源比較不得讀取目前工作 Memory")

    def list_analysis_sources(self, *, workspace_id: UUID, analysis_id: UUID) -> Never:
        raise AssertionError("來源比較不得展開另一分析窗口")


def reference() -> MemoryReference:
    return MemoryReference(
        workspace_id=UUID(int=1), published_version=1, item_id=UUID(int=4)
    )


def test_same_text_with_new_changed_version_remains_a_source_change() -> None:
    result = compare_memory_citation(
        source=reference(),
        published_version=2,
        queries=PublishedQueries(published(1), published(2, stamp=2)),
    )
    assert result.source_changed is True
    assert result.after is not None
    assert result.before.item.content == result.after.item.content


def test_unchanged_item_in_new_publication_is_not_changed() -> None:
    result = compare_memory_citation(
        source=reference(),
        published_version=2,
        queries=PublishedQueries(published(1), published(2)),
    )
    assert result.source_changed is False


def test_deleted_same_title_new_uuid_cannot_replace_fixed_source() -> None:
    newer = published(2)
    renamed_id = newer.items[1].model_copy(update={"id": UUID(int=44)})
    newer = newer.model_copy(update={"items": (newer.items[0], renamed_id)})
    result = compare_memory_citation(
        source=reference(),
        published_version=2,
        queries=PublishedQueries(published(1), newer),
    )
    assert result.source_changed is True and result.after is None
    assert result.before.item.content.title == "查驗判斷"


def test_understanding_compares_its_fixed_situation_body() -> None:
    result = compare_memory_citation(
        source=reference(),
        published_version=2,
        queries=PublishedQueries(published(1), published(2, text="來源改寫", stamp=2)),
    )
    assert result.source_changed is True and result.after is not None
    assert result.before.situations[0].content.body == "固定原文"
    assert result.after.situations[0].content.body == "來源改寫"


def test_missing_fixed_source_is_failure_not_deleted_or_unchanged() -> None:
    with pytest.raises(CitationSourceDataError):
        compare_memory_citation(
            source=reference(),
            published_version=2,
            queries=PublishedQueries(published(2)),
        )
