"""Offline HTTP boundary cases; no RAG imports, running server, or model calls."""

import asyncio
import json
from copy import deepcopy
from dataclasses import FrozenInstanceError
from typing import Any

import httpx2
import pytest

from caliburn.adapters.occupation_references import (
    OccupationReferenceClient,
    ReferenceClientError,
)

REFERENCE_ID = "reference-1"
SOURCE_HASH = "a" * 64


def reference_payload() -> dict[str, Any]:
    return {
        "reference_id": REFERENCE_ID,
        "source_sha256": SOURCE_HASH,
        "source_file": "synthetic.json",
        "ocs_code": "TEST-001",
        "title": "合成職位",
        "overview": "完整概述\n第二行",
        "catalog_scope": "all_parsed_task_groups",
        "units": [
            {
                "unit_id": "u1",
                "code": None,
                "name": "作業",
                "tasks": [
                    {
                        "task_id": "u1-t1",
                        "names": [{"code": "T1", "name": "設計"}, {"code": None, "name": "試作"}],
                        "competency_block_count": 1,
                    },
                    {"task_id": "u1-t2", "names": [], "competency_block_count": 0},
                ],
            }
        ],
    }


def search_payload() -> dict[str, Any]:
    return {
        "references": [
            {
                "reference": reference_payload(),
                "retrieval_evidence": {
                    "document_cosine": 0.5,
                    "task_cosine": None,
                    "matched_task_ids": [],
                    "overview_matched": False,
                    "task_applicability": "not_evaluated",
                },
                "rerank_logit": -1.25,
            }
        ],
        "retrieval_policy": {
            "preprocessing": "ocs_top_body_v1",
            "candidate_limit_per_route": 20,
            "candidate_count": 1,
            "search": "exact_dense_cosine",
            "fusion": "full_union_before_rerank",
            "embedding_model": "synthetic-embedding",
            "embedding_dimensions": 1024,
            "reranker_model": "synthetic-reranker",
            "reranker_revision": "synthetic-revision",
        },
    }


def task_payload() -> dict[str, Any]:
    return {
        "reference_id": REFERENCE_ID,
        "source_sha256": SOURCE_HASH,
        "task_id": "u1-t1",
        "unit_id": "u1",
        "names": [{"code": "T1", "name": "設計"}, {"code": None, "name": "試作"}],
        "competency_blocks": [
            {
                "competency_level": None,
                "outputs": [{"code": "O1", "name": "圖稿"}],
                "indicators": [{"code": "P1", "text": "完整指標\n第二行"}],
                "knowledge": [{"code": None, "name": "材料"}],
                "skills": [{"code": "S1", "name": None}],
            }
        ],
    }


async def test_search_preserves_full_unmatched_catalog_and_borrows_http_client() -> None:
    calls = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        calls.append((request.method, request.url.path, json.loads(request.content)))
        return httpx2.Response(200, json=search_payload())

    async with httpx2.AsyncClient(
        base_url="http://references.invalid", transport=httpx2.MockTransport(respond)
    ) as transport:
        result = await OccupationReferenceClient(transport).search("  實際工作\n原文  ")
        assert not transport.is_closed
    assert calls == [
        ("POST", "/occupation-references:search", {"query": "  實際工作\n原文  ", "limit": 5})
    ]
    reference = result.references[0].reference
    assert reference.reference_id == REFERENCE_ID
    assert reference.source_sha256 == SOURCE_HASH
    assert reference.title == "合成職位"
    assert reference.overview == "完整概述\n第二行"
    assert reference.units[0].tasks[1].task_id == "u1-t2"
    assert reference.units[0].tasks[1].names == ()
    assert reference.units[0].tasks[0].names[1].code is None
    assert result.references[0].retrieval_evidence.task_applicability == "not_evaluated"
    assert result.references[0].rerank_logit == -1.25
    assert result.retrieval_policy.candidate_count == 1
    with pytest.raises(FrozenInstanceError):
        reference.title = "cannot mutate"


async def test_read_and_task_keep_source_identity_shared_names_and_full_body() -> None:
    calls = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        calls.append((request.method, request.url.path))
        body = task_payload() if "/tasks/" in request.url.path else reference_payload()
        return httpx2.Response(200, json=body)

    async with httpx2.AsyncClient(
        base_url="http://references.invalid", transport=httpx2.MockTransport(respond)
    ) as transport:
        client = OccupationReferenceClient(transport)
        reference = await client.read(REFERENCE_ID)
        task = await client.read_task(REFERENCE_ID, "u1-t1")
    assert calls == [
        ("GET", "/occupation-references/reference-1"),
        ("GET", "/occupation-references/reference-1/tasks/u1-t1"),
    ]
    assert reference.units[0].tasks[0].competency_block_count == 1
    assert task.source_sha256 == SOURCE_HASH
    assert task.names[1].name == "試作"
    assert task.competency_blocks[0].indicators[0].text == "完整指標\n第二行"
    assert task.competency_blocks[0].knowledge[0].code is None
    assert task.competency_blocks[0].skills[0].name is None


