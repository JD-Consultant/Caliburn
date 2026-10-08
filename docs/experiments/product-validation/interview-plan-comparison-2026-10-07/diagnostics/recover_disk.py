"""No-key read-only HTTP recovery after the experiment artifact disk filled."""

import asyncio
import json
import socket
import sys
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
OUTPUT = Path(
    "C:/Users/chenb/.codex/visualizations/2026/10/06/"
    "01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/recovery-disk-complete"
)
sys.path.insert(0, str(HERE))


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def closed():
    with socket.socket() as probe:
        probe.settimeout(0.5)
        return probe.connect_ex(("127.0.0.1", 8177)) != 0


async def main():
    import httpx2
    import uvicorn
    from evidence import collect_sources
    from run_batch import BASE, DSN
    from sqlalchemy import text

    from caliburn import bootstrap
    from caliburn.adapters.database_settings import DatabaseSettings
    from caliburn.settings import Settings

    if not closed():
        raise RuntimeError("Prior product server still active")
    await asyncio.to_thread(OUTPUT.mkdir, parents=True)
    directory = HERE / "formal-append/warehouse-r1-P2"
    case = json.loads((directory / "case.json").read_text(encoding="utf-8"))
    created = json.loads((directory / "created.json").read_text(encoding="utf-8"))
    accepted = json.loads((directory / "turn-12-accepted.json").read_text(encoding="utf-8"))
    originals = {}
    for path in [
        HERE / "formal-append/batch-state.json",
        HERE / "formal-append/manifest.json",
        HERE / "formal-append-console.log",
        *directory.glob("*12*.json"),
    ]:
        data = path.read_bytes()
        target = OUTPUT / "original-bytes" / path.relative_to(HERE)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        originals[str(path)] = {"sha256": sha256(data).hexdigest(), "bytes": len(data)}
    app = bootstrap.create_app(
        Settings(database=DatabaseSettings(url=DSN, schema=case["schema"]), dev_origin=BASE)
    )
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8177, log_level="warning"))
    task = asyncio.create_task(server.serve())
    record = {
        "credential_read": False,
        "provider_calls": 0,
        "prior_server_closed": True,
        "prior_process_exit_code": 1,
        "resource_interruption": "artifact_disk_full",
        "original_bytes": originals,
        "observed_at": datetime.now(UTC).isoformat(),
    }
    try:
        for _ in range(100):
            if server.started:
                break
            if task.done():
                await task
                raise RuntimeError("Read-only recovery app did not start")
            await asyncio.sleep(0.2)
        async with httpx2.AsyncClient(
            base_url=BASE, timeout=60, trust_env=False, headers={"Origin": BASE}
        ) as client:
            path = "/api/job-files/" + created["job_file_id"]

            async def get(suffix):
                response = await client.get(path + suffix)
                response.raise_for_status()
                return response.json()

            status = await get("/consultant-turns/" + accepted["execution_id"])
            interviews = await get("/interviews")
            formal = {
                "profile": await get("/jd/profile"),
                "work": await get("/jd/work"),
                "sources": await get("/jd/sources"),
            }
            save(OUTPUT / "recovered-turn-status.json", status)
            save(OUTPUT / "formal-interviews.json", interviews)
            save(OUTPUT / "formal-jd.json", formal)
            save(OUTPUT / "formal-plan.json", await get("/interview-plan"))
            save(
                OUTPUT / "fixed-source-contents.json",
                await collect_sources(client, path, formal["sources"]),
            )
            record["recovered_turn_status"] = status["status"]
            record["closure_submitted"] = False
        async with app.state.database.sessions() as session:
            rows = (
                await session.execute(
                    text("SELECT status, count(*) FROM executions GROUP BY status")
                )
            ).all()
            record["execution_status_counts"] = {str(state): count for state, count in rows}
    finally:
        server.should_exit = True
        await task
        record["recovery_server_closed"] = closed()
        save(OUTPUT / "recovery-metadata.json", record)
    print(json.dumps({key: value for key, value in record.items() if key != "original_bytes"}))


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
