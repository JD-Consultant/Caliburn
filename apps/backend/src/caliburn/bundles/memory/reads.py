"""角色依當前工作稿或固定發布版查讀，不從工具參數接受範圍。"""

import asyncio
from typing import Any, Literal, cast

from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command

from caliburn.bundles.interview.read_tool import (
    InterviewReadScopeError,
    create_read_interview_tool,
)
from caliburn.bundles.interview.references import message_refs
from caliburn.bundles.interview.services import MODEL_REFERENCES
from caliburn.bundles.memory.projections import (
    item_view,
    map_items,
    select_item,
)
from caliburn.bundles.memory.services import MEMORY_QUERIES
from caliburn.bundles.memory.state import ConsultantState
from caliburn.bundles.memory.tool_contracts import (
    EmptyArguments,
    TargetArguments,
)
from caliburn.bundles.memory.tool_output import bounded_output, encode
from caliburn.bundles.memory.tool_registration import memory_tool
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.state import AgentState
from caliburn.modules.interview.application.results import TranscriptMessage
from caliburn.modules.memory.domain.analysis import MemoryAnalysis
from caliburn.modules.memory.domain.errors import (
    InvalidMemoryPhaseError,
    InvalidMemorySourceError,
    MemoryAnalysisConflictError,
)
from caliburn.modules.memory.domain.items import MemoryItem, MemoryKind, WorkSituation
from caliburn.modules.memory.domain.work_memory import WorkMemory

type Role = Literal["consultant", "situation", "understanding"]


def analyst_scope(
    runtime: ToolRuntime[AgentContext, AgentState], role: MemoryKind
) -> tuple[WorkMemory, MemoryAnalysis]:
    root = runtime.context.services.require(MEMORY_QUERIES).get_current(
        workspace_id=runtime.state["workspace_id"]
    )
    analysis = root.require_analysis(
        analysis_id=runtime.state["turn_id"],
        phase=role,
    )
    return root, analysis


def _visible(
    runtime: ToolRuntime[AgentContext, Any], role: Role
) -> tuple[MemoryItem, ...]:
    if role == "consultant":
        state = cast(ConsultantState, runtime.state)
        snapshot = runtime.context.services.require(MEMORY_QUERIES).get_published(
            workspace_id=state["workspace_id"],
            published_version=state["memory_published_version"],
        )
        return snapshot.items if snapshot else ()
    root, _ = analyst_scope(runtime, role)
    return root.items


def create_read_tools(role: Role, *, limit: int) -> tuple[StructuredTool, ...]:
    def layer_tools(
        kind: MemoryKind, label: str
    ) -> tuple[StructuredTool, StructuredTool]:
        async def read_map(
            arguments: EmptyArguments, runtime: ToolRuntime[AgentContext, Any]
        ) -> str:
            items = await asyncio.to_thread(_visible, runtime, role)
            return bounded_output(map_items(items, kind), limit=limit)

        async def read_object(
            arguments: TargetArguments, runtime: ToolRuntime[AgentContext, Any]
        ) -> str:
            items = await asyncio.to_thread(_visible, runtime, role)
            item = select_item(items, kind, arguments.target_title)
            refs = await asyncio.to_thread(
                message_refs,
                workspace_id=runtime.state["workspace_id"],
                message_ids=item.interview_message_ids
                if isinstance(item, WorkSituation)
                else (),
                references=runtime.context.services.require(MODEL_REFERENCES),
            )
            return bounded_output(item_view(item, items, refs), limit=limit)

        return (
            memory_tool(
                f"read_work_{kind}_map",
                f"取得{label}完整導覽；已有足夠導覽可定位時就沿用。"
                "每項標題與描述只供選取，正文需另讀；空導覽不表示員工沒有相關工作。",
                EmptyArguments,
                read_map,
            ),
            memory_tool(
                f"read_work_{kind}",
                f"取得一項{label}完整正文與來源；已有足夠且仍有效的正文就沿用。"
                + (
                    "訪談引用只供定位，需要核對原句時才用 read_interview。"
                    if kind == "situation"
                    else "來源只含情境導覽；按需另讀情境正文，"
                    "已有充分正文就停止展開來源鏈。"
                ),
                TargetArguments,
                read_object,
            ),
        )

    async def read_analysis_sources(
        runtime: ToolRuntime[AgentContext, Any],
    ) -> tuple[TranscriptMessage, ...]:
        assert role != "consultant"

        def read() -> tuple[TranscriptMessage, ...]:
            try:
                _, analysis = analyst_scope(runtime, role)
                messages = runtime.context.services.require(
                    MEMORY_QUERIES
                ).list_analysis_sources(
                    workspace_id=runtime.state["workspace_id"],
                    analysis_id=analysis.analysis_id,
                )
            except (
                InvalidMemoryPhaseError,
                InvalidMemorySourceError,
                MemoryAnalysisConflictError,
            ) as error:
                raise InterviewReadScopeError(
                    "本次分析資格或完整固定來源已失效。"
                ) from error
            return tuple(
                TranscriptMessage(
                    message_id=m.message_id,
                    turn_id=m.turn_id,
                    speaker=m.speaker,
                    kind=m.kind,
                    text=m.text,
                    reply_to_message_id=m.reply_to_message_id,
                )
                for m in messages
            )

        return await asyncio.to_thread(read)

    interview_tool = create_read_interview_tool(
        reader=None if role == "consultant" else read_analysis_sources,
        max_output_characters=limit,
    )
    tools = layer_tools("situation", "工作情境")
    if role == "situation":
        return (*tools, interview_tool)
    return (*tools, *layer_tools("understanding", "工作理解"), interview_tool)


async def _request_consolidation(
    arguments: EmptyArguments, runtime: ToolRuntime[AgentContext, ConsultantState]
) -> Command[object]:
    assert runtime.tool_call_id is not None
    return Command(
        update={
            "memory_consolidation_requested": True,
            "messages": [
                ToolMessage(
                    tool_call_id=runtime.tool_call_id,
                    content=encode(
                        {"message": "已記錄整理要求；本輪成功完成後由系統處理。"}
                    ),
                )
            ],
        }
    )


def create_request_tool() -> StructuredTool:
    return memory_tool(
        "request_memory_consolidation",
        "某項已知資訊足以形成有用工作情境時，傳 {} 登記背景整理要求。"
        "只記意圖，本輪成功完成後納入完整正式訪談，包含之後的題答與略過；"
        "不必每輪要求或等待發布。",
        EmptyArguments,
        _request_consolidation,
    )
