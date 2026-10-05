"""Offline audit counterexamples; existing in-memory fixtures, no model or service."""

from __future__ import annotations

import asyncio
import hashlib
import json
import runpy
from pathlib import Path
from uuid import UUID

from caliburn.features.occupation_references.models import (
    OccupationReferenceState,
    select_references,
)


async def main() -> None:
    root = Path(__file__).resolve().parents[4]
    fixture_path = root / "apps/api/tests/unit/test_occupation_reference_tools.py"
    fixture = runpy.run_path(str(fixture_path))["bound_tools"]
    tools, workflow, client = fixture()
    invalid_query_arguments = {"query": "   "}
    invalid_query_result = json.loads(
        await tools.invoke("search_occupation_references", json.dumps(invalid_query_arguments))
    )
    assert invalid_query_result["code"] == "invalid_arguments"
    assert client.calls == []

    before = OccupationReferenceState(selected_reference_ids=("ref_frontend", "ref_backend"))
    after = select_references(before, ("ref_frontend",))
    assert after.selected_reference_ids == ("ref_frontend",)

    tools.max_result_characters = 64
    long_scope = "正式環境部署由維運負責。" * 16
    workflow.projected_state = {"selected_reference_ids": None, "excluded_work": [long_scope]}
    bounded_read_result = json.loads(await tools.invoke("read_occupation_reference_state", "{}"))
    prepared = await tools.prepare(
        "update_excluded_work",
        json.dumps({"add": [long_scope], "remove": []}),
        UUID(int=99),
    )
    assert isinstance(prepared, dict)
    write_output = await tools.execute(prepared)
    assert bounded_read_result["code"] == "read_limit_exceeded"
    assert len(write_output) > tools.max_result_characters

    reviewed_files = [
        fixture_path,
        Path(__file__),
        root / "apps/api/src/caliburn/transport/model_tools/occupation_references.py",
        root / "apps/api/src/caliburn/agents/job_consultant/reference_instructions.py",
        root / "apps/api/contracts/tools/select-occupation-references-arguments.schema.json",
        root / "apps/api/contracts/tools/tool-rejection.schema.json",
    ]
    result = {
        "scope": "offline_contract_audit_using_existing_in_memory_fixtures",
        "source_sha256": {
            path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in reviewed_files
        },
        "invalid_query": {
            "tool": "search_occupation_references",
            "arguments": invalid_query_arguments,
            "result": invalid_query_result,
            "external_calls": client.calls,
        },
        "selection_replacement": {
            "before": list(before.selected_reference_ids or ()),
            "requested": ["ref_frontend"],
            "after": list(after.selected_reference_ids or ()),
            "scope": "actual_domain_function_with_synthetic_reference_ids",
        },
        "write_result_capacity": {
            "configured_max_result_characters": tools.max_result_characters,
            "read_result": bounded_read_result,
            "write_result": json.loads(write_output),
            "write_result_characters": len(write_output),
            "scope": "actual_tool_handler_with_simulated_successful_workflow_no_database_write",
        },
        "limits": [
            "No production changes, database, HTTP, GPU or model calls.",
            "The small capacity reproduces a handler boundary; not a measured production incident.",
            "Successful existing tests establish wire behavior, not model usability or prompt quality.",
        ],
    }
    output = Path(__file__).with_name("tool-contract-audit-probes.json")
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"counterexamples_recorded": 3, "output": output.name}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
