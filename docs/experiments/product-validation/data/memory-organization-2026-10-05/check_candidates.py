"""Check candidate wire compatibility offline; never grade prose or call a provider."""

import json
import re
from copy import deepcopy
from hashlib import sha256
from pathlib import Path

from caliburn.adapters.openai_responses import ResponseRequest
from caliburn.agents.work_situation_analyst.instructions import SITUATION_INSTRUCTIONS
from caliburn.agents.work_understanding_analyst.instructions import UNDERSTANDING_INSTRUCTIONS
from caliburn.features.work_memory.revisions import MemoryLayer
from caliburn.transport.model_tools.memory_analysis import memory_analysis_tool_definitions
from caliburn.transport.model_tools.memory_reads import memory_read_names
from caliburn.workflows.memory_analysis.results import parse_outcome

HERE = Path(__file__).resolve().parent


def main() -> None:
    descriptions = json.loads((HERE / "tool-descriptions.json").read_text(encoding="utf-8"))
    assert set(descriptions) == set(memory_read_names())
    assert all(isinstance(value, str) and value.strip() for value in descriptions.values())
    roles = (
        (MemoryLayer.WORK_SITUATION, "b1-instructions.md", SITUATION_INSTRUCTIONS),
        (MemoryLayer.WORK_UNDERSTANDING, "b2-instructions.md", UNDERSTANDING_INSTRUCTIONS),
        (
            MemoryLayer.WORK_UNDERSTANDING,
            "b2-source-navigation-instructions.md",
            UNDERSTANDING_INSTRUCTIONS,
        ),
    )
    report = []
    for layer, filename, baseline in roles:
        candidate = (HERE / filename).read_text(encoding="utf-8").strip()
        examples = re.findall(r'\{"status"\s*:\s*"[^"]+"\}', candidate)
        assert len(examples) == 1
        assert parse_outcome(examples[0]).status == "complete"
        original_tools = memory_analysis_tool_definitions(layer)
        assert all(tool["strict"] for tool in original_tools)
        candidate_tools = deepcopy(original_tools)
        changed_names = []
        for original, changed in zip(original_tools, candidate_tools, strict=True):
            name = original["name"]
            if name in descriptions:
                changed["description"] = descriptions[name]
                changed_names.append(name)
            assert {key: value for key, value in original.items() if key != "description"} == {
                key: value for key, value in changed.items() if key != "description"
            }
        assert set(changed_names) == set(memory_read_names(layer))
        if layer == MemoryLayer.WORK_SITUATION:
            assert all("understanding" not in tool["name"] for tool in candidate_tools)
        else:
            assert all(
                tool["name"].startswith("read_") or tool["name"].endswith("work_understanding")
                for tool in candidate_tools
            )

        payloads = []
        for instructions, tools in (
            (baseline, original_tools),
            (candidate, original_tools),
            (candidate, candidate_tools),
        ):
            payload = ResponseRequest(
                model="gpt-6-luna",
                instructions=instructions,
                input_items=[],
                tools=tools,
                reasoning_effort="high",
                max_output_tokens=16_384,
            ).create_payload()
            assert ResponseRequest.from_snapshot(payload).create_payload() == payload
            payloads.append(payload)
        assert [key for key in payloads[0] if payloads[0][key] != payloads[1][key]] == [
            "instructions"
        ]
        assert [key for key in payloads[1] if payloads[1][key] != payloads[2][key]] == ["tools"]
        report.append(
            {
                "role": layer.value,
                "baseline_characters": len(baseline),
                "candidate_characters": len(candidate),
                "baseline_sha256": sha256(baseline.encode()).hexdigest(),
                "candidate_sha256": sha256(candidate.encode()).hexdigest(),
                "tool_count": len(original_tools),
                "description_variant_names": changed_names,
            }
        )
    print(json.dumps({"offline_contract_checks": "passed", "roles": report}, indent=2))


if __name__ == "__main__":
    main()
