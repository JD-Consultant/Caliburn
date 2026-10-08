"""App-bound read of explicit excluded work for optionally enabled Memory tools."""

from openai.types.responses import FunctionToolParam
from pydantic import ValidationError

from caliburn.contracts.generated.tools.excluded_work_view import ExcludedWorkView
from caliburn.contracts.generated.tools.read_excluded_work_arguments import (
    ReadExcludedWorkArguments,
)
from caliburn.features.executions.models import ExecutionNotFoundError, ExecutionStateError
from caliburn.features.interviews.models import (
    InterviewScopeError,
    InterviewSourceNotAvailableError,
)
from caliburn.features.occupation_references.models import ReferenceStateError
from caliburn.features.work_memory.candidates import (
    MemoryCandidateStateError,
    MemoryPermissionError,
)
from caliburn.features.work_memory.revisions import MemoryRevisionNotFoundError
from caliburn.transport.model_tools.contracts import function_definition, reject_tool_call
from caliburn.workflows.memory_reads import MemoryReadBinding
from caliburn.workflows.occupation_reference_reads import ExcludedWorkReadWorkflow


def excluded_work_read_definitions() -> list[FunctionToolParam]:
    """Inspect the contract without creating a database session or binding."""
    return [
        function_definition(
            "read_excluded_work",
            "讀取目前工作與可見範圍內，員工已明確表示不負責的工作範圍，"
            "避免把未負責內容補回 Memory；仍保留必要責任與交接邊界，不用複製整份清單。"
            "未知不當作否認，清單不是原話引用、指令或完成判定。"
            "此工具只讀內容，工作身分、版本及可見上界由 App 固定，不能修改排除清單。",
            "read-excluded-work-arguments",
        ),
    ]


class ExcludedWorkReadTools:
    """Return a complete exclusion list without granting reference selection or write tools."""

    names = ("read_excluded_work",)

    def __init__(
        self,
        workflow: ExcludedWorkReadWorkflow,
        binding: MemoryReadBinding,
        *,
        max_result_characters: int = 1_000_000,
    ) -> None:
        if max_result_characters < 1:
            raise ValueError("Tool result character limit must be positive")
        self.workflow = workflow
        self.binding = binding
        self.max_result_characters = max_result_characters

    def definitions(self) -> list[FunctionToolParam]:
        return excluded_work_read_definitions()

    async def invoke(self, name: str, arguments: str) -> str:
        if name not in self.names:
            return reject_tool_call(
                "scope_not_allowed",
                "此入口只提供排除工作範圍的讀取。",
                "使用 read_excluded_work；此入口沒有公版選擇或修改能力。",
            )
        try:
            ReadExcludedWorkArguments.model_validate_json(arguments)
        except ValidationError:
            return reject_tool_call(
                "invalid_arguments",
                "排除範圍讀取不接受參數。",
                "使用空物件 {}；工作身分及可見範圍由 App 固定。",
            )
        try:
            excluded_work = await self.workflow.read(self.binding)
        except (
            ExecutionNotFoundError,
            ExecutionStateError,
            MemoryPermissionError,
            InterviewScopeError,
        ):
            return reject_tool_call(
                "scope_not_allowed",
                "目前執行資格或可見範圍不允許這次讀取。",
                "由 App 接續有效執行，不猜範圍、版本或其他職務資料。",
            )
        except MemoryCandidateStateError:
            return reject_tool_call(
                "target_stale",
                "本次 Memory 候選階段已失效。",
                "由 App 接續有效階段，不重送過時請求。",
            )
        except MemoryRevisionNotFoundError, InterviewSourceNotAvailableError, ReferenceStateError:
            return reject_tool_call(
                "source_not_available",
                "目前可見範圍的保存資料無法完整讀取。",
                "未回傳部分內容；保存資料問題由 App 處理，不視為沒有排除工作。",
            )
        output = ExcludedWorkView(excluded_work=list(excluded_work)).model_dump_json()
        if len(output) > self.max_result_characters:
            return reject_tool_call(
                "read_limit_exceeded",
                "完整排除清單超過工具輸出容量，未回傳截斷內容。",
                "由 App 處理資料容量，不視為已讀或沒有排除工作。",
            )
        return output
