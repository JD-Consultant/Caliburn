from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError

from app.adapters.eval_capture_repo import EvalCaptureRepo
from app.adapters.interview_repo import InterviewRepo
from app.adapters.persistence import DocRepo
from app.api.routes.interview import start_interview
from app.config import settings
from app.interview.eval_capture import (
    EvalSessionStart,
    build_reference_snapshot,
    canonical_hash,
    prompt_bundle_hash,
    static_tool_schema_hash,
)
from app.interview.service import run_finish, run_turn
from app.models import (
    InterviewEvalArtifact,
    InterviewEvalCapture,
    InterviewLlmCall,
    JobProfile,
    User,
)
from app.adapters.stubs import StubKnowledge, StubLlm


def test_capture_hashes_and_contract_are_deterministic():
    value = {"b": [2, 1], "a": "測試"}
    assert canonical_hash(value) == canonical_hash({"a": "測試", "b": [2, 1]})
    assert canonical_hash(value).startswith("sha256:")
    assert prompt_bundle_hash().startswith("sha256:")
    assert static_tool_schema_hash().startswith("sha256:")
    EvalSessionStart(
        schema_version="interview_eval_session_start.v0.1",
        consent_policy_version="pilot-consent.v1",
        locale="zh-TW",
        initial_document_hash=canonical_hash({}),
        initial_state_hash=canonical_hash({}),
        reference_snapshot_hash=canonical_hash({}),
        prompt_bundle_hash=prompt_bundle_hash(),
        tool_schema_hash=static_tool_schema_hash(),
        code_git_sha="abc123",
        dirty_worktree=False,
    )


@pytest.mark.asyncio
async def test_reference_snapshot_has_self_declared_content_hash():
    snapshot = await build_reference_snapshot(StubKnowledge(), ["KRM2421-001v4"])
    declared = snapshot.pop("content_hash")
    assert declared == canonical_hash(snapshot)
    assert list(snapshot["tasks_by_ocs"]) == ["KRM2421-001v4"]


async def _profile(db_session):
    user = User(email=f"{uuid4()}@x.com", name="n")
    db_session.add(user)
    await db_session.flush()
    profile = JobProfile(
        user_id=user.id,
        job_title="工程師",
        selected_ocs_codes=["KRM2421-001v4"],
    )
    db_session.add(profile)
    await db_session.flush()
    await DocRepo(db_session).save(profile.id, {"ocs_profile": {"ocs_code": "KRM2421-001v4"}})
    return profile


