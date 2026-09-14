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

---

# HTTP 入口：兩個人工操作接到同一條保存路由

## 11. 同一條路由，同一種引用

還原與撤回沒有新增路由，也沒有第二個 writer：它們是 `ManualCommand` 的兩個新變體，走既有的人工保存路由。契約由 SSOT 生成（`contracts/jd-manual-http.schema.json` → Python 與 TypeScript），`generate_contract.py --check` 相符。

**HTTP 說引用，內部命令說身分。**員工手上只有 App 發配的 `revision_ref`，不會有原始 UUID；`ManualService` 把它解析成身分再交給 writer——與 `base_revision_ref` 早就有的翻譯完全相同的一層。因此：

- `ManualRestoreRevisionCommand.arguments` 是 `{target_revision_ref}`
- `ManualUndoAiTurnCommand.arguments` 是 `{ai_run_id, expected_result_ref}`

`ManualCommand` 的 `oneOf` 從 8 個變體增為 10 個；模型那一側的 `MODELS` 仍是 8 個，兩者不相通。

## 12. 反例與實測

`..._employee_can_restore_a_revision_and_take_back_an_ai_turn`：員工改了工作目的，再以**第一版的引用**還原，內容回到原樣；接著以引用請求撤回一個沒有寫過 JD 的回合，得到 `target_missing` 且目前版不動——這正好證明引用真的變成了 writer 檢查的那個身分，而不是被當字串放行。

| 範圍 | 結果 |
|---|---|
| `tests/test_manual_service_postgres.py` ＋ `tests/test_manual_http_postgres.py`（真 PG） | **14 passed** |
| App 全離線測試 | **2856 passed／305 skipped／45.34s** |
| `generate_contract.py --check` | **相符** |
| `npx tsc --noEmit`（Web 型別） | **通過** |

首敗兩個都是測試自身的錯：AI 那筆改動用了 codec 發配的 `field_ref` 而非 `intent_for` 的別名慣例；以及該 fixture 的 authority 是真 `ManualRuntime`、沒有測試用的 `admit`。第二個讓我把 HTTP 層的撤回案例改成**驗證翻譯與路由**（完整撤回語意已在 storage 層以真 PG 驗過），而不是在 HTTP 測試裡硬造一個 AI 回合。

## 13. 限制

1. **預覽流程仍未做。**設計 §4 要求還原前先看 H→S 的整份差異、確認文案、並在確認期間停手改與新 AI 回合；目前只有「送出就執行」。**OI-06 仍未關閉。**
2. **Web 畫面沒有按鈕。**型別檢查通過只代表生成的 TS 可編譯，不代表畫面接了這兩個操作。
3. 回執仍只記 `command_kind`，沒有記被撤回的 T 與實際 S（見限制 §10.3）。
4. 沒有真瀏覽器驗收。

---

# 還原預覽：先看整份差異，再決定

## 14. 為什麼不能沿用已保存的差異形狀

設計 §4 要求還原前先看 **H→S 的整份差異**，且「Web 不計算業務差異」。投影本身已經有了：`project_revision_changes(base, result, codec)` 本來就能對比任意兩版。

但**回應形狀不能沿用 `ChangeReadPage`**：它必填 `operation_ref` 與 `origin`。預覽時什麼都還沒發生，硬塞就等於假造一個回執。因此新增 `RestorePreviewPage`——同一份 SSOT 生成，同樣的 `ChangeReadRecord`，但：

- `view: "restore_preview"`，`access: "current"`——這個比較**會過時**，形狀本身就說出來了。
- `base_revision_ref` 是**比較時的 head**；確認還原時把它送回去，head 若已移動會在保存時被 `stale_view` 擋下。
- `target_revision_ref` 是要還原成的那一版。**沒有** `operation_ref`、`origin`、`result_revision_ref`——它們在預覽裡都沒有意義。

路由 `POST /api/documents/{id}/jd/restore/preview` 只讀不寫，沿用既有 query app 的嚴格重解析與 RFC 9457 錯誤處理。`ReadCursor` 的 view 列舉多一個 `restore_preview`（cursor 仍是不透明簽章 token）。

## 15. 反例與實測

| 案例 | 釘住的事 |
|---|---|
| `..._preview_shows_the_whole_difference_before_anything_happens` | 列出整份差異、指名比較時的 head、**目前版完全沒動**；之後新增的職責顯示為會被移除 |
| `..._previewing_the_current_content_reports_no_difference` | 內容相同時 `total_changes == 0`，仍然不寫入 |
| `..._preview_route_forwards_the_reparsed_arguments_and_writes_nothing` | 路由只到達預覽讀取器，不碰目前讀取器與已保存差異讀取器 |
| `..._preview_route_refuses_a_body_that_is_not_its_own_shape` | 缺欄或夾帶 App 欄位都回 422，不到達讀取器 |

| 範圍 | 結果 |
|---|---|
| App 全離線測試 | **2858 passed／307 skipped／46.11s** |
| 受影響真 PG（還原、撤回、查詢、人工 service） | **35 passed／12.16s** |
| `generate_contract.py --check` | **相符** |
| `npx tsc --noEmit` | **通過** |

首敗兩個：`ReadCursor.view` 沒有 `restore_preview`（分頁時才會踩到，第一頁不會），以及一次 `@app.post` 被我的批次編輯削成 `.post`。前者是真實缺口並已補，後者是編輯失誤。

