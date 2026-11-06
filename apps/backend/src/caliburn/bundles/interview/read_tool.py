"""唯一 read_interview 工廠；角色 reader 先提供完整合法的有序集合。"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, Literal

from langchain_core.tools import StructuredTool
from langgraph.prebuilt import ToolRuntime
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from caliburn.bundles.interview.read_output import bounded_interview, rejection
from caliburn.bundles.interview.references import message_refs
from caliburn.bundles.interview.services import INTERVIEW_QUERIES, MODEL_REFERENCES
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.interview.application.results import TranscriptMessage
from caliburn.modules.model_references import (
    InvalidModelReferenceError,
    UnknownModelReferenceError,
)

type InterviewReader = Callable[
    [ToolRuntime[AgentContext, Any]], Awaitable[tuple[TranscriptMessage, ...]]
]
type MessageRef = Annotated[str, Field(pattern=r"^message_[1-9][0-9]*$")]


class InterviewReadScopeError(ValueError):
    """固定來源或分析資格失效；不能繼續篩選剩餘訊息。"""


class _Selection(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class _Messages(_Selection):
    kind: Literal["messages"]
    refs: list[MessageRef] = Field(
        min_length=1,
        description=(
            "使用訪談預載、已保存本輪原話或工具結果提供的 message_N；"
            "去重後依正式訪談順序回傳。"
        ),
    )


class _Range(_Selection):
    kind: Literal["range"]
    start_ref: MessageRef = Field(description="有效可讀起點，包含此則。")
    end_ref: MessageRef = Field(
        description="有效可讀終點，包含此則；依訪談順序，不依短碼數字比較。"
    )


class _ReadInput(_Selection):
    query: _Messages | _Range = Field(
        description="明列訊息或有效集合內的順序區間；任一指定來源失效整次拒絕。"
    )


async def read_available_interview(
    runtime: ToolRuntime[AgentContext, Any],
) -> tuple[TranscriptMessage, ...]:
    """A 的有效訪談包含本輪已保存原話；B 以自己的 reader 限定固定範圍。"""
    return await asyncio.to_thread(
        runtime.context.services.require(INTERVIEW_QUERIES).list_messages,
        workspace_id=runtime.state["workspace_id"],
    )


def _invalid_arguments(error: ValidationError, query: object) -> str:
    issues = error.errors(include_input=False, include_url=False)
    kind = query.get("kind") if isinstance(query, dict) else None
    branch = "_Range" if kind == "range" else "_Messages"
    issue = next((issue for issue in issues if branch in issue["loc"]), issues[0])
    location = ""
    fields = {"query", "kind", "refs", "start_ref", "end_ref"}
    for part in issue["loc"]:
        if part in {"messages", "range", "_Messages", "_Range"}:
            continue
        if isinstance(part, int):
            location += f"[{part}]"
        else:
            location += ("." if location else "") + (
                part if part in fields else "<extra>"
            )
    return rejection(
        "invalid_arguments",
        f"{location or 'query'} 格式不合法。",
        "請依 query 的 messages 或 range 格式修正；ref 必須是材料提供的 message_N。",
    )


def create_read_interview_tool(
    *, reader: InterviewReader | None = None, max_output_characters: int = 24000
) -> StructuredTool:
    """reader 先驗完整資格並回 owner 順序；資料故障直接傳出，不當成空集合。"""
    if max_output_characters < 1:
        raise ValueError("max_output_characters 必須為正整數")
    load_sources = reader or read_available_interview

    async def read_interview(
        runtime: ToolRuntime[AgentContext, Any], **raw: object
    ) -> str:
        try:
            query = _ReadInput.model_validate(raw).query
        except ValidationError as error:
            return _invalid_arguments(error, raw.get("query"))
        try:
            sources = await load_sources(runtime)
        except InterviewReadScopeError:
            return rejection(
                "scope_not_allowed",
                "本次固定訪談來源或分析資格已失效。",
                "請由應用重新確認分析工作；不要改用剩餘來源或自行擴大範圍。",
            )
        requested = (
            query.refs
            if isinstance(query, _Messages)
            else [query.start_ref, query.end_ref]
        )
        references = runtime.context.services.require(MODEL_REFERENCES)
        workspace_id = runtime.state["workspace_id"]
        try:
            targets = await asyncio.to_thread(
                references.resolve_refs, workspace_id, requested
            )
        except (InvalidModelReferenceError, UnknownModelReferenceError) as error:
            code = (
                "invalid_arguments"
                if isinstance(error, InvalidModelReferenceError)
                else "source_not_available"
            )
            return rejection(
                code,
                f"{_reference_path(query, error.reference)} 的 ref 無法讀取。",
                "請改用目前材料提供的 message_N；不要猜號、UUID 或其他 Workspace。",
            )
        positions = {source.message_id: index for index, source in enumerate(sources)}
        for ref in requested:
            target = targets[ref]
            if target.resource_kind != "message":
                return rejection(
                    "invalid_arguments",
                    f"{_reference_path(query, ref)} 必須指向訪談訊息。",
                    "請複製材料提供的 message_N。",
                )
            if target.resource_id not in positions:
                return rejection(
                    "scope_not_allowed"
                    if reader is not None
                    else "source_not_available",
                    f"{_reference_path(query, ref)} 的 {ref} 不在目前可讀來源內。",
                    "請使用目前有效來源的 ref；不能讀已撤回訊息或擴大固定分析範圍。",
                )
        if isinstance(query, _Messages):
            selected_ids = {targets[ref].resource_id for ref in requested}
            selected = tuple(
                source for source in sources if source.message_id in selected_ids
            )
        else:
            start = positions[targets[query.start_ref].resource_id]
            end = positions[targets[query.end_ref].resource_id]
            if start > end:
                return rejection(
                    "invalid_arguments",
                    "query.start_ref 晚於 query.end_ref。",
                    "請依材料中的正式訪談順序選起迄；不要比較短碼數字。",
                )
            selected = sources[start : end + 1]
        ids = tuple(
            message_id
            for source in selected
            for message_id in (source.message_id, source.reply_to_message_id)
            if message_id is not None
        )
        refs = await asyncio.to_thread(
            message_refs,
            workspace_id=workspace_id,
            message_ids=ids,
            references=references,
        )
        return bounded_interview(
            selected, refs=refs, selection=query.kind, limit=max_output_characters
        )

    return StructuredTool.from_function(
        coroutine=read_interview,
        name="read_interview",
        description="查讀已保存的訪談完整文字，保留發話者與明確題答關係。需要核對原話、代稱或來源時使用；只讀指定訊息或有效來源集合的順序區間，不摘要。",
        args_schema=_ReadInput.model_json_schema(),
    )


def _reference_path(query: _Messages | _Range, ref: str) -> str:
    if isinstance(query, _Messages):
        return f"query.refs[{query.refs.index(ref)}]"
    return "query.start_ref" if ref == query.start_ref else "query.end_ref"
