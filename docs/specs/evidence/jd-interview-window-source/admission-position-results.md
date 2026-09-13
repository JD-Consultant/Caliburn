# 完成窗口：非末尾窗口重驗身分與新窗口 admission 的固定位置

2026-09-13；JD-R002／OI-01、OI-02。依[c1c9f8f7 複核](cursor-lineage-review.md) R-01／R-02 修正，基準 `503ba37e`／tag `jd-window-cursor-lineage-20260913`。0 provider、沒有新增資料表、沒有第二份游標。**本片只修這兩項**，不接 B1、不做整理通知、不改契約。

## R-01：整批共同 root，重驗卻用了窗口自己的回合身分

`plan_windows` 是對的：一次規劃的所有窗口固定在**同一個** root，位置也已經刻意分開 `root_run_id`（讀回該位置的身分）與 `last_run_id`（這個窗口的範圍終點）。錯的是 `validate_saved_window` 讀回時拿 `last_run_id` 去開那個共同 root。

`observe_at` 會核對該 root 的 run record 身分是否等於傳入的 run：只有整批**最後一個**窗口兩者才相同，前面每一個都回 `run_not_found`，再被 `_pinned` 轉成 `source_not_available`。也就是說，程式自己剛發出的合法 pair，除了最後一個以外都無法重驗——而已驗 B1 的 `reextract` 正是先呼叫 `validate_saved_window`，接上去就會擋住前面所有窗口的重抽。

原測試只取 `planned[-1]`，恰好避開這個差異，所以先前全綠。

### 修法

一行：改用 token 裡既有的 `root_run_id` 讀回原固定位置。預算檢查、用途檢查、`read_window` 的範圍核對都不動；**不改 planner 為每個窗口另取 root，也不重新發配 pair**。

新案例遍歷**所有**公開規劃出來的 pair（`max_chars=20`／`context_chars=10` 產生多窗口），逐一 `read_window` 再 `validate_saved_window`；接著再追加一輪訪談，確認每個 pair 讀回的頁面與先前**完全相同**——原 pair、原文字不隨最新位置前進。

## R-02：`follows` 證明了舊游標在最新 head 上，沒有證明新窗口在哪裡

`_cursor_boundary` 這次已經會打開舊游標自己的固定位置，但 `follows` 傳進去的 `observed` 是**目前最新 head**，而新窗口 `reference` 只被解碼、取用 `new.first`。新窗口自己的固定 root 從頭到尾沒有被核對。

契約 §7.2 要求的是舊游標的固定位置為**新窗口固定位置**的祖先、兩端在同一條 canonical 鏈；只證明舊游標在 latest 上並不成立。

反例完全走公開發配：從第二輪終局產生 A 分支，在 A 上發配第二輪窗口；再從**相同**終局產生 B 兄弟分支當目前 head。兩分支訊息完全相同，舊游標是第一輪、是兩者的共同祖先，所以任何只比對「游標→latest」或「游標→新 root」的檢查都會放行。原生 parent 鏈證明 A 不是 B 的祖先；`read_window(candidate)` 仍讀得到它保存的內容，`follows` 卻沒有拒絕。

**可以當歷史讀回，不等於可以當目前新批次的輸入。**

### 修法

`follows` 改成每個引用都在**自己的**固定位置上比較：

1. 新窗口的固定 root 必須在本文件 canonical 鏈上（就是目前位置，或經 `ancestor_of` 證明為真祖先）
2. 舊游標仍走共用的 `_cursor_boundary`，但對象換成**新窗口自己的位置**，不是最新 head
3. 先後與連續性用新窗口自己保存的訊息序列判斷
4. 新窗口的 `last` 必須正好等於該位置上某個安全收尾回合的 `last`

把「這個 checkpoint 是否在這條鏈上」抽成 `_on_lineage`，是既有 `AiRunHistory.ancestor_of` 的共用小包裝，`_cursor_boundary` 一併改用同一個。**沒有新增 lineage 表、通用分支管理、第二份游標或 latest fallback**，走鏈仍是 `find` 用的同一組公開 parent 連結與同一個 `MAX_PARENT_LOOKUPS` 上限。

同 root、正常祖先、同批連續窗口的既有正向案例全部保留通過；歷史重抽仍走獨立重抽路徑，不套新 admission 規則。

## 實際執行

首敗與複核描述一致，逐字保留：

| 反例 | 首敗 |
|---|---|
| 遍歷整批規劃 pair 重驗 | `ConversationSourceError: source_not_available`（`conversation_sources.py:797`） |
| 兄弟分支的候選窗口 | `Failed: DID NOT RAISE ConversationSourceError` |

| 範圍 | 結果 |
|---|---|
| 窗口來源＋歷史（含 2 個新案例） | **57 passed／7.84s** |
| 受影響來源／Memory／checkpoint 檔案 | **253 passed／13.32s** |
| App 全離線測試 | **2776 passed／257 skipped／60.63s** |
| Memory 套件全測 | **130 passed／5.89s** |
| 真 PG18：原話來源＋C 顧問接合＋Memory 核心 | **14 passed／14.80s** |
| [複核當時的兩個探針](review-c1c9f8f7-probes.py)（修正後重跑） | **2 passed／4.42s** |

探針檔保留為複核當時的證據，案例已依複核要求轉入 `tests/test_interview_window_source.py`；探針不在 `testpaths` 內，不會被日常收集。真 PG18 為既有 `compose.test.yaml` 的隔離測試庫，未動產品 DB。付費 0，沒有自然模型、真瀏覽器或新 Windows 程序證據。

## 仍然開著的（不在本片）

- **W-13／`reextract` 與正常 B1 輸入位置不前進**、**保存 pair 的不可變性**、**用途感知讀取**：依複核判定，隨 B1／B2 實際 adapter 一次驗收，**不現在另造配對系統或中間引擎**。
- 整理通知的工具註冊、結果分類、關閉／停止恢復仍是一個完整工作單位，未開始；不借 JD operation 或 C publication。
- H4、完整旅程與自然品質（OI-09）未開始；日常 AI 未啟用。

## 界線

1. 本片**只修 R-01／R-02**，不代表完成窗口能力已接通 B1／B2 或 H4 已完成。
2. 沒有新增資料表、第二份游標、第二個原話 owner；planner、[窗口契約](../../2026-09-13-jd-interview-window-source-contract.md)、B1／B2 prompt 與角色配置皆未改。
3. C repair 與四個只讀工具的 source port 未改，用途隔離不變。
4. 正式產品（`apps/api`／`apps/web`／`packages/job-analysis-contract`）未改；ADR0074／0075 Proposed、production 0060 不變。
