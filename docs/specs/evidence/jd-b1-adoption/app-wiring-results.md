# B1 OpenAI adapter 與固定接合測試完成

2026-09-14；JD-R002／OI-01、OI-02。依[採用映射 §6.2](../../2026-09-13-jd-consultant-b1-b2-adoption-mapping.md)與本輪工作單位定義，基準 `353c400b`／tag `jd-b1-core-adoption-20260913`；依[本片審查](app-wiring-review.md) F1–F4 與[複核](app-wiring-followup-review.md) P1／P2 修正後重寫。

**B1 是訪談資料整理進 Memory 的既有階段**，不是重新設計 JD 編輯器，也不是另一個使用者頁面。本片只把已完成的 B1 接上新 App 的來源 owner 與 OpenAI，**不重做 B1、不改整個顧問**。

完成範圍要分三層講，不能混為一談：

| 層 | 狀態 |
|---|---|
| B1 核心採用（套件） | **已完成**（前一片 `353c400b`） |
| App 端 adapter／provider wiring 的固定接合 | **本片完成**，全部為 MockTransport／InMemorySaver／InMemoryStore 的固定行為證據 |
| B1 runtime 觸發、背景准入與排空、宿主重開續作、設定與金鑰、真 PostgreSQL 保存 | **未開始** |

**因此本片不代表日常 App 已可使用 B1**，也不代表 H4 或完整旅程有進展。

## 1. 只新增 App 端適配器

新增兩個檔案層級的東西，其餘全部沿用：

| 新增 | 內容 |
|---|---|
| `jd_relational/extraction_app.py` | OpenAI 綁定、`accepted` 終局證據、`ExtractionSourceAdapter`、`build_extraction_workflow` 組裝 |
| `ConversationSourceService.read_context` 的 `turns` | 審查 F1：由同一 owner 在固定位置投影範圍內可證明的回合終局 |
| `ConversationSourceService.plan_saved_windows` | 複核 P1：owner **直接收 window 引用**，在該引用自己的固定 root 上驗範圍與 lineage，並在同一 snapshot 切出所有 pair |
| `ExtractionSourceAdapter._owner_errors` | 複核 P2：單一錯誤邊界，沿 owner 既有轉換把祖先鏈缺失／超限映射成 `source_not_available` |

複核 P1 原本新增的 `window_bounds` 已**刪除**——它只為了那條錯誤流程存在。

**沒有**新增 parser、Agent loop、資料表、第二份游標、第二套流程或第二個原話 owner。訪談整理、驗證、更正、保存、續作、重抽全部留在 `caliburn_memory.extraction`，本片一行都沒改它。

### 來源接線（`ExtractionSourceAdapter`）

| B1 需要 | 接到既有 owner |
|---|---|
| `validate_reference` | `validate_window_reference`（只接受完成窗口；本輪 source 與 context 皆拒） |
| `extraction_windows` | `plan_saved_windows`（見下方 P1） |
| `read(ref, offset)` | window → `read_window`（分頁）；context → `read_context` |
| `validate_saved_window` | 同名 |
| `require_new_source_after` | `follows` |

規劃、分頁、重驗與 admission 的權威仍在 owner；adapter 只綁 document 並把固定錯誤碼翻成套件的可更正位址錯誤。

### 複核 P1：規劃曾經回到目前 head（來源分支污染）

複核抓到的是實質缺陷，不是文件問題。原本 `extraction_windows` 只從引用取出 `first_run_id`／`last_run_id`，接著 `plan_windows` 以 `_settled`（最新 discover）取材、`_window_root` 也以 `find`（同樣從最新 discover 起算）決定 root——**引用自己的 `root_checkpoint_id` 完全沒被使用**。兩個 sibling branch 的反例確認：來自已放棄分支的合法 token 不但沒被拒絕，還會在目前分支上重新產生 pair。若兩分支內容不同，B1 會把另一分支的工作當成原窗口內容。這違反 9/13 契約「固定 root、不回退 latest」。

