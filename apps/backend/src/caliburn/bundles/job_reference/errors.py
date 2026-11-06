"""保留模型可採取行動的公版拒絕；未知程式錯誤仍向外傳遞。"""

import json
from collections.abc import Iterator
from contextlib import contextmanager

from langchain_core.tools import ToolException
from pydantic import ValidationError
from pydantic.v1 import ValidationError as ValidationErrorV1

from caliburn.modules.model_references.contracts import ModelReferenceError
from caliburn.modules.occupation_reference.application.errors import (
    ReferenceIndexError,
    ReferenceNotFoundError,
    ReferenceProviderError,
    ReferenceQueryError,
    ReferenceUnavailableError,
)


def rejection(code: str, message: str, next_action: str) -> str:
    return json.dumps(
        {
            "status": "rejected",
            "code": code,
            "message": message,
            "next_action": next_action,
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def invalid_search_arguments(error: ValidationError | ValidationErrorV1) -> str:
    return rejection(
        "invalid_arguments",
        "query 或搜尋欄位不合法，本次未執行搜尋。",
        "只填非空 query，最多 12,000 字元；使用本人已確認的主要工作，不填其他參數。",
    )


def invalid_read_arguments(error: ValidationError | ValidationErrorV1) -> str:
    return rejection(
        "invalid_arguments",
        "reference_id 或 task_id 不合法，本次未讀取公版。",
        "原樣帶回已提供的 occupation_ 公版短碼；task_id 必填，"
        "null 讀目錄，任務定位讀細節。",
    )


@contextmanager
def reference_errors() -> Iterator[None]:
    try:
        yield
    except ModelReferenceError as error:
        raise ToolException(
            rejection(
                "invalid_reference",
                "公版短碼無效或不屬於目前工作區。",
                "核對已提供的 occupation_ 公版短碼；找不到時重新搜尋，"
                "不猜造或改用 UUID。",
            )
        ) from error
    except ReferenceNotFoundError as error:
        raise ToolException(
            rejection(
                "reference_not_found",
                "指定公版或任務的固定來源定位不存在。",
                "核對工具提供的定位，原樣帶回；來源不可用交 App 處理，不代換同名新版。",
            )
        ) from error
    except ReferenceIndexError as error:
        raise ToolException(
            rejection(
                "reference_index_incompatible",
                "公版索引未就緒或與目前服務不相容。",
                "由 App 核對索引及模型版本；不改用同名來源或把故障當空候選。",
            )
        ) from error
    except ReferenceQueryError as error:
        raise ToolException(
            rejection(
                "reference_query_invalid",
                "公版服務拒絕本次查詢。",
                "核對 query 的非空、長度與服務限制，保留本人已確認的主要工作脈絡。",
            )
        ) from error
    except ReferenceProviderError as error:
        raise ToolException(
            rejection(
                "reference_provider_invalid_response",
                "公版服務的上游結果不符合契約。",
                "由 App 核對上游資料；本次沒有可用完整結果，不視為沒有相關工作。",
            )
        ) from error
    except ReferenceUnavailableError as error:
        raise ToolException(
            rejection(
                "reference_service_unavailable",
                "公版服務目前不可用，未取得完整結果。",
                "由 App 處理服務連線；不視為沒有相關工作。",
            )
        ) from error


def encode_result(value: object, *, max_characters: int) -> str:
    result = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if len(result) > max_characters:
        raise ToolException(
            rejection(
                "read_limit_exceeded",
                "完整公版資料超過工具輸出容量，未回傳截斷內容。",
                "資料容量由 App 處理，不視為已讀或沒有相關任務。",
            )
        )
    return result
