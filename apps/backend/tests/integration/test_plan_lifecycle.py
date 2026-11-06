"""Plan 公開用例以真 PostgreSQL 驗證最新內容與取消恢復基準。"""

from functools import partial
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine

from caliburn.modules.plan.application.errors import (
    PlanConcurrencyError,
    PlanNotInitializedError,
    PlanVersionNotFoundError,
    WorkspaceNotFoundError,
)
from caliburn.modules.plan.application.plans import (
    initialize_plan,
    patch_plan,
    restore_plan,
)
from caliburn.modules.plan.application.results import PlanView
from caliburn.modules.plan.infrastructure.persistence.queries import (
    SqlAlchemyPlanQueries,
)
from caliburn.modules.plan.infrastructure.persistence.unit_of_work import (
    SqlAlchemyPlanUnitOfWork,
)
from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.infrastructure.persistence.unit_of_work import (
    SqlAlchemyWorkspaceUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory


def test_current_query_preserves_uninitialized_plan(pg_engine: Engine) -> None:
    sessions = create_session_factory(pg_engine)
    workspace = WorkspaceService(
        lambda: SqlAlchemyWorkspaceUnitOfWork(sessions)
    ).create(interviewee_name="Plan 合成測試")
    queries = SqlAlchemyPlanQueries(pg_engine)

    assert queries.get_current(workspace_id=workspace.workspace_id) == PlanView(
        workspace_id=workspace.workspace_id, version=None, body=None
    )
    assert queries.get_current(workspace_id=workspace.workspace_id).version is None


def test_initialization_saves_a_single_reusable_baseline(pg_engine: Engine) -> None:
    sessions = create_session_factory(pg_engine)
    workspace = WorkspaceService(
        lambda: SqlAlchemyWorkspaceUnitOfWork(sessions)
    ).create(interviewee_name="Plan 初始化")

    first = initialize_plan(
        workspace_id=workspace.workspace_id,
        uow_factory=lambda: SqlAlchemyPlanUnitOfWork(sessions),
    )
    second = initialize_plan(
        workspace_id=workspace.workspace_id,
        uow_factory=lambda: SqlAlchemyPlanUnitOfWork(sessions),
    )

    assert (
        first
        == second
        == PlanView(workspace_id=workspace.workspace_id, version=1, body=None)
    )
    assert (
        SqlAlchemyPlanQueries(pg_engine).get_current(
            workspace_id=workspace.workspace_id
        )
        == first
    )


def test_patch_returns_actual_effect_and_latest_saved_content(
    pg_engine: Engine,
) -> None:
    sessions = create_session_factory(pg_engine)
    workspace_id = (
        WorkspaceService(lambda: SqlAlchemyWorkspaceUnitOfWork(sessions))
        .create(interviewee_name="Plan 修改")
        .workspace_id
    )
    factory = partial(SqlAlchemyPlanUnitOfWork, sessions)
    initialize_plan(workspace_id=workspace_id, uow_factory=factory)

    changed = patch_plan(
        workspace_id=workspace_id,
        expected_version=1,
        diff="@@\n+# 訪談計畫\n+先確認工作範圍\n*** End of File",
        uow_factory=factory,
    )

    assert changed.changed is True
    assert changed.plan == PlanView(workspace_id, 2, "# 訪談計畫\n先確認工作範圍")
    assert changed.diff is not None and "+先確認工作範圍" in changed.diff
    assert (
        SqlAlchemyPlanQueries(pg_engine).get_current(workspace_id=workspace_id)
        == changed.plan
    )
    assert (
        initialize_plan(workspace_id=workspace_id, uow_factory=factory) == changed.plan
    )


def test_restore_adopts_saved_body_as_a_new_current_version(pg_engine: Engine) -> None:
    sessions = create_session_factory(pg_engine)
    workspace_id = (
        WorkspaceService(lambda: SqlAlchemyWorkspaceUnitOfWork(sessions))
        .create(interviewee_name="Plan 恢復")
        .workspace_id
    )
    factory = partial(SqlAlchemyPlanUnitOfWork, sessions)
    initialize_plan(workspace_id=workspace_id, uow_factory=factory)
    patch_plan(
        workspace_id=workspace_id,
        expected_version=1,
        diff="@@\n+輪前安排\n*** End of File",
        uow_factory=factory,
    )
    patch_plan(
        workspace_id=workspace_id,
        expected_version=2,
        diff="@@\n-輪前安排\n+本輪安排",
        uow_factory=factory,
    )

    restored = restore_plan(
        workspace_id=workspace_id,
        expected_version=3,
        target_version=2,
        uow_factory=factory,
    )

    assert restored == PlanView(workspace_id, 4, "輪前安排")
    assert (
        SqlAlchemyPlanQueries(pg_engine).get_current(workspace_id=workspace_id)
        == restored
    )
    assert (
        restore_plan(
            workspace_id=workspace_id,
            expected_version=4,
            target_version=2,
            uow_factory=factory,
        )
        == restored
    )
    assert restore_plan(
        workspace_id=workspace_id,
        expected_version=4,
        target_version=3,
        uow_factory=factory,
    ) == PlanView(workspace_id, 5, "本輪安排")


def test_noop_preserves_none_and_still_requires_the_current_version(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    sessions = create_session_factory(pg_engine)
    factory = partial(SqlAlchemyPlanUnitOfWork, sessions)
    initial = initialize_plan(workspace_id=jd_workspace_id, uow_factory=factory)
    noop = patch_plan(
        workspace_id=jd_workspace_id,
        expected_version=1,
        diff="@@\n+\n*** End of File",
        uow_factory=factory,
    )
    assert noop.plan == initial and noop.changed is False and noop.diff is None
    changed = patch_plan(
        workspace_id=jd_workspace_id,
        expected_version=1,
        diff="@@\n+安排\n*** End of File",
        uow_factory=factory,
    )

    for diff in ("@@\n-安排\n+安排", "invalid patch"):
        with pytest.raises(PlanConcurrencyError):
            patch_plan(
                workspace_id=jd_workspace_id,
                expected_version=1,
                diff=diff,
                uow_factory=factory,
            )
    with pytest.raises(PlanConcurrencyError):
        restore_plan(
            workspace_id=jd_workspace_id,
            expected_version=1,
            target_version=1,
            uow_factory=factory,
        )
    assert (
        SqlAlchemyPlanQueries(pg_engine).get_current(workspace_id=jd_workspace_id)
        == changed.plan
    )


def test_clear_and_restore_keep_none_distinct_from_empty_string(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    sessions = create_session_factory(pg_engine)
    factory = partial(SqlAlchemyPlanUnitOfWork, sessions)
    initialize_plan(workspace_id=jd_workspace_id, uow_factory=factory)
    patch_plan(
        workspace_id=jd_workspace_id,
        expected_version=1,
        diff="@@\n+安排\n*** End of File",
        uow_factory=factory,
    )
    cleared = patch_plan(
        workspace_id=jd_workspace_id,
        expected_version=2,
        diff="@@\n-安排",
        uow_factory=factory,
    )
    assert cleared.plan == PlanView(jd_workspace_id, 3, "")
    assert restore_plan(
        workspace_id=jd_workspace_id,
        expected_version=3,
        target_version=1,
        uow_factory=factory,
    ) == PlanView(jd_workspace_id, 4, None)
    assert restore_plan(
        workspace_id=jd_workspace_id,
        expected_version=4,
        target_version=3,
        uow_factory=factory,
    ) == PlanView(jd_workspace_id, 5, "")


def test_missing_workspace_root_and_saved_version_are_distinct(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    sessions = create_session_factory(pg_engine)
    factory = partial(SqlAlchemyPlanUnitOfWork, sessions)
    queries = SqlAlchemyPlanQueries(pg_engine)
    missing = uuid4()
    with pytest.raises(WorkspaceNotFoundError):
        queries.get_current(workspace_id=missing)
    with pytest.raises(WorkspaceNotFoundError):
        initialize_plan(workspace_id=missing, uow_factory=factory)
    with pytest.raises(PlanNotInitializedError):
        patch_plan(
            workspace_id=jd_workspace_id,
            expected_version=1,
            diff="@@\n+安排\n*** End of File",
            uow_factory=factory,
        )
    with pytest.raises(PlanNotInitializedError):
        restore_plan(
            workspace_id=jd_workspace_id,
            expected_version=1,
            target_version=1,
            uow_factory=factory,
        )
    assert queries.get_current(workspace_id=jd_workspace_id).version is None
    initial = initialize_plan(workspace_id=jd_workspace_id, uow_factory=factory)
    other = WorkspaceService(lambda: SqlAlchemyWorkspaceUnitOfWork(sessions)).create(
        interviewee_name="其他 Plan"
    )
    initialize_plan(workspace_id=other.workspace_id, uow_factory=factory)
    patch_plan(
        workspace_id=other.workspace_id,
        expected_version=1,
        diff="@@\n+其他內容\n*** End of File",
        uow_factory=factory,
    )
    with pytest.raises(PlanVersionNotFoundError):
        restore_plan(
            workspace_id=jd_workspace_id,
            expected_version=1,
            target_version=2,
            uow_factory=factory,
        )
    assert queries.get_current(workspace_id=jd_workspace_id) == initial


@pytest.mark.parametrize("version", [0, -1, True, 9_007_199_254_740_992])
def test_invalid_version_preconditions_do_not_change_the_plan(
    pg_engine: Engine, jd_workspace_id: UUID, version: int
) -> None:
    sessions = create_session_factory(pg_engine)
    factory = partial(SqlAlchemyPlanUnitOfWork, sessions)
    initial = initialize_plan(workspace_id=jd_workspace_id, uow_factory=factory)
    with pytest.raises(ValueError):
        patch_plan(
            workspace_id=jd_workspace_id,
            expected_version=version,
            diff="@@\n+安排\n*** End of File",
            uow_factory=factory,
        )
    with pytest.raises(ValueError):
        restore_plan(
            workspace_id=jd_workspace_id,
            expected_version=1,
            target_version=version,
            uow_factory=factory,
        )
    assert (
        SqlAlchemyPlanQueries(pg_engine).get_current(workspace_id=jd_workspace_id)
        == initial
    )