修法**沒有**新增 parser、cursor 或 lineage 引擎：把規劃本體抽成 `_plan(...)`（在一組給定的 snapshot／root 上切 pair），再新增 `plan_saved_windows(window_ref, ...)`，它依序做四件事——在引用自己的固定位置讀回、以既有 `_on_lineage` 證明該 root 在本文件 canonical 鏈上、確認 `first`／`last` 在該 snapshot 上仍是完整的安全收尾回合邊界、然後在**同一個** snapshot 與 root 上發出全部 source／context pair。任一步不成立即 `invalid_ref`／`source_not_available`，不改用目前 head。`plan_windows`（以 run id 規劃目前範圍）沿用同一個 `_plan`，語意不變。

首敗：`plan_saved_windows` 不存在，以及 App 層 `start()` 對 sibling branch token **DID NOT RAISE**。

### 複核 P2：內部 checkpoint 例外穿過了 port 邊界

`plan_saved_windows` 走 `_on_lineage`／`_settled_turns` 時，祖先鏈缺失或超過 256 層查找上限會由 owner 拋出 `AiCheckpointError("original_run_lookup_required")`。adapter 原本只轉換 `ConversationSourceError`，所以 B1 呼叫端收到的是內部型別，而不是契約規定的 `source_not_available`。結果本來就是安全失敗（沒有模型呼叫、沒有 Store 產物、沒有 fallback），問題在錯誤邊界不一致。

修法是把四個做 I/O 的方法收進同一個 `_owner_errors()` 邊界，**沿 owner 既有的 `_pinned` 轉換規則**（`invalid_input` → 可更正位址，其餘 → `source_not_available`）。owner 自己的 `safe_turns` 仍照契約 §8 明示 `original_run_lookup_required`，那是「受限」而不是「沒有更早的回合」，本片沒有改它。**沒有新增錯誤引擎、重試引擎、歷史索引或資料表。**

### 用途授予（原複核指定隨接合驗的三項之一）

B1 的 extraction artifact 要驗 **source 與 context 兩個**引用，所以組裝用 `MemorySourceReader(..., window_references=True, context_references=True)`。C repair 與四個只讀工具維持 source-only 預設未改；B2 發布仍只收 window 作 `processed_source`。

## 2. OpenAI 接受條件：不是 HTTP 200 就算成功

`accepted(raw)` 用**已驗的同一組公開 SDK 欄位**判斷，沒有自己發明規則：無 refusal 區塊、且 `response_metadata["status"] == "completed"`。工作流程另外要求 `parsing_error is None` 與三個字串欄位的形狀成立。

2026-09-14 核 [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)：官方要求應用在信任結構化輸出前檢查三件事——`status` 為 `completed`、內容不是 `refusal`、符合 schema。**截斷**由同一個 `status` 表示：達到輸出上限的回覆是 `status: "incomplete"`、`incomplete_details.reason: "max_output_tokens"`，不會變成一個短的成功。這正好是上述三項，已驗邏輯不需改寫。

模型綁定設 `store=False`（權威記錄是本 App 的 Saver 與 Memory，不是 provider）。B1 的角色預算是**本案實測值**：顯式 `max_output_tokens=8192`、`reasoning.effort="high"`，不是廠商預設，也不是顧問的配置。

**審查 F3：已移除 `truncation` 參數。**2026-09-14 核 [Responses API create 參考](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)：`truncation` 已標為 deprecated，且 `disabled` **本來就是預設值**，該預設下「輸入超過模型上下文窗口，請求會以 400 失敗」。所以不送這個參數，行為完全不變——「不默默縮短來源」現在由兩件事保證：App 端的 `max_chars`／`context_chars` 來源預算（超大回合在呼叫模型前就 `WindowBudgetExceeded`），以及 provider 的 400。兩者都有固定案例。

**顧問的 Anthropic 設定完全未動**：沒有全 App provider 切換、沒有 fallback、沒有使用者選單。只有 B1 綁 OpenAI。

## 3. 相依性

**審查 F2：已改鎖現行版本。**初版沿用舊 CT checkout 的 `1.6.0`，這是錯的做法。2026-09-14 查官方 PyPI：`langchain-openai` 最新為 **1.6.2**（2026-09-09 發布；1.6.1 為 2026-09-08、1.6.0 為 2026-08-19）。其宣告需求為 `langchain-core>=1.6.2,<2`、`openai>=2.45.0,<4`、`tiktoken>=0.7,<1`，與本工作區既有的 `langchain-core 1.6.3`、`openai 3.13.0` 相容。

