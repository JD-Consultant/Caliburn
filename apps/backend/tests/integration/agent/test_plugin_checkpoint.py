"""公開 Bundle 接點的合成能力，經真 PostgreSQL 重新啟動後接續。"""

import asyncio
from typing import Any
from uuid import UUID

import httpx2
import pytest
from langchain_core.runnables import RunnableConfig
from langgraph.types import StateSnapshot

from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from tests.integration.agent.plugin_fixture import (
    INTERVIEW_SOURCE,
    MEMORY_SOURCE,
    SUMMARY_TRACE,
    InterviewSource,
    MemorySource,
)
from tests.integration.agent.stream_support import consume
from tests.unit.modules.agent.offline_openai import (
    MODEL_REQUEST,
    EventStream,
    call,
    message,
    offline_client,
    reasoning,
    request_body,
    response_events,
    response_payload,
    sse_response,
)

PLUGIN_MODULE = "tests.integration.agent.plugin_fixture"
WORKSPACE = UUID(int=1)


def test_same_thread_new_turn_selects_latest_memory(
    checkpoint_conninfo: str,
) -> None:
    """每輪只選版一次；第二輪使用最新資料及新 input。"""
    sent = []
    source = MemorySource("v1")

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        output = (
            [call("read_memory", arguments='{"item":"k1"}')]
            if len(sent) in (1, 3)
            else None
        )
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        async with (
            open_postgres_checkpointer(checkpoint_conninfo, initialize=True) as saver,
            offline_client(httpx2.MockTransport(respond)) as client,
            open_agent(
                agent_id="new-turn",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(PLUGIN_MODULE)],
                external_services=(MEMORY_SOURCE.bind(source),),
                checkpointer=saver,
            ) as agent,
        ):
            for version in ("v1", "v2"):
                source.current_version = version
                turn_id = UUID(int=101 if version == "v1" else 102)
                await consume(
                    agent.astream(
                        turn_id=turn_id, workspace_id=WORKSPACE, input=version
                    )
                )
                saved = await agent.aget_state(workspace_id=WORKSPACE)
                assert saved.values["turn_input"] == version
                assert saved.values["memory_pin"]["version"] == version
                assert saved.values["model_step"] == 2
                assert saved.values["workspace_id"] == WORKSPACE
            assert source.selections == ["v1", "v2"]

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert [body["input"][0]["content"] for body in sent] == [
        "Memory v1: k1=old-object",
        "Memory v1: k1=old-object",
        "Memory v2: k1=different-object",
        "Memory v2: k1=different-object",
    ]
    assert sent[2]["input"] == [
        {"role": "developer", "content": "Memory v2: k1=different-object"},
        {"role": "user", "content": "v2"},
    ]


def test_resumed_memory_keeps_saved_version_and_short_ids_at_next_model_step(
    checkpoint_conninfo: str,
) -> None:
    """冷恢復不重新選 latest，保存的插件欄位仍可供工具使用。"""
    sent = []
    first_source = MemorySource("v1")
    resumed_source = MemorySource("v2")

    def first_response(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(
            EventStream(
                response_events(
                    response_payload([call("read_memory", arguments='{"item":"k1"}')])
                )
            )
        )

    def final_response(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with (
            open_postgres_checkpointer(checkpoint_conninfo, initialize=True) as saver,
            offline_client(httpx2.MockTransport(first_response)) as client,
            open_agent(
                agent_id="memory-pinned",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(PLUGIN_MODULE, {"fail_tool": True})],
                external_services=(MEMORY_SOURCE.bind(first_source),),
                checkpointer=saver,
            ) as agent,
        ):
            with pytest.raises(RuntimeError, match="synthetic tool outage"):
                await consume(
                    agent.astream(
                        turn_id=UUID(int=101), workspace_id=WORKSPACE, input=[]
                    )
                )

        # 新 client、source、Bundle、runtime 及 PG pool；沒有重用先前閉包。
        async with (
            open_postgres_checkpointer(checkpoint_conninfo) as saver,
            offline_client(httpx2.MockTransport(final_response)) as client,
            open_agent(
                agent_id="memory-pinned",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(PLUGIN_MODULE)],
                external_services=(MEMORY_SOURCE.bind(resumed_source),),
                checkpointer=saver,
            ) as agent,
        ):
            saved = await agent.aget_state(workspace_id=WORKSPACE)
            assert saved.values["memory_pin"] == {
                "version": "v1",
                "ids": {"k1": "old-object"},
            }
            await consume(agent.aresume(turn_id=UUID(int=101), workspace_id=WORKSPACE))
            saved = await agent.aget_state(workspace_id=WORKSPACE)
            assert saved.values["model_response"].output_text == "Synthetic reply"
            assert saved.values["memory_pin"]["version"] == "v1"
            assert saved.values["turn_input"] == []
            assert resumed_source.selections == []

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert first_source.selections == ["v1"]
    assert len(sent) == 2
    assert sent[1]["input"][-1]["output"] == "v1:old-object"
    assert [body["input"][0]["content"] for body in sent] == [
        "Memory v1: k1=old-object",
        "Memory v1: k1=old-object",
    ]


