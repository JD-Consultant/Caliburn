"""同一程序並行比較兩候選，正式 HTTP／SDK／Graph／PG 各自保存可查原件。"""

import asyncio
import json
from dataclasses import replace

import psycopg
import pytest
from psycopg import sql

from caliburn.settings import ModelSettings, Settings
from evaluations import consultant_comparison
from evaluations.consultant_cases import ConsultantCandidate, EvaluationCase
from evaluations.consultant_comparison import (
    prepare_isolated_database,
    run_candidate,
    scripted_composition,
)

pytestmark = pytest.mark.postgres


def test_two_candidates_run_concurrently_with_isolated_context_and_formal_data(
    database_settings, tmp_path
):
    left_database = database_settings
    right_database = prepare_isolated_database(database_settings.url)
    candidates = (
        ConsultantCandidate(
            name="left",
            prompts={"focus": "只屬於甲候選的訪談重點"},
            jd_read_max_result_characters=100,
        ),
        ConsultantCandidate(
            name="right",
            prompts={"focus": "只屬於乙候選的訪談重點"},
            tool_descriptions={"read_jd": "乙候選工具說明"},
            jd_read_max_result_characters=200,
        ),
    )
    settings = Settings(database=left_database, model=ModelSettings(api_key="synthetic"))
    case = EvaluationCase(name="synthetic", inputs=("職稱：前端工程師；單位：產品開發部",))
    for candidate in candidates:
        (tmp_path / candidate.name).mkdir()

    async def compare():
        return await asyncio.gather(
            *(
                run_candidate(
                    replace(settings, database=database),
                    scripted_composition(candidate),
                    case,
                    output_directory=tmp_path / candidate.name,
                )
                for database, candidate in zip(
                    (left_database, right_database), candidates, strict=True
                )
            )
        )

    try:
        with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
            left, right = runner.run(compare())
        assert left.result["job_file_id"] != right.result["job_file_id"]
        for outcome in (left, right):
            assert outcome.diagnostics_available
            result = outcome.result
            assert result["all_inputs_completed"] is True
            assert result["formal_jd"]["profile"]["profile"]["job_title"] == "前端工程師"
        left_diagnostics, right_diagnostics = (
            json.loads((tmp_path / candidate.name / "diagnostics.json").read_text(encoding="utf-8"))
            for candidate in candidates
        )
        assert "只屬於甲候選的訪談重點" in str(left_diagnostics)
        assert "只屬於乙候選的訪談重點" not in str(left_diagnostics)
        assert "只屬於乙候選的訪談重點" in str(right_diagnostics)
        assert "只屬於甲候選的訪談重點" not in str(right_diagnostics)
        assert "乙候選工具說明" in str(right_diagnostics)
        assert "乙候選工具說明" not in str(left_diagnostics)
        for diagnostics, limit in ((left_diagnostics, 100), (right_diagnostics, 200)):
            captured = diagnostics[0]["execution"]["captured_initial_context"]
            assert captured["tool_configuration"] == {"jd_read_max_result_characters": limit}
    finally:
        # 只移除本測試新建並持有的隨機 schema；左側由既有 fixture 管理。
        assert right_database.schema.startswith("eval_")
        with psycopg.connect(database_settings.url, autocommit=True) as connection:
            connection.execute(
                sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(right_database.schema))
            )


def test_failed_evaluation_migration_rolls_back_its_new_namespace(database_settings, monkeypatch):
    def namespaces():
        with psycopg.connect(database_settings.url, autocommit=True) as connection:
            return {
                row[0]
                for row in connection.execute(
                    "SELECT nspname FROM pg_namespace WHERE nspname LIKE 'eval_%'"
                ).fetchall()
            }

    before = namespaces()

    def fail_migration(*_args, **_kwargs):
        raise RuntimeError("synthetic migration failure")

    monkeypatch.setattr(consultant_comparison.command, "upgrade", fail_migration)
    with pytest.raises(RuntimeError, match="synthetic migration"):
        prepare_isolated_database(database_settings.url)
    assert namespaces() == before
