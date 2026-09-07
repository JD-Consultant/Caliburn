"""CT10 offline characterization, NOT a production patch adapter or model test.

Run from experiments/analysis-agent with an ephemeral openai-agents==0.22.0.
No environment files, clients, databases, or model calls. JSON goes to stdout.
Real CT09 old/new requests are mechanically represented as V4A line hunks;
this is not evidence that Luna will generate those hunks.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
from importlib.metadata import version
import json
from pathlib import Path

from agents import apply_diff
from deepagents.backends.utils import perform_string_replacement


def line_patch(old: str, new: str, anchor: str = "") -> str:
    """Fixture conversion only; preserves the erroneous spaces in old lines."""
    return "\n".join([
        "@@" + (" " + anchor if anchor else ""),
        *("-" + line for line in old.splitlines()),
        *("+" + line for line in new.splitlines()),
    ])


def exact(text: str, old: str, new: str) -> dict:
    outcome = perform_string_replacement(text, old, new, False)
    if isinstance(outcome, str):
        return {"error": outcome, "result": text, "changed": False}
    return {"error": None, "result": outcome[0], "changed": outcome[0] != text}


def patch(text: str, diff: str) -> dict:
    # The public SDK function is pure. No backend write happens here.
    try:
        result = apply_diff(text, diff)
    except ValueError as error:
        return {"error": str(error), "result": text, "changed": False}
    return {"error": None, "result": result, "changed": result != text}


def real_failures(evidence: dict) -> list[dict]:
    turns = [p for p in evidence["live"]["phases"] if p["mode"] == "turn"]
    current = turns[6]["before"]["knowledge"]
    rows = []
    for recorded in evidence["exact_edit_audit"]:
        args = recorded["arguments"]
        old, new = args["old_string"], args["new_string"]
        original = exact(current, old, new)
        if not original["error"]:
            # Follow the real successful edits only, so each failed attempt is
            # tested against its own actual pre-edit state, not a new timeline.
            current = original["result"]
            continue
        assert recorded["request"] in (40, 42, 45)
        assert "String not found" in original["error"]
        # These THREE known fixture mistakes added exactly two spaces per
        # nonempty line. This is a hand-audited expected span, not a repair rule.
        intended = "\n".join(line[2:] if line else "" for line in old.split("\n"))
        assert current.count(intended) == 1
        at = current.index(intended)
        expected = current[:at] + new + current[at + len(intended):]
        diff = line_patch(old, new)
        result = patch(current, diff)
        assert result["error"] is None, result["error"]
        assert result["result"] == expected, f"unexpected outside-span change in #{recorded['request']}"
        rows.append({
            "request": recorded["request"], "old": old, "new": new,
            "source_before_sha256": hashlib.sha256(current.encode()).hexdigest(),
            "exact_error": original["error"], "v4a_fixture": diff,
            "patch_matches_hand_audited_span": True,
            "unaffected_content_and_references_byte_preserved": True,
            "patch_changed_content": result["changed"],
        })
    assert len(rows) == 3
    return rows


def safety_cases() -> list[dict]:
    # Independent literals make the intended destination explicit. The first
    # two unsafe outcomes are characterized, not silently marked as passes.
    cases = [
        ("unique_whitespace", "# B\n  - 每月彙整\n來源 B\n",
         "    - 每月彙整", "  - 每週彙整", "",
         "# B\n  - 每週彙整\n來源 B\n"),
        ("repeated_exact_no_context", "# A\n- 每月彙整\n# B\n- 每月彙整\n",
         "- 每月彙整", "- 每週彙整", "",
         "# A\n- 每月彙整\n# B\n- 每週彙整\n"),
        ("repeated_with_extra_indent_no_context", "# A\n- 每月彙整\n# B\n  - 每月彙整\n",
         "    - 每月彙整", "  - 每週彙整", "",
         "# A\n- 每月彙整\n# B\n  - 每週彙整\n"),
        ("same_repeated_content_with_B_anchor", "# A\n- 每月彙整\n# B\n  - 每月彙整\n",
         "    - 每月彙整", "  - 每週彙整", "# B",
         "# A\n- 每月彙整\n# B\n  - 每週彙整\n"),
        ("wrong_single_anchor", "# A\n- 每月彙整\n# B\n  - 每月彙整\n",
         "    - 每月彙整", "  - 每週彙整", "# 不存在",
         None),
        ("content_mismatch", "# B\n- 每月彙整\n", "- 每年彙整", "- 每週彙整", "# B", None),
        ("chinese_crlf", "# B\r\n- 每月彙整\r\n來源 B\r\n",
         "  - 每月彙整", "- 每週彙整", "# B",
         "# B\r\n- 每週彙整\r\n來源 B\r\n"),
        ("no_eof_newline", "# B\n- 每月彙整", "  - 每月彙整", "- 每週彙整", "# B",
         "# B\n- 每週彙整"),
    ]
    rows = []
    for name, source, old, new, anchor, expected in cases:
        diff = line_patch(old, new, anchor)
        out = patch(source, diff)
        good = (out["error"] is not None) if expected is None else out["result"] == expected
        rows.append({"case": name, "source": source, "expected": expected,
                     "patch": diff, "patch_outcome": out,
                     "exact_outcome": exact(source, old, new),
                     "meets_intended_location_or_rejection": good})
    # Real contextual lines, not just a missing advisory single anchor.
    source = "# A\n- 每月彙整\n# B\n  - 每月彙整\n"
    diff = "@@\n # 不存在\n-    - 每月彙整\n+  - 每週彙整"
    out = patch(source, diff)
    assert out["error"] and out["result"] == source
    rows.append({"case": "wrong_actual_context", "source": source, "patch": diff,
                 "patch_outcome": out, "meets_intended_location_or_rejection": True})
    # First hunk valid, second invalid: pure function returns no partial result.
    diff = "@@\n # A\n-- 每月彙整\n+- 每週彙整\n@@\n-不存在的內容\n+不能寫入"
    out = patch(source, diff)
    assert out["error"] and out["result"] == source
    rows.append({"case": "second_hunk_failure_no_partial_result", "source": source,
                 "patch": diff, "patch_outcome": out,
                 "meets_intended_location_or_rejection": True})
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="New evidence file; refuses overwrite")
    options = parser.parse_args()
    path = Path("../../docs/specs/evidence/2026-09-07-long-interview-acceptance.json")
    raw = path.read_bytes()
    evidence = json.loads(raw)
    assert version("openai-agents") == "0.22.0"
    assert version("deepagents") == "0.7.13"
    real = real_failures(evidence)
    safety = safety_cases()
    failed = [r["case"] for r in safety if not r["meets_intended_location_or_rejection"]]
    module = importlib.import_module("agents.apply_diff")
    result = {
        "topic": "LLM-Q019/CT10", "type": "offline characterization; no model calls",
        "evidence_sha256": hashlib.sha256(raw).hexdigest(),
        "versions": {p: version(p) for p in ("openai-agents", "deepagents", "openai")},
        "sdk_apply_diff_sha256": hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),
        "ct09_failures": real, "safety_cases": safety,
        "candidate_safety_gate": not failed, "safety_findings": failed,
        "production_changed": False, "model_requests": 0, "model_cost_usd": 0,
    }
    result["comparison_script_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    encoded = json.dumps(result, ensure_ascii=False, indent=2)
    if options.output:
        with options.output.open("x", encoding="utf-8", newline="\n") as output:
            output.write(encoded + "\n")
        print(json.dumps({"ct09_reproduced": len(real), "safety_cases": len(safety),
                          "candidate_safety_gate": not failed, "safety_findings": failed,
                          "model_requests": 0, "evidence": str(options.output)}, ensure_ascii=False))
    else:
        print(encoded)


if __name__ == "__main__":
    main()
