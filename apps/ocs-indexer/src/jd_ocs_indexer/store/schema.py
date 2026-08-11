"""Collection vectors / payload index spec."""

from __future__ import annotations

from qdrant_client.http import models


def dense_vector_params(size: int = 1024) -> models.VectorParams:
    return models.VectorParams(
        size=size,
        distance=models.Distance.COSINE,
    )


def sparse_vector_params() -> models.SparseVectorParams:
    return models.SparseVectorParams(
        index=models.SparseIndexParams(on_disk=False),
    )


PAYLOAD_INDEXES: list[tuple[str, models.PayloadSchemaType]] = [
    ("chunk_level", models.PayloadSchemaType.KEYWORD),
    ("ocs_code", models.PayloadSchemaType.KEYWORD),
    ("ocs_code_base", models.PayloadSchemaType.KEYWORD),
    ("job_title", models.PayloadSchemaType.TEXT),
    ("is_current", models.PayloadSchemaType.BOOL),
    ("version", models.PayloadSchemaType.KEYWORD),
    ("ocs_level", models.PayloadSchemaType.INTEGER),
    ("industry_codes", models.PayloadSchemaType.KEYWORD),
    ("occupation_codes", models.PayloadSchemaType.KEYWORD),
]
