# ADR 0019 — API 命名對齊:AIP `:verb` + 根層 occupations 搜尋 + PUT occupations

- **狀態**:Accepted（2026-07-02）。
- 研究依據:[`../specs/2026-07-02-api-naming-alignment-research.md`](../specs/2026-07-02-api-naming-alignment-research.md)(§1 破壞面實查、§2 冒號路由實證、§4 monorepo 原子遷移、§7 規範原文查核)。
- 關聯:API review findings F3/F4/F5/F7([`../specs/2026-06-30-api-review-findings.md`](../specs/2026-06-30-api-review-findings.md))。

## 脈絡

- **indexer** 自訂方法用 slash+camelCase(`/tasks/batchGet`、`/tasks/findSimilar`、`/tasks/search`、`/occupations/search`),同時違反 Google AIP-136(自訂方法應 `:verb`)與 Microsoft/Zalando(path 段 kebab-case);slash 讓動作看起來像子資源。
- **後端** documents router 混名詞資源與動作路徑(`document/finalize`、`build-tasks`、`ocs-search`);`ocs-search` 實際搜**全域 OCS 目錄**(知識全域共享,ARCHITECTURE)卻掛在 profile 底下——F5 改 `PUT …/occupations`(此檔已選職類)後,同 URI 基底掛搜尋會違反「同 URI 同資源」(RFC 9110)。
- `POST …/occupations` 語意是冪等整批取代 → 應為 PUT。
- **破壞面實查**(研究 §1):`batchGet`/`findSimilar` **producer-only 無消費者**;`indexer-contract` 共用 **model 非 path**(改路徑不需版本 bump);web 對 api 的呼叫集中在 `lib/api.ts` 一檔 → 全部 caller 在 monorepo 內,可**原子改名、不需 API 版本化/棄用窗**。
- FastAPI 字面冒號路由**本機實證可行**(與 `{code}` path param 共存)。

## 決定

| # | 之前 | 之後 |
|---|---|---|
| F3a | `POST /occupations/search` · `POST /tasks/search`(indexer) | `POST /occupations:search` · `POST /tasks:search` |
| F3b | `POST /tasks/batchGet` · `POST /tasks/findSimilar`(indexer,producer-only) | `POST /tasks:batchGet` · `POST /tasks:findSimilar` |
| F4a | `POST …/document/finalize` | `POST …/document:finalize` |
| F4c | `POST …/build-tasks` | `POST …/document:buildTasks`(與 finalize 同為 document 的 custom method,一致化) |
| F4b | `GET …/job-profiles/{id}/ocs-search?q=` 回 `{hits}` | **根層** `GET /api/v1/occupations?q=` 回 `{occupations}`(AIP-132 List+filter;`q` = Zalando #137 慣例參數;全域集合不再借位 profile) |
| F5 | `POST …/occupations` | `PUT …/occupations`(冪等整批取代,RFC 9110) |
| F4d | `ai/*` 全動詞 | **保留**(提議型 stateless RPC,docstring 標明刻意 action-style) |
| F7 | `ksa-pool` vs `task-catalogs` 命名重疊 | ksa-pool REST 端點已刪(F8)→ **自動消解**,僅記錄 |

**實作**:新 `app/api/routes/occupations.py`;`get_knowledge` 依賴搬共用 `app/api/deps.py`;舊 `ocs-search` 刪除。
**遷移**:monorepo **原子 commit**(indexer 路徑 + api client 字串同 commit;api 路徑 + web `api.ts` 同 commit),不做版本化/雙支援期——全部 caller 可 grep 且個位數。

**刻意偏離(白紙黑字,非遺漏)**:
- `:batchGet` 維持 **POST body `{ids}` + 缺失靜默略過**——偏離 AIP-231(must GET、query param、原子全成全敗);理由:ids(URN)長且可多(AIP-136「payload 超 URL 限制可 POST」例外),drop-missing 是 producer 去重流程需求。改名不改行為。
- 根層 List **不分頁**——偏離 AIP-132(page_size/token must);理由:目錄有界、去重後 ≤8 筆(F6 YAGNI,規模成長再加)。
- 空 `q` 回空陣列——indexer 無 list-all 能力,此端點實為 search-only collection。

## 後果

- ✅ 三層命名風格一致:自訂方法一律 `:verb`、path 段 kebab、全域集合在根層。
- ✅ `PUT/GET …/occupations` 撞衫問題在設計期就避開;全域知識搜尋不再假借 profile 授權位。
- ✅ 無契約套件版本問題(model 不動,只動路徑字串)。
- ⚠️ 破壞性(內部):所有 caller 同 commit 更新;green-before==green-after 為安全網。
- ⚠️ 根層端點無 profile 檢查——知識全域共享(ARCHITECTURE);未來 auth 落地時 authn 即可、不需 tenant scoping。
