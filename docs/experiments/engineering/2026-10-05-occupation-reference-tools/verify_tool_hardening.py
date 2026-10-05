"""Record corrected probes without overwriting the original pre-fix audit."""

import asyncio
import hashlib
import json
import runpy
from pathlib import Path
from uuid import UUID

from caliburn.transport.model_tools.occupation_references import (
    occupation_reference_definitions,
    occupation_reference_write_result_format,
)


async def main() -> None:
    root = Path(__file__).resolve().parents[4]
    fixture_path = root / "apps/api/tests/unit/test_occupation_reference_tools.py"
    fixture = runpy.run_path(str(fixture_path))["bound_tools"]
    tools, _, client = fixture()
    invalid_search = json.loads(
        await tools.invoke("search_occupation_references", json.dumps({"query": "   "}))
    )
    assert invalid_search["code"] == "invalid_arguments"
    assert "query" in invalid_search["next_action"]
    assert "add/remove" not in invalid_search["next_action"]
    assert client.calls == []
    selection = next(
        item
        for item in occupation_reference_definitions()
        if item["name"] == "select_occupation_references"
    )
    assert "取代" in selection["description"]
    parameter_description = selection["parameters"]["properties"]["reference_ids"][
        "description"
    ]
    assert "保留" in parameter_description
    modes = {}
    for mode in ("state", "status"):
        tools, workflow, client = fixture()
        tools.write_result_format = mode
        assert occupation_reference_write_result_format(tools.definitions()) == mode
        tools.max_result_characters = 64
        scope = "正式環境部署由維運負責。" * 16
        workflow.projected_state = {
            "selected_reference_ids": None,
            "excluded_work": [scope],
        }
        prepared = await tools.prepare(
            "update_excluded_work",
            json.dumps({"add": [scope], "remove": []}),
            UUID(int=99),
        )
        assert isinstance(prepared, dict)
        original = json.loads(json.dumps(prepared))
        output = await tools.execute(original)
        read = json.loads(await tools.invoke("read_occupation_reference_state", "{}"))
        assert original == prepared
        assert workflow.executions[0][1].state.excluded_work == (scope,)
        assert read["code"] == "read_limit_exceeded"
        assert client.calls == []
        assert json.loads(output) == (
            {"status": "updated"} if mode == "status" else workflow.projected_state
        )
        modes[mode] = {
            "write_result": json.loads(output),
            "write_result_characters": len(output),
            "read_result": read,
            "saved_command_unchanged": original == prepared,
            "saved_scope_characters": len(scope),
        }
    assert modes["status"]["write_result_characters"] == 20
    sources = [
        Path(__file__),
        fixture_path,
        root / "apps/api/src/caliburn/transport/model_tools/occupation_references.py",
        root / "apps/api/src/caliburn/agents/job_consultant/runner.py",
        root / "apps/api/src/caliburn/agents/job_consultant/reference_instructions.py",
        root / "apps/api/contracts/tools/occupation-reference-write-result.schema.json",
        root
        / "apps/api/contracts/tools/select-occupation-references-arguments.schema.json",
        root
        / "apps/api/contracts/tools/read-occupation-reference-arguments.schema.json",
    ]
    result = {
        "scope": "actual_handlers_with_synthetic_in_memory_workflow_no_database_or_http",
        "source_sha256": {
            path.relative_to(root).as_posix(): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in sources
        },
        "selection_description": selection["description"],
        "selection_parameter_description": parameter_description,
        "invalid_search": invalid_search,
        "configured_read_limit_characters": 64,
        "write_result_modes": modes,
        "limits": [
            "Character count only, not tokens, latency or JD quality.",
            "Legacy requests intentionally retain their original larger result.",
            "Synthetic low capacity, not a measured production incident.",
        ],
    }
    target = Path(__file__).with_name("hardening-probes.json")
    target.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "output": target.name,
                "result_characters": {
                    mode: data["write_result_characters"]
                    for mode, data in modes.items()
                },
            }
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
