"""Scoped JD model writes: prepare/save the bound intent before executing any effects."""

from uuid import UUID

from openai.types.responses import FunctionToolParam
from pydantic import ValidationError

from caliburn.contracts.generated.tools.delete_jd_item_arguments import DeleteJdItemArguments
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
from caliburn.features.job_description.areas import InvalidAreaChangeError
from caliburn.features.job_description.candidates import CandidateStateError
from caliburn.features.job_description.capabilities import (
    CapabilityInUseError,
    InvalidCapabilityChangeError,
)
from caliburn.features.job_description.collaborators import InvalidCollaboratorChangeError
from caliburn.features.job_description.conditions import InvalidConditionChangeError
from caliburn.features.job_description.models import InvalidProfileChangeError
from caliburn.features.job_description.navigation import JdReadTargetNotFoundError
from caliburn.features.job_description.sources import InvalidJdSourceError
from caliburn.features.job_description.tasks import InvalidTaskChangeError
from caliburn.features.work_memory.models import InvalidMemoryChangeError, MemoryTargetNotFoundError
from caliburn.features.work_memory.revisions import MemoryRevisionNotFoundError
from caliburn.transport.model_tools.contracts import function_definition, reject_tool_call
from caliburn.transport.model_tools.jd_item_creation_wire import parse_item_creation
from caliburn.transport.model_tools.jd_item_movement_wire import parse_item_movement
from caliburn.transport.model_tools.jd_item_revision_wire import parse_item_revision
from caliburn.transport.model_tools.jd_write_wire import parse_profile_write, parse_task_write
from caliburn.workflows.jd_item_creation import JdItemCreationWorkflow, PreparedItemCreation
from caliburn.workflows.jd_item_deletion import JdItemDeletionWorkflow, PreparedItemDeletion
from caliburn.workflows.jd_item_movement import (
    InvalidItemMovementError,
    JdItemMovementWorkflow,
    PreparedItemMovement,
)
from caliburn.workflows.jd_item_revision import (
    InvalidItemRevisionError,
    JdItemRevisionWorkflow,
    PreparedItemRevision,
)
from caliburn.workflows.jd_profile_writes import JdProfileWriteWorkflow, PreparedProfileWrite
from caliburn.workflows.jd_task_writes import JdTaskWriteWorkflow, PreparedTaskWrite
from caliburn.workflows.memory_reads import PublishedMemoryRead

type PreparedJdWrite = (
    PreparedProfileWrite
    | PreparedTaskWrite
    | PreparedItemCreation
    | PreparedItemRevision
    | PreparedItemDeletion
    | PreparedItemMovement
)

_INVALID_ARGUMENTS = (
    ValidationError,
    InvalidProfileChangeError,
    InvalidTaskChangeError,
    InvalidJdSourceError,
    InvalidInterviewSelectionError,
    InvalidMemoryChangeError,
    InvalidAreaChangeError,
    InvalidCapabilityChangeError,
    InvalidCollaboratorChangeError,
    InvalidConditionChangeError,
    InvalidItemRevisionError,
    InvalidItemMovementError,
)


def _invalid_arguments() -> str:
    return reject_tool_call(
        "invalid_arguments",
        "欄位、內容或來源選取不合法，本次未改。",
        "依工具格式提交；各欄只改一次，來源選目前可見內容，不猜來源或引用代號。",
    )


