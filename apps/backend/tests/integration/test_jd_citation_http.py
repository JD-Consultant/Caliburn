"""不載入 Agent 的 HTTP 引用查讀與原子內容修改。"""

from functools import partial
from uuid import UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from caliburn.modules.interview.application.withdrawal import withdraw_turn
from caliburn.modules.interview.infrastructure.persistence.unit_of_work import (
    SqlAlchemyInterviewUnitOfWork,
)
from caliburn.modules.job_description.infrastructure.persistence import citation_sources
from caliburn.modules.job_description.infrastructure.persistence.queries import (
    SqlAlchemyJobDescriptionQueries,
)
from caliburn.modules.job_description.presentation.api.router import (
    build_job_description_router,
)
from caliburn.modules.memory.infrastructure.persistence.queries import (
    SqlAlchemyMemoryQueries,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.content_scenarios import JD, T1
from tests.integration.content_support import factory, seed_root
from tests.integration.test_jd_citations import source_message


def test_http_keeps_citations_and_reads_withdrawn_source_without_agent(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    seed_root(pg_engine, jd_workspace_id)
    turn, source = source_message(pg_engine, jd_workspace_id)
    app = FastAPI()
    queries = SqlAlchemyJobDescriptionQueries(pg_engine)
    app.include_router(
        build_job_description_router(
            uow_factory=factory(pg_engine),
            queries=queries,
            history_queries=queries,
            citation_sources=citation_sources.SqlAlchemyCitationSourceQueries(
                pg_engine
            ),
            memory_queries=SqlAlchemyMemoryQueries(pg_engine),
        )
    )
    base = f"/workspaces/{jd_workspace_id}/job-descriptions/{JD}"
    with TestClient(app) as client:
        updated = client.patch(
            base + f"/tasks/{T1}",
            json={
                "expected_version": 1,
                "description": "原子描述修改",
                "citations": [
                    {"action": "add", "source": source.model_dump(mode="json")}
                ],
            },
        )
        assert updated.status_code == 200, updated.text
        citation = updated.json()["citations"][0]
        source_path = base + "/citations/" + citation["id"]
        read = client.get(source_path)
        assert read.status_code == 200, read.text
        assert read.json()["source"]["text"] == "合成來源原話"
        assert read.json()["needs_recheck"] is False
        assert client.get(base).json()["citations"] == [citation]
        withdraw_turn(
            workspace_id=jd_workspace_id,
            turn_id=turn,
            uow_factory=partial(
                SqlAlchemyInterviewUnitOfWork, create_session_factory(pg_engine)
            ),
        )
        unavailable = client.get(source_path)
        assert unavailable.status_code == 200
        assert unavailable.json()["source"]["availability"] == "unavailable"
        assert unavailable.json()["source"]["text"] is None
        bad = client.patch(
            base + "/citations",
            json={
                "expected_version": 2,
                "target_kind": "job_description",
                "target_id": str(JD),
                "changes": [
                    {"action": "add", "source": source.model_dump(mode="json")}
                ],
            },
        )
        assert bad.status_code == 422
        assert bad.json()["detail"]["commit_status"] == "not_committed"
        removed = client.patch(
            base + "/citations",
            json={
                "expected_version": 2,
                "target_kind": "task",
                "target_id": str(T1),
                "changes": [{"action": "remove", "citation_id": citation["id"]}],
            },
        )
        assert removed.status_code == 200, removed.text
        assert removed.json()["citations"] == []
