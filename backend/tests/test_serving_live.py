from langgraph.checkpoint.memory import MemorySaver

from app.graph_v3.serving import AGENT_NAME, build_live_agent, build_live_deps
from app.graph_v3.deps import LiveDbPersist
from app.services.knowledge.http_client import HttpIndexerClient
from app.graph_v3.llm import OpenRouterLlm


def test_build_live_deps_types():
    deps = build_live_deps()
    assert isinstance(deps.knowledge, HttpIndexerClient)
    assert isinstance(deps.persist, LiveDbPersist)
    assert isinstance(deps.llm, OpenRouterLlm)


def test_build_live_agent_has_name():
    # 用 MemorySaver 當 checkpointer 佔位（不需真 PG；只驗組裝）
    agent = build_live_agent(MemorySaver(), build_live_deps())
    assert agent.name == AGENT_NAME
