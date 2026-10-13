"""Memory writes split preflight from effects so Runtime can save the exact command first."""

from uuid import UUID

from openai.types.responses import FunctionToolParam
from pydantic import ValidationError

from caliburn.adapters.body_matching import BodyEditError
from caliburn.features.executions.models import (
    ExecutionNotFoundError,
    ExecutionStateError,
    ExecutionWriter,
)
from caliburn.features.interviews.models import (
    InterviewScopeError,
    InterviewSourceNotAvailableError,
    InvalidInterviewSelectionError,
)
from caliburn.features.work_memory.candidates import (
    MemoryCandidateStateError,
    MemoryPermissionError,
)
from caliburn.features.work_memory.models import (
    InvalidMemoryChangeError,
    MemoryReferenceNotFoundError,
    MemoryTargetNotFoundError,
    MemoryTitleConflictError,
)
from caliburn.features.work_memory.revisions import MemoryLayer, MemoryRevisionNotFoundError
from caliburn.transport.model_tools.contracts import function_definition, reject_tool_call
from caliburn.transport.model_tools.memory_write_checkpoint import PreparedMemoryToolCall
from caliburn.transport.model_tools.memory_write_wire import (
    parse_write_intent,
    render_write_preview,
)
from caliburn.workflows.work_memory.candidates import MemoryCandidateWorkflow
from caliburn.workflows.work_memory.reads import CandidateMemoryRead
from caliburn.workflows.work_memory.write_preparation import MemoryWritePreparation


def memory_write_names(layer: MemoryLayer) -> tuple[str, ...]:
    return tuple(f"{action}_{layer.value}" for action in ("create", "update", "delete"))


def memory_write_definitions(layer: MemoryLayer) -> list[FunctionToolParam]:
    """Expose the canonical role contracts before a runtime candidate binding exists."""
    subject = "工作情境" if layer == MemoryLayer.WORK_SITUATION else "工作理解"
    references = (
        "interview_references 的正式訪談序號"
        if layer == MemoryLayer.WORK_SITUATION
        else "work_situation_references 的目前情境標題"
    )
    content_guidance = (
        "完整承接相關有效片段與已知背景、規則／方法／工具、精確數值期限及更正；尚無任務不丟已知內容。"
        if layer == MemoryLayer.WORK_SITUATION
        else "提煉可用的工作理解，保留必要適用範圍、責任、規則與精確數值期限，"
        "不按每件情境強造一項。"
    )
    descriptions = (
        f"建立本批一項{subject}候選。提供完整 title、description、Markdown body"
        f" 與{references}；"
        "來源須實際支持本項內容；可無來源，但不能猜事實。來源不放正文。"
        "同層標題不得重複，成功不代表發布。" + content_guidance,
        f"修訂本批一項{subject}候選。target_title 精確選修改前物件；changes 只列要改的欄位，"
        "每欄一次。title／description 給完整新值；body 給真實上下文的 V4A diff。"
        f"{references}依修改後內容的實際支持關係按需 add／remove，未列保留。"
        "局部更正保留未受影響的有效內容。" + content_guidance + "全欄、全 hunk 通過才採用；"
        "歧義拒絕，依回饋核對目前正文／補上下文，不原樣盲重送。"
        "成功回傳的展示 diff 描述實際前後差異，不是下一次可直接提交的 V4A。",
        f"刪除本批一項{subject}候選，精確指定 target_title；不刪歷史快照或發布新版。"
        + (
            "同時解除指向它的候選理解關係，不刪理解。"
            if layer == MemoryLayer.WORK_SITUATION
            else "同時移除它自己的關係，不刪上游情境。"
        ),
    )
    return [
        function_definition(
            name,
            description,
            "delete-memory-object-arguments"
            if name.startswith("delete_")
            else name.replace("_", "-") + "-arguments",
        )
        for name, description in zip(memory_write_names(layer), descriptions, strict=True)
    ]


