"""Synthetic public sources and deterministic external model substitutes."""

import json

from caliburn.modules.occupation_reference.application.models import (
    Embedding,
    EmbeddingSignature,
)
from caliburn.modules.occupation_reference.domain.source import (
    ReferenceDocument,
    build_reference,
)


def source_document(
    code: str = "OC1", *, overview: str = "網頁服務"
) -> ReferenceDocument:
    return build_reference(
        json.dumps(
            {
                "ocs_profile": {
                    "ocs_code": code,
                    "ocs_name": {"occupation_name": "職位標題"},
                    "job_description": f"工作內容\n## {overview}",
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
                                        {"code": "T2", "name": "流程整合"},
                                        {"code": None, "name": "資料串接"},
                                    ],
                                    "competency_blocks": [
                                        {
                                            "outputs": [
                                                {"code": "O1", "name": "O1 網頁"}
                                            ],
                                            "indicators": [
                                                {"code": "P1", "text": "P1 顯示資料"}
                                            ],
                                            "knowledge": [
                                                {"code": None, "name": "工程識圖"}
                                            ],
                                            "skills": [
                                                {"code": None, "name": "資料閱讀"}
                                            ],
                                        },
                                        {
                                            "outputs": [
                                                {"code": None, "name": "無碼產出"}
                                            ]
                                        },
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


class FixedEmbedder:
    """Two-dimensional vectors make route selection observable without weights."""

    signature = EmbeddingSignature("test", "fixed", 2, "weights:test;policy:1")

    def __init__(self, vectors: dict[str, list[float]] | None = None) -> None:
        self.vectors = vectors or {}
        self.batch_sizes: list[int] = []

    def embed_query(self, text: str) -> Embedding:
        return Embedding(self.vectors.get(text, [1.0, 0.0]))

    def embed_texts(self, texts: list[str]) -> list[Embedding]:
        self.batch_sizes.append(len(texts))
        return [self.embed_query(text) for text in texts]


class FixedReranker:
    model = "test-reranker"
    revision = "weights:test;policy:1"

    def __init__(self, scores: list[float] | None = None) -> None:
        self.scores = scores

    def score(self, query: str, documents: list[str]) -> list[float]:
        if self.scores is not None:
            return self.scores
        return [8.0 if "特有工作" in text else -1.0 for text in documents]
