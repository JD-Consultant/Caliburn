"""AG-UI serving for authoring (D22).

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
from app.adapters.persistence import LiveDbPersist
from app.authoring.deps import Deps
from app.authoring.graph import build_graph
from app.adapters.llm_openrouter import OpenRouterLlm
from app.adapters.stubs import InMemoryPersist, StubKnowledge
from app.adapters.knowledge_http import HttpIndexerClient

AGENT_NAME = "jd_authoring"


def build_demo_agent() -> LangGraphAgent:
    deps = Deps(knowledge=StubKnowledge(), persist=InMemoryPersist())
    return LangGraphAgent(
        name=AGENT_NAME,
        description="JD 撰寫顧問（stub demo）",
        graph=build_graph(checkpointer=MemorySaver()),
        config={"configurable": {"deps": deps}},
    )


def build_live_deps() -> Deps:
    # 沒設 OPENROUTER_API_KEY 就不建 LLM：深問/收尾節點對 llm=None 優雅降級
    # （STAR 保留原答、indicator force_accepted），可全程 interrupt 驅動測完整流程，
    # 且免去注定失敗的 API 呼叫 retry+backoff。
    llm = OpenRouterLlm() if settings.openrouter_api_key else None
    return Deps(
        knowledge=HttpIndexerClient(settings.indexer_base_url,
                                    settings.indexer_api_key,
                                    settings.indexer_timeout_s),
        persist=LiveDbPersist(AsyncSessionLocal),
        llm=llm,
    )


def build_live_agent(checkpointer, deps) -> LangGraphAgent:
    return LangGraphAgent(
        name=AGENT_NAME,
        description="JD 撰寫顧問（live）",
        graph=build_graph(checkpointer=checkpointer),
        config={"configurable": {"deps": deps}},
    )
