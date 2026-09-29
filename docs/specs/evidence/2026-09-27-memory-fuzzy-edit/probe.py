"""Disposable, synthetic-only feasibility probe; NOT a production editor.

No App imports, tools, persistence, provider, filesystem writes or network.
RapidFuzz supplies distance calculation, not span discovery or uniqueness.
The deliberately bounded candidate policy tests whole-line fuzzy windows;
counterexamples below expose its limits rather than silently widening it.
Keep this as research evidence, not as a module for the App to import.
"""

from dataclasses import dataclass
from importlib.metadata import version
import json
import platform
from time import perf_counter

from rapidfuzz.distance import Levenshtein


@dataclass(frozen=True)
class Span:
    start: int
    end: int
    score: float


@dataclass(frozen=True)
class Outcome:
    status: str
    text: str
    method: str
    matches: tuple[Span, ...]


def normalize_block(text):
    # Matching view only: never normalize/rewrite the rest of the document.
    return "\n".join(line.strip() for line in text.splitlines())


def replace_probe(text, old, new, *, threshold=0.90):
    """One edit, exact first; otherwise same-line-count fuzzy candidates.

    Threshold and limits are EXPERIMENT settings, not accepted tool policy.
    Every qualifying window is retained, including overlaps and unequal scores.
    No best-match selection, overlap suppression or automatic model correction.
    """
    if not old.strip():
        return Outcome("invalid", text, "none", ())
    hits, offset = [], 0
    while (start := text.find(old, offset)) != -1:
        hits.append(Span(start, start + len(old), 1.0))
        offset = start + 1  # Also count overlapping exact matches.
    method = "exact"
    if not hits:
        method = "fuzzy_lines"
        lines = text.splitlines(keepends=True)
        target = normalize_block(old)
        count = len(old.splitlines())
        if len(target) < 10:
            return Outcome("unsupported_short_fuzzy", text, method, ())
        # Bound this experiment; no scan truncation masquerading as uniqueness.
        if len(lines) * len(target) ** 2 > 400_000_000:
            return Outcome("scan_limit", text, method, ())
        offsets = [0]
        for line in lines:
            offsets.append(offsets[-1] + len(line))
        for index in range(len(lines) - count + 1):
            start = offsets[index]
            end = offsets[index + count]
            end -= len(lines[index + count - 1]) - len(
                lines[index + count - 1].rstrip("\r\n")
            )
            candidate = normalize_block(text[start:end])
            score = Levenshtein.normalized_similarity(
                target, candidate, score_cutoff=threshold
            )
            if score >= threshold:
                hits.append(Span(start, end, score))
    if len(hits) != 1:
        return Outcome("ambiguous" if hits else "no_match", text, method, tuple(hits))
    hit = hits[0]
    return Outcome(
        "applied", text[:hit.start] + new + text[hit.end:], method, tuple(hits)
    )


FACT = "本人每月彙整網站訂單異常，先核對重複送單與付款紀錄，再交由後端同事修正，並追蹤處理結果。"
QUERY = FACT.replace("付款紀錄", "付欵紀錄")
NEW = FACT.replace("每月", "每週")
PREFIX = "# 工作情境\r\n保留的中文、tab\t、emoji 🧾 與來源 [I17]。\r\n"
SUFFIX = "\r\n\r\n# 不相關段落\r\n  這裡的格式與引用 [I18] 必須逐字保留。\r\n"
ROWS = []


def check(name, body, old, new, expected_status, expected_text=None,
          *, kind="guard_check", **kwargs):
    started = perf_counter()
    result = replace_probe(body, old, new, **kwargs)
    elapsed_ms = round((perf_counter() - started) * 1000, 3)
    assert result.status == expected_status, (name, result.status, expected_status)
    if expected_status == "applied":
        assert result.text == expected_text, name
        hit = result.matches[0]
        assert result.text[:hit.start] == body[:hit.start], name
        assert result.text[hit.start + len(new):] == body[hit.end:], name
    else:
        assert result.text == body, name
    ROWS.append({
        "name": name, "kind": kind, "status": result.status,
        "method": result.method, "characters": len(body),
        "matches": len(result.matches),
        "scores": [round(hit.score, 6) for hit in result.matches],
        "ranges": [[hit.start, hit.end] for hit in result.matches[:4]],
        "elapsed_ms": elapsed_ms,
    })
    return result


