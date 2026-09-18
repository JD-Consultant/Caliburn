# Web 優化 階段1:批次 catalog 端點 + 前端 seed + 合併重複 recommendKS

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增後端批次 task-catalog 端點(每個不同 `ocs_code` 只撈一次能力池),前端用 `setQueryData` 預灌每任務 catalog 快取,並把 `useTaskLevel` 併入同一份 query 以消除重複 `recommendKS`。

**Architecture:** 後端讀文件 → 蒐集每任務 provenance `(ocs_code, task_code)` → 每個不同 `ocs_code` 撈一次池([`competencies`](../../apps/api/app/api/routes/ai.py))→ 用 [`task_competencies`](../../apps/api/app/services/knowledge/task_detail.py) 切出每任務 K/S/O/P/level,鍵為文件任務碼 `task_key`(如 `T1.1`)。前端文件載入後抓這份批次、`setQueryData` 灌入各 `["task-catalog", profileId, taskKey]`(TkDodo seeding/push);`useTaskCatalog` 與 `useTaskLevel` 共用同一 query key + queryFn,故開填格/級別下拉 0 等待、不重打 API。

**Tech Stack:** 後端 FastAPI + pytest(`uv run pytest`);前端 Next 16 / React 19 / TanStack Query v5(驗證 `npx tsc --noEmit` + `npm run lint` + `npm run build`,web 無單元測試框架)。

## Global Constraints

- 維護者用**繁體中文**;commit 用英文 conventional commits。
- **依 ADR 0016**:批次端點唯讀、走 note-less catalog 路徑、不跑 LLM;與既有 per-task `recommend-ks`/`draft-op`(帶 note 的 LLM 個人化)**並存、不取代**。
- **行為保持**:本階段對選單**勾選判定**零變更(仍依現狀);O/P 雖在批次回應帶 `code`,前端 seed 時仍映成 `code:""` 以保留現行 `keyOf` 行為。O/P code 的消費屬**階段 2b**,不在此。
- 後端測試:`cd apps/api && uv run pytest`。前端驗證三道綠:`cd apps/web && npx tsc --noEmit`、`npm run lint`、`npm run build`。
- 一 task 一 commit,綠了才 commit;**不要 push**。
- **不在本階段**:持久化(persistQueryClient/createPersister)+ QueryClient 全域預設 → 因需新增 npm 依賴 + 決定 staleTime 政策,留待 phase 1b 另議。

## File Structure

- `apps/api/app/api/routes/documents.py` — 新增 `GET /{profile_id}/task-catalogs` 路由(與 `get_ksa_pool` 同檔同 router)。
- `apps/api/tests/test_task_catalogs_api.py` — 新測試檔(端點行為 + 整池只撈一次)。
- `apps/web/src/lib/api.ts` — 新增 `getTaskCatalogs` + 型別。
- `apps/web/src/hooks/useTaskCatalog.ts` — 抽出共用 `fetchTaskCatalog`、新增 `useTaskCatalogs`(批次+seeding)、`useTaskLevel` 改 select 同一 query。
- `apps/web/src/app/documents/[id]/page.tsx` — 文件載入後呼叫 `useTaskCatalogs(id, hasTasks)` 觸發 seeding。

---

### Task 1: 後端批次端點 `GET /{profile_id}/task-catalogs`

**Files:**
- Modify: `apps/api/app/api/routes/documents.py`(在 `get_ksa_pool` 後新增路由 + 檔頭 import)
- Test: `apps/api/tests/test_task_catalogs_api.py`(新建)

**Interfaces:**
- Consumes:`KnowledgeClient.competencies(ocs_code) -> CompetencyPool`(既有 port);`task_competencies(pool, task_code) -> dict`;`tasks.catalog_ref(task) -> {"ocs_code","task_code"}`。
- Produces:`GET /api/v1/job-profiles/{id}/task-catalogs` → `{"catalogs": {task_key: {"knowledge":[{code,name}], "skills":[{code,name}], "outputs":[{code,name}], "indicators":[{code,text}], "competency_level": int|None}}}`。

- [ ] **Step 1: 寫失敗測試(整池只撈一次 + 每任務切片)**

