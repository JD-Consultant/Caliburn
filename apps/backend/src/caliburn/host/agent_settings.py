"""Host 的明示 Agent 設定；client 與 pool 由 lifespan 建立及關閉。"""

from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from pathlib import Path

from openai import AsyncOpenAI
from openai.types.responses.response_create_params import ResponseCreateParamsBase
from openai.types.shared import ReasoningEffort
from pydantic import BaseModel, ConfigDict, Field, JsonValue

from caliburn.modules.agent.bootstrap import BundleConfig


@dataclass(frozen=True)
class AgentConfiguration:
    agent_id: str
    resume_version: str
    checkpoint_conninfo: str = field(repr=False)
    model_settings: ResponseCreateParamsBase
    max_active_turns: int = 8
    bundles: tuple[BundleConfig, ...] = ()
    client_factory: Callable[[], AsyncOpenAI] = partial(
        AsyncOpenAI, max_retries=0, timeout=120.0
    )

    def __post_init__(self) -> None:
        if not self.resume_version.strip() or "\0" in self.resume_version:
            raise ValueError("resume_version 必須為非空白且不含 NUL 的字串")
        if type(self.max_active_turns) is not int or self.max_active_turns < 1:
            raise ValueError("max_active_turns 必須為正整數")


class BundleSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    module: str = Field(min_length=1)
    config: dict[str, JsonValue] = Field(default_factory=dict)
    plugins: list[str] | None = None


class AgentSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    agent_id: str = Field(min_length=1)
    resume_version: str
    model: str = Field(min_length=1)
    max_output_tokens: int = Field(default=16384, gt=0)
    max_active_turns: int = Field(default=8, gt=0, strict=True)
    reasoning_effort: ReasoningEffort = "low"
    sdk_timeout_seconds: float = Field(default=120.0, gt=0)
    bundles: list[BundleSettings] = Field(default_factory=list)


def load_agent_configuration(
    path: Path, *, checkpoint_conninfo: str
) -> AgentConfiguration:
    """只讀明示 JSON；憑證由程序環境交給 SDK，不放進設定檔。"""
    try:
        settings = AgentSettings.model_validate_json(path.read_text(encoding="utf-8"))
        return AgentConfiguration(
            agent_id=settings.agent_id,
            resume_version=settings.resume_version,
            checkpoint_conninfo=checkpoint_conninfo,
            model_settings={
                "model": settings.model,
                "max_output_tokens": settings.max_output_tokens,
                "reasoning": {"effort": settings.reasoning_effort},
            },
            max_active_turns=settings.max_active_turns,
            bundles=tuple(
                BundleConfig(
                    bundle.module,
                    bundle.config,
                    plugins=tuple(bundle.plugins)
                    if bundle.plugins is not None
                    else None,
                )
                for bundle in settings.bundles
            ),
            client_factory=partial(
                AsyncOpenAI, max_retries=0, timeout=settings.sdk_timeout_seconds
            ),
        )
    except OSError, ValueError:
        raise ValueError("Agent 設定檔無法讀取或不符合契約") from None
