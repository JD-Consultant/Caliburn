"""從正式工具邊界驗引用比較及不可偽造的固定發布版。"""

import asyncio
import json
from uuid import UUID

import pytest
from langgraph.prebuilt import ToolRuntime

from caliburn.bundles.job_description.services import (
    JD_MEMORY_QUERIES,
    JD_QUERIES,
    JD_REFERENCES,
)
from caliburn.bundles.job_description.source_changes import create_source_changes_tool
from caliburn.bundles.job_description.state import JobDescriptionToolState
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.plugins.services import PluginServices
from caliburn.modules.job_description.application.errors import CitationSourceDataError
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.domain.models.citation import (
    Citation,
    MemoryReference,
)
from caliburn.modules.model_references.contracts import (
    ModelReferenceAllocationError,
    ReferenceTarget,
)
from tests.unit.bundles.job_description.test_citation_reading import (
    CitationReferences,
    Sources,
    citation_runtime,
)
from tests.unit.bundles.job_description.test_projection import snapshot
from tests.unit.modules.job_description.application.test_citation_changes import (
    PublishedQueries,
    published,
)


class CurrentQueries:
    def __init__(self, content: JobDescriptionResult):
        self.content = content

    def get_job_description(
        self, *, workspace_id: UUID, job_description_id: UUID
    ) -> JobDescriptionResult:
        assert workspace_id == self.content.workspace_id
        assert job_description_id == self.content.job_description_id
        return self.content


class SourceReferences(CitationReferences):
    def assigned(self) -> dict[ReferenceTarget, str]:
        return {
            **super().assigned(),
            ReferenceTarget("message", UUID(int=2)): "message_102",
        }


def source_runtime(
    queries: PublishedQueries,
) -> ToolRuntime[AgentContext, JobDescriptionToolState]:
    content = snapshot().model_copy(update={"workspace_id": UUID(int=1)})
    citation = Citation(
        id=UUID(int=11),
        target_kind="task",
        target_id=UUID(int=4),
        source=MemoryReference(
            workspace_id=content.workspace_id, published_version=1, item_id=UUID(int=4)
        ),
    )
    content = content.model_copy(update={"citations": (citation,)})
    scope = citation_runtime(Sources())
    scope.state["workspace_id"] = content.workspace_id
    scope.state["memory_published_version"] = 2
    scope.context = AgentContext(
        PluginServices(
            {
                JD_QUERIES: CurrentQueries(content),
                JD_MEMORY_QUERIES: queries,
                JD_REFERENCES: SourceReferences(),
            }
        )
    )
    return scope


def test_tool_compares_fixed_source_graph_without_advancing_jd_seen_version() -> None:
    scope = source_runtime(
        PublishedQueries(published(1), published(2, text="新原件", stamp=2))
    )
    output = asyncio.run(
        create_source_changes_tool().ainvoke(
            {
                "query": {"kind": "source", "citation_ref": "citation_111"},
                "runtime": scope,
            }
        )
    )
    result = json.loads(output)
    assert result["source_changed"] is True
    assert result["before"]["situations"][0]["body"] == "固定原文"
    assert result["after"]["situations"][0]["body"] == "新原件"
    assert result["after"]["situations"][0]["interview_refs"] == ["message_102"]
    assert str(UUID(int=2)) not in output
    assert scope.state["jd_version"] is None


def test_deleted_source_retains_original_title_without_same_title_replacement() -> None:
    newer = published(2)
    replacement = newer.items[1].model_copy(update={"id": UUID(int=44)})
    newer = newer.model_copy(update={"items": (newer.items[0], replacement)})
    scope = source_runtime(PublishedQueries(published(1), newer))
    result = json.loads(
        asyncio.run(
            create_source_changes_tool().ainvoke(
                {
                    "query": {"kind": "source", "citation_ref": "citation_111"},
                    "runtime": scope,
                }
            )
        )
    )
    assert result["after"] is None
    assert result["before"]["target_title"] == "查驗判斷"


@pytest.mark.parametrize(
    "extra", [{"published_version": 2}, {"workspace_id": str(UUID(int=1))}]
)
def test_model_cannot_supply_scope_or_comparison_version(
    extra: dict[str, object],
) -> None:
    scope = source_runtime(PublishedQueries(published(1), published(2)))
    result = json.loads(
        asyncio.run(
            create_source_changes_tool().ainvoke(
                {
                    "query": {"kind": "source", "citation_ref": "citation_111"},
                    "runtime": scope,
                    **extra,
                }
            )
        )
    )
    assert result["code"] == "invalid_arguments"


def test_no_fixed_comparison_version_does_not_fall_back_to_latest() -> None:
    scope = source_runtime(PublishedQueries())
    scope.state["memory_published_version"] = None
    result = json.loads(
        asyncio.run(
            create_source_changes_tool().ainvoke(
                {
                    "query": {"kind": "source", "citation_ref": "citation_111"},
                    "runtime": scope,
                }
            )
        )
    )
    assert result["code"] == "source_not_available"


def test_broken_fixed_source_is_not_reported_as_ordinary_rejection() -> None:
    scope = source_runtime(PublishedQueries(published(2)))
    with pytest.raises(CitationSourceDataError):
        asyncio.run(
            create_source_changes_tool().ainvoke(
                {
                    "query": {"kind": "source", "citation_ref": "citation_111"},
                    "runtime": scope,
                }
            )
        )


def test_reference_allocation_failure_remains_technical_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failed(*args: object, **kwargs: object) -> None:
        raise ModelReferenceAllocationError("刪除競爭")

    monkeypatch.setattr(SourceReferences, "get_or_create_refs", failed)
    scope = source_runtime(PublishedQueries(published(1), published(2)))
    with pytest.raises(ModelReferenceAllocationError):
        asyncio.run(
            create_source_changes_tool().ainvoke(
                {
                    "query": {"kind": "source", "citation_ref": "citation_111"},
                    "runtime": scope,
                }
            )
        )
