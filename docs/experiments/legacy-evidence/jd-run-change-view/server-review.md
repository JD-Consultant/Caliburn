# 整輪改動唯讀接線：獨立審查

- 日期：2026-09-13。
- 審查者：`jd_ref_signer_preflight`；本輪伺服器接線作者為主代理。`references.py` 為本審查者先前所寫，**不列入自我獨審結論**。
- 範圍：`run_change_reads.py`、本輪 `change_reads.py`／`chat_service.py`／`chat_api.py` 差異、`test_run_change_reads.py`／`test_run_change_api.py`，及相關正式 schema 條件。只讀核對 `AiRuntime.inspect_run`、`ManualRuntime.inspect_document`／`close` 的既有接點。

## RC-S01：App 發券失敗被誤分類為使用者引用錯誤（P2，CLOSED）

修正前，首讀已取得合法 native capture 後，`RunChangeReadService.read` 仍把全段內的 `ReferenceValidationError` 統一轉為 `invalid_ref`。例如 `issue_run_cursor` 的 App 內部發券故障，會回 `invalid_ref`，經 ChatService／HTTP 成為 **422／reread**；這不是請求方提供了錯誤 token。應由內部讀取失敗回 `read_failed`，再沿既有映射成 **503／service_unavailable／lookup_run**。

最小反例使用既有合成 `setup()` 的合法 capture，僅將 codec 包成代理，令 `issue_run_cursor` 拋固定 `ReferenceValidationError("invalid_ref")`；其他方法仍走真正 codec。實跑得到：

```text
fault: App issue_run_cursor failure after valid native capture
actual: invalid_ref
expected: read_failed
suppress_context: True
```

重現位置為修正前 `run_change_reads.py:64` 的 issuer 與 `:114` 的最外層 catch。這是故障注入的錯誤分類反例；不宣稱正常 canonical UUID dataset 一定會自然觸發，也沒有秘密外洩或重播。

主代理已把 `ReferenceValidationError → invalid_ref` 限在 `resolve_run_cursor` 的請求解碼；App 發券、差異投影及輸出驗證失敗沿原 `read_failed`。初次 capture 仍為已核原生回合的 App 產物，發券沿既有 codec 重驗，沒有新增一套驗證引擎或修改公開 schema。

作者補上 `issue_run_cursor`／`issue` × 首讀／續頁共四個反例，回報首跑 **4 FAIL／1 PASS，2.14s**。本審查者獨立讀取修正並窄跑四個發券反例、原非法 cursor、HTTP issuer 故障與原未知回合／非法 cursor：**7 PASS／11 deselected，1.86s**。確認內部故障為 503／service_unavailable／lookup_run，非法輸入 cursor 仍是 422，且不先讀 SQL 材料。RC-S01 結案；本輪限定範圍未留下 P1／P2。

## 已核對且未見其他 P1／P2

- 初頁從 `inspect_run` 已驗的原生回合及實際 receipt 取 confirmed committed IDs；不存在回合拒絕，不偽裝成沒有變更。`effects_state` 來自捕捉時的完整收尾狀態，不由 committed 數量或 HTTP 完成推定。
- 後續頁僅解原 signed capture；不再呼叫 `inspect_run` 擴張 IDs 或把 unconfirmed 升為 settled。材料的文件／回合／AI origin／committed／ID 集合與數量再次核對；連續範圍的 S/E 與首末 receipt 配對。
- 整個 native 讀取、SQL 材料及完成投影都在同一 owner 的同步 `inspect_document` callback 中。callback 返回實際 dict，沒有讓 lazy iterator 或另起工作越過排空。既有 close 追蹤 read token；同執行緒未結束讀取不能假報排空。
- 整輪與原 operation 共用 `project_revision_changes`，仍以原 immutable snapshots 計算結構差異；operation 分支原有 producer／parent／receipt 檢查沒有被刪除。頁面沿原完整 record byte 分頁，不截掉欄位本文；沒有從 current head 重新比較或偽造 operation／change ref。
- generator 不保留 `if/then` 的限制有明確反例。伺服器新增既有 `jsonschema`／`referencing` 的兩份本機正式來源驗證；不存在遠端 retrieve callback。lazy cache 僅保存這兩個固定資源與 validator，沒有新資料權威。
- OpenAPI 從同一份 `ChatRunChangePage.allOf` 深拷貝條件，只將兩個欄位所引用的唯一 `ChatOpaqueRef` 內嵌到對應 schema root；沒有另寫通用 reference 解析器。真 OpenAPI schema 能拒絕 `continuity=none` 卻 count=1 的組合；錯誤 media type 及 GET cursor 上限保持既有邊界。

## 本次實際驗證與限制

```text
uv run --frozen --offline pytest -q tests/test_run_change_reads.py tests/test_run_change_api.py tests/test_run_change_contract.py
76 passed, 2 warnings in 4.42s

uv run --frozen --offline pytest -q tests/test_run_change_reads.py tests/test_run_change_api.py -k 'issuance_failure or invalid_caller_cursor or app_issuer_failure or unknown_run_or_invalid_cursor'
7 passed, 11 deselected, 2 warnings in 1.86s
```

兩個 warning 為既有 Starlette TestClient 的 AnyIO alias deprecation，以及 pytest cache 目錄 ACL；不是測試失敗。另執行上述一個合成 issuer 故障反例，未改產品碼。

本審查不重跑真 PG；前一工作已完成的 3 個 PG／Saver／ASGI／離線 SDK 案例見 [postgres.md](postgres.md)，其後新增的出站 schema／OpenAPI 接點由上述離線測試核對，最終 PG 窄回歸由主代理負責。沒有付費模型、服務啟動、資料庫寫入或真瀏覽器結論。

兩份 `contracts` 是隔離 App 原已依賴的隨附資源；普通 source checkout 以目前路徑可解析，不把這次審查當成安裝包完整性證據。打包議題沿 OI-08 保留，不新增另一份待辦。
