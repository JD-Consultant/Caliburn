"""Read saved summary sources through the existing conversation source owner.

The page offset only projects an already resolved immutable SourceExcerpt. It is
not a new source locator, persisted state, or an offset accepted by the owner.
LangChain's public ToolRuntime is injected by ToolNode, hidden from model input:
https://docs.langchain.com/oss/python/langchain/tools#access-context
"""
from typing import Literal
from uuid import UUID
from caliburn_memory.sources import InvalidSourceReference

from langchain.tools import ToolRuntime, tool
from langchain_core.tools import BaseTool, ToolException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .conversation_sources import ConversationSourceError, SourceExcerpt
from .memory_context import MemoryReadError, memory_session


SOURCE_PAGE_CHARS = 3000
_INPUT_ERROR = "invalid_input: 使用已取得的reference、非負offset及source或context；續頁沿用next_offset。"
_REF_ERROR = "invalid_ref: 來源或詳記定位無效；請複製App已提供的原引用，不猜測或重新編碼。"
_MISSING_SUMMARY = "summary_missing: 此文件沒有這份詳記；請先讀既有Memory連結，不猜路徑。"


class _ReadConversationInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    reference: str = Field(min_length=1, max_length=4096,
        description="已讀的/interviews/<id>/summary.md，或App提供的完整conversation來源；原樣複製。")
    offset: int = Field(default=0, ge=0, le=2**63 - 1,
        description="首次0；續頁只使用此reference及part上頁回傳的next_offset，不自行計算。")
    part: Literal["source", "context"] = Field(default="source",
        description="source讀原始輸入；context只用於summary路徑，讀另外保存的前置脈絡。")


def source_page(excerpt: SourceExcerpt, offset: int = 0) -> dict:
    """Bound public text without changing IDs, whitespace, CRLF, or references.

    Offsets count Python Unicode characters over the original message sequence,
    with no inserted separator. A long message may span pages; text_offset is
    its original per-message position. The source owner, not this projection,
    validates existence and scope before this helper is called.
    """
    total = sum(len(message.text) for message in excerpt.messages)
    if type(offset) is not int or offset < 0 or offset > min(total, 2**63 - 1):
        raise ToolException(_INPUT_ERROR)
    end = min(offset + SOURCE_PAGE_CHARS, total)
    position = 0
    segments = []
    for message in excerpt.messages:
        start = max(offset - position, 0)
        stop = min(end - position, len(message.text))
        if start < stop:
            segments.append({"message_id": message.message_id, "role": message.role,
                             "text": message.text[start:stop], "text_offset": start})
        position += len(message.text)
        if position >= end:
            break
    return {"reference": excerpt.source_ref, "segments": segments,
            "next_offset": end if end < total else None}


def _source_error(error):
    if error.code == "invalid_ref":
        raise ToolException(_REF_ERROR) from None
    raise ConversationSourceError("source_not_available") from None


def _window(artifacts, reference):
    # Validate model syntax before any Store read; the core owns header parsing.
    try:
        _, kind, batch, name = reference.split("/")
        if kind != "interviews" or name != "summary.md" or str(UUID(batch)) != batch:
            raise ValueError()
    except ValueError:
        raise ToolException(_REF_ERROR) from None
    try:
        return artifacts.source_window(reference)
    except InvalidSourceReference:
        raise ToolException(_REF_ERROR) from None
    except ConversationSourceError as error:
        _source_error(error)
    except ValueError as error:
        # The adopted core has no typed artifact error. Match only its three
        # known source-window outcomes; unknown ValueError/Store failures abort.
        # Its StoreBackend.download_files does not catch Store I/O exceptions.
        if type(error) is ValueError and str(error) == f"Artifact unavailable: {reference}":
            raise ToolException(_MISSING_SUMMARY) from None
        if type(error) is ValueError and str(error) in (
            "Expected a runtime interview summary address",
            "Unambiguous runtime source header unavailable; read the historical artifact, but do not guess its source",
        ):
            raise ToolException(_REF_ERROR) from None
        raise MemoryReadError() from None
    except Exception:
        raise MemoryReadError() from None


def build_conversation_read_tool() -> BaseTool:
    # Native ToolNode injects runtime before BaseTool input validation. The
    # public JSON-schema path keeps that injected object outside strict model
    # arguments; the same Pydantic definition validates only model arguments.
    @tool(args_schema=_ReadConversationInput.model_json_schema())
    def read_conversation(runtime: ToolRuntime, **arguments) -> dict:
        """按需核對已取得詳記的固定原話，不搜尋全部歷史，也不修改Memory。

        reference可用已讀summary路徑，由App解析正式來源；也可原樣使用App提供的conversation引用。
        part=context只讀summary另外保存的前置脈絡；沒有另存時會明確說明，不代表沒有歷史。
        每頁最多3000公開文字字元，保留訊息身分及原始換行；沿next_offset續讀，不能把片段當全部原話。
        segments的assistant只是AI上下文，不等於員工確認；不回傳thinking、工具或私有模型內容。
        """
        session = memory_session(runtime)
        try:
            parsed = _ReadConversationInput.model_validate(arguments)
        except ValidationError:
            raise ToolException(_INPUT_ERROR) from None
        reference, offset, part = parsed.reference, parsed.offset, parsed.part
        metadata = {}
        if reference.startswith("/interviews/"):
            window = _window(session.artifacts, reference)
            locator = window["source_reference" if part == "source" else "context_reference"]
            metadata = {"summary_path": reference, "part": part,
                        "context_available": window["context_reference"] is not None}
            if locator is None:
                if offset != 0:
                    raise ToolException(_INPUT_ERROR)
                return {**metadata, "reference": None, "segments": [], "next_offset": None,
                        "notice": "此詳記沒有另外保存前置脈絡；這不代表沒有較早訪談。"}
        else:
            if part != "source":
                raise ToolException(_INPUT_ERROR)
            locator = reference
        try:
            excerpt = session.source.read(locator)
        except InvalidSourceReference:
            raise ToolException(_REF_ERROR) from None
        except ConversationSourceError as error:
            _source_error(error)
        except Exception:
            raise ConversationSourceError("source_not_available") from None
        return {**source_page(excerpt, offset), **metadata}

    read_conversation.handle_tool_error = True
    read_conversation.handle_validation_error = _INPUT_ERROR
    return read_conversation
