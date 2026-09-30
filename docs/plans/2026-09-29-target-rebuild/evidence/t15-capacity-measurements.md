# T15：既有合成旅程的容量與讀取量測

- 日期：2026-10-01；程式基準 `599afb33`。這是有限量測與取捨，不是壓測、SLA、完整安全驗收或產品品質通過。
- 責任：[T15](../tasks.md#t15-安全容量與維護性審查)、[Context／執行接線](../../../implementation/agent-execution.md)、[程式組織](../../../implementation/code-organization.md)。HTTP／憑證證據仍在[原安全文件](t15-local-http-security.md)，不另建第二份規範。
- 沿 Owner「核心分析效果優先、不過度設計」：重用已完成合成訪談，不再付費生成大資料，不加 cache、索引、裁切歷史或保存系統。

## 1. 樣本與量測界線

只讀 loopback PostgreSQL 18.6 的 `_test` DB、`eval_a` schema：25 份職務檔案、136 個 A 執行（122 completed、14 failed）、28 批 Memory（26 completed、2 failed）、269 則正式訊息，單檔最高訪談序號 25。含先前診斷與失敗試次，**不是抽樣品質成功率**。本片未改資料、未啟動 App supervisor、未載入金鑰；原 Demo／8102 程序不動。

所有診斷連線指定 `default_transaction_read_only=on`、`statement_timeout=20000`。直接呼叫本提交的 workflow 及原生 saver 讀取；每個樣本先暖機一次，再序列讀取五次。計時含 workflow 與物件還原，不含 HTTP／UI／JSON 序列化；回傳 bytes 另以既有 wire projector 計算（來源總覽使用同內容 dataclass 的精簡 JSON）。SQL 次數由 SQLAlchemy `before_cursor_execute` 觀測，**不含** driver 交易／握手或 saver 的獨立連線。單機暖快取、無並行負載，不當作冷啟動或多人容量保證。

## 2. 已保存的實際 token count

從 `checkpoint_writes` 的 `input_count` 原紀錄，依 `attempt_id` 去重；同一 count 在多個 checkpoint 出現只算一次。不重新呼叫供應商、不用字數推估 tokens。

| 角色 | 已保存 count 次數 | 最小 | 中位 | 最大 |
|---|---:|---:|---:|---:|
| A 職務顧問 | 525 | 6,658 | 12,630 | 42,524 |
| B1 工作情境分析 | 107 | 2,722 | 4,155 | 16,357 |
| B2 工作理解分析 | 144 | 3,332 | 5,417 | 29,667 |

這是實際發送前計數的分布，可能含後續未生成的請求；不是獨立使用者數、生成次數或帳單。樣本未達 128K／272K，**不能以此宣稱極限容量已驗**。政策邊界沿既有離線／真 PG 測試，provider compact 的實測沿 [T06 §20](t06-agent-execution.md#20-真-compact-協定預檢2026-09-30-恢復後)；大視窗延遲另列 T16 未驗範圍。

## 3. 保存量

採 PostgreSQL 官方 [`pg_total_relation_size`](https://www.postgresql.org/docs/current/functions-admin.html#FUNCTIONS-ADMIN-DBSIZE)量實際 relation 配置空間（含索引／TOAST），不混同原文長度或網路傳輸量：

| relation | bytes | 精確列數（適用時） |
|---|---:|---:|
| `checkpoint_blobs` | 141,197,312 | 9,833 |
| `checkpoint_writes` | 125,575,168 | 24,458 |
| `checkpoints` | 13,312,000 | 7,165 |
| `jd_source_references` | 5,054,464 | — |

前三項共約 267.1 MiB，是整組多角色、多次診斷的保留量，不是單一職務檔案大小。按 thread 分別加總 blobs／writes 的 `octet_length(blob)`，最大 A 執行為 10,205,951 logical bytes、97 checkpoints；包含原生接續與重複保存，**不是該次查詢實際傳了 10 MB**。全 schema 單筆 `request_snapshot` 最高 257,045 bytes、`response_snapshot` 58,399 bytes、`tool_results` 10,852 bytes；這些 channel 統計包含多次持久化，不視為 unique API 次數。

**取捨：**目前不增設儲存壓縮、垃圾回收或第二份 history。若實際檔案長期累積導致磁碟／讀取問題，再從原 checkpoint owner 評估；不得為節省空間刪除正式引用或回退仍需要的內容。

## 4. 讀取結果與慢點

取 logical payload 最大的三個已完成 A thread。兩筆屬同一職務檔案，故 JD 投影相同；不把它們當成三份獨立職務。

| 執行 ID 前綴 | checkpoints | 狀態含 commentary 中位 ms | 業務狀態單獨中位 ms | JD work 中位 ms／SQL 次數 | 來源總覽中位 ms／SQL 次數 |
|---|---:|---:|---:|---:|---:|
| `c908bc3b` | 97 | 279.01 | 2.83 | 5.99／9 | 13.42／20 |
| `b9b00415` | 77 | 108.01 | 2.97 | 5.41／9 | 13.41／20 |
| `4e556801` | 103 | 123.24 | 2.82 | 5.25／9 | 10.54／17 |

最大樣本完整狀態的五次為 296.76／279.01／257.23／343.32／169.53 ms，wire 正文只有 857 bytes；另兩筆為 1,071／1,303 bytes。JD work 為 5,871／5,871／5,384 bytes；來源總覽為 16,621／16,621／13,194 bytes。來源總覽已有**單次讀取內**的來源去重，這不是新增跨請求 cache。

根因定位：`ConsultantStatusWorkflow._with_commentary` 透過 `read_public_commentary` 遍歷原 saver history、還原 response，再做公開欄位投影。拿掉 commentary 的**診斷對照**只需約 3 ms；不是 DB 狀態 owner 本身卡住。用 [`EXPLAIN (ANALYZE, BUFFERS)`](https://www.postgresql.org/docs/current/using-explain.html)檢查最大 thread 的 checkpoint 選取：既有 `checkpoints_thread_id_idx` 生效、97 rows、execution 0.200 ms。這只是選取計畫，不含完整 saver joins／反序列化，不能拿它冒充端到端時間。

**本次不改產品。**回看中間訊息仍可用，且不阻塞正式 JD 保存或來源回讀。後續若實際 UI 明顯變慢，優先按需讀取／減少不必要 history materialization；需維持公開訊息白名單與既有保存責任，不直接複製整套進度庫。現在不為這個樣本加 cache、手改框架表或重構執行系統。

## 5. 重現與有限回歸

本機診斷腳本在 ignored `.research-tmp/eval/measure_saved_capacity.py`，不成為產品依賴。量測算法：readonly `eval_a` → relation sizes／thread payload 排序 → `ConsultantStatusWorkflow.read`（原 saver、以及不帶 saver 的診斷對照）→ `JdEditingWorkflow.read_work`／`JdEvidenceWorkflow.read_overview` → 暖機一次、五次計時。腳本不執行 `saver.setup()`、migration 或模型；既有樣本保留供再查。

保存量可用下列唯讀 SQL 重新檢查；後續新增訪談會使數值改變：

```sql
SELECT relname, pg_total_relation_size(relid)
FROM pg_stat_user_tables WHERE schemaname = 'eval_a'
ORDER BY pg_total_relation_size(relid) DESC;

SELECT channel, count(*), max(octet_length(blob))
FROM eval_a.checkpoint_writes
WHERE channel IN ('request_snapshot', 'response_snapshot', 'tool_results')
GROUP BY channel;
```

工作目錄 `apps/api`，既有測例有限回歸（provider 為合成 transport，不付費；PG 每例使用自身新 schema）：

```powershell
$env:CALIBURN_TEST_DATABASE_URL='postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test'
.venv-target/Scripts/python.exe -B -m pytest tests/unit/test_request_capacity.py tests/unit/test_import_boundaries.py tests/integration/test_request_capacity_postgres.py -q -p no:cacheprovider --tb=short
```

**41 passed，4.56s**。涵蓋原 request count／預留限制、計數保存前後故障接續及高價值 import 邊界；不是全產品 regression。更早單跑 import 的 15 例通過但有 pytest cache 權限警告；上述合併執行關閉非必要 cache，沒有修改產品權限來消除警告。

本片結論是「已有實際 token／查詢／保存量，目前代表資料可讀，已定位非核心優化點」。未驗：冷啟動／磁碟滿、多人負載、128K／272K 真大視窗與所有提示注入語意。是否關閉 T15 仍由任務表依完整安全證據判斷，不以此片自動替 T16／T17 放行。