def _in_use() -> str:
    return reject_tool_call(
        "item_in_use",
        "此知識或技能仍被任務使用，本次未刪除。",
        "先讀取相關任務，確認適合解除關聯後，再刪除共用定義。",
    )


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
        function_definition(
            "create_jd_item",
            "建立一個職責、共用知識／技能、協作對象或全職務條件。先按需 read_jd 避免重複。"
            "只寫已釐清事實並附直接支持它的 supporting_sources；未知不猜。"
            "建立任務另用 create_jd_task。成功僅更新候選，回傳新 read_ref。",
            "create-jd-item-arguments",
        ),
        function_definition(
            "revise_jd_item",
            "以 read_jd 的 read_ref 修訂一項 JD：短文用完整新值；任務可增刪修成果／要求、"
            "連接既有 K/S 與調整來源。changes 按需列出；不同直接內容各用真正依據。"
            "核對目前內容與新版來源後才 confirm_reference_alignment；讀過不等於核對。"
            "一次全成或全拒，只修改候選。任務內 K/S 引用排序用本工具的 reorder_capability 動作；"
            "項目／明細排序及任務移動用 move_jd_item。",
            "revise-jd-item-arguments",
        ),
        function_definition(
            "delete_jd_item",
            "刪除 read_ref 指向的候選 JD 項目。刪職責保留任務並轉為未歸屬；"
            "刪任務不刪共用知識／技能；仍被任務使用的 K/S 必須先解除關聯。"
            "成果／要求請透過 revise_jd_item 修改所屬任務。不提交整輪。",
            "delete-jd-item-arguments",
        ),
        function_definition(
            "move_jd_item",
            "移動或排序既有候選項目；read_ref 只選 read_jd 提供的定位。"
            "任務可移到既有職責或未歸屬；其他項目只在原集合排序。"
            "first/last 不需鄰居；before/after 選同目的集合鄰居。"
            "content_changes 只含此次移動必要的相關文字修訂，與結構一次全成或全拒。"
            "保留物件身分與來源，不提交整輪。",
            "move-jd-item-arguments",
        ),
    ]


class JdWriteTools:
    def __init__(
        self,
        profile: JdProfileWriteWorkflow,
        tasks: JdTaskWriteWorkflow,
        binding: PublishedMemoryRead,
        writer: ExecutionWriter,
        *,
        creations: JdItemCreationWorkflow,
        revisions: JdItemRevisionWorkflow,
        deletions: JdItemDeletionWorkflow,
        movements: JdItemMovementWorkflow,
    ) -> None:
        if writer.scope != binding.scope:
            raise ExecutionStateError(
                "The JD tool writer must own the same Turn as its source binding"
            )
        self.profile = profile
        self.tasks = tasks
        self.binding = binding
        self.writer = writer
        self.creations = creations
        self.revisions = revisions
        self.deletions = deletions
        self.movements = movements

    @property
    def names(self) -> tuple[str, ...]:
        return (
            "revise_jd_profile",
            "create_jd_task",
            "create_jd_item",
            "revise_jd_item",
            "delete_jd_item",
            "move_jd_item",
        )

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
            if name == "create_jd_item":
                return await self.creations.prepare(
                    self.binding, command_id=command_id, intent=parse_item_creation(arguments)
                )
            if name == "revise_jd_item":
                return await self.revisions.prepare(
                    self.binding, command_id=command_id, intent=parse_item_revision(arguments)
                )
            if name == "delete_jd_item":
                selected = DeleteJdItemArguments.model_validate_json(arguments)
                return await self.deletions.prepare(
                    self.binding, command_id=command_id, read_ref=selected.read_ref
                )
            if name == "move_jd_item":
                return await self.movements.prepare(
                    self.binding, command_id=command_id, intent=parse_item_movement(arguments)
                )
            return await self.tasks.prepare(
                self.binding, command_id=command_id, intent=parse_task_write(arguments)
            )
        except _INVALID_ARGUMENTS:
            return _invalid_arguments()
        except CapabilityInUseError:
            return _in_use()
        except InterviewScopeError:
            return reject_tool_call(
                "scope_not_allowed",
                "引用的 interview_sequence 超出本輪正式訪談上界，本次未改。",
                "若依據是本次員工輸入，改用 current_input，不預測其序號；"
                "若依據來自歷史，先用 read_interview 核對支持內容的正式序號再提交。"
                "不要更改範圍、刪掉必要來源或改引不相關訊息。",
            )
        except ExecutionNotFoundError, ExecutionStateError:
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
        try:
            if isinstance(prepared, PreparedProfileWrite):
                return await self.profile.execute(self.writer, prepared)
            if isinstance(prepared, PreparedItemCreation):
                return await self.creations.execute(self.writer, prepared)
            if isinstance(prepared, PreparedItemRevision):
                return await self.revisions.execute(self.writer, prepared)
            if isinstance(prepared, PreparedItemDeletion):
                return await self.deletions.execute(self.writer, prepared)
            if isinstance(prepared, PreparedItemMovement):
                return await self.movements.execute(self.writer, prepared)
            return await self.tasks.execute(self.writer, prepared)
        except _INVALID_ARGUMENTS:
            return _invalid_arguments()
        except CapabilityInUseError:
            return _in_use()
