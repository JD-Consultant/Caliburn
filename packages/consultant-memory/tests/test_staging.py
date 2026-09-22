"""Real native staging distinguishes repairable content from unavailable evidence."""
import pytest
from deepagents.backends import StateBackend
from deepagents.middleware.filesystem import FilesystemState
from langgraph.graph import END, START, StateGraph
from langgraph.store.memory import InMemoryStore

from caliburn_memory.memory import MemoryArtifacts
from caliburn_memory.sources import InvalidSourceReference
from caliburn_memory.staging import PATHS, StagedMemoryValidationError, staged_texts
from conftest import ExampleSource


class StageState(FilesystemState):
    material: dict


def validate(artifacts, files):
    def seed(_state):
        StateBackend().upload_files([(PATHS[name], text.encode()) for name, text in files.items()])
        return {}
    graph = StateGraph(StageState).add_node("seed", seed)
    graph.add_node("validate", lambda _state: {"material": staged_texts(artifacts)})
    graph.add_edge(START, "seed").add_edge("seed", "validate").add_edge("validate", END)
    return graph.compile().invoke({"messages": []},
        {"configurable": {"thread_id": artifacts.document_id}})["material"]


def test_valid_staging_normalizes_generated_lines_without_publishing_or_changing_original():
    source, store = ExampleSource(), InMemoryStore()
    artifacts = MemoryArtifacts(store, source.document_id, source=source)
    original = source.material[source.reference]
    content = f"任務一\r\n[原話]({source.reference})"
    assert validate(artifacts, {"knowledge": content, "guide": "詳記\r\n工作範圍"}) == {
        "knowledge": content.replace("\r\n", "\n"), "guide": "詳記\n工作範圍"}
    assert source.material[source.reference] == original
    assert store.search(("q019-memory", source.document_id, "versions")) == []


@pytest.mark.parametrize("files,detail", [
    ({"knowledge": "已有工作"}, "Missing staged guide"),
    ({"knowledge": "已有工作", "guide": "  "}, "guide.md is empty"),
    ({"knowledge": "長" * 2001, "guide": "導覽"}, "line exceeds"),
    ({"knowledge": "工作", "guide": "短行\n" * 1400}, "guide exceeds"),
    ({"knowledge": "[案例](/interviews/missing/summary.md)", "guide": "導覽"}, "Invalid Memory reference"),
])
def test_known_content_error_is_correctable_and_has_no_saved_version(files, detail):
    artifacts = MemoryArtifacts(InMemoryStore(), "document-a")
    with pytest.raises(StagedMemoryValidationError, match=detail):
        validate(artifacts, files)
    assert artifacts.store.search(("q019-memory", artifacts.document_id, "versions")) == []


def test_typed_invalid_reference_is_correctable_without_source_diagnostic_leak():
    source = ExampleSource()
    def reject(_reference):
        raise InvalidSourceReference("private synthetic signature diagnostic")
    source.validate_reference = reject
    artifacts = MemoryArtifacts(InMemoryStore(), source.document_id, source=source)
    with pytest.raises(StagedMemoryValidationError, match="Invalid Memory reference") as caught:
        validate(artifacts, {"knowledge": source.reference, "guide": "導覽"})
    assert "private" not in str(caught.value)


@pytest.mark.parametrize("failure", [ValueError("private synthetic source diagnostic"),
                                     OSError("synthetic source unavailable")])
def test_unknown_source_failure_stops_instead_of_becoming_a_model_retry(failure):
    source = ExampleSource()
    def unavailable(_reference):
        raise failure
    source.read = unavailable
    artifacts = MemoryArtifacts(InMemoryStore(), source.document_id, source=source)
    with pytest.raises(type(failure)) as caught:
        validate(artifacts, {"knowledge": source.reference, "guide": "導覽"})
    assert not isinstance(caught.value, StagedMemoryValidationError)
    assert caught.value is failure or caught.value.__cause__ is failure
