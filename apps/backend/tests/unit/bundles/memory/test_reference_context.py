"""換窗只提供預載材料，不以過去輪次的索引限制新輪查讀。"""

import asyncio
from uuid import uuid4

from langgraph.runtime import Runtime

from caliburn.bundles.memory.state import ConsultantState
from caliburn.bundles.memory.window import prepare_memory_window
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.plugins.services import PluginServices


def test_continued_window_keeps_current_capture_without_merging_old_scope() -> None:
    captured = uuid4()
    state: ConsultantState = {
        "workspace_id": uuid4(),
        "turn_id": uuid4(),
        "memory_published_version": 3,
        "memory_interview_ids": (captured,),
        "memory_consolidation_requested": False,
    }
    previous = {"memory_interview_ids": (uuid4(),)}
    runtime = Runtime(context=AgentContext(PluginServices({})))

    update = asyncio.run(
        prepare_memory_window(
            state, previous=previous, rebuilding=False, runtime=runtime
        )
    )

    assert update == {}
    assert state["memory_interview_ids"] == (captured,)
