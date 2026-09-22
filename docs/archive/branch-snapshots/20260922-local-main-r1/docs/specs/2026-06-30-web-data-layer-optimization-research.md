# Web 資料層優化研究紀錄 — 快取/預抓/持久化、存檔並發、項目穩定身分

> **類型**:研究紀錄(findings + 已拍板決策)。決策另寫 ADR。
> **日期**:2026-06-30
> **動機**:盤點 `apps/web` 的資料抓取與存檔邏輯,找優化空間。使用者起點兩個直覺:
> ①「任務級別下拉才抓,但抓過就該先記」②「判斷是否改過的邏輯」。研究後擴成三叢集。
> **協作前提(使用者補充)**:未來 LLM 會與使用者**共編同一份文件**,模式為**回合制 / 提議套用**
> (agent 提議結構化變更或套一個 patch,使用者接受/編輯;**非**逐字即時同步)。此前提決定 2a 架構。

---

## 0. 現況盤點(基礎其實不錯)

`apps/web` 已採 **TanStack Query(React Query)**:快取、樂觀更新、debounce 自動儲存皆有。
非從零,是「調得更對 + 補並發安全網」。

| 現行件 | 位置 | 觀察 |
|---|---|---|
| 文件查詢/樂觀 PATCH | [useDocument.ts](../../apps/web/src/hooks/useDocument.ts) | `usePatchDocument` 有 `onMutate`/rollback;但 PATCH **整份 OcsDocument** |
| 自動儲存 | [useDocument.ts:105](../../apps/web/src/hooks/useDocument.ts) | debounce 500ms + 卸載前 flush;狀態由 mutation `isPending` 推導 |
| 任務級別/目錄 | [useTaskCatalog.ts](../../apps/web/src/hooks/useTaskCatalog.ts) | `useTaskLevel` 與 `useTaskCatalog` **各打一次 `recommendKS`**(同任務同資料、不同 queryKey) |
| 選單勾選判定 | [FieldCombobox.tsx:41](../../apps/web/src/components/interview/fields/FieldCombobox.tsx) | `isOfficialSelected` **只比 `name`**(忽略 code,註解自承 code 為位置序碼) |
| QueryClient | [Providers.tsx:11](../../apps/web/src/components/layout/Providers.tsx) | 純記憶體、**無全域預設**;各 hook 各自重抄 `staleTime`/`refetchOnWindowFocus` |
| 後端 PATCH | [documents.py:63](../../apps/api/app/api/routes/documents.py) | `upsert_draft(profile_id, body)`:收整份、**無 version 檢查**、last-write-wins |
| 死代碼 | `AiTaskPanel.tsx`、`fields/FieldBoundSelect.tsx` | 全 repo 無 import |

---

## 1. 叢集一:快取 / 預抓 / 持久化(對應使用者例 ①)

### 診斷
1. **已會記**:`useTaskLevel` 有 `staleTime: 5min`,同任務 5 分鐘內再開不重抓。
2. **重複請求**:`useTaskLevel` + `useTaskCatalog` 各打一次 `recommendKS`;級別 `competency_level` 本就在 catalog 回應裡。
3. **重載失憶**:QueryClient 純記憶體,重新整理 → catalog/level/header-meta 全重抓(走 indexer/LLM,慢)。
4. **整池重撈(最大浪費)**:per-task catalog 來自 [ai.py `_catalog_ks`/`_catalog_op`](../../apps/api/app/api/routes/ai.py) → `knowledge.competencies(ocs_code)`,**一次撈整個 ocs_code 的能力池**再在記憶體切某 task([task_detail.py](../../apps/api/app/services/knowledge/task_detail.py))。前端每任務各打 recommend-ks + draft-op → **同一個 ocs_code 的整池被重撈 N×2 次**。
5. `task-candidates` 回應**不帶 K/S/O/P**([documents.py:153](../../apps/api/app/api/routes/documents.py)、type [CandidateTask](../../apps/web/src/types/index.ts)),故無法在「選任務當下」直接 push catalog。

### 權威發現
- **TkDodo(TanStack Query 維護者)— Seeding the Query Cache**:三種灌快取法 —
  `prefetchQuery`(並行預抓)、`setQueryData`(push:抓清單時順手寫各 detail 快取)、`initialData`/`placeholderData`(pull:從相關 query 取初值)。
- **TanStack — persistQueryClient / createPersister**:把快取寫進 localStorage/IndexedDB 以跨重載;`maxAge`(預設 24h)、`gcTime ≥ maxAge`、`buster` 字串綁版本失效;`createPersister` 可**per-query 選擇性**持久化。
- **TanStack — Render Optimizations / structural sharing**:資料未變則保留引用,`select` 衍生值 shape 不變即穩定。

