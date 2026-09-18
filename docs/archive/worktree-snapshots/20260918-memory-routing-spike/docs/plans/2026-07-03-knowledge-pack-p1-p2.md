# 知識包 P1(api 端點)+ P2(web 資料層)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 ADR 0021 的知識包:api 新端點 `GET /job-profiles/{id}/knowledge`(P1)——選職類後一次組齊 `occupation_details + 12 池 + source_tasks`,每個官方值帶 srcs;web 新 query `["knowledge", profileId]`(P2)——persist + PUT occupations 後背景 prefetch。**本 plan 不切任何畫面**(逐面切換屬 P3,另 plan)——P1/P2 先讓包端到端可用、可驗。

**Architecture:** 決策與形狀=spec [`2026-07-03-editor-provenance-knowledge-pack-decisions.md`](../specs/2026-07-03-editor-provenance-knowledge-pack-decisions.md) §5(池 key 表、append 序、srcs 欄位名照 indexer-contract、source_tasks byURN)+ ADR 0021。組裝器= **`app/core/domain/knowledge_pack.py` 純函式**(六邊形內圈:吃 indexer DTO、產 dict、零 IO——可無 DB 單測);路由薄轉接(gather 並行、partial 降級照 ADR 0018、全掛 502)。契約機制=ADR 0021 後果段:同 ADR 0016 類,web 手寫 TS 型別、不 codegen。

**Tech Stack:** api:FastAPI + pytest(`TEST_DATABASE_URL` 供端點測試;組裝器單測無 DB)。web:TanStack Query v5(三道綠 tsc/lint/build)。

## Global Constraints

- 維護者用**繁體中文**;commit 用英文 conventional commits。一 task 一 commit、綠了才 commit、**不要 push**。green-before == green-after(api 現 164 passed)。
- **文檔同 commit 更新**(維護者 2026-07-03 指示 + Google docguide):動端點 → 同 commit 更新 `apps/api/README.md` 端點表;動 web 資料層 → 同 commit 更新 `apps/web/README.md` query 表。
- 池 key 表(spec §5.1)照抄,**不做名字正規化**(維護者:先不用做;key=原始字串精確比對)。
- srcs 欄位名**只用** indexer-contract 既有名:`ocs_code, ocs_name, ocu_code, ocu_name, task_code, task_name, code, competency_level`。
- 空池也要給空 dict(web 讀取零 guard);`occupation_details` 為 list(保序)。
- 本 plan 完成後三個舊端點(header-meta/task-candidates/task-catalogs)**照常活著**——退役在 P3 之後。

## File Structure

- `apps/api/app/core/domain/knowledge_pack.py` — 新:純組裝器 `build_pack()`。
- `apps/api/tests/test_knowledge_pack.py` — 新:組裝器單測(無 DB)。
- `apps/api/app/api/routes/documents.py` — 新路由 `GET /{profile_id}/knowledge`。
- `apps/api/tests/test_knowledge_api.py` — 新:端點測試(DB)。
- `apps/api/README.md`、`apps/web/README.md` — 端點表/query 表(同 commit)。
- `apps/web/src/types/index.ts`、`src/lib/api.ts`、`src/hooks/useKnowledge.ts`(新)、`src/hooks/useDocument.ts`(prefetch 接線)。

---

### Task 1: 組裝器 `build_pack()`(純函式,TDD)

**Files:** Create `apps/api/app/core/domain/knowledge_pack.py`、`apps/api/tests/test_knowledge_pack.py`

**Interfaces:**
- Consumes:indexer-contract DTO(`OccupationDetail`/`OccupationTasks`/`CompetencyPool`)。
- Produces:`build_pack(order, details, tasks_by_code, pools_by_code) -> dict`
  = `{occupation_details, pools:{units,tasks,knowledge,skills,outputs,indicators,attitudes,job_categories,occupations,industries,prerequisites,supplements}, source_tasks}`(meta 由路由掛)。

- [ ] **Step 1: 失敗測試**(涵蓋 spec 的每條規則;fixture 手組兩個 code 的 DTO)