class MemoryWriteTools:
    def __init__(
        self,
        preparation: MemoryWritePreparation,
        candidates: MemoryCandidateWorkflow,
        binding: CandidateMemoryRead,
        writer: ExecutionWriter,
        *,
        max_result_characters: int = 1_000_000,
    ) -> None:
        if writer.scope != binding.scope:
            raise MemoryPermissionError("The writer and tool must share one execution scope")
        if max_result_characters < 1:
            raise ValueError("Tool result character limit must be positive")
        self.preparation = preparation
        self.candidates = candidates
        self.binding = binding
        self.writer = writer
        self.max_result_characters = max_result_characters

    @property
    def names(self) -> tuple[str, ...]:
        return memory_write_names(self.binding.stage.phase)

    def definitions(self) -> list[FunctionToolParam]:
        return memory_write_definitions(self.binding.stage.phase)

    async def prepare(
        self, name: str, arguments: str, *, command_id: UUID
    ) -> PreparedMemoryToolCall | str:
        if name not in self.names:
            return reject_tool_call(
                "scope_not_allowed",
                "本角色沒有這項修改能力。",
                "使用本角色提供的工具，不更改 scope。",
            )
        try:
            intent = parse_write_intent(name, arguments)
        except ValidationError, InvalidMemoryChangeError:
            return _invalid_arguments()
        try:
            prepared = await self.preparation.prepare(
                self.binding, command_id=command_id, layer=self.binding.stage.phase, intent=intent
            )
        except MemoryTitleConflictError:
            return reject_tool_call(
                "title_conflict",
                "本層已有其他物件使用這個標題，本次未改。",
                "讀目前導覽，使用能區別工作的標題。",
            )
        except MemoryReferenceNotFoundError:
            return reject_tool_call(
                "reference_not_found",
                "欲移除的來源不是目前引用，本次未改。",
                "讀目標目前來源，選現行序號或情境標題；不要用舊名稱猜身分。",
            )
        except BodyEditError as error:
            return _patch_rejection(error)
        except InvalidMemoryChangeError, InvalidInterviewSelectionError:
            return _invalid_arguments()
        except (
            ExecutionNotFoundError,
            ExecutionStateError,
            MemoryPermissionError,
            InterviewScopeError,
        ):
            return reject_tool_call(
                "scope_not_allowed",
                "本工作或來源範圍不允許此次修改，本次未改。",
                "只使用本角色與固定範圍的來源；執行資格由 App 處理。",
            )
        except MemoryCandidateStateError:
            return reject_tool_call(
                "target_stale",
                "候選階段已失效，本次未改。",
                "由 App 接續有效工作，不重送過時操作。",
            )
        except MemoryTargetNotFoundError:
            return reject_tool_call(
                "target_not_found",
                "目前可見範圍沒有這個精確標題，本次未改。",
                "讀目前導覽，重新選擇目標或來源，不猜歷史名稱。",
            )
        except MemoryRevisionNotFoundError, InterviewSourceNotAvailableError:
            return reject_tool_call(
                "source_not_available",
                "必要的來源無法完整讀取，本次未改。",
                "核對選取；保存問題由 App 處理。",
            )
        # Result validation failures are programming errors, not model arguments errors.
        output = render_write_preview(prepared.preview)
        if len(output) > self.max_result_characters:
            return reject_tool_call(
                "write_result_limit_exceeded",
                "完整效果回傳超過容量，本次未改。",
                "縮小同次修改範圍；不能截斷效果或先保存再宣稱拒絕。",
            )
        return PreparedMemoryToolCall(prepared.command, output)

    async def execute(self, prepared: PreparedMemoryToolCall) -> str:
        """Save prepared first. Uncertain commit/errors propagate for Runtime reconciliation."""
        command = prepared.command
        if (command.position.stage_id, command.layer) != (
            self.binding.stage.stage_id,
            self.binding.stage.phase,
        ):
            raise MemoryPermissionError("The prepared command belongs to a different role stage")
        await self.candidates.edit(self.writer, command)
        # Do not reparse title, recompute output or apply today's smaller output cap on replay.
        return prepared.success_output


def _invalid_arguments() -> str:
    return reject_tool_call(
        "invalid_arguments",
        "欄位、型別或變更集合不合法，本次未改。",
        "每欄只列一次，文字非空白；引用增刪按需且不可同時選同一來源。",
    )


def _patch_rejection(error: BodyEditError) -> str:
    message = str(error)
    if error.hunk_number is not None:
        message = f"Hunk {error.hunk_number}: {message}"
    for candidate in error.candidates:
        message += f"\n候選行 {candidate.start_line}–{candidate.end_line}:\n{candidate.excerpt}"
    guidance = {
        "invalid_patch": (
            "語法不合法時，依最小合法替換範例修正格式：\n@@\n-原有完整行\n+修改後完整行\n"
            "已有目前正文不必為格式重讀。若 message 指明修改結果為空白，保留有效正文；"
            "確需移除整個物件時用既有 delete 工具。"
        ),
        "patch_context_not_found": (
            "先核對已持有的目前完整 body 與來源行；不足或版本不確定時重讀。"
            "使用實際完整來源行及必要上下文，以真正換行為界，不把同一行拆成句子替換。"
        ),
        "ambiguous_patch_context": "依既有候選片段補足能唯一定位的真實上下文，不自動選取匹配。",
        "patch_limit_exceeded": "縮小修改範圍，依既有內容限制修正。",
    }
    return reject_tool_call(
        error.code,
        message + "\n本次所有欄位均未改。",
        guidance[error.code],
    )
