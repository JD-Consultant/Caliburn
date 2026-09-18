# Plan — F1 indexer 降級政策顯性化(`meta.partial` + docstring)

- 依據:[ADR 0018](../adr/0018-indexer-dependency-degradation-policy.md) · 研究 [`../specs/2026-07-02-app-composition-health-degradation-research.md`](../specs/2026-07-02-app-composition-health-degradation-research.md)。
- 原則:additive 欄位,幾乎零行為變更;green-before==green-after。

## Task 3 — enrichment 端點降級加 `meta.partial`

**改** `apps/api/app/api/routes/documents.py`
- `get_header_meta`:某 code `occupation()` 失敗時記 `partial=True`;回應併 `{"meta": {"partial": partial}}`(全成功則 `partial=false`)。docstring 標明 enrichment 分類。
- `task_catalogs`:某 ocs_code `competencies()` 撈不到(`pools[code] is None`)時 `partial=True`;回應加 `"meta": {"partial": partial}`。docstring 標明。
- `task_candidates` / `ocs_search`:docstring 標明 **critical**(維持 502);不改行為。

**web 型別**(additive):
- `apps/web/src/types/index.ts`:`HeaderMeta` / `TaskCatalogs` 回應加 optional `meta?: { partial: boolean }`。前端暫可忽略(未來接 UI 提示)。

**測試**
- `test_documents_api.py`:header-meta indexer-down → 斷言 `meta.partial == true` 且仍 200 + 空建議。
- `test_task_catalogs_api.py`:某 ocs_code 掛 → `meta.partial == true`,該任務略過、其餘照常。
- 全成功路徑 → `meta.partial == false`。

**驗收**:`uv run pytest -q` 綠(+ 新斷言)。
**commit**:`feat(api): signal degraded enrichment via meta.partial; document critical/enrichment policy [F1, ADR 0018]`

## 不做(記錄)
- circuit breaker、共用 `_indexer()` helper — 延後(ADR 0018)。
