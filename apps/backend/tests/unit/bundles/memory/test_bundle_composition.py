"""Memory 的 Prompt 可單獨選用，不攜帶工具、資料注入或背景工作。"""

import pytest

from caliburn.bundles.memory import create_bundle


@pytest.mark.parametrize("role", ["consultant", "situation", "understanding"])
def test_role_prompt_is_independent_of_business_capabilities(role: str) -> None:
    bundle = create_bundle({"role": role})
    (prompt,) = [plugin for plugin in bundle.plugins if plugin.prompt_sections]
    assert prompt.name == (
        "memory_prompt" if role == "consultant" else f"memory_{role}_prompt"
    )
    assert not prompt.tools
    assert not prompt.required_services
    assert not prompt.provided_services
    assert prompt.open_services is None
    assert prompt.state_schema is None
    assert not prompt.on_turn_start
    assert not prompt.before_model_step
    assert not prompt.on_turn_end
    assert prompt.on_turn_cancel is None
