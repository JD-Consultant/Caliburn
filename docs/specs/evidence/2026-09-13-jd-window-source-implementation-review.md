# 完成窗口 source port 實作與固定情境審查

日期：2026-09-13。審查範圍為 `78ce5689`、`cc179ab1`、`78992ad1`、`38d6f6d9`、`bdc28ce2` 及其 tags，並對照 9/12 關聯式保存／Agent 工具契約、9/13 App source integration、顧問 context、B1／B2 adoption mapping，以及 9/06 Memory 整理節奏研究。這是 source port 的審查，不是 H4、B1／B2 或自然訪談的採用驗收。

## 結論

**整體方向可以保留，但目前不能把 W-01–W-14 宣稱為全部完成，也不能進入 B1／B2 採用。** 最新切片的停止判斷是正確的：整理通知不能只註冊一半；目前 `consultant_tools.prepare`、`ai_runtime._verify_saved_results` 與 `_settle` 尚未形成純通知的完整結果分類及停止契約，應留給同一個完整工作單位處理。

我在目前 HEAD 以隔離環境獨立執行 `tests/test_interview_window_source.py`，結果為 **30 passed**。這證明現有固定案例通過，不足以證明契約列出的所有語意已被測到；下列缺口須在 H4 前閉合。

## 發現

### F-01／P1：admission 沒有真的核對 cursor 的 lineage 與完整回合邊界

契約 §7.2 要求比較 `processed_source` 前，證明兩個引用位於同一條 canonical root ancestor lineage，並拒絕不完整 boundary。實作的 `ConversationSourceService._after_cursor`（`conversation_sources.py`）只解析簽章、確認 `position.last` 出現在目前訊息 ID 清單，再用位置索引計算下一輪；`follows` 也只比較目前訊息順序。兩者都沒有：

- 在引用自己的固定 root 讀取並確認 root 與目前 canonical root 的祖先關係；
- 確認 `first`／`last` 是完整、已安全收尾回合的邊界，而不是回合中間的 AI／tool message；
- 確認 `last_run_id`、固定 root 及範圍欄位彼此一致。

目前 W-08 測試只涵蓋不存在的 `last`／不存在 root，並沒有同 ID 的分支 lineage 或合法簽章的 mid-turn cursor。這不符合 9/13 契約明定的「同 ID 不足以證明 lineage」及「不完整 boundary 不得默認已處理」。若舊 cursor 來自另一個分支或錯誤邊界，背景可能跳過未處理原話或把部分回合當成已發布。

**處理要求：**先在 source owner 補一個固定位置的 boundary／lineage 驗證，讓 `_after_cursor` 與 `follows` 共用；新增分支、mid-turn、root 不可追溯的固定反例。不要用最新 snapshot fallback，也不要新增第二份 cursor。這是 B1 admission 前的阻擋項。

### F-02／P1：W-13 只有重新驗證測試，沒有重抽與輸入位置證據

契約 W-13 要求「重抽已保存窗口讀回原窗口內容，且正常 B1 輸入位置不前進」。目前 `test_a_saved_window_is_revalidated_without_being_replanned` 只呼叫 `validate_saved_window`，再測預算變小時失敗；它沒有執行 `reextract`／B1 adapter，也沒有證明新回合加入後仍讀原 root，或正常 B1 的輸入位置保持不變。現況文件其實也承認 B1／B2 尚未採用，因此這是**驗收宣稱過寬**，不是要求現在偷偷接一套 B1。

**處理要求：**把 W-13 改標為「source 層部分證據」，在 B1 adapter 接上後補一個不可變 pair 重抽案例及 cursor 不前進斷言；完成前不得把 W-13 算作完整通過。

### F-03／P2：W-14 沒有測到 `>256` ancestor，只測到缺鏈

`bdc28ce2` 的案例透過 root input checkpoint 保存失敗製造缺鏈，確認 `original_run_lookup_required` 會向上傳遞；這個行為與既有 `AiRunHistory` 一致，判斷「不是產品修復」正確。但契約 W-14 同時列出「缺鏈／超過 256 祖先」，目前沒有超過 `MAX_PARENT_LOOKUPS` 的固定鏈案例，不能用缺鏈案例代表兩者。

