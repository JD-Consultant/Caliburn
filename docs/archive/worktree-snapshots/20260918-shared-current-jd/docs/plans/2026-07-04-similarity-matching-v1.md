# 相似比對(similarity matching)v1 — 實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** indexer 新增確定性 `POST /items:match`(池進 → 真重複群 + 灰區對出),api 組完知識包後掛 `similarity`,web 態度池收合 + 任務相似徽章——全程非破壞、降級 = 沒這功能。

**Architecture:** 權威 = [spec](../specs/2026-07-04-similarity-matching-v1-spec.md) + ADR 0022。六步純管線關在 indexer(僅嵌入一步有 I/O);api 純搬運(enrichment);web 鐵律 = **選擇邏輯跑在平選項上一行不改,分群只是 render 顯示變換**。

**Tech Stack:** pydantic(indexer-contract)· FastAPI · BGE-M3 via `apps/embedder` HTTP · vitest(web src/lib)· pytest。

## Global Constraints

- 一 task 一 commit,綠了才 commit;**不 push**。收尾打 tag `similarity-v1`。
- 測試指令:indexer `cd apps/ocs-indexer && uv run --all-extras pytest`;api `cd apps/api && uv run pytest`;web `cd apps/web && npm run test`、`npx tsc --noEmit`、`npm run lint`。CJK 輸出加 `PYTHONUTF8=1`。
- 命名:pair 欄位 **left/right 家族,禁用 a/b**(Splink 慣例)。kind 集合:`task|unit|knowledge|skill|output|indicator|attitude`。
- 門檻(spec §2,實驗出處研究 §9.4):task/unit {0.95, 0.80} · knowledge/skill/output/indicator {0.85, 0.65} · attitude {0.90, 0.70}。
- 錯誤:items>500 → 413、kind 不認得 → 422、embedder 掛 → 503;body = FastAPI `detail` dict 含 `code` 欄位。
- **顯示文字永不改**:前處理/NFKC 只產比對 key;回應引用一律原 id。
- Windows 踩雷:動手前 `pwd` + `git branch --show-current`(工作分支 = `main`,repo = `S:\caliburn`)。

---

### Task 1: 契約模型(indexer-contract)+ SimilarPair a/b 改名

**Files:**
- Modify: `packages/indexer-contract/src/indexer_contract/models.py`
- Modify: `apps/ocs-indexer/src/jd_ocs_indexer/api/schemas.py`(re-export 清單)
- Modify: `apps/ocs-indexer/src/jd_ocs_indexer/api/service.py`(`_pairwise_candidates` 的 `"a"/"b"` dict key)
- Modify: `apps/ocs-indexer/tests/test_find_similar.py`(斷言 key)
- Modify: `apps/api/app/core/knowledge_dto.py`(re-export 清單)

**Interfaces:**
- Produces(後續 task 依賴的確切型別):`MatchItem(id, text, sources)`、`MatchRequest(kind, items)`、`GroupMember(id, score)`、`MatchGroup(medoid, members)`、`PossibleMatch(left_id, right_id, score)`、`MatchConfig(kind, theta_high, theta_low, model)`、`MatchResponse(groups, possible_matches, config)`。

- [ ] **Step 1: models.py 加相似比對模型 + SimilarPair 改名**

在 `models.py` 的 `# ── requests ──` 區加:

```python
class MatchItem(_Base):
    id: str
    text: str
    sources: list[str] = Field(default_factory=list)


class MatchRequest(_Base):
    kind: str
    items: list[MatchItem] = Field(default_factory=list)
```

在 `# ── batch get / find similar / ops ──` 區、`FindSimilarResponse` 之後加:

```python
# 相似比對(ADR 0022)。pair 命名照 Splink left/right 慣例(禁用 a/b)。
class GroupMember(_Base):
    id: str
    score: float = 0.0          # 與群中心的分數;中心自身 = 1.0


class MatchGroup(_Base):
    medoid: str = ""            # 幾何代表(群內平均相似度最高的成員 id)
    members: list[GroupMember] = Field(default_factory=list)


class PossibleMatch(_Base):
    left_id: str = ""
    right_id: str = ""          # 恆 left_id < right_id(決定論)
    score: float = 0.0


class MatchConfig(_Base):
    kind: str = ""
    theta_high: float = 0.0
    theta_low: float = 0.0
    model: str = "bge-m3"


class MatchResponse(_Base):
    groups: list[MatchGroup] = Field(default_factory=list)
    possible_matches: list[PossibleMatch] = Field(default_factory=list)
    config: MatchConfig = Field(default_factory=MatchConfig)
```

同檔把 `SimilarPair` 改成:

```python
class SimilarPair(_Base):
    left: SimilarTaskRef
    right: SimilarTaskRef
    score: float
```

- [ ] **Step 2: 追平消費者**

`apps/ocs-indexer/src/jd_ocs_indexer/api/schemas.py` 的 import 清單加 `MatchItem, MatchRequest, MatchResponse, MatchGroup, GroupMember, PossibleMatch, MatchConfig`。
`service.py` 內 grep `"a":` / `"b":`(`_pairwise_candidates` 回傳的 dict)改為 `"left"` / `"right"`。
`tests/test_find_similar.py` 斷言 `p["a"]`/`p["b"]` 改 `p["left"]`/`p["right"]`。
`apps/api/app/core/knowledge_dto.py` 的 import 清單加 `MatchItem, MatchResponse`(api 端只需這兩個 + 巢狀自動帶入)。

- [ ] **Step 3: 跑兩邊測試**

Run: `cd apps/ocs-indexer && uv run --all-extras pytest tests/test_find_similar.py -q` → PASS;`cd apps/api && uv run pytest tests/test_knowledge_models.py -q` → PASS(契約 re-export 未破)。

