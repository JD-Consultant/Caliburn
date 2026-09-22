"""V1 stays readable; only V2 can express a new version-bound request."""

from copy import deepcopy
import json
from uuid import UUID

import pytest

from jd_relational.ai_checkpoints import AiCheckpointError, new_run_record


DATASET = "aaaaaaaa-1111-4222-8333-444444444444"
DOCUMENT = "bbbbbbbb-1111-4222-8333-444444444444"
RUN = "cccccccc-1111-4222-8333-444444444444"
REVISION = "dddddddd-1111-4222-8333-444444444444"
TEXT = "原話\r\n  每月處理異常。😀"


def test_new_request_cannot_omit_its_explicit_start_revision():
    with pytest.raises(TypeError):
        new_run_record(DATASET, DOCUMENT, RUN, TEXT)


def test_new_request_emits_v2_and_keeps_original_human_exactly():
    from jd_relational.ai_records import AiRunRecordV2, request_digest_for_record
    record, human = new_run_record(DATASET, DOCUMENT, RUN, TEXT, start_revision_id=REVISION)
    assert type(record) is AiRunRecordV2 and record.format_version == 2
    assert record.start_revision_id == REVISION and human.id == RUN and human.content == TEXT
    assert record.request_digest == "02080de6edaa967b8cc904861db9505c7ad825f09c8910b873ccee275b7e61a7"
    assert record.request_digest == request_digest_for_record(record, TEXT)
    different, _ = new_run_record(DATASET, DOCUMENT, RUN, TEXT,
        start_revision_id="eeeeeeee-1111-4222-8333-444444444444")
    assert different.request_digest != record.request_digest
    same, _ = new_run_record(DATASET, DOCUMENT, "eeeeeeee-1111-4222-8333-444444444444", TEXT,
                            start_revision_id=REVISION)
    assert same.request_digest == record.request_digest  # ID remains the outer intent key.


def legacy_record():
    # A literal original-format fixture, never produced by the new builder.
    return {"format_version": 1, "dataset_id": DATASET, "document_id": DOCUMENT,
            "run_id": RUN, "request_digest": "3790c84260604934881e9eaa13da172e679cff5b02ec32882a991fcabf470cdd", "status": "running"}


@pytest.mark.parametrize("version", [1, 2])
def test_native_version_parser_round_trips_without_upgrade(version):
    from jd_relational.ai_records import parse_run_record, parse_run_record_json, request_digest_for_record
    value = legacy_record() if version == 1 else new_run_record(
        DATASET, DOCUMENT, RUN, TEXT, start_revision_id=REVISION)[0].model_dump(mode="json")
    before = deepcopy(value)
    assert parse_run_record(value).model_dump(mode="json") == value == before
    assert parse_run_record_json(json.dumps(value)).model_dump(mode="json") == value
    assert request_digest_for_record(parse_run_record(value), TEXT) == value["request_digest"]
    closed = parse_run_record(value).model_copy(update={"status": "failed"}).model_dump(mode="json")
    assert closed == {**value, "status": "failed"}
    if version == 1:
        assert "start_revision_id" not in closed


@pytest.mark.parametrize("version", [1, 2])
@pytest.mark.parametrize("bad_tag", [True, False, 1.0, 2.0, "1", "2", None, 0, 3])
def test_version_tag_type_is_not_weakened_by_native_literal_coercion(version, bad_tag):
    from jd_relational.ai_records import AiRecordError, parse_run_record, parse_run_record_json
    value = legacy_record() if version == 1 else new_run_record(
        DATASET, DOCUMENT, RUN, TEXT, start_revision_id=REVISION)[0].model_dump(mode="json")
    value["format_version"] = bad_tag
    with pytest.raises(AiRecordError, match="^invalid_run_record$"):
        parse_run_record(value)
    with pytest.raises(AiRecordError, match="^invalid_run_record$"):
        parse_run_record_json(json.dumps(value))


@pytest.mark.parametrize("value", [None, True, 1, UUID(REVISION), REVISION.upper(), "not-a-uuid", ""])
def test_new_request_rejects_invalid_start_revision(value):
    with pytest.raises(AiCheckpointError, match="^invalid_input$"):
        new_run_record(DATASET, DOCUMENT, RUN, TEXT, start_revision_id=value)


@pytest.mark.parametrize("fault", ["missing_version", "old_extra_revision", "new_missing_revision", "extra",
                                  "bad_digest", "bad_scope", "bad_status", "bad_revision"])
def test_only_the_exact_original_or_new_record_shape_is_accepted(fault):
    from jd_relational.ai_records import AiRecordError, parse_run_record
    value = legacy_record() if fault == "old_extra_revision" else new_run_record(
        DATASET, DOCUMENT, RUN, TEXT, start_revision_id=REVISION)[0].model_dump(mode="json")
    if fault == "missing_version": del value["format_version"]
    elif fault == "old_extra_revision": value["start_revision_id"] = REVISION
    elif fault == "new_missing_revision": del value["start_revision_id"]
    elif fault == "extra": value["unexpected"] = True
    elif fault == "bad_digest": value["request_digest"] = "no"
    elif fault == "bad_scope": value["dataset_id"] = DATASET.upper()
    elif fault == "bad_status": value["status"] = "closing"
    elif fault == "bad_revision": value["start_revision_id"] = REVISION.upper()
    with pytest.raises(AiRecordError, match="^invalid_run_record$"):
        parse_run_record(value)


@pytest.mark.parametrize("version,bad_tag", [(1, True), (1, 1.0), (2, 2.0)])
def test_direct_native_model_validation_retains_strict_version_type(version, bad_tag):
    from pydantic import ValidationError
    from jd_relational.ai_records import AiRunRecordV1, AiRunRecordV2
    value = legacy_record() if version == 1 else new_run_record(
        DATASET, DOCUMENT, RUN, TEXT, start_revision_id=REVISION)[0].model_dump(mode="json")
    value["format_version"] = bad_tag
    with pytest.raises(ValidationError):
        (AiRunRecordV1 if version == 1 else AiRunRecordV2).model_validate(value, strict=True)
