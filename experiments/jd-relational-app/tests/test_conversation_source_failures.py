"""Source failure/lifecycle counterexamples over existing native owners."""
from types import SimpleNamespace
from uuid import uuid4

import pytest

from jd_relational.consultant_tools import AiToolError
from jd_relational.manual_service import ManualService, ManualError
from jd_relational.memory_context import issue_scoped_evidence_key
from jd_relational.reads import ReadError
from jd_relational.references import ReferenceCodec, SignedReference
from test_manual_runtime import runtime


def test_source_storage_failure_stops_before_write_or_another_model_call():
    from test_consultant_tools import setup, run, call, task_args, done
    session, context, owner, _, _ = setup()
    def unavailable(*args):
        raise ReadError("source_not_available")
    session.source_resolver = unavailable
    source_reference = "source-owner-ref"
    context.source_notice = lambda messages: {
        "type": "conversation_source_notice",
        "source_ref": source_reference,
        "messages": [{"message_id": "synthetic-message", "role": "user"}],
        "instruction": "只供合成測試使用。",
    }
    evidence_key = issue_scoped_evidence_key(
        dataset_id=context.dataset_id, document_id=context.document_id,
        run_id=context.run_id, scope_kind="current_turn", scope_id=context.run_id,
        source_reference=source_reference,
    )
    with pytest.raises(AiToolError, match="^ai_tool_unavailable") as error:
        run(context, [call("jd_read", {"view": "current", "target_ref": None, "cursor": None}),
            call("jd_create_task", {**task_args(), "basis_evidence_keys": [evidence_key]}), done()])
    assert str(error.value) == "ai_tool_unavailable"
    assert not owner.calls and len(context.last_test_model.requests) == 2


def test_manual_source_read_must_finish_before_host_can_close(runtime, monkeypatch):
    import jd_relational.manual_service as module
    from test_manual_http_contract import save
    owner, _, storage = runtime
    document, revision, dataset = (str(uuid4()) for _ in range(3))
    codec = ReferenceCodec(b"synthetic-source-lifecycle-key-32", dataset)
    results = []
    def source_resolver(*args):
        results.append(owner.close(timeout=0))
        raise ReadError("source_not_available")
    # The counterexample concerns Saver lifetime during preparation, not SQL.
    # Keep the real ManualService and owner, only replace its material ports.
    monkeypatch.setattr(module, "command_context", lambda value, command, codec, resolver, new_id:
        resolver("source-owner-ref", document))
    history = SimpleNamespace(read_revision=lambda *args: SimpleNamespace(domain={}))
    service = ManualService(owner, history, codec, source_resolver=source_resolver)
    envelope = save()
    envelope["base_revision_ref"] = codec.issue(SignedReference(document_id=document,
        revision_id=revision, purpose="history", role="revision", kind="revision"))
    with pytest.raises(ManualError, match="^service_unavailable$"):
        service.save(document, envelope)
    assert results == [False], "A live source read must keep the Saver owner open."
    assert owner.close(timeout=1)
