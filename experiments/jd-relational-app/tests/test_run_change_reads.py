"""Fixed captured-range public projection. SQL/native/HTTP tested separately."""
from dataclasses import replace
from types import SimpleNamespace
from uuid import uuid4

import pytest

from jd_relational.references import ReferenceCodec, ReferenceValidationError, RunChangeCursor, SignedReference
from jd_relational.reads import ReadError
from jd_relational.run_change_reads import RunChangeReadService
from jd_relational.storage.history import HistoryError, RunChangeMaterial, _verified_revision
from test_run_change_material import DOCUMENT, receipt, revision_row


RUN = str(uuid4())
SECRET = b"synthetic-run-read-key-with-32-bytes"


def setup(*, settled=False, continuity="continuous", text="每月核對合約內服務紀錄。"):
    first, second = revision_row(1), revision_row(2, text=text, run_id=RUN)
    operations = () if continuity == "none" else (receipt(second),)
    material = RunChangeMaterial(continuity, operations,
        _verified_revision(first) if continuity == "continuous" else None,
        _verified_revision(second) if continuity == "continuous" else None)
    calls = []
    def read(document, run, ids):
        calls.append((document, run, ids))
        return material
    codec = ReferenceCodec(SECRET, str(uuid4()))
    reader = RunChangeReadService(SimpleNamespace(read_run_change=read), codec, page_bytes=4096)
    capture = RunChangeCursor.capture(DOCUMENT, RUN, tuple(row.operation_id for row in operations), settled)
    return reader, capture, material, calls


def test_full_pagination_keeps_original_capture_and_has_no_operation_alias():
    reader, capture, material, calls = setup()
    page = reader.read(DOCUMENT, RUN, captured=capture)
    original = page
    records, seen = list(page["records"]), set()
    while page["next_cursor"]:
        cursor = page["next_cursor"]
        assert cursor not in seen
        seen.add(cursor)
        page = reader.read(DOCUMENT, RUN, cursor=cursor)
        assert page["capture_ref"] == original["capture_ref"]
        assert page["effects_state"] == "unconfirmed"
        assert page["start_index"] == len(records)
        records.extend(page["records"])
    assert seen and len(records) == original["total_records"]
    assert original["total_changes"] == 1 and original["captured_operation_count"] == 1
    assert all(ids == capture.operation_ids for _, _, ids in calls)
    assert "operation_ref" not in page and "change_ref" not in page
    assert {row["side"] for row in records if row["type"] == "value"} == {"before", "after"}
    for side in ("base", "result"):
        revision = getattr(material, side)
        assert page[f"{side}_revision_ref"] == reader.codec.issue(SignedReference(
            document_id=DOCUMENT, revision_id=str(revision.revision_id),
            purpose="history", role="revision", kind="revision"))


@pytest.mark.parametrize("continuity,settled,count", [("none", False, 0), ("none", True, 0),
                                                   ("discontinuous", True, 1)])
def test_none_and_discontinuous_do_not_invent_net_diff(continuity, settled, count):
    reader, capture, _, _ = setup(settled=settled, continuity=continuity)
    page = reader.read(DOCUMENT, RUN, captured=capture)
    assert page["continuity"] == continuity
    assert page["captured_operation_count"] == count
    assert page["effects_state"] == ("settled" if settled else "unconfirmed")
    assert page["base_revision_ref"] is page["result_revision_ref"] is None
    assert page["records"] == [] and page["total_changes"] == page["total_records"] == 0
    assert page["next_cursor"] is None and not page["has_more"]