async def test_successful_empty_search_is_distinct_from_failure() -> None:
    body = search_payload()
    body["references"] = []
    body["retrieval_policy"]["candidate_count"] = 0
    async with httpx2.AsyncClient(
        base_url="http://references.invalid",
        transport=httpx2.MockTransport(lambda _: httpx2.Response(200, json=body)),
    ) as transport:
        result = await OccupationReferenceClient(transport).search("工作")
    assert result.references == ()
    assert result.retrieval_policy.candidate_count == 0


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (404, "reference_not_found"),
        (409, "reference_index_incompatible"),
        (422, "reference_query_invalid"),
        (502, "reference_provider_invalid_response"),
        (503, "reference_service_unavailable"),
        (500, "reference_service_unavailable"),
        (302, "invalid_response"),
    ],
)
async def test_http_failures_do_not_become_empty_success_or_expose_body(status, code) -> None:
    calls = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        calls.append(request)
        return httpx2.Response(status, json={"detail": "private upstream body"})

    async with httpx2.AsyncClient(
        base_url="http://references.invalid", transport=httpx2.MockTransport(respond)
    ) as transport:
        with pytest.raises(ReferenceClientError) as failure:
            await OccupationReferenceClient(transport).search("private query")
    assert failure.value.code == code
    assert "private" not in str(failure.value)
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("error_type", "code"),
    [
        (httpx2.ReadTimeout, "timeout"),
        (httpx2.ConnectError, "reference_service_unavailable"),
    ],
)
async def test_transport_failures_are_typed_once_without_retry(error_type, code) -> None:
    calls = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        calls.append(request)
        raise error_type("private query or provider body", request=request)

    async with httpx2.AsyncClient(
        base_url="http://references.invalid", transport=httpx2.MockTransport(respond)
    ) as transport:
        with pytest.raises(ReferenceClientError) as failure:
            await OccupationReferenceClient(transport).read(REFERENCE_ID)
    assert failure.value.code == code
    assert "private" not in str(failure.value)
    assert len(calls) == 1


@pytest.mark.parametrize(
    "locator", ["", " ", "../ref", "/ref", "ref?x=1", "ref#x", "%2fref", "ref\\other"]
)
async def test_invalid_path_identifiers_never_send_requests(locator) -> None:
    def reject_outbound(_: httpx2.Request) -> httpx2.Response:
        pytest.fail("Invalid path identifiers must not reach HTTP")

    async with httpx2.AsyncClient(
        base_url="http://references.invalid", transport=httpx2.MockTransport(reject_outbound)
    ) as transport:
        client = OccupationReferenceClient(transport)
        for operation in (
            lambda: client.read(locator),
            lambda: client.read_task(REFERENCE_ID, locator),
        ):
            with pytest.raises(ReferenceClientError) as failure:
                await operation()
            assert failure.value.code == "invalid_arguments"


@pytest.mark.parametrize(
    ("query", "limit"),
    [("", 5), ("  ", 5), ("x" * 12_001, 5), ("x", 0), ("x", 6), ("x", True)],
    ids=["empty", "blank", "long", "zero", "too_many", "boolean"],
)
async def test_invalid_query_or_quota_never_sends_requests(query, limit) -> None:
    def reject_outbound(_: httpx2.Request) -> httpx2.Response:
        pytest.fail("Invalid search arguments must not reach HTTP")

    async with httpx2.AsyncClient(
        base_url="http://references.invalid", transport=httpx2.MockTransport(reject_outbound)
    ) as transport:
        with pytest.raises(ReferenceClientError) as failure:
            await OccupationReferenceClient(transport).search(query, limit=limit)
    assert failure.value.code == "invalid_arguments"