```python
"""knowledge_pack 組裝器單測(純函式,無 DB)。spec §5:池 key 表、append 序、聯集、A5。"""
from app.core.domain import knowledge_pack as kp
from app.core.knowledge_dto import (
    CitableItem, CodeName, CompetencyPool, OccupationDetail, OccupationTasks,
    OcsName, SourceRef, TaskRef, UnitTasks,
)

def _detail(code, occ_name, attitudes=(), cats=(), prereqs=()):
    return OccupationDetail(
        ocs_code=code, ocs_name=OcsName(occupation_name=occ_name),
        job_categories=[CodeName(code=c, name=n) for c, n in cats],
        attitudes=[CodeName(code=c, name=n) for c, n in attitudes],
        prerequisites=list(prereqs), job_description=f"{occ_name}描述", ocs_level=4)

def _tasks(code, occ_name, units):  # units = [(ocu_code, ocu_name, [(t_code, t_name)])]
    return OccupationTasks(ocs_code=code, ocs_name=occ_name, units=[
        UnitTasks(ocu_code=uc, ocu_name=un,
                  tasks=[TaskRef(task_code=tc, task_name=tn) for tc, tn in ts])
        for uc, un, ts in units])

def _pool(code, occ_name, knowledge=(), skills=(), outputs=(), indicators=()):
    def items(spec, textual=False):
        out = []
        for item_code, val, srcs in spec:  # srcs=[(task_code, level)]
            out.append(CitableItem(
                code=item_code, name=None if textual else val, text=val if textual else None,
                ocs_code=code, ocs_name=occ_name,
                sources=[SourceRef(task_code=tc, competency_level=lv) for tc, lv in srcs]))
        return out
    return CompetencyPool(ocs_code=code,
        knowledge=items(knowledge), skills=items(skills),
        outputs=items(outputs), indicators=items(indicators, textual=True))

def _two_code_pack():
    """A=OC1(順序1)、B=OC2:同名職責「維護」、同名任務「保養」、同名 K「統計」;
    B 另有 A01 撞碼態度(名字不同,A5)。"""
    details = {
        "OC1": _detail("OC1", "甲職業", attitudes=[("A01", "主動積極")],
                       cats=[("J", "資訊服務")], prereqs=["大學以上"]),
        "OC2": _detail("OC2", "乙職業", attitudes=[("A01", "誠信正直")],
                       cats=[("J", "資訊服務")], prereqs=["大學以上"]),
    }
    tasks = {
        "OC1": _tasks("OC1", "甲職業", [("T1", "維護", [("T1.1", "保養"), ("T1.2", "巡檢")])]),
        "OC2": _tasks("OC2", "乙職業", [("T2", "維護", [("T2.3", "保養")])]),
    }
    pools = {
        "OC1": _pool("OC1", "甲職業",
                     knowledge=[("K03", "統計", [("T1.1", 3)]), ("K05", "電學", [("T1.2", 3)])],
                     outputs=[("O1", "紀錄表", [("T1.1", None)])],
                     indicators=[("P1", "完成保養並記錄", [("T1.1", None)])]),
        "OC2": _pool("OC2", "乙職業", knowledge=[("K07", "統計", [("T2.3", 4)])]),
    }
    return kp.build_pack(["OC1", "OC2"], details, tasks, pools)

def test_pools_merge_by_key_and_accumulate_srcs():
    p = _two_code_pack()
    stats = p["pools"]["knowledge"]["統計"]
    assert [s["ocs_code"] for s in stats["srcs"]] == ["OC1", "OC2"]   # append 序:A 先
    assert stats["srcs"][0]["code"] == "K03" and stats["srcs"][1]["code"] == "K07"
    assert list(p["pools"]["knowledge"]) == ["統計", "電學"]           # 合併列停在首現位置

def test_attitudes_dedup_by_name_not_code():  # A5:A01 撞碼不得合併
    p = _two_code_pack()
    assert set(p["pools"]["attitudes"]) == {"主動積極", "誠信正直"}

def test_categories_dedup_by_code_and_notes_by_text():
    p = _two_code_pack()
    assert list(p["pools"]["job_categories"]) == ["J"]
    assert [s["ocs_code"] for s in p["pools"]["job_categories"]["J"]["srcs"]] == ["OC1", "OC2"]
    assert [s["ocs_code"] for s in p["pools"]["prerequisites"]["大學以上"]["srcs"]] == ["OC1", "OC2"]

def test_units_and_tasks_merge_by_name_with_urn_srcs():
    p = _two_code_pack()
    assert [s["ocs_code"] for s in p["pools"]["units"]["維護"]["srcs"]] == ["OC1", "OC2"]
    assert p["pools"]["tasks"]["保養"]["srcs"] == ["ocs:OC1:T:T1.1", "ocs:OC2:T:T2.3"]

def test_source_tasks_carry_refs_and_level():
    p = _two_code_pack()
    t11 = p["source_tasks"]["ocs:OC1:T:T1.1"]
    assert t11["k_refs"] == ["統計"] and t11["o_refs"] == ["紀錄表"]
    assert t11["p_refs"] == ["完成保養並記錄"] and t11["competency_level"] == 3
    assert p["source_tasks"]["ocs:OC2:T:T2.3"]["competency_level"] == 4

def test_occupation_details_keep_selection_order():
    p = _two_code_pack()
    assert [d["ocs_code"] for d in p["occupation_details"]] == ["OC1", "OC2"]

def test_empty_input_gives_empty_shape():
    p = kp.build_pack([], {}, {}, {})
    assert p["occupation_details"] == [] and p["source_tasks"] == {}
    assert set(p["pools"]) == {"units", "tasks", "knowledge", "skills", "outputs",
        "indicators", "attitudes", "job_categories", "occupations", "industries",
        "prerequisites", "supplements"}
    assert all(v == {} for v in p["pools"].values())
```

