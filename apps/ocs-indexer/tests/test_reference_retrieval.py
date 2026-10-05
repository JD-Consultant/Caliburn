"""Reference retrieval behavior, including source groups absent from matched chunks."""

import json
from dataclasses import replace

import pytest
from jd_ocs_indexer.references.errors import ReferenceProviderError
from jd_ocs_indexer.references.service import Candidate, ReferenceSearch
from jd_ocs_indexer.references.source import build_reference


def source_document(code="OC1"):
    return build_reference(
        json.dumps(
            {
                "ocs_profile": {
                    "ocs_code": code,
                    "ocs_name": {"occupation_name": "職位標題"},
                    "job_description": "工作內容\n## 網頁服務",
                },
                "ocs_content": {
                    "ocu_units": [
                        {
                            "ocu_code": "U1",
                            "ocu_name": "開發",
                            "tasks": [
                                {
                                    "task_codes": [
                                        {"code": "T1", "name": "介面製作"},
                                        {"code": None, "name": "資料串接"},
                                    ],
                                    "competency_blocks": [
                                        {
                                            "outputs": [{"code": "O1", "name": "O1 網頁"}],
                                            "indicators": [{"code": "P1", "text": "P1 顯示資料"}],
                                            "knowledge": [{"code": None, "name": "工程識圖"}],
                                        }
                                    ],
                                },
                                {
                                    "task_codes": [{"code": "T1", "name": "測試"}],
                                    "competency_blocks": [],
                                },
                                {"task_codes": [], "competency_blocks": []},
                            ],
                        }
                    ]
                },
            },
            ensure_ascii=False,
        ),
        source_file="selected.json",
    )


def test_source_keeps_full_groups_without_embedding_titles_or_codes():
    doc = source_document()
    assert len(doc.tasks) == 3
    assert [t.task_id for t in doc.tasks] == ["u1-t1", "u1-t2", "u1-t3"]
    assert len(doc.tasks[0].group.task_codes) == 2
    assert doc.tasks[0].group.competency_blocks[0].knowledge[0].name == "工程識圖"
    assert doc.document_text == "網頁服務\n開發\n介面製作\n資料串接\n網頁\n顯示資料\n測試"
    assert "職位標題" not in doc.document_text
    assert "工程識圖" not in doc.document_text
    assert (
        build_reference(doc.source_utf8 + "\n", source_file=doc.source_file).reference_id
        != doc.reference_id
    )


class Store:
    def __init__(self, docs):
        self.docs = {d.reference_id: d for d in docs}
        self.validated = False

    def validate_index(self):
        self.validated = True

    def search(self, dense, *, route, limit):
        assert self.validated
        refs = list(self.docs)
        # The task route's extra parent MUST reach rerank, even if D ranks another higher.
        if route == "document":
            return [Candidate(refs[0], 0.9)]
        return [
            Candidate(refs[0], 0.8, ("u1-t1",)),
            Candidate(refs[1], 0.7, ("u1-t2",)),
        ]

    def read(self, reference_id):
        return self.docs[reference_id]


class Ranker:
    model = "test"
    revision = "test"

    def __init__(self):
        self.seen = []

    def score(self, query, documents):
        self.seen = documents
        return [8.0 if "特有工作" in text else -1.0 for text in documents]


def test_full_union_reaches_rerank_before_limit_and_keeps_unmatched_tasks(
    stub_embedder,
):
    first = source_document("A")
    second = replace(source_document("B"), document_text="特有工作")
    ranker = Ranker()
    result = ReferenceSearch(Store([first, second]), stub_embedder, ranker).search(
        "實際工作", limit=1
    )
    assert result.candidate_count == 2
    assert len(ranker.seen) == 2
    assert result.hits[0].document.reference_id == second.reference_id
    assert len(result.hits[0].document.tasks) == 3
    assert result.hits[0].matched_task_ids == ("u1-t2",)


@pytest.mark.parametrize("scores", [[1.0], [float("nan"), 1.0], [float("inf"), 1.0]])
def test_invalid_rerank_result_is_failure_not_empty_hits(stub_embedder, scores):
    ranker = Ranker()
    ranker.score = lambda query, documents: scores
    search = ReferenceSearch(
        Store([source_document("A"), source_document("B")]), stub_embedder, ranker
    )
    with pytest.raises(ReferenceProviderError):
        search.search("工作")
