"""JD 的提示、工具與流程可獨立選取，仍沿同一正式請求初始化器。"""

import asyncio

import httpx2
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from openai.types.responses.response_create_params import ResponseCreateParamsBase

from caliburn.bundles.job_description import create_bundle
from caliburn.bundles.job_description.instructions import JD_INSTRUCTIONS
from caliburn.modules.agent.bootstrap import BundleConfig, load_plugins, open_agent
from caliburn.modules.agent.infrastructure.openai.request_initialization import (
    OpenAIRequestInitializer,
)
from caliburn.modules.agent.plugins.contracts import AgentBundle, AgentPlugin
from caliburn.modules.agent.plugins.services import ServiceBinding
from tests.unit.modules.agent.offline_openai import MODEL_REQUEST, offline_client


def request_for(plugins: tuple[AgentPlugin, ...]) -> ResponseCreateParamsBase:
    initializer = OpenAIRequestInitializer(
        MODEL_REQUEST,
        tuple(tool for plugin in plugins for tool in plugin.tools),
        tuple(section for plugin in plugins for section in plugin.prompt_sections),
    )
    return initializer.initialize({"turn_input": "讀取目前 JD"})["model_request"]


def test_replacing_prompt_preserves_tool_declarations_and_lifecycle() -> None:
    original = create_bundle({}).plugins
    replacement = AgentPlugin(name="alternate_jd_prompt", prompt_sections=("替代提示",))
    selected = load_plugins(
        (
            BundleConfig(
                "caliburn.bundles.job_description",
                plugins=tuple(
                    plugin.name for plugin in original if not plugin.prompt_sections
                ),
            ),
        )
    )
    baseline = request_for(original)
    changed = request_for((*selected, replacement))

    assert changed["tools"] == baseline["tools"]
    assert len(list(changed["tools"])) == 8
    assert changed["instructions"] == "替代提示"
    assert JD_INSTRUCTIONS in str(baseline["instructions"])
    assert any(plugin.on_turn_start for plugin in selected)
    assert any(plugin.on_turn_end for plugin in selected)
    assert any(plugin.on_turn_cancel for plugin in selected)


def test_disabling_manual_changes_preserves_tools_and_turn_capture() -> None:
    original = create_bundle({}).plugins
    selected = load_plugins(
        (
            BundleConfig(
                "caliburn.bundles.job_description",
                plugins=tuple(
                    plugin.name for plugin in original if not plugin.before_model_step
                ),
            ),
        )
    )

    assert request_for(selected)["tools"] == request_for(original)["tools"]
    assert any(plugin.on_turn_start for plugin in selected)
    assert any(plugin.on_turn_end for plugin in selected)
    assert any(plugin.on_turn_cancel for plugin in selected)


@pytest.mark.parametrize(
    ("selected", "required"),
    [
        ("job_description_tools", "job_description"),
        ("job_description_changes", "job_description"),
        ("job_description_context", "job_description"),
        ("job_description_prompt", "job_description_tools"),
    ],
)
def test_missing_required_plugin_is_rejected_before_execution(
    selected: str, required: str
) -> None:
    plugins = load_plugins(
        (BundleConfig("caliburn.bundles.job_description", plugins=(selected,)),)
    )
    # 本例只核啟動依賴；提供佔位服務以排除無關的缺服務拒絕，不執行業務。
    bindings = tuple(
        ServiceBinding(key, object()) for key in plugins[0].required_services
    )

    def unexpected(request: httpx2.Request) -> httpx2.Response:
        pytest.fail("無效 Plugin 組裝不應呼叫模型")

    async def run() -> None:
        async with offline_client(httpx2.MockTransport(unexpected)) as client:
            with pytest.raises(ValueError, match=required):
                async with open_agent(
                    agent_id="jd-composition",
                    resume_version="v1",
                    client=client,
                    model_settings=MODEL_REQUEST,
                    bundles=(AgentBundle(plugins),),
                    checkpointer=InMemorySaver(),
                    external_services=bindings,
                ):
                    pytest.fail("缺少輪次／工具依賴仍允許啟動")

    asyncio.run(run())