- [ ] **Step 4: Commit**

```bash
git add packages/indexer-contract apps/ocs-indexer apps/api/app/core/knowledge_dto.py
git commit -m "feat(contract): items:match models; rename SimilarPair a/b -> left/right (Splink naming)"
```

---

### Task 2: matching core 純函式(indexer,TDD)

**Files:**
- Create: `apps/ocs-indexer/src/jd_ocs_indexer/matching/__init__.py`(空檔)
- Create: `apps/ocs-indexer/src/jd_ocs_indexer/matching/core.py`
- Test: `apps/ocs-indexer/tests/test_matching_core.py`

**Interfaces:**
- Produces:`THRESHOLDS: dict[str, tuple[float, float]]`、`preprocess(text) -> str`、`collapse_key(text) -> str`、`cosine(a, b) -> float`、`band(scored_pairs, th_hi, th_lo) -> (dup, gray)`(scored_pairs = `[(score, id_i, id_j)]`)、`star_clusters(dup_pairs, score_of, th_hi) -> list[(center, {member: score})]`(score_of = `(x, y) -> float | None`)、`medoid_of(ids, score_of) -> str`。

- [ ] **Step 1: 寫失敗測試**

```python
"""matching core 純函式測試 — 假分數,不需 GPU/embedder。spec §2/§6。"""
from jd_ocs_indexer.matching import core


def test_preprocess_strips_marks_and_cjk_gaps():
    assert core.preprocess("問題解決能力【T1.1】【T1.2】") == "問題解決能力"
    assert core.preprocess("檢驗分 析能力") == "檢驗分析能力"          # CJK 字間空白刪
    assert core.preprocess("ISO 9001 品質知識") == "ISO 9001品質知識"  # 拉丁 token 間保留
    assert core.preprocess("操作機台【註3】 ") == "操作機台"


def test_collapse_key_nfkc():
    assert core.collapse_key("品質(管理)") == core.collapse_key("品質(管理)")  # 全形=半形


def test_band_three_zones():
    pairs = [(0.96, "x", "y"), (0.85, "x", "z"), (0.5, "y", "z")]
    dup, gray = core.band(pairs, 0.95, 0.80)
    assert dup == [(0.96, "x", "y")]
    assert gray == [(0.85, "x", "z")]          # <0.80 丟棄


def _score_of(table):
    def f(x, y):
        return table.get(frozenset((x, y)))
    return f


def test_star_no_chaining():
    # A–B 0.96、B–C 0.96,但 A–C 只有 0.5 → C 不得經 B 鏈入 A 的群(SKOS 紅線)
    table = {frozenset(("A", "B")): 0.96, frozenset(("B", "C")): 0.96, frozenset(("A", "C")): 0.5}
    clusters = core.star_clusters([(0.96, "A", "B"), (0.96, "B", "C")], _score_of(table), 0.95)
    assert clusters == [("A", {"B": 0.96})]    # center=min(id);C 與中心 A 直連 0.5 → 拒入


def test_star_admits_direct_link():
    table = {frozenset(("A", "B")): 0.97, frozenset(("A", "C")): 0.96, frozenset(("B", "C")): 0.96}
    clusters = core.star_clusters([(0.97, "A", "B"), (0.96, "B", "C")], _score_of(table), 0.95)
    assert clusters == [("A", {"B": 0.97, "C": 0.96})]  # C 與中心 A 直連 0.96 → 以該分入群


def test_star_deterministic_ordering():
    # 同分對:照 (left, right) id 升序處理 → 同輸入必同輸出
    table = {frozenset(("A", "B")): 0.96, frozenset(("C", "D")): 0.96}
    c1 = core.star_clusters([(0.96, "C", "D"), (0.96, "A", "B")], _score_of(table), 0.95)
    c2 = core.star_clusters([(0.96, "A", "B"), (0.96, "C", "D")], _score_of(table), 0.95)
    assert c1 == c2 == [("A", {"B": 0.96}), ("C", {"D": 0.96})]


def test_medoid_highest_avg_tie_by_id():
    table = {frozenset(("A", "B")): 0.9, frozenset(("A", "C")): 0.9, frozenset(("B", "C")): 0.99}
    assert core.medoid_of(["A", "B", "C"], _score_of(table)) == "B"   # B 平均最高;缺分以 0 計
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd apps/ocs-indexer && uv run --all-extras pytest tests/test_matching_core.py -q`
Expected: FAIL(`ModuleNotFoundError: jd_ocs_indexer.matching`)

- [ ] **Step 3: 實作 core.py**

```python
"""相似比對核心 — 純函式(零 I/O)。ADR 0022;spec docs/specs/2026-07-04-similarity-matching-v1-spec.md。
分帶 = Fellegi-Sunter 三區;分群 = 貪婪星型(成員與中心直連 ≥θ_high,SKOS closeMatch
非遞移紅線——絕不做連通分量)。改門檻 = 改 THRESHOLDS + 跑校準腳本留紀錄(docs/specs/)。"""
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
_CJK = "㐀-䶿一-鿿豈-﫿"
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


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


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
        elif cx is not None and cy is None and cy != cx:
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
```

- [ ] **Step 4: 跑測試確認通過**

Run: `cd apps/ocs-indexer && uv run --all-extras pytest tests/test_matching_core.py -q` → PASS(7 tests)。
再跑全套確認零回歸:`uv run --all-extras pytest -q` → PASS。

- [ ] **Step 5: Commit**

```bash
git add apps/ocs-indexer/src/jd_ocs_indexer/matching apps/ocs-indexer/tests/test_matching_core.py
git commit -m "feat(indexer): matching core — preprocess/NFKC/FS banding/greedy star/medoid (pure, TDD)"
```

