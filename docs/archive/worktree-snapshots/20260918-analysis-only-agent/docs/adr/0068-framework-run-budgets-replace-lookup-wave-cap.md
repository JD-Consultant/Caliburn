# 0068. 以 framework run budgets 取代自訂 lookup-wave 上限

- **狀態**：Accepted
- **日期**：2026-08-23
- **Owner 核准**：owner 於 2026-08-23 核准移除固定兩波 external-data lookup 限制；不得把 2 任意改成另一個未經量測的數字
- **研究與實測**：[`2026-08-23-luna-structured-tools-and-context-official-audit.md`](../specs/2026-08-23-luna-structured-tools-and-context-official-audit.md)
- **Supersedes**：ADR 0062 決定 8 的固定兩波 lookup、ADR 0065 決定 4 保留的兩波限制，以及 ADR 0067 沿用該限制的 runtime mapping
- **保留**：依資料需求按需讀取、不要無故重讀、文件 scope／唯讀 root／可編輯 root、11 次 model calls、48 次總 Tool calls、單次 context、總 token、成本、elapsed、retry、workspace validator、Evidence 與員工 authority 邊界

## Context

「lookup wave」是 Caliburn 自行定義的計數：一次 model response 只要包含對 `/sources`、`/approved` 或 `/review` 的 `ls`／`read_file`／`grep`，便算一波；第三波在 Tool 執行前由自寫 middleware fail closed。既有研究已明載，兩波不是 OpenAI、Anthropic、Microsoft、LangChain 或 Deep Agents 的通用標準，而是早期三步 agent 的本地 operational guess。

持久 JD workspace 完成後，同一回合可能合法地先讀核准基線、再讀 semantic review，經 workspace 自動驗證發現精確 diagnostic 後才取得新的資料依賴並讀取修復所需內容。兩次獨立 Luna smoke 都在尚未耗盡 model、Tool、token、成本或 elapsed budgets 時被第三波規則攔截；2026-08-23 的 `Luna／medium／max_tokens=8192` run 已成功持久化 2 個 Duty、5 個 Task 與 14 個 OPKS，核准 JD 保持不變，但第八個 model step 需要讀取修復 diagnostic 時觸發 `LookupWaveLimitExceeded`。這證明固定波數會把合法 recovery 誤判成 runaway loop。

LangChain 與 Deep Agents 的 production 指引直接提供 `ModelCallLimitMiddleware` 與 `ToolCallLimitMiddleware`，用每次 invocation 的總 model／Tool 呼叫限制失控成本；可恢復的 Tool／validation 錯誤應回饋給模型修正，真正需要人類輸入才暫停。官方 primitive 可另對昂貴 Tool 做 per-tool limit，但沒有「文件最多讀幾波」的通用概念。Caliburn 的六個 Tool 都是本地、document-scoped VFS 操作，真正風險由總執行預算、權限、路徑與 domain validation 承接，不需要第二套按路徑猜測的循環計數器。

## Decision

1. **刪除自訂 lookup-wave middleware 與全部設定契約。** `LookupWaveLimitMiddleware`、其 private graph state／例外、`max_lookup_waves` 的 Settings／RunPolicy／ResolvedExecution 欄位及 agent assembly hard guard 全部移除，不保留相容 alias、停用欄位或隱藏預設。
2. **不以 3、4 或其他固定 read-wave 數字替代。** 模型可以在同一員工回合內，依新取得的明確資料依賴繼續讀取 eligible `/skills`、`/sources`、`/approved`、`/review` 與 `/workspace`；是否需要下一次讀取由當前 state、Tool result、validation diagnostic 與 prompt stopping rule 決定。
3. **失控保護交給成熟 framework 的總預算。** 互動 policy revision 升為 3，保留 LangChain `ModelCallLimitMiddleware(run_limit=11)` 與 `ToolCallLimitMiddleware(run_limit=48)`；另保留 24,000 單次 context、160,000 累計 raw tokens、US$2、180 秒、一次 model retry、一次 Tool retry與 graph recursion limit。這些是 ceiling，不是每輪目標。
4. **application 特有防線不移除。** Composite backend 繼續強制 `/skills`、`/sources`、`/approved`、`/review` 唯讀，只有 `/workspace` 可寫；document scope、stable handle、Evidence exact quote、workspace schema／identity／dependency validation，以及員工 accept／edit-accept 前的 authority validation 全部不變。
5. **停止條件維持 outcome-driven。** context 足夠時零次 Tool call；彼此獨立的 reads 仍應在同一 model response 平行提出；已有結果不得無故重讀。workspace valid 或 conflicted、沒有新的資料依賴時應直接回傳 compact structured result。這些是 agent contract 與可觀測行為，不再由一個不理解語意的 path counter 執行。
6. **觀測真實使用，不建立新 limiter。** attempt receipts 繼續記錄 model calls、Tool calls、tokens、cache、cost、latency 與錯誤。若代表性 runs 顯示特定 Tool 有獨立的成本、延遲或 abuse 風險，再依實測使用 framework per-tool limit；本 ADR 不加入重複讀取偵測器、lookup planner、另一個 Agent 或 RAG。
7. **窄 live gate。** 離線回歸全綠後，只對同一份已保存、曾被兩波限制阻擋的 workspace 重跑一次 `GPT-5.6 Luna／medium`。成功條件是能繼續修復並形成可審 semantic review，且 employee 未接受前 approved JD 不變；不能只以「不再出現舊例外」宣稱完成。

## Consequences

- 合法的 workspace repair 能在既有總 budget 內繼續，不再因資料依賴出現於第三次 read response 而浪費整輪成本。
- runtime 刪除一套自寫 state、middleware、exception、設定與測試，安全上限改由 LangChain production-ready primitives 統一承接。
- 單輪 external reads 可能超過兩波，但最多仍受 11 model calls、48 Tool calls、token、金額與時間多重 fail-closed 限制；六個 Tool 沒有網路、shell、host filesystem 或 authority commit 能力。
- prompt 中「最多第二波」的指令必須移除；按需讀取、平行獨立 reads、valid 後停止與禁止無故重讀則保留。
- 歷史 ADR／研究中的兩波紀錄不事後改寫；現行設計、run policy 與索引以本 ADR 為準。

## Rejected alternatives

- **把上限從 2 提高到 3 或 4**：只會把已證明錯誤的猜測換成另一個猜測，且下一個合法 repair 仍可能被誤擋。
- **完全移除 run budgets**：agent 仍可能循環或消耗過多；官方 production guidance 明確建議同時限制 model 與 Tool calls。
- **新增語意化重讀偵測器／lookup planner**：必須理解資料依賴、validation 與 VFS projection，複雜度高且沒有代表性證據；目前 prompt＋總 budgets 已足夠。
- **提高 reasoning effort 或改模型繞過限制**：限制由 application middleware 觸發，模型再強也無法通過；也會混淆品質與 orchestration 修正。
- **移除 validator 讓模型直接完成**：會犧牲 Evidence、schema、identity 與 authority 正確性，與本問題無關。

## Sources

- [LangChain — Prebuilt middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)
- [LangChain — Agents](https://docs.langchain.com/oss/python/langchain/agents)
- [Deep Agents — Going to production](https://docs.langchain.com/oss/python/deepagents/going-to-production)
- [OpenAI — GPT-5.6 model guidance](https://developers.openai.com/api/docs/guides/latest-model)
