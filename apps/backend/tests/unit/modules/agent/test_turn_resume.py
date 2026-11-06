"""同一輪的故障續作與人工回答，保護原生待續工作。"""

import asyncio
from collections.abc import Mapping
from typing import TypedDict, cast
from uuid import UUID

import httpx2
import pytest
from langchain_core.tools import StructuredTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import Command, interrupt

from caliburn.modules.agent.agent import AgentExecutionError, has_pending_work
from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    openai_checkpoint_serializer,
)
from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    AgentPlugin,
    PluginStep,
)
from caliburn.modules.agent.state import AgentState
from tests.unit.modules.agent.offline_openai import (
    MODEL_REQUEST,
    EventStream,
    call,
    offline_client,
    response_events,
    response_payload,
    sse_response,
)

WORKSPACE = UUID(int=1)
TURN = UUID(int=11)


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    return AgentBundle(cast(tuple[AgentPlugin, ...], config["plugins"]))


class AnswerState(TypedDict):
    answer: str | None


@pytest.mark.parametrize("ask_again", [False, True])
def test_answered_interrupt_failure_resumes_after_reopen_without_repeating_work(
    ask_again: bool,
) -> None:
    answers: list[str] = []
    effects: list[str] = []
    attempts: list[tuple[UUID, int]] = []
    sent: list[httpx2.Request] = []
    fail_after_answer = True

    async def read_source(item: str) -> str:
        effects.append(item)
        return "saved source"

    async def ask(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> Mapping[str, object]:
        nonlocal fail_after_answer
        first = interrupt("First question")
        attempts.append((state["turn_id"], state["model_step"]))
        if fail_after_answer:
            fail_after_answer = False
            raise RuntimeError("synthetic failure after answer")
        second = interrupt("Second question") if ask_again else "unused"
        answers.extend((first, second))
        return {}

    plugin = AgentPlugin(
        "answer",
        tools=(
            StructuredTool.from_function(
                coroutine=read_source,
                name="read_source",
                description="Read the synthetic source.",
            ),
        ),
        on_turn_end=(PluginStep("ask", ask),),
    )
    replies = iter([response_payload([call("read_source")]), response_payload()])

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        return sse_response(EventStream(response_events(next(replies))))

    async def run() -> None:
        saver = InMemorySaver(serde=openai_checkpoint_serializer())
        async with offline_client(httpx2.MockTransport(respond)) as client:
            for first_open in (True, False):
                async with open_agent(
                    agent_id="answered-failure",
                    resume_version="v1",
                    client=client,
                    model_settings=MODEL_REQUEST,
                    bundles=[BundleConfig(__name__, {"plugins": (plugin,)})],
                    checkpointer=saver,
                ) as agent:
                    if first_open:
                        async for _ in agent.astream(
                            workspace_id=WORKSPACE, turn_id=TURN, input="original"
                        ):
                            pass
                        waiting = await agent.aget_state(workspace_id=WORKSPACE)
                        assert [item.value for item in waiting.interrupts] == [
                            "First question"
                        ]
                        with pytest.raises(RuntimeError, match="failure after answer"):
                            async for _ in agent.aresume(
                                workspace_id=WORKSPACE,
                                turn_id=TURN,
                                resume_command=Command(
                                    resume={waiting.interrupts[0].id: "first answer"}
                                ),
                            ):
                                pass
                        failed = await agent.aget_state(workspace_id=WORKSPACE)
                        assert failed.interrupts
                        assert any(task.error for task in failed.tasks)
                        continue

                    async for _ in agent.aresume(workspace_id=WORKSPACE, turn_id=TURN):
                        pass
                    if ask_again:
                        waiting = await agent.aget_state(workspace_id=WORKSPACE)
                        assert [item.value for item in waiting.interrupts] == [
                            "Second question"
                        ]
                        assert answers == []
                        with pytest.raises(AgentExecutionError, match="waiting"):
                            async for _ in agent.astream(
                                workspace_id=WORKSPACE,
                                turn_id=UUID(int=12),
                                input="skip",
                            ):
                                pass
                        async for _ in agent.aresume(
                            workspace_id=WORKSPACE, turn_id=TURN
                        ):
                            pass
                        still_waiting = await agent.aget_state(workspace_id=WORKSPACE)
                        assert still_waiting.interrupts == waiting.interrupts
                        assert still_waiting.values == waiting.values
                        assert answers == []
                        async for _ in agent.aresume(
                            workspace_id=WORKSPACE,
                            turn_id=TURN,
                            resume_command=Command(
                                resume={waiting.interrupts[0].id: "second answer"}
                            ),
                        ):
                            pass
                    done = await agent.aget_state(workspace_id=WORKSPACE)
                    assert not done.next and not done.interrupts
                    assert done.values["turn_id"] == TURN
                    assert done.values["turn_input"] == "original"
                    assert done.values["model_step"] == 2
                    assert answers == [
                        "first answer",
                        "second answer" if ask_again else "unused",
                    ]
                    assert effects == ["alpha"]
                    assert len(sent) == 2
                    assert all(item == (TURN, 2) for item in attempts)

    asyncio.run(run())


@pytest.mark.parametrize("answer", ["yes", {}, {"unknown": "yes"}])
def test_answer_requires_current_interrupt_id_before_any_persisted_change(
    answer: str | dict[str, str],
) -> None:
    async def ask(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> Mapping[str, object]:
        interrupt("Continue?")
        return {}

    plugin = AgentPlugin("answer", on_turn_start=(PluginStep("ask", ask),))

    async def run() -> None:
        async with (
            offline_client(
                httpx2.MockTransport(lambda _: pytest.fail("model before answer"))
            ) as client,
            open_agent(
                agent_id="answer-id",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(__name__, {"plugins": (plugin,)})],
                checkpointer=InMemorySaver(),
            ) as agent,
        ):
            async for _ in agent.astream(
                workspace_id=WORKSPACE, turn_id=TURN, input="original"
            ):
                pass
            before = await agent.aget_state(workspace_id=WORKSPACE)
            history = [
                item.config
                async for item in agent.aget_state_history(workspace_id=WORKSPACE)
            ]
            with pytest.raises(AgentExecutionError, match="interrupt.*ID"):
                async for _ in agent.aresume(
                    workspace_id=WORKSPACE,
                    turn_id=TURN,
                    resume_command=Command(resume=answer),
                ):
                    pass
            after = await agent.aget_state(workspace_id=WORKSPACE)
            assert after.config == before.config
            assert after.values == before.values
            assert after.interrupts == before.interrupts
            assert [
                item.config
                async for item in agent.aget_state_history(workspace_id=WORKSPACE)
            ] == history

    asyncio.run(run())


def test_interrupt_id_mapping_can_answer_one_of_multiple_pending_questions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    answers: dict[str, str] = {}

    async def ask_left(state: AgentState) -> Mapping[str, object]:
        answers["left"] = interrupt("Left question")
        return {}

    async def ask_right(state: AgentState) -> Mapping[str, object]:
        answers["right"] = interrupt("Right question")
        return {}

    graph = StateGraph(
        AgentState,
        context_schema=AgentContext,
        input_schema=AgentState,
        output_schema=AgentState,
    )
    graph.add_node("left", ask_left)
    graph.add_node("right", ask_right)
    for name in ("left", "right"):
        graph.add_edge(START, name)
        graph.add_edge(name, END)
    plugin = AgentPlugin(
        "questions", on_turn_start=(PluginStep("ask", graph.compile()),)
    )
    # 已編譯子圖由 Bundle 工廠提供，不當成啟動配置深複製。
    monkeypatch.setattr(f"{__name__}.create_bundle", lambda _: AgentBundle((plugin,)))

    async def run() -> None:
        async with (
            offline_client(
                httpx2.MockTransport(
                    lambda _: sse_response(
                        EventStream(response_events(response_payload()))
                    )
                )
            ) as client,
            open_agent(
                agent_id="partial-answer",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(__name__)],
                checkpointer=InMemorySaver(),
            ) as agent,
        ):
            async for _ in agent.astream(
                workspace_id=WORKSPACE, turn_id=TURN, input="original"
            ):
                pass
            before = await agent.aget_state(workspace_id=WORKSPACE)
            assert len(before.interrupts) == 2
            questions = {item.value: item.id for item in before.interrupts}
            async for _ in agent.aresume(
                workspace_id=WORKSPACE,
                turn_id=TURN,
                resume_command=Command(
                    resume={questions["Left question"]: "left answer"}
                ),
            ):
                pass
            waiting = await agent.aget_state(workspace_id=WORKSPACE)
            assert [item.value for item in waiting.interrupts] == ["Right question"]
            assert answers == {"left": "left answer"}
            async for _ in agent.aresume(
                workspace_id=WORKSPACE,
                turn_id=TURN,
                resume_command=Command(
                    resume={questions["Right question"]: "right answer"}
                ),
            ):
                pass
            done = await agent.aget_state(workspace_id=WORKSPACE)
            assert not done.next and not done.interrupts
            assert answers == {"left": "left answer", "right": "right answer"}

    asyncio.run(run())


