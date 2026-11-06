"""人工等待在真 PostgreSQL 保存後，仍只能由同輪答案接續。"""

import asyncio
import json
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from uuid import UUID

import httpx2
import pytest
from langgraph.runtime import Runtime
from langgraph.types import interrupt

from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from caliburn.modules.agent.plugins.contracts import (
    AgentContext,
    AgentPlugin,
    PluginStep,
)
from caliburn.modules.agent.state import AgentState
from tests.unit.modules.agent.offline_openai import MODEL_REQUEST, offline_client


def test_human_interrupt_returns_native_question_without_execution_error(
    checkpoint_conninfo: str,
) -> None:
    async def ask(
        state: AgentState, *, runtime: Runtime[AgentContext]
    ) -> Mapping[str, object]:
        interrupt({"question": "Which source is approved?"})
        return {}

    async def run() -> None:
        async with (
            open_postgres_checkpointer(checkpoint_conninfo, initialize=True) as saver,
            offline_client(
                httpx2.MockTransport(lambda _: pytest.fail("model before answer"))
            ) as client,
            open_agent(
                agent_id="waiting",
                resume_version="v1",
                client=client,
                model_settings=MODEL_REQUEST,
                bundles=(
                    BundleConfig(
                        "tests.unit.modules.agent.offline_openai",
                        {
                            "plugins": (
                                AgentPlugin(
                                    "approval",
                                    on_turn_start=(PluginStep("ask", ask),),
                                ),
                            )
                        },
                    ),
                ),
                checkpointer=saver,
            ) as agent,
        ):
            chunks = [
                chunk
                async for chunk in agent.astream(
                    workspace_id=UUID(int=51),
                    turn_id=UUID(int=501),
                    input="original question",
                )
            ]
            questions = [
                question for part in chunks for question in part.get("interrupts", ())
            ]
            assert len(questions) == 1
            assert questions[0].value == {"question": "Which source is approved?"}

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_waiting_survives_process_restart_and_accepts_only_its_turn_answer(
    checkpoint_conninfo: str, tmp_path: Path
) -> None:
    for mode in ("writer", "reader"):
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "tests.integration.agent.interrupt_process",
                mode,
                checkpoint_conninfo,
                str(tmp_path),
            ],
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
    assert json.loads((tmp_path / "writer.json").read_text()) == []
    sent = json.loads((tmp_path / "reader.json").read_text())
    assert len(sent) == 1
    assert sent[0]["input"] == [{"role": "user", "content": "original question"}]
