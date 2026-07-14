"""promptfoo 確定性斷言(T11;先行;llm-rubric 留 Phase 2)。

輸入 output = provider_turn 的 JSON 字串 {say, turn, doc, turns}。
promptfoo 用法:`assert: [{type: python, value: "file://assertions/deterministic.py:每回合有問題"}]`
——promptfoo python assertion 回 bool / float / {pass, score, reason}。
"""
from __future__ import annotations

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from source_score import iter_pending, source_score  # noqa: E402

_POSITION_CODE = re.compile(r"^(T\d+(\.\d+)?|[OPA]\d|[OP]\d+\.\d+)")


def _parse(output: str) -> dict:
    return json.loads(output) if isinstance(output, str) else (output or {})


def consultant_asks_forward(output, context) -> dict:
    """C″ 規則:每回合以恰好一個往前的問題收尾(問號數=1;無問=訪談死掉)。"""
    say = _parse(output).get("say", "")
    n = say.count("?") + say.count("?")
    return {"pass": n == 1, "score": 1.0 if n == 1 else 0.0,
            "reason": f"問號數={n}(規則=恰好 1)"}


def no_position_codes_written(output, context) -> dict:
    """結構不變量⑤:位置碼是 renumber 職權,AI 寫入條目不得自帶位置碼樣式的 code
    (官方池 ref 導出碼除外——那是 URN/官方碼,非 T1.1/O1.1.1 位置樣式)。"""
    doc = _parse(output).get("doc") or {}
    bad = []
    for path, mark in iter_pending(doc):
        if mark.get("op") != "add":
            continue
        node_code = (mark.get("value") or {}).get("code") if isinstance(mark.get("value"), dict) else None
        if node_code and _POSITION_CODE.match(str(node_code)):
            bad.append(path)
    return {"pass": not bad, "score": 0.0 if bad else 1.0,
            "reason": ("AI 寫入自帶位置碼:" + ";".join(bad[:5])) if bad else "ok"}


def source_score_min80(output, context) -> dict:
    """Source Score ≥ 0.8(分母=doc `_pending`;turns 由 provider 附帶)。
    ref_codes 由 test vars `ref_codes`(list)給;缺省=空集合(等同 quote-only 判定)。"""
    data = _parse(output)
    turns = {int(k): v for k, v in (data.get("turns") or {}).items()}
    refs = set(((context or {}).get("vars") or {}).get("ref_codes") or [])
    r = source_score(data.get("doc") or {}, turns=turns, ref_codes=refs)
    return {"pass": r["score"] >= 0.8, "score": r["score"],
            "reason": f"source_score={r['score']:.2f}({r['passed']}/{r['total']})"}


def doc_structure_intact(output, context) -> dict:
    """結構不變量:任務必掛職責、態度只在文件層(不掛任務)。"""
    doc = _parse(output).get("doc") or {}
    problems = []
    for u in ((doc.get("ocs_content") or {}).get("ocu_units")) or []:
        for t in (u.get("tasks") or []):
            if not isinstance(t, dict):
                problems.append("task 非物件")
            for b in (t.get("competency_blocks") or []):
                if "attitudes" in (b or {}):
                    problems.append("態度掛在任務層")
    return {"pass": not problems, "score": 0.0 if problems else 1.0,
            "reason": ";".join(problems) or "ok"}