---

### Task 3: `POST /items:match` 端點(indexer)

**Files:**
- Modify: `apps/ocs-indexer/src/jd_ocs_indexer/api/service.py`(加 `match_items`)
- Modify: `apps/ocs-indexer/src/jd_ocs_indexer/api/routes.py`(加 route)
- Test: `apps/ocs-indexer/tests/test_items_match.py`

**Interfaces:**
- Consumes: Task 1 契約模型、Task 2 core 函式、既有 `HttpEmbedder.embed_texts(texts) -> list[EmbeddedVector]`(`.dense: list[float]`)。
- Produces: `service.match_items(embedder, *, kind: str, items: list[MatchItem]) -> MatchResponse`;route `POST /items:match`。

- [ ] **Step 1: 寫失敗測試(假 embedder,不需容器)**

```python
"""items:match 端點測試 — 假 embedder 餵可控向量。spec §1/§2/§5。"""
import threading
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from jd_ocs_indexer.api.routes import router


class _Vec(SimpleNamespace):
    pass


class FakeEmbedder:
    provider = "bge-m3"

    def __init__(self, table):
        self._table = table          # text -> dense vector

    def embed_texts(self, texts):
        return [_Vec(dense=self._table[t]) for t in texts]


def _app(table):
    app = FastAPI()
    app.include_router(router)
    app.state.embedder = FakeEmbedder(table)
    app.state.embed_lock = threading.Lock()
    app.state.client = None          # match 不碰 Qdrant
    app.state.settings = SimpleNamespace(qdrant_collection="unused")
    return TestClient(app)


def _items(*rows):
    return [{"id": r[0], "text": r[0], "sources": list(r[1])} for r in rows]


def test_groups_and_gray_and_config():
    # 向量設計:X≈Y(cos≈1, 進群)、X–Z cos≈0.72(灰區)、皆跨來源
    table = {"主動積極": [1.0, 0.0], "主動 積極": [1.0, 0.0], "持續學習": [0.72, 0.6939]}
    c = _app(table)
    body = {"kind": "attitude", "items": _items(
        ("主動積極", ["OC1"]), ("主動 積極", ["OC2"]), ("持續學習", ["OC3"]))}
    r = c.post("/items:match", json=body)
    assert r.status_code == 200
    data = r.json()
    assert data["config"] == {"kind": "attitude", "theta_high": 0.9, "theta_low": 0.7, "model": "bge-m3"}
    # 「主動 積極」前處理後與「主動積極」同字 → exact-collapse 成群(score 1.0),不經嵌入分帶
    [g] = data["groups"]
    ids = {m["id"] for m in g["members"]}
    assert ids == {"主動積極", "主動 積極"}
    [p] = data["possible_matches"]
    assert p["left_id"] < p["right_id"] and 0.7 <= p["score"] < 0.9


def test_same_source_pairs_skipped():
    table = {"甲": [1.0, 0.0], "乙": [1.0, 0.0]}
    c = _app(table)
    r = c.post("/items:match", json={"kind": "task", "items": _items(("甲", ["OC1"]), ("乙", ["OC1"]))})
    assert r.status_code == 200
    assert r.json()["groups"] == [] and r.json()["possible_matches"] == []  # 同基準刻意分開,不比


def test_limits_and_unknown_kind():
    c = _app({})
    too_many = {"kind": "task", "items": [{"id": str(i), "text": str(i), "sources": []} for i in range(501)]}
    assert c.post("/items:match", json=too_many).status_code == 413
    assert c.post("/items:match", json={"kind": "nope", "items": []}).status_code == 422
    # <2 條:短路回空,不打 embedder(FakeEmbedder 空表也不會炸)
    ok = c.post("/items:match", json={"kind": "task", "items": _items(("唯一", ["OC1"]))})
    assert ok.status_code == 200 and ok.json()["groups"] == []
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd apps/ocs-indexer && uv run --all-extras pytest tests/test_items_match.py -q`
Expected: FAIL(404 — route 不存在)

- [ ] **Step 3: service.py 加 `match_items`**

