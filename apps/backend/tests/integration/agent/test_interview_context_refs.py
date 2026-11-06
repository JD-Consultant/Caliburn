"""正式 Bundle 經真 PG 交付來源 ref，並沿原輸入身分恢復映射故障。"""

import asyncio
import json
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from functools import partial
from typing import Any
from uuid import UUID, uuid4

import httpx2
import pytest
from langgraph.runtime import Runtime
from langgraph.types import StateSnapshot
from sqlalchemy import Engine, create_engine
from sqlalchemy.exc import DBAPIError

from caliburn.bundles.context.contracts import WindowContribution
from caliburn.bundles.context.history import previous_completed_window
from caliburn.bundles.context.services import PREVIOUS_WINDOW, WINDOW_CONTRIBUTIONS
from caliburn.bundles.interview.services import (
    INTERVIEW_QUERIES,
    INTERVIEW_UOW_FACTORY,
    MODEL_REFERENCES,
)
from caliburn.modules.agent.agent import Agent
from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.state import AgentState
from caliburn.modules.interview.application.recording import record_opening
from caliburn.modules.interview.infrastructure.persistence.queries import (
    SqlAlchemyInterviewQueries,
)
from caliburn.modules.interview.infrastructure.persistence.unit_of_work import (
    SqlAlchemyInterviewUnitOfWork,
)
from caliburn.modules.model_references import ModelReferences, ReferenceTarget
from caliburn.modules.model_references.persistence import SqlAlchemyModelReferences
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.agent.http_support import api_client
from tests.integration.agent.interview_context_support import (
    ScriptedInterviewModel,
    context_messages,
)
from tests.integration.agent.stream_support import consume
from tests.unit.modules.agent.offline_openai import (
    MODEL_REQUEST,
    EventStream,
    call,
    offline_client,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


@asynccontextmanager
async def reference_agent(
    engine: Engine,
    checkpoint_conninfo: str,
    transport: httpx2.MockTransport,
    *,
    initialize: bool,
    references: ModelReferences | None = None,
    window: bool = False,
    rebuild_each_turn: bool = False,
) -> AsyncIterator[Agent]:
    """單一正式組裝 seam；僅映射連線可切換成真 PG 故障配置。"""
    sessions = create_session_factory(engine)
    bundles = [
        BundleConfig(
            "caliburn.bundles.interview",
            plugins=("interview", "interview_source_prompt", "interview_read")
            if window
            else None,
        )
    ]
    if window:
        bundles.extend(
            (
                BundleConfig("caliburn.bundles.interview.window", {"preload": False}),
                BundleConfig(
                    "caliburn.bundles.context",
                    plugins=("window",),
                ),
            )
        )

    async def previous(workspace_id: UUID, turn_id: UUID) -> StateSnapshot | None:
        return await previous_completed_window(
            agent, workspace_id=workspace_id, turn_id=turn_id
        )

    async def no_material(
        state: AgentState,
        *,
        previous: Mapping[str, Any] | None,
        rebuilding: bool,
        runtime: Runtime[AgentContext],
    ) -> Mapping[str, object]:
        return {}

    async with (
        open_postgres_checkpointer(checkpoint_conninfo, initialize=initialize) as saver,
        offline_client(transport) as client,
        open_agent(
            agent_id="interview-references",
            resume_version="references-v1",
            client=client,
            model_settings=MODEL_REQUEST,
            bundles=bundles,
            external_services=(
                PREVIOUS_WINDOW.bind(previous),
                WINDOW_CONTRIBUTIONS.bind(
                    (
                        WindowContribution(
                            no_material,
                            should_renew=lambda state, previous: rebuild_each_turn,
                        ),
                    )
                    if window
                    else ()
                ),
                INTERVIEW_UOW_FACTORY.bind(
                    partial(SqlAlchemyInterviewUnitOfWork, sessions)
                ),
                INTERVIEW_QUERIES.bind(SqlAlchemyInterviewQueries(engine)),
                MODEL_REFERENCES.bind(
                    references
                    if references is not None
                    else SqlAlchemyModelReferences(sessions)
                ),
            ),
            checkpointer=saver,
        ) as agent,
    ):
        yield agent


def input_reference(request: dict[str, Any]) -> dict[str, str]:
    for item in request["input"]:
        content = item.get("content")
        if item.get("role") != "user" or not isinstance(content, str):
            continue
        try:
            material = json.loads(content)
        except json.JSONDecodeError:
            continue
        if (
            isinstance(material, dict)
            and material.get("data_kind") == "employee_input_reference"
        ):
            return material
    raise AssertionError("SDK 請求缺少本輪已保存輸入的 ref")


def test_current_input_ref_is_readable_in_the_same_turn_and_stable_after_reopening(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    original = "  員工原文保留 message_777\n第二行 "
    requests: list[dict[str, Any]] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        captured = request_body(request)
        requests.append(captured)
        output = None
        if len(requests) == 1:
            reference = input_reference(captured)
            assert set(reference) == {"data_kind", "ref"}
            assert reference["ref"].startswith("message_")
            assert captured["input"][0] == {"role": "user", "content": original}
            assert (
                sum(
                    item == {"role": "user", "content": original}
                    for item in captured["input"]
                )
                == 1
            )
            output = [
                call(
                    "read_interview",
                    "read-current-input",
                    json.dumps(
                        {"query": {"kind": "messages", "refs": [reference["ref"]]}}
                    ),
                )
            ]
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        for index, text in enumerate((original, "第二輪原文")):
            async with reference_agent(
                pg_engine,
                checkpoint_conninfo,
                httpx2.MockTransport(respond),
                initialize=index == 0,
            ) as agent:
                await consume(
                    agent.astream(
                        workspace_id=jd_workspace_id, turn_id=uuid4(), input=text
                    )
                )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert len(requests) == 3
    current_ref = input_reference(requests[0])["ref"]
    read_result = next(
        json.loads(item["output"])
        for item in requests[1]["input"]
        if item.get("type") == "function_call_output"
    )
    assert read_result["messages"] == [
        {
            "ref": current_ref,
            "speaker": "employee",
            "kind": "text",
            "text": original,
            "reply_to": None,
        }
    ]
    history = context_messages(requests[2])
    assert history[0]["ref"] == current_ref
    assert history[0]["text"] == original
    assert all("position" not in item for item in history)
    source = SqlAlchemyInterviewQueries(pg_engine).list_messages(
        workspace_id=jd_workspace_id
    )[0]
    references = SqlAlchemyModelReferences(create_session_factory(pg_engine))
    assert references.resolve_refs(jd_workspace_id, [current_ref]) == {
        current_ref: ReferenceTarget("message", source.message_id)
    }


def test_mapping_failure_after_input_commit_resumes_with_the_original_message_uuid(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    turn_id = uuid4()
    original = " 映射故障前已保存的原文\n "
    model = ScriptedInterviewModel([None])
    queries = SqlAlchemyInterviewQueries(pg_engine)
    broken_url = pg_engine.url.update_query_dict(
        {"options": f"-csearch_path=missing_reference_{uuid4().hex}"}
    )
    broken_engine = create_engine(broken_url, hide_parameters=True)
    broken_references = SqlAlchemyModelReferences(create_session_factory(broken_engine))
    saved_id: UUID | None = None

    async def run() -> None:
        nonlocal saved_id
        async with reference_agent(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(model),
            initialize=True,
            references=broken_references,
        ) as agent:
            with pytest.raises(DBAPIError):
                await consume(
                    agent.astream(
                        workspace_id=jd_workspace_id, turn_id=turn_id, input=original
                    )
                )
            (saved,) = queries.list_messages(workspace_id=jd_workspace_id)
            saved_id = saved.message_id
            assert saved.text == original
            assert model.requests == []
        async with reference_agent(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(model),
            initialize=False,
        ) as agent:
            await consume(agent.aresume(workspace_id=jd_workspace_id, turn_id=turn_id))

    try:
        asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    finally:
        broken_engine.dispose()
    transcript = queries.list_messages(workspace_id=jd_workspace_id)
    assert [
        (item.message_id, item.text)
        for item in transcript
        if item.speaker == "employee"
    ] == [(saved_id, original)]
    assert saved_id is not None
    reference = input_reference(model.requests[0])["ref"]
    references = SqlAlchemyModelReferences(create_session_factory(pg_engine))
    assert references.resolve_refs(jd_workspace_id, [reference]) == {
        reference: ReferenceTarget("message", saved_id)
    }


@pytest.mark.parametrize("rebuild_each_turn", [False, True])
def test_explicit_window_input_callback_survives_rebuild_and_continuation(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    jd_workspace_id: UUID,
    rebuild_each_turn: bool,
) -> None:
    model = ScriptedInterviewModel([None, None])
    inputs = ("  先前原文 message_777\n ", "目前原文")

    async def run() -> None:
        async with reference_agent(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(model),
            initialize=True,
            window=True,
            rebuild_each_turn=rebuild_each_turn,
        ) as agent:
            for original in inputs:
                await consume(
                    agent.astream(
                        workspace_id=jd_workspace_id, turn_id=uuid4(), input=original
                    )
                )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert len(model.requests) == 2
    references = SqlAlchemyModelReferences(create_session_factory(pg_engine))
    employees = [
        message
        for message in SqlAlchemyInterviewQueries(pg_engine).list_messages(
            workspace_id=jd_workspace_id
        )
        if message.speaker == "employee"
    ]
    for index, request in enumerate(model.requests):
        metadata = []
        for item in request["input"]:
            content = item.get("content")
            if item.get("role") == "user" and isinstance(content, str):
                try:
                    material = json.loads(content)
                except json.JSONDecodeError:
                    continue
                if isinstance(material, dict):
                    metadata.append(material)
        current = [
            item
            for item in metadata
            if item.get("data_kind") == "employee_input_reference"
        ]
        navigation = [
            item for item in metadata if item.get("data_kind") == "interview_navigation"
        ]
        assert len(current) == (1 if rebuild_each_turn else index + 1)
        assert len(navigation) == len(current)
        current_ref = current[-1]["ref"]
        assert references.resolve_refs(jd_workspace_id, [current_ref]) == {
            current_ref: ReferenceTarget("message", employees[index].message_id)
        }
        assert navigation[-1]["last_ref"] == current_ref
        assert (
            sum(
                item == {"role": "user", "content": inputs[index]}
                for item in request["input"]
            )
            == 1
        )
        assert context_messages(request) == []
    if rebuild_each_turn:
        assert not any(
            item.get("content") == inputs[0] for item in model.requests[1]["input"]
        )
    else:
        assert (
            model.requests[1]["input"][: len(model.requests[0]["input"])]
            == model.requests[0]["input"]
        )


@pytest.mark.parametrize("preload", [False, True])
def test_host_window_preserves_current_input_ref_and_navigation_without_memory(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    jd_workspace_id: UUID,
    preload: bool,
) -> None:
    sessions = create_session_factory(pg_engine)
    opening = record_opening(
        workspace_id=jd_workspace_id,
        text="換窗前已保存的開場",
        uow_factory=partial(SqlAlchemyInterviewUnitOfWork, sessions),
    )
    model = ScriptedInterviewModel([None, None])
    inputs = ("  首輪原文 message_777\n ", "續輪原文")

    async def run() -> None:
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(model),
            bundles=(
                BundleConfig(
                    "caliburn.bundles.interview",
                    plugins=("interview", "interview_source_prompt", "interview_read"),
                ),
                BundleConfig("caliburn.bundles.interview.window", {"preload": preload}),
                BundleConfig(
                    "caliburn.bundles.context",
                    plugins=("window",),
                ),
            ),
        ) as client:
            for original in inputs:
                submitted = await client.post(
                    f"/workspaces/{jd_workspace_id}/agent/turns",
                    json={"turn_id": str(uuid4()), "input": original},
                )
                assert submitted.status_code == 202, submitted.text
                async with asyncio.timeout(10):
                    while True:
                        turn = (await client.get(submitted.headers["Location"])).json()
                        if turn["status"] != "running":
                            break
                        await asyncio.sleep(0.01)
                assert turn["status"] == "completed", turn

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert len(model.requests) == 2
    transcript = SqlAlchemyInterviewQueries(pg_engine).list_messages(
        workspace_id=jd_workspace_id
    )
    employees = [message for message in transcript if message.speaker == "employee"]
    references = SqlAlchemyModelReferences(sessions)
    for index, request in enumerate(model.requests):
        metadata = []
        for item in request["input"]:
            content = item.get("content")
            if item.get("role") == "user" and isinstance(content, str):
                try:
                    material = json.loads(content)
                except json.JSONDecodeError:
                    continue
                if isinstance(material, dict):
                    metadata.append(material)
        current = [
            item
            for item in metadata
            if item.get("data_kind") == "employee_input_reference"
        ]
        navigation = [
            item for item in metadata if item.get("data_kind") == "interview_navigation"
        ]
        assert len(current) == index + 1, "換窗或續接遺失本輪輸入 ref"
        assert len(navigation) == index + 1, "換窗或續接遺失本輪訪談導覽"
        current_ref = current[-1]["ref"]
        assert navigation[-1]["last_ref"] == current_ref
        assert references.resolve_refs(jd_workspace_id, [current_ref]) == {
            current_ref: ReferenceTarget("message", employees[index].message_id)
        }
        assert references.resolve_refs(
            jd_workspace_id, [navigation[-1]["first_ref"]]
        ) == {
            navigation[-1]["first_ref"]: ReferenceTarget("message", opening.message_id)
        }
        assert (
            sum(
                item == {"role": "user", "content": inputs[index]}
                for item in request["input"]
            )
            == 1
        )
        assert bool(context_messages(request)) is preload
