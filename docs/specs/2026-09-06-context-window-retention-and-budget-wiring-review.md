# Context 接線：近期原句、工具配對與完整 request 預算

> 2026-09-06／`LLM-Q017`／G4 研究與候選審閱；未選引擎、未施工。
>
> 父稿：[Compaction 審閱 §9.6](2026-09-05-conversation-compaction-framework-gap-review.md#96-接續查證成功保存時點恢復與接線門檻)。本文接續其 `CC-F12`，不複製 Memory 分層、原文 reader 或保存／retry 的完整沿革。

## 0. 本輪問題與結論

- **本輪唯一問題：**兩條現有候選如何保留當下需要的原句、有效工具往返，並控制整次模型 request，而非只算對話？
- **有效邊界：**原文同源 Checkpointer、非破壞性 model view、根 `create_agent`、A/B/C 及五 artifact 不變；背景 B 不拿 continuation summary 當完整原文。
- **結論：**已有公開元件可用，但 LangMem short-term 的既有優先建議需要重審：除了沒有獨立 `keep`，所查固定 source 尚有多工具切點風險。不能為了少一份衍生歷史檔，就忽略現成 middleware 的保留／恢復能力。
- **最新 Owner 偏好：**優先可自訂的公開元件組合，以承接 Memory 與 Context 流程；不是自行重寫框架，也不是已選 LangMem 或拒絕所有 Deep Agents 元件。前輪「優先 Deep Agents 獨立摘要 middleware」保留為比較建議，**不是目前必選 gate**；見 §5。
- **不做：**重研 OpenAI、新增原文庫／Agent／語意分類器、安裝／付費模型測試、Q018 協調、JD 或 UI 施工。

## 1. 官方行為：原句保留與工具配對不能混為一談

### 1.1 `trim_messages` 是可用小元件，不是完整 Compaction

**Official fact：**公開 `trim_messages` 提供 token／message count、`strategy="last"`、`start_on`／`end_on`、`include_system`、`allow_partial`。官方要求輸入模型的 history 合法，特別提醒 ToolMessage 要有對應 AI tool call；函式只返回選取結果，不自行保存摘要或修改資料庫。[API](https://reference.langchain.com/python/langchain-core/messages/utils/trim_messages)、[官方 history 範例](https://github.com/langchain-ai/docs/blob/main/src/oss/langgraph/add-memory.mdx)

**依參數語意的推導：**`start_on="human"` 在裁切後找起點，並不是「不管多長都保住最新 HumanMessage」。整段放不下時，不能假設它仍有本輪完整訊息。`end_on="human"` 會排除最後 HumanMessage 後的內容，故不能照抄到已拿回工具結果的 model step；官方工具範例使用 `end_on=("human", "tool")`。`allow_partial=False` 只是不切半則，並不代表不會整則排除。不可把這些參數當 universal pairing validator，也不能裁掉最新工具結果後再要求模型繼續依它判斷。[同一 API 的參數定義](https://reference.langchain.com/python/langchain-core/messages/utils/trim_messages)

### 1.2 LangMem 固定 source 的多工具切點缺口

**Official fact：**既有固定 SHA `f8c7ebd6110c124a36995dab645a8cb0eb0b8210` 的 `_preprocess_messages` 按累積 tokens 找切點；只有「待摘要段最後一則是帶 tool calls 的 AIMessage」時，才把相符 ToolMessage 加入待摘要段。若切點已落在某個 ToolMessage，沒有同樣補齊剩餘同批結果的分支。[固定完整 source：`_preprocess_messages`、`_prepare_summarization_result`](https://raw.githubusercontent.com/langchain-ai/langmem/f8c7ebd6110c124a36995dab645a8cb0eb0b8210/src/langmem/short_term/summarization.py)

**Inference／可達反例，未執行框架測試：**

```text
Human → AI 同時呼叫工具 a、b → result(a) → result(b) → 新 Human
                              ↑ 若 token 門檻在此達到

待摘要段：Human、AI calls(a,b)、result(a)
剩餘尾段：result(b)、新 Human
```

這時模型視圖可能剩下沒有對應 AI call 的 `result(b)`；也可能讓摘要模型收到未完整結束的工具往返。這是正常多工具序列也可到達的分支，不能只測一個工具後宣稱配對完整。不是已證明所有 LangMem 版本都如此、不是所有呼叫必敗，也不是 production 已發生此 bug。`SummarizationNode` 底下使用相同函式，換成 node 名稱本身不解決此問題。[官方 node recipe](https://langchain-ai.github.io/langmem/guides/summarization/#using-summarizationnode)

### 1.3 現成整合元件已有更多機制，但仍有邊界

**Official fact：**目前 LangChain 官方 `SummarizationMiddleware` reference 明列 `trigger`／`keep` 及 AI／Tool 成對保留；並記錄摘要暫時性錯誤以 Runnable retry 最多三次嘗試，耗盡拋錯。不能再把 LangMem 函式沒有 retry 的限制推廣成所有摘要元件都沒有。[LangChain middleware API](https://reference.langchain.com/python/langchain/agents/middleware/summarization/SummarizationMiddleware)

**Official fact：**Deep Agents 公開 factory／middleware 在這個基礎上提供非破壞性 model view、衍生歷史 rendering、模型 profile 的預設保留門檻，以及 overflow 後摘要重試；可以取用獨立元件。它不是另一套 Semantic Memory。[公開 factory 與用途](https://reference.langchain.com/python/deepagents/middleware/summarization/create_summarization_middleware)、[模組／公開 alias](https://reference.langchain.com/python/deepagents/middleware/summarization)

**限制：**`keep` 的訊息／token 數不是「整個本輪 user→多次工具→回答」的絕對保留承諾；長 run 仍可能讓本輪最早訊息離開保留窗。成對保留也不等於所有 provider 的 reasoning／特殊 content blocks 都已驗證。現成 retry 不等於摘要先獨立持久化，不能把父稿 §9.6 的 LangMem 分步方案套成 Deep Agents 已有行為。Deep Agents 正常保留 state 與 overflow/offload 支線的差異沿用[固定 source trace §3.2](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md#32-deep-agents-summarizationmiddleware修正前輪誤讀)。

## 2. 完整 request 預算：可直接重用的官方能力

**Official fact：**研究日官方 `langchain-core` API（reference 標示 v1.6.1）`count_tokens_approximately` 已接受 `tools=`，包含訊息、AI tool calls、ToolMessage call ID 及工具 schema 估算。這比只看 message 字數完整，**不必自己發明工具 schema 計價器**。但它不是每家 provider 的精確 tokenizer；預設字元比例針對常見英文，影像亦採估算。中文訪談不應把英文近似值當精確上限。[完整參數與限制](https://reference.langchain.com/python/langchain-core/messages/utils/count_tokens_approximately)

**Official fact：**provider adapter 能力不完全相同：`ChatOpenAI.get_num_tokens_from_messages` 對支援模型提供 tools 參數；`ChatAnthropic` 的對應方法會使用官方 token-count API，而非純本機計算。不能默認同名函式都沒有額外網路延遲，或 gateway／任意模型都支援相同計算方式。[OpenAI adapter](https://reference.langchain.com/python/langchain-openai/chat_models/base/BaseChatOpenAI/get_num_tokens_from_messages)、[Anthropic adapter](https://reference.langchain.com/python/langchain-anthropic/chat_models/ChatAnthropic)

**組合建議，未定閾值：**

1. 用 model middleware 組裝**本次實際**的規則、導覽、已選召回、對話視圖與工具清單；不將導覽重複 append 成真實訪談。公開 `request.override` 可分別承接 messages／tools。[Context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)、[custom middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)
2. 依所選 provider／模型限制分配對話空間，包含輸出／推理所需餘裕與估算誤差；不是所有模型套相同百分比，也不是對 `max_input_tokens` 無條件重複扣兩次輸出。[ModelProfile 欄位](https://reference.langchain.com/python/langchain-core/language_models/model_profile/ModelProfile)
3. 使用上述公開 counter 計算含工具的組裝視圖；`response_format` 或 provider 轉換後的額外內容另依 adapter 核對。不能把 `tools=` 的存在說成已精確計算所有 request 欄位。
4. 每次真正模型呼叫前都適用，包括 tool result 回來後；只檢查使用者按送出時不夠。先組裝後計算的順序不能被下一層 middleware 再加大量內容破壞。精確 hook 排序留選定元件接線，不另加一個 LLM 做預算判斷。

這些是官方 API 的組合，不是 OpenAI／Anthropic 內部使用相同 middleware 的證據。預算估算不是精確帳單；快取折扣也不代表內容不占 context。

## 3. 前輪候選比較與建議（最新組合偏好見 §5）

| 比較點 | LangMem 公開 short-term＋middleware | Deep Agents 獨立 summarization middleware |
|---|---|---|
| 正常原文保留 | 官方 recipe 可分原文／摘要欄位 | 正常摘要保存 event、不換掉原文；offload 支線另看 |
| 近期保留 | 無獨立 keep；需要 caller 明確選段 | 公開 keep／trigger 已有；不是整輪無上限保證 |
| 多工具配對 | 本文反例未解，不能直接推薦裸接 | 現成 helper 有成對切段，仍需所選版本最小驗證 |
| retry／overflow | 摘要 retry、保存與 overflow 邊界需組合 | 整合較多；不能再外包一層 retry 而不計總次數 |
| 額外產物 | 不要求 backend history rendering | 有衍生 history rendering；不是第二份 canonical 原文 authority |
| 全 request 預算 | 兩者都要與實際規則、導覽、工具及 provider 配置對接；官方 counter 可用 | 同左，不因有預設百分比就算完成 |

**推薦理由（mapping）：**本輪建議將獨立 Deep Agents middleware 提升為優先審閱候選，以重用成對切段／保留／overflow 能力；其額外歷史 rendering 要明確定位為可深查的衍生產物、計入儲存成本，不能以偽成功 no-op backend 關掉。是否採用此取捨仍交 Owner；未核准前不安裝、不改根 Harness、原文 owner 或 reader。若 Owner 不希望有該衍生產物，LangMem 路線可以保留，但必須先找到經核對的公開接法／上游修正，不能把多工具缺口留給 LLM 重試。

**本輪保留規則建議：**一般訪談的最新原句保持原樣，正在使用的工具呼叫／結果不可切散；舊對話才進延續摘要。這是本案效果要求，不宣稱「每家都保護整個無限長 current turn」。若本輪本身過大，兩候選都不能靠固定 keep 保證同時完整放入又不超限；優先沿既有有界深讀／offload 查原文，仍不適用時明確回報限制，不偷偷丟最新文字。具體大小與 fallback 在選定接法時設定，不新增分類 Agent。

## 4. Findings、證據完整度與下一步

| ID／等級 | 位置／影響 | 狀態與要求 |
|---|---|---|
| `CC-F12`／P1（延續） | 父稿 §9.3：把 summary＋tail 當最新原句保證 | 本文 §1.1／§1.3釐清；接線尚未驗證，不能標 resolved |
| `CC-F13`／P1 | LangMem 固定 source 多工具中間切點，可能形成 orphan tool result | 本文 §1.2 靜態反例；阻止裸接／宣稱配對完成。先比較現成元件，不自寫 private helper |
| `CC-F14`／P2 | 完整 request 預算若只算 messages，漏規則／工具；若直接照英文近似值也可能低估中文 | 本文 §2 已找到含 tools 的公開 counter；組合未測試，不自造 tokenizer |

**本輪來源核對：**完整回讀 decision-process／current register；定向讀父稿 §9 全節、原文 primitives §1–6.2、主流程 §6–7。新查 LangMem guide/API／固定 source（分段、回傳），LangChain short-term／custom middleware／counter／trim API，以及 Deep Agents context／公開 factory。Reference 部分直取遇到 content-type 錯誤，採官方網站可讀的索引內容；API 版本標籤只是該 reference 的標示，**不是已安裝套件組合或 PyPI 全版本確認**。Deep Agents 固定 source 與 LC utils 固定 source 直取失敗；原文保存內部細節沿用既有固定 trace。分支搜尋結果只能佐證該索引快照，不宣稱已查驗研究日最新 HEAD。沒有因 API 名稱或範例模型名稱判斷成熟度。

**Closure：**新證據要求重審尚未定案的候選優先序；不推翻 Memory 流程。本文持有細節，父稿、主流程及 register 只指路。未安裝、執行框架／模型測試或改 production。

**下一個 gate／停止線：**依 §5 先釐清可組合元件的責任、輸入／輸出與保存位置，再比較公開接法；不要求 Owner 先在套件名稱間二選一。最小驗證門檻仍是最新原句、兩工具中間切點、超大尾段、摘要後原文回讀、主模型失敗恢復與 request 預算；不是新增 spike 授權。停止廣泛重搜同類文章；只有公開 API 缺口、版本反證或上述檢查會影響接法時補證。接著回原定 B 生命週期與 Q018，不重做五 artifact。

## 5. Owner 澄清：可組合元件，以及「先摘要再給模型」

**2026-09-06／Q017 G4，說明與偏好紀錄，非施工授權。** Owner 偏好能自訂組合以承接既定 Memory／Context 流程，並詢問摘要時點及 Agent／Tool／Skill／Memory 如何接起來。此偏好延續 Q015，不推導已選摘要引擎、額外 history artifact 或全套 Harness。

### 5.1 先摘要再組 Context 是官方可用接法

**Official fact：**LangMem 官方 guide 同時提供「函式先產生結果，再呼叫主模型」與獨立 `SummarizationNode → call_model` 兩種 recipe。未到門檻直接返回訊息；到門檻才呼叫摘要模型，產生 summary＋remaining messages，並利用先前 RunningSummary 避免每輪重摘要相同內容。官方亦建議完整 messages 與摘要結果分欄保存；ReAct 範例在工具結果回來後，再經摘要節點才回模型。[完整官方 guide](https://langchain-ai.github.io/langmem/guides/summarization/)

**需分清四件事：**①何時檢查／產生摘要；②選哪些訊息及如何保持工具配對；③摘要結果何時寫回可恢復 state；④最終給模型哪些規則、Memory、工具與訊息。先摘要解決順序，但不自動解決其餘三項。§1.2 的內部切點反例仍在；即使 caller 先選好一段已結束的舊對話，helper 內部仍可能再切段，不能未核對就宣稱修好。保存時點沿用[父稿 §9.6](2026-09-05-conversation-compaction-framework-gap-review.md#96-接續查證成功保存時點恢復與接線門檻)。

**組合方向，非最終 hook 順序：**先掌握固定規則／工具／已選 Memory 等大小，分配對話預算；有必要才摘要舊對話，再組成實際 model view，呼叫前核對完整預算。每個 model step 都可檢查，但不是每一步都額外呼叫 LLM 摘要。摘要模型也可以與主模型使用同一型號；實際生成摘要時仍是另外一次模型 request。讀取已保存摘要、guide 或工具 I/O，本身不等於一次模型呼叫。

Continuation summary 只為長 Context 延續，不是 B1 訪談詳記、B2 工作理解／導覽，不能因都有「摘要」二字而合併用途，也不讓 B1 改讀有損 continuation 代替 canonical 原文。

### 5.2 框架元件不是各自一個 Agent

| 層／公開接點 | 如何使用與組合 | 不可誤認 |
|---|---|---|
| Chat model adapter | 配置模型、參數，供 Agent／摘要／抽取呼叫 | 換 adapter 不保證所有 provider 參數與能力完全一致 |
| LangChain `create_agent` | 接 model、tools、middleware、checkpointer／store，建立 LangGraph 上的模型↔工具 loop | 不需另寫同功能 while-loop；一次 run 可有多次模型 request |
| Tool／`@tool` | 函式與參數說明成為可呼叫工具，框架執行並回傳結果；Runtime 可注入 state／store | 不是所有內部函式都該暴露成 Tool；Runtime 參數不交 LLM 填 |
| Context middleware | 在模型呼叫前後讀資料、組裝或覆寫本次 request；需要持久化的更新另走 state | 改 request 不等於改資料庫原文；不是只能選預設 prompt |
| Skill 支援 | 先提供名稱／描述／位置，相關時透過 read 工具讀完整指引與引用檔 | Skill 不是另一個 Agent；載入指引不自動新增任意可執行工具 |
| Checkpointer | 保存 graph 實際提交的訊息／state、支援恢復 | 不會自行抽取、整併知識，也不會保存未交回 state 的區域變數 |
| Store＋可選 StoreBackend | Store 保存資料；StoreBackend 讓資料能以虛擬檔案方式供讀寫工具使用 | 不是第二套資料庫，也不是裝好便自動完成 Memory pipeline |
| LangGraph workflow／背景 Agent | 已知順序以 task/node 接力；需要按需補查的整理步驟可用 `create_agent` | 每個 node 不一定有 LLM；不因流程圖有多格就新增多 Agent |

官方證據：[Agent 組合與 loop](https://docs.langchain.com/oss/python/langchain/agents)、[middleware 公開 hooks](https://docs.langchain.com/oss/python/langchain/middleware/custom)、[ToolRuntime 注入](https://docs.langchain.com/oss/python/langchain/tools)、[Skill progressive disclosure](https://docs.langchain.com/oss/python/deepagents/skills)、[Skill 實際讀取指引](https://reference.langchain.com/python/deepagents/middleware/skills/SKILLS_SYSTEM_PROMPT)、[StoreBackend](https://docs.langchain.com/oss/python/deepagents/backends)、[workflow 與 Agent 區別](https://docs.langchain.com/oss/python/langgraph/workflows-agents)。Checkpointer 與原文保存細節沿用[既有底層 trace](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md)。

### 5.3 本輪收斂：組合不是任意拼接，也不是整包二選一

Deep Agents 自身是在 `create_agent` 上組裝的較完整 Harness；官方也提供獨立 `FilesystemMiddleware` 接到 `create_agent` 的範例。因此比較單位應是所需公開能力，不是「可組合＝只能 LangMem；Deep Agents＝只能整包」。Skill loader 必須有可讀的 backend／read 工具，摘要元件要有合適的 state 與 budget，不能只把類別名稱加入清單就算接好。[框架分層](https://reference.langchain.com/python/deepagents)、[獨立 filesystem 接法](https://reference.langchain.com/python/deepagents/middleware/filesystem/FilesystemMiddleware)

既定 A 前台／B 背景／C 窄修補仍依[接力稿 §3](2026-09-05-openai-shaped-memory-framework-composition-research.md#3-建議如何接成完整流程)；本輪沒有核准新工具清單、排程、B/C 協調或額外 Agent。框架提供 loop、hooks、工具執行、保存與公開讀寫；我們負責依既定流程接合、隔離文件範圍及提供分析指引，具體接點仍要核對。這是官方提供的擴充方式，不宣稱 OpenAI／Anthropic 內部使用相同 SDK，也不宣稱尚未測試的組合已是最佳。

**證據與紀錄界線：**本輪完整重讀決策流程／register／本子稿，定向回看接力稿 §3 與父稿／主流程路由；重新讀官方 LangMem guide，補核 Agent、middleware、Skill、backend 的官方頁面及 reference 索引。沒有重查 OpenAI、鎖定最新可相容套件組合或執行框架測試。本文持有說明，其他三份文檔只更新路由，避免再增加一份大研究稿。
