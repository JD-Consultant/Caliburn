"""完整工具結果及明確拒絕，不把讀取或模型故障當空資料。"""

import asyncio

import pytest

from caliburn.modules.occupation_reference.application.errors import (
    ReferenceIndexError,
    ReferenceNotFoundError,
    ReferenceProviderError,
    ReferenceQueryError,
    ReferenceUnavailableError,
    RetrievalBusy,
    RetrievalUnavailable,
)
from tests.unit.bundles.job_reference.support import invoke, search_service


def test_search_preserves_query_and_returns_five_complete_catalogs_without_scores() -> (
    None
):
    service, embedder = search_service(count=6)
    query = "  維護網頁\n處理資料  "
    result = asyncio.run(
        invoke(service, "search_occupation_references", {"query": query})
    )
    assert embedder.queries == [query]
    assert set(result) == {"references"}
    assert len(result["references"]) == 5
    reference = result["references"][0]
    assert set(reference) == {
        "reference_id",
        "source_sha256",
        "source_file",
        "ocs_code",
        "title",
        "overview",
        "category",
        "ocs_level",
        "attitudes",
        "notes",
        "catalog_scope",
        "units",
    }
    assert reference["catalog_scope"] == "all_parsed_task_groups"
    assert [task["task_id"] for task in reference["units"][0]["tasks"]] == [
        "u1-t1",
        "u1-t2",
        "u1-t3",
    ]


def test_null_read_matches_search_catalog_and_task_read_keeps_all_blocks() -> None:
    service, _ = search_service()

    async def scenario() -> None:
        found = await invoke(service, "search_occupation_references", {"query": "網頁"})
        expected = found["references"][0]
        arguments = {"reference_id": expected["reference_id"], "task_id": None}
        catalog = await invoke(service, "read_occupation_reference", arguments)
        assert catalog == expected
        task = await invoke(
            service, "read_occupation_reference", {**arguments, "task_id": "u1-t1"}
        )
        assert set(task) == {
            "reference_id",
            "source_sha256",
            "task_id",
            "unit_id",
            "names",
            "competency_blocks",
            "notes",
        }
        assert task["reference_id"] == expected["reference_id"]
        assert task["source_sha256"] == expected["source_sha256"]
        assert task["names"] == [
            {"name": "介面製作"},
            {"name": "流程整合"},
            {"name": "資料串接"},
        ]
        assert task["competency_blocks"] == [
            {
                "competency_level": None,
                "outputs": [{"name": "網頁"}],
                "indicators": [{"text": "顯示資料"}],
                "knowledge": [{"name": "工程識圖"}],
                "skills": [{"name": "資料閱讀"}],
            },
            {
                "competency_level": None,
                "outputs": [{"name": "無碼產出"}],
                "indicators": [],
                "knowledge": [],
                "skills": [],
            },
        ]
        empty = await invoke(
            service, "read_occupation_reference", {**arguments, "task_id": "u1-t3"}
        )
        assert empty["names"] == []
        assert empty["competency_blocks"] == []

    asyncio.run(scenario())


def test_empty_search_is_distinct_from_over_limit_rejection() -> None:
    empty_service, _ = search_service(count=0)
    assert asyncio.run(
        invoke(empty_service, "search_occupation_references", {"query": "網頁"})
    ) == {"references": []}
    service, _ = search_service()
    result = asyncio.run(
        invoke(service, "search_occupation_references", {"query": "網頁"}, limit=50)
    )
    assert result == {
        "status": "rejected",
        "code": "read_limit_exceeded",
        "message": "完整公版資料超過工具輸出容量，未回傳截斷內容。",
        "next_action": "資料容量由 App 處理，不視為已讀或沒有相關任務。",
    }


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"query": None},
        {"query": 3},
        {"query": "  \u001c"},
        {"query": "x" * 12001},
        {"query": "工作", "limit": 1},
    ],
)
def test_invalid_search_arguments_are_safe_and_never_reach_embedding(
    arguments: dict[str, object],
) -> None:
    service, embedder = search_service()
    result = asyncio.run(invoke(service, "search_occupation_references", arguments))
    assert result == {
        "status": "rejected",
        "code": "invalid_arguments",
        "message": "query 或搜尋欄位不合法，本次未執行搜尋。",
        "next_action": (
            "只填非空 query，最多 12,000 字元；使用本人已確認的主要工作，不填其他參數。"
        ),
    }
    assert embedder.queries == []


@pytest.mark.parametrize(
    "arguments",
    [
        {"reference_id": "occupation_101"},
        {"reference_id": "../private", "task_id": None},
        {"reference_id": "occupation_101", "task_id": "T1"},
        {"reference_id": "occupation_101", "task_id": None, "workspace_id": "private"},
        {"reference_id": "task_101", "task_id": None},
        {"reference_id": "occupation_0", "task_id": None},
        {"reference_id": "occupation_01", "task_id": None},
    ],
)
def test_invalid_read_arguments_provide_locator_repair(
    arguments: dict[str, object],
) -> None:
    service, _ = search_service()
    result = asyncio.run(invoke(service, "read_occupation_reference", arguments))
    assert result == {
        "status": "rejected",
        "code": "invalid_arguments",
        "message": "reference_id 或 task_id 不合法，本次未讀取公版。",
        "next_action": (
            "原樣帶回已提供的 occupation_ 公版短碼；task_id 必填，"
            "null 讀目錄，任務定位讀細節。"
        ),
    }


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (ReferenceNotFoundError("private"), "reference_not_found"),
        (ReferenceIndexError("private"), "reference_index_incompatible"),
        (ReferenceProviderError("private"), "reference_provider_invalid_response"),
        (ReferenceQueryError("private"), "reference_query_invalid"),
        (ReferenceUnavailableError("private"), "reference_service_unavailable"),
        (RetrievalBusy("private"), "reference_service_unavailable"),
        (RetrievalUnavailable("private"), "reference_service_unavailable"),
    ],
)
def test_known_failures_keep_their_meaning_and_hide_internal_text(
    error: Exception, code: str
) -> None:
    service, _ = search_service(error=error)
    result = asyncio.run(
        invoke(
            service, "search_occupation_references", {"query": "private employee query"}
        )
    )
    assert result["status"] == "rejected"
    assert result["code"] == code
    assert "private" not in str(result)


def test_unknown_failure_propagates() -> None:
    service, _ = search_service(error=ValueError("implementation defect"))
    with pytest.raises(ValueError, match="implementation defect"):
        asyncio.run(invoke(service, "search_occupation_references", {"query": "網頁"}))
