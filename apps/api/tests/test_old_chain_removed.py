import importlib

import pytest


@pytest.mark.parametrize(
    "mod",
    [
        "app.graph.graph",
        "app.graph.nodes.ocs_builder",
        "app.services.icap_retriever",
        "app.services.interview_orchestrator",
        "app.authoring.graph",
        "app.copilotkit_live_app",
        "app.interview",
        "app.interview_vnext",
        "app.job_authoring",
    ],
)
def test_removed_runtime_modules_are_gone(mod):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(mod)


def test_main_app_still_imports():
    import app.main

    assert app.main.app is not None
