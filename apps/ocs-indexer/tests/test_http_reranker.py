"""Validate the provider boundary and batch without giving models index parameters."""

import json

import httpx
import pytest
from jd_ocs_indexer.references.errors import ReferenceProviderError, ReferenceQueryError
from jd_ocs_indexer.reranking.http_reranker import MODEL, REVISION, HttpReranker


def test_reranker_batches_full_union_in_order_and_does_not_close_borrowed_client():
    lengths = []

    def handler(request):
        body = json.loads(request.content)
        lengths.append(len(body["documents"]))
        return httpx.Response(
            200,
            json={
                "model": MODEL,
                "revision": REVISION,
                "scores": [float(text) for text in body["documents"]],
            },
        )

    with httpx.Client(
        base_url="http://local-model", transport=httpx.MockTransport(handler)
    ) as client:
        ranker = HttpReranker("http://local-model", client=client)
        assert ranker.score("work", [str(i) for i in range(81)]) == list(range(81))
        assert lengths == [32, 32, 17]
        ranker.close()
        assert not client.is_closed


@pytest.mark.parametrize(
    "body",
    [
        {"scores": [1]},
        {"model": MODEL, "revision": "wrong", "scores": [1]},
        {"model": MODEL, "revision": REVISION, "scores": []},
    ],
)
def test_bad_reranker_result_is_not_silently_accepted(body):
    with httpx.Client(
        base_url="http://local",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json=body),
        ),
    ) as client:
        with pytest.raises(ReferenceProviderError):
            HttpReranker("http://local", client=client).score("work", ["public body"])


def test_query_capacity_rejection_is_distinct_from_service_failure():
    with httpx.Client(
        base_url="http://local",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(422, json={"detail": {"code": "query_too_long"}}),
        ),
    ) as client:
        with pytest.raises(ReferenceQueryError):
            HttpReranker("http://local", client=client).score("work", ["public body"])
