"""公版工具使用真 PG 短碼；Qdrant 記憶體模式與固定外部模型不驗服務部署。"""

import asyncio
import re
from collections.abc import Iterator
from contextlib import closing
from uuid import UUID

import pytest
from qdrant_client import QdrantClient
from sqlalchemy import Engine

from caliburn.modules.model_references.contracts import ReferenceTarget
from caliburn.modules.model_references.persistence import SqlAlchemyModelReferences
from caliburn.modules.occupation_reference.application.search import ReferenceSearch
from caliburn.modules.occupation_reference.infrastructure.qdrant.store import (
    QdrantReferenceStore,
    index_references,
)
from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.infrastructure.persistence.unit_of_work import (
    SqlAlchemyWorkspaceUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import (
    create_database_engine,
    create_session_factory,
)
from tests.unit.bundles.job_reference.support import invoke
from tests.unit.modules.occupation_reference.source_support import (
    FixedEmbedder,
    FixedReranker,
    source_document,
)

pytestmark = pytest.mark.filterwarnings("ignore:Payload indexes have no effect")


@pytest.fixture
def reference_search() -> Iterator[ReferenceSearch]:
    embedder = FixedEmbedder()
    with closing(QdrantClient(":memory:")) as database:
        index_references(database, "reference_test", [source_document()], embedder)
        yield ReferenceSearch(
            QdrantReferenceStore(database, "reference_test", embedder.signature),
            embedder,
            FixedReranker(),
        )


def test_searched_reference_remains_readable_after_database_engine_reopens(
    pg_engine: Engine,
    jd_workspace_id: UUID,
    reference_search: ReferenceSearch,
) -> None:
    first_engine = create_database_engine(pg_engine.url)
    try:
        references = SqlAlchemyModelReferences(create_session_factory(first_engine))
        searched = asyncio.run(
            invoke(
                reference_search,
                "search_occupation_references",
                {"query": "網頁服務"},
                references=references,
                workspace_id=jd_workspace_id,
            ),
            loop_factory=asyncio.SelectorEventLoop,
        )
    finally:
        first_engine.dispose()

    catalog = searched["references"][0]
    reference_id = catalog["reference_id"]
    assert re.fullmatch(r"occupation_[1-9][0-9]*", reference_id)
    reopened_engine = create_database_engine(pg_engine.url)
    try:
        reopened = SqlAlchemyModelReferences(create_session_factory(reopened_engine))

        async def read_and_search_again() -> None:
            read = await invoke(
                reference_search,
                "read_occupation_reference",
                {"reference_id": reference_id, "task_id": None},
                references=reopened,
                workspace_id=jd_workspace_id,
            )
            assert read == catalog
            searched_again = await invoke(
                reference_search,
                "search_occupation_references",
                {"query": "資料串接"},
                references=reopened,
                workspace_id=jd_workspace_id,
            )
            assert searched_again == searched

        asyncio.run(read_and_search_again(), loop_factory=asyncio.SelectorEventLoop)
        assert reopened.resolve_refs(jd_workspace_id, [reference_id]) == {
            reference_id: ReferenceTarget(
                "occupation", UUID(source_document().reference_id)
            )
        }
    finally:
        reopened_engine.dispose()


@pytest.mark.parametrize("task_id", [None, "u1-t1"])
def test_same_global_source_has_distinct_workspace_refs_and_rejects_cross_read(
    pg_engine: Engine,
    jd_workspace_id: UUID,
    reference_search: ReferenceSearch,
    task_id: str | None,
) -> None:
    sessions = create_session_factory(pg_engine)
    references = SqlAlchemyModelReferences(sessions)
    other_workspace = WorkspaceService(
        lambda: SqlAlchemyWorkspaceUnitOfWork(sessions)
    ).create(interviewee_name="另一份合成工作區")

    async def run() -> None:
        first = await invoke(
            reference_search,
            "search_occupation_references",
            {"query": "網頁服務"},
            references=references,
            workspace_id=jd_workspace_id,
        )
        other = await invoke(
            reference_search,
            "search_occupation_references",
            {"query": "網頁服務"},
            references=references,
            workspace_id=other_workspace.workspace_id,
        )
        first_catalog = first["references"][0]
        other_catalog = other["references"][0]
        first_ref = first_catalog["reference_id"]
        other_ref = other_catalog["reference_id"]
        assert first_ref != other_ref
        assert other_catalog == {**first_catalog, "reference_id": other_ref}
        source = ReferenceTarget("occupation", UUID(source_document().reference_id))
        assert references.resolve_refs(jd_workspace_id, [first_ref]) == {
            first_ref: source
        }
        assert references.resolve_refs(other_workspace.workspace_id, [other_ref]) == {
            other_ref: source
        }

        own_read = await invoke(
            reference_search,
            "read_occupation_reference",
            {"reference_id": other_ref, "task_id": None},
            references=references,
            workspace_id=other_workspace.workspace_id,
        )
        assert own_read == other_catalog
        cross_read = await invoke(
            reference_search,
            "read_occupation_reference",
            {"reference_id": first_ref, "task_id": task_id},
            references=references,
            workspace_id=other_workspace.workspace_id,
        )
        assert cross_read["status"] == "rejected"
        assert cross_read["code"] == "invalid_reference"
        assert "occupation_" in cross_read["next_action"]
        assert "units" not in cross_read
        assert source_document().reference_id not in str(cross_read)

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


@pytest.mark.parametrize(
    ("locator", "code"),
    [
        ("wrong_kind", "invalid_arguments"),
        ("changed_prefix", "invalid_reference"),
        ("source_uuid", "invalid_arguments"),
        ("unknown", "invalid_reference"),
    ],
)
def test_public_read_rejects_non_occupation_locator_without_global_source_bypass(
    pg_engine: Engine,
    jd_workspace_id: UUID,
    reference_search: ReferenceSearch,
    locator: str,
    code: str,
) -> None:
    references = SqlAlchemyModelReferences(create_session_factory(pg_engine))
    document = source_document()
    task = ReferenceTarget("task", UUID(document.reference_id))
    task_ref = references.get_or_create_refs(jd_workspace_id, [task])[task]
    rejected = {
        "wrong_kind": task_ref,
        "changed_prefix": task_ref.replace("task_", "occupation_"),
        "source_uuid": document.reference_id,
        "unknown": "occupation_9223372036854775807",
    }[locator]

    result = asyncio.run(
        invoke(
            reference_search,
            "read_occupation_reference",
            {"reference_id": rejected, "task_id": None},
            references=references,
            workspace_id=jd_workspace_id,
        ),
        loop_factory=asyncio.SelectorEventLoop,
    )

    assert result["status"] == "rejected"
    assert result["code"] == code
    assert "occupation_" in result["next_action"]
    assert "units" not in result
    assert document.reference_id not in str(result)
    assert reference_search.read(document.reference_id) == document
