"""固定案例與明示候選的輸入邊界；評閱判準不送進受測 Agent。"""

from dataclasses import asdict, dataclass, replace
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from caliburn.agents.job_consultant.configuration import (
    ConsultantConfiguration,
    ConsultantPrompts,
    ToolDescriptionOverride,
)
from caliburn.agents.job_consultant.tools import consultant_tool_definitions
from caliburn.transport.model_tools.jd_reads import DEFAULT_JD_READ_MAX_RESULT_CHARACTERS

type PromptSection = Literal[
    "professional_method", "focus", "interview_plan", "occupation_references"
]


class EvaluationCase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    employee_name: str = "合成受訪者"
    inputs: tuple[str, ...] = Field(min_length=1)
    criteria: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class PreparedConsultantCandidate:
    """單次比較的固定值；manifest 與正式 App 共用同一份不可變配置。"""

    name: str
    interview_plans_enabled: bool
    configuration: ConsultantConfiguration

    def manifest(self) -> dict[str, object]:
        return {
            "name": self.name,
            "interview_plans_enabled": self.interview_plans_enabled,
            "configuration": asdict(self.configuration),
            "instructions": self.configuration.instructions(
                interview_plans_enabled=self.interview_plans_enabled,
                occupation_references_enabled=False,
            ),
            "tools": self.configuration.describe_tools(
                consultant_tool_definitions(interview_plans_enabled=self.interview_plans_enabled)
            ),
        }


class ConsultantCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,60}$")
    prompts: dict[PromptSection, str] = Field(default_factory=dict)
    tool_descriptions: dict[str, str] = Field(default_factory=dict)
    interview_plans_enabled: bool = True
    jd_read_max_result_characters: int = Field(
        default=DEFAULT_JD_READ_MAX_RESULT_CHARACTERS, strict=True, gt=0
    )

    def configuration(self) -> ConsultantConfiguration:
        """將輸入轉成 Runner 所需的不可變值，排除 DTO 中的可變 dict。"""
        return ConsultantConfiguration(
            jd_read_max_result_characters=self.jd_read_max_result_characters,
            prompts=replace(ConsultantPrompts(), **self.prompts),
            tool_descriptions=tuple(
                ToolDescriptionOverride(name, description)
                for name, description in self.tool_descriptions.items()
            ),
        )

    def prepare(self) -> PreparedConsultantCandidate:
        return PreparedConsultantCandidate(
            name=self.name,
            interview_plans_enabled=self.interview_plans_enabled,
            configuration=self.configuration(),
        )

    def manifest(self) -> dict[str, object]:
        return self.prepare().manifest()


class ConsultantComparison(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    case: EvaluationCase
    candidates: tuple[ConsultantCandidate, ...] = Field(min_length=2)

    @model_validator(mode="after")
    def distinct_candidates(self) -> Self:
        names = [candidate.name for candidate in self.candidates]
        if len(names) != len(set(names)):
            raise ValueError("Candidate names must be distinct")
        # 預檢時即拒絕未知工具，不能到建立資料庫／外部 client 後才失敗。
        for candidate in self.candidates:
            candidate.manifest()
        return self
