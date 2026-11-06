"""固定人工差異的模型注入與成功完成版捕捉；取消不推進基準。"""

import json
from collections.abc import Mapping

from langgraph.func import task
from langgraph.runtime import Runtime

from caliburn.bundles.job_description.citation_reading import read_citation_results
from caliburn.bundles.job_description.manual_changes import project_manual_changes
from caliburn.bundles.job_description.projection import reference_targets
from caliburn.bundles.job_description.services import (
    JD_HISTORY_QUERIES,
    JD_REFERENCES,
)
from caliburn.bundles.job_description.state import JobDescriptionExecutionState
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.state import request_items
from caliburn.modules.job_description.application.history.operations import get_history
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)


async def inject_manual_changes(
    state: JobDescriptionExecutionState, *, runtime: Runtime[AgentContext]
) -> Mapping[str, object]:
    if state["model_step"] != 1 or state["jd_id"] is None:
        return {}
    jd_id = state["jd_id"]
    before_version = state["jd_manual_before_version"]
    after_version = state["jd_turn_start_version"]
    assert before_version is not None and after_version is not None

    @task
    def capture() -> str | None:
        queries = runtime.context.services.require(JD_HISTORY_QUERIES)
        endpoints = []
        for version in (before_version, after_version):
            historical = get_history(
                workspace_id=state["workspace_id"],
                job_description_id=jd_id,
                version=version,
                queries=queries,
            )
            endpoints.append(
                JobDescriptionResult(**dict(historical.content), version=version)
            )
        before, after = endpoints
        references = runtime.context.services.require(JD_REFERENCES)
        mapped = references.get_or_create_refs(
            state["workspace_id"],
            (*reference_targets(before), *reference_targets(after)),
        )
        # 人工淨差異中的已刪引用也須保留原固定來源；不混入本輪來源比較。
        before_citations = read_citation_results(
            before, services=runtime.context.services, published_version=None
        )
        after_citations = read_citation_results(
            after, services=runtime.context.services, published_version=None
        )
        projected = project_manual_changes(
            before,
            after,
            mapped,
            before_citations=before_citations,
            after_citations=after_citations,
        )
        return (
            json.dumps(projected, ensure_ascii=False) if projected is not None else None
        )

    content = await capture()
    if content is None:
        return {}
    request = state["model_request"]
    return {
        "model_request": {
            **request,
            "input": [
                *request_items(request),
                {
                    "role": "user",
                    "content": content,
                },
            ],
        },
        "jd_version": after_version,
    }


async def capture_completed_jd(
    state: JobDescriptionExecutionState, *, runtime: Runtime[AgentContext]
) -> Mapping[str, object]:
    # 模型請求途中可能有人改稿；不可把模型未見的新版本吸收入完成基準。
    version = state["jd_version"]
    return {
        "jd_completed_version": version
        if version is not None
        else state["jd_turn_start_version"]
    }
