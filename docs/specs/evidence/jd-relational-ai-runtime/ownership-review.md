# RS-4：前景 AI 共用 writer 的獨立審查

查閱／實測：2026-09-13。範圍為 `manual_runtime.py` 的 foreground 增補、`test_foreground_runtime.py`，並核對既有人工及目錄回歸。先獨立只讀審查，發現 OR-R01 後由主代理明示交付此兩檔作有限修正；沒有啟動 provider、Windows host 或資料庫。

## 結果

首輪獨立受影響離線測試 **78 PASS／0.69s**：

```text
uv run --frozen --offline pytest -q -p no:cacheprovider \
  tests/test_foreground_runtime.py tests/test_manual_runtime.py tests/test_catalog_runtime.py
```

測試使用真原生 Future／執行緒，保存與 checkpoint 為合成替身，不能替代真 PG、跨程序停止或完整 AiRuntime 接合證據。

## OR-R01 — P2：已結束 recovery 的 context 仍可通過寫入門閘（已修，獨立複核通過）

後續由另一位 reviewer 重跑四個反例 PASS，完整記於[coordinator 獨立複核](coordinator-review.md#or-r01-窄複核)；下方保留首敗與作者修正過程。

位置：[`manual_runtime.py`](../../../../experiments/jd-relational-app/src/jd_relational/manual_runtime.py) 的 `_run`、`require_stopped`；本次查閱約第 595、660–678 行。

`require_stopped` 核對 operation token、文件、`recover` 模式、執行緒，以及原 SQL／前景 Future 已結束，卻沒有核對**目前這一次 recovery Future 仍在執行**。若保存查回尚未確認、因此 entry 仍被保留，舊 recovery 捕捉的 context 在同一 pool 執行緒被重用時仍會通過門閘。這是晚到呼叫的權責檢查缺口，不表示本次已有真 JD 資料遭修改。

獨立最小反例使用 `max_workers=1`、實際 `ThreadPoolExecutor` 及合成 Storage：

1. `start_foreground` 執行空工作，等待原 Future 真正結束。
2. 用合法 AI `AdmittedIdentity` 呼叫 `recover_foreground`。合成 `reconcile_stopped` 先通過正常 `require_stopped`，記下 `copy_context()`／`get_ident()`，再回傳 `WriteObservation(..., None, "unknown")`。
3. 等 recovery handle 返回。確認原 `entry.attempt.future.done()` 已為真，但 operation 尚未 confirmed，entry 仍在。
4. 在該原生 pool 的下一個工作執行 `captured.run(owner.require_stopped, identity)`。執行緒相同，已結束的 recovery context 仍通過。

實際輸出（無內容、DSN 或秘密）：

```text
recover_done True confirmed False
{'same_thread': True, 'late_authorized': True}
closed True
```

最後一行是合成測試完成後的正常收尾；此探針沒有執行真 SQL。首個探針指令因未指定已授權 UV cache 而在啟動前失敗；補上專案 cache 後才取得以上有效證據。

建議把 recovery context 綁到**原 attempt 身分**，並要求它仍是目前 entry 的 recovery attempt、其原生 Future 正在 running。不能只因原 writer 已停止，就讓任何沿用該 operation token 的已結束 recovery 取得新写入權。至少保留上述同執行緒／done Future 反例；若換入下一次 recovery，也應拒絕前一次捕捉的 context。

修正與驗證：

- 新增四個參數化反例：manual／AI，分別在原 recovery 已 done 後、下一次 recovery 執行期間，於同一實際 pool 執行緒重用第一個 context。首跑 **4 FAIL／28 deselected**，四個分支皆錯誤放行。
- 每個 `_Attempt` 現在有不保存至 DB 的本程序 token；`_execution` 同時綁 entry 與 attempt token。`require_stopped` 要求 exact current attempt、`recover` 模式及其原生 Future 仍 running；`require_bound` 同樣明確核對原 write Future 就是目前 write attempt 的 Future。沒有重造持久身分、operation 或另一套 writer。
- 修正後 `test_foreground_runtime.py`、`test_manual_runtime.py`、`test_catalog_runtime.py`、`test_startup_recovery.py` 合計 **92 PASS／0.80s**。這包含上述四個紅例轉綠；正常原結果恢復及人工／目錄／啟動收尾仍通過。
- 此修正由發現者實作，需主代理另做窄複核，不能把同一作者回歸稱為獨立審查已完成。

## 其餘已核範圍與限制

- registry 全域鎖只管理 slots／accepting；文件工作使用同一 per-document slot。前景純訪談會阻擋同文件新人工保存、metadata 修改及另一 AI 回合；另一文件可繼續。
- 取消只設定 Event；timeout 不冒充停止。`recover_foreground`／`finish_foreground` 會等待實際前景 Future 結束，SQL 的未結束 Future 仍阻擋收尾。
- AI SQL 沿共用 Storage 執行，未借用人工 checkpoint descriptor；原結果仍可查回，unknown 不重新執行候選命令。
- `require_bound` 對晚到 SQL context 已核原 write Future running，並增加執行緒比對；此次 OR-R01 是 recovery 分支缺少對應限制。
- `close()` 關閉新准入後仍等待已准入工作及明示 durable closure；未把 pool 等待逾時當作成功退出。
- 本次未獨立驗真 PostgreSQL receipt、provider、跨宿主 AI 復原、Memory 或 HTTP 行為；不得把 78 PASS 解讀為這些範圍已完成。
