"""統一建立向量服務的 HTTP client；批次由遠端服務管理。"""

from __future__ import annotations

from jd_ocs_indexer.config import Settings
from jd_ocs_indexer.embeddings.http_embedder import HttpEmbedder


def make_embedder(settings: Settings) -> HttpEmbedder:
    return HttpEmbedder(settings.embedder_url)