@pytest.mark.asyncio
async def test_capture_request_fails_closed_when_server_disabled(db_session):
    profile = await _profile(db_session)
    with pytest.raises(HTTPException) as exc:
        await start_interview(
            profile.id,
            body={"eval_capture": {
                "enabled": True,
                "consent_policy_version": "pilot-consent.v1",
            }},
            db=db_session,
            knowledge=StubKnowledge(),
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "eval_capture_disabled"


@pytest.mark.asyncio
async def test_capture_start_is_turn_zero_complete_and_idempotent(db_session, monkeypatch):
    profile = await _profile(db_session)
    monkeypatch.setattr(settings, "interview_eval_capture_enabled", True)
    monkeypatch.setattr(settings, "interview_eval_capture_git_sha", "test-git-sha")
    monkeypatch.setattr(settings, "interview_eval_capture_dirty_worktree", False)
    body = {"eval_capture": {
        "enabled": True,
        "consent_policy_version": "pilot-consent.v1",
        "locale": "zh-TW",
    }}

    first = await start_interview(
        profile.id, body=body, db=db_session, knowledge=StubKnowledge()
    )
    second = await start_interview(
        profile.id, body=body, db=db_session, knowledge=StubKnowledge()
    )

    assert first["session_id"] == second["session_id"]
    assert first["eval_capture"] == {
        "schema_version": "interview_eval_session_start.v0.1",
        "status": "capturing",
        "replay_ready": False,
    }
    capture_repo = EvalCaptureRepo(db_session)
    capture = await capture_repo.get_for_session(UUID(first["session_id"]))
    artifacts = await capture_repo.list_artifacts(capture.id)
    assert [(row.kind, row.sequence) for row in artifacts] == [
        ("initial_document", 0),
        ("initial_state", 0),
        ("reference_snapshot", 0),
    ]
    assert all(row.content_hash == canonical_hash(row.content) for row in artifacts)

    nested = await db_session.begin_nested()
    try:
        with pytest.raises(DBAPIError, match="interview eval artifacts are immutable"):
            await db_session.execute(
                update(InterviewEvalArtifact)
                .where(InterviewEvalArtifact.id == artifacts[0].id)
                .values(content={"tampered": True})
            )
            await db_session.flush()
    finally:
        await nested.rollback()

    nested = await db_session.begin_nested()
    try:
        with pytest.raises(DBAPIError, match="eval capture metadata is immutable"):
            await db_session.execute(
                update(InterviewEvalCapture)
                .where(InterviewEvalCapture.id == capture.id)
                .values(code_git_sha="tampered")
            )
            await db_session.flush()
    finally:
        await nested.rollback()


@pytest.mark.asyncio
async def test_captured_turn_has_complete_hash_chain_and_semantic_call_order(
    db_session, monkeypatch
):
    profile = await _profile(db_session)
    monkeypatch.setattr(settings, "interview_eval_capture_enabled", True)
    monkeypatch.setattr(settings, "interview_eval_capture_git_sha", "test-git-sha")
    monkeypatch.setattr(settings, "interview_eval_capture_dirty_worktree", False)
    await start_interview(
        profile.id,
        body={"eval_capture": {
            "enabled": True,
            "consent_policy_version": "pilot-consent.v1",
        }},
        db=db_session,
        knowledge=StubKnowledge(),
    )

    await run_turn(
        profile.id,
        "我每天會做設備巡檢，發現異常就記錄並通知主管。",
        db=db_session,
        llm=StubLlm(select_result={"records": []}),
        knowledge=StubKnowledge(),
    )

    session = await InterviewRepo(db_session).get_active(profile.id)
    capture = await EvalCaptureRepo(db_session).get_for_session(session.id)
    artifacts = await EvalCaptureRepo(db_session).list_artifacts(capture.id)
    by_kind = {row.kind: row for row in artifacts}
    for kind in (
        "turn_state_before",
        "turn_document_before",
        "turn_state_after",
        "turn_document_after",
        "turn_tool_results",
        "turn_stage_outputs",
        "turn_trajectory",
    ):
        assert kind in by_kind
        assert by_kind[kind].content_hash == canonical_hash(by_kind[kind].content)

    trajectory = by_kind["turn_trajectory"].content
    assert trajectory["state_before_hash"] == by_kind["turn_state_before"].content_hash
    assert trajectory["document_before_hash"] == by_kind["turn_document_before"].content_hash
    assert trajectory["state_after_hash"] == by_kind["turn_state_after"].content_hash
    assert trajectory["document_after_hash"] == by_kind["turn_document_after"].content_hash
    assert by_kind["turn_state_after"].content["phase"] == "survey"
    assert "derived_phase" in by_kind["turn_state_after"].content

    rows = (await db_session.scalars(
        select(InterviewLlmCall).where(InterviewLlmCall.session_id == capture.session_id)
    )).all()
    stage_by_id = {str(row.id): row.stage for row in rows}
    stages = [stage_by_id[call_id] for call_id in trajectory["model_call_ids"]]
    assert stages == [stage for stage in ("curation", "consultant", "scribe", "harvest")
                      if stage in stage_by_id.values()]

    first_finish = await run_finish(
        profile.id,
        db=db_session,
        llm=StubLlm(select_result={"records": []}),
        knowledge=StubKnowledge(),
    )
    second_finish = await run_finish(
        profile.id,
        db=db_session,
        llm=StubLlm(select_result={"records": []}),
        knowledge=StubKnowledge(),
    )
    assert second_finish == first_finish
    completed = await EvalCaptureRepo(db_session).get_for_session(session.id)
    assert completed.status == "completed"
    final_artifacts = await EvalCaptureRepo(db_session).list_artifacts(completed.id)
    assert sum(row.kind == "session_finish" for row in final_artifacts) == 1
