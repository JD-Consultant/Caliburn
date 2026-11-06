"""從公開批次能力驗證提交、持久身分與 Workspace 範圍。"""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine

from caliburn.modules.model_references import (
    ReferenceTarget,
    ResourceKind,
    UnknownModelReferenceError,
)
from caliburn.modules.model_references.persistence import SqlAlchemyModelReferences
from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.infrastructure.persistence.unit_of_work import (
    SqlAlchemyWorkspaceUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import (
    create_database_engine,
    create_session_factory,
)


def test_batch_assignments_survive_new_engine_and_repeated_allocation(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    references = SqlAlchemyModelReferences(create_session_factory(pg_engine))
    task = ReferenceTarget("task", uuid4())
    message = ReferenceTarget("message", uuid4())
    citation = ReferenceTarget("citation", uuid4())
    assigned = references.get_or_create_refs(
        jd_workspace_id, [task, message, task, citation]
    )

    assert set(assigned) == {task, message, citation}
    assert assigned[task].startswith("task_")
    assert assigned[message].startswith("message_")
    assert assigned[citation].startswith("citation_")
    assert assigned[task] != assigned[message]

    reopened_engine = create_database_engine(pg_engine.url)
    try:
        reopened = SqlAlchemyModelReferences(create_session_factory(reopened_engine))
        assert (
            reopened.get_or_create_refs(jd_workspace_id, [message, task, citation])
            == assigned
        )
        assert reopened.resolve_refs(jd_workspace_id, list(assigned.values())) == {
            assigned[task]: task,
            assigned[message]: message,
            assigned[citation]: citation,
        }
    finally:
        reopened_engine.dispose()


@pytest.mark.parametrize("unknown", ["missing", "wrong_kind", "other_workspace"])
def test_resolution_rejects_whole_batch_when_one_reference_is_out_of_scope(
    pg_engine: Engine, jd_workspace_id: UUID, unknown: str
) -> None:
    sessions = create_session_factory(pg_engine)
    references = SqlAlchemyModelReferences(sessions)
    task = ReferenceTarget("task", uuid4())
    known = references.get_or_create_refs(jd_workspace_id, [task])[task]
    if unknown == "missing":
        rejected = "task_9223372036854775807"
    elif unknown == "wrong_kind":
        rejected = known.replace("task_", "message_")
    else:
        other = WorkspaceService(
            lambda: SqlAlchemyWorkspaceUnitOfWork(sessions)
        ).create(interviewee_name="隔離工作區")
        rejected = references.get_or_create_refs(other.workspace_id, [task])[task]

    with pytest.raises(UnknownModelReferenceError) as error:
        references.resolve_refs(jd_workspace_id, [known, rejected])

    assert error.value.reference == rejected


def test_all_kinds_and_same_uuid_have_distinct_stable_references(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    kinds: tuple[ResourceKind, ...] = (
        "message",
        "duty",
        "task",
        "outcome",
        "requirement",
        "knowledge",
        "skill",
        "collaboration",
        "condition",
        "occupation",
        "citation",
    )
    resource_id = uuid4()
    targets = [ReferenceTarget(kind, resource_id) for kind in kinds]
    references = SqlAlchemyModelReferences(create_session_factory(pg_engine))

    assigned = references.get_or_create_refs(jd_workspace_id, targets)

    assert set(assigned) == set(targets)
    assert len(set(assigned.values())) == 11
    assert references.resolve_refs(jd_workspace_id, list(assigned.values()) * 2) == {
        reference: target for target, reference in assigned.items()
    }
    new_task = ReferenceTarget("task", uuid4())
    combined = references.get_or_create_refs(jd_workspace_id, [targets[2], new_task])
    assert combined[targets[2]] == assigned[targets[2]]
    assert combined[new_task] not in assigned.values()


def test_target_lifecycle_does_not_reassign_or_require_business_rows(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    references = SqlAlchemyModelReferences(create_session_factory(pg_engine))
    original = ReferenceTarget("task", uuid4())
    replacement = ReferenceTarget("task", uuid4())
    old_ref = references.get_or_create_refs(jd_workspace_id, [original])[original]
    new_ref = references.get_or_create_refs(jd_workspace_id, [replacement])[replacement]

    # 映射不依賴業務表存在；刪除／撤回資格由 owner 判斷，恢復同 UUID 仍得原碼。
    assert new_ref != old_ref
    assert references.resolve_refs(jd_workspace_id, [old_ref]) == {old_ref: original}
    assert references.get_or_create_refs(jd_workspace_id, [original]) == {
        original: old_ref
    }


def test_workspace_deletion_removes_only_its_references(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    sessions = create_session_factory(pg_engine)
    references = SqlAlchemyModelReferences(sessions)
    workspaces = WorkspaceService(lambda: SqlAlchemyWorkspaceUnitOfWork(sessions))
    survivor = workspaces.create(interviewee_name="保留工作區")
    target = ReferenceTarget("occupation", uuid4())
    deleted_ref = references.get_or_create_refs(jd_workspace_id, [target])[target]
    surviving_ref = references.get_or_create_refs(survivor.workspace_id, [target])[
        target
    ]
    assert deleted_ref != surviving_ref

    workspaces.delete(workspace_id=jd_workspace_id)

    with pytest.raises(UnknownModelReferenceError):
        references.resolve_refs(jd_workspace_id, [deleted_ref])
    assert references.resolve_refs(survivor.workspace_id, [surviving_ref]) == {
        surviving_ref: target
    }
