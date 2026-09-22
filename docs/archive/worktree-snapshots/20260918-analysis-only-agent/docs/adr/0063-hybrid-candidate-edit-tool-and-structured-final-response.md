# 0063. 候選文件編輯 Tool 與 Structured Final Response 混合迴圈

- **狀態**：Accepted
- **日期**：2026-08-15
- **Owner 核准**：owner 在完成舊／新流程、優缺點與 Structured Output 邊界對照後，明確同意混合方案
- **研究**：[`2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md`](../specs/2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md) §3.7.5、§9.17–§9.18
- **Supersedes**：ADR 0062 決定 5；ADR 0062 決定 8 的固定三次 model-call 上限；ADR 0061 決定 1、3、6 中「完整文件候選只由 final response_format 承載」的 provider channel 選擇
- **保留**：ADR 0060 的 LangChain／LangGraph runtime 與單一 durable authority；ADR 0061 的 compact／union-free wire、Evidence basis、pure mapper 與 verifier；ADR 0062 的四個唯讀 Tool、員工 authority command、必要澄清、依賴驅動 lookup、無 Tool Search 與 no-RAG

## Context

現行顧問把可修訂理解、Gap、下一題與完整 Duty／Task／OPKS 文件候選一起放在一次 final `ConsultantModelOutput`。application 只能在模型結束 tool loop 後，才把文件候選映射成 changeset 並執行 document invariant、read-set、identity、dependency 與 evidence 驗證。這保住員工 authority，但有四個效果缺口：

1. 模型在同一 run 看不到候選實際套用結果，驗證失敗時無法依具體錯誤修正；
2. 跨 Duty／Task／OPKS 的重組必須一次猜對，合法部分也可能跟著整輪失敗；
3. final response 宣稱的內容與 application 真正能建立的 candidate artifact 之間缺少 action／observation 閉環；
4. 後續 context 目前主要看到 pending handle／operation／path，不能安全地把相關候選當成明示、非核准的條件式 overlay。

OpenAI Apply Patch、Anthropic Text Editor、Google Function Calling 與 Microsoft Agent Framework 均採 model action → application execution → tool result → model continuation；OpenAI 與 Google 也明確把 Function Calling 用於應用功能／動作，把 Structured Output 用於最後交付格式。LangChain 的 agent loop 會先完成 Tool Calling，再產生 final structured response；Tool 可透過 LangGraph `Command` 更新 state 並以 `ToolMessage` 回傳實際結果。

這不表示每個文件操作都要變成 Tool，也不表示 candidate write 等於 approved write。Caliburn 需要的是一個受限、document-scoped、可反覆驗證的候選編輯環境；員工接受前，任何內容都不得進核准文件。

## Decision

1. **採 Tool Calling＋Structured Output 混合迴圈。** Tool 負責必須實際執行、觀察結果並可能在 final response 前修正的候選文件編輯；final Structured Output 負責員工可見回覆、可修訂理解、Gap／充分性建議、下一題／必要澄清，以及成功 candidate revision 的引用。

2. **新增一個 model-facing `job_document_candidate_edit` Tool。** 不新增 `add_task`、`split_task`、`merge_duty`、`revise_opks` 等重疊 Tool。單一 Tool 以 typed atomic batch 表達新增、修改、撤回、移動、重新歸類、排序與跨 Duty／Task／OPKS 重組；batch 的 deterministic 套用是全成或全敗，成功 actions 再依 dependency 分成員工可獨立裁決的 atomic subgroup，split 等不可分割重組仍整組決定。split／merge 可由一般操作組合，若保留 intent label 也只供 semantic diff／audit，不代表額外權限。

3. **候選編輯 wire 維持 compact、strict、union-free。** 使用固定 target／field／payload slots 與 normalized `analysis_bases`＋1-based basis ordinal；不得接受任意 JSON Pointer、open object、SQL、host path 或自由 patch script。`document_id`、核准 baseline revision、權限、ID 配置與 server budget 由 application 注入，模型不得選擇另一份文件或自填 authority revision。

4. **每次成功 Tool call 產生新的 run-scoped candidate revision。** 呼叫可引用上一個 candidate revision 繼續編輯；stale base 必須拒絕。LangChain 負責 Tool loop，LangGraph typed state／reducer／`Command` 保存隔離候選，Tool result 至少回傳 candidate revision、實際 semantic diff、action handles、dependency／stale 影響與可行動錯誤。模型只能依真實 result 繼續，不能把意圖當成已套用。

5. **Tool 永遠沒有 approved-document write edge。** candidate revision 是非權威、run-scoped workspace；只有 final verifier 明確引用且完整通過 evidence／domain 驗證的 revision，才會在該 run 的 semantic commit 中轉成 durable review bundle。run 失敗或未引用的 candidate 不得出現在員工 review queue，也不得改核准文件；framework checkpoint 只用於恢復，不建立第二份 document authority。

6. **final response 不再重送完整文件草稿。** 它只引用最後一個要發布的成功 candidate revision／action handles，並承載非文件的 final effects。application 必須比對 Tool receipt、revision digest 與 final reference；不一致、未知、失敗或已被後續 revision supersede 的 handle 一律 fail closed。

7. **pending overlay 不會被默認當成核准基線。** Context middleware 提供相關 approved slice，以及另行標示的 pending／deferred／stale semantic candidate slice與 employee decision history。若新候選建立在尚未核准 action 上，必須顯式記錄 dependency；若要取代既有候選，必須顯式記錄 supersession。員工 reject／edit-accept／direct edit 後，framework 依 dependency 與 read-set 重驗下游候選，必要時標 stale；被拒絕內容不得被下一輪偷偷復活。