```python
# service.py 頂部 import 區加:
from jd_ocs_indexer.api.schemas import (..., GroupMember, MatchConfig, MatchGroup,
                                        MatchItem, MatchResponse, PossibleMatch)
from jd_ocs_indexer.matching import core

# 檔尾加:
def match_items(embedder, *, kind: str, items: list[MatchItem]) -> MatchResponse:
    """相似比對(ADR 0022):①清洗 ②NFKC 同字收斂 ③嵌入(唯一 I/O)④跨來源兩兩
    cosine ⑤FS 分帶 ⑥星型分群+medoid。純輸入輸出,不碰 Qdrant。"""
    th_hi, th_lo = core.THRESHOLDS[kind]
    cfg = MatchConfig(kind=kind, theta_high=th_hi, theta_low=th_lo,
                      model=getattr(embedder, "provider", "bge-m3"))

    # ① 清洗(空文字丟);② NFKC key 收斂:rep = 池序第一個,exact_dup 記在 rep 名下
    rep_text: dict[str, str] = {}                    # key -> 清洗後文字(rep 的)
    rep_id: dict[str, str] = {}                      # key -> rep id
    rep_sources: dict[str, set[str]] = {}            # key -> 來源聯集(跨來源跳過規則用)
    exact_dups: dict[str, list[str]] = {}            # rep id -> 其餘同字 id
    order: list[str] = []
    for it in items:
        text = core.preprocess(it.text)
        if not text:
            continue
        k = core.collapse_key(text)
        if k not in rep_id:
            rep_id[k], rep_text[k], rep_sources[k] = it.id, text, set(it.sources)
            exact_dups[it.id] = []
            order.append(k)
        else:
            exact_dups[rep_id[k]].append(it.id)
            rep_sources[k] |= set(it.sources)

    ids = [rep_id[k] for k in order]
    if len(ids) >= 2:
        # ③ 一批嵌入;④ 跨來源兩兩(來源有交集 → 同基準刻意分開,不比)
        vecs = {rep_id[k]: v.dense for k, v in zip(order, embedder.embed_texts([rep_text[k] for k in order]))}
        srcs = {rep_id[k]: rep_sources[k] for k in order}
        scores: dict[frozenset, float] = {}
        for x in range(len(ids)):
            for y in range(x + 1, len(ids)):
                i, j = ids[x], ids[y]
                if srcs[i] & srcs[j]:
                    continue
                scores[frozenset((i, j))] = core.cosine(vecs[i], vecs[j])

        def score_of(i, j):
            return scores.get(frozenset((i, j)))

        # ⑤⑥ 分帶 → 星型 → medoid
        pairs = [(s, *sorted(p)) for p, s in scores.items()]
        dup, gray = core.band(pairs, th_hi, th_lo)
        clusters = core.star_clusters(dup, score_of, th_hi)
    else:
        score_of = lambda i, j: None  # noqa: E731
        gray, clusters = [], []

    # 組回應:exact-dup(score 1.0)併入所屬群;純 exact 群(未進嵌入群)單獨成群
    groups: list[MatchGroup] = []
    clustered_reps = set()
    for center, mems in clusters:
        clustered_reps.update({center, *mems})
        all_ids = [center, *mems.keys()]
        member_rows = [GroupMember(id=center, score=1.0)]
        member_rows += [GroupMember(id=m, score=round(s, 4)) for m, s in sorted(mems.items())]
        for rep in list(all_ids):
            member_rows += [GroupMember(id=d, score=1.0) for d in exact_dups.get(rep, [])]
        groups.append(MatchGroup(medoid=core.medoid_of(all_ids, score_of), members=member_rows))
    for rep, dups in exact_dups.items():
        if dups and rep not in clustered_reps:
            groups.append(MatchGroup(medoid=rep, members=[
                GroupMember(id=rep, score=1.0), *[GroupMember(id=d, score=1.0) for d in dups]]))
    groups.sort(key=lambda g: g.medoid)

    matches = [PossibleMatch(left_id=i, right_id=j, score=round(s, 4)) for s, i, j in gray]
    matches.sort(key=lambda m: (-m.score, m.left_id, m.right_id))
    return MatchResponse(groups=groups, possible_matches=matches, config=cfg)
```

- [ ] **Step 4: routes.py 加 route**

import 清單加 `MatchRequest, MatchResponse`;`tasks:findSimilar` route 之後加:

```python
# 相似比對(ADR 0022):池進 → {真重複群, 灰區對} 出。確定性、非破壞;
# 錯誤 body = detail dict 含 code(version_conflict 先例)。
@router.post("/items:match", response_model=MatchResponse)
async def match_items(req: MatchRequest, request: Request):
    app = request.app
    if len(req.items) > 500:
        raise HTTPException(status_code=413, detail={"code": "too_many_items", "max": 500})
    if req.kind not in core.THRESHOLDS:
        raise HTTPException(status_code=422, detail={"code": "unknown_kind", "kind": req.kind})

    def _run():
        with app.state.embed_lock:
            return service.match_items(app.state.embedder, kind=req.kind, items=req.items)

    try:
        return await run_in_threadpool(_run)
    except httpx.HTTPError as exc:   # embedder 掛/超時 → 503(api 端據此降級)
        raise HTTPException(status_code=503, detail={"code": "embedder_unavailable"}) from exc
```

routes.py 頂部加 `import httpx` 與 `from jd_ocs_indexer.matching import core`。

- [ ] **Step 5: 跑測試**

Run: `cd apps/ocs-indexer && uv run --all-extras pytest tests/test_items_match.py tests/test_matching_core.py -q` → PASS;全套 `uv run --all-extras pytest -q` → PASS。

- [ ] **Step 6: Commit**

```bash
git add apps/ocs-indexer
git commit -m "feat(indexer): POST /items:match — six-step deterministic pipeline (ADR 0022)"
```

---

### Task 4: 校準腳本(units 一起跑)

**Files:**
- Create: `apps/ocs-indexer/scripts/calibrate_match.py`
- Test: 手動跑(需 embedder 容器;輸出人審)

**Interfaces:**
- Consumes: Task 2 core、既有 `HttpEmbedder`、`data/jd-json/*.json`。
- Produces: stdout 報告(per kind:池量/exact 收斂/分布直方/斷崖位置/dup 對/灰區對數)——校準紀錄貼進 `docs/specs/`。

- [ ] **Step 1: 寫腳本**

以本輪實驗腳本為基礎(研究 §9.6 scratchpad `grayzone_experiment.py`),差異:
(1) 改用 `core.preprocess/collapse_key/cosine/band`(DRY——同一套碼,校準即生產);
(2) 嵌入走 `HttpEmbedder(settings.embedder_url)`;
(3) kinds 加 `unit`(ocu_name 池);
(4) 組合清單放檔頭常數(軟體三職類 / 品管三職類 / 同職雙版本,ocs_code 見研究 §9.4);
(5) 每 kind 輸出:`池 n → 唯一 m(exact 收斂 k)| 跨來源對 p | ≥θ_high: d 對 | 灰區: g 對`
    + 0.1 級距直方圖 + 高分帶前 10 對全文。

- [ ] **Step 2: 跑並留紀錄**

