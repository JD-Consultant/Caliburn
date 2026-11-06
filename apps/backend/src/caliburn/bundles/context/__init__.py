"""上下文生命週期：Memory 換窗及 OpenAI 原生壓縮兩個插件。"""

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field

from caliburn.bundles.context.contracts import WindowContribution as WindowContribution
from caliburn.bundles.context.native_plugin import create_native_plugin
from caliburn.bundles.context.window import create_window_plugin
from caliburn.modules.agent.plugins.contracts import AgentBundle


class _Settings(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    history_threshold_tokens: int = Field(default=96000, gt=0)
    threshold_tokens: int = Field(default=160000, gt=0)


def create_bundle(config: Mapping[str, object]) -> AgentBundle:
    settings = _Settings.model_validate(config)
    return AgentBundle(
        plugins=(
            create_window_plugin(),
            create_native_plugin(
                threshold_tokens=settings.threshold_tokens,
                history_threshold_tokens=settings.history_threshold_tokens,
            ),
        )
    )