@pytest.mark.parametrize(
    "case",
    [
        "missing_catalog",
        "missing_policy",
        "duplicate_reference",
        "duplicate_unit",
        "duplicate_task",
        "unknown_match",
        "wrong_catalog_scope",
        "negative_blocks",
        "string_count",
        "nonfinite_score",
        "too_few_results",
        "bad_source_hash",
        "task_wrong_unit",
    ],
)
async def test_incomplete_or_inconsistent_search_response_is_never_success(case) -> None:
    body = search_payload()
    reference = body["references"][0]["reference"]
    if case == "missing_catalog":
        del reference["units"]
    elif case == "missing_policy":
        del body["retrieval_policy"]
    elif case == "duplicate_reference":
        body["references"].append(deepcopy(body["references"][0]))
        body["retrieval_policy"]["candidate_count"] = 2
    elif case == "duplicate_unit":
        reference["units"].append(deepcopy(reference["units"][0]))
    elif case == "duplicate_task":
        reference["units"][0]["tasks"].append(deepcopy(reference["units"][0]["tasks"][0]))
    elif case == "unknown_match":
        body["references"][0]["retrieval_evidence"]["matched_task_ids"] = ["u9-t1"]
    elif case == "wrong_catalog_scope":
        reference["catalog_scope"] = "matched_only"
    elif case == "negative_blocks":
        reference["units"][0]["tasks"][0]["competency_block_count"] = -1
    elif case == "string_count":
        body["retrieval_policy"]["candidate_count"] = "1"
    elif case == "nonfinite_score":
        body["references"][0]["rerank_logit"] = float("nan")
    elif case == "too_few_results":
        body["retrieval_policy"]["candidate_count"] = 5
    elif case == "bad_source_hash":
        reference["source_sha256"] = "not-a-hash"
    elif case == "task_wrong_unit":
        reference["units"][0]["tasks"][0]["task_id"] = "u2-t1"
    async with httpx2.AsyncClient(
        base_url="http://references.invalid",
        transport=httpx2.MockTransport(lambda _: httpx2.Response(200, content=json.dumps(body))),
    ) as transport:
        with pytest.raises(ReferenceClientError) as failure:
            await OccupationReferenceClient(transport).search("工作")
    assert failure.value.code == "invalid_response"


@pytest.mark.parametrize(
    ("operation", "field", "value"),
    [
        ("read", "reference_id", "other-reference"),
        ("task", "reference_id", "other-reference"),
        ("task", "task_id", "u1-t2"),
        ("task", "unit_id", "u2"),
        ("task", "competency_blocks", None),
    ],
)
async def test_reads_reject_wrong_identity_or_missing_task_body(operation, field, value) -> None:
    body = reference_payload() if operation == "read" else task_payload()
    body[field] = value
    async with httpx2.AsyncClient(
        base_url="http://references.invalid",
        transport=httpx2.MockTransport(lambda _: httpx2.Response(200, json=body)),
    ) as transport:
        client = OccupationReferenceClient(transport)
        with pytest.raises(ReferenceClientError) as failure:
            if operation == "read":
                await client.read(REFERENCE_ID)
            else:
                await client.read_task(REFERENCE_ID, "u1-t1")
    assert failure.value.code == "invalid_response"


async def test_invalid_json_is_typed_without_exposing_raw_body() -> None:
    async with httpx2.AsyncClient(
        base_url="http://references.invalid",
        transport=httpx2.MockTransport(lambda _: httpx2.Response(200, text="private invalid JSON")),
    ) as transport:
        with pytest.raises(ReferenceClientError) as failure:
            await OccupationReferenceClient(transport).read(REFERENCE_ID)
    assert failure.value.code == "invalid_response"
    assert "private" not in str(failure.value)


async def test_request_does_not_follow_redirect_even_with_redirecting_borrowed_client() -> None:
    calls = []

    def redirect(request: httpx2.Request) -> httpx2.Response:
        calls.append(request.url.host)
        return httpx2.Response(307, headers={"location": "http://other.invalid/"})

    async with httpx2.AsyncClient(
        base_url="http://references.invalid",
        follow_redirects=True,
        transport=httpx2.MockTransport(redirect),
    ) as transport:
        with pytest.raises(ReferenceClientError) as failure:
            await OccupationReferenceClient(transport).search("工作")
    assert failure.value.code == "invalid_response"
    assert calls == ["references.invalid"]


async def test_cancellation_propagates_without_becoming_reference_failure() -> None:
    def cancel(_: httpx2.Request) -> httpx2.Response:
        raise asyncio.CancelledError

    async with httpx2.AsyncClient(
        base_url="http://references.invalid", transport=httpx2.MockTransport(cancel)
    ) as transport:
        with pytest.raises(asyncio.CancelledError):
            await OccupationReferenceClient(transport).read(REFERENCE_ID)
