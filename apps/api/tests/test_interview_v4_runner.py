import copy
import json
from pathlib import Path

import pytest

from evals.interview_v4.contracts import EvalRunArtifact
from evals.interview_v4.runner import (
    CurrentC0Processor,
    ProcessorResult,
    SnapshotKnowledge,
    run_c0_case,
)


ROOT = Path(__file__).parents[1] / "evals" / "interview_v4"
CASE = ROOT / "cases" / "development" / "JD-golden-001"


class DeterministicProcessor:
    async def process_employee_turn(self, *, document, state, employee_turns, turn_seq):
        new_state = copy.deepcopy(state)
        new_state.setdefault("evidence", []).append({
            "evidence_id": f"ev_{turn_seq}",
            "kind": "action",
            "source": {
                "turn_id": turn_seq,
                "speaker": "employee",
                "quote": employee_turns[turn_seq],
            },
        })
        return ProcessorResult(
            document=copy.deepcopy(document),
            state=new_state,
            candidate_output={"turn_seq": turn_seq},
            verifier_result={"ok": True},
        )

    async def close_episode(self, *, document, state, employee_turns, episode):
        new_state = copy.deepcopy(state)
        new_state.setdefault("closed_episodes", []).append(episode)
        return ProcessorResult(
            document=copy.deepcopy(document),
            state=new_state,
            candidate_output={"closed": episode["target"]},
            verifier_result={"ok": True},
        )

    async def finish(self, *, document, state, employee_turns):
        return ProcessorResult(document=copy.deepcopy(document), state=copy.deepcopy(state))


class NoneSelectingLlm:
    async def select_schema(self, prompt, schema, *, role, schema_name):
        return {"records": [{"type": "none"}]}


class NoKnowledgeCallsExpected:
    async def competencies(self, ocs_code):
        raise AssertionError(f"unexpected reference lookup: {ocs_code}")


@pytest.mark.asyncio
async def test_runner_rejects_provisional_case_by_default(tmp_path):
    with pytest.raises(ValueError, match="provisional"):
        await run_c0_case(
            CASE,
            processor=DeterministicProcessor(),
            output_root=tmp_path,
            git_sha="test-sha",
            dirty_worktree=True,
        )


@pytest.mark.asyncio
async def test_runner_isolated_artifact_and_source_fixture_unchanged(tmp_path):
    before = (CASE / "initial_state.json").read_bytes()
    first = await run_c0_case(
        CASE,
        processor=DeterministicProcessor(),
        output_root=tmp_path,
        git_sha="test-sha",
        dirty_worktree=True,
        allow_provisional=True,
    )
    second = await run_c0_case(
        CASE,
        processor=DeterministicProcessor(),
        output_root=tmp_path,
        git_sha="test-sha",
        dirty_worktree=True,
        trial_index=2,
        allow_provisional=True,
    )
    assert first != second and first.is_dir() and second.is_dir()
    assert (CASE / "initial_state.json").read_bytes() == before

    artifact = EvalRunArtifact.model_validate_json((first / "run.json").read_text(encoding="utf-8"))
    assert artifact.candidate == "C0"
    assert artifact.trial_index == 1
    assert artifact.case_content_hash.startswith("sha256:")
    assert len(artifact.case_content_hash) == 71
    assert len(artifact.trajectory) == 7
    final_state = json.loads((first / "final_state.json").read_text(encoding="utf-8"))
    assert len(final_state["evidence"]) == 7
    assert len(final_state["closed_episodes"]) == 1
    graders = json.loads((first / "grader_results.json").read_text(encoding="utf-8"))
    quote = next(row for row in graders if row["grader"] == "quote_validity")
    projection = next(row for row in graders if row["grader"] == "projection_grounding")
    assert quote["passed"] is True
    assert projection["applicable"] is False and projection["score"] is None


@pytest.mark.asyncio
async def test_current_c0_adapter_wraps_scribe_without_db_write():
    processor = CurrentC0Processor(
        llm=NoneSelectingLlm(),
        knowledge=NoKnowledgeCallsExpected(),
        reference_snapshot_id="sha256:test-snapshot",
    )
    document = {
        "ocs_profile": {},
        "ocs_content": {"ocu_units": []},
        "ocs_attitude": {"attitudes": []},
    }
    result = await processor.process_employee_turn(
        document=document,
        state={},
        employee_turns={2: "我目前沒有要補充的。"},
        turn_seq=2,
    )
    assert result.document == document
    assert result.state == {}
    assert result.candidate_output["phase"] == "scribe"
    assert result.candidate_output["progressed"] is False
    assert result.projection_delta == []


@pytest.mark.asyncio
async def test_snapshot_knowledge_never_falls_through_to_live_corpus():
    knowledge = SnapshotKnowledge({
        "content_hash": "sha256:fixture",
        "competencies_by_ocs": {
            "QA": {"ocs_code": "QA", "skills": [], "knowledge": []}
        },
    })
    pool = await knowledge.competencies("QA")
    assert pool.ocs_code == "QA"
    assert knowledge.snapshot_id == "sha256:fixture"
    with pytest.raises(KeyError, match="missing competencies"):
        await knowledge.competencies("LIVE-ONLY")