8. **員工審核仍是獨立 authority command。** candidate Tool 在隔離 workspace 內可自動執行，不在每次草擬前跳 approval；accept／edit-accept／reject／defer 只能由 UI/API 發出 LangGraph command。只有 accept／edit-accept 或員工 direct edit 能更新核准文件，模型不能呼叫、偽造或自我核准。

9. **Structured Output 不取得 deterministic projection authority。** 一般回覆、理解、Gap、充分性建議與下一題適合 final schema；員工看到的 coverage／depth／decision／gap 進度仍由 durable state 確定性投影。必要澄清由 final typed output 觸發 LangGraph `interrupt()`／resume；Skill／員工來源仍由四個 read Tool 按需取得。

10. **Tool surface 固定為五個且不導入 Tool Search。** 第一版為 `read_file`、三個 `employee_source_*` read Tool，加上 `job_document_candidate_edit`。候選 Tool 不算 lookup wave；lookup 仍最多兩波且依資料依賴驅動。

11. **固定三次 model call 不再是產品 invariant。** 初始 profile 以五次 model step 作 hard ceiling，容納最多兩波 lookup、一次候選編輯、一次錯誤修正與 final response；同時保留總 Tool calls、總 token、成本、elapsed time、provider timeout 與 LangGraph recursion hard budget。真模型 canary 可在不改產品語意下調低 profile，但不得無上限循環，也不得為保留舊呼叫數取消結果回饋後修正。

12. **先做小型真模型 canary，不提前建立完整 eval 平台。** 至少覆蓋 Task＋O/P 新增、跨實體原子重組後錯誤修正、九項接受一項 O 拒絕後的 context、以及員工 direct edit 造成 stale。量測 semantic diff 正確性、tool error recovery、authority bypass、review clarity、token 與 latency；通過後才完成 production hard cut。本輪仍不接 RAG，也不產生能力級別／A。

## Consequences

- 模型能在同一 run 取得候選實際結果並修正，複雜重組不再依賴一次 final output 全部猜對。
- 待審內容來自 framework 中真實存在且驗證過的 candidate revision，不是模型另外描述的一份副本；員工 review bundle／atomic subgroup UX 保持不變。
- 一般對話或沒有文件變更的回合不呼叫 candidate Tool；簡單文件變更通常一次 Tool call，只有錯誤或重組才增加 round trip。
- 成本、延遲與狀態轉換比 only-Structured-Output 高；run budget、candidate revision、dependency、supersession、stale 與 tool receipt 必須可觀測、可測試。
- LangChain／LangGraph 承接 agent loop、typed state、Command、Tool result、checkpoint 與 resume；Caliburn 只保留職務文件 invariant、Evidence、read-set、employee authority 與 Task／Duty／OPKS 方法。
- 實作前必須量測「四個 read Tool＋candidate Tool＋縮小 final schema」經 LangChain／OpenRouter 轉換後的合併 grammar；不得因把 schema 從 response 移到 Tool 就宣稱已縮小。zero optional／union／open object 的 compact gate 保持。
- Accepted ADR 0061／0062 保留歷史原文；本 ADR 只取代上列 provider channel 與 fixed-call-topology 決定。

## Rejected alternatives

- **維持 only-Structured-Output**：成本最低，但無法在同一 run 對實際 candidate error 做 action／observation 修正。
- **每種文件操作一個 Tool**：Tool 數量、選擇錯誤、schema 重複與部分成功面都增加，且 split／merge 本可由 atomic batch 組合。
- **完整 Deep Agents virtual filesystem／provider-native editor 作 production 主介面**：file semantics 與 JD typed invariant 不一致，並帶來多餘 `ls／grep／write／edit` surface 或 provider lock-in；Deep Agents `FilesystemMiddleware` 仍只用於按需 Skill reader。
- **任意 JSON Patch／通用 write_document**：把 path、payload 與 authority 邊界交給模型，重新引入 open schema 與越權風險。
- **每次 candidate Tool call 先讓員工核准**：把草擬過程變成連續彈窗，妨礙模型修正；員工應審核可理解的 semantic bundle，而不是內部 tool step。
- **把 accept／reject 做成模型 Tool**：讓模型跨越員工文件權威，與產品目的直接衝突。
- **默認把所有 pending 候選合併成下一輪基線**：會把未核准內容偽裝成事實，並在拒絕一項時造成無法追蹤的下游污染。

## Sources

- [OpenAI — Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI — Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [OpenAI — Apply Patch](https://developers.openai.com/api/docs/guides/tools-apply-patch)
- [Anthropic — How tool use works](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works)
- [Anthropic — Text editor tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/text-editor-tool)
- [Anthropic — Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents)
- [Google Gemini — Function calling](https://ai.google.dev/gemini-api/docs/function-calling)
- [Google Gemini — Structured output](https://ai.google.dev/gemini-api/docs/structured-output)
- [Microsoft Agent Framework — Adding Tools](https://learn.microsoft.com/en-us/agent-framework/journey/adding-tools)
- [Microsoft Agent Framework — Workflow capabilities](https://learn.microsoft.com/en-us/agent-framework/workflows/)
- [LangChain — Context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)
- [LangChain — Tools](https://docs.langchain.com/oss/python/langchain/tools)
- [LangChain — Structured output](https://docs.langchain.com/oss/python/langchain/structured-output)
- [LangGraph — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [Deep Agents — Backends](https://docs.langchain.com/oss/python/deepagents/backends)
