# H4-R1：有界批次的 B1 在真 PostgreSQL 上保存與恢復

2026-09-14；JD-R002／OI-01、OI-02。實作[H4 計畫 §4 R1](../../../plans/2026-09-14-jd-h4-runtime-integration.md) 第2–5點，接續同單位[第1點的批次接點](fixed-target-batch-results.md)。基準 `7a2a381b`。**0 provider、沒有新增資料表、沒有新 parser／游標／B1 流程。**

## 範圍

新增 `experiments/jd-relational-app/tests/test_extraction_postgres.py`。**產品程式一行未改**：用的是既有 `build_extraction_workflow`、既有 `ExtractionWorkflow`、既有 prompt、既有更正額度（1）與既有 OpenAI structured adapter；模型 profile 沿已驗的 8192 輸出／`effort=high`／`store=false`。B1 自身 `max_windows` 維持預設 16，只把 **owner 的批次上限**降到 1–2 以在固定 fixture 內產生兩批。

資源是真的：`PostgresSaver`（`jd_runtime_test` 四張 checkpoint 表）、`PostgresStore`（`jd_memory_core_test`）、PG18.6，皆先由既有 `init_test_runtime.py`／`init_test_memory.py` 明示初始化。測試不 setup、不清資料、不刪 volume。provider 由 `httpx.MockTransport` 在程序內回覆，SDK 與結構化輸出繫結是真的；**這不是模型品質證據**。

窗口預算用**已驗的 6000／1500**，不是為了湊測試而調小的數字；回合長度（每邊 1250 字）才是 fixture 選擇。

## 六個案例與它們釘住的事

| 案例 | 釘住的事 |
|---|---|
| `..._one_bounded_batch_saves_durably_and_the_cursor_alone_takes_the_tail` | target→有界批次→B1 完整一批；`files` 的 pair 等於規劃出的固定 pair；尾端只由第一批自己的引用推動，不需新通知 |
| `..._store_fault_resumes_on_rebuilt_resources_without_calling_the_model_again` | 模型結果已 checkpoint 後 Store 失敗；**關閉並重開全部連線／graph／saver／store**，以原 config `resume()`，新 transport **零次** HTTP |
| `..._half_written_pair_leaves_an_unreferenced_artifact_and_still_completes` | 詳記已寫、候選未寫；續作後 `files` 指向真正成對的產物，落單的那份**允許存在**，不要求跨 Saver／Store 交易或 GC |
| `..._unconfirmed_save_checkpoint_resumes_without_buying_the_window_again` | 兩產物都已寫、記錄它們的 checkpoint 未確認；續作不重呼叫模型（見下方發現） |
| `..._repeat_request_reads_back_and_a_pending_job_refuses_a_new_input` | 相同 input 原樣查回且不再呼叫模型；pending 時換 input 被拒 |
| `..._re_extraction_reads_the_original_pair_and_leaves_the_normal_position` | 重抽讀回**原**成對引用，正常 B1 的 `files`／`source_reference` 位置不前進 |

每個案例都直接以 SQL 核對真表：`store` 的產物列數、`q019_document_memory_head` 恆為 **0 列**——B1 保存的詳記從未變成目前 Memory。

## 實測與首敗

```powershell
$env:JD_RELATIONAL_TEST_DB='1'
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache `
  pytest -c pyproject.toml -q -p no:cacheprovider tests/test_extraction_postgres.py
