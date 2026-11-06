"""以真 PostgreSQL 驗證訪談兩表、範圍外鍵與所有權清除。"""

from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from psycopg import Error as PostgresError
from sqlalchemy import Engine, inspect, text
from sqlalchemy.exc import IntegrityError

from caliburn.modules.interview.application.recording import (
    record_answers,
    record_opening,
    record_questions,
    record_turn_input,
)
from caliburn.modules.interview.domain.models.interview_turn import InterviewTurn
from caliburn.modules.interview.domain.models.message_content import (
    AnswerInput,
    Question,
)
from caliburn.modules.interview.infrastructure.persistence.unit_of_work import (
    SqlAlchemyInterviewUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory


def test_interview_migration_roundtrip_matches_metadata(pg_engine: Engine) -> None:
    backend = Path(__file__).resolve().parents[2]
    config = Config(str(backend / "alembic.ini"))
    with pg_engine.begin() as connection:
        config.attributes["connection"] = connection
        schema = inspect(connection)
        assert {"interview_turns", "interview_messages"} <= set(
            schema.get_table_names()
        )
        assert schema.get_pk_constraint("interview_turns")["constrained_columns"] == [
            "workspace_id",
            "turn_id",
        ]
        assert {
            tuple(item["constrained_columns"]): (
                item["referred_table"],
                item["options"].get("ondelete"),
            )
            for item in schema.get_foreign_keys("interview_messages")
        } == {
            ("workspace_id", "turn_id"): ("interview_turns", "CASCADE"),
            ("reply_to_message_id", "workspace_id", "turn_id"): (
                "interview_messages",
                None,
            ),
        }
        command.downgrade(config, "0005_plans")
        assert not {"interview_turns", "interview_messages"} & set(
            inspect(connection).get_table_names()
        )
        command.upgrade(config, "head")
        command.check(config)


@pytest.mark.parametrize("foreign_workspace", [False, True])
def test_database_rejects_answer_outside_original_question_scope(
    pg_engine: Engine, jd_workspace_id: UUID, foreign_workspace: bool
) -> None:
    sessions = create_session_factory(pg_engine)
    turn = InterviewTurn.create_conversation(
        workspace_id=jd_workspace_id, turn_id=uuid4(), text="原輪"
    )
    (question,) = turn.record_questions((Question(question="原題"),))
    with SqlAlchemyInterviewUnitOfWork(sessions) as uow:
        uow.turns.get_or_create_for_update(turn)
        uow.commit()
    target_workspace = uuid4() if foreign_workspace else jd_workspace_id
    target_turn = turn.turn_id if foreign_workspace else uuid4()
    with pg_engine.begin() as connection:
        if foreign_workspace:
            connection.execute(
                text("INSERT INTO workspaces VALUES (:id, '另一份合成訪談')"),
                {"id": target_workspace},
            )
        connection.execute(
            text("""
                INSERT INTO interview_turns
                    (workspace_id, turn_id, kind, created_at)
                VALUES (:workspace, :turn, 'conversation', now())
            """),
            {"workspace": target_workspace, "turn": target_turn},
        )
    with pytest.raises(IntegrityError) as rejected:
        with pg_engine.begin() as connection:
            connection.execute(
                text("""
                    INSERT INTO interview_messages
                        (id, workspace_id, turn_id, position, speaker, kind,
                         content, reply_to_message_id, created_at)
                    VALUES (:id, :workspace, :turn, 0, 'employee', 'answer',
                            CAST(:content AS jsonb), :question, now())
                """),
                {
                    "id": uuid4(),
                    "workspace": target_workspace,
                    "turn": target_turn,
                    "question": question.id,
                    "content": '{"selected":[],"custom":null}',
                },
            )
    assert isinstance(rejected.value.orig, PostgresError)
    assert rejected.value.orig.diag.constraint_name == "fk_interview_messages_reply"


@pytest.mark.parametrize(
    ("assignment", "constraint"),
    [
        ("position=-1", "ck_interview_messages_position"),
        ("kind='question', speaker='employee'", "ck_interview_messages_kind_speaker"),
        ("reply_to_message_id=id", "ck_interview_messages_reply"),
    ],
)
def test_database_rejects_invalid_message_shape(
    pg_engine: Engine, jd_workspace_id: UUID, assignment: str, constraint: str
) -> None:
    turn = InterviewTurn.create_conversation(
        workspace_id=jd_workspace_id, turn_id=uuid4(), text="資料庫約束"
    )
    with SqlAlchemyInterviewUnitOfWork(create_session_factory(pg_engine)) as uow:
        uow.turns.get_or_create_for_update(turn)
        uow.commit()
    with pytest.raises(IntegrityError) as rejected:
        with pg_engine.begin() as connection:
            connection.execute(
                text(f"UPDATE interview_messages SET {assignment} WHERE id=:id"),
                {"id": turn.messages[0].id},
            )
    assert isinstance(rejected.value.orig, PostgresError)
    assert rejected.value.orig.diag.constraint_name == constraint


def test_database_enforces_one_opening_per_workspace(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    record_opening(
        workspace_id=jd_workspace_id,
        text="固定開場",
        uow_factory=lambda: SqlAlchemyInterviewUnitOfWork(
            create_session_factory(pg_engine)
        ),
    )
    with pytest.raises(IntegrityError) as rejected:
        with pg_engine.begin() as connection:
            connection.execute(
                text("""
                INSERT INTO interview_turns (workspace_id, turn_id, kind, created_at)
                VALUES (:workspace, :turn, 'opening', now())
            """),
                {"workspace": jd_workspace_id, "turn": uuid4()},
            )
    assert isinstance(rejected.value.orig, PostgresError)
    assert rejected.value.orig.diag.constraint_name == "uq_interview_turns_opening"


def test_database_enforces_one_answer_per_question(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    def factory() -> SqlAlchemyInterviewUnitOfWork:
        return SqlAlchemyInterviewUnitOfWork(create_session_factory(pg_engine))

    turn_id = uuid4()
    record_turn_input(
        workspace_id=jd_workspace_id, turn_id=turn_id, text="原文", uow_factory=factory
    )
    (question,) = record_questions(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        questions=(Question(question="問題"),),
        uow_factory=factory,
    )
    (answer,) = record_answers(
        workspace_id=jd_workspace_id,
        turn_id=turn_id,
        answers=(AnswerInput(question_message_id=question.message_id),),
        uow_factory=factory,
    )
    with pytest.raises(IntegrityError) as rejected:
        with pg_engine.begin() as connection:
            connection.execute(
                text("""
                INSERT INTO interview_messages
                    (id, workspace_id, turn_id, position, speaker, kind,
                     content, reply_to_message_id, created_at)
                SELECT :id, workspace_id, turn_id, position + 1, speaker, kind,
                    content, reply_to_message_id, created_at
                FROM interview_messages WHERE id=:original
            """),
                {"id": uuid4(), "original": answer.message_id},
            )
    assert isinstance(rejected.value.orig, PostgresError)
    assert rejected.value.orig.diag.constraint_name == "uq_interview_messages_reply"
