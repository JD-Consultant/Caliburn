"""Deterministic embeddings used only by the isolated integration tests."""

from __future__ import annotations

from dataclasses import dataclass, field


EMBEDDING_DIMENSIONS = 8


@dataclass
class DeterministicEmbeddingSpy:
    seen_batches: list[tuple[str, ...]] = field(default_factory=list)

    @property
    def seen_texts(self) -> tuple[str, ...]:
        return tuple(text for batch in self.seen_batches for text in batch)

    async def __call__(self, texts: list[str]) -> list[list[float]]:
        self.seen_batches.append(tuple(texts))
        return [self._vector(text) for text in texts]

    @staticmethod
    def _vector(text: str) -> list[float]:
        groups = (
            ("A 案", "餐飲", "預約", "分店"),
            ("B 案", "健身", "會員", "CSV", "匯入", "場館"),
            ("需求訪談", "前端", "資料串接", "測試", "驗收"),
            ("過敏", "過敏原"),
            ("Safari", "行動版"),
            ("重複訂位", "尖峰"),
            ("退款", "核准"),
        )
        vector = [float(sum(text.count(token) for token in tokens)) for tokens in groups]
        vector.append(0.01)
        return vector
