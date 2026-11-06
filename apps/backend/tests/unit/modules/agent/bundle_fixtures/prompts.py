"""固定提示在啟動宣告一次。"""

from collections.abc import Mapping

from caliburn.modules.agent.plugins.contracts import AgentBundle, AgentPlugin


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    label = str(config["label"])
    return AgentBundle(
        (
            AgentPlugin(f"{label}-opening", prompt_sections=(f"{label}: opening",)),
            AgentPlugin(
                f"{label}-details",
                prompt_sections=(
                    f"{label}: first detail",
                    "",
                    f"{label}: second detail",
                ),
            ),
        )
    )
