"""讀工具展開引用的業務結果，技術失敗不可冒充來源撤回。"""

import asyncio
import json
from collections.abc import Collection
from uuid import UUID

import pytest
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command

from caliburn.bundles.job_description.reading import create_read_tool
from caliburn.bundles.job_description.services import (
    JD_CITATION_SOURCES,
    JD_QUERIES,
    JD_REFERENCES,
)
from caliburn.bundles.job_description.state import JobDescriptionToolState
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.plugins.services import PluginServices
from caliburn.modules.job_description.application.citation_sources import (
    CitationSourceView,
)
from caliburn.modules.job_description.application.errors import CitationSourceDataError
from caliburn.modules.job_description.domain.models.citation import (
    Citation,
    InterviewReference,
    SourceReference,
)
from caliburn.modules.model_references.contracts import ReferenceTarget
from tests.unit.bundles.job_description.test_projection import refs, snapshot
from tests.unit.bundles.job_description.test_read import Queries, References, runtime


class CitationReferences(References):
    def get_or_create_refs(
        self, workspace_id: UUID, targets: Collection[ReferenceTarget]
    ) -> dict[ReferenceTarget, str]:
        return {target: self.assigned()[target] for target in targets}

    def resolve_refs(
        self, workspace_id: UUID, requested: Collection[str]
    ) -> dict[str, ReferenceTarget]:
        assigned = {value: key for key, value in self.assigned().items()}
        return {value: assigned[value] for value in requested}

    def assigned(self) -> dict[ReferenceTarget, str]:
        return {
            **refs(),
            ReferenceTarget("citation", UUID(int=11)): "citation_111",
            ReferenceTarget("message", UUID(int=12)): "message_112",
        }


class Sources:
    def __init__(self, *, unavailable: bool = False, broken: bool = False):
        self.unavailable = unavailable
        self.broken = broken

    def read(self, *, source: SourceReference) -> CitationSourceView:
        if self.broken:
            raise CitationSourceDataError("壞掉的來源資料")
        return CitationSourceView(
            source=source,
            availability="unavailable" if self.unavailable else "available",
            text=None if self.unavailable else "固定訪談原文",
        )


def citation_runtime(
    sources: Sources,
) -> ToolRuntime[AgentContext, JobDescriptionToolState]:
    content = snapshot()
    citation = Citation(
        id=UUID(int=11),
        target_kind="task",
        target_id=UUID(int=4),
        source=InterviewReference(
            workspace_id=content.workspace_id, message_id=UUID(int=12)
        ),
        jd_changed=True,
    )
    content = content.model_copy(update={"citations": (citation,)})
    scope = runtime(Queries(content))
    scope.context = AgentContext(
        PluginServices(
            {
                JD_QUERIES: Queries(content),
                JD_REFERENCES: CitationReferences(),
                JD_CITATION_SOURCES: sources,
            }
        )
    )
    return scope


@pytest.mark.parametrize("unavailable", [False, True])
def test_citation_item_expands_source_and_preserves_unavailable_locator(
    unavailable: bool,
) -> None:
    result = asyncio.run(
        create_read_tool().ainvoke(
            {
                "view": "item",
                "read_ref": "citation_111",
                "runtime": citation_runtime(Sources(unavailable=unavailable)),
            }
        )
    )
    assert isinstance(result, Command) and isinstance(result.update, dict)
    item = json.loads(result.update["messages"][0].content)["item"]
    assert item["availability"] == ("unavailable" if unavailable else "available")
    assert item["source_text"] == (None if unavailable else "固定訪談原文")
    assert item["needs_recheck"] is True
    assert item["source_changed"] is False
    assert item["message_ref"] == "message_112"


def test_source_message_ref_is_not_a_jd_item() -> None:
    result = asyncio.run(
        create_read_tool().ainvoke(
            {
                "view": "item",
                "read_ref": "message_112",
                "runtime": citation_runtime(Sources()),
            }
        )
    )
    assert isinstance(result, str)
    assert json.loads(result)["code"] == "target_not_found"


def test_source_data_failure_is_not_reported_as_unavailable() -> None:
    with pytest.raises(CitationSourceDataError):
        asyncio.run(
            create_read_tool().ainvoke(
                {"view": "map", "runtime": citation_runtime(Sources(broken=True))}
            )
        )
