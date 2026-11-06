"""指定歷史 JD 版回查來源；目前稿及最新 Memory 不得取代歷史定位。"""

from functools import partial
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

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
from caliburn.modules.memory.application.inputs import MemoryWriteContext
from caliburn.modules.memory.application.service import MemoryService
from caliburn.modules.memory.domain.content import MemoryContent
from caliburn.modules.memory.infrastructure.persistence.queries import (
    SqlAlchemyMemoryQueries,
)
from caliburn.modules.memory.infrastructure.persistence.unit_of_work import (
    SqlAlchemyMemoryUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.content_scenarios import JD, T1
from tests.integration.content_support import factory, read_current, seed_root
from tests.integration.test_jd_citations import CompletedTurns, source_message


def http_app(engine: Engine) -> tuple[FastAPI, SqlAlchemyJobDescriptionQueries]:
    app = FastAPI()
    queries = SqlAlchemyJobDescriptionQueries(engine)
    app.include_router(
        build_job_description_router(
            uow_factory=factory(engine),
            queries=queries,
            history_queries=queries,
            citation_sources=citation_sources.SqlAlchemyCitationSourceQueries(engine),
            memory_queries=SqlAlchemyMemoryQueries(engine),
        )
    )
    return app, queries


def test_historical_interview_citation_survives_current_edits_and_removal(
    pg_engine: Engine, jd_workspace_id: UUID, monkeypatch: pytest.MonkeyPatch
) -> None:
    seed_root(pg_engine, jd_workspace_id)
    turn_id, source = source_message(pg_engine, jd_workspace_id)
    app, queries = http_app(pg_engine)
    base = f"/workspaces/{jd_workspace_id}/job-descriptions/{JD}"
    with TestClient(app) as client:
        attached = client.patch(
            base + f"/tasks/{T1}",
            json={
                "expected_version": 1,
                "citations": [
                    {"action": "add", "source": source.model_dump(mode="json")}
                ],
            },
        )
        assert attached.status_code == 200, attached.text
        citation = attached.json()["citations"][0]
        edited = client.patch(
            base + f"/tasks/{T1}",
            json={"expected_version": 2, "description": "後續人工語意修改"},
        )
        assert edited.status_code == 200, edited.text
        removed = client.patch(
            base + "/citations",
            json={
                "expected_version": 3,
                "target_kind": "task",
                "target_id": str(T1),
                "changes": [{"action": "remove", "citation_id": citation["id"]}],
            },
        )
        assert removed.status_code == 200, removed.text
        assert client.get(base + f"/citations/{citation['id']}").status_code == 404

        def forbidden_current_read(**kwargs: object) -> None:
            raise AssertionError("歷史來源不得重讀目前 JD 內容")

        monkeypatch.setattr(queries, "get_job_description", forbidden_current_read)
        path = base + f"/history/2/citations/{citation['id']}"
        historical = client.get(path)
        assert historical.status_code == 200, historical.text
        assert historical.json()["citation"] == citation
        assert historical.json()["source"]["text"] == "合成來源原話"
        assert historical.json()["needs_recheck"] is False
        later = client.get(base + f"/history/3/citations/{citation['id']}")
        assert later.status_code == 200, later.text
        assert later.json()["citation"]["jd_changed"] is True
        assert later.json()["needs_recheck"] is True

        failures = (
            (path.replace(str(jd_workspace_id), str(uuid4())), "jd_not_found"),
            (path.replace(str(JD), str(uuid4())), "jd_not_found"),
            (path.replace("/history/2/", "/history/999/"), "jd_history_not_found"),
            (path.replace(citation["id"], str(uuid4())), "citation_not_found"),
            (path.replace("/history/2/", "/history/4/"), "citation_not_found"),
        )
        for missing_path, code in failures:
            missing = client.get(missing_path)
            assert missing.status_code == 404, missing.text
            assert missing.json()["detail"]["code"] == code

        withdraw_turn(
            workspace_id=jd_workspace_id,
            turn_id=turn_id,
            uow_factory=partial(
                SqlAlchemyInterviewUnitOfWork, create_session_factory(pg_engine)
            ),
        )
        unavailable = client.get(path)
        assert unavailable.status_code == 200, unavailable.text
        assert unavailable.json()["citation"] == citation
        assert unavailable.json()["source"]["availability"] == "unavailable"
        assert unavailable.json()["source"]["text"] is None
    assert read_current(pg_engine, workspace_id=jd_workspace_id).version == 4


def test_historical_memory_citation_uses_fixed_item_and_fixed_situation_chain(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    seed_root(pg_engine, jd_workspace_id)
    turn, interview = source_message(pg_engine, jd_workspace_id)
    turns = CompletedTurns(frozenset((turn,)))
    service = MemoryService(
        partial(SqlAlchemyMemoryUnitOfWork, create_session_factory(pg_engine)),
        completed_turns=turns,
    )
    analysis = uuid4()

    def context(version: int) -> MemoryWriteContext:
        return MemoryWriteContext(
            workspace_id=jd_workspace_id, expected_version=version, analysis_id=analysis
        )

    service.start(context(0), through_message_id=interview.message_id)
    situation = service.create_situation(
        context(1),
        content=MemoryContent(
            title="舊情境", description="情境說明", body="原情境正文"
        ),
        interview_message_ids=(interview.message_id,),
    )
    assert situation.item_id is not None
    service.handoff(context(2))
    understanding = service.create_understanding(
        context(3),
        content=MemoryContent(
            title="固定理解", description="理解說明", body="原理解正文"
        ),
        situation_ids=(situation.item_id,),
    )
    assert understanding.item_id is not None
    service.publish(context(4))
    app, _ = http_app(pg_engine)
    base = f"/workspaces/{jd_workspace_id}/job-descriptions/{JD}"
    with TestClient(app) as client:
        attached = client.patch(
            base + "/citations",
            json={
                "expected_version": 1,
                "target_kind": "task",
                "target_id": str(T1),
                "changes": [
                    {
                        "action": "add",
                        "source": {
                            "kind": "memory",
                            "workspace_id": str(jd_workspace_id),
                            "published_version": 5,
                            "item_id": str(understanding.item_id),
                        },
                    }
                ],
            },
        )
        assert attached.status_code == 200, attached.text
        citation = attached.json()["citations"][0]
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
        turn2, interview2 = source_message(pg_engine, jd_workspace_id)
        turns.ids |= {turn2}
        analysis = uuid4()
        service.start(context(5), through_message_id=interview2.message_id)
        service.revise_situation(
            context(6),
            item_id=situation.item_id,
            content=MemoryContent(
                title="改名情境", description="新說明", body="新情境正文"
            ),
            interview_message_ids=(interview2.message_id,),
        )
        service.handoff(context(7))
        service.revise_understanding(
            context(8),
            item_id=understanding.item_id,
            content=MemoryContent(
                title="改名理解", description="新說明", body="新理解正文"
            ),
            situation_ids=(situation.item_id,),
        )
        service.publish(context(9))
        path = base + f"/history/2/citations/{citation['id']}"
        original = client.get(path)
        assert original.status_code == 200, original.text
        assert original.json()["citation"] == citation
        assert original.json()["source"]["title"] == "固定理解"
        assert original.json()["source"]["text"] == "原理解正文"
        assert original.json()["comparison"] is None
        assert original.json()["source_changed"] is None
        compared = client.get(path, params={"published_version": 10})
        assert compared.status_code == 200, compared.text
        comparison = compared.json()["comparison"]
        assert comparison["before"]["item"]["content"]["title"] == "固定理解"
        assert comparison["before"]["situations"][0]["content"]["body"] == "原情境正文"
        assert comparison["before"]["situations"][0]["interview_message_ids"] == [
            str(interview.message_id)
        ]
        assert comparison["after"]["item"]["content"]["title"] == "改名理解"
        assert comparison["after"]["situations"][0]["content"]["body"] == "新情境正文"
        assert compared.json()["source_changed"] is True

        turn3, interview3 = source_message(pg_engine, jd_workspace_id)
        turns.ids |= {turn3}
        analysis = uuid4()
        service.start(context(10), through_message_id=interview3.message_id)
        service.handoff(context(11))
        service.delete_understanding(context(12), item_id=understanding.item_id)
        replacement = service.create_understanding(
            context(13),
            content=MemoryContent(
                title="固定理解", description="同名新項", body="不可補位正文"
            ),
            situation_ids=(situation.item_id,),
        )
        assert replacement.item_id != understanding.item_id
        service.publish(context(14))
        deleted = client.get(path, params={"published_version": 15})
        assert deleted.status_code == 200, deleted.text
        assert deleted.json()["comparison"]["after"] is None
        assert deleted.json()["source"]["text"] == "原理解正文"
        assert deleted.json()["source_changed"] is True
        assert (
            client.get(path, params={"published_version": 10}).json() == compared.json()
        )
        assert client.get(path).json() == original.json()

        with pg_engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE job_description_snapshots SET content = "
                    "jsonb_set(content, '{citations,0,source,item_id}', "
                    "to_jsonb(CAST(:missing AS text))) "
                    "WHERE job_description_id=:jd AND version=2"
                ),
                {"missing": str(uuid4()), "jd": JD},
            )
        broken = client.get(path)
        assert broken.status_code == 500, broken.text
        assert broken.json()["detail"]["code"] == "jd_citation_source_data_error"
        assert "source" not in broken.json()
    assert read_current(pg_engine, workspace_id=jd_workspace_id).version == 3
