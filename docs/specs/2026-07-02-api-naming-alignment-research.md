# API 命名對齊 — 研究(F3 / F4 / F7 / F5 落實前置)

> **類型**:研究紀錄(來源 + 診斷 + 選項 + 比對)。落實各自另開 ADR / plan。
> **日期**:2026-07-02
> **動機**:API review findings 的 **F3(indexer 自訂方法 camelCase)、F4(後端 noun/verb 混用)、
> F7(ksa-pool/task-catalogs 命名重疊)、F5(POST occupations 應 PUT)** 要落實。維護者授權命名調整,
> 但要求**先研究權威、只用可靠來源**。本輪**只研究、未改碼**。
> **原則**:對齊規範/大廠(Google AIP、Microsoft/Zalando、monorepo 慣例);命名細節承接
> [`2026-06-30-api-review-findings.md`](2026-06-30-api-review-findings.md) §F3/F4 的權威比對。

---

## 1. Grounding:破壞面比 findings 標的小很多(關鍵反轉)

實地追契約鏈後,發現 F3 的「破壞性」被高估:

| 端點 | 誰消費 | 依據 | 改名破壞面 |
|---|---|---|---|
| `/tasks/batchGet` | **沒人**(producer-only) | ADR 0010 §後果、contract-2 研究「not currently called by api」 | **僅 indexer**(routes + 自身測試) |
| `/tasks/findSimilar` | **沒人**(producer-only) | 同上 | **僅 indexer** |
| `/tasks/search` | `HttpIndexerClient.search_tasks`(1 字串) | [knowledge_http.py:29](../../apps/api/app/adapters/knowledge_http.py) | indexer routes + api client 1 行 |
| `/occupations/search` | `HttpIndexerClient.search_occupations`(1 字串) | [knowledge_http.py:24](../../apps/api/app/adapters/knowledge_http.py) | indexer routes + api client 1 行 |

**兩個要點**:
1. **`indexer-contract` 共用的是 pydantic model,不是 path**(ADR 0010:shared package、非 codegen/Pact)。
   → **改路徑不需動契約套件、不需版本 bump**;path 只存在於 indexer `routes.py` + `HttpIndexerClient` 字串。
2. **web 不直接打 indexer**(web → api → indexer)。web 對 api 的呼叫**全集中在
   [`apps/web/src/lib/api.ts`](../../apps/web/src/lib/api.ts) 一個檔**(string 字面值)。
   → F4/F5(後端端點改名)的 web 破壞面 = 這一檔的幾個字串。

**結論**:F3 幾乎是 indexer 內部整理(+ api client 2 行);F4/F5 動 api routes + `api.ts` 一檔。**無跨 repo、無契約版本問題。**

## 2. 技術驗證:FastAPI 支援 `:verb`(AIP 方案的命門)

**本機實測**(最權威):FastAPI/Starlette 對路徑中的**字面冒號**正常路由——
`POST /tasks:search`、`POST /tasks:batchGet` 皆 200,且與 `GET /occupations/{code}`(path param)**共存不衝突**。
→ Google AIP-136 的 `:verb` 慣例在本專案**技術可行**,不必退而求其次用 kebab 子資源。

## 3. 命名慣例(權威,承接前份 findings)

- **Google AIP-136(自訂方法)/ AIP-231(BatchGet)**:自訂/批次方法 URI 用 **`:verb`**(冒號標示「對集合的操作」而非子資源);優先標準方法,custom 僅在無法乾淨對映時。
- **Microsoft / Zalando REST guidelines**:URL path 一律 **kebab-case**(camelCase 只用於 JSON 欄位)。
- 現況 `/tasks/batchGet`、`/tasks/findSimilar` 的 **slash + camelCase** 同時違反上述兩者(既非 `:verb`、path 段又 camelCase)。

## 4. 遷移策略(權威):monorepo 原子改名,不版本化