def main():
    assert version("rapidfuzz") == "3.14.6", "Use the pinned research dependency"
    # >100K characters: long DOCUMENT, local edit; not a 100K-token claim.
    filler = "".join(f"- 附錄 {i:04d}：設備清潔與耗材補充，與訂單處理無關。\n" for i in range(4500))
    long_body = PREFIX + filler + FACT + SUFFIX
    expected = PREFIX + filler + NEW + SUFFIX
    check("long_exact", long_body, FACT, NEW, "applied", expected)
    check("long_fuzzy_typo", long_body, QUERY, NEW, "applied", expected)
    check("multiline_format", PREFIX + "  第一段：核對訂單來源。\r\n\t第二段：追蹤處理結果。" + SUFFIX,
          "第一段：核對訂單來源。\n第二段：追蹤處理結果。",
          "  第一段：核對訂單來源與時間。\r\n\t第二段：追蹤處理結果。", "applied",
          PREFIX + "  第一段：核對訂單來源與時間。\r\n\t第二段：追蹤處理結果。" + SUFFIX)
    check("duplicate_exact", FACT + "\n\n" + FACT, FACT, NEW, "ambiguous")
    check("overlap_exact", "aaaaa", "aaa", "b", "ambiguous")
    other = FACT.replace("本人", "本組").replace("先核對", "先檢核")
    result = check("two_unequal_fuzzy_scores", FACT + "\n" + other, QUERY, NEW, "ambiguous")
    assert len(set(hit.score for hit in result.matches)) == 2
    # Two different target windows overlap; do not collapse to one best match.
    line = "每月核對訂單異常、付款紀錄，並追蹤後端同事處理結果。"
    overlap_query = line.replace("付款", "付欵") + "\n" + line
    check("overlap_fuzzy", "\n".join([line] * 3), overlap_query, NEW, "ambiguous")
    duplicate = "# 訂單\n" + FACT + "\n# 庫存\n" + FACT
    check("context_disambiguates", duplicate, "# 庫存\n" + FACT, "# 庫存\n" + NEW,
          "applied", "# 訂單\n" + FACT + "\n# 庫存\n" + NEW)
    check("not_found", PREFIX + FACT + SUFFIX, "本人僅負責接待國際客戶及口譯服務。", NEW, "no_match")
    check("delete_block", PREFIX + FACT + SUFFIX, FACT, "", "applied", PREFIX + SUFFIX)
    check("insert_with_anchor", PREFIX + FACT + SUFFIX, FACT, FACT + "\n例外時先回報主管。",
          "applied", PREFIX + FACT + "\n例外時先回報主管。" + SUFFIX)
    check("blank_old_rejected", FACT, " \n", NEW, "invalid")
    check("short_fuzzy_rejected", "每月處理", "每週處理", "其他", "unsupported_short_fuzzy")
    check("cost_limit_is_not_no_match", "\n".join(["保留" * 100] * 200),
          "核對" * 1000, NEW, "scan_limit")
    # Deliberately record limitations. These are not feature PASS claims.
    check("wrapped_paragraph_not_supported", FACT.replace("，", "，\n", 1), QUERY, NEW,
          "no_match", kind="scope_limit")
    check("inline_fuzzy_not_supported", FACT, "先核對重複送單與付欵紀錄", "新內容",
          "no_match", kind="scope_limit")
    # A single score-qualified candidate can still contradict an important fact.
    unsafe_query = FACT.replace("後端同事", "本人")
    unsafe_new = unsafe_query.replace("每月", "每週")
    check("unique_does_not_mean_faithful", FACT, unsafe_query, unsafe_new,
          "applied", unsafe_new, kind="semantic_counterexample")
    # Exposes the exact-first policy, not an adopted cross-tier uniqueness rule.
    check("exact_precedes_nearby_variant", FACT + "\n" + other, FACT, NEW,
          "applied", NEW + "\n" + other, kind="policy_observation")
    # Observe score sensitivity; no threshold is selected for production here.
    for cutoff in [0.90, 0.95, 0.98, 0.99]:
        result = replace_probe(FACT, QUERY, NEW, threshold=cutoff)
        ROWS.append({"kind": "threshold_observation", "cutoff": cutoff,
                     "status": result.status, "matches": len(result.matches)})
    print(json.dumps({
        "scope": "DISPOSABLE SYNTHETIC PROBE; NOT PRODUCTION ACCEPTANCE",
        "python": platform.python_version(), "rapidfuzz": version("rapidfuzz"),
        "scorer": Levenshtein.normalized_similarity.__module__,
        "checks": 18, "guard_checks": 14,
        "scope_limits": 2, "semantic_counterexamples": 1, "policy_observations": 1,
        "rows": ROWS,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
