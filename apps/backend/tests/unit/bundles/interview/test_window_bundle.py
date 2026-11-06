"""窗口適配可透過正式 Bundle 載入，不由 Host 猜測業務開關。"""

import asyncio

from langgraph.runtime import Runtime

from caliburn.bundles.context.services import COMPLETED_TURNS, WINDOW_CONTRIBUTIONS
from caliburn.bundles.interview.services import INTERVIEW_QUERIES, MODEL_REFERENCES
from caliburn.modules.agent.bootstrap import BundleConfig, load_plugins
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.plugins.services import PluginServices


def test_window_adapter_exposes_contribution_and_required_recording() -> None:
    (plugin,) = load_plugins([BundleConfig("caliburn.bundles.interview.window")])
    assert plugin.name == "interview_window"
    assert plugin.required_plugins == ("interview",)
    assert set(plugin.required_services) == {
        INTERVIEW_QUERIES,
        MODEL_REFERENCES,
        COMPLETED_TURNS,
    }
    assert plugin.provided_services == (WINDOW_CONTRIBUTIONS,)
    assert not plugin.on_turn_start
    assert not plugin.tools


def test_read_only_window_does_not_require_recording_or_completed_history() -> None:
    (plugin,) = load_plugins(
        [
            BundleConfig(
                "caliburn.bundles.interview.window",
                {"preload": False, "include_input_reference": False},
            )
        ]
    )
    assert not plugin.required_plugins
    assert set(plugin.required_services) == {INTERVIEW_QUERIES, MODEL_REFERENCES}


def test_history_only_adapter_does_not_claim_the_single_input_owner() -> None:
    (plugin,) = load_plugins(
        [
            BundleConfig(
                "caliburn.bundles.interview.window",
                {"include_input_reference": False, "include_navigation": False},
            )
        ]
    )

    async def run() -> None:
        assert plugin.open_services is not None
        async with plugin.open_services(PluginServices({})) as bindings:
            (binding,) = bindings
            assert binding.key is WINDOW_CONTRIBUTIONS
            (contribution,) = binding.value
            assert contribution.prepare_input is None
            assert (
                await contribution.prepare(
                    {},
                    previous={},
                    rebuilding=False,
                    runtime=Runtime(context=AgentContext(PluginServices({}))),
                )
                == {}
            )

    asyncio.run(run())
