"""Scoped JD model writes: prepare/save the bound intent before executing any effects."""

from collections.abc import Awaitable, Callable
from uuid import UUID

from openai.types.responses import FunctionToolParam
from pydantic import ValidationError

from caliburn.contracts.generated.tools.delete_jd_item_arguments import DeleteJdItemArguments
from caliburn.contracts.validation import parse_contract
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
from caliburn.features.job_description.compound_edits import CompoundJdEdit, JdCompoundEditResult
from caliburn.features.job_description.conditions import InvalidConditionChangeError
from caliburn.features.job_description.item_movement import InvalidItemMovementError
from caliburn.features.job_description.item_revision import InvalidItemRevisionError
from caliburn.features.job_description.model_references import JdModelReferences
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
from caliburn.transport.model_tools.jd_reference_fields import (
    InvalidJdArgumentsError,
    resolve_jd_arguments,
)
from caliburn.transport.model_tools.jd_write_checkpoint import PreparedJdWrite
from caliburn.transport.model_tools.jd_write_rendering import JdWriteResult, render_jd_write_result
from caliburn.transport.model_tools.jd_write_wire import parse_profile_write, parse_task_write
from caliburn.workflows.job_description.compound_writes import PreparedJdEdit
from caliburn.workflows.job_description.item_creation import JdItemCreationWorkflow
from caliburn.workflows.job_description.item_deletion import (
    JdItemDeletionWorkflow,
    PreparedItemDeletion,
)
from caliburn.workflows.job_description.item_movement import (
    JdItemMovementWorkflow,
    PreparedItemMovement,
)
from caliburn.workflows.job_description.item_revision import JdItemRevisionWorkflow
from caliburn.workflows.job_description.profile_writes import JdProfileWriteWorkflow
from caliburn.workflows.job_description.task_writes import JdTaskWriteWorkflow
from caliburn.workflows.work_memory.reads import PublishedMemoryRead

