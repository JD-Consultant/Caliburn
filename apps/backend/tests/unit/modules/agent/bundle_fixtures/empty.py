"""明示沒有能力的 Bundle。"""

from collections.abc import Mapping

from caliburn.modules.agent.plugins.contracts import (
    AgentBundle,
)


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    return AgentBundle()