- [ ] **Step 2: 紅**:`cd apps/api && uv run pytest tests/test_knowledge_pack.py -q` → FAIL(模組不存在)。

- [ ] **Step 3: 實作 `knowledge_pack.py`**

```python
"""知識包組裝器(ADR 0021):純函式,吃 indexer-contract DTO、產 pack dict。
規則=spec 2026-07-03 §5:池 append 序 + key 去重 + srcs 累積(欄位名照 indexer-contract);
source_tasks 以任務 URN byId,掛 o/p/k/s_refs(池 key)。名字不做正規化(維護者拍板)。"""
from __future__ import annotations

from app.core.knowledge_dto import CompetencyPool, OccupationDetail, OccupationTasks

POOL_NAMES = ("units", "tasks", "knowledge", "skills", "outputs", "indicators",
              "attitudes", "job_categories", "occupations", "industries",
              "prerequisites", "supplements")


def _task_urn(ocs_code: str, task_code: str) -> str:
    return f"ocs:{ocs_code}:T:{task_code}"  # scheme 同 indexer api/urn.py


def _occ_name(d: OccupationDetail) -> str:
    return d.ocs_name.occupation_name or d.ocs_name.job_category_name or d.ocs_code


def _row(pool: dict, key: str) -> dict:
    return pool.setdefault(key, {"srcs": []})


def build_pack(order: list[str], details: dict[str, OccupationDetail],
               tasks_by_code: dict[str, OccupationTasks],
               pools_by_code: dict[str, CompetencyPool]) -> dict:
    pack: dict = {"occupation_details": [], "pools": {n: {} for n in POOL_NAMES},
                  "source_tasks": {}}
    pools = pack["pools"]
    for code in order:                        # append 序 = 職位優先序(維護者:A 先 append B)
        d = details.get(code)
        if d is None:
            continue                          # 該 code 抓失敗(partial 由路由標)
        name = _occ_name(d)
        pack["occupation_details"].append(d.model_dump())
        # 表頭池:態度=name key(A5);三類=code key;notes=text key
        for a in d.attitudes:
            if a.name:
                _row(pools["attitudes"], a.name)["srcs"].append(
                    {"ocs_code": code, "ocs_name": name, "code": a.code})
        for pool_name, items in (("job_categories", d.job_categories),
                                 ("occupations", d.occupations),
                                 ("industries", d.industries)):
            for c in items:
                if not c.code:
                    continue
                row = pools[pool_name].setdefault(c.code, {"name": c.name, "srcs": []})
                row["srcs"].append({"ocs_code": code, "ocs_name": name})
        for pool_name, texts in (("prerequisites", d.prerequisites),
                                 ("supplements", d.supplements)):
            for t in texts:
                if t.strip():
                    _row(pools[pool_name], t)["srcs"].append(
                        {"ocs_code": code, "ocs_name": name})
        # 結構層:units/tasks 池(name key)+ source_tasks 骨架(URN byId)
        occ_tasks = tasks_by_code.get(code)
        for u in (occ_tasks.units if occ_tasks else []):
            if u.ocu_name:
                _row(pools["units"], u.ocu_name)["srcs"].append(
                    {"ocs_code": code, "ocs_name": name,
                     "ocu_code": u.ocu_code, "ocu_name": u.ocu_name})
            for t in u.tasks:
                urn = _task_urn(code, t.task_code)
                if t.task_name:
                    row = _row(pools["tasks"], t.task_name)
                    if urn not in row["srcs"]:
                        row["srcs"].append(urn)   # 任務池 srcs = source_tasks 的 URN
                pack["source_tasks"][urn] = {
                    "ocs_code": code, "ocs_name": name,
                    "ocu_code": u.ocu_code, "ocu_name": u.ocu_name,
                    "task_code": t.task_code, "task_name": t.task_name,
                    "competency_level": None,
                    "o_refs": [], "p_refs": [], "k_refs": [], "s_refs": []}
        # 能力池:K/S/O=name key、P=text key;同時反向掛 refs + 補 level
        comp = pools_by_code.get(code)
        for pool_name, ref_field, items, textual in (
                ("knowledge", "k_refs", comp.knowledge if comp else [], False),
                ("skills", "s_refs", comp.skills if comp else [], False),
                ("outputs", "o_refs", comp.outputs if comp else [], False),
                ("indicators", "p_refs", comp.indicators if comp else [], True)):
            for it in items:
                key = (it.text if textual else it.name) or ""
                if not key:
                    continue
                row = _row(pools[pool_name], key)
                for s in it.sources:
                    row["srcs"].append({
                        "ocs_code": code, "ocs_name": name, "code": it.code,
                        "ocu_code": s.ocu_code, "ocu_name": s.ocu_name,
                        "task_code": s.task_code, "task_name": s.task_name,
                        "competency_level": s.competency_level})
                    node = pack["source_tasks"].get(_task_urn(code, s.task_code or ""))
                    if node is None:
                        continue
                    if key not in node[ref_field]:
                        node[ref_field].append(key)
                    if node["competency_level"] is None and s.competency_level is not None:
                        node["competency_level"] = s.competency_level
    return pack
```

