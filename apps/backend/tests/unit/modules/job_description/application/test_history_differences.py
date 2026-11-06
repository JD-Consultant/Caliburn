"""歷史 Diff 以 UUID 配對，與陣列位置及技術版本分離。"""

from uuid import UUID, uuid7

from caliburn.modules.job_description.application.content import (
    DutyResult,
    JobConditionResult,
    KnowledgeResult,
    TaskResult,
    TaskTextResult,
)
from caliburn.modules.job_description.application.history.differences import (
    compare_contents,
)
from caliburn.modules.job_description.application.history.results import (
    JobDescriptionDifference,
)
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)


def empty_result() -> JobDescriptionResult:
    identity = uuid7()
    return JobDescriptionResult(
        job_description_id=identity,
        workspace_id=uuid7(),
        job_title=None,
        organization_unit=None,
        reports_to=None,
        purpose=None,
        baseline_competency_level=None,
        version=1,
        duties=(),
        tasks=(),
        knowledge=(),
        skills=(),
        collaborations=(),
        conditions=(),
    )


def test_rename_and_reorder_keep_entity_identity() -> None:
    """改名與換位分別呈現，不將換位誤判為刪除再新增。"""
    first = DutyResult(id=uuid7(), name="分析", scope=None)
    second = DutyResult(id=uuid7(), name="交付", scope=None)
    before = empty_result().model_copy(update={"duties": (first, second)})
    renamed = first.model_copy(update={"name": "需求分析"})
    after = before.model_copy(update={"duties": (second, renamed), "version": 2})

    result = compare_contents(
        before, after, before_version=before.version, after_version=after.version
    )

    assert len(result.items) == 1
    item = result.items[0]
    assert (item.kind, item.id, item.change) == ("duty", first.id, "modified")
    assert [(x.field, x.before, x.after) for x in item.fields] == [
        ("name", "分析", "需求分析")
    ]
    assert len(result.collections) == 1
    assert result.collections[0].before_ids == (first.id, second.id)
    assert result.collections[0].after_ids == (second.id, first.id)


def test_technical_versions_do_not_create_content_difference() -> None:
    """A→B→A 的兩端相同，版本不同也回空淨差異。"""
    before = empty_result()
    after = before.model_copy(
        update={
            "version": 3,
        }
    )
    result = compare_contents(
        before, after, before_version=before.version, after_version=after.version
    )
    assert result.items == ()
    assert result.collections == ()


def task(
    *, duty_id: UUID | None = None, knowledge_ids: tuple[UUID, ...] = ()
) -> TaskResult:
    return TaskResult(
        id=uuid7(),
        duty_id=duty_id,
        name="分析任務",
        description=None,
        competency_level=None,
        outcomes=(TaskTextResult(id=uuid7(), text="成果"),),
        requirements=(),
        knowledge_ids=knowledge_ids,
        skill_ids=(),
    )


def difference(
    before: JobDescriptionResult, after: JobDescriptionResult
) -> JobDescriptionDifference:
    return compare_contents(
        before, after, before_version=before.version, after_version=after.version
    )


def test_moving_task_changes_membership_without_recreating_its_content() -> None:
    """跨職責移動保留 Task 與 O 的身分，只列歸屬及兩組順序。"""
    first = DutyResult(id=uuid7(), name="分析", scope=None)
    second = DutyResult(id=uuid7(), name="交付", scope=None)
    item = task(duty_id=first.id)
    before = empty_result().model_copy(
        update={"duties": (first, second), "tasks": (item,)}
    )
    after = before.model_copy(
        update={"tasks": (item.model_copy(update={"duty_id": second.id}),)}
    )
    result = difference(before, after)
    assert [(change.kind, change.id, change.change) for change in result.items] == [
        ("task", item.id, "modified")
    ]
    assert [
        (field.field, field.before, field.after) for field in result.items[0].fields
    ] == [("duty_id", first.id, second.id)]
    groups = {
        change.group: (change.before_ids, change.after_ids)
        for change in result.collections
    }
    assert groups == {first.id: ((item.id,), ()), second.id: ((), (item.id,))}


def test_removing_knowledge_reports_definition_and_references_once() -> None:
    """共用定義移除與 Task 解除引用分開，不把引用當成新 Entity。"""
    knowledge = KnowledgeResult(id=uuid7(), name="法規", description=None)
    item = task(knowledge_ids=(knowledge.id,))
    before = empty_result().model_copy(
        update={"knowledge": (knowledge,), "tasks": (item,)}
    )
    after = before.model_copy(
        update={
            "knowledge": (),
            "tasks": (item.model_copy(update={"knowledge_ids": ()}),),
        }
    )
    result = difference(before, after)
    assert [(change.kind, change.change) for change in result.items] == [
        ("knowledge", "removed")
    ]
    assert {change.collection for change in result.collections} == {
        "knowledge",
        "knowledge_ids",
    }
    assert all(
        change.before_ids == (knowledge.id,) and change.after_ids == ()
        for change in result.collections
    )


def test_new_item_keeps_null_fields_distinct_from_missing_item() -> None:
    """新增記載仍列選填空值，不能因 before/after 都是 None 而漏掉新增。"""
    before = empty_result()
    item = KnowledgeResult(id=uuid7(), name="法規", description=None)
    after = before.model_copy(update={"knowledge": (item,)})
    result = difference(before, after)
    assert result.items[0].change == "added"
    assert [(field.field, field.after) for field in result.items[0].fields] == [
        ("description", None),
        ("name", "法規"),
    ]


def test_cross_group_traversal_order_is_not_a_content_change() -> None:
    """只換扁平遍歷次序，不換各 Duty／條件分類的業務順序。"""
    from caliburn.modules.job_description.domain.models.condition_kind import (
        ConditionKind,
    )

    first = task(duty_id=uuid7())
    second = task(duty_id=uuid7())
    condition = JobConditionResult(
        id=uuid7(), kind=ConditionKind.QUALIFICATION, text="證照"
    )
    environment = JobConditionResult(
        id=uuid7(), kind=ConditionKind.WORK_ENVIRONMENT, text="室內"
    )
    before = empty_result().model_copy(
        update={"tasks": (first, second), "conditions": (condition, environment)}
    )
    after = before.model_copy(
        update={"tasks": (second, first), "conditions": (environment, condition)}
    )
    result = difference(before, after)
    assert result.items == ()
    assert result.collections == ()


def test_same_group_reorder_reports_one_collection_without_item_changes() -> None:
    """同組順序是內容；不逐筆回實體位置移動。"""
    first = task()
    second = task()
    before = empty_result().model_copy(update={"tasks": (first, second)})
    after = before.model_copy(update={"tasks": (second, first)})
    result = difference(before, after)
    assert result.items == ()
    assert len(result.collections) == 1
    assert result.collections[0].before_ids == (first.id, second.id)
    assert result.collections[0].after_ids == (second.id, first.id)
