"""獨立審查的固定圖反例；不修改受審實作。"""

from uuid import UUID

import pytest

from caliburn.bundles.job_description.manual_changes import project_manual_changes
from caliburn.modules.job_description.application.citation_changes import (
    compare_memory_citation,
)
from caliburn.modules.job_description.application.citation_sources import (
    CitationSourceView,
)
from caliburn.modules.job_description.application.citations import describe_citation
from caliburn.modules.job_description.application.errors import CitationSourceDataError
from caliburn.modules.job_description.domain.models.citation import (
    Citation,
    SourceReference,
)
from caliburn.modules.memory.application.errors import MemoryQueryError
from caliburn.modules.memory.domain.content import MemoryContent
from caliburn.modules.memory.domain.items import WorkSituation
from caliburn.modules.model_references.contracts import ReferenceTarget
from tests.unit.bundles.job_description.test_projection import refs, snapshot
from tests.unit.modules.job_description.application.test_citation_changes import (
    PublishedQueries,
    published,
    reference,
)


def test_unrelated_memory_change_does_not_mark_selected_citation() -> None:
    before, after = published(1), published(2)
    unrelated = WorkSituation(
        id=UUID(int=90),
        workspace_id=before.workspace_id,
        content=MemoryContent(
            title="無關情境", description="獨立說明", body="另一主題"
        ),
        interview_message_ids=(UUID(int=91),),
        changed_version=2,
    )
    after = after.model_copy(update={"items": (*after.items, unrelated)})
    compared = compare_memory_citation(
        source=reference(), published_version=2, queries=PublishedQueries(before, after)
    )
    assert compared.source_changed is False


def test_related_situation_stamp_is_checked_even_when_understanding_is_unchanged() -> (
    None
):
    before, after = published(1), published(2)
    situation = after.items[0].model_copy(update={"changed_version": 2})
    after = after.model_copy(update={"items": (situation, after.items[1])})
    compared = compare_memory_citation(
        source=reference(), published_version=2, queries=PublishedQueries(before, after)
    )
    assert compared.source_changed is True


def test_missing_original_item_in_existing_publication_is_not_a_deletion() -> None:
    before = published(1)
    before = before.model_copy(update={"items": (before.items[0],)})
    with pytest.raises(CitationSourceDataError):
        compare_memory_citation(
            source=reference(),
            published_version=2,
            queries=PublishedQueries(before, published(2)),
        )


def test_public_query_failure_is_preserved_not_forged_as_missing_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure = MemoryQueryError("合成查讀故障")

    def failed(*args: object, **kwargs: object) -> None:
        raise failure

    queries = PublishedQueries(published(1), published(2))
    monkeypatch.setattr(queries, "get_published", failed)
    with pytest.raises(MemoryQueryError) as caught:
        compare_memory_citation(
            source=reference(), published_version=2, queries=queries
        )
    assert caught.value is failure


def test_manual_changes_preserve_removed_memory_citation_original_content() -> None:
    before = snapshot().model_copy(update={"workspace_id": UUID(int=1)})
    citation = Citation(
        id=UUID(int=11), target_kind="task", target_id=UUID(int=4), source=reference()
    )
    before = before.model_copy(update={"citations": (citation,)})
    after = before.model_copy(update={"citations": (), "version": before.version + 1})

    class OriginalSources:
        def read(self, *, source: SourceReference) -> CitationSourceView:
            return CitationSourceView(
                source=source,
                availability="available",
                title="已移除來源的舊標題",
                text="原固定正文",
                item_kind="understanding",
            )

    original = describe_citation(citation=citation, sources=OriginalSources())
    compared = project_manual_changes(
        before,
        after,
        {**refs(), ReferenceTarget("citation", citation.id): "citation_111"},
        before_citations={citation.id: original},
        after_citations={},
    )
    assert compared is not None
    removed = next(item for item in compared["items"] if item["kind"] == "citation")
    assert removed["change"] == "removed"
    assert removed["before"]["target_title"] == "已移除來源的舊標題"
    assert removed["before"]["source_text"] == "原固定正文"
    assert removed["before"]["memory_kind"] == "work_understanding"
    assert removed["after"] is None
