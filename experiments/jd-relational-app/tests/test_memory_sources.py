"""One source owner serves Memory; native in-memory checkpoints, zero provider/DB."""
import base64
from dataclasses import FrozenInstanceError
import json
from uuid import uuid4

from caliburn_memory.memory import MemoryArtifacts
from caliburn_memory.references import controlled_references
from caliburn_memory.sources import InvalidSourceReference, SourceReader
from langgraph.store.memory import InMemoryStore
import pytest

from jd_relational.conversation_sources import ConversationSourceError, _json
from jd_relational.memory_sources import MemorySourceReader
from test_chat_history import native
from test_conversation_sources import seed, serializer, service


PREFIX = "conversation:"


def test_new_reference_is_found_by_commonmark_and_used_by_memory_core(native):
    observed, _ = seed(native)
    _, _, document, *_ = native
    source = service(native)
    excerpt = source.capture(document, observed.record.run_id)
    assert excerpt.source_ref.startswith(PREFIX)
    text = f"只確認合約內设备。\n\n[本次原話]({excerpt.source_ref})"
    assert controlled_references(text) == {excerpt.source_ref}
    reader: SourceReader = MemorySourceReader(source, document)
    artifacts = MemoryArtifacts(InMemoryStore(), document, source=reader)
    version = artifacts.save_memory(knowledge=text, guide="工作範圍見正文。")
    assert artifacts.read_text("/memory/knowledge.md", version) == text
    files = artifacts.save_extraction(summary="合成詳記", candidates="合成候選", slug="合成",
                                     source_reference=excerpt.source_ref)
    assert artifacts.source_window(files.summary_path)["source_reference"] == excerpt.source_ref
    assert reader.read(excerpt.source_ref) == excerpt


def test_previously_saved_bare_signed_v1_is_read_without_rewriting(native):
    observed, _ = seed(native)
    _, _, document, *_ = native
    source = service(native)
    excerpt = source.capture(document, observed.record.run_id)
    bare = excerpt.source_ref.removeprefix(PREFIX)
    assert not bare.startswith(PREFIX)
    prior = source.read(bare, document)
    assert prior.source_ref == bare and prior.messages == excerpt.messages
    assert source.resolve(bare, document).readable
    source.validate_reference(bare, document)
    assert MemorySourceReader(source, document).read(bare) == prior


def test_validation_checks_signature_and_scope_without_saver_or_body_read(native, monkeypatch):
    observed, _ = seed(native)
    graph, _, document, *_ = native
    source = service(native)
    token = source.capture(document, observed.record.run_id).source_ref
    def never(*args, **kwargs): pytest.fail("shape/scope validation must not read native storage")
    monkeypatch.setattr(graph, "get_state", never)
    monkeypatch.setattr(source, "read", never)
    reader = MemorySourceReader(source, document)
    assert source.validate_reference(token, document) is None
    assert reader.validate_reference(token) is None
    assert reader.validate_reference(token.removeprefix(PREFIX)) is None
    payload = serializer().loads(token.removeprefix(PREFIX))
    # A valid signed position is only a locator: existence remains read()'s job.
    absent = serializer().dumps(payload | {"root_checkpoint_id": "absent",
                                          "source_checkpoint_id": "absent"})
    assert reader.validate_reference(PREFIX + absent) is None
    with pytest.raises(InvalidSourceReference, match="^invalid_source_reference$"):
        MemorySourceReader(source, str(uuid4())).validate_reference(token)


@pytest.mark.parametrize("fault", ["unsigned-v0", "double-prefix", "unknown-prefix", "tamper", "long"])
def test_memory_reader_rejects_untrusted_reference_before_storage(native, monkeypatch, fault):
    observed, _ = seed(native)
    graph, _, document, *_ = native
    source = service(native)
    token = source.capture(document, observed.record.run_id).source_ref
    if fault == "unsigned-v0":
        old = {"document": document, "checkpoint": "old", "first": "first", "last": "last"}
        token = PREFIX + base64.urlsafe_b64encode(json.dumps(old).encode()).decode().rstrip("=")
    elif fault == "double-prefix": token = PREFIX + token
    elif fault == "unknown-prefix": token = "other:" + token.removeprefix(PREFIX)
    elif fault == "tamper": token = token[:-8] + ("A" if token[-8] != "A" else "B") + token[-7:]
    elif fault == "long": token = PREFIX + "x" * (4097 - len(PREFIX))
    def never(*args, **kwargs): pytest.fail("invalid reference must not read native storage")
    monkeypatch.setattr(graph, "get_state", never)
    reader = MemorySourceReader(source, document)
    for action in (reader.validate_reference, reader.read):
        with pytest.raises(InvalidSourceReference, match="^invalid_source_reference$"):
            action(token)


def test_prefix_counts_toward_uncompressed_admission_and_keeps_bare_v1_limit(native):
    observed, _ = seed(native)
    _, _, document, *_ = native
    source = service(native)
    original = source.capture(document, observed.record.run_id).source_ref
    payload = serializer().loads(original.removeprefix(PREFIX))
    # Find a schema-valid, highly compressible position just inside the old raw
    # limit but outside the new prefixed limit. No database existence claim.
    candidates = (payload | {"first": "字" * 512, "root_checkpoint_id": "x" * 256,
        "source_checkpoint_id": "x" * 256, "source_namespace": "consultant:" + "字" * n}
        for n in range(247))
    candidate = next(value for value in candidates
        if 4096 - len(PREFIX) < (4 * len(_json(value).encode()) + 2) // 3 + 44 <= 4096)
    bare = serializer().dumps(candidate)
    assert len(PREFIX + bare) < 4096  # Compression must not bypass raw admission.
    source.validate_reference(bare, document)
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"):
        source.validate_reference(PREFIX + bare, document)


def test_reader_keeps_one_fixed_document_and_delegates_exact_original_reference(native, monkeypatch):
    observed, _ = seed(native)
    _, _, document, *_ = native
    source = service(native)
    excerpt = source.capture(document, observed.record.run_id)
    calls = []
    def read(reference, scope):
        calls.append((reference, scope))
        return excerpt
    monkeypatch.setattr(source, "read", read)
    reader = MemorySourceReader(source, document)
    assert reader.read(excerpt.source_ref) is excerpt
    assert calls == [(excerpt.source_ref, document)]
    with pytest.raises((FrozenInstanceError, AttributeError)):
        reader.document_id = str(uuid4())
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"):
        MemorySourceReader(source, "not-document")


@pytest.mark.parametrize("operation", ["read", "validate_reference"])
@pytest.mark.parametrize("failure", [ConversationSourceError("source_not_available"),
                                     ValueError("private synthetic source failure"),
                                     OSError("synthetic storage failure")])
def test_memory_source_adapter_does_not_reclassify_source_failures(native, monkeypatch, operation, failure):
    observed, _ = seed(native)
    _, _, document, *_ = native
    source = service(native)
    reference = source.capture(document, observed.record.run_id).source_ref
    def fail(*_args, **_kwargs):
        raise failure
    monkeypatch.setattr(source, operation, fail)
    with pytest.raises(type(failure)) as caught:
        getattr(MemorySourceReader(source, document), operation)(reference)
    assert caught.value is failure
    assert not isinstance(caught.value, InvalidSourceReference)
