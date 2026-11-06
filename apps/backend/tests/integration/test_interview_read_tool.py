"""公開 read_interview 對真 PG：跨範圍、正式順序、撤回與持久定位。"""

import asyncio
import json
from dataclasses import dataclass
from functools import partial
from typing import Any
from uuid import UUID, uuid4

import pytest
from langgraph.prebuilt import ToolRuntime
from sqlalchemy import Engine

from caliburn.bundles.interview.read_tool import create_read_interview_tool
from caliburn.bundles.interview.references import message_refs
from caliburn.bundles.interview.services import INTERVIEW_QUERIES, MODEL_REFERENCES
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.plugins.services import PluginServices
from caliburn.modules.interview.application.recording import record_turn_input
from caliburn.modules.interview.application.withdrawal import withdraw_turn
from caliburn.modules.interview.infrastructure.persistence.queries import (
    SqlAlchemyInterviewQueries,
)
from caliburn.modules.interview.infrastructure.persistence.unit_of_work import (
    SqlAlchemyInterviewUnitOfWork,
)
from caliburn.modules.model_references import ReferenceTarget
from caliburn.modules.model_references.persistence import SqlAlchemyModelReferences
from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.infrastructure.persistence.unit_of_work import (
    SqlAlchemyWorkspaceUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory


@dataclass(frozen=True)
class Sources:
    workspace_id: UUID
    ids: tuple[UUID, ...]
    turns: tuple[UUID, ...]
    refs: tuple[str, ...]


@pytest.fixture
def sources(pg_engine: Engine, jd_workspace_id: UUID) -> Sources:
    sessions = create_session_factory(pg_engine)
    factory = partial(SqlAlchemyInterviewUnitOfWork, sessions)
    turns = tuple(uuid4() for _ in range(3))
    ids = tuple(
        record_turn_input(
            workspace_id=jd_workspace_id, turn_id=turn, text=text, uow_factory=factory
        ).message_id
        for turn, text in zip(
            turns, ("早期原話", "中間原話", "末項 message_1\n"), strict=True
        )
    )
    mapper = SqlAlchemyModelReferences(sessions)
    # 刻意逆正式順序配碼，證明配置號不參與 range/結果排序。
    by_id = {}
    for message_id in reversed(ids):
        by_id.update(
            message_refs(
                workspace_id=jd_workspace_id,
                message_ids=(message_id,),
                references=mapper,
            )
        )
    return Sources(jd_workspace_id, ids, turns, tuple(by_id[value] for value in ids))


def invoke(
    pg_engine: Engine, workspace_id: UUID, query: dict[str, object]
) -> dict[str, Any]:
    # 每次重建 mapper/queries，無前一次記憶體別名或 window 可用。
    runtime = ToolRuntime(
        state={"workspace_id": workspace_id},
        context=AgentContext(
            PluginServices(
                {
                    INTERVIEW_QUERIES: SqlAlchemyInterviewQueries(pg_engine),
                    MODEL_REFERENCES: SqlAlchemyModelReferences(
                        create_session_factory(pg_engine)
                    ),
                }
            )
        ),
        config={},
        stream_writer=lambda value: None,
        tool_call_id="read",
        store=None,
    )
    output = asyncio.run(
        create_read_interview_tool().ainvoke({"query": query, "runtime": runtime}),
        loop_factory=asyncio.SelectorEventLoop,
    )
    assert isinstance(output, str)
    decoded = json.loads(output)
    assert isinstance(decoded, dict)
    return decoded


def test_persistent_refs_select_in_formal_order_and_preserve_original_text(
    pg_engine: Engine, sources: Sources
) -> None:
    first, middle, last = sources.refs
    result = invoke(
        pg_engine,
        sources.workspace_id,
        {"kind": "messages", "refs": [last, first, first]},
    )
    assert [message["ref"] for message in result["messages"]] == [first, last]
    result = invoke(
        pg_engine,
        sources.workspace_id,
        {"kind": "range", "start_ref": first, "end_ref": last},
    )
    assert [message["ref"] for message in result["messages"]] == [first, middle, last]
    assert result["messages"][-1]["text"] == "末項 message_1\n"


def test_cancelled_middle_is_excluded_but_explicit_selection_or_endpoint_rejected(
    pg_engine: Engine, sources: Sources
) -> None:
    first, middle, last = sources.refs
    withdraw_turn(
        workspace_id=sources.workspace_id,
        turn_id=sources.turns[1],
        uow_factory=partial(
            SqlAlchemyInterviewUnitOfWork, create_session_factory(pg_engine)
        ),
    )
    result = invoke(
        pg_engine,
        sources.workspace_id,
        {"kind": "range", "start_ref": first, "end_ref": last},
    )
    assert [message["ref"] for message in result["messages"]] == [first, last]
    queries: tuple[dict[str, object], ...] = (
        {"kind": "messages", "refs": [first, middle]},
        {"kind": "range", "start_ref": middle, "end_ref": last},
    )
    for query in queries:
        rejected = invoke(pg_engine, sources.workspace_id, query)
        assert rejected["code"] == "source_not_available"
        assert "messages" not in rejected
    mapper = SqlAlchemyModelReferences(create_session_factory(pg_engine))
    assert (
        mapper.resolve_refs(sources.workspace_id, (middle,))[middle].resource_id
        == sources.ids[1]
    )


def test_unknown_and_cross_workspace_refs_cannot_disclose_sources(
    pg_engine: Engine, sources: Sources
) -> None:
    sessions = create_session_factory(pg_engine)
    other = (
        WorkspaceService(partial(SqlAlchemyWorkspaceUnitOfWork, sessions))
        .create(interviewee_name="隔離")
        .workspace_id
    )
    for workspace_id, ref in (
        (other, sources.refs[0]),
        (sources.workspace_id, "message_9223372036854775807"),
    ):
        result = invoke(pg_engine, workspace_id, {"kind": "messages", "refs": [ref]})
        assert result["code"] == "source_not_available"
        assert "query.refs[0]" in result["message"]
        assert str(sources.ids[0]) not in json.dumps(result)


def test_wrong_resource_kind_and_uuid_are_not_message_shortcuts(
    pg_engine: Engine, sources: Sources
) -> None:
    mapper = SqlAlchemyModelReferences(create_session_factory(pg_engine))
    target = ReferenceTarget("task", uuid4())
    task_ref = mapper.get_or_create_refs(sources.workspace_id, (target,))[target]
    for ref in (task_ref, str(sources.ids[0]), "message_0", "message_01"):
        result = invoke(
            pg_engine, sources.workspace_id, {"kind": "messages", "refs": [ref]}
        )
        assert result["code"] == "invalid_arguments"
