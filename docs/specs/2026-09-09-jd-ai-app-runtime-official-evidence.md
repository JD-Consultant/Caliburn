# JD AI App：工具執行與可靠性官方證據

JD-R002/C03；查閱日 **2026-09-09**；G2 證據，不是採用或施工授權。承接[整體研究](2026-09-09-ai-document-app-composition-research.md)；文件結構與審閱的 E01–E20 留在[原證據表](2026-09-09-jd-document-model-official-evidence.md)，不重抄。本文只回答「工具怎麼執行、錯誤怎麼回、框架能省掉什麼」。

分類：**Fact** 為官方直接契約；**Mapping** 為本案建議；**Unknown** 為尚未公開／未驗證。多家相同的是原則，不代表相同 API，也不證明某方案在所有情況效果最好。

## R01 OpenAI：patch 是執行介面，不是審核系統

- 來源：[Apply patch](https://developers.openai.com/api/docs/guides/tools-apply-patch)，The apply patch tool／How it works／Integration tips；以 OpenAI Docs 取得正文。
- **Fact：**模型提出 create／update／delete file 操作，應用套用 diff，每個 call 回傳 completed／failed 及結果。官方提供 Agents SDK 的 diff 套用程式；缺檔或衝突應回報，讓模型讀取後調整。原子性採整批或逐檔是應用要決定的事項。
- **Mapping：**可學習小範圍修改、寫入前讀取、結果回饋與重讀；不能由此推論原生支援 JD 節點、格式、跨位置審核或保存。
- **限制：**頁面範例／模型清單不作當前模型選擇依據；使用其中的本機 diff 程式，也不等於其他 provider 支援同一個原生 tool type。沒有比較實測，不稱 patch 在富文字一定最好。

## R02 Anthropic：精確替換與行位置仍是現行支援契約

- 來源：[Text editor tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/text-editor-tool)，Commands／Error handling／Best practices／Version history。
- **Fact：**`text_editor_20250728` 的 view 可限行範圍；`str_replace` 要完整匹配 old_str，含空白縮排且須可唯一定位；insert 仍有 insert_line。未找到、多處匹配、無檔或權限錯誤透過 tool result 回報。工具由應用執行，並由應用限制路徑及保存備份。較新支援格式已沒有 undo_edit。
- **重要修正：**不能把「所有 line number 都已淘汰」「精確替換不是大廠方式」當事實。真正要避免的是叫模型憑記憶算位置、把顯示行號抄進原文、或猜重複文字的位置。
- **Mapping：**結構文件優先研究編輯器原生目標定位；若採文字定位，必須沿所選工具的讀取呈現與匹配契約，不自行加模糊匹配。仍須測繁中、重複句與巢狀內容。

## R03 OpenAI：SDK 接循環，不替 App 寫產品政策

- 來源：[Agents SDK](https://developers.openai.com/api/docs/guides/agents)，Build with the SDK／Agents SDK vs Responses API；[Running agents](https://developers.openai.com/api/docs/guides/agents/running-agents)，The agent loop／Choose one conversation strategy／Handle pauses and failures。
- **Fact：**Runner 執行模型→工具→結果→再決定的循環，提供 session、streaming、tracing、guardrail 與可恢復核准接點；工具實作、保存及產品決策仍由應用負責。手動 history、SDK session、Conversations、previous response continuation 是不同選擇，混用要防止重複上下文。stream 未結束不當作已完成；失敗與預期 pause 不同。
- **Mapping：**一個主顧問即可；不因新增 JD 編輯就另造 agent loop 或強制多 agent。SDK 的「執行前核准」不能直接當作「內容已顯示、可續改但未審」的文件審閱。
- **限制：**SDK guide 的 session／memory 用語不能直接等同已研究的可修訂職務 Memory。此輪不更動 Memory 架構。

## R04 Anthropic：錯誤要讓模型知道，而不是假裝有結果

- 來源：[Handle tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)，Handling results from client tools／Handling errors with is_error；與 E17 的 Tool Runner 配合閱讀。
- **Fact：**tool use 與 result 以 ID 配對；結果需符合訊息順序。執行失敗使用 is_error，說明出了什麼問題及下一步，不能只寫 failed。Tool Runner 可管理基本往返。外部不可信內容留在 tool result，不提升為 system 指令。
- **Mapping：**JD 操作應把找不到位置、結構不合法、保存失敗明確回報；失敗不等於模型必然修好。文件內「請忽略規則」等文字是待編輯資料，不是操作權限。

## R05 LangChain：錯誤回饋與自動重試是兩個現成能力

- 來源：[Prebuilt middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)，Tool error／Tool retry／Model retry／Model call limit／Tool call limit。
- **Fact：**`ToolErrorMiddleware`（文檔要求 langchain≥1.3.14）把指定例外轉為 `ToolMessage(status="error")`，不自動重試。`ToolRetryMiddleware` 處理退避重試，可用 retry_on 限定錯誤；其預設並非只重試安全的讀取。兩者組合的官方順序是 retry 在 list 前、error 在後，retry 設 on_failure="error"。另有模型及工具呼叫上限。
- **Mapping：**只將可安全重試的暫時傳輸故障交自動重試；錯參數／找不到目標要回模型修參數，不能反覆送同樣壞操作。不要多層各自重試把成本相乘。
- **版本：**同頁列出≥1.3.16 的預設重試行為變動；本研究不從 repo 舊 lockfile推定現行能力，也不把 latest 文檔當已安裝。施工前鎖定相容版本。

## R06 LangChain：既有參數注入、工具格式及前端執行

- 來源：[Tools](https://docs.langchain.com/oss/python/langchain/tools)，Access context／ToolRuntime／Headless tools；[Headless tool primitive](https://reference.langchain.com/javascript/langchain/index/tool)。
- **Fact：**`ToolRuntime` 注入 context／state／store／call ID，runtime 本身不出現在模型 schema。官方 headless pattern：後端註冊 schema-only tool，呼叫時 interrupt，前端執行並 resume result；JS 可 `.implement(...)`，Python 端沒有相同方法。這是 client execution，不是 provider server tool。
- **Mapping：**目前文件、操作者、版本及審核權限由應用提供；模型只選要改哪段與內容。技術性等待瀏覽器結果，不需要員工逐次確認，也不是待審內容必須阻塞整個訪談。
- **Unknown：**Python／JS 精確相容版本、所選本機 transport 與關頁時的恢復行為需接線驗證；不能只因 guide 有 pattern 就宣稱本產品接好。JS reference 標 v1.5.10；不是 Python 版號。

## R07 參數驗證預設不能猜

- 來源：[ToolNode](https://reference.langchain.com/python/langgraph.prebuilt/tool_node/ToolNode)、[ToolInvocationError](https://reference.langchain.com/python/langgraph.prebuilt/tool_node/ToolInvocationError)、[BaseTool.handle_tool_error](https://reference.langchain.com/python/langchain-core/tools/base/BaseTool/handle_tool_error)。本轮 reference 直接開頁被讀取器拒絕 markdown content-type，使用搜尋索引回傳的官方 reference 正文；未用第三方補猜。
- **Fact：**ToolNode 預設對模型錯誤參數回描述性訊息，執行例外則可向上拋出；自訂流程可配置。一般 agent 建議用 create_agent，內部已用 ToolNode。BaseTool 的處理後錯誤，在有 call ID 時可形成 status=error 的 ToolMessage。
- **限制：**不同層預設不同；不要寫「框架所有錯誤都自動處理」。Headless tool 的瀏覽器錯誤回傳須測自己的接點，不可假設 Python middleware 捕捉前端例外。

## R08 框架恢復不是外部寫入的 exactly-once 保證

- 來源：[Functional API](https://docs.langchain.com/oss/python/langgraph/functional-api)，Idempotency／Handling side effects；[Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)，Side effects called before interrupt must be idempotent；[Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)。Functional API 的相關段落與 Persistence 已開頁閱讀；Interrupts 本輪使用官方搜尋回傳正文。
- **Fact：**恢復可能重跑未完成工作；官方要求副作用隔離並使用 idempotency key 或查既有結果避免重複。Checkpointer 管 graph state；Store 管 graph 外資料。InMemorySaver 不跨重啟。
- **Mapping：**文件已保存但回覆遺失時，先查同一次操作結果，不直接再新增一份內容；call ID／操作身分由 runtime 提供，不讓模型創造。不得用整個 agent checkpoint 回退代替拒絕一項文件修訂。
- **限制：**本文不選 JD 存到 Checkpointer 或 Store；文件儲存與 editor serialization 應沿編輯框架決定，Memory 的已核准 owner 不因此重開。

## R09 真實文件 API 的定位、批次與版本

- 來源：[Google Docs batchUpdate](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/batchUpdate)，intro／WriteControl（頁面更新2026-07-07）；[Notion Update a block](https://developers.notion.com/reference/update-a-block)，Updates the content／Errors。
- **Fact：**Google 先驗各 request，無效則整批不套用；有 requiredRevisionId 與 targetRevisionId，不同於模型自己的行號計算。Notion 依 block_id 更新，省略欄位不改、提供的欄位整個替換，子節點另外操作；錯誤包含無目標、型別或參數不正確。
- **Mapping：**穩定目標、結構化操作、版本／批次結果有實際產品先例。但這些是服務 API，不是已選本機 editor，也不是證明各家的 AI 原生 wire 格式一致。
- **版本陷阱：**Google 本頁的 writeMode=SUGGEST 與 suggestionResponses 明標 Developer Preview；不可當成熟 GA 審核底座，也不因有原子 batch 就推論存在 JD 語意審核群組。

## R10 UI 接線與可觀察性可以沿框架，不堆新引擎

- 來源：[LangChain frontend overview](https://docs.langchain.com/oss/python/langchain/frontend/overview)，Architecture／Capabilities／Integrations；[LangGraph v1 JS](https://docs.langchain.com/oss/javascript/releases/langgraph-v1)，Frontend SDK enhancements。
- **Fact：**`useStream` 可呈現 tool lifecycle、訊息、interrupt、thread state及恢復；現行頁面用 `@langchain/react`。JS v1 說明 transport 可替換，與新舊套件路徑有差異。它可配任意 UI 元件，不要求把所有能力都顯示。
- **Mapping：**顯示「分析中／正在修改／未保存／已保存待審／失敗」由實際結果驅動；不另寫第二套聊天循環，也不強制公開模型內部推理。取消、重開與恢復要測；不因此新增多人協作、訊息分支、排隊或雲端服務。
- **限制：**有 frontend hook 不等於已有任意 FastAPI endpoint 相容性；本機服務仍須符合所選 transport 的正式契約。

## 資料取得限制與研究停止線

Vercel AI SDK 官方搜尋可見 ToolLoopAgent／prepareStep／stopWhen／experimental_repairToolCall 等能力，但數次直接開頁回 unsupported markdown content-type，本機網路讀取也未成功。只列正式 runtime 備選，不拿未讀完整契約作精確主方案；Tiptap 的 Vercel integration 範例則另依 E18 的直接資料核對。

以上足以排除「所有工具都靠自行寫 loop／所有錯誤都重試／有 approval 就等於文件審核」等錯誤前提。編輯器選擇、部分失敗及 C02 情境的後續證據已寫入 [F01–F05](2026-09-09-jd-editor-framework-comparison.md)，整體取捨在[可執行方案](2026-09-09-jd-ai-editing-executable-proposal.md)。不重做 Memory、provider 或所有 LLM App 功能研究。