新建 `apps/api/tests/test_task_catalogs_api.py`:
```python
"""階段1 批次 task-catalogs 端點：每個 ocs_code 只撈一次池、依 task_key 切片。"""
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio

from app.api.routes.documents import get_knowledge
from app.database import get_db
from app.main import app
from app.models import JobProfile, User
from app.core.knowledge_dto import CitableItem, CompetencyPool, SourceRef


class StubKnowledge:
    def __init__(self, pool=None, fail=False):
        self.pool = pool
        self.fail = fail
        self.calls = []

    async def competencies(self, ocs_code):
        self.calls.append(ocs_code)
        if self.fail:
            raise RuntimeError("indexer down")
        return self.pool or CompetencyPool(ocs_code=ocs_code)


def _pool_two_tasks():
    """OC1 池含 T1.1(K01,S01,O1,P1) 與 T1.2(K02)。"""
    return CompetencyPool(
        ocs_code="OC1",
        knowledge=[
            CitableItem(code="K01", name="標準知識", sources=[SourceRef(task_code="T1.1", competency_level=3)]),
            CitableItem(code="K02", name="法規知識", sources=[SourceRef(task_code="T1.2")]),
        ],
        skills=[CitableItem(code="S01", name="分析技能", sources=[SourceRef(task_code="T1.1")])],
        outputs=[CitableItem(code="O1", name="標準清單", sources=[SourceRef(task_code="T1.1")])],
        indicators=[CitableItem(code="P1", text="完成蒐集", sources=[SourceRef(task_code="T1.1")])],
    )


def _doc_two_tasks_same_ocs():
    def task(code, name):
        return {
            "task_codes": [{"code": code, "name": name}],
            "competency_blocks": [{"outputs": [], "indicators": [], "knowledge": [], "skills": []}],
            "provenance": {"ocs_code": "OC1", "task_code": code},
        }
    return {
        "ocs_content": {"ocu_units": [{"ocu_code": "T1", "ocu_name": "u",
                                       "tasks": [task("T1.1", "蒐集標準"), task("T1.2", "彙整法規")]}]},
        "ocs_attitude": {"attitudes": []},
    }


@pytest_asyncio.fixture
async def client(db_session):
    async def _db():
        yield db_session
    app.dependency_overrides[get_db] = _db
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t", follow_redirects=True) as ac:
        ac._db = db_session
        yield ac
    app.dependency_overrides.clear()


async def _mk_profile(db_session):
    u = User(email=f"{uuid4()}@x.com", name="n")
    db_session.add(u)
    await db_session.flush()
    p = JobProfile(user_id=u.id, job_title="工程師", job_summary="做事", selected_ocs_codes=["OC1"])
    db_session.add(p)
    await db_session.flush()
    return p


@pytest.mark.asyncio
async def test_task_catalogs_batches_pool_once_per_ocs_code(client):
    p = await _mk_profile(client._db)
    await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=_doc_two_tasks_same_ocs())
    stub = StubKnowledge(_pool_two_tasks())
    app.dependency_overrides[get_knowledge] = lambda: stub
    r = await client.get(f"/api/v1/job-profiles/{p.id}/task-catalogs")
    assert r.status_code == 200, r.text
    cats = r.json()["catalogs"]
    assert set(cats) == {"T1.1", "T1.2"}
    assert [k["code"] for k in cats["T1.1"]["knowledge"]] == ["K01"]
    assert [s["code"] for s in cats["T1.1"]["skills"]] == ["S01"]
    assert [o["code"] for o in cats["T1.1"]["outputs"]] == ["O1"]
    assert [i["code"] for i in cats["T1.1"]["indicators"]] == ["P1"]
    assert cats["T1.1"]["competency_level"] == 3
    assert [k["code"] for k in cats["T1.2"]["knowledge"]] == ["K02"]
    # 核心:同一 ocs_code 的池只撈一次(兩任務不重撈)
    assert stub.calls == ["OC1"]


@pytest.mark.asyncio
async def test_task_catalogs_skips_custom_tasks(client):
    p = await _mk_profile(client._db)
    doc = _doc_two_tasks_same_ocs()
    doc["ocs_content"]["ocu_units"][0]["tasks"].append({
        "task_codes": [{"code": "T1.3", "name": "自訂"}],
        "competency_blocks": [{"outputs": [], "indicators": [], "knowledge": [], "skills": []}],
        "provenance": {"ocs_code": "", "task_code": ""},
    })
    await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=doc)
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(_pool_two_tasks())
    r = await client.get(f"/api/v1/job-profiles/{p.id}/task-catalogs")
    assert r.status_code == 200, r.text
    assert "T1.3" not in r.json()["catalogs"]


@pytest.mark.asyncio
async def test_task_catalogs_indexer_down_degrades_empty(client):
    p = await _mk_profile(client._db)
    await client.patch(f"/api/v1/job-profiles/{p.id}/document", json=_doc_two_tasks_same_ocs())
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(fail=True)
    r = await client.get(f"/api/v1/job-profiles/{p.id}/task-catalogs")
    assert r.status_code == 200, r.text
    assert r.json() == {"catalogs": {}}


@pytest.mark.asyncio
async def test_task_catalogs_no_document_empty(client):
    p = await _mk_profile(client._db)
    app.dependency_overrides[get_knowledge] = lambda: StubKnowledge(_pool_two_tasks())
    r = await client.get(f"/api/v1/job-profiles/{p.id}/task-catalogs")
    assert r.status_code == 200, r.text
    assert r.json() == {"catalogs": {}}
```

