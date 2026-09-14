# 整份還原：施工與結果

2026-09-14；JD-R002／OI-06。實作[歷史、整份還原與重開恢復設計 §4–5](../2026-09-12-jd-history-and-recovery-design.md)的伺服器端操作。基準 `fae65a66`。**0 provider、沒有新增資料表。**

## 1. 範圍

OI-06 是「已承諾未接線」：可以直接更正、可以看歷史，但**還原與整輪撤回都沒有實作**。本輪完成其中的**整份還原**（`restore_revision`）；整輪 AI 撤回（`undo_ai_turn`）沿同一 restore 服務，尚未做。

還原**不是倒帶**：它寫入一個新的修訂，內容是歷史的那一份，中間發生的事全部留在歷史裡。還原範圍只有 canonical JD 的六章資料、項目身分、順序、關係與既有來源引用——不動文件名稱／封存狀態、原始訪談、Memory、聊天或操作歷史。

## 2. 誰可以要求還原

**顧問永遠拿不到這個工具。**把整份文件退回去是員工的決定，不是某一輪可以選的動作。

- `MODELS`（模型工具集）不含 `restore_revision`；`build_consultant_tools()` 也沒有它。
- `model_command("restore_revision", …)` 回 `unknown_tool`——對模型而言它**不存在**，而不是一個要解釋的權限失敗。
- `manual_command` 接受它，並且**與其他命令走完全相同的解析、驗證與 writer**。

輸入形狀由**同一份 SSOT** 生成（`contracts/jd-work.schema.json` → `generated/models.py`），不是手寫；`generate_contract.py --check` 通過。放進 SSOT 目錄不等於變成模型工具，因為工具是由 `MODELS` 決定的。

## 3. 保存語意

`prepare_restore()` 以目前 base 版本的身分，從那一份歷史 snapshot 重建 domain，再用**今天的規則**整份驗證：不合規的歷史版本整組拒絕，不部分套用。接著沿既有 `write_candidate` → 比對 → 新修訂 → 新回執 → head，**全部在同一交易**，與其他編輯完全相同的路徑。

- 內容與目前相同 → `no_change`，不造空修訂。
- 目前 head 不是準備時看的那一版 → `stale_view`，同意套用在另一版上是不允許的。
- 目標不是這份文件自己的版本 → `target_missing`。
- 回覆遺失／重按同一 operation → 回原結果，**只新增一次修訂**。

**項目身分是身分，不是複本**：還原後的任務就是原來那個任務。來源引用**沿用歷史記錄**，不重新核定——舊依據回來時仍是舊依據。

## 4. 反例與實測

| 案例 | 釘住的事 |
|---|---|
| `..._consultant_is_never_given_restoring_as_a_tool` | 不在 `MODELS`／工具清單；模型呼叫是 `unknown_tool`；人工入口接受 |
| `..._restoring_writes_a_new_revision_and_keeps_what_happened_since` | 新修訂、內容 digest 等於目標、之後新增的職責從目前稿消失但**三個版本都還在歷史** |
| `..._restoring_to_content_that_is_already_current_changes_nothing` | `no_change`，修訂數不變 |
| `..._restore_prepared_against_an_older_head_is_refused` | `stale_view`，較晚的工作沒有被覆蓋 |
| `..._another_documents_revision_is_never_restored_here` | `target_missing` |
| `..._repeated_restore_returns_the_original_result_once` | 同 operation 回原結果，修訂數是 4 不是 5 |
| `..._restored_source_links_come_back_as_they_were_recorded` | 刪掉任務連同來源後還原，來源引用原樣回來 |

| 範圍 | 結果 |
|---|---|
| `tests/test_restore_revision.py`（真 PG） | **7 passed** |
| 受影響真 PG（還原、storage service／rows、人工 service／HTTP、run operations／change API） | **79 passed**，另有一項既有順序失敗（見限制 3） |
| App 全離線測試 | **2848 passed／296 skipped／45.50s** |
| `generate_contract.py --check` | **Python 與 TypeScript 皆相符** |

首敗全部是測試自身的形狀假設錯（`insert_item` 的 `scope_text`、`jd_delete_item` 的 `content_changes`、`source_links` 是 list 不是 dict、`WriteObservation` 的修訂在 `receipt` 上），以及一次 `@staticmethod` 裝飾詞未套用。沒有為通過而放寬產品。

既有守門正確地報出新的 catalog root：`test_catalog_has_eight_named_closed_tool_roots` 已改名並涵蓋新命令，仍然要求每個 root 是封閉物件、必填齊全、拒絕 App 專屬欄位。

## 5. 限制

1. **只完成伺服器端操作。**設計 §4 的**預覽流程**（H→S 整份差異、確認文案、還原期間停手改與新 AI 回合）與 HTTP／Web 入口**都還沒做**；目前沒有員工可以按的按鈕。
2. **整輪 AI 撤回（`undo_ai_turn`）未做。**它沿同一 restore 服務，但還需要回合歸屬查詢與 §4 的五項資格條件。OI-06 因此**尚未關閉**。
3. `test_run_change_api_postgres.py::test_ai_create_whole_run_equals_original_operation_and_stays_fixed_after_manual_change` 在多套件合跑時失敗、單獨跑通過；**移除本輪新檔案後仍然重現**，因此是既有的跨套件順序效應，不是本次造成。與先前記錄的 `test_chat_api_postgres` 失敗同類，兩者都未診斷。
4. 沒有真瀏覽器驗收；沒有自然模型。

