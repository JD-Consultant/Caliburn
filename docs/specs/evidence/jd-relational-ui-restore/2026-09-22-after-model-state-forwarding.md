# 2026-09-22 A／JD 直接旅程：after-model state 接線修正

## 結論

本次驗收找到並修正一個不改產品語意的 Runtime 接線錯誤：LangChain 1.4.0 的 node-style `after_model(state, runtime)` 將目前 state 以第一個參數傳入；`runtime` 提供 context／store，但不保證有 `runtime.state`。A 的 `reproject_active_evidence_catalog()` 原本在這個 hook 路徑呼叫 `memory_session(runtime)`，因此第二個 JD tool 進入前被錯誤判為 `invalid_memory_session`。

修正沿用既有 Memory validator 與同一個 `MemoryReadSession`，只把 hook 已收到的 state 以既有 `SimpleNamespace(context, state, store)` 接點傳入；沒有新增 Memory、registry、Agent、資料表、queue、版本或另一套驗證。

## 驗證

- 受影響窄回歸：`62 passed／0 failed`，涵蓋 consultant tools 與 UI chat fixture。
- 2026-09-22 續驗：在新 JD App 隔離 `basetemp` 下執行排除兩個 Windows ACL 受限檔案後的完整離線集合，`3043 passed／322 skipped／0 failed`；warnings 為既有第三方 serializer／deprecation 警告。未把 `tests/test_config_file.py` 與 `tests/test_operator_entry.py` 的 37 個 Windows DPAPI／本機設定檔案例標成通過；它們在本機暫存／受保護路徑初始化時遭 ACL 拒絕，與產品回歸分開記錄。
- 續查結果：將兩個檔案移到另一個已確認可寫的隔離 `basetemp`，並縮小到單一 `test_missing_read_does_not_initialize`，仍在 pytest 暫存根目錄掃描／清理階段得到 `WinError 5`，沒有產品 assertion traceback。因此本機目前只能把這 37 個案例列為環境 `UNVERIFIED`，不修改 `config_file.py`、operator 入口或測試安全語意。
- 真 PostgreSQL／Saver／managed host／LangGraph／JD tool 的離線直接 HTTP 旅程：`jd_read → jd_create_task → 無工具收尾`，模型請求 3 次、SQL writer 1 次、提交 1 次，最後查回同一 `run_id` 為 `completed`，JD 修改保留。
- 瀏覽器 gate preflight：全新合成 fixture 的 `prepare` 未進入資料庫建立，因專用驗收 PostgreSQL `127.0.0.1:55436` 沒有 listener；Docker API 也回報 permission denied。沒有改用 repo compose 的舊 `5432` DB，避免把非本驗收 fixture／舊架構服務接入新 App；因此本輪瀏覽器頁面流程仍未執行，維持 `UNVERIFIED`。
- 2026-09-22 續驗：專用 PG fixture 已啟動並初始化，API `8772`、新 JD production Web `3002` 均 ready；在 Codex IAB 以同一新架構執行建立文件。IAB 畫面在建立文件後顯示「連線中斷或服務未回應」，沒有進入文件頁。Server evidence 收到 `GET 4／OPTIONS 6／POST 4`，全部 `200`、CORS origin 相符，且每個 ASGI response start／body end 都已轉送；沒有模型請求或 JD writer。之後從同一驗收 API 直接查回文件清單，確認 `完整流程驗收-20260922` 已存在，表示建立已提交而 IAB 沒有讀到結果；使用者另確認自己的瀏覽器可成功建立文件。這把本次差異定位在 IAB response-body／client completion 觀察層，仍不足以判定 IAB 內部 exact root cause；不修改 CORS、deadline、retry、request identity 或產品錯誤語意。固定 Chrome CDP 旅程另因 `chrome_devtools_unavailable` 尚未進入流程，維持 `UNVERIFIED`。
- 模型 transport 仍是固定 `httpx.MockTransport`；provider network、正式資料與付費呼叫均為 0。
- 一次過早查詢在 runtime closure 尚未完成時回傳暫時 `503 service_unavailable`；沒有重送模型或 writer，稍後以同一 `run_id` 查回成功。這保留既有 unknown／查回語意，不把它誤判成保存失敗。

## 尚未宣稱

Stable Chrome 的專用 CDP 驗收腳本本輪在啟動 Chrome 時得到 `chrome_devtools_unavailable`，尚未進入頁面流程；因此完整瀏覽器旅程仍是 `UNVERIFIED`。這不改寫先前的瀏覽器 failure evidence，也不授權修改 CORS、deadline、retry 或 request identity。

依據：

- [A 證據與 JD 來源接線施工計畫](../../../plans/2026-09-20-a-evidence-and-jd-source-alignment.md)
- [LangChain state／ToolRuntime 研究紀錄](../../2026-09-05-framework-conversation-source-and-summary-primitives-trace.md)
