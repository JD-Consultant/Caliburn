"""No-key read-only product HTTP citation probe for completed pilot artifacts."""

import asyncio
import json

import httpx2
import uvicorn
from evidence import collect_sources
from manifest import HERE
from run_batch import BASE, DSN, save

from caliburn import bootstrap
from caliburn.adapters.database_settings import DatabaseSettings
from caliburn.settings import Settings


async def main():
    results = []
    for directory in sorted((HERE / "pilot-reviewed").glob("warehouse-r1-*")):
        case = json.loads((directory / "case.json").read_text(encoding="utf-8"))
        created = json.loads((directory / "created.json").read_text(encoding="utf-8"))
        formal = json.loads((directory / "formal-jd.json").read_text(encoding="utf-8"))
        app = bootstrap.create_app(
            Settings(
                database=DatabaseSettings(url=DSN, schema=case["schema"]),
                dev_origin=BASE,
            )
        )
        server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=8177, log_level="warning")
        )
        task = asyncio.create_task(server.serve())
        try:
            for _ in range(100):
                if server.started:
                    break
                if task.done():
                    await task
                await asyncio.sleep(0.2)
            async with httpx2.AsyncClient(
                base_url=BASE, timeout=30, trust_env=False, headers={"Origin": BASE}
            ) as client:
                sources = await collect_sources(
                    client,
                    "/api/job-files/" + created["job_file_id"],
                    formal["sources"],
                )
            target = directory / "fixed-source-contents.json"
            if target.exists():
                raise RuntimeError("Pilot fixed source probe already exists")
            save(target, sources)
            results.append(
                {
                    "case": directory.name,
                    "revision_id": sources["formal_revision_id"],
                    "fixed_entries": len(sources["entries"]),
                    "content_types": sorted(
                        {entry["content"]["kind"] for entry in sources["entries"]}
                    ),
                }
            )
        finally:
            server.should_exit = True
            await task
    save(
        HERE / "fixed-source-preflight.json",
        {"credential_read": False, "provider_calls": 0, "results": results},
    )
    print(json.dumps(results, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main(), loop_factory=asyncio.SelectorEventLoop)