- [ ] **Step 4: 綠 + 全套**:`uv run pytest tests/test_knowledge_pack.py -q && uv run pytest -q`(164+7)。

- [ ] **Step 5: Commit**

```bash
git add apps/api/app/core/domain/knowledge_pack.py apps/api/tests/test_knowledge_pack.py
git commit -m "feat(api): knowledge pack assembler - pools by dedup key + source_tasks by URN [ADR 0021]"
```

---

### Task 2: 路由 `GET /{profile_id}/knowledge`(gather 並行 + partial)

**Files:** Modify `apps/api/app/api/routes/documents.py`;Create `apps/api/tests/test_knowledge_api.py`;Modify `apps/api/README.md`(端點表 + 一行流程)

- [ ] **Step 1: 失敗測試**(stub KnowledgeClient;沿 test_task_catalogs_api.py 的 fixture 模式)
  - happy:兩 code → occupation_details 保序、pools 合併、`meta.partial=False`
  - 單 code 掛(stub 對 OC2 raise)→ 200、只含 OC1、`meta.partial=True`
  - 全掛 → **502**
  - 未選職類 → 200 空 pack、partial=False
- [ ] **Step 2: 紅**。
- [ ] **Step 3: 實作**(documents.py;`import asyncio` + `from app.core.domain import knowledge_pack`)

