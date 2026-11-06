"""將 JD 內容、導覽與取消恢復接入 Agent。"""

from collections.abc import Mapping

from caliburn.bundles.job_description.cancellation import cancel_turn_jd
from caliburn.bundles.job_description.context import create_context_plugin
from caliburn.bundles.job_description.initialization import initialize_turn_jd
from caliburn.bundles.job_description.instructions import JD_INSTRUCTIONS
from caliburn.bundles.job_description.reading import create_read_tool
from caliburn.bundles.job_description.services import (
    JD_CITATION_SOURCES,
    JD_HISTORY_QUERIES,
    JD_MEMORY_QUERIES,
    JD_PREVIOUS_COMPLETED,
    JD_QUERIES,
    JD_REFERENCES,
    JD_UOW_FACTORY,
)
from caliburn.bundles.job_description.source_changes import create_source_changes_tool
from caliburn.bundles.job_description.state import JobDescriptionState
from caliburn.bundles.job_description.turn_changes import (
    capture_completed_jd,
    inject_manual_changes,
)
from caliburn.bundles.job_description.write_tools import create_write_tools
from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
    AgentPlugin,
    PluginStep,
)


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    return AgentBundle(
        plugins=(
            AgentPlugin(
                name="job_description",
                required_services=(
                    JD_QUERIES,
                    JD_UOW_FACTORY,
                    JD_PREVIOUS_COMPLETED,
                ),
                state_schema=JobDescriptionState,
                on_turn_start=(PluginStep("initialize_jd", initialize_turn_jd),),
                on_turn_cancel=cancel_turn_jd,
                on_turn_end=(PluginStep("completed_jd_version", capture_completed_jd),),
            ),
            AgentPlugin(
                name="job_description_tools",
                required_plugins=("job_description",),
                tools=(
                    create_read_tool(),
                    create_source_changes_tool(),
                    *create_write_tools(),
                ),
                required_services=(
                    JD_QUERIES,
                    JD_REFERENCES,
                    JD_UOW_FACTORY,
                    JD_MEMORY_QUERIES,
                    JD_CITATION_SOURCES,
                ),
            ),
            AgentPlugin(
                name="job_description_changes",
                required_plugins=("job_description",),
                required_services=(
                    JD_HISTORY_QUERIES,
                    JD_REFERENCES,
                    JD_MEMORY_QUERIES,
                    JD_CITATION_SOURCES,
                ),
                before_model_step=(
                    PluginStep("manual_jd_changes", inject_manual_changes),
                ),
            ),
            AgentPlugin(
                name="job_description_prompt",
                required_plugins=("job_description_tools",),
                prompt_sections=(JD_INSTRUCTIONS,),
            ),
            create_context_plugin(),
        )
    )
