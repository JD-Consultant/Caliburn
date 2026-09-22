# B1 App adapter 複核結果

2026-09-14；本稿先記錄複核提交 `68c45a61`（`jd-b1-adapter-review-fix-20260914`）與獨立測試修正 `5a5f1af5`，後附 `0372ad3e` 的 P1 修正複核。前段數字與未完項是 68c45a61 當時狀態；目前狀態以「P1 修正複核」及其後的窄修界線為準。本稿承接 [第一次審查](app-wiring-review.md)，對照 9/13 採用映射、完成窗口契約、B1 核心採用審查及目前決策入口。

**最新狀態（2026-09-14）：**`0372ad3e` 的 P1、`beb8aa8f` 的 P2 錯誤邊界、`3921a99d` 的 F-04 pair proof，以及 `f160be97` 的 P3 已完成窄修／證據補強。獨立窄跑確認新 pair 規則沒有波及 H2–H3 的 source-only reader；已在保存驗證之外直接寫入錯配 artifact，再由 `source_window` 拒絕，並以移除讀回檢查轉紅確認案例鑑別力。B1 adapter 的固定接合目前可視為**程式與固定證據通過**，但完整 B1 工作單位仍不等於正式 runtime 接入，真 PostgreSQL 保存、背景恢復、B2 與自然模型驗收仍未開始。

## 結論

本片原有四項 finding、後續 P1、P2 錯誤邊界與 F-04 pair 均按原界線修正，沒有新增第二套流程、parser、cursor、資料表或 provider fallback。上方的原結論與 P1／P2 開放段落保留作歷史；固定接合的程式修正可關閉，但仍不是 B1 runtime 或完整 App 驗收。

| Finding | 複核結果 | 證據 |
|---|---|---|
| F1：context 清掉 `turns` | **已閉合**。同一 source owner 在固定位置投影範圍內可證明的 settled turns，adapter 原樣傳遞；context 仍不可作 B1 admission，只有前置 AI 問句時才是空集合。 | `test_extraction_app.py` 16 passed；`test_interview_window_source.py` 37 passed，含 cancelled／completed 與 questions-only 情境 |
| F2：沿用舊 `langchain-openai` pin | **已閉合**。改鎖官方現行 1.6.2，使用本工作區實際 SDK 重新核 request、structured output、拒絕、截斷、重試、保存失敗與續作探針。 | B1 adapter 16 passed；lock 只改本套件版本與其對應雜湊 |
| F3：送出 deprecated `truncation` | **已閉合**。不再送參數；來源超界在模型前以 `WindowBudgetExceeded` 失敗，provider 輸入超界以 400 失敗，兩者都不保存短版結果。 | `test_extraction_app.py` 的來源預算與 provider 400 案例 |
| F4：把固定接線寫成完整接入 | **已閉合**。結果稿現在明列核心、adapter 固定接合、runtime 三層；PostgreSQL 14 案例不再算 B1 PG 證據。 | `app-wiring-results.md` §1、§5 |

游標測試另以 `5a5f1af5` 修正尾端 base64url 補位造成的簽章竄改假陽性；目前 `test_chat_history.py` 45 passed。這是既有測試可靠性修正，與 B1 產品語意分開。

## 新增 P1：初次輸入窗口沒有保留固定 root

`ExtractionSourceAdapter.extraction_windows()` 先呼叫 `window_bounds()` 取出 `first_run_id`／`last_run_id`，再呼叫 `ConversationSourceService.plan_windows()`。後者從目前 `discover()` 的 canonical head 重新取得 `safe_turns`，並由 `last_run_id` 的當前 terminal 選 root；它沒有驗證輸入窗口自己的 `root_checkpoint_id`，也沒有用該固定位置規劃輸出。

在同一份文件建立兩個 sibling checkpoint branch，讓兩邊的訊息 ID 與內容相同，從已放棄 branch 發出的合法 `window` token 會通過 `extraction_windows()`，而輸出的新 pair 已換成目前 branch 的 root。這正是 9/13 契約 §3.2–§3.3 禁止的「讀到合法內容但位置不是原發配 root」情境；同 ID／同內容不能證明 lineage。若分支內容不同，B1 會把另一分支的工作當成原窗口整理，屬內容污染。

**修正界線：**不在 adapter 另造 parser 或 lineage 引擎。讓同一 source owner 接受輸入 `window` 引用，於其固定 root 讀回並驗證 `first`／`last`、回合終局及必要的 canonical lineage，再在同一固定 snapshot 上產生所有 `{source_reference, context_reference}`；輸出 pair 的 root 必須等於輸入窗口的 root。補初次 `start()`（尚無既有 B1 游標）對 sibling branch 的反例，以及追加新 head 後仍讀原固定 root 的案例。若無法證明固定位置，明示 `invalid_ref`／`source_not_available`，不改用目前 head。

