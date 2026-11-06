"""離線 Agent 測試不繼承外部自訂標頭與遠端 trace 設定。"""

import pytest


@pytest.fixture(autouse=True)
def isolate_external_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_CUSTOM_HEADERS", raising=False)
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