def test_role_threads_resume_their_own_interview_boundary_and_capabilities(
    checkpoint_conninfo: str,
) -> None:
    """同 Workspace 的兩個 Agent 不共用角色資料或工作歷史。"""
    sent: dict[str, list[dict[str, Any]]] = {role: [] for role in ("B1", "B2")}
    source = InterviewSource(cutoff=1)

    def response(role: str, *, final: bool) -> httpx2.MockTransport:
        def handle(request: httpx2.Request) -> httpx2.Response:
            sent[role].append(request_body(request))
            output = (
                None
                if final
                else [
                    call(
                        "read_source",
                        call_id="within",
                        arguments='{"kind":"interview","index":1}',
                    ),
                    call(
                        "read_source",
                        call_id="outside",
                        arguments='{"kind":"interview","index":2}',
                    ),
                    call(
                        "read_source",
                        call_id="understanding",
                        arguments='{"kind":"understanding","index":0}',
                    ),
                ]
            )
            return sse_response(EventStream(response_events(response_payload(output))))

        return httpx2.MockTransport(handle)

    async def run() -> None:
        async with open_postgres_checkpointer(
            checkpoint_conninfo, initialize=True
        ) as saver:
            for role in sent:
                async with (
                    offline_client(response(role, final=False)) as client,
                    open_agent(
                        agent_id=role,
                        resume_version="v1",
                        client=client,
                        model_settings=MODEL_REQUEST,
                        bundles=[
                            BundleConfig(
                                PLUGIN_MODULE, {"role": role, "fail_tool": True}
                            )
                        ],
                        external_services=(INTERVIEW_SOURCE.bind(source),),
                        checkpointer=saver,
                    ) as agent,
                ):
                    with pytest.raises(RuntimeError, match="synthetic tool outage"):
                        await consume(
                            agent.astream(
                                turn_id=UUID(int=101), workspace_id=WORKSPACE, input=[]
                            )
                        )
        async with open_postgres_checkpointer(checkpoint_conninfo) as saver:
            for role in sent:
                async with (
                    offline_client(response(role, final=True)) as client,
                    open_agent(
                        agent_id=role,
                        resume_version="v1",
                        client=client,
                        model_settings=MODEL_REQUEST,
                        bundles=[BundleConfig(PLUGIN_MODULE, {"role": role})],
                        external_services=(
                            INTERVIEW_SOURCE.bind(InterviewSource(cutoff=2)),
                        ),
                        checkpointer=saver,
                    ) as agent,
                ):
                    await consume(
                        agent.aresume(turn_id=UUID(int=101), workspace_id=WORKSPACE)
                    )
                    state = await agent.aget_state(workspace_id=WORKSPACE)
                    assert state.values["role_scope"] == {"role": role, "cutoff": 1}

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    for role in sent:
        assert len(sent[role]) == 2
        assert [body["input"][0]["content"] for body in sent[role]] == [
            f"Role {role}; interview through 1",
        ] * 2
        assert [item["output"] for item in sent[role][1]["input"][-3:]] == [
            "first statement",
            "denied:outside_batch",
            "denied:role" if role == "B1" else "synthetic understanding",
        ]
        assert "later statement" not in str(sent[role])
    assert "synthetic understanding" not in str(sent["B1"])