```python
@router.get("/{profile_id}/knowledge")
async def get_knowledge_pack(
    profile_id: UUID,
    db: AsyncSession = Depends(get_db),
    knowledge: KnowledgeClient = Depends(get_knowledge),
):
    """知識包(ADR 0021):選職類後一次抓齊(occupation_details + 12 池 + source_tasks,
    每官方值帶 srcs)。per-code 並行抓、**組裝照優先序**(append 序);單 code 掛 → 略過 +
    ``meta.partial=true``(ADR 0018);**全掛 → 502**(沒有 knowledge 流程走不下去,critical)。"""
    profile = await _require_profile(profile_id, db)
    codes = profile.selected_ocs_codes or []
    if not codes:
        pack = knowledge_pack.build_pack([], {}, {}, {})
        pack["meta"] = {"partial": False}
        return pack

    async def fetch_one(code: str):
        return (await knowledge.occupation(code),
                await knowledge.occupation_tasks(code),
                await knowledge.competencies(code))

    results = await asyncio.gather(*(fetch_one(c) for c in codes), return_exceptions=True)
    details, tasks_by, pools_by, ok = {}, {}, {}, []
    for code, r in zip(codes, results):
        if isinstance(r, BaseException):
            logger.warning("knowledge: fetch(%s) failed; skipping", code, exc_info=r)
            continue
        details[code], tasks_by[code], pools_by[code] = r
        ok.append(code)
    if not ok:
        raise HTTPException(status_code=502, detail="indexer unavailable")
    pack = knowledge_pack.build_pack(ok, details, tasks_by, pools_by)
    pack["meta"] = {"partial": len(ok) < len(codes)}
    return pack
```

- [ ] **Step 4: 綠 + 全套**。
- [ ] **Step 5: 同 commit 更新 `apps/api/README.md`**:端點表加一列
  `GET …/knowledge | 知識包:occupation_details+12 池+source_tasks,每值帶 srcs(ADR 0021) | 全掛 502/單掛 partial`;
  「關鍵流程」補一小節(選職類→抓包→池化,3 行)。
- [ ] **Step 6: Commit**

```bash
git add apps/api/app/api/routes/documents.py apps/api/tests/test_knowledge_api.py apps/api/README.md
git commit -m "feat(api): GET /job-profiles/{id}/knowledge - parallel per-code fetch, partial degrade, 502 on total failure [ADR 0021]"
```

---

### Task 3(P2): web query + prefetch 接線

**Files:** Modify `apps/web/src/types/index.ts`、`src/lib/api.ts`、`src/hooks/useDocument.ts`;Create `src/hooks/useKnowledge.ts`;Modify `apps/web/README.md`

- [ ] **Step 1: 型別**(手寫,ADR 0021 契約裁決;欄位名照 wire)

```typescript
// ── 知識包(ADR 0021):選職類後一次抓齊,所有選單的資料源;每官方值帶 srcs ──
export interface PackSrc {
  ocs_code: string; ocs_name: string;
  ocu_code?: string | null; ocu_name?: string | null;
  task_code?: string | null; task_name?: string | null;
  code?: string | null; competency_level?: number | null;
}
export interface PoolRow { srcs: PackSrc[] }
export interface CodedPoolRow extends PoolRow { name: string }        // 三類池(key=分類碼)
export interface SourceTask {
  ocs_code: string; ocs_name: string;
  ocu_code?: string | null; ocu_name?: string | null;
  task_code: string; task_name: string;
  competency_level: number | null;
  o_refs: string[]; p_refs: string[]; k_refs: string[]; s_refs: string[];
}
export interface KnowledgePack {
  occupation_details: {
    ocs_code: string; ocs_name: { job_category_name?: string | null; occupation_name?: string | null };
    job_description: string; ocs_level: number | null;
  }[];
  pools: {
    units: Record<string, PoolRow>;
    tasks: Record<string, { srcs: string[] }>;      // srcs = source_tasks 的 URN
    knowledge: Record<string, PoolRow>; skills: Record<string, PoolRow>;
    outputs: Record<string, PoolRow>; indicators: Record<string, PoolRow>;
    attitudes: Record<string, PoolRow>;
    job_categories: Record<string, CodedPoolRow>;
    occupations: Record<string, CodedPoolRow>; industries: Record<string, CodedPoolRow>;
    prerequisites: Record<string, PoolRow>; supplements: Record<string, PoolRow>;
  };
  source_tasks: Record<string, SourceTask>;         // 鍵 = 任務 URN
  meta?: DegradeMeta;
}
```

