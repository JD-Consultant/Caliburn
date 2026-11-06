"""Start the configured consultant and its turn completion work."""

import asyncio
from collections.abc import Callable, Sequence
from contextlib import AsyncExitStack
from functools import partial
from typing import Any
from uuid import UUID

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.types import StateSnapshot

from caliburn.bundles.context.history import (
    completed_window_turns,
    previous_completed_window,
)
from caliburn.bundles.context.services import (
    COMPACTION_CLIENT,
    COMPLETED_TURNS,
    PREVIOUS_WINDOW,
)
from caliburn.bundles.interview.cancellation import cancel_turn_interview
from caliburn.bundles.interview.services import (
    INTERVIEW_QUERIES,
    INTERVIEW_UOW_FACTORY,
    MODEL_REFERENCES,
)
from caliburn.bundles.job_description.cancellation import cancel_turn_jd
from caliburn.bundles.job_description.services import (
    JD_PREVIOUS_COMPLETED,
    JD_UOW_FACTORY,
)
from caliburn.bundles.job_description.state import JobDescriptionState
from caliburn.bundles.job_description.turn_history import project_completed_turn
from caliburn.bundles.memory.coordinator import completed_consultant_turns
from caliburn.bundles.memory.services import (
    MEMORY_COMPLETED_TURNS,
    MEMORY_COORDINATOR_FACTORY,
    MEMORY_QUERIES,
)
from caliburn.bundles.plan.cancellation import cancel_turn_plan
from caliburn.bundles.plan.services import PLAN_QUERIES, PLAN_UOW_FACTORY
from caliburn.bundles.plan.state import PlanState
from caliburn.host.agent_settings import AgentConfiguration
from caliburn.host.memory import MemoryHost
from caliburn.modules.agent.agent import Agent, completed_turn_id
from caliburn.modules.agent.application.agent_service import AgentService
from caliburn.modules.agent.application.errors import TurnNotFound
from caliburn.modules.agent.bootstrap import BundleConfig, load_plugins, open_agent
from caliburn.modules.agent.plugins.contracts import AgentBundle, AgentPlugin
from caliburn.modules.agent.plugins.services import ServiceBinding
from caliburn.modules.interview.application.persistence import InterviewQueries
from caliburn.modules.job_description.application.turn_history import (
    CompletedTurnReader,
    JobDescriptionTurnVersions,
)
from caliburn.modules.memory.application.persistence import (
    MemoryQueries,
    MemoryUnitOfWork,
)
from caliburn.modules.model_references import ModelReferences
from caliburn.modules.workspace.application.errors import WorkspaceNotFoundError
from caliburn.modules.workspace.application.workspace_service import WorkspaceService


def compose_consultant_bundles(
    bundles: Sequence[BundleConfig | AgentBundle],
) -> tuple[AgentBundle, ...]:
    plugins = load_plugins(bundles)
    cancellations = tuple(plugin.on_turn_cancel for plugin in plugins)
    retained = []
    if cancel_turn_jd not in cancellations:
        retained.append(
            AgentPlugin(
                name="job_description_cancellation",
                required_services=(JD_UOW_FACTORY,),
                state_schema=JobDescriptionState,
                on_turn_cancel=cancel_turn_jd,
            )
        )
    if cancel_turn_plan not in cancellations:
        retained.append(
            AgentPlugin(
                name="plan_cancellation",
                required_services=(PLAN_QUERIES, PLAN_UOW_FACTORY),
                state_schema=PlanState,
                on_turn_cancel=cancel_turn_plan,
            )
        )
    if cancel_turn_interview not in cancellations:
        retained.append(
            AgentPlugin(
                name="interview_cancellation",
                required_services=(INTERVIEW_UOW_FACTORY,),
                on_turn_cancel=cancel_turn_interview,
            )
        )
    return (AgentBundle(plugins=(*plugins, *retained)),)


