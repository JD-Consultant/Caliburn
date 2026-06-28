"""jd-ocs-indexer: OCS JSON -> Qdrant index builder.

Embedding (BGE-M3 dense+sparse) is served by apps/embedder over HTTP (ADR 0012);
no torch runs in this process, so the former Windows OpenMP workaround is gone.
"""

__version__ = "0.1.0"
