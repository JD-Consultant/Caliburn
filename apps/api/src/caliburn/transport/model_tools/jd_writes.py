"""Scoped JD model writes: prepare/save the bound intent before executing any effects."""

from uuid import UUID

from openai.types.responses import FunctionToolParam
from pydantic import ValidationError

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
from caliburn.features.job_description.candidates import CandidateStateError
from caliburn.features.job_description.models import InvalidProfileChangeError
from caliburn.features.job_description.navigation import JdReadTargetNotFoundError
from caliburn.features.job_description.sources import InvalidJdSourceError
from caliburn.features.job_description.tasks import InvalidTaskChangeError
from caliburn.features.work_memory.models import InvalidMemoryChangeError, MemoryTargetNotFoundError
from caliburn.features.work_memory.revisions import MemoryRevisionNotFoundError
from caliburn.transport.model_tools.contracts import function_definition, reject_tool_call
from caliburn.transport.model_tools.jd_write_wire import parse_profile_write, parse_task_write
from caliburn.workflows.jd_profile_writes import JdProfileWriteWorkflow, PreparedProfileWrite
from caliburn.workflows.jd_task_writes import JdTaskWriteWorkflow, PreparedTaskWrite
from caliburn.workflows.memory_reads import PublishedMemoryRead

type PreparedJdWrite = PreparedProfileWrite | PreparedTaskWrite


def jd_write_definitions() -> list[FunctionToolParam]:
    """Describe existing JD writes before a Turn's binding and writer are available."""
    return [
        function_definition(
            "revise_jd_profile",
            "修訂目前 JD 候選的職務名稱、單位、匯報關係或目的；changes 只列要改的欄位。"
            "資訊足夠且已核對才寫；不猜事實。set_field 填完整新值，clear_field 明確清空。"
            "來源可選本次 current_input、正式訪談序號或本輪 Memory 的 target_title。"
            "既存來源改版或 JD 改文後，重評仍支持目前文字才 confirm_reference_alignment；"
            "add_source 不會刷新舊引用。一次全成或全拒；成功只代表候選更新，不是整輪提交。",
            "revise-jd-profile-arguments",
        ),
        function_definition(
            "create_jd_task",
            "資訊已足夠時，在既有職責或未歸屬位置一次建立任務、已知成果／要求和已有 K/S 關聯。"
            "parent_read_ref 與 capability_read_ref 只使用 read_jd 提供的定位。"
            "task、每筆成果／要求、每筆能力關係各附真正支持它的 supporting_sources；"
            "不要套用父項來源。"
            "未知不編造，未有內容用空集合；先 read_jd 查看相關內容，避免重複建立任務。"
            "一次全成或全拒；成功返回新 read_ref，僅修改候選，不提交整輪。",
            "create-jd-task-arguments",
        ),
    ]


class JdWriteTools:
    def __init__(
        self,
        profile: JdProfileWriteWorkflow,
        tasks: JdTaskWriteWorkflow,
        binding: PublishedMemoryRead,
        writer: ExecutionWriter,
    ) -> None:
        if writer.scope != binding.scope:
            raise ExecutionStateError(
                "The JD tool writer must own the same Turn as its source binding"
            )
        self.profile = profile
        self.tasks = tasks
        self.binding = binding
        self.writer = writer

    @property
    def names(self) -> tuple[str, ...]:
        return ("revise_jd_profile", "create_jd_task")

    def definitions(self) -> list[FunctionToolParam]:
        return jd_write_definitions()

    async def prepare(self, name: str, arguments: str, command_id: UUID) -> PreparedJdWrite | str:
        if name not in self.names:
            return reject_tool_call(
                "scope_not_allowed", "本角色沒有這項 JD 修改能力。", "使用已提供的具名工具。"
            )
        try:
            if name == "revise_jd_profile":
                changes, sources = parse_profile_write(arguments)
                return await self.profile.prepare(
                    self.binding, command_id=command_id, changes=changes, sources=sources
                )
            return await self.tasks.prepare(
                self.binding, command_id=command_id, intent=parse_task_write(arguments)
            )
        except (
            ValidationError,
            InvalidProfileChangeError,
            InvalidTaskChangeError,
            InvalidJdSourceError,
            InvalidInterviewSelectionError,
            InvalidMemoryChangeError,
        ):
            return reject_tool_call(
                "invalid_arguments",
                "欄位、內容或來源選取不合法，本次未改。",
                "依工具格式提交；各欄只改一次，來源選目前可見內容，不猜來源或引用代號。",
            )
        except ExecutionNotFoundError, ExecutionStateError, InterviewScopeError:
            return reject_tool_call(
                "scope_not_allowed",
                "本輪資格或固定來源範圍不允許此次修改。",
                "由 App 處理執行資格；不要自行指定版本或超出訪談範圍。",
            )
        except CandidateStateError:
            return reject_tool_call(
                "target_stale", "本輪候選位置已失效，本次未改。", "由 App 接續正確工作位置。"
            )
        except JdReadTargetNotFoundError, MemoryTargetNotFoundError:
            return reject_tool_call(
                "target_not_found",
                "目前可見範圍沒有這個目標，本次未改。",
                "重新讀取相應 JD／Memory 導覽，選擇 App 提供的定位。",
            )
        except MemoryRevisionNotFoundError, InterviewSourceNotAvailableError:
            return reject_tool_call(
                "source_not_available",
                "必要來源無法完整取得，本次未改。",
                "確認來源選取；不要猜內容、假裝核對或引用未完成訪談。",
            )

    async def execute(self, prepared: PreparedJdWrite) -> str:
        # Infrastructure/commit uncertainty propagates to the shared Runtime, not to the model.
        if isinstance(prepared, PreparedProfileWrite):
            return await self.profile.execute(self.writer, prepared)
        return await self.tasks.execute(self.writer, prepared)
