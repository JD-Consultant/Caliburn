# 本階段獨立審查：發現、修正與處置

日期：2026-09-14；Topic：JD-R002。審查範圍 `151d1858..HEAD`（19 個提交）的產品程式、文件宣稱、採用保真度與測試鑑別力。審查者不是實作者，只讀不改；修正由實作者做，之後另請同一審查者窄複核。

## 1. 一句話

**兩個真缺陷共同的毛病是：把「不知道」說成「知道」。**其餘六項是較小的一致性問題。八項全部修正，tag `jd-review-fixes-20260914`。

## 2. 發現與處置

| # | 嚴重度 | 發現 | 處置 |
|---|---|---|---|
| A1 | HIGH | 來源讀取失敗被回報成「這段訪談不在了」。source owner 把「原回合真的沒了」與「讀取當下失敗」都收斂成 `source_not_available`，這一層分不出來，卻回 `target_missing`（404、`reread_current`），等於請員工從一個沒人握有的結果繼續走 | 改回 `read_failed`（500、`stop`）。分不出來就不宣稱；理由寫進程式註解 |
| A2 | HIGH | 移除金鑰失敗被回報成「原本就沒有金鑰」且 exit 0。操作者交機前清金鑰，被告知從未設過，**而金鑰仍在** | 只有 Windows 自己的 not-found（1168）算「沒有」，其餘回 `credential_delete_failed` |
| A3 | MEDIUM | 任何 `CredRead` 失敗都被讀成「尚未設定」；`configured_roles` 還吞掉 `ProviderKeyError`，所以 `status` 永遠說得出一個答案 | 同上分辨；`configured_roles` 不再吞錯，讀不到就說讀不到 |
| A4 | MEDIUM | 寫入端拒絕的收據形狀，讀取端不拒絕。被改寫的列可以讓一次 AI 編輯以「員工把你整輪取回」的身分進入下一輪通知 | `ReceiptBody` 驗證器補上同一條規則 |
| A5 | LOW | `no_change` 的撤回／還原仍寫入「放回了某一版」的宣稱 | `body_for` 要求 `status == "committed"`；`no_change` 路徑不再傳 |
| A7 | LOW | 來源面板沒有世代守衛：關閉後晚到的回應會把面板重開，快速切換兩個標記會互相蓋掉 | 加上 `sourceGeneration`，關閉與 onClose 都遞增 |
| A8 | LOW | 非互動式 `set-key` 說「金鑰內容不符合格式」，真正原因是沒有可輸入的終端機 | 改為 `interactive_key_entry_required` 與對應訊息 |
| A9 | LOW | 本輪通知帶裸的 `ai_run_id`，而同一份通知裡其他識別都是簽章引用 | 改成 `took_back_an_ai_turn: true` 標記；模型沒有任何工具吃 run id |
| A10 | LOW | `/jd/restore/preview` 與 `/jd/sources/read` 在診斷紀錄裡記成 `unmatched` | 兩條都列入 `QueryBoundary.routes` |

**A6 維持原樣：**背景可用性提示在回合關鍵路徑上，讀取失敗會讓該回合失敗。審查者認為「大聲失敗」在此可辯護但未記錄。這是刻意的：這個模組存在的理由就是避免把未整理的資料當成已記得，安靜地略過提示正是它要防的事。已記在此處。

## 3. 測試鑑別力

| # | 發現 | 處置 |
|---|---|---|
| D1 | `test_an_unexpected_owner_failure_stays_a_safe_code` 用真 owner 不會丟的 `RuntimeError` 測 `read_failed`，**A1 就是因此沒被發現** | 該案例明確標為防禦性；另加兩個依 owner 真實錯誤形狀的案例 |
| D2 | `assert set(before) == db.JD_TABLE_NAMES` 永遠不會失敗——`row_state` 正是用同一份 metadata 建出來的 | 改成比對 `JD_CONTENT_TABLE_NAMES ∪ {jd_memory_admission}`，新表必須被刻意放進來 |

D2 那條是我上一輪自己寫進去的：為了修表數硬編碼，換成了一個看起來更嚴謹、實際上不可能失敗的斷言。

## 4. 審查者獨立核對通過的部分

- 採用保真度：`skills.py` 與三個 `SKILL.md` 對 `033540ce` **位元組相同**；`MEMORY_ACTION_GUIDANCE` 以 AST 取出比對逐字相同，sha256 與 `adoption.json` 的 `instructions_sha256` 相符。
- `_undo_target`／`_restore_target` 的來源推導：run 範圍是**證明**出來的（依 `ai_run_id` 選已提交列、強制單一不斷鏈、必須終止於目前 head），不是照單全收。
- 不可偏離的產品效果在本 diff 上成立：還原與撤回共用同一 `_edit_locked` → `prepare_restore` → 單一 `JdStorage` 交易；`SourceReadService` 包既有 owner 而不自己擁有；兩個人工命令都不在模型工具集中；撤回後 checkpoint 列未減少。
- 分頁斷言那次修改**不是**為綠燈改測試：契約原文與實作、Web client 一致，被改的斷言才是離群值，且替換後更嚴格。
- 重跑三個套件與 wheel 內容，數字與宣稱相符。

## 5. 文件更正

`2026-09-14-jd-source-readback-slice.md` 原本寫「未預期的失敗只留 `read_failed`」，在修正前是假的（A1）——已改寫成實際行為並說明為什麼。`consultant_guidance.py` 註解寫「Ten sentences」，實際 11 句，已更正。

## 6. 修正後狀態

真 PG 全組 **3258 passed、0 failed**；Web **305 passed**；契約生成與 `tsc` 通過。兩個 HIGH 修正各做變異驗證（改回原行為→對應反例失敗；還原後以 `git hash-object` 確認）。窄複核已請同一審查者進行，結果另記。