Run: `npm run infra`(embedder 起)後
`cd apps/ocs-indexer && PYTHONUTF8=1 uv run python scripts/calibrate_match.py`
Expected: 三組合 × 5 kind 報告;attitude/task 數字與研究 §9.4 表一致(±嵌入非決定性容差)。
把輸出貼進 `docs/specs/2026-07-04-similarity-matching-calibration.md`(校準紀錄;units 的
分布是否乾淨 → 決定 units 接不接線,記在同檔)。

- [ ] **Step 3: Commit**

```bash
git add apps/ocs-indexer/scripts/calibrate_match.py docs/specs/2026-07-04-similarity-matching-calibration.md
git commit -m "feat(indexer): match calibration script + first calibration record (incl. units)"
```

---

### Task 5: api port / client(KnowledgePort.match + HttpIndexerClient.match)

**Files:**
- Modify: `apps/api/app/core/ports.py`
- Modify: `apps/api/app/adapters/knowledge_http.py`
- Test: `apps/api/tests/test_http_indexer_client.py`(加一測;照該檔既有 respx/httpx mock 模式)

**Interfaces:**
- Consumes: Task 1 的 `MatchResponse`(經 `app.core.knowledge_dto` re-export)。
- Produces: `KnowledgePort.match(kind: str, items: list[dict]) -> MatchResponse`(items = `[{id, text, sources}]` 原始 dict——api 端組池 rows,不強型別化以免重複映射)。

- [ ] **Step 1: 寫失敗測試**

打開 `tests/test_http_indexer_client.py`,照該檔既有 mock 模式(讀檔頂 fixture)加:

```python
async def test_match_posts_items_and_parses(respx_or_fixture):   # 依該檔既有簽名命名
    # mock POST /items:match 回 {"groups":[],"possible_matches":[{"left_id":"甲","right_id":"乙","score":0.82}],
    #                            "config":{"kind":"task","theta_high":0.95,"theta_low":0.8,"model":"bge-m3"}}
    resp = await client.match("task", [{"id": "甲", "text": "甲", "sources": ["OC1"]}])
    assert resp.possible_matches[0].left_id == "甲"
    assert resp.config.theta_low == 0.8
```

Run: `cd apps/api && uv run pytest tests/test_http_indexer_client.py -q` → FAIL(`match` 不存在)。

- [ ] **Step 2: 實作**

`ports.py` 的 import 加 `MatchResponse`,`KnowledgePort` 加:

```python
    async def match(self, kind: str, items: list[dict]) -> MatchResponse: ...
```

`knowledge_http.py` 的 import 加 `MatchResponse`,class 加:

```python
    async def match(self, kind: str, items: list[dict]) -> MatchResponse:
        resp = await self._client.post("/items:match", json={"kind": kind, "items": items})
        resp.raise_for_status()
        return MatchResponse.model_validate(resp.json())
```

grep `apps/api` 內其他 KnowledgePort 實作(`adapters/stubs.py`、測試 stub)補 `match`(stub 回空 `MatchResponse()`)。

- [ ] **Step 3: 跑測試 → Commit**

Run: `cd apps/api && uv run pytest -q` → PASS。

```bash
git add apps/api
git commit -m "feat(api): KnowledgePort.match + HttpIndexerClient.match"
```

---

### Task 6: api 掛載(`similarity` + `meta.similarity`)

**Files:**
- Modify: `apps/api/app/core/domain/knowledge_pack.py`(加純 helper `similarity_items`)
- Modify: `apps/api/app/api/routes/documents.py::get_knowledge_pack`
- Test: `apps/api/tests/test_knowledge_pack.py`(純 helper)+ `apps/api/tests/test_knowledge_api.py`(route,照該檔既有 stub 模式)

**Interfaces:**
- Consumes: Task 5 `knowledge.match`。
- Produces: pack 回應多 `similarity: {attitude?, task?}` 與 `meta.similarity: "ok"|"partial"|"unavailable"`(spec §3;池與既有 `meta.partial` 不動)。

- [ ] **Step 1: 寫失敗測試(純 helper)**

`test_knowledge_pack.py` 加:

```python
def test_similarity_items_from_pools():
    pack = {"pools": {
        "attitudes": {"主動積極": {"srcs": [{"ocs_code": "OC1", "ocs_name": "n", "code": "A1"},
                                            {"ocs_code": "OC2", "ocs_name": "n", "code": "A2"}]}},
        "tasks": {"巡檢": {"srcs": ["ocs:OC1:T:T1.1", "ocs:OC2:T:T2.2"]}},
    }}
    items = knowledge_pack.similarity_items(pack)
    assert items["attitude"] == [{"id": "主動積極", "text": "主動積極", "sources": ["OC1", "OC2"]}]
    assert items["task"] == [{"id": "巡檢", "text": "巡檢", "sources": ["OC1", "OC2"]}]
```

Run: `cd apps/api && uv run pytest tests/test_knowledge_pack.py -q` → FAIL。

- [ ] **Step 2: 實作 helper(knowledge_pack.py 檔尾)**

```python
def similarity_items(pack: dict) -> dict[str, list[dict]]:
    """v1 兩表面的 items:match 輸入(spec §3)。sources 排序去重 → 決定論。
    態度池 srcs = dict(取 ocs_code);任務池 srcs = URN "ocs:{ocs_code}:T:{code}"(取第 2 段)。"""
    att = [{"id": k, "text": k, "sources": sorted({s["ocs_code"] for s in row["srcs"]})}
           for k, row in pack["pools"]["attitudes"].items()]
    task = [{"id": k, "text": k, "sources": sorted({u.split(":")[1] for u in row["srcs"]})}
            for k, row in pack["pools"]["tasks"].items()]
    return {"attitude": att, "task": task}
```

