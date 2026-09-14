import asyncio
import json
import os
import sys
from uuid import UUID

from app.adapters.langgraph.postgres import open_postgres_consultant_runtime
from app.config import settings
from app.consultant.skill_backend import CONSULTANT_SKILL_IDS
from app.consultant.workspace_resources import WorkspaceCatalog
from app.consultant.workspace_resources import parse_workspace_files
from app.consultant.workspace_state import StoreBackedWorkspace
from app.consultant.workspace_validation import validate_workspace_payload


if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def main() -> None:
    document_id = UUID(os.environ["SMOKE_DOCUMENT_ID"])
    async with open_postgres_consultant_runtime(settings.database_url) as runtime:
        snapshot = await runtime.reopen_document(document_id)
        workspace = StoreBackedWorkspace(store=runtime.store, document_id=document_id)
        current = await workspace.read_snapshot()
        sources = await runtime.list_sources(document_id)
        catalog = WorkspaceCatalog.from_snapshot(
            snapshot.approved_document,
            sources=sources,
            handle_registry=current.manifest.entity_ids_by_handle,
        )
        validation = validate_workspace_payload(
            current.files,
            catalog=catalog,
            selected_skill_ids=CONSULTANT_SKILL_IDS,
            loaded_skill_ids=CONSULTANT_SKILL_IDS,
        )
        raw_document_error = None
        try:
            draft = parse_workspace_files(
                document_id,
                current.files,
                handle_registry=catalog.handle_to_stable,
                baseline_document=snapshot.approved_document,
            )
            draft.approved_document
        except Exception as error:
            raw_document_error = f"{type(error).__name__}: {error}"
        evidence = (snapshot.latest_run or {}).get("execution_evidence") or {}
        resources = {}
        for path, content in current.files.items():
            if not path.endswith(".json"):
                continue
            try:
                payload = json.loads(content)
            except json.JSONDecodeError:
                resources[path] = {"invalid_json": True}
                continue
            resource_evidence = payload.get("evidence") or []
            resources[path] = {
                "handle": payload.get("handle"),
                "statement": payload.get("statement"),
                "duty_handle": payload.get("duty_handle"),
                "task_handles": payload.get("task_handles"),
                "evidence_skill_ids": sorted({
                    skill_id
                    for item in resource_evidence
                    for skill_id in item.get("skill_ids", [])
                }),
            }
        print(json.dumps({
            "run": {
                "run_id": (snapshot.latest_run or {}).get("run_id"),
                "status": (snapshot.latest_run or {}).get("status"),
                "error_code": (snapshot.latest_run or {}).get("error_code"),
            },
            "manifest": {
                "status": current.manifest.validation_status,
                "diagnostics": [item.model_dump(mode="json") for item in current.manifest.diagnostics],
            },
            "live": {
                "has_document": validation.document is not None,
                "diagnostics": [item.model_dump(mode="json") for item in validation.diagnostics],
            },
            "raw_document_error": raw_document_error,
            "source_handles": {
                str(source.source_id): catalog.source_handle_for_id(source.source_id)
                for source in sources
            },
            "resources": resources,
            "attempts": [{
                "attempt_kind": item.get("attempt_kind"),
                "status": item.get("status"),
                "actual_model": item.get("actual_model"),
                "actual_provider": item.get("actual_provider"),
                "finish_reason": item.get("finish_reason"),
                "error_code": item.get("error_code"),
                "error_message": item.get("error_message"),
                "usage": item.get("usage"),
                "cost_usd": item.get("cost_usd"),
            } for item in evidence.get("attempt_receipts") or []],
        }, ensure_ascii=False, indent=2, default=str))


asyncio.run(main())