本次獨立重跑結果為 B1 adapter **16 passed**、完成窗口來源 **37 passed**、游標 **45 passed**；排除與本片無關的 Windows DPAPI 設定檔案例後，App 離線套件 **2762 passed／257 skipped／31 deselected**。完整組第一次重跑的 31 個設定檔案例在 pytest 暫存根目錄讀取時遇到 `WinError 5`，因此不能把本機完整組宣稱為全綠；這是測試環境權限問題，並未出現在上述受影響案例。

## 剩餘界線（P1 複核當時的狀態）

以下不是本片 finding，仍須下一個工作單位完成：

- B1 尚未由正式 App runtime 觸發；背景准入／排空、宿主重開、模型設定與金鑰、真 PostgreSQL B1 保存／續作／冪等尚未驗證。
- 沒有真 provider、自然模型品質、長訪談或員工操作證據；既有 CT49／CT50 結論不因 adapter 固定測試自動延伸。
- `failed` context turn 的專用 fixture 尚未另列；現有案例已覆蓋相同非成功分支的 `cancelled`。若要宣稱兩種錯誤終局都獨立驗證，應在不改產品邏輯的情況下補一個窄案例。
- P1 修正完成前，不能將 B1 adapter 標為已完成；其餘 runtime／真 PostgreSQL／自然模型界線維持不變。

## P1 修正複核（2026-09-14）

後續提交 `0372ad3e`／tag `jd-b1-pinned-planning-20260914` 已按本稿的修正界線處理原 P1，以下取代上方「P1 修正完成前」的暫時狀態；上方舊段落保留作為發現沿革，前段的 16／37 測試數與 failed-context 未列項也只代表當時複核。

- `ConversationSourceService.plan_saved_windows(window_ref, ...)` 直接接收完整 window 引用，在引用自己的 `root_checkpoint_id` 讀取固定 snapshot，沿既有 `_on_lineage` 核對 canonical lineage，並在同一 snapshot／root 上驗證完整 settled-turn bounds 後產生所有 source/context pair。
- `ExtractionSourceAdapter.extraction_windows()` 已改呼叫該 owner 方法；`window_bounds` 已刪除。沒有新增 parser、cursor、lineage 引擎、資料表或第二個原話 owner。
- sibling branch 的合法簽章 token 在 B1 `start()` 的第一次模型呼叫前拒絕（0 次 HTTP、無 Store 產物），追加新回合後同一 saved window 的規劃結果與讀回內容保持不變。這兩項正好覆蓋原 P1 的「不重規劃到 current head」反例。

本次獨立窄複核執行 `test_extraction_app.py`、`test_interview_window_source.py`、`test_chat_history.py` 共 **102 passed**；另確認 `git diff --check` 無輸出。實作者報告的 2797／257 是其環境結果，本複核不把它當成跨環境證據；目前仍須用可寫的 pytest 暫存根目錄在受限環境重跑設定檔案例。

### 尚需窄修的錯誤邊界（P2，未阻擋本次 P1 關閉）

以超過 `MAX_PARENT_LOOKUPS` 的固定鏈實測，`plan_saved_windows()` 目前會從 `_settled()` 直接拋出 `AiCheckpointError("original_run_lookup_required")`；`ExtractionSourceAdapter` 只轉換 `ConversationSourceError`，因此 B1 呼叫端拿到的是內部例外，而不是 source owner 契約使用的 `invalid_ref`／`source_not_available` 兩種錯誤。這仍然是明示受限、沒有 fallback 或產物的安全結果，但與結果稿「任一步不成立即 `invalid_ref`／`source_not_available`」的宣稱不完全一致，也沒有專用案例鎖住 adapter 邊界。

下一個有限修正應只做錯誤邊界對齊：沿既有 owner／adapter 的錯誤轉換，為超限／缺鏈建立一個窄案例，確認不呼叫 provider、不寫 Store、不重設游標；不要新增錯誤引擎、重試或歷史索引。完成前，結果稿應把此列為 P2 邊界，不宣稱 B1 adapter 的所有來源失敗都已完成統一映射。

