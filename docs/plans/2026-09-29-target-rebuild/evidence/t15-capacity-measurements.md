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

## 6. T15 完成對照（2026-10-01 有界收尾）

查核基準 `63c0e5d6`，依 [T15 自身完成條件](../tasks.md#t15-安全容量與維護性審查)及 Owner 適度驗收指示：**現有證據足以收斂 T15，無須新增平台或先做效能優化**。本節更新前節尚待整合判斷的狀態，交主線核對並更新唯一任務表；本片不改 tasks、不提交，也不宣告整體產品或 V26 全部完成。

| T15 條件／風險 | 實際證據與界線 |
|---|---|
| HTTP／憑證拒絕可觀察 | 沿[安全證據](t15-local-http-security.md)：Host／Origin 在 route 副作用前拒絕、proxy 保留來源；合成 key／provider 回顯不進 request body、PG checkpoint、公開讀取或 log。已核當前 bootstrap 安裝 middleware；既有 69 例等紀錄本次未重跑，不加總成新驗收數。 |
| V24 資料不升權、偽造 scope 拒絕 | 本次重跑下列既有測例：App 參考資料／員工正文維持 user role、A／B 工具白名單拒絕未授權呼叫、真 PG 拒絕跨檔案 JD 定位及偽造 scope、B1 拒絕讀／寫理解及超界訪談。這是組裝、dispatch 與 owner 的確定性安全證據，不是模型面對所有語意誘導都不犯錯的證明；[A dispatch](../../../../apps/api/src/caliburn/agents/job_consultant/tools.py)不靠 prompt 決定資格。 |
| 前端不同檔案 cache 不串用 | 沿[T09 來源 UI 實測](t09-source-viewer-ui.md#tdd-與驗證證據)，本次核對 [source-api](../../../../apps/web/src/features/source-viewer/source-api.ts)及 [SourceViewer 測例](../../../../apps/web/src/features/source-viewer/SourceViewer.test.tsx)：key 含檔案／修訂／引用／來源；同 ID 換檔與舊檔晚到回應均有反例。前端本次只讀 code／既有結果，未重跑。 |
| V26 在 T15 的容量／成本觀測部分 | 本頁 §2–4 已量實際 count、SQL 次數、延遲及保存 bytes；慢點已定位，尚無需新增 cache／索引。§5 的 41 例與 [import 邊界](../../../../apps/api/tests/unit/test_import_boundaries.py)證據沿用，核對當前 AST 檢查仍拒絕底稿 package／錯誤依賴方向；不把量測或靜態規則當作完整模型工具效果。SDK context／工具效果及 128K／272K 真 provider 容量仍由 T16 承接。 |
| V27 回退與公開歷史保留 | 本次真 PG 重跑取消後基底重用（含採用交易 rollback）及 saver 重連公開回看；公開訊息從原 response 白名單投影，不從 compact input 猜回。Memory ①／②沿已完成 T04，核對 [候選還原測例](../../../../apps/api/tests/integration/test_memory_candidates.py)保留第二安全點、拒絕遲到分支。[保存 §6](../../../architecture/persistence.md#6-保留失效與清理)允許首版不清理；目前未新增 checkpoint GC，故沒有「刪掉唯一原件仍可回看」的主張。將來啟用清理須另驗可達性，不能先刪回退／diff／原操作依據。 |

本次僅補上述安全／保留的既有反例重跑，**12 passed，4.52s，無 skip**；不是新缺陷的 Red–Green，也不是全後端回歸。`apps/api` 執行：

```powershell
$env:CALIBURN_TEST_DATABASE_URL='postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test'
$env:PYTHONDONTWRITEBYTECODE='1'
./.venv-target/Scripts/python.exe -B -m pytest tests/unit/test_consultant_tools.py::test_definitions_can_be_built_before_binding_and_match_the_bound_handlers tests/unit/test_consultant_tools.py::test_unknown_tool_is_rejected_without_dispatching_any_handler tests/unit/test_memory_analysis_tools.py::test_existing_contracts_route_reads_and_writes_without_call_id_as_operation tests/unit/test_public_commentary.py tests/integration/test_consultant_context_binding.py::test_initial_request_separates_raw_input_and_hidden_binding_without_jd_map tests/integration/test_jd_reads.py::test_current_candidate_sources_are_scoped_and_reads_do_not_formalize_or_align tests/integration/test_memory_read_workflow.py::test_model_read_rejections_are_actionable_not_partial_or_false_empty_success tests/integration/test_memory_write_tools.py::test_model_create_update_delete_reports_real_effects_and_isolates_permission tests/integration/test_role_context_history.py tests/integration/test_interview_history_turns.py::test_completed_history_locator_reopens_saved_public_commentary_only -q -p no:cacheprovider --tb=short
```

每例只建立／清理自身隨機測試 schema；合成模型結果不外送，未讀 `.env`、未改 Demo／啟停其程序。**無新增 T15 阻擋項**；冷啟動／磁碟滿／多人負載未驗，無已知相應使用阻塞，暫不擴測。真模型抗誘導與 JD 事實／引用品質、native compaction 大視窗及正式切換仍屬 T14／T16／T17／T18，不以這 12 例、既有總數或 API 200 代替。
