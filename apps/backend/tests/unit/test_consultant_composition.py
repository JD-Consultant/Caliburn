"""顧問 Host 的撤回依賴不隨模型能力開關消失。"""

import asyncio

import httpx2
import pytest
from langgraph.checkpoint.memory import InMemorySaver

from caliburn.bundles.context.services import COMPLETED_TURNS
from caliburn.host.consultant import compose_consultant_bundles
from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from tests.unit.modules.agent.offline_openai import MODEL_REQUEST, offline_client


def test_disabled_tools_still_require_business_cancellation_services() -> None:
    def reject_model(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("Startup must not call the model")

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(reject_model)) as client:
            with pytest.raises(ValueError, match="requires missing service"):
                async with open_agent(
                    agent_id="consultant",
                    resume_version="v1",
                    client=client,
                    model_settings=MODEL_REQUEST,
                    bundles=compose_consultant_bundles(()),
                    checkpointer=InMemorySaver(),
                ):
                    pass

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


@pytest.mark.parametrize("preload", [False, True])
def test_only_interview_history_preload_requires_completed_turn_lookup(
    preload: bool,
) -> None:
    bundles = compose_consultant_bundles(
        (
            BundleConfig("caliburn.bundles.interview", plugins=("interview",)),
            BundleConfig("caliburn.bundles.interview.window", {"preload": preload}),
            BundleConfig(
                "caliburn.bundles.context",
                plugins=("window",),
            ),
        )
    )
    contribution = next(
        plugin
        for bundle in bundles
        for plugin in bundle.plugins
        if plugin.name == "interview_window"
    )
    assert (COMPLETED_TURNS in contribution.required_services) is preload


@pytest.mark.parametrize("name", ["context", "recording", "read", "source_prompt"])
def test_interview_rejects_removed_activation_flags(
    name: str,
) -> None:
    with pytest.raises(ValueError, match=name):
        compose_consultant_bundles(
            (BundleConfig("caliburn.bundles.interview", {name: False}),)
        )
