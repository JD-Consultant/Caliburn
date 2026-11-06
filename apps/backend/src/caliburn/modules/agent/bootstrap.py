"""依明列設定或已組裝 Bundle，在啟動組裝可重用 Agent。"""

from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from importlib import import_module
from typing import Any, cast

from langgraph.checkpoint.base import BaseCheckpointSaver
from openai import AsyncOpenAI
from openai.types.responses.response_create_params import ResponseCreateParamsBase

from caliburn.modules.agent.agent import Agent
from caliburn.modules.agent.infrastructure.langgraph.agent_graph import (
    build_agent_graph,
)
from caliburn.modules.agent.infrastructure.openai.request_initialization import (
    OpenAIRequestInitializer,
)
from caliburn.modules.agent.plugins.composition import open_plugin_services
from caliburn.modules.agent.plugins.contracts import AgentBundle, AgentPlugin
from caliburn.modules.agent.plugins.services import ServiceBinding


@dataclass(frozen=True)
class BundleConfig:
    module: str
    config: Mapping[str, object] = field(default_factory=dict)
    plugins: tuple[str, ...] | None = None


def load_plugins(
    bundles: Sequence[BundleConfig | AgentBundle],
) -> tuple[AgentPlugin, ...]:
    """每個 factory 只載入一次；選名不改 Bundle 與插件的宣告順序。"""
    loaded: list[AgentPlugin] = []
    for bundle in bundles:
        if isinstance(bundle, AgentBundle):
            loaded.extend(bundle.plugins)
            continue
        module = import_module(bundle.module)
        factory = cast(
            Callable[[Mapping[str, object]], AgentBundle], module.create_bundle
        )
        plugins = factory(deepcopy(bundle.config)).plugins
        if bundle.plugins is None:
            loaded.extend(plugins)
            continue
        selected: set[str] = set()
        available = {plugin.name for plugin in plugins}
        for name in bundle.plugins:
            if name in selected:
                raise ValueError(
                    f"Duplicate plugin selection in {bundle.module}: {name}"
                )
            if name not in available:
                raise ValueError(f"Unknown plugin in {bundle.module}: {name}")
            selected.add(name)
        loaded.extend(plugin for plugin in plugins if plugin.name in selected)
    return tuple(loaded)


@asynccontextmanager
async def open_agent(
    *,
    agent_id: str,
    resume_version: str,
    client: AsyncOpenAI,
    model_settings: ResponseCreateParamsBase,
    bundles: Sequence[BundleConfig | AgentBundle],
    checkpointer: BaseCheckpointSaver[Any],
    external_services: Sequence[ServiceBinding[Any]] = (),
    max_model_steps: int = 64,
    max_tool_calls_per_step: int = 32,
    recursion_limit: int | None = None,
) -> AsyncIterator[Agent]:
    if not agent_id or not agent_id.strip():
        raise ValueError("Agent requires a stable agent_id")
    if checkpointer is None:
        raise ValueError("Agent requires a checkpointer")
    if recursion_limit is not None and recursion_limit <= 0:
        raise ValueError("recursion_limit must be positive")
    plugins = load_plugins(bundles)
    initializer = OpenAIRequestInitializer(
        model_settings,
        tuple(tool for plugin in plugins for tool in plugin.tools),
        tuple(section for plugin in plugins for section in plugin.prompt_sections),
    )
    async with open_plugin_services(plugins, tuple(external_services)) as context:
        graph = build_agent_graph(
            client=client,
            request_initialization=initializer,
            plugins=plugins,
            max_model_steps=max_model_steps,
            max_tool_calls_per_step=max_tool_calls_per_step,
            checkpointer=checkpointer,
        )
        agent = Agent(
            agent_id=agent_id,
            resume_version=resume_version,
            graph=graph,
            context=context,
            recursion_limit=recursion_limit,
            cancel_hooks=tuple(
                plugin.on_turn_cancel
                for plugin in plugins
                if plugin.on_turn_cancel is not None
            ),
        )
        try:
            yield agent
        finally:
            agent.close()