- [ ] **Step 3: route 掛載(documents.py,`build_pack` 之後、`return pack` 之前)**

```python
    pack = knowledge_pack.build_pack(ok, details, tasks_by, pools_by)
    pack["meta"] = {"partial": len(ok) < len(codes)}
    # 相似比對(ADR 0022,enrichment):失敗不擋池,狀態顯式標 meta.similarity。
    sim: dict = {}
    items_by_kind = knowledge_pack.similarity_items(pack)
    results = await asyncio.gather(
        *(knowledge.match(kind, items) for kind, items in items_by_kind.items()),
        return_exceptions=True)
    for kind, r in zip(items_by_kind.keys(), results):
        if isinstance(r, BaseException):
            logger.warning("knowledge: match(%s) failed; degrading", kind, exc_info=r)
        else:
            sim[kind] = r.model_dump()
    pack["similarity"] = sim
    pack["meta"]["similarity"] = "ok" if len(sim) == len(items_by_kind) else ("partial" if sim else "unavailable")
    return pack
```

route 測試(`test_knowledge_api.py`,照該檔既有 stub):stub 的 `match` 回固定
`MatchResponse(groups=[], possible_matches=[], config=MatchConfig(kind=...))` → 斷言回應含
`similarity.attitude` 與 `meta.similarity == "ok"`;另一測讓 stub `match` raise → 斷言
`similarity == {}`、`meta.similarity == "unavailable"`、pools 照常。

- [ ] **Step 4: 跑測試 → Commit**

Run: `cd apps/api && uv run pytest -q` → PASS。

```bash
git add apps/api
git commit -m "feat(api): attach similarity to knowledge pack (enrichment + meta.similarity)"
```

---

### Task 7: web 型別 + pack.ts 純函式(vitest)

**Files:**
- Modify: `apps/web/src/types/index.ts`
- Modify: `apps/web/src/lib/pack.ts`
- Test: `apps/web/src/lib/pack.test.ts`

**Interfaces:**
- Produces: `groupedValueOptions(options, match, primaryCode) -> OptionItem[]`(rep 列帶 `variants`)、`taskRowsWithSimilar(pack) -> TaskRowVM[]`(列帶 `similarTo`)、`survivor(members, primaryCode) -> OptionItem`。

- [ ] **Step 1: types/index.ts 加型別**

```ts
// ── 相似比對(ADR 0022;欄位名照 indexer-contract,left/right 家族)──
export interface MatchGroupMember { id: string; score: number }
export interface MatchGroup { medoid: string; members: MatchGroupMember[] }
export interface PossibleMatch { left_id: string; right_id: string; score: number }
export interface MatchResult {
  groups: MatchGroup[];
  possible_matches: PossibleMatch[];
  config: { kind: string; theta_high: number; theta_low: number; model: string };
}
```

`OptionItem` 加 `variants?: OptionItem[];`(群成員,收合展示用;沒有 = 普通選項)。
`KnowledgePack` 加 `similarity?: { attitude?: MatchResult; task?: MatchResult };`,
其 `meta` 型別加 `similarity?: "ok" | "partial" | "unavailable";`。
`pack.ts` 的 `TaskRowVM` 加 `similarTo?: { name: string; score: number }[];`。

- [ ] **Step 2: 寫失敗測試(pack.test.ts 加)**

```ts
import { groupedValueOptions, taskRowsWithSimilar } from "./pack";

const opt = (name: string, ocs: string): OptionItem =>
  ({ code: "", name, srcs: [{ ocs_code: ocs, occupation_name: ocs, code: "A1" }] });
const match = (ids: string[][]): MatchResult => ({
  groups: ids.map((g) => ({ medoid: g[0], members: g.map((id) => ({ id, score: 0.93 })) })),
  possible_matches: [], config: { kind: "attitude", theta_high: 0.9, theta_low: 0.7, model: "bge-m3" },
});

describe("groupedValueOptions", () => {
  const flat = [opt("團隊合作", "OC1"), opt("團隊意識", "OC2"), opt("持續學習", "OC3")];

  it("match 缺席 → 原樣返回(降級 = 逐位元同現狀)", () => {
    expect(groupedValueOptions(flat, undefined, "OC1")).toEqual(flat);
  });

  it("survivorship:主基準成員在群內必為代表;其餘進 variants", () => {
    const out = groupedValueOptions(flat, match([["團隊合作", "團隊意識"]]), "OC2");
    expect(out).toHaveLength(2);
    expect(out[0].name).toBe("團隊意識");                 // OC2 = 主基準 → 代表
    expect(out[0].variants?.map((v) => v.name)).toEqual(["團隊合作"]);
  });

  it("主基準不在群內 → 文字最長當代表(tie → 名稱升序)", () => {
    const out = groupedValueOptions(flat, match([["團隊合作", "團隊意識"]]), "OC9");
    expect(out[0].name).toBe("團隊合作");                 // 等長 → 升序取先
  });

  it("代表列就是成員本人(身分不變),池序保持", () => {
    const out = groupedValueOptions(flat, match([["團隊合作", "團隊意識"]]), "OC1");
    expect(out[0]).toMatchObject({ name: "團隊合作", srcs: flat[0].srcs });  // 真身
    expect(out[1].name).toBe("持續學習");                 // 群外選項原位
  });
});

describe("taskRowsWithSimilar", () => {
  it("灰區對雙向掛 similarTo;無 similarity → 原樣", () => {
    const pack = {
      pools: { units: {}, tasks: { 巡檢: { srcs: ["ocs:OC1:T:T1"] }, 控管: { srcs: ["ocs:OC2:T:T2"] } } },
      source_tasks: {
        "ocs:OC1:T:T1": { ocs_code: "OC1", ocs_name: "", task_code: "T1", task_name: "巡檢" },
        "ocs:OC2:T:T2": { ocs_code: "OC2", ocs_name: "", task_code: "T2", task_name: "控管" },
      },
      similarity: { task: { groups: [], possible_matches: [{ left_id: "巡檢", right_id: "控管", score: 0.85 }],
        config: { kind: "task", theta_high: 0.95, theta_low: 0.8, model: "bge-m3" } } },
    } as unknown as KnowledgePack;
    const rows = taskRowsWithSimilar(pack);
    expect(rows.find((r) => r.name === "巡檢")?.similarTo).toEqual([{ name: "控管", score: 0.85 }]);
    expect(rows.find((r) => r.name === "控管")?.similarTo).toEqual([{ name: "巡檢", score: 0.85 }]);
  });
});
```

