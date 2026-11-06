"""完整工具輸出或可採取行動的拒絕，不截斷保存效果。"""

import json

from langchain_core.tools import ToolException
from pydantic import ValidationError
from pydantic.v1 import ValidationError as ValidationErrorV1

from caliburn.bundles.memory.projections import ToolRejection
from caliburn.modules.memory.application.errors import MemoryConcurrencyError
from caliburn.modules.memory.domain.errors import (
    DuplicateMemoryTitleError,
    InvalidMemoryContentError,
    InvalidMemoryPhaseError,
    InvalidMemorySourceError,
    MemoryAnalysisConflictError,
    MemoryItemNotFoundError,
)
from caliburn.modules.model_references import (
    InvalidModelReferenceError,
    ModelReferenceError,
)
from caliburn.shared.domain.text_editing.errors import InvalidTextError, TextEditError

MODEL_REJECTIONS = (
    ToolRejection,
    MemoryConcurrencyError,
    DuplicateMemoryTitleError,
    InvalidMemoryContentError,
    InvalidMemoryPhaseError,
    InvalidMemorySourceError,
    MemoryAnalysisConflictError,
    MemoryItemNotFoundError,
    InvalidTextError,
    TextEditError,
    ModelReferenceError,
)


def encode(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def bounded_output(value: object, *, limit: int, writing: bool = False) -> str:
    output = encode(value)
    if len(output) > limit:
        if writing:
            raise ToolRejection(
                "write_result_limit_exceeded",
                "完整效果回傳超出容量，本次未改。",
                "縮小同次修改範圍。",
            )
        raise ToolRejection(
            "read_limit_exceeded",
            "完整結果超過容量，未回傳截斷內容。",
            "訪談可縮小選取範圍；導覽或單項仍超量時由 App 處理。",
        )
    return output


def _rejected(code: str, message: str, next_action: str) -> str:
    return encode(
        {
            "status": "rejected",
            "code": code,
            "message": message,
            "next_action": next_action,
        }
    )


def invalid_arguments(error: ValidationError | ValidationErrorV1) -> str:
    issues = (
        error.errors(include_input=False, include_url=False)
        if isinstance(error, ValidationError)
        else error.errors()
    )
    issue = issues[0]
    location = "參數"
    if path := issue["loc"]:
        location = (
            "<extra>"
            if len(path) == 1
            and issue["type"] in {"extra_forbidden", "value_error.extra"}
            else str(path[0])
        )
        # 只定位頂層欄位與緊接的陣列索引，不推斷 union 分支。
        for part in path[1:]:
            if not isinstance(part, int):
                break
            location += f"[{part}]"
    return _rejected(
        "invalid_arguments",
        f"{location} 格式不合法。",
        "依工具欄位格式修正；只傳宣告欄位，每個變更欄位只列一次。",
    )


def model_rejection(error: Exception) -> ToolException:
    if isinstance(error, ToolRejection):
        return ToolException(_rejected(error.code, str(error), error.next_action))
    if isinstance(error, ModelReferenceError):
        return ToolException(
            _rejected(
                "invalid_arguments"
                if isinstance(error, InvalidModelReferenceError)
                else "source_not_available",
                f"interview_references 的 {error.reference} 無法作為訪談引用。",
                "使用目前材料提供的 message_* ref；核對既有引用後再移除，"
                "勿猜號或傳 UUID。",
            )
        )
    if isinstance(error, TextEditError):
        locations = "、".join(
            f"{match.start_line}–{match.end_line}" for match in error.candidates[:3]
        )
        details = f"候選行：{locations}。" if locations else ""
        if error.hunk_number is not None:
            details = f"第 {error.hunk_number} 段。" + details
        return ToolException(
            _rejected(
                error.code,
                f"正文修改未採用。{error}。{details}",
                "核對目前正文及完整行，補足唯一定位的上下文或縮小修改範圍。",
            )
        )
    if isinstance(error, DuplicateMemoryTitleError):
        return ToolException(
            _rejected(
                "title_conflict",
                "本層已有相同標題。",
                "讀目前導覽，使用可區別工作的標題。",
            )
        )
    if isinstance(error, (InvalidMemoryContentError, InvalidTextError)):
        return ToolException(
            _rejected(
                "invalid_arguments",
                "文字含無法保存的字元或為空白。",
                "保留有效非空白正文並移除不合法字元。",
            )
        )
    if isinstance(error, InvalidMemorySourceError):
        return ToolException(
            _rejected(
                "source_not_available",
                "至少一個來源無效或超出目前範圍。",
                "核對導覽與固定訪談範圍。",
            )
        )
    if isinstance(error, MemoryItemNotFoundError):
        return ToolException(
            _rejected(
                "target_not_found",
                "目前可見範圍找不到目標。",
                "重讀對應導覽並選精確標題。",
            )
        )
    return ToolException(
        _rejected(
            "target_stale",
            "目前整理階段、寫入資格或版本已失效。",
            "請由 App 接續有效階段，勿重送過時修改。",
        )
    )
