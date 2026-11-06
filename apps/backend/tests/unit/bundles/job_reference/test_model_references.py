"""公版模型定位只接受 Workspace 內短碼，模組仍維持固定來源 UUID。"""

import asyncio
from uuid import UUID

import pytest

from caliburn.modules.model_references.contracts import (
    InvalidModelReferenceError,
    ReferenceTarget,
    UnknownModelReferenceError,
)
from tests.unit.bundles.job_reference.support import (
    WORKSPACE_ID,
    invoke,
    reference_ids_stub,
    search_service,
)
from tests.unit.modules.occupation_reference.source_support import source_document


def test_read_rejects_source_uuid_instead_of_bypassing_model_reference_scope() -> None:
    service, _ = search_service()
    result = asyncio.run(
        invoke(
            service,
            "read_occupation_reference",
            {"reference_id": source_document("OC0").reference_id, "task_id": None},
        )
    )
    assert result["status"] == "rejected"
    assert result["code"] == "invalid_arguments"
    assert "occupation_" in result["next_action"]


def test_search_returns_batch_assigned_refs_for_the_runtime_workspace() -> None:
    service, _ = search_service(count=6)
    references = reference_ids_stub()
    result = asyncio.run(
        invoke(
            service,
            "search_occupation_references",
            {"query": "網頁"},
            references=references,
        )
    )
    assert [item["reference_id"] for item in result["references"]] == [
        "occupation_101",
        "occupation_102",
        "occupation_103",
        "occupation_104",
        "occupation_105",
    ]
    references.get_or_create_refs.assert_called_once_with(
        WORKSPACE_ID,
        [
            ReferenceTarget(
                "occupation", UUID(source_document(f"OC{index}").reference_id)
            )
            for index in range(5)
        ],
    )
    assert source_document("OC0").reference_id not in str(result)


@pytest.mark.parametrize(
    "error",
    [
        UnknownModelReferenceError("occupation_101", "private workspace"),
        InvalidModelReferenceError("occupation_101", "private mapping error"),
    ],
)
def test_reference_resolution_errors_have_safe_repair_guidance(
    error: Exception,
) -> None:
    service, _ = search_service()
    references = reference_ids_stub()
    references.resolve_refs.side_effect = error
    result = asyncio.run(
        invoke(
            service,
            "read_occupation_reference",
            {"reference_id": "occupation_101", "task_id": None},
            references=references,
        )
    )
    assert result["code"] == "invalid_reference"
    assert result["status"] == "rejected"
    assert "occupation_" in result["next_action"]
    assert "private" not in str(result)
    references.resolve_refs.assert_called_once_with(WORKSPACE_ID, ["occupation_101"])


def test_read_checks_resolved_resource_kind_before_reading_global_source() -> None:
    service, _ = search_service()
    references = reference_ids_stub()
    references.resolve_refs.side_effect = None
    references.resolve_refs.return_value = {
        "occupation_101": ReferenceTarget(
            "task", UUID(source_document("OC0").reference_id)
        )
    }
    result = asyncio.run(
        invoke(
            service,
            "read_occupation_reference",
            {"reference_id": "occupation_101", "task_id": None},
            references=references,
        )
    )
    assert result["code"] == "invalid_reference"
    assert "units" not in result


def test_mapping_commit_failure_does_not_return_an_unpersisted_reference() -> None:
    service, _ = search_service()
    references = reference_ids_stub()
    references.get_or_create_refs.side_effect = RuntimeError("mapping commit failed")
    with pytest.raises(RuntimeError, match="mapping commit failed"):
        asyncio.run(
            invoke(
                service,
                "search_occupation_references",
                {"query": "網頁"},
                references=references,
            )
        )
