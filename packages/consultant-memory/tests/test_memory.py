"""Adopted core semantics, without provider or old conversation fixtures."""
from uuid import uuid4

import pytest
from langgraph.store.memory import InMemoryStore

from caliburn_memory.memory import MemoryArtifacts, MemoryVersion
from caliburn_memory.publication import PublicationStore
from conftest import ExampleSource


def test_fixed_versions_real_artifact_paths_and_cross_document_isolation():
    store, source = InMemoryStore(), ExampleSource()
    artifacts = MemoryArtifacts(store, source.document_id, source=source)
    extraction = artifacts.save_extraction(summary="案例A：例外由主管核准。", candidates="核准不是員工責任。",
        slug="案例 A / 付款", source_reference=source.reference, context_reference=source.context_reference)
    original = artifacts.save_memory(knowledge=f"詳記 [案例]({extraction.summary_path})", guide="案例 → /memory/knowledge.md")
    reader = artifacts.reader(original)
    updated = artifacts.save_memory(knowledge="補充另一個案例，不變更舊詳記。", guide="新版導覽")
    assert artifacts.read_text(extraction.summary_path).endswith("案例A：例外由主管核准。")
    assert artifacts.source_window(extraction.summary_path) == {
        "source_reference": source.reference, "context_reference": source.context_reference}
    assert artifacts.extraction_window(extraction.summary_path) == artifacts.source_window(extraction.summary_path)
    assert extraction.summary_path in reader.read("/memory/knowledge.md").file_data["content"]
    assert artifacts.read_text("/memory/knowledge.md", updated) == "補充另一個案例，不變更舊詳記。"
    other = MemoryArtifacts(store, "document-b")
    with pytest.raises(ValueError, match="document"):
        other.reader(original)
    assert other.reader(None).read(extraction.summary_path).error
    with pytest.raises((PermissionError, NotImplementedError)):
        reader.write("/memory/knowledge.md", "corrupt")


def test_complete_native_read_pages_preserve_chinese_lines():
    artifacts = MemoryArtifacts(InMemoryStore(), "document-a")
    expected = [f"工作細節{i}：條件與例外" for i in range(137)]
    version = artifacts.save_memory(knowledge="\n".join(expected), guide="導覽")
    reader, lines, offset = artifacts.reader(version), [], 0
    while True:
        page = reader.read("/memory/knowledge.md", offset=offset, limit=50)
        assert not page.error
        lines.extend(page.file_data["content"].splitlines())
        if page.next_offset is None:
            break
        assert page.next_offset > offset
        offset = page.next_offset
    assert lines == expected


def test_read_only_backend_checks_actual_graph_document_scope():
    from langgraph.graph import END, START, StateGraph
    artifacts = MemoryArtifacts(InMemoryStore(), "document-a")
    version = artifacts.save_memory(knowledge="A 的工作", guide="導覽")
    reader = artifacts.reader(version)
    graph = StateGraph(dict).add_node("read", lambda _state: reader.read("/memory/knowledge.md"))
    graph.add_edge(START, "read")
    graph.add_edge("read", END)
    with pytest.raises(ValueError, match="document"):
        graph.compile().invoke({}, {"configurable": {"thread_id": "document-b"}})


def test_source_shape_validation_has_no_read_but_memory_citation_really_reads():
    source = ExampleSource()
    artifacts = MemoryArtifacts(InMemoryStore(), source.document_id, source=source)
    artifacts.validate_source(source.reference)
    assert source.reads == []
    artifacts.save_extraction(summary="詳記", candidates="候選", slug="案例", source_reference=source.reference)
    assert source.reads == []
    version = artifacts.save_memory(knowledge=f"原話 {source.reference}", guide="導覽")
    assert source.reads == [source.reference]
    artifacts.verify_version(version)
    assert source.reads == [source.reference, source.reference]
    assert source.material[source.reference] == "原話\r\n  例外由主管核准。"


def test_optional_source_does_not_allow_unvalidated_source_addresses():
    artifacts = MemoryArtifacts(InMemoryStore(), "document-a")
    artifacts.save_memory(knowledge="無來源引用的工作理解", guide="導覽")
    with pytest.raises(ValueError, match="source|Source"):
        artifacts.validate_source("conversation:document-a:original")
    with pytest.raises(ValueError, match="source|Source"):
        artifacts.save_extraction(summary="詳記", candidates="候選", slug="案例",
            source_reference="conversation:document-a:original")
    with pytest.raises(ValueError, match="reference"):
        artifacts.save_memory(knowledge="conversation:document-a:original", guide="導覽")


