"""Discover actual fixed native checkpoints without knowing a run ID."""

from copy import deepcopy
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from jd_relational.ai_checkpoints import AiCheckpointError, AiRunCheckpoints
from test_ai_checkpoints import (
    DATASET, DOCUMENT, RUN, State, Wrapper, config, initial_input_failure, native,
)


@pytest.mark.parametrize("paused", [False, True])
def test_discovery_finds_same_fixed_current_material_without_run_id(paused):
    graph, calls = native(paused=paused)
    adapter = AiRunCheckpoints(graph)
    assert adapter.discover(DOCUMENT, DATASET) == adapter.observe(DOCUMENT, RUN, DATASET)
    assert calls == ["model"]


@pytest.mark.parametrize("prior", [False, True])
def test_discovery_chooses_start_original_input_instead_of_previous_terminal(prior):
    graph, calls, record, human, previous = initial_input_failure(prior=prior)
    seen = AiRunCheckpoints(graph).discover(DOCUMENT, DATASET)
    assert seen.record == record and seen.messages[-1] == human and not seen.closed
    assert seen.messages == [*previous.values.get("messages", []), human]
    assert len(calls) == int(prior)


def test_discovery_none_is_only_no_ai_record_not_a_writer_permission():
    graph = StateGraph(State)
    graph.add_node("consultant", lambda _: (_ for _ in ()).throw(AssertionError("never invoke")))
    graph.add_edge(START, "consultant"); graph.add_edge("consultant", END)
    graph = graph.compile(checkpointer=InMemorySaver())
    adapter = AiRunCheckpoints(graph)
    assert adapter.discover(DOCUMENT, DATASET) is None
    assert graph.get_state(config()).config == config()


@pytest.mark.parametrize("change", ["pending_without_record", "old_messages_without_record", "scope", "unknown_next", "bad_values"])
def test_unknown_or_corrupt_work_is_never_absence(change):
    graph, _ = native(paused=True)
    class Malformed(Wrapper):
        def get_state(self, config, **kwargs):
            state = super().get_state(config, **kwargs)
            if config.get("configurable", {}).get("checkpoint_id") and not config["configurable"].get("checkpoint_ns"):
                values = deepcopy(state.values)
                if change in {"pending_without_record", "old_messages_without_record"}:
                    values.pop("jd_ai_run")
                    state = state._replace(values=values)
                    if change == "old_messages_without_record":
                        state = state._replace(next=(), tasks=(), interrupts=())
                elif change == "scope":
                    values["jd_ai_run"]["dataset_id"] = str(uuid4())
                    state = state._replace(values=values)
                elif change == "unknown_next": state = state._replace(next=("unknown",))
                elif change == "bad_values": state = state._replace(values=["bad"])
            return state
    with pytest.raises(AiCheckpointError, match="^invalid_checkpoint$"):
        AiRunCheckpoints(Malformed(graph)).discover(DOCUMENT, DATASET)


def test_discovery_uses_one_latest_locator_and_fixed_child_not_second_latest():
    graph, calls = native(paused=True)
    class ReadLog(Wrapper):
        def __init__(self, graph): super().__init__(graph); self.locations = []
        def get_state(self, config, **kwargs):
            self.locations.append(deepcopy(config))
            if len([c for c in self.locations if not c["configurable"].get("checkpoint_id")]) > 1:
                raise AssertionError("A second latest read could choose another run")
            return super().get_state(config, **kwargs)
    wrapped = ReadLog(graph)
    seen = AiRunCheckpoints(wrapped).discover(DOCUMENT, DATASET)
    assert seen.record.run_id == RUN and seen.source_config != seen.root_config
    assert len(wrapped.locations) == 3 and calls == ["model"]
