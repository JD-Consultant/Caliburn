import importlib
import pytest


@pytest.mark.parametrize("mod", [
    # 舊 graph 鏈(Concern B 退場)
    "app.graph.graph",
    "app.graph.nodes.ocs_builder",
    "app.services.icap_retriever",
    "app.services.icap_matcher",
    "app.services.interview_orchestrator",
    "app.services.state_service",
    "app.api.routes.interviews",
    # LangGraph/CopilotKit 鏈(T12;ADR 0030 D″):一個大腦=訪談引擎
    "app.authoring.graph",
    "app.authoring.serving",
    "app.authoring.tracing",
    "app.copilotkit_live_app",
    # v1 訪談死碼(op→verify→_pending 取代;判準已回收 skills/)
    "app.interview.executor",
    "app.interview.commands",
    "app.interview.context",
])
def test_old_modules_are_gone(mod):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(mod)


def test_main_app_still_imports():
    import app.main
    assert app.main.app is not None
