"""CopilotKit serving for graph_v3.

Provides two paths: build_demo_sdk (MemorySaver + stub deps for tests/local);
build_live_deps/build_live_sdk (HttpIndexerClient + LiveDbPersist + OpenRouterLlm for app).
deps injected via LangGraphAGUIAgent(config={"configurable": {"deps": ...}})."""
from copilotkit import CopilotKitRemoteEndpoint, LangGraphAGUIAgent
from langgraph.checkpoint.memory import MemorySaver

from app.config import settings
from app.database import AsyncSessionLocal
from app.graph_v3.deps import Deps, LiveDbPersist
from app.graph_v3.graph import build_graph_v3
from app.graph_v3.llm import OpenRouterLlm
from app.graph_v3.stubs import InMemoryPersist, StubKnowledge
from app.services.knowledge.http_client import HttpIndexerClient

AGENT_NAME = "jd_authoring"


def build_demo_sdk() -> CopilotKitRemoteEndpoint:
    deps = Deps(knowledge=StubKnowledge(), persist=InMemoryPersist())
    graph = build_graph_v3(checkpointer=MemorySaver())
    agent = LangGraphAGUIAgent(
        name=AGENT_NAME,
        description="JD 撰寫顧問（v3 stub demo）",
        graph=graph,
        config={"configurable": {"deps": deps}},
    )
    return CopilotKitRemoteEndpoint(agents=[agent])


def build_live_deps() -> Deps:
    return Deps(
        knowledge=HttpIndexerClient(settings.indexer_base_url,
                                    settings.indexer_api_key,
                                    settings.indexer_timeout_s),
        persist=LiveDbPersist(AsyncSessionLocal),
        llm=OpenRouterLlm(),
    )


def build_live_sdk(checkpointer, deps) -> CopilotKitRemoteEndpoint:
    graph = build_graph_v3(checkpointer=checkpointer)
    agent = LangGraphAGUIAgent(
        name=AGENT_NAME,
        description="JD 撰寫顧問（v3 live）",
        graph=graph,
        config={"configurable": {"deps": deps}},
    )
    return CopilotKitRemoteEndpoint(agents=[agent])