- [ ] **Step 2: client + hook**

`api.ts`:`export const getKnowledge = (profileId: string) => request<KnowledgePack>(`/job-profiles/${profileId}/knowledge`);`

`hooks/useKnowledge.ts`(新):
```typescript
import { useQuery } from "@tanstack/react-query";
import { getKnowledge } from "@/lib/api";

// 知識包(ADR 0021):選職類=唯一同步點。persist、staleTime 24h(官方基準版本化不可變,
// 與 persist maxAge 同節奏);重選職類由 useSetOccupations invalidate。
export const knowledgeKey = (profileId: string) => ["knowledge", profileId];

export function useKnowledge(profileId: string, enabled: boolean) {
  return useQuery({
    queryKey: knowledgeKey(profileId),
    queryFn: () => getKnowledge(profileId),
    enabled,
    staleTime: 1000 * 60 * 60 * 24,
    gcTime: 1000 * 60 * 60 * 24, // ≥ persist maxAge(24h)
    refetchOnWindowFocus: false,
    meta: { persist: true },
  });
}
```

- [ ] **Step 3: PUT occupations 成功 → invalidate + 背景 prefetch**

`useDocument.ts` 的 `useSetOccupations.onSuccess` 加:
```typescript
      qc.invalidateQueries({ queryKey: ["knowledge", profileId] });
      // 背景預載知識包(ADR 0021:選職類=唯一同步點;不鎖 UI,失敗交給 query 重試)
      void qc.prefetchQuery({
        queryKey: ["knowledge", profileId],
        queryFn: () => getKnowledge(profileId),
      });
```
(檔頭 import `getKnowledge`。)

- [ ] **Step 4: 三道綠**:`npx tsc --noEmit && npm run lint && npm run build`。
- [ ] **Step 5: 手動驗證**:dev 環境選職類 → Network 見一次 `GET …/knowledge`(200,含 pools/source_tasks);DevTools Application → localStorage `caliburn-rq-cache` 內含 knowledge 條目;重整頁面不再重打(staleTime 內)。
- [ ] **Step 6: 同 commit 更新 `apps/web/README.md`**:五 query 表加 `["knowledge", id]` 一列(persist ✓),持久化段落補一句。
- [ ] **Step 7: Commit**

```bash
git add apps/web/src/types/index.ts apps/web/src/lib/api.ts apps/web/src/hooks/useKnowledge.ts apps/web/src/hooks/useDocument.ts apps/web/README.md
git commit -m "feat(web): knowledge pack query - persisted, prefetched on occupation selection [ADR 0021]"
```

---

## Self-Review

- **Spec coverage:** §5 形狀(occupation_details/12 池/source_tasks/meta)、§5.1 key 表(含 A5 態度 name key 的測試)、append 序、聯集素材(srcs 累積)、URN 僅用於 source_tasks 鍵與任務池 srcs、資料流三決策之②(背景 prefetch)。**不含**:畫面切換(P3)、A4 文件重編(P3)、舊端點退役(P3 後)。
- **Type consistency:** 組裝器輸出 ⇄ 端點測試斷言 ⇄ web `KnowledgePack` 手寫型別逐欄對齊(srcs 欄位名=indexer-contract)。
- **Naming:** 端點 `knowledge`(名詞資源);`occupation_details` 用契約型別名複數;池名全部契約欄位名;`knowledge_pack.py` 住 core/domain(純)。
- **降級:** 沿 ADR 0018(partial)+ 全掛 502(critical);gather(return_exceptions)。
- **風險:** 純新增(端點/型別/hook),不動既有畫面與三個舊端點 → 零行為變更;buster 不需 bump(新增 query,舊持久化形狀未變)。
- **不過度設計檢查:** 無 gzip/ETag/快取層;fetch_one 內三個 await 循序(本地部署,毫秒級,不值得再拆);組裝器單一函式,不抽 class。
