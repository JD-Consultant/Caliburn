"""CT10 follow-up: throwaway offline characterization, never a product adapter.

Probe the previously surprising SDK boundary with hand-authored context hunks.
No model, network, env file, backend or publication. Context is deliberately
chosen by the researcher; this cannot measure Luna's ability to choose it.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
from importlib.metadata import version
import json
from pathlib import Path

from agents import apply_diff


def cases() -> list[dict]:
    repeated = "# A\n- 每月彙整\n來源 A\n# B\n  - 每月彙整\n來源 B\n"
    updated_b = "# A\n- 每月彙整\n來源 A\n# B\n  - 每週彙整\n來源 B\n"
    # Literal expectations catch changing the wrong repeated section, accepting
    # missing real context, rewriting context indentation or punctuation, and
    # falsely assuming a single advisory anchor is mandatory in this SDK.
    fixtures = [
        ("repeated_with_actual_context", repeated,
         "@@\n # B\n-  - 每月彙整\n+  - 每週彙整\n 來源 B", updated_b, None),
        ("extra_indent_with_actual_context", repeated,
         "@@\n # B\n-    - 每月彙整\n+  - 每週彙整\n 來源 B", updated_b, None),
        ("missing_actual_context_rejected", repeated,
         "@@\n # 不存在\n-    - 每月彙整\n+  - 每週彙整\n 來源 B", None, "Invalid Context"),
        ("stacked_anchors_select_B", "# A\n## 頻率\n- 每月\n# B\n## 頻率\n- 每月\n",
         "@@ # B\n@@ ## 頻率\n-- 每月\n+- 每週",
         "# A\n## 頻率\n- 每月\n# B\n## 頻率\n- 每週\n", None),
        ("missing_stacked_anchor_rejected", repeated,
         "@@ # 不存在\n@@ # B\n-    - 每月彙整\n+  - 每週彙整", None, "Invalid Anchor"),
        ("context_spaces_are_not_rewritten", "# B\n\t來源 B\n  - 每月彙整\n    不變細節\n",
         "@@\n # B\n   來源 B\n-    - 每月彙整\n+  - 每週彙整\n  不變細節",
         "# B\n\t來源 B\n  - 每週彙整\n    不變細節\n", None),
        ("meaningful_text_mismatch_rejected", repeated,
         "@@\n # B\n-  - 每年彙整\n+  - 每週彙整\n 來源 B", None, "Invalid Context"),
        ("sdk_does_not_normalize_smart_quotes", "# B\n- 使用\u201c正式\u201d版本\n",
         '@@\n # B\n-- 使用"正式"版本\n+- 使用新版', None, "Invalid Context"),
        # Retain a counterexample, even after adding positive context cases:
        # a valid but semantically wrong A context is NOT automatically detected.
        ("valid_wrong_section_still_applies_A", repeated,
         "@@\n # A\n-- 每月彙整\n+- 每週彙整\n 來源 A",
         "# A\n- 每週彙整\n來源 A\n# B\n  - 每月彙整\n來源 B\n", None),
        ("missing_single_anchor_is_not_a_guard", repeated,
         "@@ # 不存在\n-    - 每月彙整\n+  - 每週彙整",
         "# A\n  - 每週彙整\n來源 A\n# B\n  - 每月彙整\n來源 B\n", None),
    ]
    results = []
    for name, source, diff, expected, expected_error in fixtures:
        outcome = source
        error = None
        try:
            outcome = apply_diff(source, diff)
        except ValueError as failure:
            error = str(failure)
        if expected_error:
            assert error and expected_error in error, (name, error)
            assert outcome == source
        else:
            assert error is None and outcome == expected, (name, error, outcome)
        results.append({"case": name, "source": source, "patch": diff,
                        "expected": expected, "expected_error": expected_error,
                        "result": outcome, "error": error})
    return results


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", type=Path, help="New evidence file; exclusive create")
    cli.add_argument("--verify", type=Path, help="Compare with existing evidence; no write")
    args = cli.parse_args()
    if args.output and args.verify:
        cli.error("Choose --output or --verify")
    assert version("openai-agents") == "0.22.0"
    module = importlib.import_module("agents.apply_diff")
    result = {"topic": "LLM-Q019/CT10/context-follow-up",
              "type": "offline SDK characterization, not a model or Codex executable test",
              "versions": {p: version(p) for p in ("openai-agents", "openai")},
              "sdk_sha256": hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),
              "probe_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              "cases": cases(), "model_requests": 0, "model_cost_usd": 0,
              "production_changed": False}
    if args.verify:
        assert json.loads(args.verify.read_text(encoding="utf-8")) == result
    elif args.output:
        with args.output.open("x", encoding="utf-8", newline="\n") as output:
            output.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    print(json.dumps({"observations_verified": len(result["cases"]),
                      "counterexamples_retained": 2, "model_requests": 0,
                      "evidence": str(args.output or args.verify)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
