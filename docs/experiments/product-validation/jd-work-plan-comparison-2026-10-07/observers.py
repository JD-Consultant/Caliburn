"""Only the repaired official-adoption observer seam; no historical batch gate or deadline.

Copied unchanged from predecessor diagnostics/repaired_comparison.py for isolation.
"""

import json

from guard import digest, role


def checkpoint_stage(thread_id, values):
    if values.get("adopted") is not True or values.get("compaction_snapshot") is None:
        return "unknown"
    policy = values.get("preparation_policy", "missing")
    if isinstance(policy, dict) and thread_id.endswith(
        ":job_consultant:prepared_history"
    ):
        return "pre-work"
    if (
        policy is None
        and ":job_consultant:completed_work:compact:" in thread_id
        and role(values.get("request_snapshot", {})) == "A"
    ):
        return "mid-work"
    return "unknown"


def bind_case_observers(run_batch, guard, directory):
    """Defer the original pressure-release callback until official C adoption is saved."""
    from caliburn.adapters.openai_responses import ResponseRequest
    from caliburn.agent_execution.context_compaction import read_compacted_window

    base_transport, base_saver = run_batch.GuardedTransport, run_batch.ObservedSaver
    release = []
    released = False

    class RecordedTransport(base_transport):
        def __init__(self, current_guard, *args, **kwargs):
            if not release:
                release.append(current_guard.on_a_compact)
                current_guard.on_a_compact = lambda: None
            super().__init__(current_guard, *args, **kwargs)

    class AdoptedSaver(base_saver):
        async def aput(self, config, checkpoint, metadata, new_versions):
            nonlocal released
            result = await super().aput(config, checkpoint, metadata, new_versions)
            values = checkpoint["channel_values"]
            if (
                values.get("compaction_snapshot") is None
                or role(values.get("request_snapshot", {})) != "A"
            ):
                return result
            thread = config["configurable"]["thread_id"]
            stage = checkpoint_stage(thread, values)
            verified = False
            if stage == "mid-work":
                await read_compacted_window(
                    self,
                    thread_id=thread,
                    checkpoint_id=checkpoint["id"],
                    request=ResponseRequest.from_snapshot(values["request_snapshot"]),
                    input_count=values["input_count"],
                )
                verified = True
                if not released:
                    if not release:
                        raise ValueError(
                            "Mid-work adoption has no original pressure callback"
                        )
                    release[0]()
                    released = True
            with (directory / "pressure-adoption.jsonl").open(
                "a", encoding="utf-8"
            ) as output:
                output.write(
                    json.dumps(
                        {
                            "thread_id": thread,
                            "checkpoint_id": checkpoint["id"],
                            "stage": stage,
                            "adopted": values.get("adopted"),
                            "official_saver_acknowledged": True,
                            "saved_midwork_read_verified": verified,
                            "pressure_released": released,
                            "parent_input_sha256": digest(
                                values.get("request_snapshot", {}).get("input", [])
                            ),
                        }
                    )
                    + "\n"
                )
            return result

    run_batch.GuardedTransport, run_batch.ObservedSaver = (
        RecordedTransport,
        AdoptedSaver,
    )
    return base_transport, base_saver
