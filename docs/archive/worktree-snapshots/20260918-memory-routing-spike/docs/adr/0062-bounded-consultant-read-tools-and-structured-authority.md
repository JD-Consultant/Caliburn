# 0062. 受限顧問唯讀 Tool 與 structured authority 邊界

- **狀態**：Accepted
- **日期**：2026-08-14
- **Owner 核准**：在完成官方資料研究與產品北極星複核後，owner 明確同意依最新主流做法直接施工
- **研究**：[`2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md`](../specs/2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md) §9.16.3–§9.16.4
- **延續**：ADR 0060 的 LangChain／LangGraph runtime 與 ADR 0061 的 compact structured output；本 ADR 補上 0061 明確延後的 Tool 決策，不改寫兩份 Accepted ADR

## Context

顧問需要在當輪 context 不足時讀取專業分析 Skill，或找回同一份文件中沒有預載的員工原話、更正關係與來源脈絡。現行 runtime 已使用 Deep Agents `FilesystemMiddleware` 與三個 document-scoped source lookup tools，但仍有四個問題：

1. source tool 名稱 `source_by_id`／`source_lineage`／`source_lexical_search` 太泛，且把目前的 lexical backend 寫進 model-facing contract；
2. `document_id` 雖已由 application 綁定，搜尋筆數上限仍暴露給模型，違反「application 已知的參數不要再要求模型填」；
3. framework 通用 `read_file` 說明包含編輯、PDF、圖片、分頁等本產品不存在或不允許的能力，增加錯誤選擇；
4. prompt 曾把查詢固定成「第一波 Skill、第二波 Source」，但員工更正可能必須先查 lineage，彼此獨立的 Skill／source 讀取也可在同一波完成。

OpenAI、Anthropic 與 Google 的官方指引一致把 Tool Calling 用於外部資料、既有系統或可執行動作，並要求名稱／描述清楚、輸入強型別、工具集合精簡、回傳高訊號且受限。三者也都把「產生一份符合 schema 的最終結果」與「呼叫外部 Tool」分成不同 primitive；LangChain 對應為 provider-native structured output 與 Tool／middleware。

Anthropic Tool Search 的目前定位是大型 catalog：官方文件以數百至數千個 Tool 為主要情境，並說一般 Tool 選擇品質可能在約 30–50 個開始下降。Caliburn 只有四個小型唯讀 Tool，沒有足夠理由增加 Tool Search、另一個 LLM selector、mid-conversation provider beta 或 MCP catalog。

## Decision

1. **第一版 model-facing Tool surface 固定為四個唯讀 Tool：**
   - `read_file`：讀取本輪 eligible 的一份 `/skills/<skill-id>/SKILL.md`；
   - `employee_source_get`：依 stable source ID 取回一筆員工來源；
   - `employee_source_lineage`：取回來源及其更正／被更正鏈；
   - `employee_source_search`：在同一文件內依文字查找相關員工來源。
2. **Skill reader 使用成熟 framework，不自寫替代 loop。** 保留 Deep Agents `FilesystemMiddleware` 與 `read_file` 標準名稱，以公開的 `custom_tool_descriptions` 收斂成 Caliburn 真實能力。`PackageSkillBackend` 繼續限制 exact eligible path、完整讀取與 loaded receipt；模型不能存取 host filesystem。
3. **application-known arguments 不進模型 schema。** `document_id`、source namespace、權限與搜尋 `limit=5` 由 application closure／runtime 注入。模型只為來源查詢提供它真的需要判斷的 `source_id` 或 `query`。
4. **來源 Tool 回傳可驗證、受限的 evidence payload。** 至少包含 stable `source_id`、`kind`、`speaker`、exact `text`、`created_at`、`validity`、`supersedes_source_id` 與 `superseded_by_source_id`。不存在、跨文件或不合資格來源必須 fail closed，不以近似文字替代。
5. **文件候選不是 business Tool。** ADD／REVISE／WITHDRAW／MERGE／SPLIT，以及未來的重新歸類／排序，仍由 ADR 0061 的 provider-native Structured Output 產生 typed review draft；不得拆成讓模型直接執行的 `add_task`、`merge_duty` 或通用 `write_document` Tool。
6. **員工決策不是 model Tool。** accept／edit-accept／reject／defer 是 UI/API 發出的 LangGraph authority command。只有這些命令或員工 direct edit 能改核准文件；模型不能呼叫、偽造或繞過。
7. **必要澄清不是 Tool。** 模型以 Structured Output 表達一個 typed required clarification，由 LangGraph `interrupt()`／`Command(resume=...)` 暫停且只阻擋相依 branch。一般 Gap、目前焦點與可信進度仍是 durable graph state／projection，不變成 Tool。
8. **查詢按依賴驅動，最多兩波。** 當現有 context 足夠時可零次 Tool call；彼此獨立的 Skill／source 讀取可在同一 model response 平行呼叫；只有第一波結果產生新的資料依賴時才使用第二波。既有最多三次 model call、兩個 lookup waves 與總 Tool／token／timeout budget 維持。
9. **目前不啟用動態 Tool catalog。** 四個 definition 靜態、精簡且穩定地提供給模型。只有未來 Tool 數量或實測選擇品質出現問題時，才評估 LangChain deterministic filtering 或 provider Tool Search；不能先加 keyword router 或另一個 LLM router。
10. **本輪不接 RAG。** `employee_source_search` 只查同文件員工來源，名稱刻意不綁 lexical backend，讓未來可在相同語意契約下改善索引。Reference／RAG 是另一個 bounded context 與後續決策，不得由本 Tool 名稱偷接 production。