以 1.6.2 重跑**同一組** MockTransport request／structured output／拒絕／截斷／格式錯誤／重試／保存失敗／續作探針：**16 passed**，未見不相容，因此鎖 1.6.2。

| 依賴 | 版本 |
|---|---|
| `langchain-openai` | **1.6.2**（現行最新） |
| `regex`（transitive） | 2026.9.10 |
| `tiktoken`（transitive） | 0.14.0 |

未變：`langchain` 1.4.0、`langchain-core` 1.6.3、`langchain-anthropic` 1.7.2、`langgraph` 1.2.11、`langgraph-checkpoint` 4.2.0、`openai` 3.13.0。lock 差異只有新增這三個套件與本次的版本號調整，**既有套件一個都沒有升版**。

**要標明的差異：**已驗 CT50 profile 跑的是 `openai==3.8.0`，本工作區是 `3.13.0`。測試的合成回覆一律經**實際安裝的** SDK `Response` schema 驗證，所以線上形狀是對現行版本核過的；但 CT49／CT50 的自然品質結論是在 3.8.0 上取得的，不自動延伸。

## 4. 實際執行

首敗為 `ModuleNotFoundError: No module named 'jd_relational.extraction_app'`；審查修正的首敗為 context `turns` 的 `KeyError: 'turns'` 與 `assert 'truncation' not in request`。

實作中有 7 個首敗是**測試自身假設錯**，已修測試、**未放寬產品**：`InMemoryStore.batch` 唯讀故改用真 Store 子類、長訪談窗口的結尾是該輪回覆而非員工原話、預設預算下三輪只切成一個窗口所以沒有 context、LangGraph 會在錯誤訊息後附任務名、`capture` 需要最新一輪，以及本輪兩個——payload 的 `content` 是字串不是區塊陣列、原先選的預算組合根本產不出跨越整輪的 context（已改用 `max_chars=24／context_chars=12` 並補第四輪，才同時取得涵蓋 cancelled 與 completed 回合的 context；複核輪另補 failed 回合的 context fixture，關掉原本記為非阻擋的證據缺口）。

| 範圍 | 結果 |
|---|---|
| B1 接線案例（含審查與複核新增 6 例） | **19 passed** |
| 完成窗口來源案例（含 context turns 與 P1 lineage 新例） | **39 passed** |
| App 全離線測試 | **2798 passed／257 skipped／58.21s** |
| Memory 套件全測 | **146 passed** |
| 真 PostgreSQL 18：原話來源＋C 顧問接合＋Memory 核心 | **14 passed** |

**測試環境差異須記錄：**複核者的環境有 31 個 `WinError 5` 暫存目錄權限錯誤，排除 Windows 設定檔測試後為 2762 passed，無法重現 2793。本機這次跑到 **2797 passed／257 skipped、0 error**，`test_config_file.py`／`test_configured_host*.py` 全過。這些案例用的是 pytest `tmp_path`，所以差異在系統 `TEMP` 的權限或防毒鎖檔，不在產品程式；可用 `pytest --basetemp=<可寫目錄>` 指定另一個位置再核。**在對方環境能跑完之前，不把「全綠」當成跨環境已證實。**

**另外發現並修掉一個既有的不穩定測試（與 B1 無關）。**`test_chat_history.py` 的 cursor 竄改案例把簽章 token 的**最後一個字元**翻掉，但 base64url 尾字元帶有解碼時被丟棄的補位位元，因此翻掉它有機率完全不改變簽章。實測 2000 次取樣：**119 次（5.9%）竄改後仍然合法**，該案例因此本來就會偶發假通過／假失敗。改為竄改 payload 第一個字元（4000 次取樣 0 次仍合法），連跑三次 45 passed。這是既有缺陷，不是本次改動造成，但它會污染所有「全綠」宣稱，所以一併修並分開提交。

固定情境涵蓋工作單位要求的七項與四項驗證：

