"""T3:doc diff 純函式 + 人工 PATCH → human_touched 鉤子。"""
import pytest
from uuid import uuid4

from app.interview.diff import doc_paths_changed
from app.adapters.interview_repo import InterviewRepo
from app.api.routes.documents import patch_document
from app.models import JobProfile, User


# --- 純函式 ---

def test_scalar_change_and_no_change():
    old = {"ocs_profile": {"job_description": "舊", "ocs_code": "A"}}
    new = {"ocs_profile": {"job_description": "新", "ocs_code": "A"}}
    assert doc_paths_changed(old, new) == ["ocs_profile.job_description"]
    assert doc_paths_changed(new, new) == []


def test_list_items_aligned_by_stable_id_survive_reorder():
    t1 = {"_tid": "aaa", "task_codes": [{"code": "T1.1", "name": "x"}]}
    t2 = {"_tid": "bbb", "task_codes": [{"code": "T1.2", "name": "y"}]}
    old = {"ocs_content": {"ocu_units": [{"_uid": "u1", "tasks": [t1, t2]}]}}
    # 重排(t2 在前)但內容沒變 → 零變動
    new = {"ocs_content": {"ocu_units": [{"_uid": "u1", "tasks": [t2, t1]}]}}
    assert doc_paths_changed(old, new) == []
    # 重排 + 改 t1 的名 → 只標 t1 那條葉
    t1b = {"_tid": "aaa", "task_codes": [{"code": "T1.1", "name": "改"}]}
    new2 = {"ocs_content": {"ocu_units": [{"_uid": "u1", "tasks": [t2, t1b]}]}}
    assert doc_paths_changed(old, new2) == [
        "ocs_content.ocu_units.u1.tasks.aaa.task_codes.0.name"
    ]


def test_item_added_and_removed_marks_item_path():
    old = {"notes": {"prerequisites": ["a"]}}
    new = {"notes": {"prerequisites": ["a", "b"]}}
    assert doc_paths_changed(old, new) == ["notes.prerequisites.1"]
    assert doc_paths_changed(new, old) == ["notes.prerequisites.1"]


def test_details_slot_change_path():
    old = {"ocs_content": {"ocu_units": [{"_uid": "u1", "tasks": [
        {"_tid": "t1", "details": {"frequency": None}}]}]}}
    new = {"ocs_content": {"ocu_units": [{"_uid": "u1", "tasks": [
        {"_tid": "t1", "details": {"frequency": "每週"}}]}]}}
    assert doc_paths_changed(old, new) == [
        "ocs_content.ocu_units.u1.tasks.t1.details.frequency"
    ]


# --- 鉤子(真 DB;人工 PATCH 記入 active session) ---

async def _profile(db_session):
    u = User(email=f"{uuid4()}@x.com", name="n")
    db_session.add(u)
    await db_session.flush()
    p = JobProfile(user_id=u.id, job_title="工程師")
    db_session.add(p)
    await db_session.flush()
    return p


@pytest.mark.asyncio
async def test_patch_records_human_touched_when_active_session(db_session):
    p = await _profile(db_session)
    repo = InterviewRepo(db_session)
    s = await repo.create(p.id)
    await patch_document(p.id, {"ocs_profile": {"ocs_code": "X", "job_description": "v1"}},
                         db=db_session)
    await patch_document(p.id, {"ocs_profile": {"ocs_code": "X", "job_description": "v2"}},
                         db=db_session)
    got = await repo.get_active(p.id)
    assert "ocs_profile.job_description" in got.human_touched


@pytest.mark.asyncio
async def test_patch_without_session_untouched(db_session):
    p = await _profile(db_session)
    out = await patch_document(p.id, {"ocs_profile": {"ocs_code": "X"}}, db=db_session)
    assert out["version"] == 1   # 正常存檔,無 session 零影響
