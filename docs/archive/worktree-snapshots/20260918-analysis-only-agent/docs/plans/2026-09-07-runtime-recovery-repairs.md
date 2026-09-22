# Q019 Runtime recovery repairs

> Topic `Q019-RUNTIME-RECOVERY-REPAIR-01` · 2026-09-07 · Owner「好繼續，一樣可以模仿參考大廠作法」核准既有隔離底座的四項局部修復。不是 production gate。
> Implementation: use superpowers:subagent-driven-development. Existing worktree `codex/analysis-only-agent`; baseline `1d2be04c`.

當前實作／審核狀態只更新在[本段結果](../specs/2026-09-07-runtime-recovery-repair-results.md)，不要把本計畫的 task 清單當成已完成。

## Scope and evidence

完整問題／反例見[整體審核](../../../../docs/specs/2026-09-07-analysis-only-runtime-context-coherence-audit.md)。以主 checkout 的 [current register](../../../../docs/current-decisions.md)／[decision process](../../../../docs/decision-process.md) 路由為準，不以隔離 worktree 的歷史 register 重新選架構。

保留分析-only、A/B1/B2/C、原生 reasoning/compaction、原文與引用、官方持久化與發布 receipt/CAS。不增加 JD、UI、Skills、向量召回、新記憶層、LLM 必填 ID。CT-01/SK-01、一般原文搜尋與 grep 提示另處理。本段不用真 API、不重啟 Docker、不 merge/push。

官方依據（2026-09-07 核對）：

