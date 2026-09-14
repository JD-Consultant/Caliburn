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

## 2. 背景准入的持久落點

### 缺口驗證（施工前）

計畫要求「先驗證既有 Saver／catalog 是否確實無法承載准入責任」。驗證以**真 PG 實測**而非推論：逐欄列出 B1 Saver state、B2 Saver state、publication head 與 `jd_document` 的全部欄位，`target_reference`、`status`、`error_code`、`recovery_count` 四項都不在其中。第二條案例證明批次不能代替 target——丟掉 target 後只剩目前 head，而從 head 重推的範圍會隨員工繼續講話而變大，已准入的工作因此永遠不會收斂。

缺口成立後**先停下回報**，由維護者裁決採用哪個方向，再施工。

### 決定與文件順序

依裁決意見的順序：先寫[狀態機、失敗與恢復條件](../../2026-09-14-jd-background-admission-design.md)，再落實 [ADR0076](../../../adr/0076-jd-background-admission-record.md) 與 Alembic migration `20260914_0002`，最後才寫程式。採用映射 §3.3 的「候選／待判定」已改為選定方向，原論證保留作出處。

**表數如實說明：十三張 JD 內容表未增減任何欄位，但 App 的 public 總表數自十三增為十四。**README、runbook 與 ADR 都寫明這一點，不以「JD 表沒變」掩蓋。

### 三個位置分開

| 位置 | 回答什麼 |
|---|---|
| `target_reference` | 這次已准入工作的固定終點；後續訪談不得擴大它 |
| `source_reference` | 目前正在交接的固定批次；invoke B1 **之前**提交 |
| `publication.processed_source` | 唯一已發布進度 |

B1／B2 的節點、`files` 與模型預算仍由原 Saver 負責，**不複製進此表**。此表不保存第二份原話、Memory 或已整併游標。

### 准入列證明不了什麼

`running` 不證明模型執行過，`idle` 不證明發布成功。`reconcile()` 因此**不信任這一列**：它依序讀 Saver 的 pending 狀態與 publication head，再決定下一步。**不要求跨 Saver、Store 與此表的單一大交易。**

### 反例與變異

`reconcile()` 若信任過期的列而不比對已發布 head，就會對同一批重做一次整併。實測變異（把 `published != batch` 的比較拿掉）使 `..._published_batch_is_recognised_even_when_the_row_is_stale` 從 `next_batch` 變成 `consolidate` 並轉紅；還原後 hash 核對相符。

「交接門閘」的反例由 R2 獨立審查重現後才建立：B1 在 B2 未發布時以相鄰新範圍 `start()` 會被 `follows()` 放行並覆寫 `files`。`require_handed_over` 改以 publication head 判定，**不在准入列另存一份判斷**。

### 驗收涵蓋

准入提交後尚未啟動（`start_batch`）、B1 完成但 B2 未開始（`consolidate`）、發布成功但准入列尚未更新（**不重做**，回 `next_batch`）、原 target 尚有尾端時新增訪談（target 不變、尾端仍可達）、重複喚醒（冪等、不重置恢復額度）、`blocked` 與恢復額度跨重開、封存停止新准入且保留原列與額度、以及表本身拒絕不描述真實工作的欄位組合。

原本「缺口存在」的兩條測試依裁決意見改寫為**責任歸屬與恢復行為**的驗收（檔案更名為 `test_background_admission_responsibilities.py`），不再永久要求新系統繼續缺少這些欄位。

### 實測

| 範圍 | 結果 |
|---|---|
| `tests/test_background_admission.py`（離線門閘） | **4 passed** |
| `tests/test_background_admission_postgres.py`（真 PG 准入） | **12 passed** |
| `tests/test_background_admission_responsibilities.py`（真 PG 責任歸屬） | **2 passed** |
| 受影響真 PG 全組（准入、B1、B2、來源、Memory 核心、C 接合、C context、C 修補、AI runtime、storage、setup） | **101 passed／67.13s** |
| App 全離線測試 | **2834 passed／282 skipped** |

新表使既有三個守門正確地報錯，全部依實況修正而非放寬：`test_exact_thirteen_business_tables_and_history_only_jsonb` 改為明示區分十三張內容表與這一張 runtime 表；離線 DDL 的 `CREATE TABLE jd_` 計數改為 14；`ddl_profile_v1.json` 重新產生（新 revision、新 schema hash、兩個 migration 的 hash、新表的實際 PostgreSQL CHECK 渲染）。`storage_setup.REVISION` 與兩處版本斷言推進到 `20260914_0002`。

固定 SDK 的工具斷言依計畫改為**核工具身分**而非只改數字：`_offline_model` 現在比對 wire 上的工具名稱集合，加一個工具是明示可見的變更。

### 本節限制與一項既有失敗

1. **宿主生命週期尚未接。**有界背景 worker、關閉順序（停新准入→等已登記工作退出→關 client／Store／Saver）與**真新 Windows 程序取回原 B 工作**都還沒做。目前沒有任何東西會自動喚醒准入。
2. 資源重建仍是同一程序內；跨程序證據是 R3 未完成的部分。
3. 顧問指引、三項分析 Skills、`MEMORY_ACTION_GUIDANCE`／`BackgroundAvailability` 與 JD 編輯器共用 writer 的接合都未做。
4. **`test_chat_api_postgres.py::test_http_ai_edit_results_match_original_receipt_change_and_history_after_manual_head_advance` 目前失敗，且與本輪無關。**把本輪對 `ai_runtime.py`／`memory_context.py` 的改動暫時還原後**仍然重現**（還原後 hash 核對相符）。失敗點是 anchored 聊天歷史回傳 assistant 訊息而非預期的 user 訊息。這是既有問題，記錄於此不代表已診斷或已修；不得因它與本輪同時出現而歸因於背景准入。
