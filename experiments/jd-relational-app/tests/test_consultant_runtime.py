"""Formal process composition for the completed consultant; no model request."""

from jd_relational.openrouter_model import ReceiptChatOpenRouter
from jd_relational.consultant_runtime import open_consultant_runtime


def test_runtime_assembles_existing_tools_once_and_closes_owned_clients():
    runtime = open_consultant_runtime(api_key="synthetic-runtime-not-a-key")
    assert isinstance(runtime.role_models.consultant, ReceiptChatOpenRouter)
    assert isinstance(runtime.role_models.case, ReceiptChatOpenRouter)
    assert isinstance(runtime.role_models.understanding, ReceiptChatOpenRouter)
    tools = set(runtime.graph.nodes["tools"].bound.tools_by_name)
    assert {"jd_read", "jd_set_text", "repair_memory",
            "request_memory_consolidation"}.issubset(tools)
    assert any("BackgroundAvailability" in node for node in runtime.graph.nodes)
    assert not runtime.http_client.is_closed and not runtime.async_http_client.is_closed
    assert runtime.close() is True
    assert runtime.http_client.is_closed and runtime.async_http_client.is_closed
    assert runtime.close() is True, "closing the process-owned runtime is idempotent"
