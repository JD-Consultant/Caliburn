# web — Caliburn 前端(Next.js 16)

現行 greenfield 本機產品入口是 `/workspace`：不登入，直接讀寫
`/api/v1/job-analysis/*`，可建立、改名並重新開啟多份彼此隔離的本機職務說明書；畫面任一時間只開一份。
這條線使用 `@caliburn/job-analysis-contract` 生成型別與獨立 `jobAnalysisApi.ts`，不接舊
user/profile/OCS 狀態。舊 `/dashboard` 與 `/documents/*` 暫留作歷史開發面，不是新路徑的依賴。
Greenfield Task 編輯採「編輯 → 明確儲存／取消」；沒有 debounce autosave。下方 autosave 說明只描述舊 OCS 工作台。
`/workspace/[document_id]` 同頁顯示可恢復的 AI 顧問訪談、待確認 Proposal 與 Current JD；
AI 只能提出文件變更，員工接受／修改後接受才會更新 Current JD。人工 Task 編輯仍走同一組
`/api/v1/job-analysis` application seam，沒有第二份前端 store、舊 AI 整合或舊資料雙寫。Current JD
同頁另按 Task 顯示 O/P/K/S，態度與未連結 K/S 留在文件層；員工可明確儲存，或要求 AI 先產生
逐項可接受／修改／拒絕／稍後處理的 OPKS Proposal。

「著作」bounded context 的前端:職務說明書**工作台**(D27)。使用者在一張可編輯的官方
職能基準表格上「選職類 → 選任務 → 填格」,所有變更自動儲存為 draft,最後 finalize 產
正式版本。只跟 `apps/api`(:8001)講話;**不直接碰 indexer / DB**。

