"""Bounded audit probes. A pass reproduces a known gap; no product mutation.

Real native Agent/Saver and in-memory SQLite publication; no external DB/provider.

SUPERSEDED 2026-09-13: CA-01/CA-02 are fixed, so these "recovery still blocks"
assertions now fail by design. This file is kept as the record of the audited
state. The product regressions are the named cases in
`experiments/jd-relational-app/tests/test_memory_repair_session.py` and
`tests/test_consultant_memory_postgres.py`; see
`docs/specs/2026-09-13-jd-memory-repair-app-integration-slice.md`.
"""
import sys
from pathlib import Path
from uuid import uuid4

REPO_ROOT = next(parent for parent in Path(__file__).resolve().parents
    if (parent / "experiments/jd-relational-app/pyproject.toml").is_file())
sys.path.insert(0, str(REPO_ROOT / "experiments/jd-relational-app/tests"))

import pytest
from jd_relational.ai_checkpoints import AiRunCheckpoints, new_run_record
from jd_relational.ai_runtime import AiRuntime, AiRuntimeError, _pending_calls
from test_chat_history import native
from test_consultant_memory_context import memory
from test_memory_repair_session import setup_repair, call


def fixture(memory):
    graph, model, initial, repair, publication, context, payload, config = setup_repair(memory, [call(1)])
    record, human = new_run_record(initial.dataset_id, initial.document_id, initial.run_id,
        "Synthetic audit correction", start_revision_id=str(uuid4()))
    payload.update(jd_ai_run=record.model_dump(mode="json"), messages=[human])
    runtime = AiRuntime.__new__(AiRuntime)
    runtime.graph = graph
    runtime.memory_engine = publication.engine
    runtime.conversation_sources = initial.source.service
    return graph, model, initial, repair, publication, context, payload, config, runtime


@pytest.mark.parametrize("fault", ["source_before_binding", "child_start_checkpoint"])
def test_reproduce_unclosed_safe_boundaries(memory, monkeypatch, fault):
    graph, model, initial, repair, publication, context, payload, config, runtime = fixture(memory)
    entered = []
    original_seed = repair.workflow._seed
    def seed(state):
        entered.append("seed")
        return original_seed(state)
    monkeypatch.setattr(repair.workflow, "_seed", seed)
    if fault == "source_before_binding":
        def unavailable(_messages):
            raise OSError("synthetic source notice failure")
        context.source_notice = unavailable
    else:
        original_put = graph.checkpointer.put
        def fail_first_child_loop(cfg, checkpoint, metadata, versions):
            if cfg["configurable"].get("checkpoint_ns", "").startswith("memory_repair:") and metadata["source"] == "loop":
                raise OSError("synthetic first child loop save failure")
            return original_put(cfg, checkpoint, metadata, versions)
        monkeypatch.setattr(graph.checkpointer, "put", fail_first_child_loop)
    with pytest.raises(OSError):
        graph.invoke(payload, config, context=context, durability="sync")
    observed = AiRunCheckpoints(graph).observe(initial.document_id, initial.run_id, initial.dataset_id)
    assert len(model.requests) == 1 and entered == [] and publication.current().revision == 1
    if fault == "source_before_binding":
        assert observed.repair_bindings == [] and observed.repair_checkpoint is None
    else:
        assert len(observed.repair_bindings) == 1
        assert observed.repair_checkpoint["next"] == ["__start__"]
    pending = _pending_calls(observed.messages)
    assert len(pending) == 1
    with pytest.raises(AiRuntimeError, match="^run_recovery_required$"):
        runtime._recover_pending_repair(observed, observed.messages, pending)
    print(f"AUDIT {fault}: seed=0 model=1 publication=0; recovery blocks")