async def read_completed_jd_turn(
    *, agent: Agent, workspace_id: UUID, turn_id: UUID
) -> JobDescriptionTurnVersions | None:
    """只判讀指定輪的最新保存點；不由較舊完成狀態覆蓋取消或未完成。"""
    snapshots = [
        snapshot
        async for snapshot in agent.aget_state_history(
            workspace_id=workspace_id, turn_id=turn_id, limit=1
        )
    ]
    if not snapshots or completed_turn_id(snapshots[0]) != turn_id:
        return None
    return project_completed_turn(
        workspace_id=workspace_id, turn_id=turn_id, values=snapshots[0].values
    )


async def start_consultant(
    stack: AsyncExitStack,
    *,
    config: AgentConfiguration,
    checkpointer: BaseCheckpointSaver[Any],
    workspaces: WorkspaceService,
    interview_queries: InterviewQueries,
    memory_queries: MemoryQueries,
    memory_uow_factory: Callable[[], MemoryUnitOfWork],
    references: ModelReferences,
    services: tuple[ServiceBinding[Any], ...],
) -> tuple[AgentService, MemoryHost | None, CompletedTurnReader]:
    client = await stack.enter_async_context(config.client_factory())
    bundles = compose_consultant_bundles(config.bundles)

    async def completed(workspace_id: UUID) -> frozenset[UUID]:
        return await completed_consultant_turns(agent, workspace_id=workspace_id)

    async def previous(workspace_id: UUID, turn_id: UUID) -> StateSnapshot | None:
        return await previous_completed_window(
            agent, workspace_id=workspace_id, turn_id=turn_id
        )

    async def completed_windows(workspace_id: UUID) -> frozenset[UUID]:
        return await completed_window_turns(agent, workspace_id=workspace_id)

    async def previous_completed(
        workspace_id: UUID, turn_id: UUID
    ) -> StateSnapshot | None:
        return await agent.aget_previous_completed_turn(
            workspace_id=workspace_id, before_turn_id=turn_id
        )

    agent = await stack.enter_async_context(
        open_agent(
            agent_id=config.agent_id,
            resume_version=config.resume_version,
            client=client,
            checkpointer=checkpointer,
            model_settings=config.model_settings,
            bundles=bundles,
            external_services=(
                COMPACTION_CLIENT.bind(client),
                PREVIOUS_WINDOW.bind(previous),
                COMPLETED_TURNS.bind(completed_windows),
                JD_PREVIOUS_COMPLETED.bind(previous_completed),
                INTERVIEW_QUERIES.bind(interview_queries),
                MODEL_REFERENCES.bind(references),
                MEMORY_QUERIES.bind(memory_queries),
                MEMORY_COMPLETED_TURNS.bind(completed),
                *services,
            ),
        )
    )
    memory_host = None
    if any(
        MEMORY_COORDINATOR_FACTORY in plugin.provided_services
        for bundle in bundles
        for plugin in bundle.plugins
    ):
        coordinator = agent.services.require(MEMORY_COORDINATOR_FACTORY)(
            consultant=agent,
            queries=memory_queries,
            interview_queries=interview_queries,
            uow_factory=memory_uow_factory,
            agent_id=config.agent_id,
            resume_version=config.resume_version,
            client=client,
            model_settings=config.model_settings,
            checkpointer=checkpointer,
            references=references,
        )
        memory_host = MemoryHost(
            consultant=agent,
            coordinator=coordinator,
            interview_queries=interview_queries,
            max_active=config.max_active_turns,
        )
        stack.push_async_callback(memory_host.aclose)

    async def ensure_workspace(workspace_id: UUID) -> None:
        try:
            await asyncio.to_thread(workspaces.get, workspace_id=workspace_id)
        except WorkspaceNotFoundError as error:
            raise TurnNotFound(str(workspace_id)) from error

    service = AgentService(
        agent,
        ensure_workspace=ensure_workspace,
        max_active_turns=config.max_active_turns,
        on_turn_completed=memory_host.notify if memory_host else None,
    )
    stack.push_async_callback(service.aclose)
    if memory_host is not None:
        await memory_host.recover(workspaces)
    return service, memory_host, partial(read_completed_jd_turn, agent=agent)
