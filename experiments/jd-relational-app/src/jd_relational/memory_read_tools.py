"""Read saved summary sources through the existing conversation source owner.

The page offset only projects an already resolved immutable SourceExcerpt. It is
not a new source locator, persisted state, or an offset accepted by the owner.
LangChain's public ToolRuntime is injected by ToolNode, hidden from model input:
https://docs.langchain.com/oss/python/langchain/tools#access-context
"""
import json
from hashlib import sha256
from typing import Literal
from uuid import UUID
from caliburn_memory.sources import InvalidSourceReference

from langchain.tools import ToolRuntime, tool
from langchain_core.tools import BaseTool, ToolException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .conversation_sources import ConversationSourceError, SourceExcerpt
from .memory_context import (
    MemoryReadError,
    evidence_read_projection,
    layered_read_proof,
    memory_session,
)


SOURCE_PAGE_CHARS = 3000
_INPUT_ERROR = "invalid_input: 使用已取得的reference、非負offset及source或context；續頁沿用next_offset。"
_REF_ERROR = "invalid_ref: 來源或詳記定位無效；請複製App已提供的原引用，不猜測或重新編碼。"
_MISSING_SUMMARY = "summary_missing: 此文件沒有這份詳記；請先讀既有Memory連結，不猜路徑。"
_EVIDENCE_KEY_ERROR = (
    "unknown_evidence_key: 請只使用本回合來源通知、JD、read_case或Working State已提供的evidence_key。"
)


