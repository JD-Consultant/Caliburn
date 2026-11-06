"""顧問提示對照的測試 Bundle。"""

from collections.abc import Mapping

from caliburn.bundles.consultant.instructions import CONSULTANT_INSTRUCTIONS
from caliburn.modules.agent.plugins.contracts import AgentBundle, AgentPlugin


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    return AgentBundle(
        plugins=(
            AgentPlugin(
                name="consultant",
                prompt_sections=(
                    f"{CONSULTANT_INSTRUCTIONS}\n"
                    "訪談初期若已能辨認員工提到的案例屬於哪項工作及本人分工，"
                    "且主要工作範圍仍不清楚，下一問先用一個中立問題了解其他平常或定期做的工作。",
                ),
            ),
        )
    )
