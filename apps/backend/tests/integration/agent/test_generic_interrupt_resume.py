"""通用恢復走真 PostgreSQL；不依賴提問工具或問答能力。"""

import asyncio
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from typing import TypedDict, cast
from uuid import UUID

import httpx2
import pytest
from langgraph.runtime import Runtime
from langgraph.types import StateSnapshot, interrupt

from caliburn.modules.agent.agent import Agent
from caliburn.modules.agent.application.agent_service import AgentService
from caliburn.modules.agent.application.errors import AgentUnavailable, TurnConflict
from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from caliburn.modules.agent.interrupts import InterruptResume, ResumePoint
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
    offline_client,
    response_events,
    response_payload,
    sse_response,
)

WORKSPACE = UUID(int=1)
TURN = UUID(int=11)


class DecisionState(TypedDict):
    decision: str


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    return AgentBundle((cast(AgentPlugin, config["plugin"]),))


async def ensure_workspace(workspace_id: UUID) -> None:
    assert workspace_id == WORKSPACE


@asynccontextmanager
async def service_for(
    conninfo: str, plugin: AgentPlugin
) -> AsyncIterator[tuple[Agent, AgentService]]:
    async with (
        open_postgres_checkpointer(conninfo, initialize=True) as saver,
        offline_client(
            httpx2.MockTransport(
                lambda _: sse_response(EventStream(response_events(response_payload())))
            )
        ) as client,
        open_agent(
            agent_id="generic-resume",
            resume_version="v1",
            client=client,
            model_settings=MODEL_REQUEST,
            bundles=[BundleConfig(__name__, {"plugin": plugin})],
            checkpointer=saver,
        ) as agent,
    ):
        service = AgentService(agent, ensure_workspace=ensure_workspace)
        try:
            yield agent, service
        finally:
            await service.aclose()


async def finish(service: AgentService) -> None:
    async for _ in service.stream_turn(workspace_id=WORKSPACE, turn_id=TURN):
        pass


def saved_decision(snapshots: Sequence[StateSnapshot]) -> bool:
    return any(
        snapshot.values.get("turn_id") == TURN
        and snapshot.values.get("decision") == "deploy"
        for snapshot in snapshots
    )


