"""顧問的新回合配置；已保存回合仍由原生 request 決定提示與工具能力。"""

from copy import deepcopy
from dataclasses import dataclass

from openai.types.responses import FunctionToolParam

from caliburn.agents.job_consultant.instructions import CONSULTANT_INSTRUCTIONS
from caliburn.agents.job_consultant.planning_instructions import (
    FOCUS_INSTRUCTIONS,
    INTERVIEW_PLAN_INSTRUCTIONS,
)
from caliburn.agents.job_consultant.reference_instructions import OCCUPATION_REFERENCE_INSTRUCTIONS
from caliburn.transport.model_tools.jd_reads import DEFAULT_JD_READ_MAX_RESULT_CHARACTERS


@dataclass(frozen=True, slots=True)
class ConsultantPrompts:
    """具名提示的值；替換單一段落不需要複製整個 Agent 或改 module global。"""

    professional_method: str = CONSULTANT_INSTRUCTIONS
    focus: str = FOCUS_INSTRUCTIONS
    interview_plan: str = INTERVIEW_PLAN_INSTRUCTIONS
    occupation_references: str = OCCUPATION_REFERENCE_INSTRUCTIONS


@dataclass(frozen=True, slots=True)
class ToolDescriptionOverride:
    """只比較工具說明；schema、handler 及 App 綁定的 scope 仍沿正式契約。"""

    name: str
    description: str


@dataclass(frozen=True, slots=True)
class ConsultantConfiguration:
    """可並存的候選值；不持有 clients、可變工具 schema 或每回合狀態。"""

    prompts: ConsultantPrompts = ConsultantPrompts()
    tool_descriptions: tuple[ToolDescriptionOverride, ...] = ()
    jd_read_max_result_characters: int = DEFAULT_JD_READ_MAX_RESULT_CHARACTERS

    def __post_init__(self) -> None:
        # Python 呼叫者即使傳入 list，也不能在建立配置後悄悄改動候選。
        object.__setattr__(self, "tool_descriptions", tuple(self.tool_descriptions))
        names = [item.name for item in self.tool_descriptions]
        if len(names) != len(set(names)):
            raise ValueError("Duplicate consultant tool description override")
        if (
            type(self.jd_read_max_result_characters) is not int
            or self.jd_read_max_result_characters < 1
        ):
            raise ValueError("JD read result character limit must be a positive integer")

    def instructions(
        self, *, interview_plans_enabled: bool, occupation_references_enabled: bool
    ) -> str:
        """能力開關由組裝根提供；關閉能力時不送出相應操作指示。"""
        sections = [self.prompts.professional_method, self.prompts.focus]
        if interview_plans_enabled:
            sections.append(self.prompts.interview_plan)
        if occupation_references_enabled:
            sections.append(self.prompts.occupation_references)
        return "\n\n".join(sections)

    def describe_tools(self, definitions: list[FunctionToolParam]) -> list[FunctionToolParam]:
        """回傳獨立 schema 值；不存在或未啟用的工具名稱是配置錯誤。"""
        overrides = {item.name: item.description for item in self.tool_descriptions}
        missing = overrides.keys() - {tool["name"] for tool in definitions}
        if missing:
            raise ValueError(
                f"Consultant tool description target is not enabled: {sorted(missing)}"
            )
        copied = deepcopy(definitions)
        for tool in copied:
            if tool["name"] in overrides:
                tool["description"] = overrides[tool["name"]]
        return copied
