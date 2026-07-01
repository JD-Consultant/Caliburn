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

## 7. 來源(全權威:規範 / 大廠 / 官方 / 本機實證)

- **命名**:[Google AIP-136 自訂方法](https://google.aip.dev/136) · [AIP-231 BatchGet](https://google.aip.dev/231) · [Microsoft Azure REST Guidelines](https://github.com/microsoft/api-guidelines/blob/vNext/azure/Guidelines.md) · [Zalando RESTful API Guidelines](https://opensource.zalando.com/restful-api-guidelines/)
- **遷移**:[Snellman — monorepo atomic cross-project commits](https://www.snellman.net/blog/archive/2021-07-21-monorepo-atomic/)(Google monorepo / trunk-based 慣例)
- **技術可行性**:FastAPI/Starlette 字面冒號路由——**本機 TestClient 實測**(§2)
- **REST 方法語意**(F5 PUT):冪等整體取代用 PUT(HTTP 語意 / MDN / RFC 9110)
- 命名比對細節:本 repo [`2026-06-30-api-review-findings.md`](2026-06-30-api-review-findings.md) §F3/F4
