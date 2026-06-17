"""AG-UI serving for graph_v3 (D22).

Serves the graph over the AG-UI protocol via ag-ui-langgraph (replaces the
legacy copilotkit CopilotKitRemoteEndpoint, which is incompatible with new
CopilotKit JS useAgent — see decision-log D22 / CopilotKit #2898).

Two paths: build_demo_agent (MemorySaver + stub deps, tests/local) and
build_live_deps/build_live_agent (HttpIndexerClient + LiveDbPersist +
OpenRouterLlm). deps injected via LangGraphAgent(config={"configurable": {"deps": ...}}).
Apps mount an agent with add_langgraph_fastapi_endpoint(app, agent, "/copilotkit")."""
from ag_ui_langgraph import LangGraphAgent
from langgraph.checkpoint.memory import MemorySaver

from app.config import settings
from app.database import AsyncSessionLocal
from app.graph_v3.deps import Deps, LiveDbPersist
from app.graph_v3.graph import build_graph_v3
from app.graph_v3.llm import OpenRouterLlm
from app.graph_v3.stubs import InMemoryPersist, StubKnowledge
from app.services.knowledge.http_client import HttpIndexerClient

AGENT_NAME = "jd_authoring"


def build_demo_agent() -> LangGraphAgent:
    deps = Deps(knowledge=StubKnowledge(), persist=InMemoryPersist())
    return LangGraphAgent(
        name=AGENT_NAME,
        description="JD 撰寫顧問（v3 stub demo）",
        graph=build_graph_v3(checkpointer=MemorySaver()),
        config={"configurable": {"deps": deps}},
    )


def build_live_deps() -> Deps:
    return Deps(
        knowledge=HttpIndexerClient(settings.indexer_base_url,
                                    settings.indexer_api_key,
                                    settings.indexer_timeout_s),
        persist=LiveDbPersist(AsyncSessionLocal),
        llm=OpenRouterLlm(),
    )


def build_live_agent(checkpointer, deps) -> LangGraphAgent:
    return LangGraphAgent(
        name=AGENT_NAME,
        description="JD 撰寫顧問（v3 live）",
        graph=build_graph_v3(checkpointer=checkpointer),
        config={"configurable": {"deps": deps}},
    )
