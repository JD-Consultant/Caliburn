"""以固定輸入對照顧問配置；CLI 的 dry-run／scripted 均不呼叫付費模型。

從 apps/api 執行 python -m evaluations.consultant_comparison --help。
已授權的真模型研究可呼叫 run_candidate 並注入有整批費用護欄的 AppComposition；
此入口不宣称每次 execution 的預算就是整批上限，也不另造費用／恢復引擎。
"""

import argparse
import asyncio
import hashlib
import json
import os
import platform
import sys
import zipfile
from dataclasses import asdict
from pathlib import Path
from time import monotonic
from uuid import UUID, uuid4

import httpx2
from alembic import command
from psycopg.conninfo import conninfo_to_dict
from sqlalchemy import create_engine
from sqlalchemy.schema import CreateSchema

from caliburn.adapters.database import migration_config
from caliburn.adapters.database_settings import DatabaseSettings
from caliburn.adapters.openai_responses import create_responses_client
from caliburn.app_composition import AppComposition
from caliburn.bootstrap import create_app
from caliburn.diagnostics.inspection import read_diagnostics
from caliburn.diagnostics.refresh import refresh_diagnostics
from caliburn.settings import ModelSettings, Settings
from evaluations.consultant_cases import (
    ConsultantCandidate,
    ConsultantComparison,
    EvaluationCase,
    PreparedConsultantCandidate,
)

BASE_URL = "http://127.0.0.1:8100"


async def drive_case(
    client: httpx2.AsyncClient, case: EvaluationCase, *, timeout_seconds: float = 60
) -> dict[str, object]:
    """只送案例公開輸入，沿正式 HTTP 等待結果；逾時不自動重送或宣稱完成。"""
    created = await client.post(
        "/api/job-files",
        json={
            "command_id": str(uuid4()),
            "display_name": case.name,
            "employee_name": case.employee_name,
        },
    )
    created.raise_for_status()
    job_file_id = UUID(created.json()["job_file_id"])
    path = f"/api/job-files/{job_file_id}"

    async def read(suffix):
        response = await client.get(path + suffix)
        response.raise_for_status()
        return response.json()

    turns = []
    for message in case.inputs:
        started = monotonic()
        submitted = await client.post(
            path + "/inputs", json={"command_id": str(uuid4()), "text": message}
        )
        submitted.raise_for_status()
        accepted = submitted.json()
        suffix = "/consultant-turns/" + str(UUID(accepted["execution_id"]))
        timed_out = False
        while True:
            current = await read(suffix)
            if current["status"] in {"completed", "cancelled", "failed", "paused"}:
                break
            if monotonic() - started >= timeout_seconds:
                timed_out = True
                break
            await asyncio.sleep(0.05)
        turns.append(
            {
                "accepted": accepted,
                "status": current,
                "observation_timeout": timed_out,
                "elapsed_seconds": monotonic() - started,
            }
        )
        if timed_out or current["status"] != "completed":
            break
    return {
        "job_file_id": str(job_file_id),
        "turns": turns,
        "interviews": await read("/interviews"),
        "formal_jd": {part: await read("/jd/" + part) for part in ("profile", "work", "sources")},
        "formal_plan": await read("/interview-plan"),
        "all_inputs_completed": len(turns) == len(case.inputs)
        and all(turn["status"]["status"] == "completed" for turn in turns),
    }


async def run_candidate(
    settings: Settings,
    composition: AppComposition,
    case: EvaluationCase,
    *,
    timeout_seconds: float = 60,
) -> dict[str, object]:
    """借用已遷移的獨立 namespace；生命週期、工具、保存與取消皆由正式 App 擁有。

    呼叫者負責資料／付費授權與整批護欄，可注入真 SDK、其受控 transport 或本機替身。
    此函式不建立／清除 schema、不改 global、不複製 Agent，結束後保留 checkpoint 原件。
    """
    if settings.database is None or settings.model is None:
        raise ValueError("Evaluation requires explicit database and model settings")
    _require_test_database(settings.database.url)
    if settings.database.schema in {"public", "caliburn"}:
        raise ValueError("Evaluation requires an independently prepared schema")
    if timeout_seconds <= 0:
        raise ValueError("Evaluation observation timeout must be positive")
    app = create_app(settings, composition=composition)
    async with (
        app.router.lifespan_context(app),
        httpx2.AsyncClient(
            transport=httpx2.ASGITransport(app=app),
            base_url=BASE_URL,
            headers={"Origin": BASE_URL},
            trust_env=False,
        ) as client,
    ):
        result = await drive_case(client, case, timeout_seconds=timeout_seconds)
    # 診斷副本只供本機查閱；擷取失敗不改正式訪談／JD，也不偽造成功副本。
    job_file_id = UUID(result["job_file_id"])
    await asyncio.to_thread(refresh_diagnostics, settings.database, job_file_id=job_file_id)
    result["diagnostics"] = await asyncio.to_thread(
        read_diagnostics, settings.database, job_file_id=job_file_id
    )
    result["background_settlement"] = "inspect_diagnostic_execution_statuses"
    return result


