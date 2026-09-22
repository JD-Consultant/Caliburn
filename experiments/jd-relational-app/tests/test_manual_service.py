"""Manual boundary input/error probes; runtime uses real in-process ownership."""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from jd_relational.manual_service import ManualError, ManualService, parse_manual_save
from jd_relational.references import ReferenceCodec
from test_manual_runtime import runtime
from test_manual_http_contract import save


@pytest.mark.parametrize("archived", [0, 1, "false", None])
def test_output_flags_cannot_coerce_malformed_storage_values(runtime, archived):
    owner, _, storage = runtime
    storage.read_current = lambda document: SimpleNamespace(archived=archived)
    service = ManualService(owner, None, ReferenceCodec(b"synthetic-flags-key-only-0000000000", "synthetic-flags"))
    with pytest.raises(ManualError, match="^service_unavailable$"):
        service.status(str(uuid4()))


@pytest.mark.parametrize("raw", [
    '{"operation_id":"a","operation_id":"b"}',
    '{"operation_id":NaN}', 'null', '[]', '"\ud800"',
])
def test_invalid_raw_json_is_safe_and_never_admitted(raw):
    with pytest.raises(ManualError, match="^invalid_input$") as failed:
        parse_manual_save(raw)
    assert failed.value.__suppress_context__


def test_http_cannot_supply_actor_or_runtime_metadata():
    for key, value in (("origin", "ai"), ("ai_run_id", "claimed-run"), ("request_digest", "forged")):
        with pytest.raises(ManualError, match="^invalid_input$"):
            parse_manual_save({**save(), key: value})
