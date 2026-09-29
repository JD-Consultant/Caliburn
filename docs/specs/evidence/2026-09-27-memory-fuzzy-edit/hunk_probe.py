"""Synthetic hunk-semantics probe, NOT a patch parser or production tool.

Fixture tuples represent already-parsed context/delete/add lines. Numeric
unified headers, file envelopes, V4A parsing and multi-hunk execution are NOT
implemented. Reuse the bounded locator to test the user's contextual-edit
requirement, preserving actual context lines even when fuzzy matching them.
"""

from importlib.metadata import version
import json
from time import perf_counter

from probe import FACT, NEW, PREFIX, SUFFIX, Outcome, replace_probe


def hunk_probe(text, hunk):
    before = "\n".join(line for tag, line in hunk if tag != "+")
    located = replace_probe(text, before, before)
    if located.status != "applied":
        return located
    hit = located.matches[0]
    actual = text[hit.start:hit.end].splitlines(keepends=True)
    newline = "\r\n" if "\r\n" in text[hit.start:hit.end] else "\n"
    pieces, index = [], 0
    for tag, line in hunk:
        if tag == " ":
            pieces.append(actual[index])  # Never copy approximate context back.
            index += 1
        elif tag == "-":
            index += 1
        elif tag == "+":
            pieces.append(line + newline)
        else:
            raise AssertionError("Invalid fixture tag")
    assert index == len(actual)
    replacement = "".join(pieces)
    # Fixture scope: the located span excludes its final line ending.
    if replacement.endswith(newline):
        replacement = replacement[:-len(newline)]
    return Outcome("applied", text[:hit.start] + replacement + text[hit.end:],
                   located.method, located.matches)


def main():
    assert version("rapidfuzz") == "3.14.6"
    rows = []

    def check(name, text, hunk, status, expected=None):
        started = perf_counter()
        result = hunk_probe(text, hunk)
        elapsed = round((perf_counter() - started) * 1000, 3)
        assert result.status == status, (name, result.status, status)
        assert result.text == (expected if status == "applied" else text), name
        rows.append({"name": name, "status": result.status,
                     "method": result.method, "matches": len(result.matches),
                     "characters": len(text), "elapsed_ms": elapsed})

    target = "function calculateTotal(items) {\n  let tax = 0.05;\n  return items.reduce(...);\n}"
    other = target.replace("calculateTotal", "calculateDifferentRegionalTotal")
    hunk = [(" ", "function calculateTotal(items) {"),
            ("-", "  let tax = 0.05;"), ("+", "  let tax = 0.08;"),
            (" ", "  return items.reduce(...);"), (" ", "}")]
    revised = target.replace("0.05", "0.08")
    text = other + "\n\n" + target
    check("context_selects_second_function", text, hunk, "applied", other + "\n\n" + revised)
    # Earlier lines move the target; declared line numbers aren't authority.
    check("context_survives_prefix_shift", PREFIX + text, hunk, "applied",
          PREFIX + other + "\n\n" + revised)
    # Fuzzy context is for location, not implicit rewriting of context lines.
    formatted = target.replace("function calculate", "function  calculate").replace("\n", "\r\n")
    check("fuzzy_context_is_not_rewritten", PREFIX + formatted + SUFFIX, hunk,
          "applied", PREFIX + formatted.replace("0.05", "0.08") + SUFFIX)
    check("duplicate_complete_hunk_rejected", target + "\n\n" + target, hunk, "ambiguous")
    typo_hunk = [(tag, line.replace("calculateTotal", "calculateTota1")) for tag, line in hunk]
    near = target.replace("calculateTotal", "calculateTotals")
    check("two_near_complete_hunks_rejected", target + "\n\n" + near, typo_hunk, "ambiguous")
    check("wrong_context_not_ignored", target,
          [(" ", "function unrelatedPayrollApprovalAndAudit(employees) {"), *hunk[1:]], "no_match")
    case_hunk = [(" ", "## 訂單異常處理"), ("-", FACT), ("+", NEW),
                 (" ", "未確認：跨部門升級条件。")]
    actual_case = "## 訂單異常處理\n" + FACT + "\n未確認：跨部門升級條件。"
    filler = "".join(f"- 保留項 {i:04d}：辦公室設備、耗材與庶務記錄。\n" for i in range(4500))
    check("long_chinese_hunk_preserves_actual_context", PREFIX + filler + actual_case + SUFFIX,
          case_hunk, "applied", PREFIX + filler + actual_case.replace(FACT, NEW) + SUFFIX)
    print(json.dumps({"scope": "DISPOSABLE CONTEXTUAL-HUNK PROBE; NO PARSER OR PRODUCT ACCEPTANCE",
                      "rapidfuzz": version("rapidfuzz"), "checks": len(rows), "rows": rows},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
