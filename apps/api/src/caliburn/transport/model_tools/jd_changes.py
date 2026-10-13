"""固定來源的按需比較；人工 net 由起始 context 完整提供。"""

from openai.types.responses import FunctionToolParam
from pydantic import ValidationError

from caliburn.features.executions.models import ExecutionNotFoundError, ExecutionStateError
from caliburn.features.interviews.models import (
    InterviewScopeError,
    InterviewSourceNotAvailableError,
)
from caliburn.features.job_description.candidates import CandidateStateError
from caliburn.features.job_description.model_references import JdModelReferences
from caliburn.features.job_description.navigation import (
    JdReadTargetNotFoundError,
)
from caliburn.features.work_memory.candidates import (
    MemoryCandidateStateError,
    MemoryPermissionError,
)
from caliburn.features.work_memory.revisions import MemoryRevisionNotFoundError
from caliburn.transport.jd_source_markdown import (
    project_jd_source_changes as project_jd_source_changes,
)
from caliburn.transport.model_tools.contracts import function_definition
from caliburn.transport.model_tools.jd_changes_wire import parse_jd_changes
from caliburn.transport.model_tools.jd_reference_fields import (
    InvalidJdArgumentsError,
    resolve_jd_arguments,
)
from caliburn.workflows.job_description.source_changes import (
    JdChangesWorkflow,
    UnsupportedJdSourceKindError,
)
from caliburn.workflows.work_memory.reads import PublishedMemoryRead


def jd_changes_definitions() -> list[FunctionToolParam]:
    """Definitions are independent of a Turn binding and tool handler construction."""
    return [
        function_definition(
            "read_jd_changes",
            (
                "需要查某筆 JD 既有 Memory 引用自固定舊版到本輪固定比較版發生什麼"
                "變化時使用。從 read_jd 局部結果取得該筆 citation_ref，以 "
                "query.kind=source 送入；App 決定同一來源身分及比較兩端，不可自行"
                "選版本或藉此讀任意舊全文。人工 JD 的完整最終差異由當輪 context "
                "提供，本工具不查人工改稿；不可變訪談不適用，歷史原話用 "
                "read_interview，本次輸入沿用已提供原文。\n成功直接回 Markdown「"
                "JD 來源差異」：比較說明指出固定舊來源與本輪版本；citation_ref 回"
                "顯引用定位；「歷史名稱」是原來源名稱；「可讀 target_title」是比"
                "較版的同一物件標題，若不存在則明示來源可用性，不能按同名替代。"
                "title、description、body 的 diff 分別表示標題、導覽描述與正文變"
                "化；新增／移除訪談引用序號表示來源引用集合的變化。工作理解的相關"
                "直接情境有變化時另列其名稱與差異；新增／移除直接情境引用不等於全"
                "域新建／刪除該情境。結果只列相關變化，未變正文不展開；可明示自身"
                "無變化、相關來源鏈無變化，或只有修訂更新而無淨文字差異。diff 是"
                "閱讀結果，不是編輯工具的輸入格式；空差異、已讀差異都不代表已核清"
                "支持關係。本工具不改 JD、不換來源、不確認引用，也不解除待核對。"
                "\n拒絕直接回文字「rejected: 原因代碼；處理提示」，不是 JSON，也"
                "不是空差異。引用定位不對時依提示取得目前 citation_ref；來源類型"
                "不支持時使用對應讀取工具。資格、保存資料或單筆差異容量問題交由 "
                "App 處理，不自行換版本或無限重送。"
            ),
            "read-jd-changes-arguments",
        )
    ]


class JdChangesTools:
    def __init__(
        self,
        reader: JdChangesWorkflow,
        binding: PublishedMemoryRead,
        *,
        references: JdModelReferences,
        max_result_characters: int = 1_000_000,
    ) -> None:
        if max_result_characters < 1:
            raise ValueError("Tool result character limit must be positive")
        self.reader = reader
        self.binding = binding
        self.references = references
        self.max_result_characters = max_result_characters

    @property
    def names(self) -> tuple[str, ...]:
        return ("read_jd_changes",)

    def definitions(self) -> list[FunctionToolParam]:
        return jd_changes_definitions()

    async def invoke(self, name: str, arguments: str) -> str:
        if name not in self.names:
            return "rejected: scope_not_allowed；使用 read_jd_changes。"
        try:
            resolved = await resolve_jd_arguments(self.references, arguments)
        except JdReadTargetNotFoundError:
            return "rejected: target_not_found；重讀 read_jd，原樣帶回 App 提供的定位。"
        except InvalidJdArgumentsError:
            return "rejected: invalid_arguments；選 source 的 citation_ref，不帶版本。"
        try:
            query = parse_jd_changes(resolved)
        except ValidationError, ValueError:
            return "rejected: invalid_arguments；選 source 的 citation_ref，不帶版本。"
        return await read_jd_source_changes(
            self.reader,
            self.binding,
            query.citation_ref,
            self.references,
            max_result_characters=self.max_result_characters,
        )


async def read_jd_source_changes(
    reader: JdChangesWorkflow,
    binding: PublishedMemoryRead,
    citation_ref: str,
    references: JdModelReferences,
    *,
    max_result_characters: int = 1_000_000,
) -> str:
    """來源查讀錯誤與內部失敗分開；不以空差異掩蓋失敗。"""
    if max_result_characters < 1:
        raise ValueError("Tool result character limit must be positive")
    try:
        result = await reader.read_source(binding, citation_ref)
    except UnsupportedJdSourceKindError as error:
        return f"rejected: source_kind_not_supported；{error}"
    except ExecutionNotFoundError, ExecutionStateError, MemoryPermissionError, InterviewScopeError:
        return (
            "rejected: scope_not_allowed；目前執行或固定來源範圍不允許讀取；由 App 恢復合法範圍。"
        )
    except CandidateStateError:
        return "rejected: target_stale；本 Turn 已無有效 JD 候選；不可重送舊定位。"
    except JdReadTargetNotFoundError:
        return (
            "rejected: target_not_found；目前 JD 找不到引用；用 read_jd 局部讀取取得 citation_ref。"
        )
    except MemoryRevisionNotFoundError, MemoryCandidateStateError, InterviewSourceNotAvailableError:
        return (
            "rejected: source_not_available；固定來源或比較端點無法完整取回，未回傳假空差異；"
            "請由 App 核對保存資料，不推論來源已刪除。"
        )
    canonical = f"citation_{result.reference.citation_id.hex}"
    assigned = await references.assign((canonical,))
    output = project_jd_source_changes(result, citation_ref=assigned[canonical])
    if len(output) > max_result_characters:
        return (
            "rejected: read_limit_exceeded；完整相關差異超過容量，未截斷或視為已讀；"
            "單筆來源已是最小合法範圍，交 App 處理。"
        )
    return output
