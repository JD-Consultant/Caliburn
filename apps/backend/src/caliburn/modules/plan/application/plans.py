"""明示初始化、patch 最新正文與供 Agent 取消使用的內容恢復。"""

from collections.abc import Callable
from uuid import UUID

from caliburn.modules.plan.application.errors import (
    PlanConcurrencyError,
    PlanNotInitializedError,
)
from caliburn.modules.plan.application.persistence import PlanUnitOfWork
from caliburn.modules.plan.application.results import PatchPlanResult, PlanView
from caliburn.modules.plan.domain.plan import Plan
from caliburn.modules.plan.domain.snapshot import MAX_PLAN_VERSION
from caliburn.shared.domain.text_editing.body_edits import describe_body_change


def initialize_plan(
    *, workspace_id: UUID, uow_factory: Callable[[], PlanUnitOfWork]
) -> PlanView:
    """保存首版，或回目前版；重複呼叫不清空、不增版。"""
    with uow_factory() as uow:
        uow.plans.lock_workspace(workspace_id=workspace_id)
        plan = uow.plans.get_for_update(workspace_id=workspace_id)
        if plan is None:
            plan = Plan.create(workspace_id=workspace_id)
            uow.plans.add(plan)
        result = PlanView(
            workspace_id=plan.workspace_id, version=plan.version, body=plan.body
        )
        uow.commit()
    return result


def patch_plan(
    *,
    workspace_id: UUID,
    expected_version: int,
    diff: str,
    uow_factory: Callable[[], PlanUnitOfWork],
) -> PatchPlanResult:
    """先核目前版再原子 patch；no-op 不增版，也不略過前置版本。"""
    _require_version(expected_version)
    with uow_factory() as uow:
        plan = _load_current(
            uow, workspace_id=workspace_id, expected_version=expected_version
        )
        before = plan.body
        changed = plan.apply_patch(diff)
        if changed:
            uow.plans.save(plan)
        result = PatchPlanResult(
            plan=PlanView(plan.workspace_id, plan.version, plan.body),
            changed=changed,
            diff=describe_body_change(before or "", plan.body or "")
            if changed
            else None,
        )
        uow.commit()
    return result


def _require_version(version: int) -> None:
    if (
        isinstance(version, bool)
        or not isinstance(version, int)
        or not 1 <= version <= MAX_PLAN_VERSION
    ):
        raise ValueError("Plan 版本必須為可精確表示的正整數")


def _load_current(
    uow: PlanUnitOfWork, *, workspace_id: UUID, expected_version: int
) -> Plan:
    plan = uow.plans.get_for_update(workspace_id=workspace_id)
    if plan is None:
        raise PlanNotInitializedError("Workspace 尚未初始化 Plan")
    if plan.version != expected_version:
        raise PlanConcurrencyError()
    return plan


def restore_plan(
    *,
    workspace_id: UUID,
    expected_version: int,
    target_version: int,
    uow_factory: Callable[[], PlanUnitOfWork],
) -> PlanView:
    """將同根舊內容保存為最新版本；相同內容不增版，不倒退版號。"""
    _require_version(expected_version)
    with uow_factory() as uow:
        plan = _load_current(
            uow, workspace_id=workspace_id, expected_version=expected_version
        )
        _require_version(target_version)
        snapshot = uow.plans.get_snapshot(
            workspace_id=workspace_id, version=target_version
        )
        if plan.restore(snapshot):
            uow.plans.save(plan)
        result = PlanView(plan.workspace_id, plan.version, plan.body)
        uow.commit()
    return result
