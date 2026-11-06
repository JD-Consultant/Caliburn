"""公開 JD 歷史、淨差異與恢復，使用真 PostgreSQL 與獨立 Session。"""

import base64
import json
from functools import partial
from uuid import UUID, uuid7

import pytest
from pydantic import ValidationError
from sqlalchemy import Engine

from caliburn.modules.job_description.application.collaborations import (
    add_collaboration,
)
from caliburn.modules.job_description.application.conditions import add_condition
from caliburn.modules.job_description.application.duties import (
    UpdateDutyInput,
    add_duty,
    update_duty,
)
from caliburn.modules.job_description.application.errors import (
    InvalidHistoryPaginationError,
    JobDescriptionConcurrencyError,
    JobDescriptionHistoryNotFoundError,
    JobDescriptionNotFoundError,
)
from caliburn.modules.job_description.application.history.operations import (
    RestoreJobDescriptionInput,
    compare_history,
    get_history,
    list_history,
    restore,
)
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.application.job_descriptions import (
    UpdateJobDescriptionInput,
    create_job_description,
    update_job_description,
)
from caliburn.modules.job_description.application.knowledge import (
    add_knowledge,
    delete_knowledge,
)
from caliburn.modules.job_description.application.placement import PlacementInput
from caliburn.modules.job_description.application.tasks.inputs import (
    AddTaskInput,
    ExistingDefinitionInput,
    NewDefinitionInput,
    TaskPlacementInput,
    UpdateRequirementInput,
    UpdateTaskInput,
)
from caliburn.modules.job_description.application.tasks.lifecycle import (
    add_task,
    delete_task,
    update_task,
)
from caliburn.modules.job_description.domain.models.condition_kind import ConditionKind
from caliburn.modules.job_description.infrastructure.persistence.queries import (
    SqlAlchemyJobDescriptionQueries,
)
from caliburn.modules.job_description.infrastructure.persistence.unit_of_work import (
    SqlAlchemyJobDescriptionUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory


@pytest.fixture
def complete_jd(pg_engine: Engine, jd_workspace_id: UUID) -> JobDescriptionResult:
    factory = partial(
        SqlAlchemyJobDescriptionUnitOfWork, create_session_factory(pg_engine)
    )
    current = create_job_description(workspace_id=jd_workspace_id, uow_factory=factory)
    for name in ("分析", "交付"):
        current = add_duty(
            workspace_id=jd_workspace_id,
            job_description_id=current.job_description_id,
            expected_version=current.version,
            name=name,
            uow_factory=factory,
        )
    current = add_knowledge(
        workspace_id=jd_workspace_id,
        job_description_id=current.job_description_id,
        expected_version=current.version,
        name="既有法規",
        uow_factory=factory,
    )
    current = add_task(
        workspace_id=jd_workspace_id,
        input=AddTaskInput(
            job_description_id=current.job_description_id,
            expected_version=current.version,
            name="訪談",
            duty_id=current.duties[0].id,
            outcomes=("訪談紀錄", "需求文件"),
            requirements=("完整性", "可追查"),
            knowledge=(
                ExistingDefinitionInput(id=current.knowledge[0].id),
                NewDefinitionInput(name="研究方法"),
            ),
            skills=(NewDefinitionInput(name="分析"),),
        ),
        uow_factory=factory,
    )
    current = add_collaboration(
        workspace_id=jd_workspace_id,
        job_description_id=current.job_description_id,
        expected_version=current.version,
        collaborator_name="主管",
        scope="核對",
        uow_factory=factory,
    )
    return add_condition(
        workspace_id=jd_workspace_id,
        job_description_id=current.job_description_id,
        expected_version=current.version,
        kind=ConditionKind.QUALIFICATION,
        text="相關經驗",
        uow_factory=factory,
    )


def test_complete_historical_cut_keeps_unchanged_parents_and_changed_child(
    pg_engine: Engine,
    complete_jd: JobDescriptionResult,
) -> None:
    """只改 P 時，Task 舊列與 O／K/S／協作條件仍組成同一保存點的完整 JD。"""
    factory = partial(
        SqlAlchemyJobDescriptionUnitOfWork, create_session_factory(pg_engine)
    )
    before = complete_jd
    task = before.tasks[0]
    written = update_task(
        workspace_id=complete_jd.workspace_id,
        input=UpdateTaskInput(
            job_description_id=before.job_description_id,
            task_id=task.id,
            expected_version=before.version,
            correlation_id="round-A",
            changes=(
                UpdateRequirementInput(id=task.requirements[0].id, text="修正要求"),
            ),
        ),
        uow_factory=factory,
    )
    after = written
    queries = SqlAlchemyJobDescriptionQueries(pg_engine)
    old = get_history(
        workspace_id=complete_jd.workspace_id,
        job_description_id=before.job_description_id,
        version=before.version,
        queries=queries,
    )
    new = get_history(
        workspace_id=complete_jd.workspace_id,
        job_description_id=after.job_description_id,
        version=after.version,
        queries=queries,
    )
    assert old.content.model_dump() == before.model_dump(exclude={"version"})
    assert new.content.model_dump() == after.model_dump(exclude={"version"})
    assert old.content.tasks[0].requirements[0].text == "完整性"
    assert new.content.tasks[0].requirements[0].text == "修正要求"
    delta = compare_history(
        workspace_id=complete_jd.workspace_id,
        job_description_id=before.job_description_id,
        before_version=before.version,
        after_version=after.version,
        queries=queries,
    )
    assert [(item.kind, item.id, item.change) for item in delta.items] == [
        ("requirement", task.requirements[0].id, "modified")
    ]
    assert delta.collections == ()
    assert new.entry.version == before.version + 1
    assert new.entry.correlation_id == "round-A"


def test_restore_rebuilds_deleted_entities_links_classification_and_order(
    pg_engine: Engine,
    complete_jd: JobDescriptionResult,
) -> None:
    """多次修改後恢復舊內容，原 UUID 復活、版本前進，舊歷史仍可查。"""
    factory = partial(
        SqlAlchemyJobDescriptionUnitOfWork, create_session_factory(pg_engine)
    )
    initial = complete_jd
    current = update_task(
        workspace_id=complete_jd.workspace_id,
        input=UpdateTaskInput(
            job_description_id=initial.job_description_id,
            task_id=initial.tasks[0].id,
            expected_version=initial.version,
            placement=TaskPlacementInput(destination_duty_id=initial.duties[1].id),
        ),
        uow_factory=factory,
    )
    moved = current
    current = update_duty(
        workspace_id=complete_jd.workspace_id,
        input=UpdateDutyInput(
            job_description_id=current.job_description_id,
            duty_id=current.duties[1].id,
            expected_version=current.version,
            placement=PlacementInput(before_id=current.duties[0].id),
        ),
        uow_factory=factory,
    )
    current = delete_knowledge(
        workspace_id=complete_jd.workspace_id,
        job_description_id=current.job_description_id,
        knowledge_id=current.knowledge[0].id,
        expected_version=current.version,
        uow_factory=factory,
    )
    current = delete_task(
        workspace_id=complete_jd.workspace_id,
        job_description_id=current.job_description_id,
        task_id=current.tasks[0].id,
        expected_version=current.version,
        uow_factory=factory,
    )
    queries = SqlAlchemyJobDescriptionQueries(pg_engine)
    moved_diff = compare_history(
        workspace_id=complete_jd.workspace_id,
        job_description_id=initial.job_description_id,
        before_version=initial.version,
        after_version=moved.version,
        queries=queries,
    )
    assert [(item.kind, item.change) for item in moved_diff.items] == [
        ("task", "modified")
    ]
    assert len(moved_diff.collections) == 2
    restored = restore(
        workspace_id=complete_jd.workspace_id,
        input=RestoreJobDescriptionInput(
            job_description_id=initial.job_description_id,
            target_version=initial.version,
            expected_version=current.version,
            correlation_id="undo-A",
            reverts_correlation_id="round-A",
        ),
        uow_factory=factory,
    )
    result = restored
    assert result.version == current.version + 1
    assert result.tasks[0].id == initial.tasks[0].id
    assert result.tasks[0].knowledge_ids == initial.tasks[0].knowledge_ids
    assert result.tasks[0].duty_id == initial.duties[0].id
    assert tuple(item.id for item in result.duties) == tuple(
        item.id for item in initial.duties
    )
    delta = compare_history(
        workspace_id=complete_jd.workspace_id,
        job_description_id=initial.job_description_id,
        before_version=initial.version,
        after_version=result.version,
        queries=queries,
    )
    assert delta.items == ()
    assert delta.collections == ()
    entry = get_history(
        workspace_id=complete_jd.workspace_id,
        job_description_id=result.job_description_id,
        version=result.version,
        queries=queries,
    ).entry
    assert entry.restored_from_version == initial.version
    assert entry.reverts_correlation_id == "round-A"
    assert (
        get_history(
            workspace_id=complete_jd.workspace_id,
            job_description_id=current.job_description_id,
            version=current.version,
            queries=queries,
        ).content.tasks
        == ()
    )


def test_no_difference_restore_is_durable_and_rejects_stale_version(
    pg_engine: Engine,
    complete_jd: JobDescriptionResult,
) -> None:
    """恢復目前同一版仍增版；重播原 expected_version 必須失敗。"""
    factory = partial(
        SqlAlchemyJobDescriptionUnitOfWork, create_session_factory(pg_engine)
    )
    initial = complete_jd
    request = RestoreJobDescriptionInput(
        job_description_id=initial.job_description_id,
        target_version=initial.version,
        expected_version=initial.version,
        correlation_id="undo-marker",
    )
    written = restore(
        workspace_id=initial.workspace_id, input=request, uow_factory=factory
    )
    assert written.version == initial.version + 1
    assert written.model_dump(exclude={"version"}) == initial.model_dump(
        exclude={"version"}
    )
    queries = SqlAlchemyJobDescriptionQueries(pg_engine)
    current = queries.get_job_description(
        workspace_id=initial.workspace_id, job_description_id=initial.job_description_id
    )
    assert current == written
    entry = list_history(
        workspace_id=initial.workspace_id,
        job_description_id=initial.job_description_id,
        correlation_id="undo-marker",
        queries=queries,
    ).items[0]
    assert entry.kind == "restored"
    assert entry.version == written.version
    assert entry.restored_from_version == initial.version
    with pytest.raises(JobDescriptionConcurrencyError):
        restore(workspace_id=initial.workspace_id, input=request, uow_factory=factory)


def test_filtered_keyset_history_keeps_true_predecessor_and_scope(
    pg_engine: Engine,
    jd_workspace_id: UUID,
) -> None:
    """續頁期間新增不重複；游標綁定範圍與篩選。"""
    factory = partial(
        SqlAlchemyJobDescriptionUnitOfWork, create_session_factory(pg_engine)
    )
    first = create_job_description(
        workspace_id=jd_workspace_id, correlation_id="A", uow_factory=factory
    )
    second = update_job_description(
        workspace_id=jd_workspace_id,
        input=UpdateJobDescriptionInput(
            job_description_id=first.job_description_id,
            expected_version=first.version,
            job_title="B",
            correlation_id="B",
        ),
        uow_factory=factory,
    )
    third = update_job_description(
        workspace_id=jd_workspace_id,
        input=UpdateJobDescriptionInput(
            job_description_id=second.job_description_id,
            expected_version=second.version,
            job_title="C",
            correlation_id="A",
        ),
        uow_factory=factory,
    )
    queries = SqlAlchemyJobDescriptionQueries(pg_engine)
    page = list_history(
        workspace_id=jd_workspace_id,
        job_description_id=first.job_description_id,
        queries=queries,
        correlation_id="A",
        page_size=1,
    )
    assert [entry.version for entry in page.items] == [third.version]
    assert page.next_page_token is not None
    fourth = update_job_description(
        workspace_id=jd_workspace_id,
        input=UpdateJobDescriptionInput(
            job_description_id=third.job_description_id,
            expected_version=third.version,
            job_title="D",
            correlation_id="A",
        ),
        uow_factory=factory,
    )
    older = list_history(
        workspace_id=jd_workspace_id,
        job_description_id=first.job_description_id,
        queries=queries,
        correlation_id="A",
        page_token=page.next_page_token,
        page_size=100,
    )
    assert [entry.version for entry in older.items] == [first.version]
    assert older.next_page_token is None
    with pytest.raises(InvalidHistoryPaginationError):
        list_history(
            workspace_id=jd_workspace_id,
            job_description_id=first.job_description_id,
            queries=queries,
            correlation_id="B",
            page_token=page.next_page_token,
        )
    noop = update_job_description(
        workspace_id=jd_workspace_id,
        input=UpdateJobDescriptionInput(
            job_description_id=fourth.job_description_id,
            expected_version=fourth.version,
            job_title="D",
            correlation_id="noop",
        ),
        uow_factory=factory,
    )
    assert noop == fourth
    assert (
        list_history(
            workspace_id=jd_workspace_id,
            job_description_id=first.job_description_id,
            queries=queries,
            correlation_id="noop",
        ).items
        == ()
    )


def test_history_rejects_unknown_versions_and_wrong_workspace(
    pg_engine: Engine,
    complete_jd: JobDescriptionResult,
) -> None:
    queries = SqlAlchemyJobDescriptionQueries(pg_engine)
    current = complete_jd
    with pytest.raises(JobDescriptionHistoryNotFoundError):
        get_history(
            workspace_id=current.workspace_id,
            job_description_id=current.job_description_id,
            version=current.version + 1,
            queries=queries,
        )
    with pytest.raises(JobDescriptionNotFoundError):
        get_history(
            workspace_id=uuid7(),
            job_description_id=current.job_description_id,
            version=current.version,
            queries=queries,
        )
    with pytest.raises(JobDescriptionNotFoundError):
        compare_history(
            workspace_id=current.workspace_id,
            job_description_id=uuid7(),
            before_version=1,
            after_version=current.version,
            queries=queries,
        )
    with pytest.raises((InvalidHistoryPaginationError, ValidationError)):
        list_history(
            workspace_id=current.workspace_id,
            job_description_id=current.job_description_id,
            page_size=-1,
            queries=queries,
        )


def test_restore_can_swap_names_without_transient_uniqueness_failure(
    pg_engine: Engine,
    complete_jd: JobDescriptionResult,
) -> None:
    """恢復交換過的名稱在同次提交檢查唯一性，不留臨時名或額外歷史。"""
    factory = partial(
        SqlAlchemyJobDescriptionUnitOfWork, create_session_factory(pg_engine)
    )
    original = complete_jd
    first, second = original.duties
    current = original
    for duty_id, name in (
        (first.id, "暫存名稱"),
        (second.id, first.name),
        (first.id, second.name),
    ):
        current = update_duty(
            workspace_id=complete_jd.workspace_id,
            input=UpdateDutyInput(
                job_description_id=current.job_description_id,
                duty_id=duty_id,
                expected_version=current.version,
                name=name,
            ),
            uow_factory=factory,
        )
    result = restore(
        workspace_id=complete_jd.workspace_id,
        input=RestoreJobDescriptionInput(
            job_description_id=original.job_description_id,
            target_version=original.version,
            expected_version=current.version,
        ),
        uow_factory=factory,
    )
    assert [(item.id, item.name) for item in result.duties] == [
        (first.id, first.name),
        (second.id, second.name),
    ]
    queries = SqlAlchemyJobDescriptionQueries(pg_engine)
    page = list_history(
        workspace_id=complete_jd.workspace_id,
        job_description_id=current.job_description_id,
        queries=queries,
    )
    assert page.items[0].kind == "restored"
    assert page.items[0].version == current.version + 1


def test_restore_rejects_stale_version(
    pg_engine: Engine,
    complete_jd: JobDescriptionResult,
) -> None:
    """恢復必須使用呼叫者原版本，不能覆寫已成立的新編修。"""
    factory = partial(
        SqlAlchemyJobDescriptionUnitOfWork, create_session_factory(pg_engine)
    )
    old = complete_jd
    current = update_job_description(
        workspace_id=complete_jd.workspace_id,
        input=UpdateJobDescriptionInput(
            job_description_id=old.job_description_id,
            expected_version=old.version,
            purpose="修改目的",
        ),
        uow_factory=factory,
    )
    with pytest.raises(JobDescriptionConcurrencyError) as error:
        restore(
            workspace_id=complete_jd.workspace_id,
            input=RestoreJobDescriptionInput(
                job_description_id=old.job_description_id,
                target_version=old.version,
                expected_version=old.version,
            ),
            uow_factory=factory,
        )
    assert type(error.value) is JobDescriptionConcurrencyError
    assert (
        SqlAlchemyJobDescriptionQueries(pg_engine).get_job_description(
            workspace_id=old.workspace_id, job_description_id=old.job_description_id
        )
        == current
    )


@pytest.mark.parametrize("version", [2**31, 2**63, 2**128])
def test_oversized_history_cursor_is_invalid_request(
    pg_engine: Engine, complete_jd: JobDescriptionResult, version: int
) -> None:
    token = base64.urlsafe_b64encode(
        json.dumps(
            [
                1,
                [
                    str(complete_jd.workspace_id),
                    str(complete_jd.job_description_id),
                    None,
                    None,
                ],
                version,
            ]
        ).encode()
    ).decode()
    with pytest.raises(InvalidHistoryPaginationError):
        list_history(
            workspace_id=complete_jd.workspace_id,
            job_description_id=complete_jd.job_description_id,
            queries=SqlAlchemyJobDescriptionQueries(pg_engine),
            page_token=token,
        )


@pytest.mark.parametrize("version", [2**31, 2**53 - 1, 2**128])
def test_unstored_large_versions_are_not_found_after_scope_check(
    pg_engine: Engine,
    complete_jd: JobDescriptionResult,
    version: int,
) -> None:
    queries = SqlAlchemyJobDescriptionQueries(pg_engine)
    scope = {
        "workspace_id": complete_jd.workspace_id,
        "job_description_id": complete_jd.job_description_id,
    }
    with pytest.raises(JobDescriptionHistoryNotFoundError):
        get_history(**scope, version=version, queries=queries)
    with pytest.raises(JobDescriptionHistoryNotFoundError):
        compare_history(
            **scope,
            before_version=complete_jd.version,
            after_version=version,
            queries=queries,
        )
    with pytest.raises(JobDescriptionHistoryNotFoundError):
        restore(
            workspace_id=complete_jd.workspace_id,
            input=RestoreJobDescriptionInput(
                job_description_id=complete_jd.job_description_id,
                target_version=version,
                expected_version=complete_jd.version,
            ),
            uow_factory=partial(
                SqlAlchemyJobDescriptionUnitOfWork, create_session_factory(pg_engine)
            ),
        )
    with pytest.raises(JobDescriptionNotFoundError):
        get_history(
            workspace_id=uuid7(),
            job_description_id=complete_jd.job_description_id,
            version=version,
            queries=queries,
        )
