"""Candidate-free recovery metadata validation; no database or worker proof."""

from dataclasses import asdict, replace
from types import SimpleNamespace
from uuid import UUID

import pytest

from jd_relational.intents import AdmittedIdentity, IntentValidationError
from jd_relational.storage.service import JdReader, JdStorage, StorageError


def identity():
    return AdmittedIdentity("synthetic-doc", UUID("10000000-0000-4000-8000-000000000001"),
        UUID("20000000-0000-4000-8000-000000000001"), "manual", None, "a" * 64, "jd_set_text")


INVALID_FIELDS = [
    ("document_id", ""), ("document_id", "  "), ("document_id", None),
    ("document_id", "contains\x00nul"), ("document_id", "\ud800"),
    ("operation_id", "10000000-0000-4000-8000-000000000001"), ("operation_id", True),
    ("base_revision_id", None), ("base_revision_id", False),
    ("origin", "unknown"), ("origin", []), ("origin", "ai"),
    ("ai_run_id", "unrelated-manual-run"),
    ("request_digest", "A" * 64), ("request_digest", "g" * 64),
    ("request_digest", "a" * 63), ("request_digest", None),
    ("command_kind", "jd_unknown"), ("command_kind", []),
]


@pytest.mark.parametrize("field,value", INVALID_FIELDS)
def test_reloaded_identity_rejects_invalid_fields(field, value):
    with pytest.raises(IntentValidationError, match="invalid_input"):
        replace(identity(), **{field: value})


@pytest.mark.parametrize("value", ["", "  ", 42, "\ud800", "contains\x00nul"])
def test_ai_identity_requires_readable_nonempty_run(value):
    with pytest.raises(IntentValidationError, match="invalid_input"):
        replace(identity(), origin="ai", ai_run_id=value)


def forbidden(*args, **kwargs):
    pytest.fail("Rejected identity cannot reach writer authority or SQL.")


def disconnected_store():
    engine = SimpleNamespace(dialect=SimpleNamespace(name="postgresql", driver="psycopg"), connect=forbidden)
    authority = SimpleNamespace(require_bound=forbidden, require_stopped=forbidden)
    return JdStorage(engine, authority)


@pytest.mark.parametrize("field,value", INVALID_FIELDS)
def test_storage_revalidates_identity_before_authority_or_sql(field, value):
    corrupted = identity()
    object.__setattr__(corrupted, field, value)  # Simulate a loader bypassing dataclass initialization.
    with pytest.raises(StorageError, match="invalid_input"):
        disconnected_store().reconcile_stopped(corrupted)


@pytest.mark.parametrize("value", [None, {}, True])
def test_storage_rejects_untyped_identity_before_authority_or_sql(value):
    with pytest.raises(StorageError, match="invalid_input"):
        disconnected_store().reconcile_stopped(value)


def test_identity_rejects_extra_candidate_material():
    with pytest.raises(TypeError):
        AdmittedIdentity(**asdict(identity()), context={})


def test_writer_adapter_requires_authority_even_when_reader_does_not():
    engine = SimpleNamespace(dialect=SimpleNamespace(name="postgresql", driver="psycopg"), connect=forbidden)
    assert isinstance(JdReader(engine), JdReader)
    for authority in (None, SimpleNamespace(require_bound=forbidden)):
        with pytest.raises(ValueError, match="WriterAuthority is required"):
            JdStorage(engine, authority)
