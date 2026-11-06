"""顧問與工作記憶分析角色的靜態組裝入口。"""

from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from caliburn.bundles.context.contracts import WindowContribution
from caliburn.bundles.context.services import WINDOW_CONTRIBUTIONS
from caliburn.bundles.interview.discovery import discover_interview_sources
from caliburn.bundles.interview.services import INTERVIEW_QUERIES, MODEL_REFERENCES
from caliburn.bundles.memory.factory import create_coordinator_factory
from caliburn.bundles.memory.initialization import (
    CONSULTANT_MEMORY_INSTRUCTIONS,
    AnalystLifecycle,
    initialize_consultant,
)
from caliburn.bundles.memory.reads import create_read_tools, create_request_tool
from caliburn.bundles.memory.services import (
    MEMORY_COMPLETED_TURNS,
    MEMORY_COORDINATOR_FACTORY,
    MEMORY_QUERIES,
    MEMORY_SERVICE,
)
from caliburn.bundles.memory.situation_instructions import SITUATION_INSTRUCTIONS
from caliburn.bundles.memory.state import ConsultantMemoryState
from caliburn.bundles.memory.understanding_instructions import (
    UNDERSTANDING_INSTRUCTIONS,
)
from caliburn.bundles.memory.window import (
    memory_published_changed,
    prepare_memory_input,
    prepare_memory_window,
)
from caliburn.bundles.memory.writes import create_write_tools
from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentPlugin,
    PluginStep,
)
from caliburn.modules.agent.plugins.services import PluginServices, ServiceBinding


class _Settings(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    role: Literal["consultant", "situation", "understanding"] = "consultant"
    max_tool_result_characters: int = Field(default=1_000_000, gt=0)
    max_context_characters: int = Field(default=1_000_000, gt=0)


@asynccontextmanager
async def _open_window_contribution(
    services: PluginServices,
) -> AsyncIterator[tuple[ServiceBinding[Any], ...]]:
    yield (
        WINDOW_CONTRIBUTIONS.bind(
            (
                WindowContribution(
                    prepare_memory_window,
                    memory_published_changed,
                    prepare_memory_input,
                ),
            )
        ),
    )


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    settings = _Settings.model_validate(config)
    role = settings.role
    tools = create_read_tools(role, limit=settings.max_tool_result_characters)
    if role == "consultant":
        factory = create_coordinator_factory(
            max_tool_result_characters=settings.max_tool_result_characters,
            max_context_characters=settings.max_context_characters,
        )

        @asynccontextmanager
        async def open_consolidation(
            services: PluginServices,
        ) -> AsyncIterator[tuple[ServiceBinding[Any], ...]]:
            yield (MEMORY_COORDINATOR_FACTORY.bind(factory),)

        return AgentBundle(
            plugins=(
                AgentPlugin(
                    name="memory_context",
                    required_services=(
                        MEMORY_QUERIES,
                        INTERVIEW_QUERIES,
                        MEMORY_COMPLETED_TURNS,
                        MODEL_REFERENCES,
                    ),
                    state_schema=ConsultantMemoryState,
                    on_turn_start=(
                        PluginStep("initialize_consultant", initialize_consultant),
                        PluginStep("discover_interview", discover_interview_sources),
                    ),
                ),
                AgentPlugin(
                    name="memory_prompt",
                    prompt_sections=(CONSULTANT_MEMORY_INSTRUCTIONS,),
                ),
                AgentPlugin(
                    name="memory_read",
                    tools=tools,
                    required_plugins=("memory_context",),
                    required_services=(
                        MEMORY_QUERIES,
                        INTERVIEW_QUERIES,
                        MODEL_REFERENCES,
                    ),
                ),
                AgentPlugin(
                    name="memory_consolidation",
                    tools=(create_request_tool(),),
                    required_plugins=("memory_context",),
                    provided_services=(MEMORY_COORDINATOR_FACTORY,),
                    open_services=open_consolidation,
                ),
                AgentPlugin(
                    name="memory_window",
                    required_plugins=("memory_context",),
                    required_services=(
                        MEMORY_QUERIES,
                        INTERVIEW_QUERIES,
                        MODEL_REFERENCES,
                    ),
                    provided_services=(WINDOW_CONTRIBUTIONS,),
                    open_services=_open_window_contribution,
                ),
            )
        )
    lifecycle = AnalystLifecycle(role, context_limit=settings.max_context_characters)
    prompt = (
        SITUATION_INSTRUCTIONS if role == "situation" else UNDERSTANDING_INSTRUCTIONS
    )
    return AgentBundle(
        plugins=(
            AgentPlugin(
                name=f"memory_{role}_context",
                required_services=(MEMORY_QUERIES, MODEL_REFERENCES),
                on_turn_start=(PluginStep("initialize_analyst", lifecycle.initialize),),
            ),
            AgentPlugin(
                name=f"memory_{role}_prompt",
                prompt_sections=(prompt,),
            ),
            AgentPlugin(
                name=f"memory_{role}_tools",
                tools=(
                    *tools,
                    *create_write_tools(
                        role, limit=settings.max_tool_result_characters
                    ),
                ),
                required_services=(MEMORY_QUERIES, MEMORY_SERVICE, MODEL_REFERENCES),
            ),
        )
    )