_INVALID_ARGUMENTS = (
    InvalidJdArgumentsError,
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


def _parse_arguments[T](parser: Callable[[str], T], arguments: str) -> T:
    # 只轉譯純 wire 解析，owner／renderer 的驗證錯誤必須外拋。
    try:
        return parser(arguments)
    except ValidationError:
        raise InvalidJdArgumentsError("Invalid JD write arguments") from None


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
            (
                "修改 JD 的基本資料、職務目的及各欄各自的直接來源。changes 只列本"
                "次要改的部分，編修時一併整理正文與引用，可只改來源。顧問實改的欄"
                "位同步更新 JD 核對基準，不新增待核對；Memory 來源版本仍由引用動"
                "作更新。其他 JD 項目用 revise_jd_item。整次修改全成或全拒。成功回短字串："
                "updated 表示候選已更新，aligned 表示只有指定引用的確認產生變化，"
                "unchanged 表示本次沒有改變；不附更新後全文或來源清單，也不表示其"
                "餘引用已核清。僅更新本輪候選。拒絕回 status=rejected、code、"
                "message 與 next_action，依提示處理可修正問題。"
            ),
            "revise-jd-profile-arguments",
        ),
        function_definition(
            "create_jd_task",
            (
                "新增一個任務，可同時建立成果、要求，連接既有知識／技能並加入任務"
                "依據。先利用已取得的 JD 資料判斷是否已有同項工作；資料不足時再局"
                "部讀取。已有任務改文字用 revise_jd_item，改歸屬用 move_jd_item；"
                "所需職責或能力定義尚不存在時，先用 create_jd_item 建立。任務及其"
                "明細、能力用途共用任務來源；共用能力定義另有自己的來源。整次建立"
                "全成或全拒。成功回 created · read_ref: 加上新任務定位，可直接用"
                "於後續工具；不回完整任務或明細定位。僅更新本輪候選。拒絕回 "
                "status=rejected、code、message 與 next_action，依提示處理可修正"
                "問題。"
            ),
            "create-jd-task-arguments",
        ),
        function_definition(
            "create_jd_item",
            (
                "新增一個職責、共用知識／技能、協作對象或共通條件。先利用已取得的"
                " JD 導覽及正文辨認是否已有適合項目，需要時再局部讀取；修改既有項"
                "目用 revise_jd_item。新職責不會自動接收既有任務，須用 "
                "move_jd_item 調整歸屬；新知識／技能只建立共用定義，須用 "
                "revise_jd_item 的 set_capability 連接既有任務，或由 "
                "create_jd_task 連接新任務。新任務用 create_jd_task；既有任務新增"
                "成果／要求用 revise_jd_item。項目及其來源一次全成或全拒。成功回 "
                "created · read_ref: 加上新項目定位，可直接填後續工具，不需只為取"
                "得相同定位而重讀。僅更新本輪候選。拒絕回 status=rejected、code、"
                "message 與 next_action，依提示處理可修正問題。"
            ),
            "create-jd-item-arguments",
        ),
        function_definition(
            "revise_jd_item",
            (
                "修改一個既有 JD 項目的文字、來源，或所選任務的成果、要求與知識／"
                "技能關聯。read_ref 選實際要改的項目；修改成果、要求或任務能力關"
                "聯時，外層仍選所屬任務。顧問編修時一併整理正文與引用，實改的支持"
                "內容同步更新 JD 核對基準，不新增待核對；Memory 來源版本仍由引用"
                "動作更新。共用知識／技能的定義修改須一併處理使用任務的影響；只增"
                "刪某任務的使用關係則選該任務並用 set_capability。基本資"
                "料與目的用 revise_jd_profile，新建共用項目用 create_jd_item；項"
                "目、明細排序及任務歸屬用 move_jd_item，任務內能力順序用本工具的 "
                "reorder_capability。changes 可只有來源動作，文字與來源也可合併提"
                "交，一次全成或全拒。成功回短字串：updated 表示候選已更新，"
                "aligned 表示只有指定引用的確認產生變化，unchanged 表示本次沒有改"
                "變；不附更新後全文或來源清單，也不表示其餘引用已核清。僅更新本輪"
                "候選。拒絕回 status=rejected、code、message 與 next_action，依提"
                "示處理可修正問題。"
            ),
            "revise-jd-item-arguments",
        ),
        function_definition(
            "delete_jd_item",
            (
                "從本輪 JD 候選刪除指定職責、任務、共用知識／技能、協作對象或共通"
                "條件。確認項目本身應移除時使用；只改文字用 revise_jd_item，重組"
                "任務歸屬用 move_jd_item。刪職責保留其任務並轉為未歸屬；刪任務不"
                "刪共用知識／技能。仍被任務使用的知識／技能會拒絕刪除，須先用 "
                "revise_jd_item 解除相關任務的連接。成果／要求須以所屬任務為目標"
                "，用 revise_jd_item 的 remove_detail 刪除。成功回 deleted；刪職"
                "責造成任務未歸屬時，另附保留任務數。僅更新本輪候選。拒絕回 "
                "status=rejected、code、message 與 next_action，依提示處理可修正"
                "問題。"
            ),
            "delete-jd-item-arguments",
        ),
        function_definition(
            "move_jd_item",
            (
                "調整既有 JD 項目的順序，或把任務移到其他職責／未歸屬；保留物件身"
                "分、任務明細、能力關係與既有來源。任務以外的項目只能在原集合內排"
                "序；需要新職責時先 create_jd_item，再用返回定位移入既有任務。只"
                "有任務確實更換歸屬時，才可把相關文字修訂放入 content_changes 與"
                "移動一次全成或全拒；純排序時填 []。一般文字、來源或能力關係修訂"
                "，以及任務內能力排序，使用 revise_jd_item。成功回 moved 或 "
                "unchanged；任務解除原職責時另附已轉未歸屬說明，不回全文。僅更新"
                "本輪候選。拒絕回 status=rejected、code、message 與 next_action，"
                "依提示處理可修正問題。"
            ),
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
        references: JdModelReferences,
        execute_edit: Callable[
            [ExecutionWriter, PreparedJdEdit[CompoundJdEdit]], Awaitable[JdCompoundEditResult]
        ],
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
        self.references = references
        self.execute_edit = execute_edit

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
            arguments = await resolve_jd_arguments(self.references, arguments)
            if name == "revise_jd_profile":
                changes, sources = _parse_arguments(parse_profile_write, arguments)
                return await self.profile.prepare(
                    self.binding, command_id=command_id, changes=changes, sources=sources
                )
            if name == "create_jd_item":
                return await self.creations.prepare(
                    self.binding,
                    command_id=command_id,
                    intent=_parse_arguments(parse_item_creation, arguments),
                )
            if name == "revise_jd_item":
                return await self.revisions.prepare(
                    self.binding,
                    command_id=command_id,
                    intent=_parse_arguments(parse_item_revision, arguments),
                )
            if name == "delete_jd_item":
                selected = _parse_arguments(
                    lambda value: parse_contract(DeleteJdItemArguments, value), arguments
                )
                return await self.deletions.prepare(
                    self.binding.scope, command_id=command_id, read_ref=selected.read_ref
                )
            if name == "move_jd_item":
                return await self.movements.prepare(
                    self.binding.scope,
                    command_id=command_id,
                    intent=_parse_arguments(parse_item_movement, arguments),
                )
            return await self.tasks.prepare(
                self.binding,
                command_id=command_id,
                intent=_parse_arguments(parse_task_write, arguments),
            )
        except _INVALID_ARGUMENTS:
            return _invalid_arguments()
        except CapabilityInUseError:
            return _in_use()
        except InterviewScopeError:
            return reject_tool_call(
                "scope_not_allowed",
                "引用的 interview_sequence 不在本輪可引用範圍，本次未改。",
                "若依據是本次員工輸入，使用本次 input 提供的訪談序號；"
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
        result: JdWriteResult
        try:
            if isinstance(prepared, PreparedItemDeletion):
                result = await self.deletions.execute(self.writer, prepared)
            elif isinstance(prepared, PreparedItemMovement):
                result = await self.movements.execute(self.writer, prepared)
            else:
                result = await self.execute_edit(self.writer, prepared)
        except _INVALID_ARGUMENTS:
            return _invalid_arguments()
        except CapabilityInUseError:
            return _in_use()
        return await render_jd_write_result(self.references, result)