- [ ] **Step 2: 跑測試,確認失敗(端點尚未存在 → 404)**

Run:
```bash
cd apps/api && uv run pytest tests/test_task_catalogs_api.py -v
```
Expected: FAIL(`assert 404 == 200`,端點未建)。

- [ ] **Step 3: 實作端點**

在 `apps/api/app/api/routes/documents.py` 檔頭 import 區加入:
```python
from app.services.ai import tasks as ai_tasks
from app.services.knowledge.task_detail import task_competencies
```
在 `get_ksa_pool` 之後新增路由:
```python
@router.get("/{profile_id}/task-catalogs")
async def task_catalogs(
    profile_id: UUID,
    db: AsyncSession = Depends(get_db),
    knowledge: KnowledgeClient = Depends(get_knowledge),
):
    """批次:文件每任務的官方 catalog(K/S/O/P + level),每個不同 ocs_code 只撈一次池。
    唯讀、note-less、不跑 LLM(ADR 0016)。indexer 某 code 掛 → 略過該 code 的任務(降級)。"""
    await _require_profile(profile_id, db)
    latest = await DocRepo(db).latest(profile_id)
    content = (latest or {}).get("content") or {}
    triples: list[tuple[str, str, str]] = []  # (task_key, ocs_code, task_code)
    for unit in (content.get("ocs_content") or {}).get("ocu_units") or []:
        for task in unit.get("tasks") or []:
            tcs = task.get("task_codes") or []
            tk = tcs[0].get("code") if tcs and isinstance(tcs[0], dict) else ""
            ref = ai_tasks.catalog_ref(task)
            if tk and ref["ocs_code"] and ref["task_code"]:
                triples.append((tk, ref["ocs_code"], ref["task_code"]))
    pools: dict[str, object | None] = {}
    for _, ocs_code, _ in triples:
        if ocs_code not in pools:
            try:
                pools[ocs_code] = await knowledge.competencies(ocs_code)
            except Exception:
                logger.warning("task-catalogs: competencies(%s) failed; skipping", ocs_code, exc_info=True)
                pools[ocs_code] = None
    catalogs: dict[str, dict] = {}
    for tk, ocs_code, task_code in triples:
        pool = pools.get(ocs_code)
        if pool is None:
            continue
        catalogs[tk] = task_competencies(pool, task_code)
    return {"catalogs": catalogs}
```

- [ ] **Step 4: 跑測試,確認全綠**

Run:
```bash
cd apps/api && uv run pytest tests/test_task_catalogs_api.py -v
```
Expected: 4 passed。

- [ ] **Step 5: 跑 api 全測試,確認沒打壞別的**

Run:
```bash
cd apps/api && uv run pytest -q
```
Expected: 全綠(green-before == green-after)。

- [ ] **Step 6: Commit**

```bash
git add apps/api/app/api/routes/documents.py apps/api/tests/test_task_catalogs_api.py
git commit -m "feat(api): batch task-catalogs endpoint (one pool fetch per ocs_code) [ADR 0016]"
```

---

### Task 2: 前端 API client + 型別 `getTaskCatalogs`

**Files:**
- Modify: `apps/web/src/lib/api.ts`(在 `getDocumentExport` 一帶新增)
- Modify: `apps/web/src/types/index.ts`(新增型別)

**Interfaces:**
- Consumes:Task 1 的 `GET /job-profiles/{id}/task-catalogs`。
- Produces:`getTaskCatalogs(profileId: string) => Promise<TaskCatalogs>`;型別 `TaskCatalogEntry`、`TaskCatalogs`。

- [ ] **Step 1: 新增型別**

