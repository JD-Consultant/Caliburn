"""合成比較用替代 Memory Bundle：只替換 B1 提示，沿原工具與資料規則。"""

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from caliburn.bundles.memory import create_bundle as create_memory_bundle
from caliburn.bundles.memory.factory import create_coordinator_factory
from caliburn.bundles.memory.services import MEMORY_COORDINATOR_FACTORY
from caliburn.bundles.memory.situation_instructions import SITUATION_INSTRUCTIONS
from caliburn.modules.agent.bootstrap import BundleConfig
from caliburn.modules.agent.plugins.contracts import AgentBundle, AgentPlugin
from caliburn.modules.agent.plugins.services import PluginServices, ServiceBinding

DEFAULT_NOTE = "先核對原話中的精確數值及適用範圍；未知或未提供的內容保持未知。"


class _Settings(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    role: Literal["consultant", "situation"] = "consultant"
    note: str = DEFAULT_NOTE
    threshold_tokens: int = Field(default=160000, gt=0)
    context_plugins: list[str] = Field(default_factory=lambda: ["native_compaction"])


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    settings = _Settings.model_validate(config)
    if settings.role == "situation":
        return AgentBundle(
            (
                AgentPlugin(
                    name="candidate_situation_prompt",
                    prompt_sections=(SITUATION_INSTRUCTIONS + "\n" + settings.note,),
                ),
            )
        )

    native = BundleConfig(
        "caliburn.bundles.context",
        {"threshold_tokens": settings.threshold_tokens},
        plugins=tuple(settings.context_plugins),
    )
    factory = create_coordinator_factory(
        situation_bundles=(
            BundleConfig(
                "caliburn.bundles.memory",
                {"role": "situation"},
                plugins=("memory_situation_context", "memory_situation_tools"),
            ),
            BundleConfig(__name__, {"role": "situation", "note": settings.note}),
            native,
        ),
        understanding_bundles=(
            BundleConfig("caliburn.bundles.memory", {"role": "understanding"}),
            native,
        ),
    )

    @asynccontextmanager
    async def open_services(
        services: PluginServices,
    ) -> AsyncIterator[tuple[ServiceBinding[Any], ...]]:
        yield (MEMORY_COORDINATOR_FACTORY.bind(factory),)

    return AgentBundle(
        tuple(
            replace(
                plugin,
                provided_services=(MEMORY_COORDINATOR_FACTORY,),
                open_services=open_services,
            )
            if plugin.name == "memory_consolidation"
            else plugin
            for plugin in create_memory_bundle({}).plugins
        )
    )