Run: `cd apps/web && npm run test` → FAIL(函式不存在)。

- [ ] **Step 3: pack.ts 實作(檔尾加)**

```ts
// ── 相似比對(ADR 0022)。鐵律:選擇邏輯(primaryDefaults/自動套/勾選/寫入)跑在
// 平選項上一行不改;以下只是 render 前最後一步的顯示變換。──────────────────────

// survivorship(顯示代表):主基準成員優先 → 文字最長 → 名稱升序(決定論)。
function survivor(members: OptionItem[], primaryCode: string): OptionItem {
  const primary = members.find((o) => (o.srcs ?? []).some((s) => s.ocs_code === primaryCode));
  if (primary) return primary;
  return [...members].sort((a, b) => b.name.length - a.name.length || a.name.localeCompare(b.name))[0];
}

// 值池選項 → 顯示列:群成員收成一列(代表 = survivor,其餘進 variants;代表列就是
// 成員本人,群無可選身分)。match 缺席 → 原樣返回(降級)。池序保持:群在首個成員位。
export function groupedValueOptions(
  options: OptionItem[], match: MatchResult | undefined, primaryCode: string,
): OptionItem[] {
  if (!match?.groups?.length) return options;
  const byName = new Map(options.map((o) => [o.name, o]));
  const groupOf = new Map<string, MatchGroup>();
  for (const g of match.groups) for (const m of g.members) groupOf.set(m.id, g);
  const emitted = new Set<MatchGroup>();
  const out: OptionItem[] = [];
  for (const o of options) {
    const g = groupOf.get(o.name);
    if (!g) { out.push(o); continue; }
    if (emitted.has(g)) continue;
    emitted.add(g);
    const members = g.members.map((m) => byName.get(m.id)).filter((x): x is OptionItem => !!x);
    if (members.length < 2) { out.push(o); continue; }   // 成員對不上池 → 不收合
    const rep = survivor(members, primaryCode);
    out.push({ ...rep, variants: members.filter((m) => m !== rep) });
  }
  return out;
}

// 任務列 + 灰區對(雙向)。similarity 缺席 → 原樣(降級)。
export function taskRowsWithSimilar(pack: KnowledgePack): TaskRowVM[] {
  const rows = taskRows(pack);
  const pairs = pack.similarity?.task?.possible_matches ?? [];
  if (!pairs.length) return rows;
  const map = new Map<string, { name: string; score: number }[]>();
  const push = (k: string, v: { name: string; score: number }) => {
    const arr = map.get(k) ?? [];
    arr.push(v);
    map.set(k, arr);
  };
  for (const p of pairs) {
    push(p.left_id, { name: p.right_id, score: p.score });
    push(p.right_id, { name: p.left_id, score: p.score });
  }
  return rows.map((r) => (map.has(r.name) ? { ...r, similarTo: map.get(r.name)! } : r));
}
```

(import 區補 `MatchGroup, MatchResult`。)

- [ ] **Step 4: 跑測試 → Commit**

Run: `cd apps/web && npm run test && npx tsc --noEmit && npm run lint` → PASS。

```bash
git add apps/web/src/types/index.ts apps/web/src/lib/pack.ts apps/web/src/lib/pack.test.ts
git commit -m "feat(web): similarity types + groupedValueOptions/taskRowsWithSimilar (render-only, vitest)"
```

---

### Task 8: web 態度池收合 UI(FieldCombobox variants + JobDocTable)

**Files:**
- Modify: `apps/web/src/components/interview/fields/FieldCombobox.tsx`
- Modify: `apps/web/src/components/interview/JobDocTable.tsx`(態度區,~L298)

**Interfaces:**
- Consumes: Task 7 `groupedValueOptions`、`OptionItem.variants`。
- 鐵律檢查:`defaults` prop 繼續餵**平選項**的 `primaryDefaults` 結果 → `applyDefaults`/首開自動套/`officialMatch` 全不感知分群。

- [ ] **Step 1: FieldCombobox 渲染 variants**

`toggleList` 的 CommandItem 渲染中,選項帶 `variants` 時:(1) 勾選標記改看
`isOfficialSelected(o) || (o.variants ?? []).some(isOfficialSelected)`(群列 checked =
任一成員 checked);(2) 名稱旁加「n 個版本」小徽章,點擊 toggle 展開(`useState<Set<string>>`
記展開的 rep key,`e.stopPropagation()` 防觸發勾選);(3) 展開時 variants 逐條渲染成縮排
CommandItem(`className="pl-8"`),各自走既有 `toggle(variant)` / `isOfficialSelected(variant)`
——**寫入身分永遠是成員真身**。徽章示意:

