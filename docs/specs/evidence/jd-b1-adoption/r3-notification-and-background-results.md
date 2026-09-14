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

## 3. 宿主生命週期與有界背景 worker

### 沿用既有接點，不新造

計畫要求「採既有宿主的有限 worker 接點…不加入新長駐服務、分散式 queue 或無限 Future loop」。`ManualRuntime` 已經有每文件 slot、前景登記與 `close()` 的排空；背景工作**沿同一組機制登記**：

- `admit_background(document_id, work)` 把一個**有界批次**交給宿主自己的單一背景 worker，回傳 Future 由 caller 擁有。**沒有迴圈、沒有輪詢、批次之間不留常駐物**。
- `close()` 依既有順序多排空一項：停止新准入 → 取消尚未開始的批次 → 等已開始的批次真的退出 → 關 client／Store／Saver／engine。
- 尚未開始的批次直接取消，**不在程序內保留佇列**：讓它續作的是持久准入列，不是這個 process。

**單一背景 worker 是容量選擇，不是鎖。**前景與人工各有自己的 pool，所以一份文件的長批次不會擋住另一份文件。

背景准入另外要等 `finish_startup()`：**啟動恢復先決定原工作怎麼續作**，新批次不得與它競爭。

### 反例

| 案例 | 釘住的事 |
|---|---|
| `..._registered_background_job_is_drained_before_close_returns` | 關閉真的等已登記工作退出 |
| `..._close_stops_new_background_admission_before_it_drains` | 關閉後不再受理，新工作不會加入正在排空的集合 |
| `..._background_job_never_blocks_another_document` | 背景忙碌時另一份文件的讀取立即完成 |
| `..._background_batches_run_one_at_a_time` | 第二批等待，worker 空出後才開始 |
| `..._overrunning_job_is_reported_rather_than_left_hanging` | 超時回 `False`，不無限等待；釋放後再關可成功 |
| `..._real_host_gates_admits_drains_and_then_closes_its_resources`（真 PG 真宿主） | 啟動前拒絕；批次在關閉期間仍可用 Store 與准入列；關閉回 True 後兩條連線都已關；此後不再受理 |

### 實測

| 範圍 | 結果 |
|---|---|
| `tests/test_background_host.py`（離線） | **5 passed** |
| `tests/test_background_host_postgres.py`（真 PG 真宿主） | **1 passed** |
| 宿主相關真 PG 全組（背景宿主、宿主恢復、manual runtime／service、准入） | **37 passed／75.19s** |
| App 全離線測試 | **2839 passed／283 skipped／64.60s** |

真宿主案例是**單一測試涵蓋整個生命週期**：一個 process 只能 bootstrap 一個宿主，所以啟動閘門、排空與關閉後拒絕受理合併在同一條，而不是拆成三條各開一個宿主。

### 本節限制

1. **沒有任何東西會自動喚醒背景。**`admit_background` 是接點，喚醒條件（安全收尾後、啟動恢復後）與 dispatcher 尚未接上。
2. **真新 Windows 程序取回原 B 工作仍未做**（計畫 R3 第 7 點的四個停點）。本節的關閉／重開仍是同一程序。
3. 模型 client 的關閉屬 App 組裝層，不由 `ManualHost` 擁有；本節只驗它擁有的 Store／Saver／engine。
4. 顧問指引、Skills、`BackgroundAvailability` 與 JD 編輯器共用 writer 的接合仍未做。

## 4. 喚醒接點

### 一個入口，決定權在持久狀態

`BackgroundDispatcher.wake()` 是這份文件背景工作的**唯一入口**。喚醒本身便宜且可重複；**能不能執行由持久狀態決定，不由誰敲了幾次決定**。每次喚醒最多交出**一個有界批次**給宿主的背景 worker 然後返回——沒有迴圈、沒有佇列、批次之間不留常駐物。

決定順序完全沿用[設計 §5](../../2026-09-14-jd-background-admission-design.md) 的對帳表：`reconcile()` 先看 Saver 的 pending、再看 publication head，最後才看准入列想做什麼。

**新 target 必須有真正已保存的整理請求。**已驗 dispatcher 的字數後備**刻意不啟用**：由員工自己的通知決定何時開始背景工作。

### 各步驟實際做什麼

| 步驟 | 動作 |
|---|---|
| `wait` | 什麼都不做 |
| `busy` | 本文件的批次還在跑；**不再開一批** |
| `blocked` | 維持受阻；喚醒不得覆蓋具名決定 |
| `next_batch` | 從 target 切下一批、**先提交再** invoke B1 |
| `start_batch` | 批次已提交但 B1 沒跑過，就在該批次上啟動 B1 |
| `consolidate`／`resume_consolidation` | 交給 B2；只有**確認發布**後才推進准入列 |
| `resume_extraction` | 以原 config 續作 B1 |
| `settle_idle` | target 已涵蓋，轉 `idle` |

