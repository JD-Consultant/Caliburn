# H4-R3：通知、背景生命週期與顧問方法

2026-09-14；JD-R002／OI-01、OI-02。實作[H4 計畫 §4 R3](../../../plans/2026-09-14-jd-h4-runtime-integration.md)，接續 [R2](r2-consolidation-handover-results.md)。基準 `d0e07d22`／tag `jd-h4-r2-consolidation-20260914`。**本稿隨 R3 分段完成逐節追加；未寫進來的段落就是還沒做。**

## 1. 純通知工具的完整接合

### 現況與缺口

`request_memory_consolidation` 自 `4f94fbfb` 採用進套件後**一直沒有註冊給顧問**：`build_consultant_tools()` 只有十個 JD 工具、四個 Memory 只讀工具與一個修補工具，顧問發不出整理通知，`pending_windows()` 因此永遠是空的。

更實際的缺口在**結果分類**。`ai_runtime` 有兩處按工具名分流：

- `_settle()` 為停止前未執行的呼叫補結果，預設落到 `_not_executed()`——那是 **JD operation 形狀**（`status`／`effect`／`receipt_durability`／`operation_ref`／`change_ref`）。
- `_verify_saved_results()` 對沒有 binding 的結果，同樣預設要求它是一個合法的 JD operation 失敗結果。

只註冊工具而不改這兩處，停止前未執行的通知就會被寫成「嘗試過一次 JD 寫入、結果未改變」——計畫明令「純通知不能借用 JD operation 或 C publication」「不假造 JD 的 `_not_executed()`」。

### 施工

註冊工具；新增 `_request_not_executed()` 回 `{"error": "memory_consolidation_not_requested", "next_action": "stop"}`，形狀與既有 Memory 只讀工具的停止結果一致，沒有任何 JD operation 欄位；`_verify_saved_results()` 為此工具建立自己的分支：**artifact 就是它的全部憑證**（成功必須帶 `{"kind": REQUEST_KIND}`），失敗只允許它自己的固定停止結果。

沒有新增背景執行、沒有新表、沒有動 `has_saved_request` 的辨識規則。

### 反例先行

| 案例 | 先紅的原因 |
|---|---|
| `..._consultant_is_given_the_notification_tool_by_name` | 工具不在清單裡（斷言的是**身分**，不是數量） |
| `..._unanswered_notification_closes_as_its_own_result_not_a_jd_effect` | 實際得到 JD operation 形狀的 `_not_executed()` |
| `..._saved_notification_receipt_needs_no_binding_and_is_still_a_request` | 真憑證被當成非法 JD operation 結果，整輪 `run_recovery_required` |
| `..._notification_without_its_own_receipt_or_result_is_refused`（三個變體） | 無 artifact／錯 kind／借用 JD 失敗結果都必須拒絕 |

`..._unanswered_notification_never_counts_as_a_saved_request` 在修改前後都通過：它釘住的是產品性質（沒有請求就不得准入），目前由「錯誤狀態」與「沒有 artifact」兩件獨立事實共同保證。**這是守門案例，不是經變異驗證的鑑別性案例**，不能拿它宣稱辨識規則本身有被測。

寫測試時我自己有一個變體寫錯：原本把「內容是 JD operation 形狀但 artifact 正確」當成必須拒絕。artifact 才是憑證、內容形狀不是，模型也偽造不出 artifact，所以該變體無意義；改成守住真正的風險——**失敗結果不得借用 JD operation 形狀**。

### 實測

| 範圍 | 結果 |
|---|---|
| `tests/test_consultant_request_tool.py` | **7 passed** |
| App 全離線測試 | **2830 passed／268 skipped／43.41s**（較 R2 +7，即新增案例；註冊新工具沒有造成任何既有案例退化） |

### 本節限制

1. **只完成通知本身。**背景准入、排空、宿主生命週期與新程序恢復都還沒做；顧問現在能發出通知，但**沒有任何東西會消費它**。
2. 工具回覆對員工說「系統會在本輪安全結束後評估排程」。在准入接好之前這句話還不成立；目前日常 AI 未啟用，沒有員工看得到，但**不得在准入完成前啟用**。
3. 本節沒有碰 `has_saved_request` 的辨識規則，也沒有新增背景表。