在 `apps/web/src/types/index.ts` 末尾新增:
```typescript
// 批次 task-catalogs(階段1):每任務官方 catalog(K/S/O/P + level)。
export interface TaskCatalogEntry {
  knowledge: { code: string; name: string }[];
  skills: { code: string; name: string }[];
  outputs: { code: string; name: string }[];
  indicators: { code: string; text: string }[];
  competency_level: number | null;
}
export interface TaskCatalogs {
  catalogs: Record<string, TaskCatalogEntry>; // 鍵 = 文件任務碼(如 T1.1)
}
```

- [ ] **Step 2: 新增 API client**

在 `apps/web/src/lib/api.ts` 的 `getDocumentExport` 之後新增(並把 `TaskCatalogs` 加進檔頭 type import):
```typescript
// 批次:文件所有任務的官方 catalog(每 ocs_code 撈一次池;ADR 0016）。
export const getTaskCatalogs = (profileId: string) =>
  request<TaskCatalogs>(`/job-profiles/${profileId}/task-catalogs`);
```

- [ ] **Step 3: 型別檢查綠**

Run:
```bash
cd apps/web && npx tsc --noEmit
```
Expected: 無輸出、exit 0。

- [ ] **Step 4: Commit**

```bash
git add apps/web/src/lib/api.ts apps/web/src/types/index.ts
git commit -m "feat(web): add getTaskCatalogs API client + types"
```

---

### Task 3: 前端 seeding + 合併 `useTaskLevel`(消除重複 recommendKS)

**Files:**
- Modify: `apps/web/src/hooks/useTaskCatalog.ts`(整檔重構)
- Modify: `apps/web/src/app/documents/[id]/page.tsx`(觸發 seeding)

**Interfaces:**
- Consumes:`getTaskCatalogs`、`recommendKS`、`draftOP`。
- Produces:`useTaskCatalogs(profileId, enabled)`(批次+seeding);`useTaskCatalog(profileId, taskKey, enabled)`(同前簽名)、`useTaskLevel(profileId, taskKey, enabled)`(同前簽名,但與 useTaskCatalog 共用 `["task-catalog", profileId, taskKey]` 一份快取)。

- [ ] **Step 1: 重寫 `useTaskCatalog.ts`**

整檔換成:
```typescript
import { useEffect } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { draftOP, getTaskCatalogs, recommendKS } from "@/lib/api";
import type { OptionItem, TaskCatalogEntry } from "@/types";

// 共用形狀:一份 per-task catalog(含 level)。O/P 暫不帶 code(階段2b 才消費)。
export interface TaskCatalogData {
  knowledge: OptionItem[];
  skills: OptionItem[];
  outputs: OptionItem[];
  indicators: { code: string; text: string }[];
  competency_level: number | null;
}

const STALE = 5 * 60 * 1000;
const catalogKey = (profileId: string, taskKey: string) => ["task-catalog", profileId, taskKey];

// 後備(快取未命中)：per-task 兩端點。批次 seeding 命中時不會跑到這裡。
async function fetchTaskCatalog(profileId: string, taskKey: string): Promise<TaskCatalogData> {
  const [ks, op] = await Promise.all([
    recommendKS({ profile_id: profileId, task_key: taskKey }),
    draftOP({ profile_id: profileId, task_key: taskKey }),
  ]);
  return {
    knowledge: ks.knowledge.map((k) => ({ code: k.code, name: k.name })),
    skills: ks.skills.map((s) => ({ code: s.code, name: s.name })),
    outputs: op.outputs.map((o) => ({ code: "", name: o.name })),
    indicators: op.indicators.map((i) => ({ code: "", text: i.text })),
    competency_level: ks.competency_level ?? null,
  };
}

// 批次回應 → 共用形狀(O/P 仍映 code:""，保留現行勾選判定行為)。
function fromEntry(e: TaskCatalogEntry): TaskCatalogData {
  return {
    knowledge: e.knowledge.map((k) => ({ code: k.code, name: k.name })),
    skills: e.skills.map((s) => ({ code: s.code, name: s.name })),
    outputs: e.outputs.map((o) => ({ code: "", name: o.name })),
    indicators: e.indicators.map((i) => ({ code: "", text: i.text })),
    competency_level: e.competency_level ?? null,
  };
}

// 文件載入後抓批次,把每任務 catalog 灌進 per-task 快取(TkDodo seeding/push)。
export function useTaskCatalogs(profileId: string, enabled: boolean) {
  const qc = useQueryClient();
  const q = useQuery({
    queryKey: ["task-catalogs", profileId],
    queryFn: () => getTaskCatalogs(profileId),
    enabled,
    staleTime: STALE,
    refetchOnWindowFocus: false,
  });
  useEffect(() => {
    if (!q.data) return;
    for (const [tk, entry] of Object.entries(q.data.catalogs)) {
      qc.setQueryData(catalogKey(profileId, tk), fromEntry(entry));
    }
  }, [q.data, profileId, qc]);
  return q;
}

export function useTaskLevel(profileId: string, taskKey: string, enabled: boolean): number | null {
  const q = useQuery({
    queryKey: catalogKey(profileId, taskKey),
    enabled: enabled && !!taskKey,
    staleTime: STALE,
    queryFn: () => fetchTaskCatalog(profileId, taskKey),
    select: (d: TaskCatalogData) => d.competency_level,
  });
  return q.data ?? null;
}

export function useTaskCatalog(profileId: string, taskKey: string, enabled: boolean) {
  const q = useQuery({
    queryKey: catalogKey(profileId, taskKey),
    enabled: enabled && !!taskKey,
    staleTime: STALE,
    queryFn: () => fetchTaskCatalog(profileId, taskKey),
  });
  return {
    knowledge: q.data?.knowledge ?? [],
    skills: q.data?.skills ?? [],
    outputs: q.data?.outputs ?? [],
    indicators: q.data?.indicators ?? [],
    isLoading: q.isLoading,
  };
}
```