```

| 範圍 | 結果 |
|---|---|
| 本檔案（真 PG＋真 Saver／Store＋真 SDK） | **6 passed／11.90s** |
| 相鄰真 PG 回歸（來源、Memory 核心、C 接合、C context、C 修補核心） | **17 passed／11.79s** |
| App 全離線測試 | **2812 passed／263 skipped／42.52s**（skip 較先前 +6，即本檔在未啟用時正確跳過） |

一批的實際數字（測試印出，每個值都是量到的）：`windows=4 files=4 http=4 rows=8 published=0`——4 個規劃窗口分兩批各 2 個，模型呼叫數等於窗口數沒有重複，Store 有 8 列產物，publication head 0 列。初版這行把 `files` 與 `provider_calls` 寫成常數，經獨立審查指出後改為實測值；`provider_calls` 已移除，因為那是設計事實（transport 在程序內），不是這次量到的數。

三個首敗全部是**測試自身**的假設錯，沒有為了通過而放寬產品：

1. `pytest.raises(..., match="^synthetic store fault$")` 永不匹配：LangGraph 會在例外訊息後附加 `During task with name 'save'...`。改成非錨定匹配。
2. 以 `metadata["writes"]` 辨識 save 步驟的故障注入從未觸發：本機 LangGraph 1.2.11 在 `put` 帶的 metadata 中該欄為空。改以「第一個帶有 `files` 的 checkpoint」定位，那正是記錄已寫入產物的那一步。
3. 預期「save checkpoint 未確認」續作後會出現**四**列產物（落單一對＋重寫一對），實測是**兩**列。

## 第 3 點是一個實際發現

在該位置，`save` 節點自己的輸出已被寫成持久 pending write，所以續作是**套用已記錄的結果**，不是重跑該節點——因此沒有第二對產物，也沒有第二次模型呼叫。

**這是對這個位置的觀察，不是外部副作用 exactly-once 保證。**同一份工作在別的位置（例如模型已回覆但結果尚未 checkpoint）不適用；本輪**沒有**模擬那個未知位置，因此對它不做任何「零次重呼叫」宣稱。上表第三列的落單產物案例已經證明：位置不同，結果就不同。

## 獨立審查與窄複核

由未參與施工的審查者依 §3.6／契約 §7－§8／計畫 §4－§6 獨立複核，**沒有找到現存程式缺陷**，並獨立重跑了本稿宣稱的兩個變異（皆被殺）、以 84+5 次差異比對確認 `plan_saved_windows` 重構後行為完全不變、實跑 `test_extraction_postgres.py` 得到與本稿逐字相同的輸出。

審查提出的可重現問題已在本輪修掉：**游標停在 target 起點之前時，批次規劃會靜默跳過中間回合**（重現條件 cursor=`t0..t0`、target=`t2..t3`）。已改為明示 `invalid_ref` 並補反例，詳見[批次接點結果](fixed-target-batch-results.md)第八個案例。另外本稿引用的印出行原本含硬寫常數，已改為實測值。

其餘 finding 均為「下一片未接」或「可延後」：R3 的 dispatcher 須先 `follows()` 再切批次並沿用 `_owner_errors()` 錯誤邊界；`through_reference` 不得放上一批的 batch ref。這些已寫進批次接點結果稿的限制。

修正後窄複核：受影響組 **309 passed**、真 PG **6 passed**、全離線 **2812 passed／263 skipped**。

## 限制與未完成

1. R1 完成的是**有界批次＋一批 B1 的真 PG 保存／恢復**。**B2、publication 交接、通知註冊、背景准入、宿主生命週期、真新 Windows 程序全部未做**；R2／R3 仍未開始。
2. 資源重建是**同一程序內**關閉再開新連線／graph／saver／store。**真新 Windows 程序取回原工作是 R3 第7點**，本輪沒有該證據。
3. 固定 SDK 回覆不是自然模型品質；`accepted()` 驗的是 provider 的終局／拒絕欄位，不是內容好壞。**日常 AI 仍未啟用。**
4. 既有 C／source 的真 PG 案例與本檔是不同層級，不相加成一個「已驗」總數。
5. 未模擬的位置與未宣稱的保證已在上一節明列；不得由本稿推導 B1 在任意中斷下都不重複呼叫模型。
6. 背景准入狀態的持久落點（映射 §3.3）仍未決，本輪沒有建表。
