"""相似比對門檻校準腳本(ADR 0022;spec §6)。

對「真實會共選」的職類組合,用生產同一套 matching.core 跑完整管線,輸出 per-kind:
池量 / exact 收斂 / 跨來源對數 / 分帶結果(自動群、灰區對數)/ 0.1 級距直方 / 高分帶前 10 對。
輸出貼進 docs/specs/ 當校準紀錄;改門檻 = 改 core.THRESHOLDS + 重跑本腳本留紀錄。

用法(需 embedder 容器,npm run infra):
  cd apps/ocs-indexer && PYTHONUTF8=1 uv run python scripts/calibrate_match.py
"""
from __future__ import annotations

import glob
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from jd_ocs_indexer.api.schemas import MatchItem  # noqa: E402
from jd_ocs_indexer.embeddings.http_embedder import HttpEmbedder  # noqa: E402
from jd_ocs_indexer.matching import core  # noqa: E402
from jd_ocs_indexer.matching import service as matching  # noqa: E402

DATA = os.path.join(os.path.dirname(__file__), "..", "data", "jd-json")
EMBEDDER_URL = os.getenv("EMBEDDER_URL", "http://localhost:8082")

# 真實會共選的組合(研究 §5/§5.1/§9.4 同款)
COMBOS: dict[str, list[str]] = {
    "軟體三職類": ["SET3115-001v5", "ISD2152-001v4", "ISD2519-002v2"],
    "品管三職類": ["MQM2141-001v4", "MQM2141-008v1", "MQM2141-005v2"],
    "同職雙版本(品管 v2×v4)": ["MQM2141-001v2", "MQM2141-001v4"],
}


def load_doc(code: str) -> dict:
    for f in glob.glob(os.path.join(DATA, "*.json")):
        d = json.load(open(f, encoding="utf-8"))
        if d.get("ocs_profile", {}).get("ocs_code") == code:
            return d
    raise SystemExit(f"not found in data/jd-json: {code}")


def extract(doc: dict, code: str) -> dict[str, list[tuple[str, str, str]]]:
    """回 {kind: [(id, text, source)]};kind 對齊 core.THRESHOLDS(unit 一起跑)。"""
    out: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for u in doc.get("ocs_content", {}).get("ocu_units", []):
        if u.get("ocu_name"):
            out["unit"].append((f"{code}:{u.get('ocu_code')}", u["ocu_name"], code))
        for t in u.get("tasks", []):
            for tc in t.get("task_codes", []):
                if tc.get("name"):
                    out["task"].append((f"{code}:{tc.get('code')}", tc["name"], code))
            for b in t.get("competency_blocks", []):
                for kind, field in (("knowledge", "knowledge"), ("skill", "skills")):
                    for it in b.get(field, []):
                        if it.get("name"):
                            out[kind].append((f"{code}:{it.get('code')}", it["name"], code))
    for a in doc.get("ocs_attitude", {}).get("attitudes", []):
        if a.get("name"):
            out["attitude"].append((f"{code}:{a.get('code')}", a["name"], code))
    return out


def run_combo(embedder: HttpEmbedder, name: str, codes: list[str]) -> dict:
    pools: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for c in codes:
        for kind, items in extract(load_doc(c), c).items():
            pools[kind].extend(items)
    print(f"\n{'=' * 72}\n組合:{name}{codes}")
    report = {}
    for kind in sorted(pools):
        th_hi, th_lo = core.THRESHOLDS[kind]
        # ①②④ 走生產同一套管線(matching.service:collapse + score_pairs)——校準即生產。
        # id 加序號保唯一(髒資料同代碼可掛異名;生產的池 key 天然唯一,校準得自己保)。
        items = [MatchItem(id=f"{i}#{n}", text=t, sources=[s])
                 for n, (i, t, s) in enumerate(pools[kind])]
        pool = matching.collapse(items)
        exact = len(items) - len(pool.ids) - sum(1 for i, t, s in pools[kind] if not core.preprocess(t))
        vectors = [v.dense for v in embedder.embed_texts(pool.texts)]   # ③
        scores = matching.score_pairs(pool, vectors)
        text_of = dict(zip(pool.ids, pool.texts))
        hist: dict[float, int] = defaultdict(int)
        for s in scores.values():
            hist[round(s, 1)] += 1
        pairs = [(s, *sorted(p)) for p, s in scores.items()]
        dup, gray = core.band(pairs, th_hi, th_lo)
        n_cross = len(scores)
        print(f"\n[{kind}] 池 {len(pools[kind])} → 唯一 {len(pool.ids)}(exact 收斂 {exact})"
              f" | 跨來源對 {n_cross} | ≥{th_hi}: {len(dup)} 對 | 灰區 [{th_lo},{th_hi}): {len(gray)} 對")
        top = sorted(hist.items(), reverse=True)[:6]
        print(f"  分布(高分帶):{['%.1f:%d' % (b, c) for b, c in top]}")
        for s, i, j in sorted(dup, reverse=True)[:5]:
            print(f"    DUP  {s:.3f}{text_of[i][:26]}{text_of[j][:26]}")
        for s, i, j in sorted(gray, reverse=True)[:10]:
            print(f"    GRAY {s:.3f}{text_of[i][:26]}{text_of[j][:26]}")
        report[kind] = {"pool": len(pools[kind]), "uniq": len(pool.ids), "exact": exact,
                        "cross": n_cross, "dup": len(dup), "gray": len(gray)}
    return report


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    embedder = HttpEmbedder(EMBEDDER_URL)
    print(f"embedder = {EMBEDDER_URL} | 門檻 = {core.THRESHOLDS}")
    all_r = {name: run_combo(embedder, name, codes) for name, codes in COMBOS.items()}
    print(f"\n{'=' * 72}\n總表(kind: 自動群對/灰區對):")
    for name, r in all_r.items():
        row = " · ".join(f"{k}:{v['dup']}/{v['gray']}" for k, v in sorted(r.items()))
        print(f"  {name}{row}")


if __name__ == "__main__":
    main()
