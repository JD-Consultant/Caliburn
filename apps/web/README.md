# web — Caliburn 前端(Next.js 16)

「著作」bounded context 的前端:職務說明書**工作台**(D27)。使用者在一張可編輯的官方
職能基準表格上「選職類 → 選任務 → 填格」,所有變更自動儲存為 draft,最後 finalize 產
正式版本。只跟 `apps/api`(:8001)講話;**不直接碰 indexer / DB**。

- 埠:`:3000`(api CORS 白名單只有 :3000/127.0.0.1:3000)。
- OCS 文件型別由 [`packages/ocs-contract`](../../packages/ocs-contract/) 生成的 TS 為底,
  web 疊 UI-only 欄位(契約 #3 Part A,ADR 0011)。

## 跑 / 測試

```bash
npm run dev            # :3000(或 monorepo 根 npx turbo dev)
npx tsc --noEmit       # 型別檢查(web 無單元測試,以 tsc + lint 為 gate)
npm run lint
```

後端需先起 api(:8001);知識查詢再需 indexer + embedder(見 [`docs/runbook.md`](../../docs/runbook.md))。

## Codemap

| 路徑 | 是什麼 |
|---|---|
| `src/app/` | 路由:`/`(→dashboard)、`/dashboard`(職務檔案清單)、`/documents/[id]`(**工作台**,主畫面)、`/documents/[id]/intake`(3 題小訪談,選用)、`/api/copilotkit`(AG-UI runtime 轉接到後端 `/copilotkit`) |
| `src/components/interview/` | 工作台元件:`JobDocTable`(主表格,dnd 排序)、`DocHeader`(官方表頭 5 欄)、`CellFillerPanel`(O/P/K/S 填格側欄)、`OccupationPicker`(選職類 modal)、`TaskCuratePanel`(選任務 modal + AI 預勾)、`ConflictDialog`(409 衝突二選一)、`DocNotes`、`fields/*`(FieldCombobox/OfficialMenu/FieldText/SourceLine 共用選單元件)、`InterruptHandlers`(LangGraph 訪談 HITL 面板;**目前無頁面掛載**,待訪談引擎重寫,ADR 0020) |
| `src/hooks/` | 資料層 hooks:`useDocument`(文件 + autosave + header-meta + task-candidates)、`useTaskCatalog`(批次 catalog + per-task 快取)、`useProfiles`、`useHydrated` |
| `src/lib/` | `api.ts`(唯一 fetch client,`/api/v1/*` + `ApiError`)、`ocsDoc.ts`(**純函式**文件編輯:clone→改→回傳 + 位置重編碼)、`headerMeta.ts`(候選池→選單 options)、`download.ts` |
| `src/store/user.ts` | zustand + persist:匿名 userId(localStorage `caliburn-user`;404 時自動重建) |
| `src/types/index.ts` | 契約型別(生成底 + UI 欄位)+ 各端點回應型別 |
| `src/components/layout/Providers.tsx` | QueryClient + **選擇性持久化** + CopilotKitProvider |

## 資料層:五個 query、兩種性質

| queryKey | 內容 | staleTime | 持久化 |
|---|---|---|---|
| `["document", id]` | of-record 信封 `{id, version, revision, status, content}` | 0 | **否(刻意)** |
| `["header-meta", id]` | 表頭候選池(職類/職業/行業/態度/notes,server 端已聯集去重+溯源) | 5min | **是** |
| `["task-candidates", id]` | 任務候選(依職類→職責分組) | 5min | 否 |
| `["task-catalogs", id]` | 批次每任務官方 K/S/O/P+level(ADR 0016) | 5min | **是** |
| `["task-catalog", id, taskKey]` | 單任務 catalog(由批次 seed;cache miss 才 fallback 打 `/ai/*`) | 5min | 否 |

**核心不變量:document 是「可寫的工作狀態」,其餘全是「唯讀參考池」。** 這條線決定一切:
誰能持久化(只有唯讀池)、誰走 invalidate 重抓、誰的 cache 允許本地先寫。

## 關鍵流程

### 1. 編輯 → 自動儲存(主線)

```
UI 編輯(表格/填格/拖拉)
→ ocsDoc.ts 純函式:structuredClone → 改 → 依位置重編碼(T1.1/O1.1.1/K01…,身分由 _id 維持)
→ commit(next):
   a. setQueryData(["document"]) 立刻寫 cache(畫面即時,樂觀、純本地)
   b. no-op skip:與 baseline 逐位元相同 → 取消排程、不打網路
   c. 否則 debounce 500ms → PATCH /document?expect_version=&expect_revision=(2a 樂觀鎖)
→ 成功:baseline = 「送出的 content」+ 新 token(不能用 cache——PATCH 飛行中可能又打了字)
→ 409:ConflictDialog 強制二選一(載入最新版 / 以我的版本覆蓋),不回滾本地編輯
```

baseline = 最後已知 server 狀態快照,是 dirty 判定 / no-op skip / 樂觀鎖 token 的唯一依據。
細節與反例(漏存 bug)見 [2a spec §6.3](../../docs/specs/2026-07-02-2a-minimal-save-concurrency-spec.md)。

### 2. 選職類

`OccupationPicker` → `GET /occupations?q=`(根層目錄搜尋)→ 勾選(順序=優先度)→
`PUT /job-profiles/{id}/occupations` → invalidate **document + task-candidates + header-meta**
(server 已把表頭刷成第一順位官方基準,三個池全部重抓)。

### 3. 選任務

`TaskCuratePanel` → `GET task-candidates` →(有自述時 `POST /ai/extract-tasks` AI 預勾、
`POST /ai/structure-task` 補自訂)→ `POST document:buildTasks`(加法:已在文件的任務依
provenance 跳過)→ setQueryData(document) + invalidate profiles。

### 4. 填格(O/P/K/S)

點格 → `CellFillerPanel` → `useTaskCatalog(taskKey)` 讀 per-task 快取(文件載入後
`useTaskCatalogs` 已批次抓好並 seed,開面板 0 等待)→ 勾官方(帶 `_ref` 溯源)/加自訂 →
`setKS`/`setOp` → commit(回到流程 1)。

### 5. 重載還原(持久化)

`PersistQueryClientProvider`(localStorage `caliburn-rq-cache`,buster `ocs-v4-1`,maxAge 24h)
只還原標了 `meta.persist === true` 的 query(= header-meta、task-catalogs)。task-catalogs 還原後
由 effect 重新 seed 各 `["task-catalog", id, taskKey]`。document 永遠重新 GET(of-record 即時)。

## 不變量(從代碼讀不出來的規則)

- **document 的 React Query cache 就是編輯器狀態**(cache-as-state):UI 讀 cache 的
  `envelope.content`,不另設 local state;`useAutosaveDocument` 依賴同頁掛著的 `useDocument`
  訂閱來驅動重繪。
- **document 刻意不持久化**:localStorage 還原舊文件會蓋掉 server 真相。
- **代碼是位置、身分是 `_id`**:O/P/K/S/態度的 `code` 隨陣列位置重編(`renumberCoded`),
  來源/自訂判定看 `_id`/`_src`/`_ref`,不看 code。
- **UI-only 欄位一律 `_` 前綴**(`_id/_uid/_tid/_src/_ref/_notes/_levelSrc`):draft 會存進 DB,
  但 finalize/export 在後端 `_strip_underscore` 全剝,正式 OCS JSON 契約純淨。
- **官方項改了內容就變自訂**:編輯官方帶入項 → `_src="custom"`、`_ref` 清空(選單勾選判定
  採 DDD 實體/值物件:有來源 code 比 provenance,無 code 比 name)。
- 兩把 localStorage 鑰匙:`caliburn-rq-cache`(React Query)、`caliburn-user`(zustand userId)。

## API 消費面(全部經 `lib/api.ts` → `/api/v1`)

文件:`GET/PATCH …/document`、`POST …/document:finalize`、`POST …/document:buildTasks`、
`GET …/document/export`。池:`GET …/header-meta`、`GET …/task-candidates`、`GET …/task-catalogs`。
職類:`GET /occupations?q=`、`PUT …/occupations`。AI 提議(只提議不寫 DB):`POST /ai/recommend-ks`、
`/ai/draft-op`、`/ai/extract-tasks`、`/ai/structure-task`。CRUD:`/users`、`/job-profiles`。
端點語意與錯誤碼見 [`apps/api/README.md`](../api/README.md)。

## 指路

ADR [0011](../../docs/adr/0011-web-ocs-types-generated.md)(契約 #3)·
[0015](../../docs/adr/0015-document-save-optimistic-concurrency.md)(樂觀並發)·
[0016](../../docs/adr/0016-batch-task-catalog-endpoint.md)(批次 catalog)·
[0019](../../docs/adr/0019-api-naming-alignment.md)(命名)·
[0020](../../docs/adr/0020-interview-authoring-interaction-model.md)(訪談互動模式)·
specs:[web 資料層優化](../../docs/specs/2026-06-30-web-data-layer-optimization-research.md)、
[2a 存檔並發](../../docs/specs/2026-07-02-2a-minimal-save-concurrency-spec.md)。
