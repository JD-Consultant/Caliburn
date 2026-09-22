# 完成窗口：逐輪安全終局、發配與分頁讀取

2026-09-13；JD-R002／OI-01、OI-02。接續[用途隔離](purpose-isolation-results.md)，實作[契約](../../2026-09-13-jd-interview-window-source-contract.md) §4／§5 與 §3.1 的讀取側。基準 `78ce5689`／tag `jd-window-purpose-isolation-20260913`。0 provider、沒有新增資料表、沒有第二份原話庫或游標。

## 這一片做了什麼

全部放在**同一個 source owner**（`ConversationSourceService`）上，不另建服務去碰私有 codec，也沒有新 lineage 表——沿[9/13 原回合查回](../../2026-09-13-jd-chat-admission-and-original-run-slice.md)既定的 `AiRunCheckpoints`／`AiRunHistory`。

| 方法 | 契約對應 | 行為 |
|---|---|---|
| `safe_turns(document_id)` | §5 | 逐輪以 `AiRunHistory.find` 在**該輪自己的終局 checkpoint** 核對；`record.status != "running"` 且 `observed.closed` 才算安全。遇到第一個未安全收尾的回合就停，後面的終局不會回頭釋放前面的 |
| `capture_window(document_id, *, first_run_id, last_run_id)` | §3.1 | 兩端都必須是本文件的安全回合且順序正確，範圍因此天然連續。引用固定在**最後一輪自己的終局 root**，不是「當時最新」 |
| `read_window(ref, document_id, offset=0)` | §4 | 回 `reference`／`segments`／`turns`／`omitted_content_types`／`next_offset`；只讀固定位置，不回退 latest |

**lineage 不是靠 ID 相同。**每一輪的終局觀察，其完整訊息序列必須是我們釘住的對話的**精確前綴**；不成立即 `invalid_ref`。這比比對 message ID 或 UUID 順序強，符合契約 §7.2。

**分頁只切可見文字。**`turns` 每頁都完整列出窗口涵蓋的回合，呼叫者不必湊頁才知道終局。offset／`next_offset`／`text_offset` 一律是可見文字串接的 **Unicode code point**（Python `len`）位置，不插入分隔字元。

**省略的種類要具名。**工具／系統訊息與非 text 內容區塊（如 thinking）是 canonical 但不是員工原話，列進 `omitted_content_types`，不靜默丟棄。

## 實際驗證

首敗：`ModuleNotFoundError: No module named 'jd_relational.interview_windows'`（實作前）。
另有兩個**測試自身**的首敗，已修測試而非放寬產品：`next_offset` 斷言誤以為 emoji 佔多個 code point（2600 個 😀 是 2600 code points，正好證明是 code-point 計數，不是 bytes）；偽造引用用了不存在的 root，那本來就該回 `source_not_available` 而非 `invalid_ref`。

| 範圍 | 結果 |
|---|---|
| 本檔案案例（含前一片 8 個） | **13 passed／3.91s** |
| App 全離線測試 | **2753 passed／257 skipped／61.52s** |
| Memory 套件全測 | **130 passed／6.32s** |
| 真 PG：C 接合＋原話來源＋Memory 核心＋聊天 HTTP | **16 passed／1 failed／16.06s** |

該 1 failed 是 OI-05 已記錄的**既有**聊天歷史分頁缺陷（`test_chat_api_postgres.py::test_http_ai_edit_results_match_original_receipt_change_and_history_after_manual_head_advance`），先前已在基準 tag `jd-memory-repair-core-20260913` 的獨立 worktree 重現同一斷言，與本片無關。

新增案例涵蓋：逐輪終局與停在未收尾回合之前、安全收尾的 `cancelled` 回合仍保留員工原話且 `answer_succeeded=false`、角色與省略種類投影、跨頁 Unicode code-point 分頁且 `turns` 每頁完整、發配拒絕未收尾結尾與反向範圍、固定位置上 first／last 對不上回 `invalid_ref`、root 不存在回 `source_not_available`。

## 固定情境進度

| 已涵蓋 | 尚未涵蓋 |
|---|---|
| W-03、W-05、W-07、W-08；W-04 的「停在未收尾回合之前」 | W-01、W-02、W-04 的「後續通知不得先列為目標」、W-06、W-09、W-10、W-11、W-12、W-13、W-14 |

## 明確**沒有**做的（下一片）

- **`pending_windows`／`unprocessed_source`／`covered`／`follows`**：整理請求辨識（§6）、觸發清單與連續安全範圍分開（§7.1）、與 publication head `processed_source` 的覆蓋比較與 B1 admission（§7.2）。
- **窗口切分與 `context_reference` pair**（§3.3／§7.3）：`max_chars`／`context_chars` 預算、消歧前置問題、`max_windows` 超限時保留尾端、重抽回原窗口。目前 `capture_window` 一次發配整段安全範圍，**沒有**按預算切分。
- **`MemorySourceReader.read` 的窗口內容讀取**：窗口內容目前只能經 `read_window`。授予 window 的 reader 仍是驗證用（發布路徑不讀內容），B1／B2 的引用回查要接上時再補。
- W-14 的 >256 祖先／缺鏈雖由既有 `original_run_lookup_required` 明確保留並向上傳遞，**本片沒有建立該案例**。

## 界線與已知成本

1. `safe_turns` 每輪呼叫一次 `AiRunHistory.find`，每次各自重新 discover 並沿鏈回走，成本為 O(回合數 × 鏈深)。這是**刻意**選擇：重用已驗的走鏈與終局核對，而不是另寫一份。它跑在背景規劃路徑，不在前景聊天路徑；若日後成為瓶頸，再以單次走鏈取代，並須保留逐輪核對語意。
2. 這是契約的第二片，**不是 H4、B1／B2 或完成窗口能力已接通**。
3. 全部為離線固定 fixture，沒有 provider 呼叫；日常 AI 未啟用。
4. 沒有新增資料表、第二份游標或第二個原話 owner；C repair 與當輪四個只讀工具的 source port 未改。
