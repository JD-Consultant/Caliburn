import pytest

from app.config import settings
from app.graph_v3 import llm as llm_mod
from app.graph_v3.deps import LlmPort


def test_model_for_role_maps_three_tiers():
    settings.model_deep = "vendor/deep"
    settings.model_indicator = "vendor/mid"
    settings.model_cheap = "vendor/cheap"
    assert llm_mod.model_for_role("deep") == "vendor/deep"
    assert llm_mod.model_for_role("indicator") == "vendor/mid"
    assert llm_mod.model_for_role("cheap") == "vendor/cheap"
    # 未知 role → 退回 cheap
    assert llm_mod.model_for_role("???") == "vendor/cheap"


def test_get_chat_llm_uses_openrouter_base_url():
    settings.openrouter_base_url = "https://openrouter.ai/api/v1"
    settings.openrouter_api_key = "sk-test"
    settings.model_indicator = "vendor/mid"
    llm_mod._build_chat.cache_clear()
    chat = llm_mod.get_chat_llm("indicator")
    # langchain_openai ChatOpenAI 暴露 model_name 與 openai_api_base
    assert chat.model_name == settings.model_indicator
    assert "openrouter.ai" in str(chat.openai_api_base)


def test_openrouter_llm_satisfies_port_and_parses_json():
    impl = llm_mod.OpenRouterLlm()
    assert isinstance(impl, LlmPort)  # runtime_checkable Protocol

    # 不打網路：覆寫 complete_text 驗 complete_json 解析路徑。
    # 注意 safe_parse_json 只吃「純 JSON」或「markdown ```json 圍欄」，不從雜訊抽 {...}。
    class _Stub(llm_mod.OpenRouterLlm):
        async def complete_text(self, prompt, *, role="cheap"):
            return '```json\n{"a": 1, "b": [2, 3]}\n```'

    import asyncio
    out = asyncio.run(_Stub().complete_json("p", role="indicator", default=None))
    assert out == {"a": 1, "b": [2, 3]}
