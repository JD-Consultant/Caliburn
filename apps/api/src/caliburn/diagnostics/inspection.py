"""唯讀查閱現有診斷副本及原業務關聯；不觸發 refresh 或模型。"""

from uuid import UUID

import psycopg
from psycopg import sql
from pydantic import JsonValue, TypeAdapter

from caliburn.adapters.database_settings import DatabaseSettings
from caliburn.diagnostics.projection import redact

_DOCUMENTS = TypeAdapter(list[dict[str, JsonValue]])


def read_diagnostics(
    settings: DatabaseSettings, *, job_file_id: UUID | None = None, execution_id: UUID | None = None
) -> list[dict[str, JsonValue]]:
    """輸出帶擷取時點的受控正文；公開 log 不呼叫這個查詢。"""
    if (job_file_id is None) == (execution_id is None):
        raise ValueError("Select exactly one job_file_id or execution_id")
    dsn = settings.url.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(dsn, autocommit=True, connect_timeout=10) as connection:
        with connection.transaction():
            connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            connection.execute(
                sql.SQL("SET LOCAL search_path TO {}").format(sql.Identifier(settings.schema))
            )
            connection.execute("SET LOCAL statement_timeout = '60s'")
            connection.execute("SET LOCAL lock_timeout = '5s'")
            field = "job_file_id" if job_file_id is not None else "execution_id"
            rows = connection.execute(
                sql.SQL("""
                    SELECT jsonb_build_object(
                        'execution', to_jsonb(h),
                        'steps', COALESCE((
                            SELECT jsonb_agg(to_jsonb(s) ORDER BY response_order)
                            FROM diagnostic_model_steps s
                            WHERE s.job_file_id=h.job_file_id AND s.execution_id=h.execution_id
                        ), '[]'::jsonb),
                        'tool_calls', COALESCE((
                            SELECT jsonb_agg(to_jsonb(t) ORDER BY response_order,output_index)
                            FROM diagnostic_tool_calls t
                            WHERE t.job_file_id=h.job_file_id AND t.execution_id=h.execution_id
                        ), '[]'::jsonb)
                    ) FROM diagnostic_execution_history h
                    WHERE {}=%s ORDER BY h.created_at,h.execution_id
                """).format(sql.Identifier("h", field)),
                (job_file_id or execution_id,),
            ).fetchall()
    return _DOCUMENTS.validate_python(redact([row[0] for row in rows]))