def test_same_content_after_saved_change_still_has_capture_and_endpoint_identity():
    reader, _, _, _ = setup(settled=True)
    initial = revision_row(1)
    middle = revision_row(2, text="暫時的敘述", run_id=RUN)
    final = revision_row(3, text=None, run_id=RUN)
    receipts = (receipt(middle), receipt(final))
    reader.history.read_run_change = lambda *args: RunChangeMaterial("continuous", receipts,
        _verified_revision(initial), _verified_revision(final))
    capture = RunChangeCursor.capture(DOCUMENT, RUN, tuple(row.operation_id for row in receipts), True)
    page = reader.read(DOCUMENT, RUN, captured=capture)
    assert page["continuity"] == "continuous" and page["captured_operation_count"] == 2
    assert page["total_changes"] == 0 and page["records"] == []
    assert page["base_revision_ref"] != page["result_revision_ref"]


def test_cursor_cannot_be_swapped_to_other_run_or_passed_with_new_capture():
    reader, capture, _, calls = setup()
    page = reader.read(DOCUMENT, RUN, captured=capture)
    cursor = page["next_cursor"]
    assert cursor
    before = len(calls)
    for document, run, kwargs in [(DOCUMENT, str(uuid4()), {"cursor": cursor}),
            (str(uuid4()), RUN, {"cursor": cursor}),
            (DOCUMENT, RUN, {"cursor": cursor, "captured": capture})]:
        with pytest.raises(ReadError):
            reader.read(document, run, **kwargs)
    assert len(calls) == before


def test_invalid_offset_and_missing_material_fail_instead_of_reporting_no_changes():
    reader, capture, _, _ = setup()
    bad = reader.codec.issue_run_cursor(capture.model_copy(update={"offset": 10000}))
    with pytest.raises(ReadError, match="^invalid_ref$"):
        reader.read(DOCUMENT, RUN, cursor=bad)
    for code in ("operation_missing", "stored_content_mismatch", "read_failed"):
        def fail(*args):
            raise HistoryError(code)
        broken = RunChangeReadService(SimpleNamespace(read_run_change=fail), reader.codec)
        with pytest.raises(ReadError):
            broken.read(DOCUMENT, RUN, captured=capture)


def test_material_scope_cannot_exceed_native_captured_ids():
    reader, capture, material, _ = setup()
    foreign = replace(material, receipts=(replace(material.receipts[0], ai_run_id=str(uuid4())),))
    reader.history.read_run_change = lambda *args: foreign
    with pytest.raises(ReadError, match="^read_failed$"):
        reader.read(DOCUMENT, RUN, captured=capture)


def test_source_conditionals_are_checked_even_when_generated_model_accepts(monkeypatch):
    from jd_relational.generated.chat_http import ChatRunChangePage
    reader, capture, _, _ = setup()
    valid = reader.read(DOCUMENT, RUN, captured=capture)
    invalid = valid | {"captured_operation_count": 0}
    assert ChatRunChangePage.model_validate(invalid, strict=True)
    monkeypatch.setattr("jd_relational.run_change_reads.pack_read_records", lambda *args: invalid)
    with pytest.raises(ReadError, match="^read_failed$"):
        reader.read(DOCUMENT, RUN, captured=capture)


@pytest.mark.parametrize("method", ["issue_run_cursor", "issue"])
@pytest.mark.parametrize("continuation", [False, True])
def test_app_reference_issuance_failure_is_not_a_bad_caller_cursor(monkeypatch, method, continuation):
    reader, capture, _, _ = setup()
    cursor = reader.read(DOCUMENT, RUN, captured=capture)["next_cursor"]
    assert cursor
    def fail(*args, **kwargs):
        raise ReferenceValidationError()
    monkeypatch.setattr(type(reader.codec), method, fail)
    with pytest.raises(ReadError, match="^read_failed$"):
        reader.read(DOCUMENT, RUN, **({"cursor": cursor} if continuation else {"captured": capture}))


def test_invalid_caller_cursor_keeps_invalid_ref_and_never_reads_history():
    reader, _, _, calls = setup()
    with pytest.raises(ReadError, match="^invalid_ref$"):
        reader.read(DOCUMENT, RUN, cursor="bad")
    assert calls == []
