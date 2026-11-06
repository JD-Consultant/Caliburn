"""窗口 JD 導覽與已見版本，延續窗口不可偷換成資料庫最新版本。"""

import asyncio
import json

from langgraph.runtime import Runtime

from caliburn.bundles.job_description.context import prepare_jd_window
from caliburn.bundles.job_description.services import JD_QUERIES, JD_REFERENCES
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.plugins.services import PluginServices
from caliburn.modules.agent.state import AgentState
from tests.unit.bundles.job_description.test_citation_reading import (
    Sources,
    citation_runtime,
)
from tests.unit.bundles.job_description.test_projection import snapshot
from tests.unit.bundles.job_description.test_read import Queries, References


def test_rebuilt_window_appends_navigation_and_matching_version() -> None:
    jd = snapshot()
    state: AgentState = {
        "workspace_id": jd.workspace_id,
        "model_request": {
            "model": "offline",
            "input": [{"role": "user", "content": "之前"}],
        },
    }
    runtime = Runtime(
        context=AgentContext(
            PluginServices({JD_QUERIES: Queries(jd), JD_REFERENCES: References()})
        )
    )
    result = asyncio.run(
        prepare_jd_window(state, previous=None, rebuilding=True, runtime=runtime)
    )
    assert result["jd_version"] == 7
    request = result["model_request"]
    assert isinstance(request, dict)
    assert request["input"][0] == {"role": "user", "content": "之前"}
    added = json.loads(request["input"][-1]["content"])
    assert added["data_kind"] == "job_description_map"
    assert added["jd"]["tasks"][0]["read_ref"] == "task_104"
    assert "jd_turn_start_version" not in result
    assert len(state["model_request"]["input"]) == 1


def test_continuing_window_uses_previous_seen_version_without_reading_latest() -> None:
    result = asyncio.run(
        prepare_jd_window(
            {},
            previous={"jd_version": 3},
            rebuilding=False,
            runtime=Runtime(context=AgentContext(PluginServices({}))),
        )
    )
    assert result == {"jd_version": 3}


def test_rebuilt_window_uses_application_citation_status() -> None:
    scope = citation_runtime(Sources(unavailable=True))
    state: AgentState = {
        "workspace_id": scope.state["workspace_id"],
        "model_request": {"model": "offline", "input": []},
    }
    result = asyncio.run(
        prepare_jd_window(
            state,
            previous=None,
            rebuilding=True,
            runtime=Runtime(context=scope.context),
        )
    )
    request = result["model_request"]
    assert isinstance(request, dict)
    source = json.loads(request["input"][0]["content"])["jd"]["tasks"][0][
        "supporting_sources"
    ][0]
    assert source["availability"] == "unavailable"
    assert source["jd_changed"] is True and source["needs_recheck"] is True
    assert source["message_ref"] == "message_112"
