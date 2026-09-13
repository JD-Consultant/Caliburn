"""Completed-window reference purpose isolation; no DB, provider or new table.

Window content reads and planning are a later slice. What this file pins down
is the boundary the B2 publication path depends on: a completed-window
reference must be validatable by the same source owner without ever becoming
usable as a current-turn source for C or the read tools.
"""
import hashlib
from uuid import uuid4

from caliburn_memory import MemoryArtifacts, PublicationStore
from caliburn_memory.sources import InvalidSourceReference
from itsdangerous import URLSafeSerializer
from langgraph.store.memory import InMemoryStore
import pytest
import sqlalchemy as sa
from sqlalchemy.pool import StaticPool

from jd_relational.conversation_sources import ConversationSourceError, _WindowPosition
from jd_relational.memory_sources import MemorySourceReader
from test_chat_history import native
from test_conversation_sources import KEY, seed, service


def window_ref(sources, document, *, first, last, first_run, last_run, root="root-checkpoint-1"):
    """Issue directly: the public issuing path belongs with the window planner."""
    position = _WindowPosition(format_version=1, purpose="window",
        dataset_id=sources.dataset_id, document_id=document, root_checkpoint_id=root,
        first=first, last=last, first_run_id=first_run, last_run_id=last_run)
    return sources._codec._issue_window(position)


@pytest.fixture
def issued(native):
    observed, _ = seed(native)
    _, dataset, document, *_ = native
    sources = service(native)
    run = observed.record.run_id
    source_ref = sources.capture(document, run).source_ref
    return sources, document, dataset, source_ref, window_ref(
        sources, document, first=run, last="this-run-reply", first_run=run, last_run=run)


def test_a_window_reference_is_never_accepted_as_a_current_turn_source(issued):
    sources, document, _, source_ref, window = issued
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"):
        sources.validate_reference(window, document)
    sources.validate_window_reference(window, document)


def test_a_turn_source_is_never_accepted_as_a_completed_window(issued):
    sources, document, _, source_ref, _ = issued
    sources.validate_reference(source_ref, document)
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"):
        sources.validate_window_reference(source_ref, document)


def test_the_two_purposes_share_the_codec_but_not_the_signature_domain(issued):
    sources, document, _, source_ref, window = issued
    source_domain = URLSafeSerializer(KEY, salt="caliburn.jd.conversation-source.v1",
        signer_kwargs={"digest_method": hashlib.sha256})
    with pytest.raises(Exception):
        source_domain.loads(window.split(":", 1)[1])


@pytest.mark.parametrize("change", ["key", "dataset", "document"])
def test_a_window_reference_from_another_owner_scope_is_rejected(native, issued, change):
    sources, document, dataset, _, window = issued
    other = service(native, key=b"another-synthetic-source-key-32bytes") if change == "key" \
        else service(native, dataset=str(uuid4())) if change == "dataset" else sources
    target = str(uuid4()) if change == "document" else document
    with pytest.raises(ConversationSourceError, match="^invalid_ref$"):
        other.validate_window_reference(window, target)


def test_the_memory_reader_validates_windows_only_when_the_owner_grants_them(issued):
    sources, document, _, source_ref, window = issued
    turn_only = MemorySourceReader(sources, document)
    with_windows = MemorySourceReader(sources, document, window_references=True)
    turn_only.validate_reference(source_ref)
    with_windows.validate_reference(source_ref)
    with pytest.raises(InvalidSourceReference):
        turn_only.validate_reference(window)
    with_windows.validate_reference(window)


def test_consolidation_publishes_its_completed_window_only_through_a_granting_reader(issued):
    sources, document, _, _, window = issued
    store = InMemoryStore()
    engine = sa.create_engine("sqlite://", connect_args={"check_same_thread": False},
                              poolclass=StaticPool)
    try:
        blocked = PublicationStore(engine, MemoryArtifacts(store, document,
            source=MemorySourceReader(sources, document)))
        blocked.setup()
        artifacts = MemoryArtifacts(store, document,
            source=MemorySourceReader(sources, document, window_references=True))
        publication = PublicationStore(engine, artifacts)
        version = artifacts.save_memory(knowledge="只做檢查。", guide="只做檢查")
        with pytest.raises(InvalidSourceReference):
            blocked.prepare(version, expected_revision=0, kind="consolidation",
                            processed_source=window)
        head = publication.publish(publication.prepare(version, expected_revision=0,
            kind="consolidation", processed_source=window))
        assert head.revision == 1 and head.processed_source == window
        assert publication.current().processed_source == window
    finally:
        engine.dispose()
