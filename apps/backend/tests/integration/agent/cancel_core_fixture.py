"""取消驗收用的合成插件，透過正式 Bundle／服務契約提供可觀察效果。"""

import operator
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Annotated, TypedDict
from uuid import UUID

from langgraph.runtime import Runtime
from langgraph.types import interrupt

from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentContext,
    AgentPlugin,
    PluginStep,
)
from caliburn.modules.agent.plugins.services import ServiceKey
from caliburn.modules.agent.state import AgentState


class BaselineFields(TypedDict, total=False):
    baseline: Annotated[list[str], operator.add]
    baseline_turn_id: UUID


class BaselineState(AgentState, BaselineFields):
    pass


@dataclass
class CancellationEffects:
    fail: bool = False
    withdrawals: dict[UUID, list[str] | None] = field(default_factory=dict)
    started: list[UUID] = field(default_factory=list)
    missing_states: set[UUID] = field(default_factory=set)


EFFECTS = ServiceKey[CancellationEffects]("cancel.effects")


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    async def initialize(
        state: BaselineState, *, runtime: Runtime[AgentContext]
    ) -> BaselineState:
        runtime.context.services.require(EFFECTS).started.append(state["turn_id"])
        if config.get("drain"):
            assert runtime.control is not None
            runtime.control.request_drain("synthetic drain")
        return {
            "baseline": [str(state["turn_id"])],
            "baseline_turn_id": state["turn_id"],
        }

    async def wait(
        state: BaselineState, *, runtime: Runtime[AgentContext]
    ) -> BaselineState:
        if config.get("wait"):
            interrupt("synthetic question")
        return {}

    async def cancel(
        state: BaselineState | None,
        *,
        workspace_id: UUID,
        turn_id: UUID,
        context: AgentContext,
    ) -> None:
        effects = context.services.require(EFFECTS)
        if effects.fail:
            raise RuntimeError("synthetic withdrawal failure")
        if state is None:
            effects.missing_states.add(turn_id)
        baseline = None
        if state is not None and state.get("baseline_turn_id") == turn_id:
            baseline = state["baseline"]
        effects.withdrawals[turn_id] = baseline

    return AgentBundle(
        (
            AgentPlugin(
                "cancel_fixture",
                required_services=(EFFECTS,),
                state_schema=BaselineFields,
                on_turn_start=(
                    PluginStep("initialize", initialize, input_schema=BaselineState),
                ),
                before_model_step=(
                    PluginStep("wait", wait, input_schema=BaselineState),
                ),
                on_turn_cancel=cancel,
            ),
        )
    )
