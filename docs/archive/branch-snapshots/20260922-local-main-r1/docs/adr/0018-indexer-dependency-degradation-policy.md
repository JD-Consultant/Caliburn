# ADR 0018 — indexer 依賴降級政策:critical fail-fast vs enrichment 降級

- **狀態**:Accepted（2026-07-02）。
- 研究依據:[`../specs/2026-07-02-app-composition-health-degradation-research.md`](../specs/2026-07-02-app-composition-health-degradation-research.md)(§2.5、§4-F1)。
- 關聯:API review findings F1([`../specs/2026-06-30-api-review-findings.md`](../specs/2026-06-30-api-review-findings.md) §F1)。

## 脈絡

後端多個端點消費 indexer(知識服務)。indexer 掛掉時,現況失敗契約**兩套且隱性**:

- **502(fail-fast)**:`task-candidates`、`ocs-search`。
- **降級回空(200)**:`header-meta`、`task-catalogs`、`ai/*`。

政策散在各端點 try/except,無統一分類、無「部分資料」訊號——前端拿到空 `{}` 分不清「真的沒有」還是「indexer 暫掛」。

## 決定

顯性化並文件化政策,對齊 AWS Well-Architected **REL05-BP01**(逐依賴分類:critical→fail、non-critical→degrade)+ Google SRE(fail-fast 勝 fail-slow)。**分層落在架構正確的位置**:service 產部分結果、delivery(route)決定狀態碼。

| 端點 | 分類 | 掛掉行為 | 理由 |
|---|---|---|---|
| `task-candidates` | **critical** | 502 | 沒候選清單就選不了任務,主流程斷 → 快錯讓前端顯示錯誤 |
| `ocs-search` | **critical** | 502 | 空搜尋結果會被誤解成「查無此職類」→ 快錯更誠實 |
| `header-meta` | **enrichment** | 200 + `meta.partial=true` | 只是填格建議,缺了仍可手動編輯 |
| `task-catalogs` | **enrichment** | 200 + `meta.partial=true` | 同上;某 ocs_code 池撈不到僅略過該任務 |

**唯一行為變更**:enrichment 端點降級時,回應加 `"meta": {"partial": true}`,讓前端能提示「部分建議暫時無法載入」。**additive 欄位**——舊前端忽略此欄位不受影響。分類寫進端點 docstring。

## 後果

- ✅ 降級行為顯性化 + 文件化;前端可區分「真沒有」vs「暫掛」。
- ✅ 幾乎零行為變更(critical 維持 502、enrichment 維持降級,只多 additive `meta`)→ 低風險,靠既有測試當 net。
- ✅ 分層正確:service(`header_meta.aggregate` 已能吃空 metas)產部分結果;route 只負責 502 映射與 partial 旗標。

## 延後(記錄,非遺漏)

- **circuit breaker**(Nygard/Fowler):依賴持續掛時短路、防級聯失敗。本專案**單一 indexer + 已有 timeout**,現加屬過度工程 → **延後**;未來多依賴/高流量再引入。
- **共用 `_indexer(critical=…)` helper**:現有 per-code try/except 已清楚,抽 helper 收益有限,暫不為重構而重構。
