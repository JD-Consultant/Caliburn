"""獨立配置訪談保存、既有原話預載與來源閱讀說明。"""

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field

from caliburn.bundles.interview.cancellation import cancel_turn_interview
from caliburn.bundles.interview.context import preload_interview_context
from caliburn.bundles.interview.discovery import discover_interview_sources
from caliburn.bundles.interview.read_tool import create_read_interview_tool
from caliburn.bundles.interview.recording import record_final_message, record_input
from caliburn.bundles.interview.services import (
    INTERVIEW_QUERIES,
    INTERVIEW_UOW_FACTORY,
    MODEL_REFERENCES,
)
from caliburn.bundles.interview.source_prompt import INTERVIEW_SOURCE_PROMPT
from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentPlugin,
    PluginStep,
)


class _Settings(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    max_output_characters: int = Field(default=24000, ge=1)


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    settings = _Settings.model_validate(config)
    return AgentBundle(
        plugins=(
            AgentPlugin(
                name="interview",
                required_services=(INTERVIEW_UOW_FACTORY, MODEL_REFERENCES),
                on_turn_start=(PluginStep("record_input", record_input),),
                on_turn_end=(PluginStep("record_final_message", record_final_message),),
                on_turn_cancel=cancel_turn_interview,
            ),
            AgentPlugin(
                name="interview_context",
                required_services=(INTERVIEW_QUERIES, MODEL_REFERENCES),
                on_turn_start=(
                    PluginStep("preload_context", preload_interview_context),
                ),
            ),
            AgentPlugin(
                name="interview_source_prompt",
                prompt_sections=(INTERVIEW_SOURCE_PROMPT,),
            ),
            AgentPlugin(
                name="interview_read",
                required_services=(INTERVIEW_QUERIES, MODEL_REFERENCES),
                tools=(
                    create_read_interview_tool(
                        max_output_characters=settings.max_output_characters
                    ),
                ),
            ),
            AgentPlugin(
                name="interview_navigation",
                required_services=(INTERVIEW_QUERIES, MODEL_REFERENCES),
                on_turn_start=(
                    PluginStep("discover_sources", discover_interview_sources),
                ),
            ),
        ),
    )
