"""Small actual-engine check, isolated collection, not occupation quality."""

from uuid import uuid4

import numpy as np
import pytest
from qdrant_client import QdrantClient, models

from evaluation import rrf


def test_actual_qdrant_exact_cosine_and_rrf_contract():
    client = QdrantClient(url="http://127.0.0.1:6335", trust_env=False)
    name = f"ocs_eval_contract_{uuid4().hex}"
    client.create_collection(name, vectors_config={"dense": models.VectorParams(
        size=2, distance=models.Distance.COSINE)}, sparse_vectors_config={"sparse": models.SparseVectorParams()})
    points = [models.PointStruct(id=i, vector={"dense": vector,
        "sparse": models.SparseVector(indices=[1], values=[weight])})
        for i, (vector, weight) in enumerate([([1, 0], 1), ([0.8, 0.6], 3), ([0, 1], 2)])]
    client.upsert(name, points, wait=True)
    query = [1.0, 0.0]
    exact = client.query_points(name, query=query, using="dense", limit=3,
                                search_params=models.SearchParams(exact=True)).points
    assert [point.id for point in exact] == [0, 1, 2]
    np.testing.assert_allclose([point.score for point in exact], [1, 0.8, 0], atol=1e-6)
    sparse = models.SparseVector(indices=[1], values=[1])
    fused = client.query_points(name, prefetch=[
        models.Prefetch(query=query, using="dense", limit=3),
        models.Prefetch(query=sparse, using="sparse", limit=3)],
        query=models.RrfQuery(rrf=models.Rrf(k=60)), limit=3).points
    offline = rrf([[0, 1, 2], [1, 2, 0]], depth=3, constant=60)
    assert [point.id for point in fused] == [key for key, _ in offline]
    assert [point.score for point in fused] == pytest.approx([score for _, score in offline], abs=1e-7)
    # Keep the tiny collection as evidence; do not delete any collection.
    client.close()
