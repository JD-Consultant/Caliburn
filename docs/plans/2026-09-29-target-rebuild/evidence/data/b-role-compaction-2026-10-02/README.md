# B1／B2 輪前壓縮的真模型觀察（2026-10-02，部分完成）

登記與判準見 [T16 §12](../../t16-compaction-continuity.md#12-b1b2-輪前壓縮的真模型觀察2026-10-02執行前-manifest)；結果與判定見同頁「結果」小節。本資料包只保存原件與衍生分析，不重新解讀為通過。

**狀態：**一次登記的訪談在第 4 輪被 **OpenAI 帳戶儲值額度用完（`credit_balance_exhausted`）**擋下，依登記的停止條件停止；沒有重送、沒有重跑。被擋之前，B1 與 B2 的輪前壓縮已在真 provider 上各發生並被採用一次。

| 檔案 | 內容 |
|---|---|
| `runs/b-compaction-1.json` | harness 的最終結果：逐字稿、事件、當時的 JD 與引用（4 輪，其中第 4 輪 failed） |
| `runs/b-compaction-1.progress.jsonl`／`.events.jsonl`／`.stdout.log` | 逐輪紀錄、事件（含第 4 輪失敗後以原句重送一次）、harness 標準輸出 |
| `analysis/b-compaction-analysis.txt` | `tools/analyze_b_compaction.py` 對該職務檔案的唯讀輸出：各批次的外送嘗試、B1／B2 `prepared_history` 計數與被採用的壓縮及其 usage、壓後請求大小、已發布快照 |
| `analysis/provider-failures.txt` | 後端對三次被擋請求保存的安全診斷（白名單欄位：failure 類別、HTTP status、provider code、本地請求身分），沒有請求或回應內容 |
| `tools/` | 探針專用啟動器（把 B1／B2 的輪前門檻在該程序內調為 3,000；產品程式不變）、啟停腳本、分析腳本；執行前固定的 SHA-256 見 T16 §12 結果 |
| `SHA256SUMS.txt` | 除本 README 外所有檔案的雜湊（LF 換行；`.gitattributes` 設為不轉換換行） |

**環境：**新 schema `b_compaction_20261002`（loopback `caliburn_t01_test`）、8105（已停止）；產品預設 `gpt-6-luna`／high、員工模擬 `gpt-6-luna`／low；全合成課程行政人設。產品 ledger 累計 US$0.0161（員工模擬不在內）。

**不能從這包推出的事：**B 批次在壓縮後「發布快照」沒有被觀察到（批次因帳戶額度失敗）；沒有再壓縮的觀察；128K 這個值本身沒有被測試。