`_after_publication` 只在 publication head **真的**等於本批時才推進；沒發布成功就原地不動，下一次喚醒看到的仍是同一份未完成的工作。

### 反例與變異

| 案例 | 釘住的事 |
|---|---|
| `..._wakeup_without_a_saved_request_starts_nothing` | 安靜回合再怎麼喚醒都不啟動；准入列仍是 `idle`，零模型呼叫 |
| `..._saved_request_admits_a_target_and_runs_exactly_one_batch` | 請求決定何時開始、target 決定範圍；**只跑一批**（2 次呼叫而非整個 target） |
| `..._next_wakeup_hands_the_finished_batch_to_b2_and_publishes` | B1 完成／B2 未開始時，下一次喚醒做的就是交接；發布後本批清掉、target 保留 |
| `..._wakeup_after_publication_takes_the_tail_without_a_new_request` | 游標推進即接尾端，**不需要第二次通知**，target 不變 |
| `..._wakeup_on_blocked_work_changes_nothing` | 受阻是決定，不是喚醒可以覆蓋的狀態 |
| `..._waking_again_while_a_batch_runs_is_not_a_second_batch` | 連續三次喚醒只得到 `busy`，工作與准入列都不變 |

變異確認：拿掉「必須有有效整理請求」的條件後，第一條案例從 `wait` 變成 `next_batch` 並轉紅；還原後 hash 核對相符。

### 實測

| 範圍 | 結果 |
|---|---|
| `tests/test_background_dispatch_postgres.py`（真 PG） | **6 passed** |
| 背景相關真 PG 全組（喚醒、准入、責任歸屬、宿主、B1、B2） | **32 passed／45.31s** |
| App 全離線測試 | **2839 passed／289 skipped／45.68s** |

### 本節限制

1. **還沒有東西呼叫 `wake()`。**計畫要求「安全回合與啟動恢復時喚醒同一背景入口」——那兩個呼叫點尚未接上 `AiRuntime._settle` 與宿主啟動。
2. 測試以 inline worker 驅動決定邏輯；真背景 worker 的排空與關閉由 §3 的真宿主案例涵蓋，兩者不互相代稱。
3. **真新 Windows 程序取回原 B 工作仍未做**（計畫 R3 第 7 點的四個停點）。
4. 顧問指引、Skills、`BackgroundAvailability` 與 JD 編輯器共用 writer 仍未做。

## 5. 兩個喚醒呼叫點

計畫要求「安全回合與啟動恢復時喚醒同一背景入口」。`AiRuntime` 取得一個**可選**的 `background` 入口，在兩個位置呼叫，兩處都**只喚醒、不決定**：

| 位置 | 何時 |
|---|---|
| `_settle()` | 回合真的收尾之後。收尾失敗（`run_recovery_required`）**不喚醒**——結局未知的回合不該交給背景 |
| `_recover_previous()` | 啟動恢復檢視完一份文件之後。恢復拋錯則不喚醒 |

**喚醒失敗是背景自己的事**：不改變員工回合的結果，也不擋住宿主啟動。下一次喚醒會從同樣的持久狀態重新判斷。啟動恢復途中若順帶收尾了一個回合，會喚醒兩次——**這是設計上的冪等**，案例因此釘住「哪一份文件」而不是次數。

### 反例

| 案例 | 釘住的事 |
|---|---|
| `..._settled_turn_wakes_the_background_for_its_own_document` | 一次安全收尾、一次喚醒、指名該文件 |
| `..._turn_that_could_not_be_closed_wakes_nothing` | 收尾失敗不喚醒；明示 `recover()` 收尾後才喚醒 |
| `..._failing_wake_never_changes_what_the_turn_did` | 喚醒拋錯，回合結果、保存內容與查回都不變 |
| `..._startup_recovery_wakes_each_document_it_inspected` | 重開會請背景再看一次 |
| `..._failing_wake_never_stops_a_host_from_starting` | 背景不可用時宿主仍然 `ready` |
| `..._runtime_without_a_background_entry_still_settles` | 背景是可選接線，不是回合的前提 |
| `..._uncallable_background_entry_is_refused_at_assembly` | 錯誤接線在組裝時就失敗，不在員工回合裡爆 |

### 實測

| 範圍 | 結果 |
|---|---|
| `tests/test_background_wakeup.py` | **7 passed** |
| 受影響真 PG（AI runtime、C 接合、喚醒、准入、宿主、宿主恢復） | **39 passed／83.64s** |
| App 全離線測試 | **2846 passed／289 skipped／45.42s** |

### 本節限制

1. `AiRuntime` 現在會喚醒，但**日常組裝尚未把 `BackgroundDispatcher` 傳進去**——`managed_app`／`configured_host` 的接線還沒做，所以產品路徑上仍然沒有背景執行。
2. **真新 Windows 程序取回原 B 工作仍未做**（計畫 R3 第 7 點的四個停點）。
3. 顧問指引、Skills、`BackgroundAvailability` 與 JD 編輯器共用 writer 仍未做。
