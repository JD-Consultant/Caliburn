# 完成窗口：切分規劃、消歧 pair 與 admission

2026-09-13；JD-R002／OI-01、OI-02。接續[觸發與連續範圍](trigger-and-coverage-results.md)，實作[契約](../../2026-09-13-jd-interview-window-source-contract.md) §3.3／§7.2／§7.3。基準 `78992ad1`／tag `jd-window-trigger-coverage-20260913`。0 provider、沒有新增資料表。

## 演算法是移接，不是重寫

切分沿固定來源 `4f94fbfb:sources.py` 的 `extraction_windows`／`extraction_batch`／`validate_saved_window`／`require_new_source_after` 逐條移接：

- 單一回合超過 `max_chars` → **失敗**，不砍掉中段
- 消歧前綴必須回溯到最近一則有公開文字的前置 AI 問句，並包含其間的員工答覆；放不進 `context_chars` 或總預算 → **失敗**，不省略也不截斷
- 整個前一輪只有在仍含該必要問句且放得下時才可當 context，永遠不取代更舊的問句
- 預算界線沿已驗值：`max_chars` 預設 6000／範圍 1..24000，`context_chars` 預設 1500／範圍 `0..max_chars-1`，`max_windows` 預設 16

## 三個用途，各自的簽章 domain

`context_reference` **不是**較小的窗口：它從前置問句起算，不是回合邊界，而且不得被當成另一個待整併來源。因此新增第三個 purpose `context`，獨立 salt／prefix，與 `source`／`window` 互不可驗。

`_ContextPosition` 只帶 `root_run_id` 作**釘住位置自身的身分**（讀回時需要），沒有範圍 run 界線。

**用途授予改成分開兩個旗標。**套件的 `save_extraction` 對 `source_reference` 與 `context_reference` **都**走同一個 `validate_source`，若只有單一旗標，context 引用就可能被當成 `processed_source`。現在：

| 使用者 | 授予 |
|---|---|
| C repair、當輪四個只讀工具 | 皆否（source-only） |
| B2 發布 | `window_references` |
| B1 抽取 artifact | `window_references` ＋ `context_references` |

## 規劃結果固定在同一 root

一次規劃產生的所有窗口，連同其 context，都固定在**發配時的同一 root checkpoint**（沿固定來源的單一 snapshot 做法）。因此窗口位置也帶 `root_run_id`：範圍界線是 `first_run_id`／`last_run_id`，讀回位置用 `root_run_id`，兩者分開。

## 有界批次不丟尾端

`plan_batch` 回 `{"windows", "covers_whole_range"}`。尾端**不需要額外狀態**：publication 游標決定下一批從哪裡開始。`covers_whole_range` 的存在就是為了讓呼叫者無法取前綴卻宣稱整段完成。

## admission

`follows(reference, previous, document_id)` 沿已驗兩條：新範圍必須在已發布範圍**之後**，且**連續**——起點必須正好是游標之後的第一個安全回合，跳過中間員工回合一律拒絕。比較用保存的對話順序，不用 ID 或時間戳。

## 一個未新增公開錯誤碼的決定

來源錯誤碼是既有的**固定公開集合**（`invalid_ref`／`source_not_available`），任何其他字串都會塌回 `source_not_available`。預算失敗屬規劃層、不是引用解析失敗，固定來源原本也是拋帶訊息的 `ValueError`。因此新增具名例外 `WindowBudgetExceeded(ValueError)`，**沒有動既有公開碼契約**。

## 實際驗證

首敗：`ImportError: cannot import name '_ContextPosition'`。之後四個首敗全部是**測試自身**的假設錯，已修測試未放寬產品：縮小 `max_chars` 卻沒同步調 `context_chars`（違反既有 `0 <= context_chars < max_chars`）、預算設太寬導致只規劃出一個窗口、預期用不存在的錯誤碼、context 讀回缺釘住位置身分。

| 範圍 | 結果 |
|---|---|
| 本檔案案例（累計） | **30 passed／4.64s** |
| App 全離線測試 | **2770 passed／257 skipped／40.65s** |
| Memory 套件全測 | **130 passed／6.76s** |
| 真 PG：C 接合＋原話來源＋Memory 核心 | **14 passed／16.27s** |

## 固定情境進度

**W-01–W-14 都有對應的測試入口，但不能把它們全部標成完整通過。** 目前 W-08 只測不存在的 bounds／root，沒有同 ID 分支 lineage 或合法 mid-turn cursor；W-13 只測 `validate_saved_window`，尚未接 B1 `reextract` 及「正常輸入位置不前進」；W-14 只測缺鏈，沒有 `>256` ancestor 的 fixture。這三項依審查紀錄列為部分證據，不能作為 H4／B1 已完成的宣稱。

W-14 的缺鏈案例沿既有做法建立（讓新回合的 root `input` checkpoint 保存失敗，同 `test_ai_history.py` 的技法），確認 `safe_turns`／`unprocessed_source` 會**明示** `original_run_lookup_required`，不退化成「沒有更早的回合」。**這個案例一寫就通過**：明示受限的行為本來就由既有 `AiRunHistory` 提供並向上傳遞，本案例是補上缺的證據，不是驅動產品改動。完整的 `>256` 深度案例及 W-08／W-13 補驗列在[實作審查](../2026-09-13-jd-window-source-implementation-review.md)。

## 明確**沒有**做的

- **工具尚未註冊給顧問**：顧問仍發不出整理通知（映射 §6 第5項）。
- **B1／B2 本身未採用**：本 port 只提供它們要吃的來源與規劃，`ExtractionWorkflow`／`ConsolidationWorkflow` 尚未進套件。
- **`MemorySourceReader.read` 的窗口／context 內容讀取**：仍只經 `read_window`／`read_context`。
- 背景准入狀態的持久落點（映射 §3.3）未決。

## 界線

1. 這是契約的第四片，**不是 H4 或完成窗口能力已接通**。
2. 全部為離線與固定 fixture，沒有 provider 呼叫；日常 AI 未啟用。
3. 沒有新增資料表、第二份游標或第二個原話 owner；C repair 與四個只讀工具未改。
4. 窗口／context 引用格式在本片改變（新增 `root_run_id`）。目前**沒有任何已發配的正式引用**，因此不涉及遷移；`format_version` 維持 1。
