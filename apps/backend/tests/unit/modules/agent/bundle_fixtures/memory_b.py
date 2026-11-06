"""可替換的 Memory B 宣告。"""

from collections.abc import Mapping

from caliburn.modules.agent.plugins.contracts import AgentBundle
from tests.unit.modules.agent.bundle_fixtures.memory_materials import memory_bundle


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    return memory_bundle("B")