def _jd_evidence_projection(entry, page: dict, context) -> tuple[str, dict]:
    """Expose the same bounded source page for a JD-issued evidence key."""
    content = json.dumps({
        "evidence_key": entry.evidence_key,
        "source_order": "oldest_to_newest",
        "segments": [{
            "role": segment["role"],
            "text": segment["text"],
            "continued_from_previous_page": segment["text_offset"] > 0,
        } for segment in page["segments"]],
        "has_more": page["next_offset"] is not None,
    }, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    dataset_id, document_id, run_id = context.dataset_id, context.document_id, context.run_id
    return content, {
        "format_version": 1, "kind": "jd_evidence",
        "dataset_id": dataset_id, "document_id": document_id, "run_id": run_id,
        "scope_kind": entry.scope_kind, "scope_id": entry.scope_id,
        "evidence_key": entry.evidence_key,
        "source_reference": entry.source_reference,
        "read_offset": page["read_offset"], "next_offset": page["next_offset"],
        "content_digest": sha256(content.encode("utf-8")).hexdigest(),
    }


class _ReadConversationInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    reference: str = Field(min_length=1, max_length=4096,
        description="已讀的/interviews/<id>/summary.md，或App提供的完整conversation來源；原樣複製。")
    offset: int = Field(default=0, ge=0, le=2**63 - 1,
        description="首次0；續頁只使用此reference及part上頁回傳的next_offset，不自行計算。")
    part: Literal["source", "context"] = Field(default="source",
        description="source讀原始輸入；context只用於summary路徑，讀另外保存的前置脈絡。")


class _ReadEvidenceInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")
    evidence_key: str = Field(
        min_length=3,
        max_length=64,
        description="只使用本回合來源通知、JD、read_case或Working State提供的短key；不要填reference、offset或版本。",
    )


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
        return {**source_page(excerpt, offset), "read_offset": offset, **metadata}

    read_conversation.handle_tool_error = True
    read_conversation.handle_validation_error = _INPUT_ERROR
    return read_conversation


def build_evidence_read_tool() -> BaseTool:
    """Build A's scoped source reader with a Runtime-owned cursor."""

    @tool(
        "read_evidence",
        args_schema=_ReadEvidenceInput.model_json_schema(),
        response_format="content_and_artifact",
    )
    def read_evidence(runtime: ToolRuntime, **arguments):
        """讀取本回合來源通知、JD、read_case或Working State已提供的一筆原話；只填evidence_key。

        Runtime會固定正式來源、scope與續頁位置；案例來源另固定本回合Memory版本。
        回傳按原訪談順序排列的公開問答；has_more為true時再次使用同一key續讀。
        不要猜reference或offset。
        """
        session = memory_session(runtime)
        try:
            parsed = _ReadEvidenceInput.model_validate(arguments)
        except ValidationError:
            raise ToolException(_EVIDENCE_KEY_ERROR) from None
        try:
            matches = []
            proof = None
            # JD source keys use the same Runtime catalog, but a Memory-only
            # read must remain on the existing Memory path.  Do not make
            # unrelated JD artifacts a prerequisite for B1/B2/C reads.
            messages = runtime.state.get("messages", ())
            has_jd_read = any(
                any(call.get("name") in {"jd_read", "jd_change_read"}
                    for call in getattr(message, "tool_calls", ()))
                for message in messages
            )
            jd_entry = None
            if has_jd_read:
                # The model never supplies or receives the canonical source
                # reference; the catalog validates the private artifacts.
                from .consultant_tools import jd_evidence_catalog
                jd_entry = jd_evidence_catalog(runtime).get(parsed.evidence_key)
            if jd_entry is not None:
                offset = jd_entry.next_offset
                if offset is None:
                    offset = 0
                excerpt = session.source.read(jd_entry.source_reference)
                page = {**source_page(excerpt, offset), "read_offset": offset}
                content, artifact = _jd_evidence_projection(jd_entry, page, runtime.context)
                return content, artifact
            if (session.head is not None
                    and session.artifacts.bundle_base(session.head.memory) is not None):
                proof = layered_read_proof(
                    runtime.state.get("messages", []),
                    dataset_id=session.dataset_id,
                    document_id=session.document_id,
                    run_id=session.run_id,
                    revision=session.head.revision,
                    version_id=session.head.memory.version_id,
                )
                matches = [
                (case_id, reference)
                for case_id, mapping in proof.case_evidence.items()
                for key, reference in mapping.items()
                if key == parsed.evidence_key
                ]
            from .working_state import (
                WorkingStateError, working_evidence_catalog,
                working_evidence_projection,
            )
            context = runtime.context
            working_state = runtime.state.get("interview_working_state")
            raw_source = (context.source_notice(runtime.state.get("messages", ()))
                if context.source_notice is not None else None)
            working = {}
            has_working_source = (type(raw_source) is dict
                                  and raw_source.get("type") == "conversation_source_notice")
            if working_state is not None or has_working_source:
                try:
                    working = working_evidence_catalog(
                        state=working_state, context=context,
                        messages=runtime.state.get("messages", ()), raw_source_notice=raw_source,
                    )
                except WorkingStateError:
                    raise MemoryReadError() from None
            working_entry = working.get(parsed.evidence_key)
            if len(matches) + (working_entry is not None) != 1:
                raise ToolException(_EVIDENCE_KEY_ERROR)
            if working_entry is not None:
                offset = working_entry.next_offset
                if offset is None:
                    offset = 0
                excerpt = session.source.read(working_entry.source_reference)
                page = {**source_page(excerpt, offset), "read_offset": offset}
                return working_evidence_projection(working_entry, page, context)
            case_id, reference = matches[0]
            offset = proof.evidence_next_offsets.get(parsed.evidence_key, 0)
            # A completed exact source may be read again after request-only
            # compaction; restart only that same immutable locator.
            if offset is None:
                offset = 0
            excerpt = session.source.read(reference)
            page = {**source_page(excerpt, offset), "read_offset": offset}
            return evidence_read_projection(
                session,
                case_id=case_id,
                evidence_key=parsed.evidence_key,
                source_reference=reference,
                page=page,
            )
        except ToolException:
            raise
        except InvalidSourceReference:
            raise MemoryReadError("memory_not_available") from None
        except ConversationSourceError as error:
            _source_error(error)
        except MemoryReadError:
            raise
        except Exception:
            raise MemoryReadError() from None

    read_evidence.handle_tool_error = True
    read_evidence.handle_validation_error = _EVIDENCE_KEY_ERROR
    return read_evidence