def test_subgraph_resumes_private_summary_and_persists_explicit_shared_channel(
    checkpoint_conninfo: str,
) -> None:
    """子圖故障後沿內部保存點恢復；下一次呼叫不沿用私有 scratch。"""
    first_trace: list[str] = []
    resumed_trace: list[str] = []
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        output = [reasoning(), message("commentary")] if len(sent) == 1 else None
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        async with (
            open_postgres_checkpointer(checkpoint_conninfo, initialize=True) as saver,
            offline_client(
                httpx2.MockTransport(lambda _: pytest.fail("model before summary"))
            ) as client,
            open_agent(
                agent_id="summary",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(PLUGIN_MODULE, {"summary": True, "fail": True})],
                external_services=(SUMMARY_TRACE.bind(first_trace),),
                checkpointer=saver,
            ) as agent,
        ):
            with pytest.raises(RuntimeError, match="synthetic summary outage"):
                await consume(
                    agent.astream(
                        turn_id=UUID(int=101), workspace_id=WORKSPACE, input="old"
                    )
                )
            pending = await agent.aget_state(workspace_id=WORKSPACE, subgraphs=True)
            assert "scratch" not in pending.values
            child = pending.tasks[0].state
            assert isinstance(child, StateSnapshot)
            assert child.values["scratch"] == "Summary 1 for workspace 1"
        async with (
            open_postgres_checkpointer(checkpoint_conninfo) as saver,
            offline_client(httpx2.MockTransport(respond)) as client,
            open_agent(
                agent_id="summary",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(PLUGIN_MODULE, {"summary": True})],
                external_services=(SUMMARY_TRACE.bind(resumed_trace),),
                checkpointer=saver,
            ) as agent,
        ):
            await consume(agent.aresume(turn_id=UUID(int=101), workspace_id=WORKSPACE))
            saved = await agent.aget_state(workspace_id=WORKSPACE)
            assert saved.values["summary_visits"] == 2
            assert "scratch" not in saved.values
            thread_id = saved.config["configurable"]["thread_id"]
            thread_config: RunnableConfig = {"configurable": {"thread_id": thread_id}}
            checkpoints = [item async for item in saver.alist(thread_config)]
            assert any(
                item.config["configurable"]["checkpoint_ns"] for item in checkpoints
            )
            await saver.adelete_thread(thread_id)
            assert [item async for item in saver.alist(thread_config)] == []

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert first_trace == ["prepare:1", "adopt:1"]
    assert resumed_trace == ["adopt:1", "prepare:2", "adopt:2"]
    assert [body["input"][0]["content"] for body in sent] == [
        "Summary 1 for workspace 1",
        "Summary 2 for workspace 1",
    ]
    assert sent[1]["input"][1]["encrypted_content"] == "synthetic-opaque-content"


def test_new_thread_selects_latest_and_memory_bundle_can_be_disabled(
    checkpoint_conninfo: str,
) -> None:
    """啟用／停用仍走同一 Core；新 thread 沒有繼承其他工作的 pin。"""
    sent = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with (
            open_postgres_checkpointer(checkpoint_conninfo, initialize=True) as saver,
            offline_client(httpx2.MockTransport(respond)) as client,
        ):
            for enabled in (True, False):
                async with open_agent(
                    agent_id=f"enabled-{enabled}",
                    resume_version="v1",
                    client=client,
                    model_settings=MODEL_REQUEST,
                    bundles=[BundleConfig(PLUGIN_MODULE)] if enabled else [],
                    external_services=(MEMORY_SOURCE.bind(MemorySource("v2")),)
                    if enabled
                    else (),
                    checkpointer=saver,
                ) as agent:
                    await consume(
                        agent.astream(
                            turn_id=UUID(int=101), workspace_id=WORKSPACE, input=[]
                        )
                    )
                    saved = await agent.aget_state(workspace_id=WORKSPACE)
                    assert ("memory_pin" in saved.values) is enabled

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert sent[0]["input"][0]["content"] == "Memory v2: k1=different-object"
    assert sent[0]["tools"][0]["name"] == "read_memory"
    assert sent[1]["input"] == []
    assert not sent[1].get("tools")
