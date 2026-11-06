"""JD 向 Context 提供導覽與同一份資料的已見版本。"""

import asyncio
import json
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from typing import Any, cast

from langgraph.runtime import Runtime

from caliburn.bundles.context.contracts import WindowContribution
from caliburn.bundles.context.services import WINDOW_CONTRIBUTIONS
from caliburn.bundles.job_description.citation_reading import read_citation_results
from caliburn.bundles.job_description.projection import project_jd, reference_targets
from caliburn.bundles.job_description.services import (
    JD_CITATION_SOURCES,
    JD_MEMORY_QUERIES,
    JD_QUERIES,
    JD_REFERENCES,
)
from caliburn.bundles.job_description.state import JobDescriptionToolState
from caliburn.modules.agent.plugins.contracts import AgentContext, AgentPlugin
from caliburn.modules.agent.plugins.services import PluginServices, ServiceBinding
from caliburn.modules.agent.state import AgentState, request_items


@asynccontextmanager
async def _open_contribution(
    services: PluginServices,
) -> AsyncIterator[tuple[ServiceBinding[tuple[WindowContribution, ...]]]]:
    yield (WINDOW_CONTRIBUTIONS.bind((WindowContribution(prepare_jd_window),)),)


def create_context_plugin() -> AgentPlugin:
    return AgentPlugin(
        name="job_description_context",
        required_plugins=("job_description",),
        required_services=(
            JD_QUERIES,
            JD_REFERENCES,
            JD_CITATION_SOURCES,
            JD_MEMORY_QUERIES,
        ),
        provided_services=(WINDOW_CONTRIBUTIONS,),
        open_services=_open_contribution,
    )


async def prepare_jd_window(
    state: AgentState,
    *,
    previous: Mapping[str, Any] | None,
    rebuilding: bool,
    runtime: Runtime[AgentContext],
) -> Mapping[str, object]:
    if not rebuilding:
        return {
            "jd_version": previous.get("jd_version") if previous is not None else None
        }
    queries = runtime.context.services.require(JD_QUERIES)
    snapshot = await asyncio.to_thread(
        queries.find_job_description_by_workspace, workspace_id=state["workspace_id"]
    )
    projected = None
    if snapshot is not None:
        references = runtime.context.services.require(JD_REFERENCES)
        mapped = await asyncio.to_thread(
            references.get_or_create_refs,
            state["workspace_id"],
            reference_targets(snapshot),
        )
        citation_results = await asyncio.to_thread(
            read_citation_results,
            snapshot,
            services=runtime.context.services,
            published_version=cast(JobDescriptionToolState, state).get(
                "memory_published_version"
            ),
        )
        projected = project_jd(
            snapshot, mapped, view="map", citation_results=citation_results
        )
    request = state["model_request"]
    return {
        "jd_version": snapshot.version if snapshot else None,
        "model_request": {
            **request,
            "input": [
                *request_items(request),
                {
                    "role": "user",
                    "content": json.dumps(
                        {"data_kind": "job_description_map", "jd": projected},
                        ensure_ascii=False,
                    ),
                },
            ],
        },
    }
