"""合成 Bundle 的 Host 公開服務。"""

from caliburn.modules.agent.plugins.services import ServiceKey

LABEL = ServiceKey[str]("label")
EVENTS = ServiceKey[list[str]]("events")