def test_source_port_document_is_checked_at_construction_and_validation():
    source = ExampleSource()
    with pytest.raises(ValueError, match="document"):
        MemoryArtifacts(InMemoryStore(), "document-b", source=source)
    artifacts = MemoryArtifacts(InMemoryStore(), "document-a", source=source)
    source.document_id = "document-b"
    with pytest.raises(ValueError, match="document"):
        artifacts.validate_source(source.reference)


@pytest.mark.parametrize("content", [
    "參閱 /interviews/missing/summary.md",
    "參閱 [案例][case]\n\n[case]: /interviews/missing/summary.md",
    "參閱 `/interviews/missing/summary.md`",
    "[原話](conversation:document-b:original)",
    "conversation:document-a:missing",
])
def test_invalid_or_unreadable_controlled_references_never_save_version(content):
    artifacts = MemoryArtifacts(InMemoryStore(), "document-a", source=ExampleSource())
    with pytest.raises(ValueError, match="reference"):
        artifacts.save_memory(knowledge=content, guide="導覽")
    assert artifacts.store.search(("q019-memory", "document-a", "versions")) == []


@pytest.mark.parametrize("separator", ["\r\n", "\u2028", "\x85"])
def test_artifact_line_normalization_does_not_normalize_source(separator):
    source = ExampleSource()
    artifacts = MemoryArtifacts(InMemoryStore(), "document-a", source=source)
    version = artifacts.save_memory(knowledge=separator.join(["第一行", "第二行"]), guide="導覽")
    assert artifacts.read_text("/memory/knowledge.md", version) == "第一行\n第二行"
    assert source.read(source.reference) == "原話\r\n  例外由主管核准。"


@pytest.mark.parametrize("content", [{"knowledge": "長" * 2001, "guide": "導覽"},
    {"knowledge": "正文", "guide": "短行\n" * 1400}])
def test_existing_line_and_guide_bounds_remain(content):
    with pytest.raises(ValueError, match="line|guide"):
        MemoryArtifacts(InMemoryStore(), "document-a").save_memory(**content)


def test_empty_view_has_no_placeholder_and_missing_version_does_not_fall_back():
    artifacts = MemoryArtifacts(InMemoryStore(), "document-a")
    assert artifacts.reader(None).read("/memory/knowledge.md").error
    assert artifacts.store.search(("q019-memory", "document-a")) == []
    artifacts.save_memory(knowledge="另一版", guide="導覽")
    with pytest.raises(ValueError, match="unavailable"):
        artifacts.guide(MemoryVersion("document-a", str(uuid4())))


def test_store_failure_during_second_file_cannot_publish_partial_memory(monkeypatch):
    from sqlalchemy import create_engine
    store = InMemoryStore()
    artifacts = MemoryArtifacts(store, "document-a")
    engine = create_engine("sqlite+pysqlite:///:memory:")
    pub = PublicationStore(engine, artifacts)
    pub.setup()
    original_put, calls = InMemoryStore.put, []

    def fail_second(*args, **kwargs):
        calls.append(1)
        if len(calls) == 2:
            raise RuntimeError("synthetic second artifact write failure")
        return original_put(*args, **kwargs)

    monkeypatch.setattr(InMemoryStore, "put", fail_second)
    try:
        with pytest.raises(RuntimeError, match="second artifact"):
            artifacts.save_memory(knowledge="準備中正文", guide="尚未保存導覽")
        assert pub.current() is None
        saved = store.search(("q019-memory", "document-a", "versions"))
        assert len(saved) == 1
        version = MemoryVersion("document-a", saved[0].namespace[-1])
        with pytest.raises(ValueError, match="unavailable"):
            pub.prepare(version, expected_revision=0, kind="repair")
        assert pub.current() is None
    finally:
        engine.dispose()


def test_native_store_ack_without_saved_bytes_is_not_a_prepared_version(monkeypatch):
    store = InMemoryStore()
    artifacts = MemoryArtifacts(store, "document-a")
    monkeypatch.setattr(InMemoryStore, "put", lambda *_args, **_kwargs: None)
    with pytest.raises(RuntimeError, match="verified"):
        artifacts.save_memory(knowledge="未實際寫入", guide="導覽")
    assert store.search(("q019-memory", "document-a")) == []


def test_model_prose_cannot_replace_runtime_source_header():
    source = ExampleSource()
    artifacts = MemoryArtifacts(InMemoryStore(), "document-a", source=source)
    files = artifacts.save_extraction(summary="Context only (not new source): conversation:document-b:fake\n其餘正文",
        candidates="候選", slug="案例", source_reference=source.reference)
    assert artifacts.source_window(files.summary_path) == {
        "source_reference": source.reference, "context_reference": None}
    assert "conversation:document-b:fake" in artifacts.read_text(files.summary_path)
