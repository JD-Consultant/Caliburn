# Q017：Memory 全流程框架組合提案

> 2026-09-05 · **G4／供 Owner 審核，尚未核准本稿新增接法**。
> 父層：[已暫准框架方向與 A/B/C](2026-09-05-openai-shaped-memory-framework-composition-research.md)；狀態：[current register](../current-decisions.md)。本稿只保存整體組合與取捨，不再複製 OpenAI 名詞研究，不套 JD、不施工。
> **最新閱讀路由：**Owner 已同意[等價實現原則](2026-09-05-work-understanding-memory-flow-working-design.md#01-owner-澄清流程效果必須達成實現方式不鎖死)，不要求逐項選唯一格式；五產物及按需停止審核見[流程稿 §8](2026-09-05-work-understanding-memory-flow-working-design.md#8-五個產物與按需深入的定向審核)。下文較早的待選／單一 gate 描述是提案沿革，當前接續原文契約→Context／Compaction，依 register 推進。
>
> **2026-09-06 最新接線入口：§7。** Owner 已同意「原生 reasoning／thinking 承接多輪分析，長期 Memory 保存可修訂知識並按需供 Context」。不以另存每輪筆記作預設、不取消 A/B/C。先審整體接線，再深入接點與必要擴充；§1–6 為組合沿革，舊 Compaction 優先序與下一 gate 不再單獨帶領討論。概念同意不等於端到端相容性／品質已通過。

## 1. 本次問題、研究範圍與結論

Owner 已理解摘要路由，要求進入「整套流程怎麼用框架實現、哪些差太多不值得硬接」的研究。這不等於已批准 record-to-filesystem adapter、Compaction 引擎或並行協調。本稿沿用已准的 A 主 Agent、B 背景抽取／整併、C 主 Agent 內的修補 Tool。

**結論：可以提出完整組合，不需重寫 Agent loop、檔案工具或儲存引擎；但排程、原文讀取契約與共用寫入協調不能假裝已由元件自動串好。** 官方能力是事實；以下接線與優先順序是研究提案，不宣稱各廠使用同一套底層或已實測效果最佳。

本輪完整回讀 current register／decision-process、父稿、B 背景流程、抽取產物接力、原文／摘要小元件、摘要路由與 Q018 協調子稿；沒有讀 Owner 排除的舊產品長稿。只補框架官方契約與版本，不重新研究已查清楚的 OpenAI。

2026-09-05 重新查詢官方 PyPI：LangChain **1.4.0**（09-03）、LangGraph **1.2.11**（08-11）、Deep Agents **0.7.13**（09-02）、LangMem **0.0.30**（2025-10-27）。日期是發布時間，不是品質排名；Deep Agents Beta／LangMem pre-1.0 的風險仍保留。尚未安裝或證明四者相容。[LangChain](https://pypi.org/project/langchain/1.4.0/)、[LangGraph](https://pypi.org/project/langgraph/1.2.11/)、[Deep Agents](https://pypi.org/project/deepagents/0.7.13/)、[LangMem](https://pypi.org/project/langmem/0.0.30/)

## 2. 元件逐項接法：不是一個名詞一個新服務

| 既有責任 | 建議的官方基礎 | 應用仍須接什麼／不能假定什麼 |
|---|---|---|
| A 主 Agent 的 model↔Tool 循環 | LangChain `create_agent` | 提供模型、工具與 prompt；不自行再寫循環 |
| Conversation／Session／raw rollout 的互動內容 | LangGraph messages＋PostgreSQL Checkpointer | 明確保存的角色／內容；B 與 A 深查共用一個原文 reader，不為每個名稱另存副本 |
| Compaction／有界 Context | 優先審獨立 Deep Agents summarization；LangMem 公開短期摘要 helper 作替代 | 引擎尚未選定；必須區分 request view、目前 state、歷史 checkpoint 與衍生 archive，見 §4 |
| Extraction 的摘要＋候選 | `create_agent(response_format=...)` 或公開 structured model binding；LangMem `create_thread_extractor` 可比較 | 定義抽取內容；原文位置由 Runtime 附加。單純 parser 不自帶模型修正循環 |
| `raw_memory`／`rollout_summary` 中間產物 | `BaseStore.put/get` 紀錄或 `StoreBackend` 檔案，表示未選 | 兩種語意內容不必兩張表；穩定引用、選取範圍與 model-visible rendering 由應用接合；依產物接力 §8 比較，不先指定紀錄 |
| `rollout_slug`／來源 metadata | 抽取的可讀標籤＋Runtime 已知來源位置 | 標籤不是可靠身分；不叫模型生成 checkpoint ID、時間或存在性保證 |
| B consolidation | 另一個 `create_agent`，配置 Memory 檔案工具＋摘要 reader | 用 prompt 指示去重、補充、修訂與引用；可在整理途中補查，不只一次封閉 structured output |
| `MEMORY.md` 類主題正文 | Deep Agents `FilesystemMiddleware`＋`StoreBackend` | 用官方列舉／文字搜尋／分段讀取／編輯；Store scope 由 Runtime 提供，不由模型選 |
| `memory_summary.md` 小型導覽 | 同一 backend 保存，B 整併時更新；A 用官方 model hook 載入 | 不另叫第三個 Agent 生成導覽；導覽載入是 I/O，不是重新摘要 |
| 摘要引用→原文深查 | LangChain `@tool`／`ToolRuntime`＋Store.get／graph state API | 用已提供引用讀取，不讓模型猜地址；B Phase 2 只給摘要，A 必要時才給原文入口 |
| C live repair | A 的同組 Memory edit 工具 | 不是第三個 Agent，不重跑 B；只在已准的明確過時／需當輪修正情況使用 |
| 背景步驟結果與恢復 | LangGraph Functional API `entrypoint`／`task` | 保存 task 結果，不是 scheduler，也不保證 Store 多筆寫入原子交易 |
| 錯誤回饋／有界修正 | 官方 `ToolErrorMiddleware`、適用的 Retry／CallLimit 元件 | 分清確定失敗、結果不明與正常錯誤回傳，不盲重試修改工具 |

表中根 Agent、Store／檔案工具、ToolRuntime 是公開能力：[Agents](https://docs.langchain.com/oss/python/langchain/agents)、[backend 存放與路由](https://docs.langchain.com/oss/python/deepagents/backends)、[ToolRuntime／Store.get](https://docs.langchain.com/oss/python/langchain/tools#long-term-memory-store)。原文、摘要與 metadata 的細項限制沿用[小元件 source trace](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md)、[產物接力 §2–4](2026-09-05-memory-extraction-artifact-framework-handoff-review.md)。資料用途與 producer／consumer 沿用[摘要路由證據](2026-09-05-memory-summary-routing-and-deep-read-source-review.md)，不由本表重新發明。

## 3. 實際如何接起來

> **後續閱讀順序更新（2026-09-05）：**Owner 已確認[內容分層 §2.1](2026-09-05-work-understanding-memory-flow-working-design.md#21-同一內容在不同層的樣子)，本輪要求先回讀 OpenAI 引用如何保存／使用。[引用複核 §7](2026-09-05-memory-extraction-artifact-framework-handoff-review.md#7-owner-指正後的引用流程複核先還原-openai再判斷框架缺口)已撤回依假設未知位置缺口優先①的推薦；接法仍 OPEN，先按已核實 producer／consumer 核對。不從概念已清楚推論可施工。

### A：前台互動與按需讀取

```text
新訊息 → 同一 conversation state
       → Context middleware：有界對話／continuation＋小型導覽＋既定少量召回
       → create_agent
           ├─ 資料足夠：回答
           ├─ 不足：搜尋 Memory → 深讀正文 → 依引用讀摘要 → 必要時回查原文
           └─ 明確需修補：C edit → 取得實際結果 → 繼續判斷／回答
```

每次查到夠用就停，不必逐層讀到底；新訊息已在 messages 就不再貼一次。自動召回的頻率、演算法與預算仍待定，**沒有被檔案 grep 自動取代**，也不是每個 Tool step 再叫一個搜尋模型。導覽 hook 使用當時可讀內容，不保證模型 request 送出後會跟著 Store 即時變動。[Context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)、[父稿 §3.4／§4.1](2026-09-05-openai-shaped-memory-framework-composition-research.md)

### B：背景建立／整併 Memory

```text
觸發背景工作，固定這次要處理的 conversation 範圍
→ 共用原文 reader 取得問答
→ Extraction：摘要＋候選資訊
→ Runtime 附上真實來源位置，保存可回讀產物
→ 將同一結果交給 consolidation Agent
    ↔ 讀目前 Memory、按需開摘要
    ↔ 編輯 Memory 正文／引用／小型導覽
→ 依實際結果記錄成功、部分完成或失敗
```

**保存後不需要再呼叫 LLM，也不必為交接再讀一次資料庫。** 保存服務之後的摘要補查與重用；不是抽取資訊必須先落 DB 才有語意價值。保存失敗不能發出假成功的可讀引用，是否先補存或先完成當次分析仍是待審恢復契約，見 [B §3.5](2026-09-05-memory-background-cycle-flow-review.md#35-保存中間結果為了後續補查重用不是才能整併)。

建議 B 用 Functional API 組合少數有明確輸入／輸出的 tasks，整併 Agent 仍用官方循環。這是利用同一 LangGraph 的公開組合，不引入另一套 durable engine。B 執行紀錄與 A 訪談分開，但透過 Runtime 共用同一 Memory scope；不能直接拿各自 thread ID 當兩份 Memory namespace。B 的本次輸入清單與完成結果是 workflow bookkeeping，不叫 LLM填製作進度帳本。[Functional API](https://docs.langchain.com/oss/python/langgraph/functional-api)、[B 流程與未決 trigger](2026-09-05-memory-background-cycle-flow-review.md)

### C：同輪局部修補與 B 的邊界

C 沿用 A 的 edit Tool；B 與 C 共用 Memory 內容，但不共用一份模型對話。**尚不能直接開放無協調並寫。** 原生 StoreBackend 沒有替所有 writer 保證 compare-and-swap；Server 同 thread enqueue 排的是整個 run。要維持已准分工，下一層仍須依 [Q018](2026-09-05-memory-background-live-repair-coordination-research.md) 選修改時協調，而不是把 A／B 全部塞入同 thread，或偷偷新增第三個寫入 Agent。

## 4. 哪些不值得硬套；何時才自己接

### 4.1 中間摘要：提出調整「尚未核准的建議」，不是翻已准決策

**目前接法建議集中在[原生 backend 審閱](2026-09-05-memory-artifact-native-backend-design-review.md)，三方案沿革見[產物接力](2026-09-05-memory-extraction-artifact-framework-handoff-review.md)。** 最新 source trace 後以②原生檔案繼續細化，受 Owner 等價實現原則約束；不要求再選唯一格式，也不表示完整接線已驗證。本稿不維持另一份獨立優先序，以下①／③是歷史，不是現行推薦。

歷史上先以「已有引用精讀」優先③，後以假設未知位置缺口優先①；Owner 本輪要求先回讀已研究的 OpenAI 引用。本次校正不改選任一方案：A 正常沿正文引用深讀，B 另有摘要補查；須連同寫入端的真實位置、關鍵詞與 task-local 引用一起比對框架。[ToolRuntime／Store.get](https://docs.langchain.com/oss/python/langchain/tools#long-term-memory-store)只是精確讀取零件，不由它單獨推導全流程已足夠或必須新增全庫搜尋。current Memory filesystem 方向不變，未批准 adapter。

### 4.2 Compaction：重用公開引擎，不先發明摘要算法

**2026-09-06 最新取捨／待審建議見 [Compaction §9](2026-09-05-conversation-compaction-framework-gap-review.md#9-非破壞性延續兩條既有候選的接線取捨)**：在不另存原文歷史檔的既定邊界下，建議優先 LangMem short-term 公開函式＋model middleware；尚非已核准引擎。下列是兩候選能力，不維持另一份推薦順序；函式輸出不等於 caller／Checkpointer 的保存結果。

- **獨立 Deep Agents summarization**：正常摘要路徑與 model request view 分開，已有延續與工具結果 offload 能力。但 archive 是衍生呈現，overflow 等旁支另有影響，不能宣稱任何情況都原字節無損。確切配置未准。
- **替代是 LangMem `summarize_messages`／`RunningSummary`＋公開 model hook**：不用把 manager 全套帶進來；由我們接 request view 與 summary state。官方明說 `SummarizationNode` 的輸入／輸出 key 預設分開；不要為方便改成同 key 後，又宣稱沒有改目前 messages。
- 不為了熟悉名字就選 LangChain 預設 `SummarizationMiddleware` 並誤稱只改 prompt；其 state 更新與以上不同。

完整固定源碼／reducer／DB 證據在[原文小元件 §3–5](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md)；公開小 API 與預設資料流見[LangMem Short Term Memory](https://langchain-ai.github.io/langmem/reference/short_term/)。本次是優先比較順序，沒有執行舊 spike 或選定引擎。

### 4.3 不用 manager 硬充完整背景 pipeline

LangMem 的 manager／extractor／search／manage 是不同元件。內建 manager 能整理紀錄，**不是原生完整提供本次要求的「持久摘要＋可補查的整併 Agent＋檔案正文／導覽」接力**。因此主方案以 structured extraction＋有工具的 consolidation Agent 組合；若改用 manager 後仍要再跑同一遍 Agent 整併，會重複工作。這不是判定 LangMem 記憶品質差；其抽取／短期摘要小元件仍可用，紀錄式路線也仍是備選。[既有 manager 細節比對](2026-09-05-openai-shaped-memory-framework-composition-research.md)、[抽取三接點](2026-09-05-memory-extraction-artifact-framework-handoff-review.md#21-三個官方接點責任並不相同)

## 5. 本輪新查到可以直接重用的錯誤能力

LangChain **`ToolErrorMiddleware`（需 >=1.3.14）** 已能把拋出的例外轉成模型可見 error ToolMessage，handler 決定安全內容；它**不自動重試**。這能替代通用 exception→tool-result wrapper，但仍須設定哪些錯誤給模型、哪些直接失敗。[官方契約](https://docs.langchain.com/oss/python/langchain/middleware/built-in#tool-error)

正常工具回傳的錯誤結果不等於 Python exception；不多包一層將結果改成假成功。暫時性失敗可使用官方 Retry，有界模型修正用 CallLimit；結果不明的寫入須先確認實際狀態，不因有 Retry 就盲目重放。Structured output 的 `ToolStrategy.handle_errors` 則處理輸出驗證，與 tool execution exception 不同。[Structured output 錯誤](https://docs.langchain.com/oss/python/langchain/structured-output#error-handling)、[Q018 失敗情境](2026-09-05-memory-background-live-repair-coordination-research.md#5-失敗後怎麼辦與上述候選一起審閱)

## 6. 收斂與下一步，不再展開另一份 Memory 總論

- **Finding：**端到端接力有公開框架基礎；自訂集中在來源 reader／產物交接／context policy／執行生命週期，而非資料庫、Agent loop 或檔案引擎。
- **Status：**父層 A/B/C 與根框架方向仍暫准；接續底層研究建議②原生 backend 檔案，但①／②／③仍未選型。Functional API 具體組合與 Compaction 優先序也只是建議，未登記為 Owner 已准。
- **本次唯一 gate：**依產物接力 §8.1 的完整引用交接，收斂中間產物表示／reader；不再以本稿較早的③優先序要求批准，不重問已確認的流程或要 Owner 猜 SDK 參數。
- **通過後剩三組接線契約：**① 原文／摘要 reference 與讀取範圍、Compaction／Context 預算；② B 啟動時機、輸入選取／已處理狀態與失敗續作；③ Q018 B/C 共用修改協調。既有來源夠回答就收斂，不重做概念研究；最後才寫 implementation plan。
- **不先新增：**摘要 router Agent、第三個 guide Agent、獨立語意衝突裁判、原文副本、全文向量庫、CAS／鎖服務或額外 durable 平台。這不禁止日後有明確缺口時討論。
- **成本邊界：**普通 A 可不寫 Memory；C 是按需 Tool；B 有抽取與整併模型工作，整併補查可能多次 request。存產物、讀導覽與保存 task 不另叫模型；尚無 token／延遲測量，不承諾固定兩次或必定省錢。
- **Reopen：**必要效果未覆蓋、官方版本契約改變、相容性查驗不成立或 Owner 新裁決。
- **驗證邊界：**官方文件／固定 source 的研究整合與 PyPI 版本核對，不等於已跑通的程式。無安裝、付費模型、spike、production 變更、commit 或 push。

父稿只增加此提案路由；抽取子稿保留三方案細節並標示最新建議；register 只更新當前 gate。OpenAI 事實、framework source trace 與 Q018 協調證據不搬進本稿，避免再次長文膨脹。

## 7. 原生推理延續＋長期 Memory：目前整體接線

### 7.1 Owner 已同意的分工與本輪邊界

**2026-09-06／LLM-Q017／WORKING，非施工授權。** 原生 reasoning／thinking 支持主顧問跨回合接續分析，不必把全部分析輸出給員工；長期 Memory 處理長訪談後仍可搜尋、修訂、回查的工作知識，按需進 Context。不是兩者擇一，也不把對話歷史或 Compaction 刪掉。原生推理不保證零重算、永久完整記憶、跨模型兼容或免費成本；「可以繼續接線設計」不等於已驗證分析品質。

直接依據與 framework source 已在 [B 審閱 §6.7–6.8](2026-09-05-memory-background-cycle-flow-review.md#68-框架能承接原生推理不等於目前路徑已接好)。本輪只再核對 [OpenAI reasoning continuity](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-across-calls)，不重新研究既有五產物／兩階段。§6.6「主顧問頻繁增量寫 Memory」仍是備選，不因本輪同意而擴大既定 C。

### 7.2 接線總圖（組合提案，不是新增固定 pipeline）

```text
A 主顧問：同一文件的持續訪談
新訊息 → LangChain create_agent（LangGraph 執行）
          ↕ Checkpointer：完整訊息／工具往返／原生延續資料與執行狀態
          → model middleware：依所選 provider 契約組出本次 Context
              · 規則、Skill 入口及本輪可用工具
              · 近期問答＋兼容的 reasoning／thinking 延續
              · 必要時的 Compaction 延續（不取代原始訪談）
              · 小型 Memory 導覽＋既定少量相關召回
          → provider adapter → 模型
              ↔ 按需讀 Memory／詳記／原文，或使用 Skill／JD 工具
              ↔ C：需要時局部修補 Memory，取得實際結果再繼續
          → 保存完整回應；只將對外回答／追問呈現給員工

B 背景：另一次執行，不是另一個員工聊天室
同一份已保存訪談的選定新範圍＋必要舊脈絡
→ Extraction：訪談詳記＋工作資訊候選（及既有短標籤用途）
→ 保存產物與可回查來源位置，同份結果直接交接
→ Consolidation Agent：讀目前 Memory，必要時補查詳記
→ 去重／補充／修訂正文、維護詳記引用／查找詞與小型導覽
→ 同一文件的 Store／StoreBackend，供之後 A 讀取
```

圖中的 Context 是責任清單，不是准許任意改寫歷史前綴或把各類摘要／opaque items 直接拼接。每個 model step 要維持有效的原生訊息序列；新員工訊息不重貼，工具結果交回同一主顧問 loop；讀到足夠即可停，不要求每次深查到底。背景尚未完成時，A 仍有近期問答及可用原生推理，不能把「尚未入長期 Memory」當成「本輪無資訊」。

**兩條知識接續不能誤接：**B 不能把 A 的不透明 reasoning 當成可讀 extraction 素材，不能自行解密或承諾重用全部隱藏分析。B 仍依實際訪談、必要可讀工具成果與已保存的顯式內容整理，並區分員工陳述與 AI 推論；不把 continuation 摘要冒充完整原文。C 成功修改的 Memory 可供 B 讀最新內容，避免重新套回過時理解。同一問題可能由 B 重新分析，這是持久知識整理工作，不承諾完全免除重算。

### 7.3 框架責任：沿已准組合，不重新選四套 Harness

| 責任 | 接點／狀態 | 不自動包含 |
|---|---|---|
| 主顧問及整併模型的工具循環 | LangChain `create_agent`；根方向已准，B 是獨立用途的 Agent | 不需自己寫第二種 while-loop；背景非每回合固定呼叫 |
| 原生 reasoning／thinking 進出 | `ChatOpenAI` Responses／`ChatAnthropic` 等對應 provider adapter；能力已查，實際 route 待核 | 不能把 OpenRouter 路徑視為已與官方直連等價；不在本輪換 provider |
| Conversation／恢復 | LangGraph PostgreSQL Checkpointer；保存完整 message state，不只 `.text` | 被 middleware 排除的內容不會由 Saver 自動送回模型；保留策略仍要接合 |
| Context／按需 Skill、Tool | 官方 model middleware、公開 loader／reader；組合偏好已准 | 原生推理保存與任意重組 Context 不保證相容；不先鎖摘要引擎 |
| Memory 正文／詳記／導覽 | 主要候選仍為獨立 `FilesystemMiddleware`＋`StoreBackend`→LangGraph Store | 同一份持久資料的檔案介面，不是第二套資料庫；引用、範圍與資料接力尚須配置 |
| B 抽取與持久步驟接力 | 公開 structured output＋LangGraph task/node/Functional API 作組合候選；B2 用 `create_agent` 補查 | 不代表一個 manager 已包辦完整 pipeline，也不代表 workflow 自帶背景排程 |

LangMem 的公開抽取／搜尋／摘要元件仍可依用途使用，沒有因採原生推理就整包排除，也不強求使用 manager 後再重做一次相同整併。這是本案對官方接點的組合，不宣稱 OpenAI／Anthropic 使用同一框架。

官方接點：[Agent／Harness 與配置](https://docs.langchain.com/oss/python/langchain/agents)、[Context middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)、[StoreBackend](https://docs.langchain.com/oss/python/deepagents/backends)、[Functional API](https://docs.langchain.com/oss/python/langgraph/functional-api)。原生 adapter 的保存／回傳 source 與 route unknown 見 B §6.8；原文 reader、artifact 與搜尋引用沿用 §2–4 指向的固定 source 子稿，不在本節複製。

### 7.4 下一步按接點收斂，不重做概念研究

1. **第一組：model adapter ↔ 完整訊息 ↔ Context／Compaction。** 核對所選 endpoint 能否承接原生延續、保存與回傳哪些 items、動態導覽／Skill 如何加入而不違反 provider 契約。原生 Compaction 與通用摘要的責任不等價：後者不能解碼 opaque reasoning；不能用「summary＋tail」直接宣稱保存了同等推理能力。先前 `CC-F12–14` 未因本輪同意而消失。本輪不選 provider／引擎／fallback，不偷增加新筆記層。
2. **第二組：Memory 讀寫與 B 生命週期。** 沿既有原文 reader／詳記引用／backend 研究，補觸發、處理範圍、失敗恢復與導覽更新接點；不新增另一個摘要 Agent／分類 Agent／原文副本。
3. **第三組：B／C 修改協調及收尾。** 原生 framework 不保證所有 writer 自動避免互相覆寫，依 Q018 比較真正必要的公開擴充。最後才定版最小驗證／implementation plan；仍須 Owner 核准，不自動重跑已停實驗。

每組固定交付「輸入→官方接點→輸出與保存→失敗／成本界線→缺口」，由現成元件開始，確有缺口才提出擴充與取捨；不要每個欄位另開題。模型／框架可升級，但鎖版本及實際 round trip 尚未完成。

**Closure：**本輪落實已同意的分工，提出整體接線與三組深化順序；§7.1 為 WORKING 分工，§7.2–7.4 為供 Owner 審核的組合／研究順序，非整套已核准實作。來源與責任引用留在本稿，register 只持有現況。未安裝、執行模型／框架測試、修改 production 或 commit／push；若後續相容性或效果證據要求變更分工，先討論。