def test_resume_confirmation_keeps_original_interrupt_evidence(
    checkpoint_conninfo: str,
) -> None:
    async def approve(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> Mapping[str, object]:
        decision = interrupt({"operation": "deployment", "revision": "a1"})
        return {"decision": decision}

    plugin = AgentPlugin(
        "deployment",
        state_schema=DecisionState,
        on_turn_start=(PluginStep("approve", approve),),
    )

    def prepare(snapshot: StateSnapshot) -> InterruptResume:
        return InterruptResume(
            ResumePoint(
                snapshot.config["configurable"]["checkpoint_id"], snapshot.interrupts[0]
            ),
            "deploy",
        )

    def saved_approval(snapshots: Sequence[StateSnapshot]) -> bool:
        displayed = any(
            recorded.value == {"operation": "deployment", "revision": "a1"}
            for snapshot in snapshots
            for recorded in snapshot.interrupts
        )
        if not displayed:
            raise TurnConflict("Cannot verify the original approval request")
        return saved_decision(snapshots)

    async def run() -> None:
        async with service_for(checkpoint_conninfo, plugin) as (_, service):
            await service.submit_turn(workspace_id=WORKSPACE, turn_id=TURN, input="run")
            await finish(service)
            accepted = await service.resume_interrupt(
                workspace_id=WORKSPACE,
                turn_id=TURN,
                request_key="deploy:a1",
                prepare=prepare,
                is_saved=saved_approval,
            )
            assert accepted.created
            await finish(service)
            completed = await service.get_turn(workspace_id=WORKSPACE, turn_id=TURN)
            assert completed.status == "completed"
            assert completed.output == "Synthetic reply"

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_non_question_interrupt_requires_its_own_saved_result(
    checkpoint_conninfo: str,
) -> None:
    fail_after_resume = True
    prepared = []

    async def approve(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> Mapping[str, object]:
        decision = interrupt({"operation": "deployment", "revision": "a1"})
        if fail_after_resume:
            raise RuntimeError("synthetic failure before decision checkpoint")
        return {"decision": decision}

    plugin = AgentPlugin(
        "deployment",
        state_schema=DecisionState,
        on_turn_start=(PluginStep("approve", approve),),
    )

    def prepare(snapshot: StateSnapshot) -> InterruptResume:
        prepared.append(snapshot.config)
        return InterruptResume(
            ResumePoint(
                snapshot.config["configurable"]["checkpoint_id"], snapshot.interrupts[0]
            ),
            "deploy",
        )

    async def run() -> None:
        nonlocal fail_after_resume
        async with service_for(checkpoint_conninfo, plugin) as (agent, service):
            await service.submit_turn(workspace_id=WORKSPACE, turn_id=TURN, input="run")
            await finish(service)
            with pytest.raises(AgentUnavailable):
                await service.resume_interrupt(
                    workspace_id=WORKSPACE,
                    turn_id=TURN,
                    request_key="deploy:a1",
                    prepare=prepare,
                    is_saved=saved_decision,
                )
            failed = await agent.aget_state(workspace_id=WORKSPACE)
            assert failed.interrupts and any(task.error for task in failed.tasks)
            assert not saved_decision([failed])
            with pytest.raises(TurnConflict):
                await service.resume_interrupt(
                    workspace_id=WORKSPACE,
                    turn_id=TURN,
                    request_key="deploy:a1",
                    prepare=prepare,
                    is_saved=saved_decision,
                )
            fail_after_resume = False
            await service.resume_turn(workspace_id=WORKSPACE, turn_id=TURN)
            await finish(service)
            execution = await service.read_turn_execution(
                workspace_id=WORKSPACE, turn_id=TURN
            )
            assert saved_decision([execution.current, *execution.history])
            assert execution.current.values["turn_input"] == "run"
            repeated = await service.resume_interrupt(
                workspace_id=WORKSPACE,
                turn_id=TURN,
                request_key="deploy:a1",
                prepare=prepare,
                is_saved=saved_decision,
            )
            assert not repeated.created
            assert repeated.turn.status == "completed"
            assert len(prepared) == 2

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


@pytest.mark.parametrize("changed", ["checkpoint", "payload"])
def test_core_rejects_resume_point_changed_after_preparation(
    checkpoint_conninfo: str, changed: str
) -> None:
    from langgraph.types import Command

    from caliburn.modules.agent.agent import AgentExecutionError

    async def approve(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> Mapping[str, object]:
        first = interrupt({"operation": "deployment", "revision": "a1"})
        second = interrupt({"operation": "deployment", "revision": "a2"})
        return {"decision": f"{first}/{second}"}

    plugin = AgentPlugin(
        "deployment",
        state_schema=DecisionState,
        on_turn_start=(PluginStep("approve", approve),),
    )

    async def run() -> None:
        async with service_for(checkpoint_conninfo, plugin) as (agent, service):
            await service.submit_turn(workspace_id=WORKSPACE, turn_id=TURN, input="run")
            await finish(service)
            original = await agent.aget_state(workspace_id=WORKSPACE)
            if changed == "payload":
                async for _ in agent.aresume(
                    workspace_id=WORKSPACE,
                    turn_id=TURN,
                    resume_command=Command(
                        resume={original.interrupts[0].id: "deploy"}
                    ),
                ):
                    pass
            before = await agent.aget_state(workspace_id=WORKSPACE)
            point = ResumePoint(
                "earlier-checkpoint"
                if changed == "checkpoint"
                else original.config["configurable"]["checkpoint_id"],
                original.interrupts[0],
            )
            if changed == "payload":
                assert original.config == before.config
                assert original.interrupts[0].id == before.interrupts[0].id
                assert original.interrupts[0].value != before.interrupts[0].value
            with pytest.raises(AgentExecutionError, match="changed"):
                async for _ in agent.aresume(
                    workspace_id=WORKSPACE,
                    turn_id=TURN,
                    resume_command=Command(resume={before.interrupts[0].id: "deploy"}),
                    expected=point,
                ):
                    pass
            after = await agent.aget_state(workspace_id=WORKSPACE)
            assert after.config == before.config
            assert after.values == before.values
            assert after.interrupts == before.interrupts

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_service_rechecks_prepared_interrupt_when_background_execution_starts(
    checkpoint_conninfo: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    from collections.abc import AsyncGenerator
    from typing import Any

    from langgraph.types import Command

    async def approve(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> Mapping[str, object]:
        interrupt({"operation": "deployment", "revision": "a1"})
        decision = interrupt({"operation": "deployment", "revision": "a2"})
        return {"decision": decision}

    plugin = AgentPlugin(
        "deployment",
        state_schema=DecisionState,
        on_turn_start=(PluginStep("approve", approve),),
    )

    def prepare(snapshot: StateSnapshot) -> InterruptResume:
        return InterruptResume(
            ResumePoint(
                snapshot.config["configurable"]["checkpoint_id"], snapshot.interrupts[0]
            ),
            "deploy",
        )

    async def run() -> None:
        async with service_for(checkpoint_conninfo, plugin) as (agent, service):
            await service.submit_turn(workspace_id=WORKSPACE, turn_id=TURN, input="run")
            await finish(service)
            before = await agent.aget_state(workspace_id=WORKSPACE)
            resume = agent.aresume

            async def change_before_resume(
                **kwargs: Any,
            ) -> AsyncGenerator[dict[str, Any]]:
                # 模擬准入後、Core 取得最新快照前，原生狀態已前進。
                async for _ in resume(
                    workspace_id=WORKSPACE,
                    turn_id=TURN,
                    resume_command=Command(resume={before.interrupts[0].id: "deploy"}),
                ):
                    pass
                async for part in resume(**kwargs):
                    yield part

            monkeypatch.setattr(agent, "aresume", change_before_resume)
            with pytest.raises(AgentUnavailable):
                await service.resume_interrupt(
                    workspace_id=WORKSPACE,
                    turn_id=TURN,
                    request_key="deploy:a1",
                    prepare=prepare,
                    is_saved=saved_decision,
                )
            after = await agent.aget_state(workspace_id=WORKSPACE)
            assert [pending.value for pending in after.interrupts] == [
                {"operation": "deployment", "revision": "a2"}
            ]
            assert not saved_decision([after])

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_identical_interrupt_requests_join_without_preparing_again(
    checkpoint_conninfo: str,
) -> None:
    async def run() -> None:
        consumed = asyncio.Event()
        release = asyncio.Event()
        preparations = []

        async def approve(
            state: AgentState, *, runtime: Runtime[AgentContext]
        ) -> Mapping[str, object]:
            decision = interrupt({"operation": "deployment", "revision": "a1"})
            consumed.set()
            await release.wait()
            return {"decision": decision}

        plugin = AgentPlugin(
            "deployment",
            state_schema=DecisionState,
            on_turn_start=(PluginStep("approve", approve),),
        )

        def prepare(snapshot: StateSnapshot) -> InterruptResume:
            preparations.append(snapshot.config)
            return InterruptResume(
                ResumePoint(
                    snapshot.config["configurable"]["checkpoint_id"],
                    snapshot.interrupts[0],
                ),
                "deploy",
            )

        async with service_for(checkpoint_conninfo, plugin) as (_, service):
            await service.submit_turn(workspace_id=WORKSPACE, turn_id=TURN, input="run")
            await finish(service)
            submissions = [
                asyncio.create_task(
                    service.resume_interrupt(
                        workspace_id=WORKSPACE,
                        turn_id=TURN,
                        request_key="deploy:a1",
                        prepare=prepare,
                        is_saved=saved_decision,
                    )
                )
                for _ in range(3)
            ]
            try:
                await asyncio.wait_for(consumed.wait(), timeout=5)
                with pytest.raises(TurnConflict):
                    await service.resume_interrupt(
                        workspace_id=WORKSPACE,
                        turn_id=TURN,
                        request_key="deploy:a2",
                        prepare=prepare,
                        is_saved=saved_decision,
                    )
                assert all(not task.done() for task in submissions)
            finally:
                release.set()
            results = await asyncio.gather(*submissions)
            assert sum(result.created for result in results) == 1
            assert len(preparations) == 1
            await finish(service)

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
