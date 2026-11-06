"""模型工具參數及唯讀公版查找。"""

import asyncio
from functools import partial
from typing import Annotated, TypedDict
from uuid import UUID

from langchain_core.tools import StructuredTool
from langgraph.prebuilt import ToolRuntime
from pydantic import BaseModel, ConfigDict, Field, create_model

from caliburn.bundles.job_reference.descriptions import (
    QUERY_DESCRIPTION,
    READ_DESCRIPTION,
    REFERENCE_ID_DESCRIPTION,
    SEARCH_DESCRIPTION,
    TASK_ID_DESCRIPTION,
)
from caliburn.bundles.job_reference.errors import (
    encode_result,
    invalid_read_arguments,
    invalid_search_arguments,
    reference_errors,
)
from caliburn.bundles.job_reference.projections import project_reference, project_task
from caliburn.bundles.job_reference.services import (
    REFERENCE_IDS,
    REFERENCE_RUNNER,
    REFERENCE_SEARCH,
)
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.model_references.contracts import (
    ReferenceTarget,
    UnknownModelReferenceError,
)


class _ReferenceToolState(TypedDict):
    workspace_id: UUID


def create_reference_tools(*, max_result_characters: int) -> tuple[StructuredTool, ...]:
    async def search_occupation_references(
        query: Annotated[
            str,
            Field(
                strict=True,
                min_length=1,
                max_length=12_000,
                pattern=(
                    r"[^\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680"
                    r"\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]"
                ),
                description=QUERY_DESCRIPTION,
            ),
        ],
        runtime: ToolRuntime[AgentContext, _ReferenceToolState],
    ) -> str:
        """查找最多五份公版的概述及完整已解析任務目錄，供查漏參考。"""
        service = runtime.context.services.require(REFERENCE_SEARCH)
        runner = runtime.context.services.require(REFERENCE_RUNNER)
        with reference_errors():
            result = await runner.run(partial(service.search, query, limit=5))
        references = runtime.context.services.require(REFERENCE_IDS)
        targets = [
            ReferenceTarget("occupation", UUID(hit.document.reference_id))
            for hit in result.hits
        ]
        reference_ids = await asyncio.to_thread(
            references.get_or_create_refs, runtime.state["workspace_id"], targets
        )
        return encode_result(
            {
                "references": [
                    project_reference(hit.document, reference_id=reference_ids[target])
                    for hit, target in zip(result.hits, targets, strict=True)
                ]
            },
            max_characters=max_result_characters,
        )

    async def read_occupation_reference(
        reference_id: Annotated[
            str,
            Field(
                strict=True,
                pattern=r"^occupation_[1-9][0-9]*$",
                description=REFERENCE_ID_DESCRIPTION,
            ),
        ],
        task_id: Annotated[
            str | None,
            Field(
                strict=True,
                pattern=r"^u[1-9][0-9]*-t[1-9][0-9]*$",
                description=TASK_ID_DESCRIPTION,
            ),
        ],
        runtime: ToolRuntime[AgentContext, _ReferenceToolState],
    ) -> str:
        """讀固定公版的完整目錄或任務群組細節；可以直接讀取，不必先選用。"""
        service = runtime.context.services.require(REFERENCE_SEARCH)
        references = runtime.context.services.require(REFERENCE_IDS)
        with reference_errors():
            resolved = await asyncio.to_thread(
                references.resolve_refs, runtime.state["workspace_id"], [reference_id]
            )
            target = resolved[reference_id]
            if target.resource_kind != "occupation":
                raise UnknownModelReferenceError(reference_id, "not an occupation")
            source_id = str(target.resource_id)
            if task_id is None:
                document = await asyncio.to_thread(service.read, source_id)
                output = project_reference(document, reference_id=reference_id)
            else:
                result = await asyncio.to_thread(service.read_task, source_id, task_id)
                output = project_task(result, reference_id=reference_id)
        return encode_result(output, max_characters=max_result_characters)

    tools = []
    for handler, description, invalid_arguments in (
        (search_occupation_references, SEARCH_DESCRIPTION, invalid_search_arguments),
        (read_occupation_reference, READ_DESCRIPTION, invalid_read_arguments),
    ):
        tool = StructuredTool.from_function(
            coroutine=handler,
            description=description,
            handle_tool_error=True,
            handle_validation_error=invalid_arguments,
        )
        schema = tool.get_input_schema()
        assert issubclass(schema, BaseModel)
        tool.args_schema = create_model(
            schema.__name__, __base__=schema, __config__=ConfigDict(extra="forbid")
        )
        tools.append(tool)
    return tuple(tools)
