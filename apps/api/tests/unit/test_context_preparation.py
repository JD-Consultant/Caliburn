"""New-work preparation compacts history only, and does not re-prepare on recovery."""

from copy import deepcopy
from dataclasses import replace
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from openai.types.responses.compacted_response import CompactedResponse

from caliburn.agent_execution.context_compaction import (
    CompactionRuntime,
    ReceivedCompaction,
    prepare_context_history,
)
from tests.fixtures.response_capacity import request_fixture, synthetic_capacity_limits


class PreparationProbe:
    def __init__(self, tokens=127_999):
        self.tokens = tokens
        self.count_requests = []
        self.compact_requests = []
        self.accounts = []
        self.window = [
            {"type": "compaction", "id": "cmp_synthetic", "encrypted_content": "opaque"},
            {"role": "user", "content": "retained historical input"},
        ]

    async def count(self, request, request_id):
        self.count_requests.append((request_id, request.count_payload()))
        return {"input_tokens": self.tokens, "attempt_id": uuid4()}

    async def compact(self, request, request_id):
        self.compact_requests.append((request_id, request.create_payload()))
        return ReceivedCompaction(
            CompactedResponse.construct(
                id="cmp_synthetic",
                object="response.compaction",
                created_at=1,
                output=deepcopy(self.window),
                usage={
                    "input_tokens": self.tokens,
                    "output_tokens": 20,
                    "input_tokens_details": {"cached_tokens": 0},
                    "total_tokens": self.tokens + 20,
                },
            ),
            uuid4(),
        )

    async def account(self, received):
        self.accounts.append(received.attempt_id)

    async def active(self):
        pass

    def options(self):
        return dict(
            thread_id="synthetic-history-preparation",
            history_request=request_fixture(),
            threshold_tokens=128_000,
            compact_requested=False,
            count_input=self.count,
            runtime=CompactionRuntime(
                self.compact, self.account, self.active, synthetic_capacity_limits()
            ),
        )


async def test_below_threshold_preserves_history_without_compaction():
    probe = PreparationProbe()
    args = probe.options()
    result = await prepare_context_history(InMemorySaver(), **args)
    assert result == args["history_request"].create_payload()["input"]
    assert len(probe.count_requests) == 1
    assert probe.compact_requests == []


@pytest.mark.parametrize(
    ("tokens", "requested", "compacted"),
    [(127_999, False, False), (128_000, False, True), (100, True, True)],
)
async def test_saved_preparation_reentry_reuses_decision_and_full_window(
    tokens, requested, compacted
):
    probe = PreparationProbe(tokens)
    args = {**probe.options(), "compact_requested": requested}
    saver = InMemorySaver()
    expected = probe.window if compacted else args["history_request"].create_payload()["input"]
    for _ in range(2):
        result = await prepare_context_history(saver, **args)
        assert result == expected
        # A caller adding new Turn data must not mutate this reusable pre-input base.
        result.append({"role": "user", "content": "cancelled synthetic Turn input"})
    assert len(probe.count_requests) == 1
    assert len(probe.compact_requests) == int(compacted)
    if compacted:
        assert probe.count_requests[0][0] != probe.compact_requests[0][0]
        assert (
            probe.compact_requests[0][1]["input"]
            == args["history_request"].create_payload()["input"]
        )


async def test_no_history_skips_count_and_compact_even_with_agent_intent():
    probe = PreparationProbe()
    args = probe.options()
    args["history_request"] = args["history_request"].from_snapshot(
        {**args["history_request"].create_payload(), "input": []}
    )
    args["compact_requested"] = True
    saver = InMemorySaver()
    for _ in range(2):
        assert await prepare_context_history(saver, **args) == []
    assert probe.count_requests == []
    assert probe.compact_requests == []


class PreparationSaveFault(InMemorySaver):
    fail = True
    fail_after_save = False
    keep_pending_writes = False
    field_name = "input_count"

    async def aput(self, config, checkpoint, metadata, new_versions):
        if self.fail and checkpoint["channel_values"].get(self.field_name) is not None:
            if self.fail_after_save:
                await super().aput(config, checkpoint, metadata, new_versions)
            raise ConnectionError("synthetic history count save failure")
        return await super().aput(config, checkpoint, metadata, new_versions)

    async def aput_writes(self, config, writes, task_id, task_path=""):
        if (
            self.fail
            and not self.keep_pending_writes
            and any(k == self.field_name for k, _ in writes)
        ):
            raise ConnectionError("synthetic history count pending write failure")
        await super().aput_writes(config, writes, task_id, task_path)