- [OpenAI tool results](https://developers.openai.com/api/docs/guides/function-calling#formatting-results)：工具輸出可表達失敗及錯誤資訊；不代表 SDK 能修 app 格式或知道外部寫入結果。
- [Anthropic tool errors](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls#handling-errors-with-is_error)：錯誤以配對結果交回模型；本案不照抄其 wire。
- [LangGraph errors](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph)：按責任區分 transient、LLM-recoverable、需人補充、未知錯誤。
- [LangChain custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)：公開 hook 可更新 state／轉回 model；沿既有 middleware 上限，不另包無限外部重試。
- [LangGraph fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance)：resume 與 node error handling 是可用 primitives；是否採用特定 hook 要核對安裝版及實際任務，不只看名稱。
- [LangChain structured output](https://docs.langchain.com/oss/python/langchain/structured-output)：ProviderStrategy、ToolStrategy 與 `with_structured_output` 不等價；不能拿 ToolStrategy 的回饋承諾當現況。

上述是公開原則；下列 app 邊界、回饋文字與有限額度是本案接線，**不宣稱各廠相同內部實作**。不新增 SDK 外的通用 HTTP retry；未知程式／寫入故障仍停住。

## Task map / shared boundaries

| Task | Finding / change surface | Shared boundary and verification |
|---|---|---|
| 1 | ER-A01: service/conversation、MemorySession trusted read capability | 用既有 graph checkpoint 恢復或收尾；未知 write 不放行 |
| 2 | ER-B01: B2 completion validation | 同一 create_agent 內回饋、既有 model/tool budgets 與發布 validator |
| 3 | ER-B02: B1 extraction feedback | native 三欄 schema；格式驗證、durable bounded correction，不重抽已保存視窗 |
| 4 | AC-01: guide freshness | Task1若觸及MemorySession，先完成再修改；不刪歷史、不改C發布 |

每項紅→綠→差異審查→一個局部 commit。主審最後跑全套與必要 PG 安全測試，保存結果/來源/限制；無真模型語意品質宣稱。未知 consequential approach 先回報，不能以一般「繼續」自行換架構。

### Public API 接線核對（施工前主審，2026-09-07）

- **B2 選定公開 `after_model(can_jump_to=['model'])`：**只在模型完成且沒有待執行 tool call 時驗暫存正文。可修的格式／引用失敗加一則明標 Runtime validation feedback 的私有 B 訊息再回 model；不是員工說話、不是偽造 tool result，也不進原文 reader。回饋 hook 排在 middleware 清單前方，使反向 after hooks 的既有 model counter 先完成，轉回 before_model 時照原 quota 檢查。外層 collect／發布防線保留。實際 installed create_agent + StateBackend + MockTransport 探針已驗：錯誤引用→完成→收到錯誤→edit修正→完成；4 B2 model steps、2 tools、有效引用成功發布。
- **B1 選定原生 schema 與應用驗證分離：**同一 `ExtractionOutput.model_json_schema()` 交公開 `with_structured_output(..., method='json_schema', strict=True, include_raw=True)`；先取得 raw/parsed，再由 checkpointed validation step 用原 Pydantic 規則檢查。模型仍只填原三欄，不增加工具。公開[API參考](https://reference.langchain.com/python/langchain-openai/chat_models/base/ChatOpenAI/with_structured_output)區分 dict/Pydantic schema；實際 adapter 探針已驗 dict 結果保留原回覆，下一呼叫帶原候選＋2000字行長錯誤後可通過。
- **B1 有界接法：**每個來源視窗正常1次，預設最多1次應用驗證修正（可配置，屬工程初值而非廠商共識）；候選／錯誤／已用次數由 Runtime 存 checkpoint。resume 不補新額度；refusal/incomplete/transient HTTP 不混為格式修正。錯誤僅帶欄位＋原因，不把 Pydantic 堆疊、輸入全文再包一次。原候選作為既有 AI response 延續，來源仍原 input window。
- **不選自動硬折行：**現有 newline normalization 已由 deterministic code 完成；任意2000字斷行可能破壞 Markdown 連結／code等語意。暫不取消既有可讀頁面邊界、不默默截斷細節，這種無法無損正規化的超限才回模型。若後續實測證明此限制無必要，另討論放寬，不在本次偷偷換契約。
- **不選 new node error_handler 或 ToolStrategy：**前者可攔 task failure但不會自動保留同節點尚未提交的候選／模型回覆；後者會改 B1 輸出機制。兩者並非不能用，只是以上公開 hook／state 已足以修本次接線，無需增加一套機制。

### Task 1: Recover known read-only tool interruptions

Files: `experiments/analysis-agent/src/analysis_agent/{conversation,service,live_memory,memory_tools}.py` (only necessary files); `tests/test_service.py`, `tests/test_conversation.py` or focused new recovery test; package README.

1. Read the audit ER-A01, actual framework state/ToolNode boundaries and current service recovery. Reproduce with actual ChatOpenAI+MockTransport and LangGraph: valid `read_conversation`, one OperationalError, restore reader. Initialize publication tables in harness so failure is not unrelated SQLite setup.
2. RED tests: API/service resume succeeds at the pending known read without rerunning prior model; stop/abandon can safely close failed known read and later accept a new input; reopen retains same behavior.
3. Identify trusted read-only tools from the actual bound Memory tool set, not arbitrary model-provided tool names or all `runtime_error`. Use existing public graph resume and state update paths. Read-only cancellation feedback must say result unavailable/discarded, not falsely claim tool never executed.
4. Preserve hard boundary: unknown tool/unknown write cannot be abandoned or marked safe; `repair_memory` keeps receipt reconciliation; successful prior effects not replayed, tool call IDs remain paired, per-input budgets not reset.
5. GREEN covering service/conversation/recovery tests plus related C/notification regressions. Inspect changed diff, update package README on the exposed recovery behavior, commit only task files. No new automatic outer retry or model fallback.
6. Report exact RED/GREEN commands/results and remaining limitations to the supplied report file. Do not dispatch subagents.

### Task 2: Feed B2 final model-correctable errors back inside its agent loop

Files: `experiments/analysis-agent/src/analysis_agent/consolidation.py`, optional focused `consolidation_feedback.py`, existing `consolidation_tools.py` only if necessary; `tests/test_consolidation.py` or focused test; README.

1. Verify public middleware `after_model`/jump-to-model and StateBackend context work in installed LC1.4/LG1.2.11. Reuse existing validator; no private graph APIs. Controller records concrete approach before dispatch.
2. RED: write nonexistent summary reference then final answer without validate tool. Today final collect throws and resume never calls model. Add correction response and assert bounded same-agent feedback can repair and publish; invalid intermediate data never publishes.
3. Validate final completed output before leaving agent; only known application format/reference errors receive brief actionable feedback with failing location/reason. Do not fabricate tool call IDs; internal runtime feedback is not employee speech/source. Unknown infra/refusal/incomplete remain failures.
4. Preserve final publication validation as defense. Correction traverses existing model/tool limit middleware; resume cannot reset budget, B1 never reruns, successful paths add no model call, staged edits persist. Budget exhaustion leaves no invalid publication and a meaningful background failure.
5. GREEN tests: valid no-op, missing references corrected, persistent invalid bounded stop, resume after interruption, stale/C rebase and receipt safety. Test actual SDK request pairing and counters, not only output strings.
6. README update, self-review, scoped commit, detailed report. Do not spawn subagents.

### Task 3: Give B1 precise bounded validation feedback

Files: `experiments/analysis-agent/src/analysis_agent/extraction.py`, related tests, README; other validators only if a separately recorded no-loss formatting conclusion requires them.

1. Before coding inspect `_prepare_text` and native structured output parser. Compare avoiding pure formatting retries against keeping page/read limits. No silent content truncation, source mutation, or blind line-wrap changing Markdown semantics.
2. Controller confirms concrete minimal public graph/native schema approach before dispatch. Keep exactly the same three model-authored fields; Runtime owns addresses/versions. Do not swap B1 to tool-calling manager just to get retries.
3. RED: valid JSON with application-invalid summary; next correction must receive bounded precise error plus prior candidate, not identical initial input. Valid extraction still one model call. Refusal/incomplete/HTTP failure are not app-validation correction.
4. Persist candidate/error/correction count in B1 checkpoint before corrective call; finite correction allowance survives resume, no automatic multiplication by scheduler. Successful windows remain saved, only current failed window is corrected. Existing source projection, reextract, output-token cap intact.
5. GREEN: correction success, exhaustion/reopen no fresh allowance, no source/file publication on invalid extraction, multiple windows reset only per new window, native request validity and deployment output cap. Tests use MockTransport, not paid API.
6. Document selected correction bound as configurable engineering choice, not vendor consensus; README, scoped commit, detailed report, no subagents.

### Task 4: Scope guide refresh instructions to the current input

Files: `experiments/analysis-agent/src/analysis_agent/live_memory.py`, `repair.py`, `tests/test_live_memory.py`, README.

1. RED: C publishes v2 in input1, publication becomes v3 before input2. Inspect actual SDK wire: guide v3 and historical v2 feedback coexist; assert unambiguous runtime-provided initial guide revision/current-input scope.
2. Mark initial guide freshness with runtime state (not model-filled ID/version). Only C feedback belonging to current input refreshes that input's view; previous input tool output remains historical. Keep initial prefix stable within one input, dynamic read head changes only via existing C result. An old pending checkpoint missing the new label must not fabricate a revision from a newer publication; label unknown or derive only from proven same-view state.
3. Never delete/edit old canonical tool results. Confirm new reads use v3, old context retained, successful repair updates same-turn read head, no added model step.
4. GREEN focused tests and shared service/native-context/repair regressions, README, self-review and scoped commit. No subagents.

## Completion gate

- Review all four diffs together, especially checkpoint recovery, private B feedback vs employee source, nonresetting limits, and C/new-input context.
- Run whole experiment suite offline (plus existing dedicated PG if available without infrastructure mutation), compileall, offline lock check, diff check. Record any skip/failure honestly.
- Results doc links back to audit/plan and official sources; root register only status + route. Local tag after verification; no production change, no merge/push.
