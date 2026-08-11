"""相似比對核心 — 純函式(零 I/O)。ADR 0022;spec docs/specs/2026-07-04-similarity-matching-v1-spec.md。

分帶 = Fellegi-Sunter 三區;分群 = 貪婪星型(成員與中心直連 ≥θ_high,SKOS closeMatch
非遞移紅線——絕不做連通分量)。改門檻 = 改 THRESHOLDS + 跑校準腳本留紀錄(docs/specs/)。
"""
from __future__ import annotations

import re
import unicodedata
from typing import Callable, Optional

# per-kind {θ_high, θ_low}(spec §2;實驗出處 = dedup 研究 §9.4;絕對值只對本池×bge-m3 有效)
THRESHOLDS: dict[str, tuple[float, float]] = {
    "task": (0.95, 0.80),
    "unit": (0.95, 0.80),      # 未經實驗,暫比照 task;校準乾淨才接 UI(spec §2)
    "knowledge": (0.85, 0.65),
    "skill": (0.85, 0.65),
    "output": (0.85, 0.65),
    "indicator": (0.85, 0.65),
    "attitude": (0.90, 0.70),
}

_MARK = re.compile(r"【[^】]*】")
_CJK = "㐀-䶿一-鿿豈-﫿"
_CJK_GAP = re.compile(f"(?<=[{_CJK}])\\s+(?=[{_CJK}])")
_WS = re.compile(r"\s+")

ScoreOf = Callable[[str, str], Optional[float]]  # 未比對(同來源)回 None


def preprocess(text: str) -> str:
    """剝【…】、刪 CJK 字間空白(PDF 斷行殘留)、其餘空白摺疊為單一空格、trim。
    只產比對文字——顯示文字永不改。"""
    t = _MARK.sub("", text)
    t = _CJK_GAP.sub("", t)
    return _WS.sub(" ", t).strip()


def collapse_key(text: str) -> str:
    """exact-collapse key:NFKC(全形/半形同一化)。僅內部比對用,不落地。"""
    return unicodedata.normalize("NFKC", text)


def band(scored_pairs, theta_high, theta_low):
    """FS 三區:(≥θ_high, [θ_low,θ_high)) 兩桶;<θ_low 丟棄(token 效率)。"""
    dup = [(s, i, j) for s, i, j in scored_pairs if s >= theta_high]
    gray = [(s, i, j) for s, i, j in scored_pairs if theta_low <= s < theta_high]
    return dup, gray


def star_clusters(dup_pairs, score_of: ScoreOf, theta_high: float):
    """貪婪星型(決定論):對照 (-score, left, right) 排序處理。
    兩邊皆散 → 開群(center = id 較小者);一邊在群 → 僅當與該群中心**直連** ≥θ_high
    才入群(以直連分記);兩邊已各在群 → 不合併。回 [(center, {member: score})],
    照 center id 升序。"""
    ordered = sorted(dup_pairs, key=lambda p: (-p[0], p[1], p[2]))
    center_of: dict[str, str] = {}
    members: dict[str, dict[str, float]] = {}
    for s, x, y in ordered:
        cx, cy = center_of.get(x), center_of.get(y)
        if cx is None and cy is None:
            center, leaf = (x, y) if x < y else (y, x)
            center_of[center] = center
            center_of[leaf] = center
            members[center] = {leaf: s}
        elif cx is not None and cy is None:
            link = score_of(cx, y)
            if link is not None and link >= theta_high:
                center_of[y] = cx
                members[cx][y] = link
        elif cy is not None and cx is None:
            link = score_of(cy, x)
            if link is not None and link >= theta_high:
                center_of[x] = cy
                members[cy][x] = link
        # else: 兩邊已各在群 → 不合併(星型紅線)
    return sorted(members.items(), key=lambda kv: kv[0])


def medoid_of(ids: list[str], score_of: ScoreOf) -> str:
    """幾何代表:與群內其他成員平均相似度最高;缺分(同來源未比)以 0 計;平手 → id 升序。"""
    def avg(i: str) -> float:
        vals = [(score_of(i, j) or 0.0) for j in ids if j != i]
        return sum(vals) / len(vals) if vals else 0.0
    return max(sorted(ids), key=avg)