## 16. 仍未完成

1. **Web 畫面沒有按鈕。**API 與預覽都在了，但六章管理畫面還沒接上「查看差異 → 確認還原／撤回」。**OI-06 仍未關閉。**
2. 設計 §4.2 要求「還原確認期間停手改與新 AI 回合」——目前**沒有**這個保留機制；靠的是保存時的 `stale_view` 拒絕，這能防止覆蓋，但不會在確認前先擋住。
3. 回執仍只記 `command_kind`（見 §10.3）。
4. 沒有真瀏覽器驗收。

---

# Web 畫面：員工按得到的還原

## 17. 按鈕在歷史裡，流程是「先看再確認」

「改動與歷史」面板每一版多一個「還原到第 N 版」。按下去**不會寫入**：先取預覽，逐項列出會回復與移除的內容，並明說「以這份歷史內容取代目前 JD；之後的內容仍可在歷史找到。這只會改 JD，不會動到訪談、工作理解或案例。」內容完全相同時直接說「不會產生新版本」。

確認時把**預覽當下的 head** 當作 `base_revision_ref` 送回；head 若已移動，保存端以 `stale_view` 拒絕，畫面顯示原因而不覆蓋。取消只關閉預覽，沒有任何寫入。

差異由既有的 `ChangeDetails` 呈現，用的是伺服器投影的記錄——**Web 不計算業務差異**。

## 18. 撤回按鈕還沒有位置

`RevisionRecord` 沒有 `ai_run_id`，所以歷史面板無法提供「撤回這一輪」。撤回天生屬於**當輪改動**面板（那裡才知道 run id）。要把它接上需要 run 改動頁帶出該輪的終點版本引用——**本輪沒有做，也沒有為它改契約**。

## 19. 反例與實測

| 案例 | 釘住的事 |
|---|---|
| `a restore preview reads only, and says which head it compared against` | 只打預覽路由、body 是 `{target_revision_ref, cursor}`、回傳指名比較時的 head |
| `a preview page that answers about another revision is refused` | 回覆換了目標版本就是 `invalid_response` |
| `a preview whose declared total does not match what arrived is refused` | 宣告筆數與實到不符即拒絕 |

| 範圍 | 結果 |
|---|---|
| `npm test`（Web） | **296 passed** |
| `tsc --noEmit` | **通過** |
| `npm run build` | **通過** |

## 20. 仍未完成

1. **撤回沒有 Web 入口**（見 §18）。
2. **沒有真瀏覽器驗收。**型別檢查、單元測試與 build 通過都不等於真的在瀏覽器按過；計畫第 5 項的代表性真瀏覽器旅程**尚未執行**。
3. 設計 §4.2 的「確認期間停手改與新 AI 回合」仍未實作；目前靠保存時拒絕。
4. 回執仍只記 `command_kind`。
5. **OI-06 仍未關閉。**

---

# Web 畫面：撤回這輪

## 21. 不需要契約增補

上一節寫「撤回需要先讓 run 改動頁帶出該輪終點版本」——**那是沒查就說，錯了**。`ChatRunChangePage` 早就帶著 `run_id`、`result_revision_ref`、`continuity` 與 `effects_state`，而面板也已經收到目前版 `currentRevisionRef`。**本節沒有改任何契約。**

## 22. 什麼時候才給按鈕

`undoOffer()` 把設計 §4 的資格條件寫成一條規則，**不可用時顯示原因，而不是留一顆按不動的按鈕**：

| 情況 | 回應 |
|---|---|
| 這輪尚未全部確認 | 先查看結果再決定 |
| 沒有淨變更／沒寫過 JD | 沒有可撤回的內容 |
| 改動之間夾有其他修改 | 無法整輪撤回；可逐次查看或直接修正目前稿 |
| 這輪之後已有新的修改 | **不提供**——整輪撤回會蓋掉後來的工作 |
| 以上皆非 | 提供「撤回這輪 JD 改動」 |

確認文案說明「一次取回這輪對 JD 的全部改動，不是只取消最後一項。這只會改 JD：這輪的對話、工作理解與案例都會保留，歷史也保留這輪的紀錄。」

送出時以**該輪自己的終點**當 `base_revision_ref`；文件若已移動，保存端拒絕並顯示原因，不覆蓋後來的工作。

## 23. 反例與實測

`undoing a whole turn is offered only when it can be taken back as one range` 逐條釘住上表，包括「文件已移動」與「目前版未知」兩種都不提供，且每一種拒絕都帶得出原因字串。

| 範圍 | 結果 |
|---|---|
| `npm test`（Web） | **297 passed** |
| `tsc --noEmit` | **通過** |
| `npm run build` | **通過** |
| App 全離線測試 | **2858 passed／307 skipped** |

首敗一個：測試沿用了另一檔案的 `id()` 輔助函式而該檔沒有，改用具名字串。

## 24. 仍未完成

1. **沒有真瀏覽器驗收。**單元測試、型別檢查與 build 通過**都不是**真的在瀏覽器按過還原或撤回；計畫第 5 項的代表性真瀏覽器旅程仍未執行。
2. 設計 §4.2 的「確認期間停手改與新 AI 回合」仍未實作。
3. 回執仍只記 `command_kind`，沒記被撤回的 T 與實際 S。
4. **OI-06 因此仍未關閉**，但兩個操作的伺服器、HTTP 與畫面入口都已具備。
