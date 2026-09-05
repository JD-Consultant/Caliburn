"""Do not allow environment tracing to turn offline fixtures into uploads."""

import pytest


@pytest.fixture(autouse=True)
def no_external_tracing(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_OPENAI_TCP_KEEPALIVE", "0")
