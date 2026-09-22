# Plan — API 命名對齊(F3/F4/F5;AIP `:verb` + 根層 occupations + PUT)

- 依據:[ADR 0019](../adr/0019-api-naming-alignment.md) · 研究 [`../specs/2026-07-02-api-naming-alignment-research.md`](../specs/2026-07-02-api-naming-alignment-research.md)。
- 原則:**monorepo 原子改名**(producer + 全部 caller 同 commit)、不版本化;green-before==green-after;一 task 一 commit。
- Baseline:api `uv run pytest` = 148 passed;indexer `uv run --all-extras pytest`(執行時記錄數字);web `npx tsc --noEmit` clean。

## Task 1 — indexer 四路徑 → `:verb`(+ api client 兩字串,原子)

**改 indexer** `src/jd_ocs_indexer/api/routes.py`:
- `/occupations/search` → `/occupations:search` · `/tasks/search` → `/tasks:search`
- `/tasks/batchGet` → `/tasks:batchGet` · `/tasks/findSimilar` → `/tasks:findSimilar`
- 動詞(POST)與 request/response model 不變(ADR 0019 偏離節)。

**改 api** `app/adapters/knowledge_http.py`:
- `post("/occupations/search", …)` → `post("/occupations:search", …)`
- `post("/tasks/search", …)` → `post("/tasks:search", …)`

**測試**:grep 兩 repo 測試中的舊路徑字串一併改(indexer route 測試、api 若有 mock path)。
**驗收**:indexer `uv run --all-extras pytest` 綠;api `uv run pytest` 綠(148)。
**commit**:`refactor(indexer,api): custom methods use AIP :verb paths — :search/:batchGet/:findSimilar [F3, ADR 0019]`

## Task 2 — api 端點改名 + 根層 occupations + PUT(+ web,原子)

**改 api** `app/api/routes/documents.py` + 新檔:
1. 新 `app/api/deps.py`:`get_knowledge` 從 documents.py **搬過去**(move-only),documents.py 改 import。
2. 新 `app/api/routes/occupations.py`:`GET /occupations?q=` → 回 `{"occupations":[{ocs_code, ocs_name}]}`(邏輯 = 原 ocs_search:strip→search_occupations(top_k=8)→依 ocs_code 去重保序;**critical** 502 政策不變;空 q 回空;docstring 記 search-only + 不分頁 YAGNI)。掛進 `app/api/router.py`。
3. 刪 documents.py 的 `ocs_search`。
4. `POST …/document/finalize` → `POST …/document:finalize`。
5. `POST …/build-tasks` → `POST …/document:buildTasks`。
6. `POST …/occupations` → `PUT …/occupations`(set_occupations 本就冪等整批取代)。

**改 web** `src/lib/api.ts`(+ 型別/元件):
- `getOcsSearch`:URL → `/occupations?q=`、不再帶 profileId;回應型別 `{occupations: OcsSearchHit[]}`。
- `OccupationPicker.tsx`:`r.hits` → `r.occupations`(呼叫端簽名同步)。
- finalize / buildTasks / setOccupations(PUT)三個 URL/method 字串。

**測試**:
- api:`test_documents_api.py` 路徑字串更新;ocs-search 三條測試搬成 `test_occupations_api.py`(路徑/欄位新);`test_app_wiring.py` 補 `/api/v1/occupations` 斷言。
- web:`npx tsc --noEmit` + `npm run lint`。
**驗收**:api 綠(148±,搬測試不減蓋);tsc/lint 綠。
**commit**:`refactor(api,web): document:finalize/:buildTasks, root GET /occupations?q= (hits→occupations), PUT occupations [F4/F5, ADR 0019]`

## Task 3 — living docs 同步

- `apps/ocs-indexer/README.md`:端點表 + curl 範例(4 個 `:verb` 路徑)。
- `apps/api/README.md`:REST 面一句話(occupations 根層集合)。
- `docs/adr/README.md` 索引 + `docs/README.md`(0001–0019)。
- runbook 如有引用舊路徑則更新(grep 確認)。
**commit**:`docs: propagate ADR 0019 naming into indexer/api READMEs + indexes`

## 回滾

單一 revert 對應 commit 即可(路徑字串無資料遷移)。