@pytest.mark.parametrize("answer", ["yes", None])
def test_waiting_turn_requires_same_turn_answer_after_reopen(
    answer: str | None,
) -> None:
    async def ask(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> Mapping[str, object]:
        return {"answer": interrupt("Continue?")}

    plugins = (
        AgentPlugin(
            "answer", state_schema=AnswerState, on_turn_start=(PluginStep("ask", ask),)
        ),
    )
    sent: list[httpx2.Request] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        sent.append(request)
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        saver = InMemorySaver()
        async with offline_client(httpx2.MockTransport(respond)) as client:
            for first_open in (True, False):
                async with open_agent(
                    agent_id="waiting",
                    resume_version="v1",
                    client=client,
                    model_settings=MODEL_REQUEST,
                    bundles=[BundleConfig(__name__, {"plugins": plugins})],
                    checkpointer=saver,
                ) as agent:
                    if first_open:
                        parts = [
                            part
                            async for part in agent.astream(
                                workspace_id=WORKSPACE, turn_id=TURN, input="original"
                            )
                        ]
                        assert any(part.get("interrupts") for part in parts)
                    before = await agent.aget_state(workspace_id=WORKSPACE)
                    with pytest.raises(AgentExecutionError, match="waiting"):
                        await anext(
                            agent.astream(
                                workspace_id=WORKSPACE,
                                turn_id=UUID(int=12),
                                input="skip",
                            )
                        )
                    with pytest.raises(AgentExecutionError, match="answer"):
                        await anext(agent.aresume(workspace_id=WORKSPACE, turn_id=TURN))
                    with pytest.raises(AgentExecutionError, match="turn"):
                        await anext(
                            agent.aresume(
                                workspace_id=WORKSPACE,
                                turn_id=UUID(int=12),
                                resume_command=Command(
                                    resume={before.interrupts[0].id: "yes"}
                                ),
                            )
                        )
                    unchanged = await agent.aget_state(workspace_id=WORKSPACE)
                    assert unchanged.config == before.config
                    assert unchanged.values["turn_input"] == "original"
                    assert sent == []
                    if not first_open:
                        async for _ in agent.aresume(
                            workspace_id=WORKSPACE,
                            turn_id=TURN,
                            resume_command=Command(
                                resume={before.interrupts[0].id: answer}
                            ),
                        ):
                            pass
                        done = await agent.aget_state(workspace_id=WORKSPACE)
                        assert done.values["answer"] == answer
                        assert done.values["turn_id"] == TURN
                        assert done.values["turn_input"] == "original"
                        assert done.values["model_step"] == 1
                        assert not done.interrupts
                        assert len(sent) == 1

    asyncio.run(run())


def test_resume_from_input_checkpoint_filters_previous_turn_response() -> None:
    async def run() -> None:
        saver = InMemorySaver(serde=openai_checkpoint_serializer())
        async with offline_client(
            httpx2.MockTransport(
                lambda _: sse_response(EventStream(response_events(response_payload())))
            )
        ) as client:
            async with open_agent(
                agent_id="early",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[],
                checkpointer=saver,
            ) as agent:
                for turn, text in ((UUID(int=10), "old"), (TURN, "new")):
                    async for _ in agent.astream(
                        workspace_id=WORKSPACE, turn_id=turn, input=text
                    ):
                        pass
                history = [
                    saved
                    async for saved in agent.aget_state_history(workspace_id=WORKSPACE)
                ]
                earliest = next(
                    saved
                    for saved in history
                    if saved.metadata
                    and saved.metadata.get("source") == "input"
                    and saved.metadata.get("turn_id") == str(TURN)
                )
                raw = await saver.aget_tuple(earliest.config)
                assert raw is not None
            # 重建真正 input 保存邊界，不複製後續 START 的 pending writes。
            restored = InMemorySaver(serde=openai_checkpoint_serializer())
            await restored.aput(
                {
                    "configurable": {
                        "thread_id": f"early:{WORKSPACE}",
                        "checkpoint_ns": "",
                    }
                },
                raw.checkpoint,
                raw.metadata,
                raw.checkpoint["channel_versions"],
            )
            async with open_agent(
                agent_id="early",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[],
                checkpointer=restored,
            ) as reopened:
                before = await reopened.aget_state(workspace_id=WORKSPACE)
                assert before.values["turn_id"] == UUID(int=10)
                assert has_pending_work(before)
                parts = [
                    part
                    async for part in reopened.aresume(
                        workspace_id=WORKSPACE, turn_id=TURN
                    )
                ]
                values = [part["data"] for part in parts if part["type"] == "values"]
                assert values and all(value["turn_id"] == TURN for value in values)
                done = await reopened.aget_state(workspace_id=WORKSPACE)
                assert done.values["turn_input"] == "new"
                assert done.values["model_step"] == 1
                assert not has_pending_work(done)

    asyncio.run(run())


@pytest.mark.parametrize(
    "command",
    [
        Command(resume="yes", update={"answer": "injected"}),
        Command(resume="yes", goto="call_model"),
        Command(resume="yes", graph=Command.PARENT),
        Command(resume=None),
    ],
)
def test_resume_accepts_only_answer_command_without_state_or_routing(
    command: Command[str],
) -> None:
    async def ask(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> Mapping[str, object]:
        return {"answer": interrupt("Continue?")}

    plugin = AgentPlugin(
        "answer", state_schema=AnswerState, on_turn_start=(PluginStep("ask", ask),)
    )

    async def run() -> None:
        async with offline_client(
            httpx2.MockTransport(
                lambda _: sse_response(EventStream(response_events(response_payload())))
            )
        ) as client:
            async with open_agent(
                agent_id="command",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=[BundleConfig(__name__, {"plugins": (plugin,)})],
                checkpointer=InMemorySaver(),
            ) as agent:
                async for _ in agent.astream(
                    workspace_id=WORKSPACE, turn_id=TURN, input="original"
                ):
                    pass
                before = await agent.aget_state(workspace_id=WORKSPACE)
                with pytest.raises(AgentExecutionError, match="resume-only"):
                    async for _ in agent.aresume(
                        workspace_id=WORKSPACE, turn_id=TURN, resume_command=command
                    ):
                        pass
                after = await agent.aget_state(workspace_id=WORKSPACE)
                assert after.config == before.config
                assert after.values == before.values

    asyncio.run(run())
