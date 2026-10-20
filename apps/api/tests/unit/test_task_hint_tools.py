"""Task hints must never leak occupation identity, only task content and its K/S/O/P."""

import json

from caliburn.adapters.occupation_reference_models import (
    OccupationReferenceHit,
    ReferenceEvidence,
    ReferenceRetrievalPolicy,
    ReferenceSearchResult,
)
from caliburn.adapters.occupation_references import ReferenceClientError
from caliburn.transport.model_tools.task_hints import TaskHintTools, search_task_hints_definition
from tests.unit.test_occupation_reference_tools import RecordingClient, reference


def _policy(candidate_count: int) -> ReferenceRetrievalPolicy:
    return ReferenceRetrievalPolicy(
        "plain",
        20,
        candidate_count,
        "exact_dense_cosine",
        "full_union_before_rerank",
        "bge-m3",
        1024,
        "reranker",
        "pinned",
    )


class SearchOnlyClient(RecordingClient):
    """Controls exactly which hits/matched_task_ids a search call returns."""

    def __init__(self, hits: tuple[tuple[str, ...], ...]) -> None:
        super().__init__()
        self.hits = hits

    async def search(self, query, *, limit=5):
        self.calls.append(("search", query, limit))
        if self.error:
            raise self.error
        return ReferenceSearchResult(
            tuple(
                OccupationReferenceHit(
                    reference(), ReferenceEvidence(0.8, 0.9, matched, True, "not_evaluated"), 7.8
                )
                for matched in self.hits
            ),
            _policy(len(self.hits)),
        )


def test_definition_only_accepts_a_query_no_occupation_identity_parameter():
    definition = search_task_hints_definition()
    assert definition["name"] == "search_task_hints"
    properties = definition["parameters"]["properties"]
    assert set(properties) == {"query"}


async def test_hints_never_expose_occupation_or_reference_identity():
    client = SearchOnlyClient((("u1-t1",),))
    tools = TaskHintTools(client)
    result = json.loads(await tools.invoke("search_task_hints", '{"query":"接待客人並安排座位"}'))
    assert len(result["hints"]) == 1
    hint = result["hints"][0]
    assert hint["names"] == [{"code": "T1", "name": "實作畫面"}]
    assert hint["competency_blocks"][0]["outputs"] == [{"code": "O1", "name": "可操作畫面"}]
    serialized = json.dumps(result, ensure_ascii=False)
    for forbidden in ("ocs_frontend", "網站前端工程師", "ref_frontend", "reference_id", "unit_id"):
        assert forbidden not in serialized
    assert client.calls == [
        ("search", "接待客人並安排座位", 5),
        ("read_task", "ref_frontend", "u1-t1"),
    ]


async def test_hits_without_a_matched_task_are_skipped_without_reading_detail():
    client = SearchOnlyClient((("u1-t1",), ()))
    tools = TaskHintTools(client)
    result = json.loads(await tools.invoke("search_task_hints", '{"query":"倉庫理貨"}'))
    assert len(result["hints"]) == 1
    assert client.calls == [
        ("search", "倉庫理貨", 5),
        ("read_task", "ref_frontend", "u1-t1"),
    ]


async def test_no_hits_returns_an_empty_list_not_a_rejection():
    client = SearchOnlyClient(())
    tools = TaskHintTools(client)
    result = json.loads(await tools.invoke("search_task_hints", '{"query":"少見的任務描述"}'))
    assert result == {"hints": []}


async def test_invalid_query_is_rejected_before_any_search():
    client = SearchOnlyClient((("u1-t1",),))
    tools = TaskHintTools(client)
    result = json.loads(await tools.invoke("search_task_hints", '{"query":" "}'))
    assert result["status"] == "rejected"
    assert result["code"] == "invalid_arguments"
    assert client.calls == []


async def test_unknown_tool_name_is_rejected():
    client = SearchOnlyClient((("u1-t1",),))
    tools = TaskHintTools(client)
    result = json.loads(await tools.invoke("some_other_tool", "{}"))
    assert result["status"] == "rejected"
    assert result["code"] == "scope_not_allowed"
    assert client.calls == []


async def test_search_failure_surfaces_a_rejection_not_a_crash():
    client = SearchOnlyClient((("u1-t1",),))
    client.error = ReferenceClientError("reference_service_unavailable")
    tools = TaskHintTools(client)
    result = json.loads(await tools.invoke("search_task_hints", '{"query":"接待客人"}'))
    assert result["status"] == "rejected"
    assert result["code"] == "reference_service_unavailable"


async def test_read_task_failure_after_a_successful_search_also_surfaces_a_rejection():
    class FailingDetailClient(SearchOnlyClient):
        async def read_task(self, reference_id, task_id):
            self.calls.append(("read_task", reference_id, task_id))
            raise ReferenceClientError("timeout")

    client = FailingDetailClient((("u1-t1",),))
    tools = TaskHintTools(client)
    result = json.loads(await tools.invoke("search_task_hints", '{"query":"接待客人"}'))
    assert result["status"] == "rejected"
    assert result["code"] == "timeout"
