"""Source Score(T11;ADR 0030;evals 深挖報告附錄 A):**程式算,不進裁判**。

Harvey 式雙指標的可溯源側:
- 分母 = AI 寫入條目(最終 doc 內 `_pending` ∪ 已 accept 的審閱事件)。
- 分子 = 出處通過 verify ②③ 同款判定者:
  ② quote 逐字(normalize 後 ∈ 指定 turn 原文);
  ③ ref_urn ∈ 參考集合;custom(無 ref)必附 quote;兩者可並存、至少一。
  偽 ref(給了但不在集合)= 直接不及格,不因 quote 而豁免(造假訊號)。
- 輸出 {score, total, passed, details:[{path, ok, reason}]}。

用法(promptfoo python assertion / pytest 皆可):
    from evals.source_score import source_score
    r = source_score(doc, turns={seq: 員工原文}, ref_codes={...}, accepted=[...])
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.interview.verify import normalize  # noqa: E402


def _seg(item: dict, idx: int) -> str:
    for k in ("_tid", "_uid", "_id"):
        if item.get(k):
            return str(item[k])
    return str(idx)


def iter_pending(doc: dict):
    """走全文件,產出 (path, mark)。行內標記+集合式(details/表頭/區塊級別)都收。"""
    def inline(node, path):
        m = (node or {}).get("_pending")
        if isinstance(m, dict) and m.get("op"):
            yield path, m

    def mapped(holder, base):
        for k, m in ((holder or {}).get("_pending") or {}).items():
            if isinstance(m, dict) and m.get("op"):
                yield f"{base}.{k}", m

    yield from mapped(doc.get("ocs_profile"), "ocs_profile")
    for ui, u in enumerate(((doc.get("ocs_content") or {}).get("ocu_units")) or []):
        upath = f"ocs_content.ocu_units.{_seg(u, ui)}"
        yield from inline(u, upath)
        for ti, t in enumerate(u.get("tasks") or []):
            tpath = f"{upath}.tasks.{_seg(t, ti)}"
            yield from inline(t, tpath)
            for ci, c in enumerate(t.get("task_codes") or []):
                yield from inline(c, f"{tpath}.task_codes.{_seg(c, ci)}")
            blocks = t.get("competency_blocks") or []
            if blocks:
                b = blocks[0]
                yield from mapped(b, f"{tpath}.competency_blocks.0")
                for kind in ("outputs", "indicators", "knowledge", "skills"):
                    for i, it in enumerate(b.get(kind) or []):
                        yield from inline(it, f"{tpath}.competency_blocks.0.{kind}.{_seg(it, i)}")
            yield from mapped(t.get("details"), f"{tpath}.details")
    for i, a in enumerate(((doc.get("ocs_attitude") or {}).get("attitudes")) or []):
        yield from inline(a, f"ocs_attitude.attitudes.{_seg(a, i)}")


def _src_verdict(mark: dict, turns: dict[int, str], ref_codes: set[str]) -> tuple[bool, str]:
    src = mark.get("src") or {}
    ref = src.get("ref_urn")
    q = src.get("quote") or {}
    qt, qturn = q.get("text"), q.get("turn_id")
    if ref and ref not in ref_codes:
        return False, f"ref 不在參考集合:{ref}"
    if qt:
        turn_text = turns.get(qturn) if qturn is not None else None
        if not turn_text or normalize(qt) not in normalize(turn_text):
            return False, f"quote 未驗證(turn {qturn})"
    if not ref and not qt:
        return False, "無出處(ref/quote 皆缺)"
    return True, "ok"


def source_score(doc: dict, *, turns: dict[int, str], ref_codes: set[str],
                 accepted: list[dict] | None = None) -> dict:
    """accepted=已 accept 審閱事件 [{doc_path, op_meta:{src…}?}](去標後 mark 只剩事件帳)。"""
    details: list[dict] = []
    for path, mark in iter_pending(doc):
        ok, reason = _src_verdict(mark, turns, ref_codes)
        details.append({"path": path, "ok": ok, "reason": reason})
    for ev in (accepted or []):
        meta = ev.get("op_meta") or {}
        mark = meta if meta.get("src") else {"src": meta.get("src")}
        if not (mark.get("src") or {}):
            details.append({"path": ev.get("doc_path", "?"), "ok": False,
                            "reason": "accepted 事件無出處紀錄"})
            continue
        ok, reason = _src_verdict(mark, turns, ref_codes)
        details.append({"path": ev.get("doc_path", "?"), "ok": ok, "reason": reason})
    total = len(details)
    passed = sum(1 for d in details if d["ok"])
    return {"score": (passed / total) if total else 1.0,
            "total": total, "passed": passed, "details": details}