### 決策(已與使用者拍板)
- **D-1a 後端批次 catalog 端點**:新增端點(如 `GET /job-profiles/{id}/task-catalogs`),每個**不同 `ocs_code` 撈一次池**、切出**該文件所有任務**的 `{task_key → {knowledge,skills,outputs,indicators,competency_level}}`,一次回。→ N×2 整池重撈壓到「不同 ocs_code 數」次。
- **D-1b 前端 seed**:用 `setQueryData` 把批次結果灌進各 `["task-catalog", profileId, taskKey]`;開填格 0 等待、不發請求(TkDodo push)。
- **D-1c 合併重複 `recommendKS`**:`useTaskLevel` 不自抓,改 `select` 從同一份 catalog 衍生 `competency_level`。
- **D-1d 持久化**(2026-06-30 修正:改採**穩定版** API,非 experimental):用 `PersistQueryClientProvider`
  + `createSyncStoragePersister`(localStorage),以 `dehydrateOptions.shouldDehydrateQuery` +
  query `meta:{persist:true}` **選擇性**只持久化「確定性、貴」的 query(`task-catalog`/`task-catalogs`、
  `header-meta`),**不**持久化 `document`(of-record、要即時);`maxAge`(預設 24h)+ `buster`(綁 schema 版本);
  被持久化的 query `gcTime ≥ maxAge`。
  > 原本選 `experimental_createQueryPersister`(per-query),但其 API 掛 `experimental_`、無 mutation 支援;
  > 為求主流穩定改用 `persistQueryClient` 家族(v5 已穩定、~170 萬週下載)。階段 1b plan 詳述。

---

## 2. 叢集二-a:存檔 / 並發協作(對應使用者例 ②的真正核心)

### 診斷
- 真正的地雷是**整份文件 PATCH = last-write-wins**:即使沒有 LLM,使用者**開兩個分頁**就會互蓋;LLM 共編更嚴重。
- `version` 全鏈路都有但**從未當並發守衛**([documents.py:70](../../apps/api/app/api/routes/documents.py) 不檢查 version)。
- autosave 對**每次** commit 都送 PATCH,改了又改回(內容相同)也送 no-op。

### 權威發現(人 + LLM 共編一份文件的三層做法)
| 方案 | 代表 | 適合 | 成本 |
|---|---|---|---|
| **樂觀並發(version / ETag → 409/412)** | 一般 REST、GitHub API | server 權威、**回合制** | 低(已有 `version`) |
| **OT(Operational Transform)** | Google Docs | server 權威、結構化、AI 高速 | 中 |
| **CRDT(Yjs/Automerge)** | Figma、Notion | 離線優先、**即時逐字**、P2P | 高(每字 16–32B metadata) |

- **AI 速度問題**(Taskade OT-vs-CRDT):agent 產出比人快 **25–100×**;不論演算法都需 **agent 層批次化 + 限速到人類節奏 + 人類操作優先**。
- 本專案文件是**高度結構化 JSON**(職責→任務→能力區塊→K/S/O/P 陣列),編輯本就是 [ocsDoc.ts](../../apps/web/src/lib/ocsDoc.ts) 的離散操作 → 強烈傾向「細粒度操作 + 樂觀並發」,**CRDT/OT 對回合制屬過度設計**。

### 決策(已與使用者拍板:回合制 → 樂觀並發,不上 CRDT/OT)
保留現有樂觀更新 + 自動儲存 + `version` 欄位。分兩層,**先 minimal**:

- **D-2a-minimal(先做)**:
  1. **no-op 跳過**:維護 last-saved 快照,`commit` 時結構相等比對,相等不送 PATCH;狀態列改由「current vs baseline 是否相等」推導。
  2. **啟用 version 守衛**:PATCH 帶 expected version → server 版本不符回 **409** → 前端重抓最新 + 重套未存編輯。對回合制即正確(LLM turn +1;使用者舊版本存檔 → 409 → 重抓重套)。
- **D-2a-full(延後,選用)**:整份 PATCH → **逐操作/逐區段 PATCH**,使用者與 LLM 改不同處時免 409、自動併;LLM 走**同一操作 seam** + 批次/人類優先。
- 參照 React Hook Form `isDirty`:dirty = current vs **baseline 快照**結構相等;存檔成功後**重設 baseline**(等同 `reset(values)`)。

> 註:此處的「last-saved 快照 + 結構相等」即把 dirty 從「事件式」改為「**對基準比對式**」,與 RHF / React Query structural sharing 一致。

---

## 3. 叢集二-b:官方項目的「穩定身分」(選單打勾 + 操作/LLM 指名地基)

