"""V2-B-0：PostgreSQL test foundation 的 gate 測試（plan §3.4）。

驗證新 fixture 的關鍵性質：兩個「真正獨立」的 AsyncSession 能互相看見 commit——
這是 outer-transaction `db_session` 做不到、outbox/crash recovery tests 的先決條件。
cleanup 由 `cleanup_vnext_rows`（vnext_profile 依賴鏈）負責，逐 case 依 ID 刪。
"""
from sqlalchemy import text


async def test_independent_sessions_see_committed_rows(postgres_session_factory, vnext_profile):
    ids = vnext_profile  # session A 已在 fixture 內 commit User/JobProfile

    # session B：全新 AsyncSession/transaction，必須看見 A 的 commit
    async with postgres_session_factory() as session_b:
        row = (await session_b.execute(
            text("SELECT job_title, user_id FROM job_profiles WHERE id = :profile_id"),
            {"profile_id": str(ids.profile_id)},
        )).one()
    assert row.job_title == "vNext 整合測試職務"
    assert str(row.user_id) == str(ids.user_id)


async def test_vnext_ids_are_case_unique_and_tenant_is_not_user(vnext_ids):
    values = {vnext_ids.tenant_id, vnext_ids.user_id, vnext_ids.profile_id,
              vnext_ids.session_id, vnext_ids.run_id}
    assert len(values) == 5  # 各 identity 獨立產生；tenant_id ≠ user_id（§2.3）
