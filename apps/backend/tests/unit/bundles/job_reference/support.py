"""真查詢用例與受控外部來源，工具必須經 worker 才能取得資料。"""

import json
from threading import current_thread, main_thread
from typing import Any
from unittest.mock import create_autospec
from uuid import UUID

from langgraph.prebuilt import ToolRuntime

from caliburn.bundles.job_reference import create_bundle
from caliburn.bundles.job_reference.services import (
    REFERENCE_IDS,
    REFERENCE_RUNNER,
    REFERENCE_SEARCH,
)
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.plugins.services import PluginServices
from caliburn.modules.model_references.contracts import ModelReferences, ReferenceTarget
from caliburn.modules.occupation_reference.application.errors import (
    ReferenceNotFoundError,
)
from caliburn.modules.occupation_reference.application.models import Embedding
from caliburn.modules.occupation_reference.application.search import (
    Candidate,
    ReferenceSearch,
)
from caliburn.modules.occupation_reference.domain.source import ReferenceDocument
from caliburn.modules.occupation_reference.infrastructure.execution import (
    RetrievalWorker,
)
from tests.unit.modules.occupation_reference.source_support import (
    FixedEmbedder,
    FixedReranker,
    source_document,
)

WORKSPACE_ID = UUID("00000000-0000-0000-0000-000000000001")


def reference_ids_stub() -> Any:
    """只提供已知外部 I/O 結果；持久配號與隔離由真 PG 測試驗證。"""
    assignments = {
        ReferenceTarget(
            "occupation", UUID(source_document(f"OC{index}").reference_id)
        ): reference
        for index, reference in enumerate(
            (
                "occupation_101",
                "occupation_102",
                "occupation_103",
                "occupation_104",
                "occupation_105",
                "occupation_106",
            )
        )
    }
    resolved = {reference: target for target, reference in assignments.items()}
    references = create_autospec(ModelReferences, instance=True)
    references.get_or_create_refs.side_effect = lambda workspace, targets: {
        target: assignments[target] for target in targets
    }
    references.resolve_refs.side_effect = lambda workspace, refs: {
        reference: resolved[reference] for reference in refs
    }
    return references


class SourceStore:
    def __init__(
        self, documents: list[ReferenceDocument], error: Exception | None = None
    ):
        self.documents = documents
        self.error = error

    def validate_index(self) -> None:
        assert current_thread() is not main_thread()
        if self.error is not None:
            raise self.error

    def search(self, dense: list[float], *, route: str, limit: int) -> list[Candidate]:
        return [
            Candidate(doc.reference_id, 0.8, ("u1-t1",) if route == "task" else ())
            for doc in self.documents[:limit]
        ]

    def read(self, reference_id: str) -> ReferenceDocument:
        for document in self.documents:
            if document.reference_id == reference_id:
                return document
        raise ReferenceNotFoundError("private source")


class QueryEmbedder(FixedEmbedder):
    def __init__(self) -> None:
        super().__init__()
        self.queries: list[str] = []

    def embed_query(self, text: str) -> Embedding:
        self.queries.append(text)
        return super().embed_query(text)


def search_service(
    *, count: int = 1, error: Exception | None = None
) -> tuple[ReferenceSearch, QueryEmbedder]:
    embedder = QueryEmbedder()
    documents = [source_document(f"OC{index}") for index in range(count)]
    return ReferenceSearch(
        SourceStore(documents, error), embedder, FixedReranker()
    ), embedder


async def invoke(
    service: ReferenceSearch,
    name: str,
    arguments: dict[str, object],
    *,
    limit: int = 1_000_000,
    references: ModelReferences | None = None,
    workspace_id: UUID = WORKSPACE_ID,
) -> dict[str, Any]:
    worker = RetrievalWorker()
    try:
        runtime: ToolRuntime[AgentContext, dict[str, object]] = ToolRuntime(
            state={"workspace_id": workspace_id},
            context=AgentContext(
                PluginServices(
                    {
                        REFERENCE_SEARCH: service,
                        REFERENCE_RUNNER: worker,
                        REFERENCE_IDS: references
                        if references is not None
                        else reference_ids_stub(),
                    }
                )
            ),
            config={},
            stream_writer=lambda value: None,
            tool_call_id="reference-call",
            store=None,
        )
        tools = {
            tool.name: tool
            for tool in create_bundle({"max_result_characters": limit}).plugins[0].tools
        }
        result = await tools[name].ainvoke({**arguments, "runtime": runtime})
        assert isinstance(result, str)
        decoded = json.loads(result)
        assert isinstance(decoded, dict)
        return decoded
    finally:
        await worker.aclose()