---

# 整輪 AI 撤回：施工與結果

實作[撤回一輪 AI 的 JD 改動 §4–5](../2026-09-12-jd-ai-turn-undo-design.md)的伺服器端操作，沿用上文的同一 restore 服務。

## 6. 一次按下，整輪回去

`undo_ai_turn` 取回那一輪對 JD 的**全部**改動，不是只取消最後一筆。員工**不提供要回到哪裡**：伺服器從該輪自己的已提交 operations 推導起點，推不出來就拒絕，不從時間戳或 origin 猜範圍。

只有 JD 會動。**該輪、它的 operations 與回執、對話與 Memory 全部原樣保留**，而且撤回本身是一個新的修訂。

與還原一樣，**顧問永遠拿不到這個工具**：不在 `MODELS`、不在 `build_consultant_tools()`，模型呼叫回 `unknown_tool`。輸入形狀同樣由 SSOT 生成。

## 7. 範圍怎麼證明

`_undo_target()` 讀該輪自己的已提交 operations，把 `base → result` 連成一條鏈，並要求：

1. 至少有一筆已提交的 JD 修改，否則 `target_missing`——純訪談回合沒有可撤回的效果。
2. 鏈是**單一起點、不分叉、無缺口**，且長度等於 operations 筆數。
3. 鏈的終點等於 App 說的那一版，**而且仍是目前 head**。任何一項不成立回 `stale_view`。

起點的那一份 snapshot 就是還原目標，之後完全走 `prepare_restore` 與既有交易；內容淨值相同時自然得到 `no_change`，不偽造撤回事件。

## 8. 反例與變異

| 案例 | 釘住的事 |
|---|---|
| `..._consultant_is_never_given_undoing_as_a_tool` | 模型不存在此工具；人工入口接受 |
| `..._one_press_takes_back_the_whole_turn_and_keeps_its_record` | 同輪建立任務＋新增職責一起回去；**該輪兩筆 committed operation 原樣保留** |
| `..._turn_that_wrote_nothing_to_the_jd_has_nothing_to_take_back` | `target_missing` |
| `..._later_edit_by_anyone_else_makes_the_shortcut_unavailable` | `stale_view`；不得靜默丟棄他人後續工作 |
| `..._turn_interrupted_by_another_edit_is_refused_rather_than_guessed` | 交錯歷史不能當成一段撤回 |
| `..._expected_result_that_is_not_the_turns_own_end_is_refused` | App 看到的終點必須與紀錄相符 |
| `..._pressing_undo_twice_answers_from_the_first_operation` | 同 key 回原結果；成功後換新 key 也不能再撤回同一輪 |
| `..._turn_whose_writes_cancelled_out_reports_no_change` | 淨值相同回 `no_change`，不造假事件 |

**變異結果如實記錄：**拿掉「終點仍是目前 head」的證明後，`..._later_edit_by_anyone_else...` 與 `..._pressing_undo_twice...` 兩條轉紅——這是本功能最重要的安全性質，確認有牙。

但拿掉**鏈連續性**那兩條子句時，八個案例**仍然全過**：交錯情境是被「終點必須等於 App 所說且等於 head」擋下的。連續性子句的實際價值是**讓拒絕與資料庫回傳順序無關**——沒有它，是否拒絕會取決於先取到哪個起點。**我沒有寫出能殺掉該子句的案例，因此不宣稱它經過變異驗證**；保留它是因為安全結果不該取決於列的順序。還原後 `git hash-object` 三次皆相符。

## 9. 實測

| 範圍 | 結果 |
|---|---|
| `tests/test_undo_ai_turn.py`（真 PG） | **8 passed** |
| 受影響真 PG（撤回、還原、storage service／rows、人工 service、run operations） | **84 passed／11.75s** |
| App 全離線測試 | **2856 passed／304 skipped／45.69s** |
| `generate_contract.py --check` | **相符** |

既有契約守門報出一個真實張力：`test_all_root_keys_required_and_app_context_rejected` 原本要求「App 擁有的欄位不得出現在工具輸入」，但撤回是人工操作、`ai_run_id` 正是它要撤回的對象。已拆成兩條——所有 root 仍要求欄位齊全，App-context 拒絕只套用於**模型**工具。這不是放寬：模型根本拿不到這兩個命令。

## 10. 限制

1. **仍然只有伺服器端。**預覽流程、HTTP／Web 入口都還沒做；員工沒有可以按的按鈕。OI-06 **尚未關閉**。
2. 設計 §4 的前置條件中，「該輪 runtime 已閉合、沒有未解操作與仍可寫入的 writer」由既有 foreground admission 與 writer 門閘負責；本輪**沒有**為它新增證據，也沒有測試那條路徑。
3. 設計 §5 要求的「新回執記 `undo_ai_turn`、被撤回 T 及實際 S／E／R」目前只記到 `command_kind`；**被撤回的 T 與 S 沒有寫進回執**，查詢要靠 operation 的參數。這是已知缺口。
4. 沒有真瀏覽器驗收；沒有自然模型。