| 情境 | 結果 |
|---|---|
| 正常完成 | 三欄位成稿；`source_window` 讀回的**就是**該窗口自己的 `{source_reference, context_reference}` 原對 |
| 拒絕 | `refusal` 區塊 → 明示失敗，Store 內沒有任何 interview 產物 |
| 截斷 | `status: incomplete` ／ `max_output_tokens` → 明示失敗，未保存 |
| 格式錯誤 | 缺欄位的結構 → 明示失敗，未保存 |
| 不可讀格式 | 2100 字元單行先被拒，帶 runtime feedback 更正一次後才保存 |
| 重試 | 500 後重試成功 = **2 次 HTTP、1 個模型步、1 組產物**，不會變成兩個窗口 |
| 保存失敗 | 真 Store 注入一次寫入故障；`resume()` 續作**沒有再呼叫模型** |
| 已完成內容 | 窗口只涵蓋安全收尾的回合，出站 payload 帶真實員工原話 |
| 分頁讀取 | 超過單頁 3000 字元的窗口逐頁讀回完整原話，每頁都完整列出 turns |
| 來源重驗 | 同批每個規劃 pair 都在自己的固定位置重驗通過 |
| context 權限 | context 可讀（供消歧）但**不可**作為 B1 入口；本輪 source 兩者皆拒 |
| context 回合終局（F1） | 跨越整輪的 context 回報該輪自己的 `status`／`answer_succeeded`，cancelled、failed 與 completed 都有案例；只含前置 AI 問句時為空。adapter 原樣轉交 owner 的投影 |
| 來源預算 | 超大回合 `WindowBudgetExceeded`，**0 次 HTTP**，不截斷 |
| provider 輸入過長（F3） | 400 明示失敗、未保存，不默默縮短 |
| 重抽（W-13） | 讀回**原**窗口與**原** context，正常 B1 輸入位置不前進 |
| 固定 root 規劃（P1） | 追加新回合後，同一 saved window 規劃結果**逐字相同**，讀回不含新回合原話 |
| sibling branch（P1） | 已放棄分支的 token 在 `start()` 即被拒，**0 次 HTTP**、Store 無產物；該 token 仍可作歷史讀取 |
| 祖先查找上限（P2） | 超過 256 層時四個 I/O 方法與 `start()` 一致回 `source_not_available`（不是內部 `AiCheckpointError`），**0 次 HTTP**、Store 無產物、不回退 latest |
| 出站請求 | `store=false`、**不送已淘汰的 `truncation`**、`json_schema` + `strict=true`、三欄位 schema、8192、effort high |

替身只有一個：provider 的 HTTP 傳輸（`httpx.MockTransport`，回覆經實際 SDK schema 驗證）。來源 owner、Saver、Store、SDK、結構化輸出綁定全部是真的。**0 provider、付費 0**；`api_key` 是必填參數，程式不讀環境變數、不內建任何端點。

## 5. 限制與未完成

1. **沒有呼叫真模型**，沒有自然品質、真人或成本證據；真模型另需當次明示費用授權。
2. **B1 尚未被 App runtime 觸發**：`build_extraction_workflow` 可組裝，但宿主啟停、背景准入、排空與新程序續作（映射 §3.3–3.4）未接，模型 id／金鑰／配置也還沒接上本機設定。
3. **本片證據不能外推成正式 App／資料庫完成（審查 F4）**：13＋3 個接線案例用的是 MockTransport、InMemorySaver、InMemoryStore；表中的 PostgreSQL 14 案例是**原話來源、C 接合與 Memory 核心**，**不是 B1 的 PostgreSQL 執行**，不重複計為 B1 證據。B1 的真 PG 保存／續作／冪等與設定接線留給下一個 runtime 工作單位。
4. `openai` SDK 版本與 CT profile 不同（3.13.0 vs 3.8.0），見 §3；線上形狀已對現行版本核過，自然品質結論不延伸。
5. B2 採用、背景接合、整理通知完整單位、H4 完整旅程與自然品質（OI-09）都未開始。
6. 沒有新增資料表、第二份游標、第二個原話 owner；正式產品（`apps/api`／`apps/web`／`packages/job-analysis-contract`）未改，ADR0074／0075 Proposed、production 0060 不變。