**所有消費者都在同一 monorepo**(indexer / api / web),故破壞性改名用 **atomic commit**——
「改 API + 同 commit 更新所有 caller」,**不需 API 版本化/棄用窗**(能輕易 grep 出全部 caller)。
必要時可拆成「先雙支援 → 逐一切換 → 移除舊」的漸進式,但本專案 caller 數 = 個位數,單一原子提交即可。

- 來源:[Snellman《A monorepo misconception — atomic cross-project commits》](https://www.snellman.net/blog/archive/2021-07-21-monorepo-atomic/);Google monorepo / trunk-based 慣例(zero version skew between internal libs)。

## 5. 逐項提案 + 破壞面

| # | 現況 | 提案 | 破壞面 | 風險 |
|---|---|---|---|---|
| **F3a** | `/tasks/search`、`/occupations/search` | `/tasks:search`、`/occupations:search`(AIP `:verb`) | indexer routes + api client 2 行 + 兩邊測試 | 低 |
| **F3b** | `/tasks/batchGet`、`/tasks/findSimilar` | `/tasks:batchGet`、`/tasks:findSimilar` | **僅 indexer**(routes + 測試) | 極低 |
| **F4a** | `POST …/document/finalize` | `POST …/document:finalize`(AIP 自訂方法) | api routes + `api.ts` 1 行 + 測試 | 低 |
| **F4b** | `GET …/ocs-search?q=` | `GET …/occupations:search?q=` 或標準 `GET …/occupations?q=` | api routes + `api.ts` 1 行 + 測試 | 低 |
| **F4c** | `POST …/build-tasks` | 保留(明確動作)或 `…/document:buildTasks` | api routes + `api.ts` 1 行 | 低,傾向**保留** |
| **F4d** | `ai/*`(全動詞) | **保留**(提議型 RPC),docstring 標明刻意 action-style | 無 | 無 |
| **F5** | `POST …/occupations`(整批取代、冪等) | `PUT …/occupations` | api routes + `api.ts` 1 行 + 測試 | 低 |
| **F7** | `ksa-pool`(已刪)vs `task-catalogs` | ksa-pool REST 端點 F8 已刪 → **F7 大半自動消解**;`task-catalogs`(逐任務)命名已達意 | — | 無(記錄即可) |

## 6. 建議(待維護者拍板)

- **採 Google AIP `:verb`**(技術已驗證可行)統一 F3a/F3b/F4a/F4b 的自訂方法;path 一律 kebab(現多已符合)。
- **F4b** 傾向標準 `GET …/occupations?q=`(List+filter,可快取、冪等)勝過 `:search`——入參簡單。**待決**。
- **F4c build-tasks 保留**、**F4d ai/* 保留**(action-style,docstring 標明)。
- **F5 改 PUT**(冪等整批取代)。
- **F7 無行動**(ksa-pool 已刪,重疊自解),僅在 ADR/README 記一句關係。
- **遷移**:單一 ADR「API 命名對齊」+ 逐端點 atomic commit(indexer 一組、api+web 一組),green-before==green-after;**不版本化**。
- **待決策**:①F4b 走 `?q=` 標準 List 還是 `:search`;②producer-only 的 F3b 要不要順手一起改(改動極小、但動到目前沒人用的端點——一致性 vs YAGNI)。

## 7. 追加研究(第二輪:F4b 根層設計細節 + 動詞/偏離查核)

> 維護者拍板 F4b 走**根層 `GET /occupations?q=`**後,對設計細節再抓規範原文查核(AIP-132/136/231、Zalando 原文)。

### 8.1 為什麼不能是 `GET …/job-profiles/{id}/occupations?q=`(重要修正)

F5 之後 `PUT …/occupations` = 「**此檔案已選職類**」(整批取代)。HTTP 語意(RFC 9110)同一 URI 的 GET/PUT 必須指**同一資源**;但搜尋搜的是**全域 OCS 目錄**,不是已選清單 → 同 URI 兩義,比現況更糟。且 `ocs_search` 實際只拿 profile 做存在檢查、搜的是全域知識庫——呼應 ARCHITECTURE「多租戶隔離只在 api;**知識服務全域共享**」→ 全域集合就該是**根層集合**。

### 8.2 規範查核(原文)

| 規範 | 原文要點 | 對我們的意義 |
|---|---|---|
| **AIP-132(List)** | verb **must** GET;回應 repeated 欄位 = **複數資源名**;`page_size`/`page_token` **must** | `GET /occupations?q=` ✓;回應欄位應 `occupations`(非 `hits`);**分頁我們刻意偏離**(bounded 目錄、去重 ≤8 hits、F6 YAGNI)→ 記錄 |
| **Zalando #137/#129/#141** | **`q` 是官方慣例查詢參數**;path kebab;URL verb-free | 參數名 `q` 有規範背書;根層 List+filter 正中 Zalando 風格 |
| **AIP-136(custom)** | 取數 **must** GET,**但 payload 超 URL 限制可 POST**;有副作用 must POST;`:verb` 冒號 | indexer `:search`(POST body,向量查詢)有例外背書;`document:finalize`/`:buildTasks`(mutation)POST ✓ |
| **AIP-231(BatchGet)** | verb **must** GET、ids 走 query param、**must 全成全敗(原子)**、保序 | 我們的 `batchGet` = POST body `{ids}` + **缺失靜默略過** → **三處刻意偏離**(ids 長/多 = 136 的 URL 限制例外;drop-missing 是 producer 需求)。改名 `:batchGet` 不改行為,**偏離寫進 ADR** |

### 8.3 細節定案(提案)

- 新 router `app/api/routes/occupations.py`(`GET /api/v1/occupations?q=`);`get_knowledge` 依賴從 documents.py 搬到共用 `app/api/deps.py`(fastapi-best-practices 的 dependencies 模組慣例);舊 `…/ocs-search` **原子刪除**(§4)。
- **回應欄位 `hits` → `occupations`**(AIP-132 複數資源名)——既已破壞路徑,一次到位;web 影響 3 行(api.ts + OccupationPicker + 型別欄位)。**待維護者確認**。
- **F4c 修正提案**:`build-tasks` → `document:buildTasks`——它與 finalize 同為 document 上的 custom method,只改一個是半套;成本相同(1 字串)。**待維護者確認**(推翻 §5 的「傾向保留」)。
- 空 `q` → 回空陣列(維持現行為;indexer 無 list-all 能力,此端點實為 search-only collection,記錄於 docstring)。
- 多租戶備註:根層端點無 profile 檢查——知識全域共享;未來登入落地時只需 authn、不需 tenant scoping(ARCHITECTURE 一致)。

## 8. 來源(全權威:規範 / 大廠 / 官方 / 本機實證)

- **命名**:[Google AIP-132 List](https://google.aip.dev/132) · [AIP-136 自訂方法](https://google.aip.dev/136) · [AIP-231 BatchGet](https://google.aip.dev/231) · [Microsoft Azure REST Guidelines](https://github.com/microsoft/api-guidelines/blob/vNext/azure/Guidelines.md) · [Zalando RESTful API Guidelines](https://opensource.zalando.com/restful-api-guidelines/)(#137 `q` 慣例參數、#129 kebab、#141 verb-free URL;§7 皆為原文查核)
- **HTTP 語意**(同 URI 同資源、PUT 冪等):RFC 9110(HTTP Semantics)
- **遷移**:[Snellman — monorepo atomic cross-project commits](https://www.snellman.net/blog/archive/2021-07-21-monorepo-atomic/)(Google monorepo / trunk-based 慣例)
- **技術可行性**:FastAPI/Starlette 字面冒號路由——**本機 TestClient 實測**(§2)
- **REST 方法語意**(F5 PUT):冪等整體取代用 PUT(HTTP 語意 / MDN / RFC 9110)
- 命名比對細節:本 repo [`2026-06-30-api-review-findings.md`](2026-06-30-api-review-findings.md) §F3/F4