@pytest.mark.parametrize("save_mode", ["before", "after", "pending"])
async def test_original_history_count_survives_save_failure_without_remote_recount(save_mode):
    from caliburn.agent_execution.context_compaction import PreparationCountSaveError

    probe = PreparationProbe(128_000)
    args = probe.options()
    saver = PreparationSaveFault()
    saver.fail_after_save = save_mode == "after"
    saver.keep_pending_writes = save_mode == "pending"
    with pytest.raises(PreparationCountSaveError) as failed:
        await prepare_context_history(saver, **args)
    assert probe.compact_requests == []
    saver.fail = False
    assert (
        await prepare_context_history(saver, **args, recovery=failed.value.recovery) == probe.window
    )
    assert len(probe.count_requests) == 1
    assert len(probe.compact_requests) == 1
    # Re-presenting a now-saved handoff never rewinds or repeats compaction.
    assert (
        await prepare_context_history(saver, **args, recovery=failed.value.recovery) == probe.window
    )
    assert len(probe.compact_requests) == 1


async def test_repeated_count_save_failure_keeps_the_intact_original():
    from caliburn.agent_execution.context_compaction import PreparationCountSaveError

    probe = PreparationProbe()
    args = probe.options()
    saver = PreparationSaveFault()
    with pytest.raises(PreparationCountSaveError) as failed:
        await prepare_context_history(saver, **args)
    with pytest.raises(PreparationCountSaveError) as again:
        await prepare_context_history(saver, **args, recovery=failed.value.recovery)
    assert again.value.recovery.update == failed.value.recovery.update
    assert len(probe.count_requests) == 1
    saver.fail = False
    assert (
        await prepare_context_history(saver, **args, recovery=again.value.recovery)
        == args["history_request"].create_payload()["input"]
    )


@pytest.mark.parametrize("change", ["history", "intent", "threshold", "capacity"])
async def test_preparation_rejects_changed_original_binding(change):
    probe = PreparationProbe()
    args = probe.options()
    saver = InMemorySaver()
    await prepare_context_history(saver, **args)
    if change == "history":
        args["history_request"] = args["history_request"].from_snapshot(
            {**args["history_request"].create_payload(), "input": []}
        )
    elif change == "intent":
        args["compact_requested"] = True
    elif change == "threshold":
        args["threshold_tokens"] = 512_000
    else:
        args["runtime"] = replace(
            args["runtime"],
            capacity_limits={**synthetic_capacity_limits(), "max_input_tokens": 800_000},
        )
    with pytest.raises(ValueError, match="original"):
        await prepare_context_history(saver, **args)
    assert len(probe.count_requests) == 1
    assert probe.compact_requests == []


async def test_failed_count_never_means_empty_history_or_zero_tokens():
    probe = PreparationProbe()
    args = probe.options()

    async def count_failure(*args):
        raise ConnectionError("synthetic unavailable count")

    args["count_input"] = count_failure
    with pytest.raises(ConnectionError, match="unavailable count"):
        await prepare_context_history(InMemorySaver(), **args)
    assert probe.compact_requests == []


async def test_capacity_failure_retains_count_and_history_without_blind_compaction():
    from caliburn.agent_execution.request_capacity import RequestCapacityError

    probe = PreparationProbe(950_000)
    args = probe.options()
    saver = InMemorySaver()
    for _ in range(2):
        with pytest.raises(RequestCapacityError, match="exceeds"):
            await prepare_context_history(saver, **args)
    assert len(probe.count_requests) == 1
    assert probe.compact_requests == []


async def test_ineligible_work_after_history_count_cannot_compact():
    probe = PreparationProbe(128_000)
    args = probe.options()

    async def guard():
        if probe.count_requests:
            raise PermissionError("synthetic stale writer")

    args["runtime"] = replace(args["runtime"], ensure_active=guard)
    with pytest.raises(PermissionError, match="stale writer"):
        await prepare_context_history(InMemorySaver(), **args)
    assert len(probe.count_requests) == 1
    assert probe.compact_requests == []


async def test_preparation_reuses_original_c_when_its_save_confirmation_is_lost():
    from caliburn.agent_execution.context_compaction import CompactionSaveError

    probe = PreparationProbe(128_000)
    args = probe.options()
    saver = PreparationSaveFault()
    saver.field_name = "compaction_snapshot"
    saver.fail_after_save = True
    with pytest.raises(CompactionSaveError) as failed:
        await prepare_context_history(saver, **args)
    assert probe.accounts == []
    saver.fail = False
    result = await prepare_context_history(saver, **args, recovery=failed.value.recovery)
    assert result == probe.window
    assert len(probe.count_requests) == len(probe.compact_requests) == len(probe.accounts) == 1


async def test_count_recovery_cannot_cross_preparation_boundaries():
    from caliburn.agent_execution.context_compaction import PreparationCountSaveError

    probe = PreparationProbe()
    args = probe.options()
    saver = PreparationSaveFault()
    with pytest.raises(PreparationCountSaveError) as failed:
        await prepare_context_history(saver, **args)
    saver.fail = False
    with pytest.raises(ValueError, match="different saved boundary"):
        await prepare_context_history(
            saver, **{**args, "thread_id": "other-role"}, recovery=failed.value.recovery
        )
    assert len(probe.count_requests) == 1
    assert probe.compact_requests == []
