"""D/T union, ranking, and provider failures at the public search boundary."""

from contextlib import closing

import pytest
from qdrant_client import QdrantClient

from caliburn.modules.occupation_reference.application.errors import (
    ReferenceProviderError,
    ReferenceQueryError,
)
from caliburn.modules.occupation_reference.application.search import ReferenceSearch
from caliburn.modules.occupation_reference.infrastructure.qdrant.store import (
    QdrantReferenceStore,
    index_references,
)
from tests.unit.modules.occupation_reference.source_support import (
    FixedEmbedder,
    FixedReranker,
    source_document,
)

pytestmark = pytest.mark.filterwarnings("ignore:Payload indexes have no effect")


def test_full_union_reaches_rerank_before_limit_and_keeps_unmatched_tasks() -> None:
    first = source_document("A")
    second = source_document("B", overview="特有工作")
    vectors = {chunk.text: [0.0, 1.0] for chunk in first.chunks + second.chunks}
    vectors[first.document_text] = [1.0, 0.0]
    vectors[second.document_text] = [0.0, 1.0]
    vectors[second.chunks[0].text] = [1.0, 0.0]
    embedder = FixedEmbedder(vectors)
    with closing(QdrantClient(":memory:")) as database:
        index_references(database, "references", [first, second], embedder)
        service = ReferenceSearch(
            QdrantReferenceStore(database, "references", embedder.signature),
            embedder,
            FixedReranker(),
            candidate_limit=1,
        )
        result = service.search("實際工作", limit=1)
        assert result.candidate_count == 2
        assert len(result.hits) == 1
        hit = result.hits[0]
        assert hit.document.reference_id == second.reference_id
        assert hit.document_cosine is None
        assert hit.task_cosine == pytest.approx(1.0)
        assert hit.overview_matched
        assert hit.rerank_logit == 8.0
        assert len(hit.document.tasks) == 3


@pytest.mark.parametrize("scores", [[1.0], [float("nan"), 1.0], [float("inf"), 1.0]])
def test_invalid_rerank_result_is_failure_not_empty_hits(scores: list[float]) -> None:
    embedder = FixedEmbedder()
    with closing(QdrantClient(":memory:")) as database:
        index_references(
            database,
            "references",
            [source_document("A"), source_document("B")],
            embedder,
        )
        search = ReferenceSearch(
            QdrantReferenceStore(database, "references", embedder.signature),
            embedder,
            FixedReranker(scores),
        )
        with pytest.raises(ReferenceProviderError, match="reranker scores"):
            search.search("工作")


def test_equal_rerank_scores_use_ocs_code_for_stable_order() -> None:
    embedder = FixedEmbedder()
    with closing(QdrantClient(":memory:")) as database:
        index_references(
            database,
            "references",
            [source_document("B"), source_document("A")],
            embedder,
        )
        result = ReferenceSearch(
            QdrantReferenceStore(database, "references", embedder.signature),
            embedder,
            FixedReranker(),
        ).search("工作")
        assert [hit.document.ocs_code for hit in result.hits] == ["A", "B"]


@pytest.mark.parametrize("dense", [[0.0, 0.0], [1.0], [float("nan"), 1.0]])
def test_invalid_query_embedding_is_failure(dense: list[float]) -> None:
    embedder = FixedEmbedder()
    with closing(QdrantClient(":memory:")) as database:
        index_references(database, "references", [source_document()], embedder)
        search = ReferenceSearch(
            QdrantReferenceStore(database, "references", embedder.signature),
            FixedEmbedder({"工作": dense}),
            FixedReranker(),
        )
        with pytest.raises(ReferenceProviderError, match="query embedding"):
            search.search("工作")


@pytest.mark.parametrize("query,limit", [(" ", 5), ("x" * 12_001, 5), ("工作", 6)])
def test_invalid_query_is_rejected_before_accessing_index(
    query: str, limit: int
) -> None:
    embedder = FixedEmbedder()
    with closing(QdrantClient(":memory:")) as database:
        search = ReferenceSearch(
            QdrantReferenceStore(database, "missing", embedder.signature),
            embedder,
            FixedReranker(),
        )
        with pytest.raises(ReferenceQueryError):
            search.search(query, limit=limit)
