"""CopilotKit serving for graph_v3 (stub-first demo).

probe-grounded（copilotkit 0.1.94）：CopilotKitRemoteEndpoint(agents=[LangGraphAGUIAgent(...)])。
deps 經 LangGraphAGUIAgent(config=...) 注入（透到 node 的 config["configurable"]["deps"]）。
demo 用 MemorySaver + stub deps；真 PostgresSaver/HttpIndexerClient/DbPersist 留後續 phase。"""
from copilotkit import CopilotKitRemoteEndpoint, LangGraphAGUIAgent
from langgraph.checkpoint.memory import MemorySaver

from app.graph_v3.deps import Deps
from app.graph_v3.graph import build_graph_v3
from app.graph_v3.stubs import InMemoryPersist, StubKnowledge

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