### 診斷
- 項目顯示 `code`(K01/O1.1.1…)是 [ocsDoc.ts:34 `renumberCoded`](../../apps/web/src/lib/ocsDoc.ts) 依**位置**重寫的序碼,**非穩定身分**。
- 選單「已勾選」判定用 **name** → 同任務內**同名不同項**會一起誤打勾;項目被編輯成自訂後也脫鉤。
- 穩定身分應為**來源 provenance**:`_ref.ocs_code + _ref.code`(官方原始碼)。
  - **K/S**:來源 catalog 有 `code` ✓。
  - **O/P**:**indexer 契約 DTO 本就有 code**([indexer-contract `CitableItem.code`](../../packages/indexer-contract/src/indexer_contract/models.py)、池切片 [task_detail.py:33](../../apps/api/app/services/knowledge/task_detail.py) 回 `{code,name}`/`{code,text}`),但被丟掉於 ① [ai.py `_catalog_op`](../../apps/api/app/api/routes/ai.py) 只取 name/text、② draft_op service 變純字串、③ 前端 [useTaskCatalog.ts:32](../../apps/web/src/hooks/useTaskCatalog.ts) 清成 `code:""`。**→ 不需改 indexer。**

### 決策(設計方向,細節待 plan)
- **D-2b-1 改 provenance 鍵比對**:`isOfficialSelected` 與相關比對改用 `_ref.ocs_code + _ref.code`,不用 name、不用位置序碼。顯示的位置碼不變。
- **D-2b-2 O/P code 接回**(api + 前端,**無 indexer 改動**):`_catalog_op`→draft_op→前端型別把 code 帶到 `_ref`(與 K/S 一致)。
- **連動**:此 provenance 鍵同時是 2a 操作式編輯與 LLM 提議的「指名依據」→ 2b 是 2a 的身分地基,非獨立小修。

---

## 4. 叢集三:低風險清理

- **D-3a 刪死代碼**:`AiTaskPanel.tsx`、`fields/FieldBoundSelect.tsx`(全 repo 無 import)。
- **D-3b 集中 QueryClient 預設**:把重複的 `staleTime`/`refetchOnWindowFocus` 收斂到 `new QueryClient({ defaultOptions })`;設**非零全域 staleTime** 避免掛載即重抓風暴;`document` 等要即時者 per-query 覆寫。

---

## 5. 建議階段(bite-size、各自可驗證、green-before==green-after、一 task 一 commit)

0. **叢集三**(清理打底,綠一版)。
1. **叢集一**(快取):後端批次端點 → 前端 seed → 合併 recommendKS → 持久化。
2. **叢集二-b**(身分):provenance 鍵 + O/P code 接回(2a 地基)。
3. **叢集二-a-minimal**(存檔):no-op 跳過 + version 409 守衛。
4. **(延後/選用)叢集二-a-full**:逐操作 PATCH + LLM 共編 seam。

> 各階段動到 api/web 共用契約處,依 `docs/contract-strategy.md` 選契約機制。
> 後續 ADR:①並發模型(樂觀並發,不上 CRDT/OT;含階段化)②後端批次 catalog 端點。

---

## 來源
- [TkDodo — Seeding the Query Cache](https://tkdodo.eu/blog/seeding-the-query-cache) · [Practical React Query](https://tkdodo.eu/blog/practical-react-query) · [React Query Render Optimizations](https://tkdodo.eu/blog/react-query-render-optimizations)
- [TanStack — persistQueryClient](https://tanstack.com/query/latest/docs/framework/react/plugins/persistQueryClient) · [createPersister](https://tanstack.com/query/latest/docs/framework/react/plugins/createPersister) · [Prefetching](https://tanstack.com/query/latest/docs/framework/react/guides/prefetching) · [Render Optimizations / structural sharing](https://tanstack.com/query/latest/docs/framework/react/guides/render-optimizations) · [Optimistic Updates](https://tanstack.com/query/latest/docs/framework/react/guides/optimistic-updates)
- [React Hook Form — formState `isDirty`](https://react-hook-form.com/docs/useform/formstate) · [issue #3562(toggling back 與 baseline)](https://github.com/react-hook-form/react-hook-form/issues/3562)
- [Ink & Switch — Local-first software(Kleppmann 等)](https://www.inkandswitch.com/essay/local-first/) · [Taskade — OT vs CRDT(AI agent 速度)](https://www.taskade.com/blog/ot-vs-crdt)
- [Optimistic Concurrency Control in HTTP(ETag/If-Match → 409/412)](https://medium.com/bestmile/optimistic-concurrency-control-in-http-services-c1bd911b89ad) · [HTTP 409 規範](https://http.dev/409)
