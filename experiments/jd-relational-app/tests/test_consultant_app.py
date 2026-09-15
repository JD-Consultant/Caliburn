"""The consultant the App assembles: method, Skills, tools and notices together.

Builds the real agent with the pinned OpenRouter/Luna runtime and a synthetic key.
Nothing here opens a socket, a document or a connection, and no request is made.
"""

import pytest

from jd_relational.background_admission import Admission
from jd_relational.background_availability import BackgroundAvailability
from jd_relational.consultant_app import build_consultant
from jd_relational.consultant_guidance import build_consultant_guidance
from jd_relational.consultant_model import create_consultant_model
from jd_relational.consultant_tools import AiToolMiddleware
from support.openrouter_replies import reply
from test_consultant_model import answering

DOCUMENT = "0d6de1cd-52e0-4b2f-9a19-5f0e86a2ed6a"
KEY = "synthetic-consultant-assembly-not-a-key"


@pytest.fixture
def model():
    """The real assembly on a local transport; nothing here invokes it."""
    with answering(reply("assembly")) as (value, _):
        yield value


class Admissions:
    def read(self, document_id):
        return Admission(document_id)


class Windows:
    def plan_saved_batch(self, target_reference, document_id, *, after_reference=None):
        return {"source_reference": None, "covers_whole_range": True}


TOOLS = {"jd_read", "jd_change_read", "jd_create_task", "jd_revise_work", "jd_set_text",
         "jd_insert_item", "jd_delete_item", "jd_move_item", "jd_set_task_capability",
         "jd_replace_selection", "ls", "grep", "read_file", "read_conversation",
         "repair_memory", "request_memory_consolidation"}


def _tools(agent):
    return set(agent.nodes["tools"].bound.tools_by_name)


def test_the_consultant_carries_its_method_skills_and_tools(model):
    agent = build_consultant(model)
    assert _tools(agent) == TOOLS
    # The two manual-only commands are never handed to the model.
    assert not {"restore_revision", "undo_ai_turn"} & _tools(agent)
    assert "SkillsMiddleware.before_agent" in agent.nodes


def test_background_availability_is_included_only_with_its_owners(model):
    without = build_consultant(model)
    assert not any("BackgroundAvailability" in node for node in without.nodes)
    with_background = build_consultant(model, admissions=Admissions(), windows=Windows())
    assert any("BackgroundAvailability" in node for node in with_background.nodes)
    assert _tools(with_background) == TOOLS


def test_partial_background_wiring_is_refused(model):
    with pytest.raises(ValueError) as error:
        build_consultant(model, admissions=Admissions())
    assert "incomplete_background_availability" in str(error.value)


def test_the_guidance_the_agent_gets_is_the_composed_one(model):
    guidance = build_consultant_guidance()
    assert "你是職務訪談顧問。" in guidance
    assert "## 這份 JD" in guidance
    assert "## Memory actions before the final reply" in guidance
    # Skills are mounted as middleware, never pasted into this text.
    assert "{skills_list}" not in guidance


def test_the_app_installs_the_tool_middleware_and_the_skills_middleware(model, monkeypatch):
    captured = {}
    import jd_relational.consultant_app as module

    def record(model_, *, tools, guidance, extra_middleware, context_middleware):
        captured["middleware"] = [type(item).__name__ for item in extra_middleware]
        captured["context_middleware"] = context_middleware
        captured["guidance"] = guidance
        return "agent"

    monkeypatch.setattr(module, "build_consultant_node", record)
    module.build_consultant(model, admissions=Admissions(), windows=Windows())
    assert captured["middleware"] == [AiToolMiddleware.__name__, "SkillsMiddleware",
                                      BackgroundAvailability.__name__]
    assert captured["context_middleware"] is None
    assert captured["guidance"] == build_consultant_guidance()


def test_the_optional_context_middleware_is_forwarded_as_a_separate_seam(
        model, monkeypatch):
    from jd_relational.response_context import native_context_view
    import jd_relational.consultant_app as module

    captured = {}

    def record(model_, *, tools, guidance, extra_middleware, context_middleware):
        captured["context_middleware"] = context_middleware
        captured["extra_middleware"] = tuple(extra_middleware)
        return "agent"

    monkeypatch.setattr(module, "build_consultant_node", record)
    assert module.build_consultant(
        model, context_middleware=native_context_view) == "agent"
    assert captured["context_middleware"] is native_context_view
    assert all(item is not native_context_view for item in captured["extra_middleware"])
