"""公開 JD 讀工具與模型可修正的定位拒絕。"""

import asyncio
import json
from typing import Annotated

from langchain_core.messages import ToolMessage
from langchain_core.tools import StructuredTool, ToolException
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command
from pydantic import BaseModel, ConfigDict, Field, ValidationError, create_model
from pydantic.v1 import ValidationError as ValidationErrorV1

from caliburn.bundles.job_description.citation_reading import read_citation_results
from caliburn.bundles.job_description.projection import (
    ReadView,
    project_jd,
    reference_targets,
)
from caliburn.bundles.job_description.services import JD_QUERIES, JD_REFERENCES
from caliburn.bundles.job_description.state import JobDescriptionToolState
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.model_references.contracts import ModelReferenceError


def rejection(code: str, message: str, next_action: str) -> str:
    return json.dumps(
        {
            "status": "rejected",
            "code": code,
            "message": message,
            "next_action": next_action,
        },
        ensure_ascii=False,
    )


async def read_jd(
    view: Annotated[
        ReadView, Field(description="map 讀完整導覽；item 讀一項全文；full 讀整份 JD。")
    ],
    runtime: ToolRuntime[AgentContext, JobDescriptionToolState],
    read_ref: Annotated[
        str | None,
        Field(
            description="item 填已提供的 JD 短碼；"
            "讀來源原件填 supporting_sources 的 citation_ref；map/full 填 null。"
        ),
    ] = None,
) -> Command[object]:
    """查讀目前 JD。導覽列出所有項目、分類及 K/S 關聯；Task 全文包含 O/P。

    返回同一次查詢的版本與內容；未找到與空 JD 分開。正文中的定位文字保持原樣。
    """
    if (view == "item") != (read_ref is not None):
        raise ToolException(
            rejection(
                "invalid_arguments",
                "view 與 read_ref 不匹配。",
                "item 必須提供短碼 read_ref；map/full 的 read_ref 填 null。",
            )
        )
    queries = runtime.context.services.require(JD_QUERIES)
    references = runtime.context.services.require(JD_REFERENCES)
    workspace_id = runtime.state["workspace_id"]
    snapshot = await asyncio.to_thread(
        queries.find_job_description_by_workspace, workspace_id=workspace_id
    )
    if snapshot is None:
        raise ToolException(
            rejection(
                "jd_not_found", "此工作區尚無 JD。", "請先由工作區建立 JD，再讀取。"
            )
        )
    target = None
    try:
        if read_ref is not None:
            resolved = await asyncio.to_thread(
                references.resolve_refs, workspace_id, (read_ref,)
            )
            target = resolved[read_ref]
            if target.resource_kind == "message" or target not in reference_targets(
                snapshot
            ):
                raise ToolException(
                    rejection(
                        "target_not_found",
                        "指定項目不存在於目前 JD。",
                        "以 read_jd map 取得目前可用項目。",
                    )
                )
        mapped = await asyncio.to_thread(
            references.get_or_create_refs, workspace_id, reference_targets(snapshot)
        )
    except ModelReferenceError as error:
        raise ToolException(
            rejection(
                "target_not_found",
                "指定短碼在此工作區不可用。",
                "以 read_jd map 取得短碼，不要填 UUID 或猜名稱。",
            )
        ) from error
    citation_results = await asyncio.to_thread(
        read_citation_results,
        snapshot,
        services=runtime.context.services,
        published_version=runtime.state.get("memory_published_version"),
    )
    projected = project_jd(
        snapshot, mapped, view=view, target=target, citation_results=citation_results
    )
    assert runtime.tool_call_id is not None
    return Command(
        update={
            "jd_version": snapshot.version,
            "messages": [
                ToolMessage(
                    content=json.dumps(projected, ensure_ascii=False),
                    tool_call_id=runtime.tool_call_id,
                )
            ],
        }
    )


def _validation_error(error: ValidationError | ValidationErrorV1) -> str:
    return rejection(
        "invalid_arguments",
        "讀取參數不符合格式。",
        "view 使用 map/item/full；item 的 read_ref 填短碼，map/full 填 null。",
    )


def create_read_tool() -> StructuredTool:
    tool = StructuredTool.from_function(
        coroutine=read_jd,
        handle_tool_error=True,
        handle_validation_error=_validation_error,
    )
    schema = tool.get_input_schema()
    assert issubclass(schema, BaseModel)
    tool.args_schema = create_model(
        schema.__name__, __base__=schema, __config__=ConfigDict(extra="forbid")
    )
    return tool