def prepare_isolated_database(url: str) -> DatabaseSettings:
    """只新增自有 schema 並使用套件正式 migrations；不刪除舊 namespace。"""
    _require_test_database(url)
    settings = DatabaseSettings(url=url, schema="eval_" + uuid4().hex)
    engine = create_engine(
        settings.sqlalchemy_url, connect_args={"options": f"-c search_path={settings.schema}"}
    )
    try:
        with engine.begin() as connection:
            # CREATE 與 migrations 共用交易；失敗會 rollback，不留下無名半成品 schema。
            connection.execute(CreateSchema(settings.schema))
            configured = migration_config()
            configured.attributes.update(connection=connection, schema=settings.schema)
            command.upgrade(configured, "head")
    finally:
        engine.dispose()
    return settings


def _require_test_database(url: str) -> None:
    info = conninfo_to_dict(url)
    if info.get("host") not in {"localhost", "127.0.0.1", "::1"} or not info.get(
        "dbname", ""
    ).endswith("_test"):
        raise ValueError("Use an explicit loopback database whose name ends in _test")
    # libpq 可由 hostaddr／service 改變實際位置；測試入口只接受明示 URL 的單一目標。
    if any(key in info for key in ("hostaddr", "service", "servicefile")) or any(
        os.environ.get(key) for key in ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE")
    ):
        raise ValueError("Test database target cannot be redirected by hostaddr or service")


def scripted_composition(
    candidate: ConsultantCandidate | PreparedConsultantCandidate,
) -> AppComposition:
    """每個 App 取得自己的 SDK transport 及腳本狀態；沒有共享 model 計數器。"""
    from tests.fixtures.scripted_model import ScriptedModel

    if isinstance(candidate, ConsultantCandidate):
        candidate = candidate.prepare()

    def open_scripted_client(settings: ModelSettings):
        scripted = ScriptedModel(chunk_delay_seconds=0)
        return create_responses_client(
            api_key=settings.api_key,
            timeout_seconds=settings.request_timeout_seconds,
            http_client=httpx2.AsyncClient(transport=httpx2.MockTransport(scripted.handle)),
        )

    return AppComposition(
        consultant_configuration=candidate.configuration,
        interview_plans_enabled=candidate.interview_plans_enabled,
        create_responses_client=open_scripted_client,
    )


def save_new(path: Path, value: object) -> None:
    """保留新原件，不覆寫舊比較／失敗紀錄。"""
    with path.open("x", encoding="utf-8") as output:
        json.dump(value, output, ensure_ascii=False, indent=2)
        output.write("\n")


def save_source_snapshot(directory: Path) -> dict[str, str]:
    """保存受測程式與鎖定依賴原件；不打包環境檔、憑證、資料庫或既有實驗。"""
    api = Path(__file__).resolve().parents[1]
    sources = [
        *sorted(
            path
            for path in (api / "src" / "caliburn").rglob("*")
            if path.suffix in {".py", ".json"}
        ),
        *sorted((api / "evaluations").glob("*.py")),
        api / "tests" / "fixtures" / "scripted_model.py",
        api / "pyproject.toml",
        api / "uv.lock",
    ]
    archive = directory / "source.zip"
    with zipfile.ZipFile(archive, "x", compression=zipfile.ZIP_DEFLATED) as output:
        for path in sources:
            output.write(path, path.relative_to(api).as_posix())
    return {
        "source_archive": archive.name,
        "source_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "python_version": platform.python_version(),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("specification", type=Path)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--scripted", action="store_true")
    parser.add_argument("--database-url", default=os.environ.get("CALIBURN_TEST_DATABASE_URL"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    specification = args.specification.read_bytes()
    comparison = ConsultantComparison.model_validate_json(specification)
    # 與 provider 入口相同，先固定全部候選；case 本身只含不可變字串／tuple。
    case = comparison.case
    candidates = tuple(candidate.prepare() for candidate in comparison.candidates)
    manifest = {
        "mode": "dry_run" if args.dry_run else "scripted",
        "specification_sha256": hashlib.sha256(specification).hexdigest(),
        "case": case.model_dump(mode="json"),
        "candidates": [candidate.manifest() for candidate in candidates],
        "external_provider_calls": 0,
        "quality_scope": "engineering_only; scripted replies do not evaluate model quality",
    }
    if args.dry_run:
        if args.output is not None:
            save_new(args.output, manifest)
        print(json.dumps({"preflight": "passed", "candidates": len(candidates)}))
        return 0
    if args.output is None or not args.database_url:
        parser.error("--scripted requires a fresh --output directory and isolated --database-url")
    args.output.mkdir(parents=True, exist_ok=False)
    manifest.update(save_source_snapshot(args.output))
    save_new(args.output / "manifest.json", manifest)
    for candidate in candidates:
        destination = args.output / candidate.name
        destination.mkdir()
        try:
            database = prepare_isolated_database(args.database_url)
            model = ModelSettings(api_key="synthetic-no-external-provider")
            save_new(
                destination / "runtime.json",
                {
                    "schema": database.schema,
                    "model": {
                        key: value for key, value in asdict(model).items() if key != "api_key"
                    },
                    "diagnostics": "result.json:diagnostics (captured request and actual tools)",
                },
            )
            with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
                result = runner.run(
                    run_candidate(
                        Settings(database=database, model=model, dev_origin=BASE_URL),
                        scripted_composition(candidate),
                        case,
                    )
                )
            save_new(destination / "result.json", result)
            if not result["all_inputs_completed"]:
                return 1
        except Exception as error:
            save_new(destination / "failure.json", {"error_type": type(error).__name__})
            print(
                f"Comparison failed ({type(error).__name__}); originals retained.", file=sys.stderr
            )
            return 1
    print(json.dumps({"comparison": "completed", "output": str(args.output.resolve())}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