```tsx
{(o.variants?.length ?? 0) > 0 && (
  <button type="button" className="shrink-0 rounded bg-sky-100 px-1 text-[10px] text-sky-700"
    onClick={(e) => { e.stopPropagation(); toggleExpand(k); }}>
    {(o.variants!.length + 1)} 個版本 {expanded.has(k) ? "▴" : "▾"}
  </button>
)}
```

- [ ] **Step 2: JobDocTable 態度區接線**

```tsx
const flat = pack ? valuePoolOptions(pack.pools.attitudes) : [];
const options = pack ? groupedValueOptions(flat, pack.similarity?.attitude, primaryCode) : [];
// defaults 一律用 flat(鐵律:自動勾選跑在平選項上)——原本傳法不變
```

(`primaryCode` = 該檔既有的主基準碼變數;grep `isOfficialBasis` 用法即得。)

- [ ] **Step 3: 驗證**

Run: `cd apps/web && npx tsc --noEmit && npm run lint && npm run test` → PASS。
手動(`npm run up`):選兩個品管職類 → 態度選單:同義態度收成一列帶「2 個版本▾」;
展開可改勾特定版本;首開自動套只勾主基準身分(展開檢查勾在主基準那條);
`npm run down` 後(similarity 拿不到)選單與現狀完全相同。

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/components
git commit -m "feat(web): attitude pool group collapse UI (variants expand; flat-options auto-check untouched)"
```

---

### Task 9: web 任務相似徽章(TaskPickerMenu)

**Files:**
- Modify: `apps/web/src/components/interview/TaskPickerMenu.tsx`(L27 `taskRows(pack)` → `taskRowsWithSimilar(pack)`)

- [ ] **Step 1: 接線 + 徽章**

`const rows = pack ? taskRowsWithSimilar(pack) : [];`(import 改自 pack.ts)。
列渲染處,`row.similarTo` 存在時名稱旁加徽章 + Popover 並排比較(**純顯示:不自動勾、
不合併、不擋**):

```tsx
{row.similarTo && (
  <Popover>
    <PopoverTrigger asChild>
      <button type="button" className="shrink-0 rounded bg-amber-100 px-1 text-[10px] text-amber-700"
        onClick={(e) => e.stopPropagation()}>
        ⚠ 與 {row.similarTo.length} 項相似
      </button>
    </PopoverTrigger>
    <PopoverContent className="w-80 text-xs">
      <p className="mb-1 font-medium">相似任務(請確認是否為同一件事):</p>
      <p className="rounded bg-muted/50 p-1">{row.name}</p>
      {row.similarTo.map((s) => (
        <p key={s.name} className="mt-1 rounded border p-1">{s.name}
          <span className="ml-1 text-muted-foreground">{Math.round(s.score * 100)}%</span></p>
      ))}
    </PopoverContent>
  </Popover>
)}
```

- [ ] **Step 2: 驗證 → Commit**

Run: `cd apps/web && npx tsc --noEmit && npm run lint` → PASS。手動:品管多選 →
「製程品質巡檢/控管」類任務出現徽章、點開並排全文;勾選行為與現狀無異。

```bash
git add apps/web/src/components/interview/TaskPickerMenu.tsx
git commit -m "feat(web): task similar-pair badges with side-by-side compare (display-only)"
```

---

### Task 10: 文檔更新 + tag(spec §8 義務)

**Files:**
- Modify: `docs/design/editor-knowledge-pack.md`(similarity 掛載點、web 顯示變換鐵律、不變量 A/B)
- Modify: `apps/ocs-indexer/README.md`(查詢 API 面加 `POST /items:match` 一列:input/output/門檻表/錯誤碼)
- Modify: `apps/api/README.md`(knowledge pack 端點說明加 `similarity` + `meta.similarity`)
- Modify: `apps/web/README.md`(pack 讀取層加 groupedValueOptions/taskRowsWithSimilar 與鐵律一句)
- Modify: `docs/adr/README.md`(0022 狀態 → 「Accepted(v1 已實作)」)

- [ ] **Step 1: 逐檔更新**(寫法照 dual-audience 清單:動作→請求、真名、不變量、退役禁令。
  editor-knowledge-pack.md 的不變量區加:「分群是 render-only 顯示變換;選擇/自動勾選
  永遠跑在平選項——把分群搬進選擇邏輯 = 違規」。)

- [ ] **Step 2: 全 repo 綠 → Commit + tag**

Run: `npx turbo test` → PASS。

```bash
git add docs apps/ocs-indexer/README.md apps/api/README.md apps/web/README.md
git commit -m "docs: living docs for similarity matching v1 (design/READMEs/ADR index)"
git tag similarity-v1
```

---

## Self-review(spec 覆蓋檢查)

- spec §0 範圍/非目標 → Task 1–9 = v1 範圍;reranker/快取/units 接線皆未實作 ✓(units 校準在 Task 4)
- §1 契約(left_id/right_id、SimilarPair 改名)→ Task 1 ✓
- §2 六步管線 + 門檻表 + 決定論 + 星型紅線 → Task 2/3 ✓
- §3 api 搬運 + meta.similarity → Task 6 ✓(Task 5 為其 port 前置)
- §4 web 鐵律 + survivorship + 不變量 → Task 7(純函式與測試)/8/9(UI)✓
- §5 錯誤(413/422/503、ApiError 零新機制)→ Task 3(indexer 端)/6(api 降級)✓;web 端零改動即符合
- §6 測試策略 → Task 2(星型紅線/決定論)、3(端點)、4(校準)、7(vitest 六案的純函式子集;
  自動套交互的元件層行為由 Task 8 手動驗證項覆蓋)✓
- §7 升級槽 → 不實作,僅 Task 10 文檔註記 ✓
- §8 文檔義務 → Task 10 ✓
