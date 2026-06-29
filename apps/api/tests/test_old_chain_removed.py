import importlib
import pytest


@pytest.mark.parametrize("mod", [
    "app.graph.graph",
    "app.graph.nodes.ocs_builder",
    "app.services.icap_retriever",
    "app.services.icap_matcher",
    "app.services.interview_orchestrator",
    "app.services.state_service",
    "app.api.routes.interviews",
])
def test_old_modules_are_gone(mod):
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(mod)


def test_main_app_still_imports():
    import app.main
    assert app.main.app is not None


def test_kept_pure_data_lives_in_authoring():
    from app.authoring.constants import TASK_COMPLETENESS_FIELDS  # noqa: F401
    import app.authoring.prompts.indicator  # noqa: F401
