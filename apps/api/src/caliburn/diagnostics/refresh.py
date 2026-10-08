"""Explicitly refresh a local diagnostic copy; never invoke an agent."""

from uuid import UUID

import psycopg
from psycopg import sql
from psycopg.types.json import Jsonb

from caliburn.adapters.database_settings import DatabaseSettings
from caliburn.diagnostics.checkpoints import read_checkpoint_records
from caliburn.diagnostics.projection import collect_initial_context, collect_steps, redact


def refresh_diagnostics(
    settings: DatabaseSettings, *, job_file_id: UUID | None = None, execution_id: UUID | None = None
) -> int:
    """Refresh one explicit scope atomically; source tables are only read.

    A repeatable-read snapshot prevents mixing native channels from different instants.
    Concurrent refresh conflicts fail normally; no background lock/retry subsystem.
    """
    if (job_file_id is None) == (execution_id is None):
        raise ValueError("Select exactly one job_file_id or execution_id")
    dsn = settings.url.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(dsn, autocommit=True, connect_timeout=10) as connection:
        with connection.transaction():
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            connection.execute(
                sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(settings.schema))
            )
            connection.execute("SET LOCAL statement_timeout = '60s'")
            connection.execute("SET LOCAL lock_timeout = '5s'")
            field = "job_file_id" if job_file_id is not None else "execution_id"
            rows = connection.execute(
                sql.SQL(
                    "SELECT e.job_file_id,e.execution_id,e.status,"
                    "it.interview_text,rt.interview_text "
                    "FROM executions e "
                    "LEFT JOIN interview_inputs ii ON ii.execution_id=e.execution_id "
                    "AND ii.job_file_id=e.job_file_id "
                    "LEFT JOIN interview_texts it ON it.source_id=ii.source_id "
                    "AND it.job_file_id=e.job_file_id "
                    "LEFT JOIN interview_replies rr ON rr.execution_id=e.execution_id "
                    "AND rr.job_file_id=e.job_file_id "
                    "LEFT JOIN interview_texts rt ON rt.source_id=rr.source_id "
                    "AND rt.job_file_id=e.job_file_id "
                    "WHERE {}=%s ORDER BY e.created_at,e.execution_id"
                ).format(sql.Identifier("e", field)),
                (job_file_id or execution_id,),
            ).fetchall()
            if not rows:
                if (
                    execution_id is not None
                    or connection.execute(
                        "SELECT 1 FROM job_files WHERE job_file_id=%s", (job_file_id,)
                    ).fetchone()
                    is None
                ):
                    raise ValueError("Selected job file or execution not found")
                return 0
            for file_id, run_id, status, employee_input, final_reply in rows:
                records = sorted(
                    read_checkpoint_records(connection, job_file_id=file_id, execution_id=run_id),
                    key=lambda row: (
                        row["checkpoint_time"],
                        row["thread_id"],
                        row["checkpoint_id"],
                        row["source"] == "pending_write",
                    ),
                )
                steps = collect_steps(records)
                initial_context = collect_initial_context(records)
                connection.execute(
                    "INSERT INTO diagnostic_execution_snapshots "
                    "(job_file_id,execution_id,execution_status,snapshot_at,steps,"
                    "employee_input,final_reply,captured_initial_context) "
                    "VALUES (%s,%s,%s,transaction_timestamp(),%s,%s,%s,%s) "
                    "ON CONFLICT (execution_id) DO UPDATE SET "
                    "execution_status=excluded.execution_status,snapshot_at=excluded.snapshot_at,"
                    "steps=excluded.steps,employee_input=excluded.employee_input,"
                    "final_reply=excluded.final_reply,"
                    "captured_initial_context=excluded.captured_initial_context",
                    (
                        file_id,
                        run_id,
                        status,
                        Jsonb(steps),
                        redact(employee_input),
                        redact(final_reply),
                        Jsonb(initial_context) if initial_context is not None else None,
                    ),
                )
            return len(rows)