**處理要求：**以不呼叫 provider 的 synthetic checkpointer 建立 257 層以上祖先，確認仍明示 `original_run_lookup_required`，並保留缺鏈案例。這是證據補齊，不應因此重寫歷史查找器。

### F-04／P2：保存的 source/context pair 尚未驗證「是同一個規劃 pair」

`validate_saved_window` 目前驗證 window／context 的簽章、scope、同 root 與預算，但沒有確認傳入的 `context_reference` 是該 source window 規劃時產生的那一對，或至少符合該 source 所需的最近前置問題語意。兩個同 root、各自合法的 context token 可以被交叉配對。舊 B1 的 `validate_saved_window` 也沒有提供這個保護，因此不應現在另造通用配對引擎；但 9/13 新契約已把 pair 定為不可變輸入，B1 artifact adapter 必須保存並驗證原 pair，並加入交叉配對反例，否則不能宣稱重抽忠實使用原規劃上下文。

### F-05／P2：Memory reader 的讀取 grant 是已知接線缺口，不是本片完成

`MemorySourceReader` 已能依 `window_references`／`context_references` 分開驗證用途，並證明未授予的 publication reader 會拒絕 window；但 `read()` 仍只呼叫當輪 `ConversationSourceService.read`，尚不能讀 `read_window`／`read_context`。這和結果稿的界線一致，沒有把它誤判成已接通；在 B1／B2 adapter 前仍是明確阻擋，不能只靠 validation 通過。

## 已確認正確的部分

- `pending_windows`（明示整理通知）與 `unprocessed_source`（連續安全範圍）已分開；沒有通知的相鄰安全回合不會被漏掉，未收尾缺口也不會被後面通知跳過。
- `source`、`window`、`context` 使用同一 owner 的 codec／key／dataset，但獨立簽章 domain；用途互換會拒絕，沒有引入舊無簽章 parser、第二份原話庫或第二份 cursor。
- 安全終局逐輪檢查 `record.status != running` 與 `observed.closed`；`failed`／`cancelled` 仍保留員工原話並標示 `answer_succeeded=false`。
- 窗口規劃保留完整回合、Unicode code-point 分頁、超預算明示失敗及 `source_reference`／`context_reference` pair；有限批次以 `covers_whole_range` 防止前綴冒充全範圍。
- 不先註冊 `request_memory_consolidation` 是正確決策。OpenAI 的工具流程是模型提出 call、App 執行並回傳結果；Anthropic 也要求 client tool 由應用執行並以對應 `tool_result` 回傳。這支持「純通知要有獨立結果分類與收尾路徑」，不支持先把它塞進 JD binding。AWS 的冪等原則同樣支持未知結果沿同一 operation／receipt 對帳，不另發新意圖。

## 推進決定

保留目前五個提交作為 source port 的隔離基線，但把 H4 狀態維持為未完成。下一個有限工作單位依序為：

1. 補 F-01 的固定 root lineage／完整回合 boundary 驗證及 W-08／W-09 反例。
2. 補 F-03 的超過 256 祖先案例；在 B1 adapter 出現後補 F-02／F-04 的不可變 pair 重抽案例。
3. 完整處理整理通知的工具註冊、結果分類、`_settle`／停止／恢復路徑與既有工具數斷言；不拆成只有註冊的半步。
4. 之後才接 B1／B2，並用實際 adapter 驗證 `MemorySourceReader` 能讀 window/context、publication 能保存 `processed_source=window`，再進零 provider 完整旅程。

本審查沒有修改產品程式、沒有新增資料表、沒有啟動 provider，也沒有改 JD 格式；沒有把固定測試通過誤報成自然顧問或 H4 通過。

## 依據

- [9/12 JD 關聯式保存契約](../2026-09-12-jd-relational-schema-and-write-contract.md)
- [9/12 Agent 工具契約](../2026-09-12-jd-relational-agent-tool-contract.md)
- [9/13 完成窗口 source contract](../2026-09-13-jd-interview-window-source-contract.md)
- [9/13 B1／B2 adoption mapping](../2026-09-13-jd-consultant-b1-b2-adoption-mapping.md)
- [9/06 Memory 整理節奏研究](../2026-09-06-memory-generation-cadence-and-continuity-review.md)
- [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [Anthropic tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)
- [AWS：Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)