> 重點:`useTaskCatalog` 與 `useTaskLevel` 現在**同一 queryKey + 同一 queryFn**,只是 `select` 不同 → 同任務只會有**一份**快取、**一次** fetch(消除原本 recommendKS 被打兩次)。批次 seeding 命中時兩者皆 0 fetch。

- [ ] **Step 2: 文件頁觸發 seeding**

在 `apps/web/src/app/documents/[id]/page.tsx`:
新增一行 import(`useTaskCatalogs` 定義在 `@/hooks/useTaskCatalog`,與 `useDocument` 不同檔):
```typescript
import { useTaskCatalogs } from "@/hooks/useTaskCatalog";
```
在元件內、`doc` 與 `id` 已就緒處加入(緊接 `const hasOccupations = …` 之後):
```typescript
const taskCount = doc?.ocs_content?.ocu_units?.reduce((n, u) => n + (u.tasks?.length ?? 0), 0) ?? 0;
useTaskCatalogs(id, taskCount > 0);
```

- [ ] **Step 3: 三道綠**

Run:
```bash
cd apps/web && npx tsc --noEmit && npm run lint && npm run build
```
Expected: tsc 無輸出;lint exit 0;build 成功。

- [ ] **Step 4: 手動驗證(行為)**

啟動 dev(`npm run up` 起 infra + `turbo dev`),開一份有任務的文件,DevTools Network:
- 進文件 → 應見**一次** `GET …/task-catalogs`。
- 點任務的「級別」下拉、再點某格開填格面板 → **不應**再發 `recommend-ks`/`draft-op`(被批次 seeding 命中);級別與候選正常顯示。
Expected: 上述成立(對照改前:級別下拉 + 填格會各自打 recommend-ks/draft-op、且 recommend-ks 被打兩次)。

- [ ] **Step 5: Commit**

```bash
git add apps/web/src/hooks/useTaskCatalog.ts apps/web/src/app/documents/[id]/page.tsx
git commit -m "feat(web): seed per-task catalog cache from batch; merge useTaskLevel (dedup recommendKS)"
```

---

## Self-Review

- **Spec coverage:** 對應研究紀錄 §1 / ADR 0016 的 D-1a(批次端點,Task 1)、D-1b(setQueryData seed,Task 3 Step 1-2)、D-1c(合併重複 recommendKS,Task 3 Step 1)。D-1d 持久化**刻意延後**(Global Constraints 已載明)。
- **Placeholder scan:** 無 TBD/TODO;每段含實際程式碼與指令。
- **Type consistency:** 後端回傳 `{catalogs:{task_key:{knowledge,skills,outputs,indicators,competency_level}}}` 與前端 `TaskCatalogEntry`(Task 2)、`fromEntry`(Task 3)欄位一致;`fetchTaskCatalog` 與 `fromEntry` 皆產出同一 `TaskCatalogData` 形狀;`useTaskCatalog`/`useTaskLevel` 共用 `catalogKey`。
- **行為保持:** O/P 在前端兩條路徑(seed/後備)皆映 `code:""`,與改前 `keyOf`/勾選判定一致 → 本階段不動選單行為;O/P code 消費屬階段 2b。
- **風險:** 後端純新增端點(現有測試不受影響);前端 `useTaskCatalog`/`useTaskLevel` 簽名不變,呼叫端(CellFillerPanel/JobDocTable)無需改。