官方依據仍是 [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)、[Responses API create](https://developers.openai.com/api/reference/cli/resources/responses/methods/create) 與 [langchain-openai PyPI](https://pypi.org/project/langchain-openai/)；這些只支持本片的 provider／版本判定，不替代 runtime 或自然品質驗收。

## P2 修正複核（2026-09-14）

提交 `beb8aa8f`／tag `jd-b1-error-boundary-20260914` 已閉合上述錯誤邊界。`ExtractionSourceAdapter` 以單一 `_owner_errors()` 包住 `extraction_windows`、`read`、`validate_saved_window` 與 `require_new_source_after`（另涵蓋 reference validation），沿 owner 已有 `_pinned` 規則把 `AiCheckpointError("invalid_input")` 轉為可更正的 `InvalidSourceReference`，其餘 checkpoint 缺鏈／查找超限轉為公開 `ConversationSourceError("source_not_available")`。`safe_turns` 仍保留 owner 的 `original_run_lookup_required`，因為那是 owner 端「受限」證據，不是 B1 port 的公開契約；沒有改寫既有歷史查找語意。

新增的超限案例逐一驗證四個 I/O 方法及 `start()`：均回 `source_not_available`，沒有 HTTP、Store 產物或 latest fallback。獨立重跑 `test_extraction_app.py`、`test_interview_window_source.py`、`test_chat_history.py` 為 **103 passed**；本結果仍是固定測試，沒有 provider、真 PostgreSQL B1 保存或自然模型證據。這與 9/12–9/13 的錯誤契約「明示失敗、不猜、不截斷」一致。

P2 錯誤邊界本身 **CLOSED**。F-04 後續修正見本文末段；其餘工作才按接續計畫進入 B1 runtime 觸發與真 PostgreSQL 保存。不要重做 source port 或另造錯誤／重試／歷史引擎。

## 後續複核 F-04：source/context pair 的證明與複核（2026-09-14）

`3921a99d`／tag `jd-b1-pair-proof-20260914` 已修正先前的交叉配對缺口。`_ContextPosition` 升為 v2，簽章內容記錄它所屬 source window 的固定 `source_first`／`source_last`；`_plan` 先發 source window，再以同一固定 root／snapshot 發 context。`validate_window_pair` 只由 source owner 比對同 root 及這兩個窗口界線，並由 `validate_saved_window`（重抽）、`MemoryArtifacts.save_extraction`（保存）與 `MemoryArtifacts.source_window`（讀回）共用。v1 context token 沒有 pair 證明，明示拒絕，不回退或猜測。

這個修法仍維持 9/13 的責任界線：沒有新資料表、第二個 cursor、Web 端配對、通用配對引擎或第二個原話 owner；只讀工具與 C repair 使用 source-only reader，不被要求提供 B1 pair proof。`test_memory_read_tools.py` 與 `test_consultant_memory_context.py` 獨立重跑 **40 passed**，確認 source-only 行為未被擴張。

F-04 的固定情境已包含成功 pair、相鄰窗口交叉 pair、不同 root、v1 格式、保存→讀回→重抽往返。`f160be97` 再補一個先正常保存、再直接覆寫 summary header 的已保存 artifact 反例（測試後端為 `InMemoryStore`）；`source_window` 讀回拒絕；**實作者報告**拿掉讀回檢查時同一案例以 `DID NOT RAISE` 轉紅。獨立複核執行的是正常反例，未另跑該變異，不把兩者混稱。這完成 P3 證據補強，證明的是既有讀回檢查的鑑別力，不是新增產品邏輯，也不等同真 PostgreSQL／實體磁碟證據。B1／窗口／游標三組獨立窄跑目前 **109 passed**；F-04／P3 可關閉。

**版本界線：**v1 context不帶pair證明，仍明示拒絕；固定fixture用v2。按既定fresh-data範圍不新增轉換工作、不阻R1施工、不清既有資料；若日常啟用真的遇到需保留的舊工作再明示影響。整體範圍與下一步以[9/14整體審查](whole-flow-review.md)為準。

原先的 F-04 發現與探針保留如下，作為修正前的歷史記錄。

### 修正前探針（歷史）

9/13 契約 §3.3 要求每個 planned window 保存由同一 owner 發出的不可變 `{source_reference, context_reference}`，重抽只能讀回原 pair；9/13 審查也明定此項留給 B1 adapter 驗收。`beb8aa8f` 沒有修改 pair 驗證：`MemoryArtifacts.save_extraction`／`source_window` 只各自驗證兩個 token，`ConversationSourceService.validate_saved_window` 只核同 root、內容範圍與預算，沒有證明 context 是該 source 規劃出的那一對。

獨立固定探針以同一 root 的三個 planned windows 取 `planned[0].source_reference` 加 `planned[1].context_reference`，呼叫 `ExtractionSourceAdapter.validate_saved_window`，結果為 **ACCEPTED**。這不是 provider 或資料庫故障，而是能讓重抽使用錯誤消歧上下文的可重現契約缺口。

處理要求保持最小：由 source owner／B1 adapter 研究並採用一個能從 token 或既有固定資料證明 pair 身分的做法（例如在發出的 context 位置綁定其對應 source 的穩定摘要，或等價的 owner-owned pair proof），在 `save_extraction`／`source_window`／`validate_saved_window` 同一邊界拒絕交叉 pair。不得讓 Web 猜配對、按名稱重組、回到 latest 重規劃，亦不得新增通用配對引擎或第二份 cursor。需補成功 pair、交叉 pair、不同 root、重開重抽與舊格式明示處理案例；在此完成前不能把 B1 adapter 或 W-13 宣稱為完整通過。
