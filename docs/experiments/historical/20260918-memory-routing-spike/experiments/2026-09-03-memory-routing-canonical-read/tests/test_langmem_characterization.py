from __future__ import annotations

import json

import pytest


def test_langmem_search_helper_exposes_broader_schema_and_store_item_view() -> None:
    """Characterizes why the public helper is not the approved one-field read contract."""
    pytest.importorskip("langmem")
    from langmem import create_search_memory_tool
    from langgraph.store.memory import InMemoryStore

    store = InMemoryStore(
        index={
            "dims": 2,
            "embed": lambda texts: [[1.0, 0.0] for _ in texts],
            "fields": ["title", "content"],
        }
    )
    store.put(
        ("semantic-memory",),
        "memory-a",
        {"title": "A 案", "content": "三間分店"},
    )
    tool = create_search_memory_tool(namespace=("semantic-memory",), store=store)
    schema = tool.args_schema.model_json_schema()

    assert set(schema["properties"]) == {"query", "limit", "offset", "filter"}
    assert "memories" not in schema["properties"]

    result = json.loads(tool.invoke({"query": "分店"}))
    assert len(result) == 1
    assert result[0]["namespace"] == ["semantic-memory"]
    assert result[0]["key"] == "memory-a"
    assert result[0]["value"] == {"title": "A 案", "content": "三間分店"}
    assert set(result[0]) == {
        "namespace",
        "key",
        "value",
        "created_at",
        "updated_at",
        "score",
    }