## Consequences

- LangChain／Deep Agents 承接 Tool loop、schema、middleware、錯誤與 Skill filesystem abstraction；Caliburn 只保留文件 scope、來源資格、更正 precedence、authority 與職務分析語意。
- model-facing surface 小而高訊號，仍完整支援「記得員工以前說過的話」，又不把所有歷史永久塞進 prompt。
- `read_file` 的 framework schema 仍含 optional `offset`／`limit`，但產品說明要求省略，backend 只允許 eligible Skill 的完整讀取。這是保留成熟 middleware 的刻意取捨，不另造一個功能相同的 loader。
- 搜尋 backend 可從 lexical 改善為其他本地索引，而不必改模型可見 Tool ID；任何 RAG／Reference 接入仍須另行裁決。
- 文件內容永遠經 Structured Output、deterministic verifier 與員工審核；四個 Tool 沒有任何 write capability，因此不新增 authority bypass。
- 產品北極星不變：一位顧問、動態 Task／Duty／OPKS、員工原話記憶、文件先審後入、澄清／Gap／審核分流、可信進度、自然離開／續談與單一可強制匯出。能力級別／A、RAG 與正式 eval 仍延後。

## Rejected alternatives

- **每個文件操作都做成 Tool**：混淆「模型提出內容」與「模型執行變更」，也增加 schema、權限與部分成功問題。
- **一個萬用 `consultant_context` Tool**：參數與回傳會重新長成難選擇、難驗證的大 union，且掩蓋來源與 Skill 的不同語意。
- **目前導入 Tool Search／LLM selector**：四個 Tool 不符合大型 catalog 問題，反而增加 provider lock-in、呼叫成本與新的失敗面。
- **重寫 `load_skill` 取代 `FilesystemMiddleware`**：沒有增加產品效果，只重造 framework 已提供的 path restriction、Tool loop 與 middleware integration。
- **固定先 Skill、再 Source**：資料依賴並非總是這個順序，也阻止本可平行的讀取。
- **把 review／accept 做成模型 Tool**：會讓模型跨越員工文件權威，是產品不可接受的邊界錯誤。

## Sources

- [OpenAI — Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI — Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [OpenAI — Model optimization and tool guidance](https://developers.openai.com/api/docs/guides/latest-model)
- [OpenAI — Tool search](https://developers.openai.com/api/docs/guides/tools-tool-search)
- [Anthropic — How tool use works](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works)
- [Anthropic — Tool search tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool)
- [Anthropic — Writing tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents)
- [Google Gemini — Function calling](https://ai.google.dev/gemini-api/docs/function-calling)
- [Google Gemini — Structured output](https://ai.google.dev/gemini-api/docs/structured-output)
- [LangChain — Tools](https://docs.langchain.com/oss/python/langchain/tools)
- [LangChain — Structured output](https://docs.langchain.com/oss/python/langchain/structured-output)
- [LangChain — Agents](https://docs.langchain.com/oss/python/langchain/agents)
