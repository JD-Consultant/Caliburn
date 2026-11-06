"""只讀既存 JD 引用的 Memory 固定來源差異。"""

import asyncio
import json
from typing import Literal

from langchain_core.tools import StructuredTool, ToolException
from langgraph.prebuilt import ToolRuntime
from pydantic import BaseModel, ConfigDict, Field, create_model

from caliburn.bundles.job_description.reading import rejection
from caliburn.bundles.job_description.services import (
    JD_MEMORY_QUERIES,
    JD_QUERIES,
    JD_REFERENCES,
)
from caliburn.bundles.job_description.state import JobDescriptionToolState
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.job_description.application.citation_changes import (
    MemoryCitationContent,
)
from caliburn.modules.job_description.application.citations import (
    compare_citation_source,
)
from caliburn.modules.job_description.application.errors import (
    CitationNotFoundError,
    InvalidCitationSourceError,
)
from caliburn.modules.memory.domain.items import WorkSituation
from caliburn.modules.model_references.contracts import (
    ModelReferenceError,
    ReferenceTarget,
)


class SourceChangesQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["source"]
    citation_ref: str = Field(
        pattern=r"^citation_[1-9][0-9]*$",
        description="目前 JD supporting_sources 中的 Memory citation_ref。",
    )


async def read_jd_changes(
    query: SourceChangesQuery,
    runtime: ToolRuntime[AgentContext, JobDescriptionToolState],
) -> str:
    """比較一筆既有 JD Memory 引用的固定舊版與本輪發布版，返回兩端正文及來源鏈。

    比較版刪除同一物件會明示，保留舊標題；不以同名新項目接替。
    此工具只讀來源差異；人工 JD 差異由本輪 Context 提供，讀取不核清引用。
    """
    jd_id = runtime.state["jd_id"]
    published_version = runtime.state.get("memory_published_version")
    if jd_id is None or published_version is None:
        raise ToolException(
            rejection(
                "source_not_available",
                "本輪沒有固定 Memory 比較版。",
                "使用目前可讀材料；不要自行指定版本。",
            )
        )
    workspace_id = runtime.state["workspace_id"]
    references = runtime.context.services.require(JD_REFERENCES)
    try:
        resolved = await asyncio.to_thread(
            references.resolve_refs, workspace_id, (query.citation_ref,)
        )
        target = resolved[query.citation_ref]
        if target.resource_kind != "citation":
            raise ToolException(
                rejection(
                    "target_not_found",
                    "此短碼不是 JD 引用。",
                    "先讀取 JD 的 supporting_sources。",
                )
            )
        comparison = await asyncio.to_thread(
            compare_citation_source,
            workspace_id=workspace_id,
            job_description_id=jd_id,
            citation_id=target.resource_id,
            published_version=published_version,
            queries=runtime.context.services.require(JD_QUERIES),
            memory_queries=runtime.context.services.require(JD_MEMORY_QUERIES),
        )
    except (
        ModelReferenceError,
        CitationNotFoundError,
        InvalidCitationSourceError,
    ) as error:
        raise ToolException(
            rejection(
                "source_not_available",
                "此引用不可作 Memory 來源比較。",
                "讀取目前 JD，選擇其中的 Memory citation_ref。",
            )
        ) from error
    targets: list[ReferenceTarget] = []
    for content in (comparison.before, comparison.after):
        if content is None:
            continue
        situations = (
            (content.item,)
            if isinstance(content.item, WorkSituation)
            else content.situations
        )
        for situation in situations:
            targets.extend(
                ReferenceTarget("message", item_id)
                for item_id in situation.interview_message_ids
            )
    mapped = await asyncio.to_thread(
        references.get_or_create_refs, workspace_id, targets
    )

    def project(content: MemoryCitationContent | None) -> dict[str, object] | None:
        if content is None:
            return None

        def situation(item: WorkSituation) -> dict[str, object]:
            return {
                "target_title": item.content.title,
                "description": item.content.description,
                "body": item.content.body,
                "changed_version": item.changed_version,
                "interview_refs": [
                    mapped[ReferenceTarget("message", value)]
                    for value in item.interview_message_ids
                ],
            }

        item = content.item
        if isinstance(item, WorkSituation):
            return {"kind": item.kind, **situation(item)}
        return {
            "kind": item.kind,
            "target_title": item.content.title,
            "description": item.content.description,
            "body": item.content.body,
            "changed_version": item.changed_version,
            "situations": [situation(value) for value in content.situations],
        }

    return json.dumps(
        {
            "kind": "source",
            "citation_ref": query.citation_ref,
            "source_changed": comparison.source_changed,
            "before": project(comparison.before),
            "after": project(comparison.after),
        },
        ensure_ascii=False,
    )


def create_source_changes_tool() -> StructuredTool:
    tool = StructuredTool.from_function(
        coroutine=read_jd_changes,
        handle_tool_error=True,
        handle_validation_error=lambda error: rejection(
            "invalid_arguments",
            "來源查詢格式不符。",
            "query 只傳 kind=source 與 citation_ref。",
        ),
    )
    schema = tool.get_input_schema()
    assert issubclass(schema, BaseModel)
    tool.args_schema = create_model(
        schema.__name__, __base__=schema, __config__=ConfigDict(extra="forbid")
    )
    return tool
