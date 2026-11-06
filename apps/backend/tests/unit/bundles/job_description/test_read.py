"""公開讀工具的可信範圍、短碼、可修正拒絕及已見版本。"""

import asyncio
import json
from collections.abc import Collection
from threading import current_thread, main_thread
from uuid import UUID

import pytest
from langgraph.prebuilt import ToolRuntime
from langgraph.types import Command

from caliburn.bundles.job_description.reading import create_read_tool
from caliburn.bundles.job_description.services import JD_QUERIES, JD_REFERENCES
from caliburn.bundles.job_description.state import JobDescriptionToolState
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.plugins.services import PluginServices
from caliburn.modules.job_description.application.errors import JobDescriptionQueryError
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.model_references.contracts import (
    ReferenceTarget,
    UnknownModelReferenceError,
)
from tests.unit.bundles.job_description.test_projection import refs, snapshot


class Queries:
    def __init__(
        self, result: JobDescriptionResult | None, error: Exception | None = None
    ):
        self.result = result
        self.error = error

    def find_job_description_by_workspace(
        self, *, workspace_id: UUID
    ) -> JobDescriptionResult | None:
        assert current_thread() is not main_thread()
        assert workspace_id == UUID(int=2)
        if self.error is not None:
            raise self.error
        return self.result


class References:
    """固定已配置結果，只用於工具邊界單元測試，不模擬持久映射。"""

    def get_or_create_refs(
        self, workspace_id: UUID, targets: Collection[ReferenceTarget]
    ) -> dict[ReferenceTarget, str]:
        assert current_thread() is not main_thread()
        assert workspace_id == UUID(int=2)
        return {target: refs()[target] for target in targets}

    def resolve_refs(
        self, workspace_id: UUID, requested: Collection[str]
    ) -> dict[str, ReferenceTarget]:
        assert current_thread() is not main_thread()
        assert workspace_id == UUID(int=2)
        existing = {ref: target for target, ref in refs().items()}
        if any(ref not in existing for ref in requested):
            raise UnknownModelReferenceError("unknown", "未知")
        return {ref: existing[ref] for ref in requested}


def runtime(queries: Queries) -> ToolRuntime[AgentContext, JobDescriptionToolState]:
    return ToolRuntime(
        state={
            "workspace_id": UUID(int=2),
            "turn_id": UUID(int=20),
            "jd_id": UUID(int=1),
            "jd_version": None,
        },
        context=AgentContext(
            PluginServices({JD_QUERIES: queries, JD_REFERENCES: References()})
        ),
        config={},
        stream_writer=lambda value: None,
        tool_call_id="read",
        store=None,
    )


def test_read_returns_matching_version_without_mutating_runtime() -> None:
    tool_runtime = runtime(Queries(snapshot()))
    result = asyncio.run(
        create_read_tool().ainvoke(
            {"view": "item", "read_ref": "task_104", "runtime": tool_runtime}
        )
    )
    assert isinstance(result, Command) and isinstance(result.update, dict)
    assert result.update["jd_version"] == 7
    message = result.update["messages"][0]
    assert message.tool_call_id == "read"
    assert json.loads(message.content)["item"]["read_ref"] == "task_104"
    assert tool_runtime.state["jd_version"] is None


@pytest.mark.parametrize(
    "arguments",
    [
        {"view": "item"},
        {"view": "full", "read_ref": "task_104"},
        {"view": "map", "expected_version": 7},
        {"view": "item", "read_ref": str(UUID(int=4))},
    ],
)
def test_rejected_read_has_repair_and_never_advances_seen_version(
    arguments: dict[str, object],
) -> None:
    tool_runtime = runtime(Queries(snapshot()))
    result = asyncio.run(
        create_read_tool().ainvoke({**arguments, "runtime": tool_runtime})
    )
    assert isinstance(result, str)
    assert json.loads(result)["status"] == "rejected"
    assert json.loads(result)["next_action"]
    assert tool_runtime.state["jd_version"] is None


def test_absent_jd_is_rejection_not_fake_empty_document() -> None:
    result = asyncio.run(
        create_read_tool().ainvoke({"view": "map", "runtime": runtime(Queries(None))})
    )
    assert isinstance(result, str)
    assert json.loads(result)["code"] == "jd_not_found"


def test_query_failure_remains_failure() -> None:
    with pytest.raises(JobDescriptionQueryError):
        asyncio.run(
            create_read_tool().ainvoke(
                {
                    "view": "map",
                    "runtime": runtime(Queries(None, JobDescriptionQueryError())),
                }
            )
        )
