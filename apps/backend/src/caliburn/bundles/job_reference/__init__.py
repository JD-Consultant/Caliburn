"""公版查找工具的靜態組裝。"""

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field

from caliburn.bundles.job_reference.instructions import (
    OCCUPATION_REFERENCE_INSTRUCTIONS,
)
from caliburn.bundles.job_reference.services import (
    REFERENCE_IDS,
    REFERENCE_RUNNER,
    REFERENCE_SEARCH,
)
from caliburn.bundles.job_reference.tools import create_reference_tools
from caliburn.modules.agent.plugins.contracts import AgentBundle, AgentPlugin


class _Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_result_characters: int = Field(default=1_000_000, strict=True, gt=0)


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    settings = _Settings.model_validate(config)
    return AgentBundle(
        plugins=(
            AgentPlugin(
                name="job_reference",
                prompt_sections=(OCCUPATION_REFERENCE_INSTRUCTIONS,),
                tools=create_reference_tools(
                    max_result_characters=settings.max_result_characters
                ),
                required_services=(REFERENCE_SEARCH, REFERENCE_RUNNER, REFERENCE_IDS),
            ),
        )
    )
