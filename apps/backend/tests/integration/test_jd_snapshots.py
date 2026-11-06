"""完整快照與目前關聯式內容的原子保存。"""

from copy import deepcopy
from datetime import timedelta
from functools import partial
from typing import Any
from uuid import UUID, uuid7

import pytest
from sqlalchemy import Engine, inspect, select, text
from sqlalchemy.orm import Session

from caliburn.modules.job_description.application.errors import (
    JobDescriptionHistoryDataError,
    JobDescriptionPersistenceError,
)
from caliburn.modules.job_description.application.history.operations import (
    RestoreJobDescriptionInput,
    compare_history,
    get_history,
    restore,
)
from caliburn.modules.job_description.application.job_descriptions import (
    UpdateJobDescriptionInput,
    update_job_description,
)
from caliburn.modules.job_description.domain.models.collaboration_entry import (
    CollaborationEntry,
)
from caliburn.modules.job_description.domain.models.competency_level import (
    CompetencyLevel,
)
from caliburn.modules.job_description.domain.models.condition_kind import ConditionKind
from caliburn.modules.job_description.domain.models.duty import Duty
from caliburn.modules.job_description.domain.models.job_condition import JobCondition
from caliburn.modules.job_description.domain.models.job_description import (
    JobDescription,
)
from caliburn.modules.job_description.domain.models.job_task import JobTask
from caliburn.modules.job_description.domain.models.knowledge import Knowledge
from caliburn.modules.job_description.domain.models.skill import Skill
from caliburn.modules.job_description.domain.models.task_outcome import TaskOutcome
from caliburn.modules.job_description.domain.models.task_requirement import (
    TaskRequirement,
)
from caliburn.modules.job_description.infrastructure.persistence.orm_models import (
    JobDescriptionSnapshotRow,
)
from caliburn.modules.job_description.infrastructure.persistence.queries import (
    SqlAlchemyJobDescriptionQueries,
)
from caliburn.modules.job_description.infrastructure.persistence.snapshot_codec import (
    encode_snapshot,
)
from caliburn.modules.job_description.infrastructure.persistence.unit_of_work import (
    SqlAlchemyJobDescriptionUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory


def test_creation_records_one_complete_snapshot(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    """新 JD 與 v1 全量快照同次提交，Schema 不再保留列歷史。"""
    root = JobDescription(id=uuid7(), workspace_id=jd_workspace_id)
    with SqlAlchemyJobDescriptionUnitOfWork(create_session_factory(pg_engine)) as uow:
        uow.job_descriptions.add(root)
        uow.commit()

    tables = set(inspect(pg_engine).get_table_names())
    assert "job_description_snapshots" in tables
    assert not {"transaction", "transaction_meta", "job_tasks_version"} & tables
    with pg_engine.connect() as connection:
        snapshot = connection.execute(
            text(
                "SELECT version, schema_version, kind, content "
                "FROM job_description_snapshots WHERE job_description_id = :id"
            ),
            {"id": root.id},
        ).one()
    assert (snapshot.version, snapshot.schema_version, snapshot.kind) == (
        1,
        2,
        "created",
    )
    assert snapshot.content["job_description_id"] == str(root.id)
    assert snapshot.content["workspace_id"] == str(jd_workspace_id)
    assert snapshot.content["tasks"] == []


def test_names_are_persisted_without_a_parallel_comparison_column(
    pg_engine: Engine,
) -> None:
    """DB 只保存名稱原文，Domain 的判重鍵不成為另一份持久狀態。"""
    database = inspect(pg_engine)
    for table in ("duties", "job_tasks", "knowledge", "skills"):
        columns = {column["name"] for column in database.get_columns(table)}
        assert "name_key" not in columns
        assert any(
            constraint["column_names"] == ["job_description_id", "name"]
            for constraint in database.get_unique_constraints(table)
        )


@pytest.fixture
def snapshot_root(pg_engine: Engine, jd_workspace_id: UUID) -> JobDescription:
    jd_id, duty_id, knowledge_id, skill_id = uuid7(), uuid7(), uuid7(), uuid7()
    root = JobDescription(
        id=jd_id,
        workspace_id=jd_workspace_id,
        job_title="  合成職務  ",
        organization_unit="研發",
        reports_to="主管",
        purpose="測試完整保存",
        baseline_competency_level=CompetencyLevel(value=6),
        duties=(
            Duty.create(
                id=duty_id, job_description_id=jd_id, name="分類", scope="範圍"
            ),
        ),
        knowledge=(
            Knowledge.create(
                id=knowledge_id,
                job_description_id=jd_id,
                name="知識",
                description="正文",
            ),
        ),
        skills=(
            Skill.create(
                id=skill_id, job_description_id=jd_id, name="技能", description=None
            ),
        ),
        tasks=tuple(
            JobTask.create(
                id=uuid7(),
                job_description_id=jd_id,
                duty_id=duty_id if index == 0 else None,
                name=f"任務 {index}",
                description="描述" if index == 0 else None,
                competency_level=3 if index == 0 else None,
                outcomes=(
                    TaskOutcome(id=uuid7(), text="產出一"),
                    TaskOutcome(id=uuid7(), text="產出二"),
                ),
                requirements=(
                    TaskRequirement(id=uuid7(), text="要求一"),
                    TaskRequirement(id=uuid7(), text="要求二"),
                ),
                knowledge_ids=(knowledge_id,),
                skill_ids=(skill_id,),
            )
            for index in range(2)
        ),
        collaborations=(
            CollaborationEntry(id=uuid7(), collaborator_name="同事", scope="核對"),
        ),
        conditions=tuple(
            JobCondition(id=uuid7(), kind=kind, text=f"條件 {kind}")
            for kind in ConditionKind
        ),
    )
    with SqlAlchemyJobDescriptionUnitOfWork(create_session_factory(pg_engine)) as uow:
        assert uow.job_descriptions.add(root, correlation_id=" 來源 A ") == 1
        uow.commit()
    return root


def test_snapshot_roundtrip_preserves_full_content_and_json_types(
    pg_engine: Engine,
    snapshot_root: JobDescription,
) -> None:
    queries = SqlAlchemyJobDescriptionQueries(pg_engine)
    result = get_history(
        workspace_id=snapshot_root.workspace_id,
        job_description_id=snapshot_root.id,
        version=1,
        queries=queries,
    )
    assert result.content.model_dump(mode="json") == encode_snapshot(snapshot_root)
    assert result.entry.correlation_id == " 來源 A "
    assert result.entry.recorded_at.utcoffset() == timedelta(0)
    with pg_engine.connect() as connection:
        assert (
            connection.scalar(
                text("SELECT jsonb_typeof(content) FROM job_description_snapshots")
            )
            == "object"
        )


def _corrupt(content: dict[str, Any], damage: str) -> None:
    if damage == "missing_collection":
        del content["tasks"]
    elif damage == "missing_nested_collection":
        del content["tasks"][0]["outcomes"]
    elif damage == "missing_nullable_field":
        del content["reports_to"]
    elif damage == "bad_level":
        content["baseline_competency_level"] = 999
    elif damage == "numeric_string":
        content["baseline_competency_level"] = "3"
    elif damage == "boolean_level":
        content["baseline_competency_level"] = True
    elif damage == "bad_task_level":
        content["tasks"][0]["competency_level"] = 999
    elif damage == "duplicate_knowledge_reference":
        content["tasks"][0]["knowledge_ids"] *= 2
    elif damage == "duplicate_skill_reference":
        content["tasks"][0]["skill_ids"] *= 2
    elif damage == "cross_task_outcome_identity":
        content["tasks"][1]["outcomes"][0]["id"] = content["tasks"][0]["outcomes"][0][
            "id"
        ]
    elif damage == "cross_task_requirement_identity":
        content["tasks"][1]["requirements"][0]["id"] = content["tasks"][0][
            "requirements"
        ][0]["id"]
    elif damage == "missing_knowledge_definition":
        content["knowledge"] = []
    elif damage == "missing_skill_definition":
        content["skills"] = []
    elif damage == "missing_duty":
        content["duties"] = []
    elif damage == "duplicate_name":
        content["tasks"][1]["name"] = content["tasks"][0]["name"]
    elif damage == "invalid_uuid":
        content["tasks"][0]["id"] = "not-a-uuid"
    elif damage == "wrong_jd":
        content["job_description_id"] = str(uuid7())
    elif damage == "wrong_workspace":
        content["workspace_id"] = str(uuid7())
    elif damage == "extra_field":
        content["unknown"] = "data"
    elif damage != "unknown_format":
        raise AssertionError(damage)


@pytest.mark.parametrize(
    "damage",
    [
        "missing_collection",
        "missing_nested_collection",
        "missing_nullable_field",
        "bad_level",
        "numeric_string",
        "boolean_level",
        "bad_task_level",
        "duplicate_knowledge_reference",
        "duplicate_skill_reference",
        "cross_task_outcome_identity",
        "cross_task_requirement_identity",
        "missing_knowledge_definition",
        "missing_skill_definition",
        "missing_duty",
        "duplicate_name",
        "invalid_uuid",
        "wrong_jd",
        "wrong_workspace",
        "extra_field",
        "unknown_format",
    ],
)
def test_corrupt_snapshot_is_rejected_by_read_diff_and_restore_without_partial_write(
    pg_engine: Engine,
    snapshot_root: JobDescription,
    damage: str,
) -> None:
    factory = partial(
        SqlAlchemyJobDescriptionUnitOfWork, create_session_factory(pg_engine)
    )
    current = update_job_description(
        workspace_id=snapshot_root.workspace_id,
        input=UpdateJobDescriptionInput(
            job_description_id=snapshot_root.id, expected_version=1, purpose="下一版"
        ),
        uow_factory=factory,
    )
    with Session(pg_engine) as session, session.begin():
        snapshot = session.get(JobDescriptionSnapshotRow, (snapshot_root.id, 1))
        assert snapshot is not None
        broken = deepcopy(snapshot.content)
        _corrupt(broken, damage)
        snapshot.content = broken
        if damage == "unknown_format":
            snapshot.schema_version = 999
    queries = SqlAlchemyJobDescriptionQueries(pg_engine)
    scope = {
        "workspace_id": snapshot_root.workspace_id,
        "job_description_id": snapshot_root.id,
    }
    with pytest.raises(JobDescriptionHistoryDataError):
        get_history(**scope, version=1, queries=queries)
    with pytest.raises(JobDescriptionHistoryDataError):
        compare_history(**scope, before_version=1, after_version=2, queries=queries)
    with pytest.raises(JobDescriptionHistoryDataError):
        restore(
            workspace_id=snapshot_root.workspace_id,
            input=RestoreJobDescriptionInput(
                job_description_id=snapshot_root.id,
                target_version=1,
                expected_version=2,
            ),
            uow_factory=factory,
        )
    assert queries.get_job_description(**scope) == current
    with Session(pg_engine) as session:
        assert tuple(
            session.scalars(
                select(JobDescriptionSnapshotRow.version).order_by(
                    JobDescriptionSnapshotRow.version
                )
            )
        ) == (1, 2)


def test_snapshot_insert_failure_rolls_back_current_content_and_version(
    pg_engine: Engine,
    snapshot_root: JobDescription,
) -> None:
    """伺服器拒絕快照 INSERT 時，已 flush 的關聯內容與根版一併回滾。"""
    with pg_engine.begin() as connection:
        connection.execute(
            text(
                "CREATE FUNCTION reject_snapshot() RETURNS trigger LANGUAGE plpgsql "
                "AS $$ BEGIN RAISE EXCEPTION 'synthetic snapshot rejection'; END $$"
            )
        )
        connection.execute(
            text(
                "CREATE TRIGGER reject_snapshot BEFORE INSERT ON "
                "job_description_snapshots FOR EACH ROW "
                "EXECUTE FUNCTION reject_snapshot()"
            )
        )
    factory = partial(
        SqlAlchemyJobDescriptionUnitOfWork, create_session_factory(pg_engine)
    )
    with pytest.raises(JobDescriptionPersistenceError) as failure:
        update_job_description(
            workspace_id=snapshot_root.workspace_id,
            input=UpdateJobDescriptionInput(
                job_description_id=snapshot_root.id,
                expected_version=1,
                purpose="不得保存",
            ),
            uow_factory=factory,
        )
    assert failure.value.commit_status == "not_committed"
    queries = SqlAlchemyJobDescriptionQueries(pg_engine)
    current = queries.get_job_description(
        workspace_id=snapshot_root.workspace_id, job_description_id=snapshot_root.id
    )
    assert current is not None and current.version == 1
    assert current.purpose == snapshot_root.purpose
    with pg_engine.connect() as connection:
        assert (
            connection.scalar(text("SELECT count(*) FROM job_description_snapshots"))
            == 1
        )


@pytest.mark.parametrize(
    ("table", "column"),
    [
        ("duties", "name"),
        ("job_tasks", "name"),
        ("knowledge", "name"),
        ("skills", "name"),
        ("task_outcomes", "text"),
        ("task_requirements", "text"),
        ("collaboration_entries", "collaborator_name"),
        ("job_conditions", "text"),
    ],
)
@pytest.mark.parametrize("blank", [" \t\n", "\u2003\u001c"])
def test_database_rejects_blank_required_content(
    pg_engine: Engine,
    snapshot_root: JobDescription,
    table: str,
    column: str,
    blank: str,
) -> None:
    from sqlalchemy.exc import IntegrityError

    # Identifiers are fixed parameter cases, never external input.
    with pytest.raises(IntegrityError), pg_engine.begin() as connection:
        connection.execute(
            text(
                f"UPDATE {table} SET {column} = :blank "
                f"WHERE id = (SELECT id FROM {table} LIMIT 1)"
            ),
            {"blank": blank},
        )


@pytest.mark.parametrize("column", ["correlation_id", "reverts_correlation_id"])
@pytest.mark.parametrize("invalid", ["", "\u2003\u001c", "a" * 201])
def test_database_rejects_invalid_snapshot_source_metadata(
    pg_engine: Engine,
    snapshot_root: JobDescription,
    column: str,
    invalid: str,
) -> None:
    from sqlalchemy.exc import IntegrityError

    restore(
        workspace_id=snapshot_root.workspace_id,
        input=RestoreJobDescriptionInput(
            job_description_id=snapshot_root.id, target_version=1, expected_version=1
        ),
        uow_factory=partial(
            SqlAlchemyJobDescriptionUnitOfWork, create_session_factory(pg_engine)
        ),
    )
    with pytest.raises(IntegrityError), pg_engine.begin() as connection:
        connection.execute(
            text(
                f"UPDATE job_description_snapshots SET {column} = :value "
                "WHERE version = 2"
            ),
            {"value": invalid},
        )