- 埠:`:3000`(api CORS 白名單只有 :3000/127.0.0.1:3000)。
- OCS 文件型別由 [`packages/ocs-contract`](../../packages/ocs-contract/) 生成的 TS 為底,
  web 疊 UI-only 欄位(契約 #3 Part A,ADR 0011)。

## 跑 / 測試

```bash
npm run dev            # :3000(或 monorepo 根 npx turbo dev)
npm run test           # vitest；含 greenfield workspace/API client/Task editor 元件行為
npx tsc --noEmit       # 型別檢查
npm run lint
```

後端需先起 api(:8001);知識查詢再需 indexer + embedder(見 [`docs/runbook.md`](../../docs/runbook.md))。

## Codemap

| 路徑 | 是什麼 |
|---|---|
| `src/app/` | 路由:`/`(→workspace)；舊 `/dashboard`、`/documents/[id]`、intake／interview 暫留但不被新入口依賴 |
| `src/app/workspace/` | greenfield 本機工作區；Server Component shell + 小型 Client Components，不使用 Server Action 寫資料；顧問訪談、Proposal 與可直接編輯的 Current JD 同頁 |
| `src/lib/jobAnalysisApi.ts` | 新 `/job-analysis` 唯一 fetch client；含 Consultation／Proposal 決策；Problem Details 只依 stable `type` 顯示，不解析 `detail` |
| `src/components/interview/` | 工作台元件:`JobDocTable`(主表格,dnd 排序;**T8 `_pending` 四態渲染+✓✗?+批量工具列**)、`PendingMark`(追蹤修訂 UI:綠字/紅刪除線+出處卡;ADR 0030)、`AgendaList`(議程三態)、`DocHeader`(官方表頭)、`OccupationPicker`、`UnitPickerMenu`、`TaskPickerMenu`、`GlobalTaskPickerMenu`、`ConflictDialog`、`DocNotes`、`fields/*`(FieldCombobox/OfficialMenu/FieldText/SourceLine)、`InterviewPanel`(**AI 訪談側欄**:打字機對話+議程+收尾卡;ADR 0030) |
| `src/hooks/` | 資料層 hooks:`useDocument`(文件 + autosave + 選職類)、`useKnowledge`(知識包 query,ADR 0021)、`useInterview`(start/turn/finish/view;turn 後 invalidate document→外部變化路徑重設 baseline)、`useProfiles`、`useHydrated` |
| `src/lib/` | `api.ts`(唯一 fetch client,`/api/v1/*` + `ApiError`)、`ocsDoc.ts`(**純函式**文件編輯:clone→改→回傳 + 位置重編碼 + A4 文件級 K/S 重編 + **`_pending` 四態輔助 accept/reject/listPending**;ADR 0030)、`pack.ts`(知識包→選單選項純函式;ADR 0021/0022)、`interviewUi.ts`(側欄純邏輯:議程/chips/打字機)、`slots.ts`(槽標籤)、`urn.ts`、`download.ts` |
| `src/store/user.ts` | zustand + persist:匿名 userId(localStorage `caliburn-user`;404 時自動重建) |
| `src/types/index.ts` | 契約型別(生成底 + UI 欄位)+ 各端點回應型別 |
| `src/components/layout/Providers.tsx` | QueryClient + **選擇性持久化**(CopilotKitProvider 已退場,T12) |

## 資料層:兩個 query、兩種性質(P3 收斂,ADR 0021)

| queryKey | 內容 | staleTime | 持久化 |
|---|---|---|---|
| `["document", id]` | of-record 信封 `{id, version, revision, status, content}` | 0 | **否(刻意)** |
| `["knowledge", id]` | **知識包**(occupation_details+12 池+source_tasks,每官方值帶 srcs)——**所有選單的唯一資料源**(表頭/態度/NOTE/選任務/填格/級別);選職類後背景預載 | 24h | **是** |

(另有 `["profiles"]`/`["profile", id]` CRUD 清單。header-meta/task-candidates/task-catalogs
三個池 query 已隨 pack 切換退役——P3。)

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

`OccupationPicker`(modal)或**訪談建議卡** `OccupationSuggestCard`(0031:顧問提議
→卡片進對話流,預勾+理由,一鍵加入;✕=`occupation_dismissed` 記帳)→
`PUT /job-profiles/{id}/occupations`(0029:只寫 profile 參考集合,**不動文件表頭**;
主基準由職類視窗 PATCH)→ invalidate **document + knowledge** + 背景 prefetch 新知識包
(表頭/態度/NOTE/選任務/填格選單全部吃這一包,選參考=唯一同步點)。參考集合空時
訪談面板頂常駐「📌 待選」chip 重入口。

### 3. 選職責 → 選任務(表格中心,遞迴選單)

工具列「**選職責 ▾**」(`UnitPickerMenu`,職責大池:序號+引用行)→ 勾=**空職責立即入表格**
(`addFromPool`;再點取消=移除空職責,含任務鎖定表格刪;「自動勾選」補主基準職責)→
每職責列「**選任務 ▾**」(`TaskPickerMenu`,任務**全池**不過濾:自己的預勾、其餘可勾=借用,
已在他職責標「已加入」;空職責首開自動帶官方任務;取消勾選=移除空任務,已填鎖定)→
每一勾=**前端文件編輯**(`addTasksToUnit`,任務帶 provenance+`_refs` 多來源)→ commit
(回到流程 1 的 autosave PATCH)。**盤永遠人開**(ADR 0032):AI 不彈窗、不預勾——
訪談 intake 邀請卡「開任務盤」一鍵開全域盤(受控 open),婉拒=`task_board_dismissed` 記帳。

### 4. 填格(O/P/K/S)

點格 → `CellFillerPanel` → 讀**知識包大池**(`useKnowledge`;選單=全池可跨職類借用,
序號顯示+每列引用行)→ 空格首開自動帶入該任務官方配套(source_tasks 的 o/p/k/s_refs 聯集;
「自動勾選」鈕重套)→ 勾官方(帶 `_ref` 溯源,own-first:引用對到本任務)/加自訂 →
`setKS`/`setOp` → commit(回到流程 1)。任務級別下拉同源(官方值帶引用,選中存 `_levelSrc`)。

### 5. 重載還原(持久化)

`PersistQueryClientProvider`(localStorage `caliburn-rq-cache`,buster `ocs-v4-3`,maxAge 24h)
只還原標了 `meta.persist === true` 的 query(= knowledge)。document 永遠重新 GET(of-record 即時)。

## 不變量(從代碼讀不出來的規則)

- **document 的 React Query cache 就是編輯器狀態**(cache-as-state):UI 讀 cache 的
  `envelope.content`,不另設 local state;`useAutosaveDocument` 依賴同頁掛著的 `useDocument`
  訂閱來驅動重繪。
- **document 刻意不持久化**:localStorage 還原舊文件會蓋掉 server 真相。
- **代碼是位置、身分是 `_id`**:O/P/態度的 `code` 隨陣列位置重編(`renumberCoded`),
  來源/自訂判定看 `_id`/`_src`/`_ref`,不看 code。
- **K/S 碼是文件層級**(A4,ocs-schema):name 為 key、首現給號、**同名共碼**(跨任務共用
  同一代碼);任何 K/S 內容或結構變動都全文件重編(`renumberDocKS`)。碼共用、身分各自。
- **UI-only 欄位一律 `_` 前綴**(`_id/_uid/_tid/_src/_ref/_notes/_levelSrc` + `notes._prerequisites/_supplements`):
  draft 會存進 DB,但 finalize/export 在後端 `_strip_underscore` 全剝,正式 OCS JSON 契約純淨。
- **notes 影子列是唯一真相**(spec 2026-07-04 §3):`notes._<field>` 存 `{code,text,_id,_src,_ref}`,
  契約欄 `string[]` 由 `renumber()` 導出;來源 n 碼(`_ref.code`)由 api build_pack 蓋在池 srcs。
- **改名=斷鏈變自訂**(spec §5):職責/任務改名清官方綁定 → 標「自訂」、選單取消勾選;
  自動勾選統一「首開且空→套主基準來源」(任務層維持 own refs 規則)。
- **官方項改了內容就變自訂**:編輯官方帶入項 → `_src="custom"`、`_ref` 清空(選單勾選判定
  採 DDD 實體/值物件:有來源 code 比 provenance,無 code 比 name)。
- 兩把 localStorage 鑰匙:`caliburn-rq-cache`(React Query)、`caliburn-user`(zustand userId)。

## API 消費面(全部經 `lib/api.ts` → `/api/v1`)

文件:`GET/PATCH …/document`、`POST …/document:finalize`、`GET …/document/export`。
知識:`GET …/knowledge`(唯一池端點,ADR 0021)。職類:`GET /occupations?q=`、`PUT …/occupations`。
AI 提議(只提議不寫 DB):`POST /ai/extract-tasks`、`/ai/structure-task`(recommend-ks/draft-op
server 端仍在,web 已不呼叫)。CRUD:`/users`、`/job-profiles`。
端點語意與錯誤碼見 [`apps/api/README.md`](../api/README.md)。

## 指路

**內部深文檔:[`docs/data-layer.md`](docs/data-layer.md)**(cache-as-state + autosave 狀態機)· 編輯器端到端
[`docs/design/editor-knowledge-pack.md`](../../docs/design/editor-knowledge-pack.md)。

ADR [0011](../../docs/adr/0011-web-ocs-types-generated.md)(契約 #3)·
[0015](../../docs/adr/0015-document-save-optimistic-concurrency.md)(樂觀並發)·
[0016](../../docs/adr/0016-batch-task-catalog-endpoint.md)(批次 catalog)·
[0019](../../docs/adr/0019-api-naming-alignment.md)(命名)·
[0020](../../docs/adr/0020-interview-authoring-interaction-model.md)(訪談互動模式)·
specs:[web 資料層優化](../../docs/specs/2026-06-30-web-data-layer-optimization-research.md)、
[2a 存檔並發](../../docs/specs/2026-07-02-2a-minimal-save-concurrency-spec.md)。
