# Q017：抽取產物如何保存、回讀與連回原文

> 2026-09-05 · G4／**引用效果與等價實現原則已獲 Owner 暫時同意；接法繼續細化、未實測，不授權施工**。三方案證據見 §3.3；接力覆蓋核對見 §8，最新狀態先看 §0。
> 父層：[框架接力 §3.6](2026-09-05-openai-shaped-memory-framework-composition-research.md#36-資料細節應何時討論已同意順序與完整範圍)。有效決策：[current decisions](../current-decisions.md)。

## 0. 本輪範圍與閱讀路由

**最新接續：**[原生 backend 接法審閱](2026-09-05-memory-artifact-native-backend-design-review.md)已追到 tool 註冊、路由、Store、窗口／錯誤回傳及來源內容；研究建議②。[Owner 最新原則](2026-09-05-work-understanding-memory-flow-working-design.md#01-owner-澄清流程效果必須達成實現方式不鎖死)允許依框架生態細化等價接法，不再將「等待 Owner 選唯一保存格式」當 blocker。①／③仍保留比較及替代條件，不宣稱②已實測最佳。接續[原文契約 §7](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md#7-原文回查契約來源定位與有界讀取)已提出來源定位／有界讀取基線，下一項是 Context／Compaction 保留接線。§8 及較早的「待選」文字保留推薦沿革，不作最新 gate。OpenAI 覆蓋索引仍見[流程稿 §7](2026-09-05-work-understanding-memory-flow-working-design.md#7-openai-流程細節覆蓋索引)。

**建議沿革，不是多份有效決策：**本文曾優先①；[全流程提案 §4.1](2026-09-05-memory-framework-end-to-end-composition-proposal.md#41-中間摘要提出調整尚未核准的建議不是翻已准決策)再以「已有引用精讀」優先③；上一輪又從未知位置查找優先①，Owner 本輪要求先依既有引用研究複核。三者從未獲准為實作規格；不把這次校正寫成 Owner 翻案，已准內容分層、A/B/C 與主要框架方向不變。

**本稿的接法問題：**抽取出的「對話摘要、候選記憶資訊、原文位置」採哪種保存與讀取接法，才能接續 A／B？比較保留在 §3.3–3.5；不是再研究 OpenAI 名詞或重選整套 Memory 引擎。

**前置審核沿革（已接續，非目前 gate）：**Owner 追問「為何不直接交給整併，而要先存」。[B §3.5](2026-09-05-memory-background-cycle-flow-review.md#35-保存中間結果為了後續補查重用不是才能整併)已分開兩階段分析、產物保存、接續時機：直接交接可行；保存服務後續補查／批次重用，不是語意整併必需的演算法步驟。**先審此用途與取捨，不能直接要求 Owner 選本稿 adapter。** ① 仍只是有保存需求時的候選，未核准且不保證最佳。

**接續證據：**Owner 再問「怎麼知道要開哪份相關摘要」。[摘要路由 source review](2026-09-05-memory-summary-routing-and-deep-read-source-review.md)已追到 Runtime 提供地址→整併模型保留 task-local 引用／可搜尋線索→A 沿引用深讀；B 補查摘要但不讀 raw。這補齊保存用途的實際使用者，不把「可以按需讀取」當成 reader 已接好；本稿 §3.3–3.5 接法仍 OPEN。

- 已回讀：[B 流程全文](2026-09-05-memory-background-cycle-flow-review.md)、[artifact 詳表 §4、§5.1–5.6](2026-09-05-openai-memory-artifacts-to-framework-detailed-crosswalk.md)、[原文小元件 §6](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md#6-接續核對同源原文如何供-b-抽取與-a-深查)。不重做 OpenAI 研究，不讀已排除的舊產品長稿。
- 沿用 A 前台讀取、B extraction→consolidation、C 窄幅修補；**B Phase 2 可查摘要，不直接查 raw sessions**。摘要與候選不是 final Memory，也不是 Compaction continuation。
- 只補官方 public API／固定 source 所能回答的細節。最終 schema、來源精確粒度、Compaction、排程／並行協調、JD、production 均未選定。
- 證據標示：**官方事實**＝可查 API／source；**接法建議**＝依公開能力組合，尚非官方現成 pipeline 或 Owner 核准實作。不能把所有能力都存在，寫成組合已跑通。

固定 source 沿用同日研究快照：LangChain `8215039dea978372bd3fd95b88663a11b0159043`、Deep Agents `4e5f9350e4d77b8bf19e472e8414662d3fa59dc0`、LangMem `f8c7ebd6110c124a36995dab645a8cb0eb0b8210`。官方網站本輪重新查閱；這不是宣稱三個 SHA 正好等於一組已測試的發佈版本，施工前仍需鎖定相容 release。

## 1. 先分清五種不同的「結果」

| 資料／名稱 | 官方實際作用 | 不能當成什麼 |
|---|---|---|
| `structured_response`／parsed output | 經指定 schema 解析的抽取結果 | 已自動發布到長期 Memory 或摘要目錄 |
| `include_raw=True` 的 `raw` | **這次模型回應**，可看 usage／tool call 等 | 輸入給 extraction 的完整原始訪談 |
| LangGraph checkpointed task result | 恢復相同工作流程時，可重用已完成的 task 結果 | 自動具備 summary 搜尋／路由的跨工作流程產物庫 |
| `ToolMessage.artifact` | 不送模型、供程式使用的附加資料 | 模型已看見的引用，或自動建立的 durable artifact repository |
| Store item／StoreBackend file | 在 graph state 外明確保存、依 key／path 讀取的應用資料 | 自動替我們決定抽取範圍、內容政策與來源引用關係 |

來源：[Models structured output](https://docs.langchain.com/oss/python/langchain/models#structured-output)、[Agents structured output](https://docs.langchain.com/oss/python/langchain/structured-output)、[Functional API checkpointing](https://docs.langchain.com/oss/python/langgraph/functional-api#functional-api-vs-graph-api)、[ToolMessage artifact](https://docs.langchain.com/oss/python/langchain/messages#tool-message)、[Stores](https://docs.langchain.com/oss/python/langgraph/stores)。

**結論：**已有保存／恢復元件，但「恢復 B 的執行」與「A／B 能按需補查某份摘要」是兩個使用介面；後者要明確接到保存資料的 reader，不能只寫「有 checkpointer 所以完成」。

## 2. 抽取：有現成小元件，不必讓模型兼做存檔

### 2.1 三個官方接點，責任並不相同

| 接點 | 輸入→輸出／處理 | 真正缺少的接合 |
|---|---|---|
| `model.with_structured_output(PydanticSchema)` | messages／prompt → schema instance；可選回傳原始模型回應及解析錯誤 | caller 提供資料與 instructions；不自行查 Checkpointer、不保存摘要、不啟動 consolidation |
| `create_agent(response_format=...)` | 模型／工具流程 → state 的 `structured_response`；ToolStrategy 有格式錯誤回饋機制 | 不因產生成功回應就自動寫 Store；retry／budget 仍須符合選用策略 |
| `create_thread_extractor(...)` | caller messages → LangMem 格式化 → Trustcall extraction → schema instance；預設只有 title、summary | summary＋candidates 要自訂 schema；不是已提供完整 OpenAI Phase 1，亦無產物保存 |

官方依據：[model API 的基底實作](https://github.com/langchain-ai/langchain/blob/8215039dea978372bd3fd95b88663a11b0159043/libs/core/langchain_core/language_models/chat_models.py#L2385-L2565)、[agent output／error handling](https://docs.langchain.com/oss/python/langchain/structured-output#error-handling)、[LangMem extractor](https://github.com/langchain-ai/langmem/blob/f8c7ebd6110c124a36995dab645a8cb0eb0b8210/src/langmem/knowledge/extraction.py#L113-L182)。

**容易誤用的細節：**

- `with_structured_output` 的基底實作是 model binding＋parser；`include_raw` 的 parsing fallback 不是把錯誤回送模型再分析。不能套用 agent ToolStrategy 的 retry 說明，宣稱裸 model wrapper 也自動完成同一修復 loop。Provider adapter 可覆寫實作，實際 method／strict 能力仍依整合契約，不由基底類推所有模型。
- Pydantic validation 檢查格式／欄位約束，不保證摘要語意真實或細節全覆蓋。
- LangMem 會 merge／pretty-render 輸入，先前已查清不是無損原文 reader；這個差異不代表它不能做抽取，但不能藉它的名稱宣稱已保留 canonical IDs。見[原文小元件 §6.3](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md)。

**接法建議：**沿用 B 已准的一次 extraction 輸出兩種語意內容，不為摘要、候選、存檔各新增一個 Agent。模型只寫整理內容；Runtime 使用既有 API 加上已知來源位置、保存結果。精確選哪個 extraction wrapper 留在同項收斂，不重開兩階段目的，也不把加入檔案操作 Tool 當成抽取必備。

**呼叫數不能由產物數量推算：**extraction 與後續 consolidation 是兩階段；Memory 正文與導覽在後者維護。Consolidation 的 Agent loop 可包含多次模型／Tool 往返，不是整個 B 固定兩次 request。官方依據、例子及 I/O／模型成本邊界見 [B §3.4](2026-09-05-memory-background-cycle-flow-review.md#34-呼叫計數釐清兩個階段不是固定兩次-api-request)。這項釐清不代表 §3.3 的保存方案已被核准。

空 candidates 可以成功；不因此強迫新增 current Memory。摘要是否有值得保存的內容，與候選是否為空分開。OpenAI Codex 的「全部空字串＝no output」與已准 B 契約差異已在[artifact §4.3](2026-09-05-openai-memory-artifacts-to-framework-detailed-crosswalk.md#43-phase-1rollout_summaryrollout_slugraw_memory)保留，不假裝所有官方產品都一定產生非空摘要。

## 3. 保存：BaseStore 紀錄與 StoreBackend 檔案都是官方能力

### 3.1 BaseStore：結構化內容直接保存

**官方事實：**`put/aput(namespace, key, value)` 保存 JSON dictionary；`get/aget` 依 key 讀取；`search/asearch` 可列舉／filter，設定 embeddings 才有相應語意檢索。key 可由程式產生，namespace 由應用提供；框架不要求模型填這兩者。Store item 有建立／更新時間，但這不是訪談發生時間。[官方基本用法與 API](https://docs.langchain.com/oss/python/langgraph/stores#basic-usage)

**能接的部分：**抽取內容與 Runtime 的來源定位，可以作同一筆 JSON 產物保存；不必將同一原始對話複製進 Store。實際包含哪些欄位是應用接合，不是框架已規定的 universal extraction schema。

**限制：**一般 JSON record 不會自動成為 filesystem 的 Markdown 檔案。若後續 Agent 要用現成檔案讀取工具，需要 BackendProtocol 轉成唯讀視圖；若直接用 record reader Tool，則不用這層檔案視圖。這是兩個選項，尚未決定。

### 3.2 StoreBackend：Runtime 可直接保存文字檔案

固定 source 的公開 constructor 可傳 `store=...` 與 `namespace=...`；在 graph 外使用時，namespace factory 必須不依賴不存在的 Runtime。`write/awrite(path, content)` 將文字透過官方 FileData 轉換寫入 Store。**不必叫 LLM 再使用一次 write 工具才能保存。**[constructor／scope](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/store.py#L100-L168)、[write 實作](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/store.py#L428-L474)

讀取也有公開 API：

- `read/aread(path, offset, limit)`：先 Store get，再對文字切行；回傳 ReadResult，含範圍／後續 offset 等。**模型拿到有界內容，不代表資料庫只讀那幾行。**
- `download_files(paths)`：完整檔案 bytes，供程式處理；不是重新呼叫模型。這是已存的產物檔案，不代表自動讀原始對話。
- `ls/glob/grep`：檔案導覽／搜尋。固定 StoreBackend 的 grep 先分頁取得 namespace items，再做 literal match；**不是向量搜尋，也不保證大型集合只查少量 DB rows**。

來源：[read／aread](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/store.py#L366-L426)、[ReadResult](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/protocol.py#L203-L241)、[grep](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/store.py#L593-L611)、[download](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/store.py#L689-L719)。

**重要限制：**官方 FileData／轉換只處理 content、encoding、created_at、modified_at。不能私自在同一 Store item 掛 `source_ref`，然後假設所有檔案 write/edit 都會幫忙保留：固定轉換只重建那些欄位。來源若放文字內、存 record envelope 或由額外映射維護，各有接線取捨，尚未核准。[FileData](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/protocol.py#L187-L200)、[讀寫轉換](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/store.py#L170-L228)

### 3.3 同一底層，兩種取捨；不是決定再建第二份原文

兩種保存表示，展開成以下三個實質接法。①的原始理由與限制保留如下，**目前判斷統一看 §7，仍未核准**；範圍只有 extraction 中間產物，不把 current Memory 也改回 LangMem record 方案。

| 候選接法 | 效果／現成能力 | 成本、錯誤風險與可逆性 |
|---|---|---|
| **① Record 保存＋唯讀摘要檔案視圖** | BaseStore 保存摘要、候選及 Runtime 來源定位；B 程式直接取候選。模型經 BackendProtocol 視圖，沿用 filesystem 的搜尋／分段讀取，不必讀整包 JSON | 需自行接唯讀 adapter，包含路徑映射、列舉／搜尋及結果分頁；不是零自訂。無第二份持久摘要，因此沒有 record／摘要副本同步；搜尋成本仍需受控。之後換 reader 不必重做 extraction |
| **② Runtime 直接存 StoreBackend 檔案** | 最直接重用原生 file read／grep／glob；來源可由 Runtime 寫在內容標頭，不需模型產生 | 單檔可用 JSON 或分區文字保存全部內容，並非做不到；但程式與模型需約定各區讀法。若拆 summary／candidate／metadata 多檔，增加保存／恢復接合；並非框架自動整批發布。可轉回 record，但需解析檔案格式 |
| **③ Record 保存＋專用 reader／search Tools** | 不做檔案視圖；官方 ToolRuntime＋Store.get 可直接讀摘要，框架 Store 支援資料查詢 | 精確 reader 較直接；但要另收斂模型的查找、回傳範圍與搜尋方式，不能把未設定 embeddings 的 `Store.search(query=...)` 當文字 grep。若只需已知 reference 深讀，此方案可能更省接線；換成檔案視圖可不改保存內容 |

**① 的取捨理由（不再作有效優先推薦）：**中間產物同時供「程式交接候選」與「Agent 按需深讀摘要」使用。保存時保留這兩種內容及已知來源的關係；讀取時只呈現此用途需要的部分。與已暫准 filesystem 接力一致，又不要求程式從模型可讀 Markdown 拆回候選／可信 metadata，代價是 adapter。③ 可改用精確 reader，但仍須覆蓋 B 的實際摘要目錄／補查需要；不能只用 A 的精讀需求判斷整體已足夠。三方案均未選。

依據為 §3.1–3.2 的官方保存契約、[公開 BackendProtocol 擴充方式](https://docs.langchain.com/oss/python/deepagents/backends#custom-backends)、[ToolRuntime 直接讀 Store 範例](https://docs.langchain.com/oss/python/langchain/tools#long-term-memory-store)。**沒有證據能說這三者中某一種是所有大廠唯一共識，或僅換表示就能提高模型記憶品質。**

### 3.4 建議中的「檔案」只是讀取視圖，不是第二份保存

```text
BaseStore 的一筆 extraction 產物
  ├─ 程式讀取：本批候選 → B consolidation 輸入
  ├─ 唯讀視圖：摘要內容＋可回帶的來源 reference → 現成 filesystem Tools
  └─ Runtime 讀取：來源定位 → 同源 conversation reader
```

視圖是一般程式將 record 呈現為文字，**不是再請模型摘要，也不預先另存一份 Markdown**。小型 Memory 導覽與 current Memory 仍依父層後續議題處理，不混進 extraction 產物。

既有 OpenAI 研究已查出 Codex「Stage 1 結果存 DB，Phase 2 將選定輸入整理成模型可讀檔案」的分工；因此不能把「模型用檔案」推成「所有資料一開始都只能是檔案」。本建議學的是保存與使用介面分開；**Codex 實際 materialize 檔案，而這裡建議按讀取呈現，不宣稱物理實作相同**。[既有 artifact 詳表 §4.3–4.4](2026-09-05-openai-memory-artifacts-to-framework-detailed-crosswalk.md#44-phase-2-輸入與控制-artifacts)，原始 OpenAI 證據沿用該稿，不重查。

### 3.5 哪些可直接重用，哪些確實要自己接

| 責任 | 框架原生部分 | 必要接合／不能冒稱現成 |
|---|---|---|
| 保存產物 | BaseStore `put/aput`、`get/aget`、namespace 與 JSON value | 本次輸入範圍、記錄 key、內容組裝及交接由 Runtime 處理；保存成功後可直接傳手上結果，不必為傳參數重讀一次。失敗時的續做政策未定，沒有跨所有副作用 exactly-once 保證 |
| 給模型讀摘要 | 獨立 FilesystemMiddleware 的工具；CompositeBackend 路由；BackendProtocol／ReadResult | **record → 摘要視圖 adapter 是我們要寫的擴充**。至少涵蓋所暴露的 read／ls／glob／grep、穩定路由、分頁與錯誤；不能說 framework 自動知道哪些 JSON 欄位是摘要 |
| 限制摘要只讀 | 官方 backend wrapper／subclass 接點 | 拒絕所有實際可到達的寫入路徑；sync／async、delete／upload 一併核對。不使用 standalone middleware 的 private `_permissions` |
| 回查原文 | ToolRuntime 注入、主對話 graph `get_state/aget_state`、既有訊息小元件 | 直接 reader Tool 解 reference、限 scope、選取問答及呈現。**不再替原文做第二個完整 filesystem adapter**，B Phase 1 可在程式內共用 reader |

公開契約：[BackendProtocol read／分頁](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/protocol.py#L404-L497)、[CompositeBackend 路由](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/composite.py#L195-L225)、[policy hooks](https://docs.langchain.com/oss/python/deepagents/backends#add-policy-hooks)、[原文 reader 完整查證](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md#6-接續核對同源原文如何供-b-抽取與-a-深查)。使用公開 protocol，不繼承／覆寫 StoreBackend 私有轉換函式來偷塞 metadata。

**另查 LangMem，沒有因為選 filesystem 就漏看：**`create_search_memory_tool` 可自訂 namespace／name／instructions，實際把 query／filter／limit／offset 交給 Store，並將整筆 `m.dict()` 序列化回模型。`content_and_artifact` 只是多帶 raw objects，**不會自動把可信 metadata 隱藏、也不會只回 summary 視圖**；改名仍有 long-term-memory 的預設 description。它可作 ③ 的搜尋零件，但不能直接叫它 rollout reader，或只靠工具名斷定功能已等價。[官方固定實作](https://github.com/langchain-ai/langmem/blob/f8c7ebd6110c124a36995dab645a8cb0eb0b8210/src/langmem/knowledge/tools.py#L362-L486)

**成本／驗證界線：**上述保存、render 與 reader 是 I/O，不額外加 extraction model call；Agent 是否深讀仍會影響 tool steps／tokens。自訂視圖的 grep 不是 Store 自動全文索引，列舉多筆 record 可能掃描較多資料；不得因回傳少量就宣稱查詢成本低。讀取上限、搜尋範圍與相容性須在核准後的接線中驗證，不能現在宣稱最便宜或全量無漏；也不因此提前加入向量索引、複製快取或新的搜尋服務。

## 4. 來源位置：Runtime 已知什麼，模型需要看到什麼

**官方事實：**原文 reader 可使用 graph state/config 與 canonical messages；能力／限制見[原文 source trace §6.1–6.2](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md)。Store 不會替抽取結果自動連到這些資料。

**接法建議（適用三方案；精確表示待審）：**B 的 loader 既已選定一段輸入，就由 Runtime 在產物中記下該選取位置，不要求模型從正文猜 database identity。模型看到的是可原樣帶回的 reference，由 reader 解析回已保存的位置，而不是由模型填 thread／checkpoint／時間。這是「本份產物根據哪段輸入整理」的粗粒度關係，**不是每個候選句子已通過引文驗證**，也不自動解決 Q014 的 final Memory lineage 位置裁決。

必須把下列接線規則講清楚，尚不是最終欄位表：

1. 原文定位必須能回到當時被抽取的問答範圍；只記 thread、之後一律讀 latest，不能表達同一 thread 的多次抽取邊界。實際用選定 checkpoint／訊息範圍的哪種組合仍待收斂，不把 checkpoint ID 叫 rollout ID。
2. Locator 不會自己保護原文免於 retention／刪除；任何保留政策不得偷偷讓定位變成空連結。這輪不新增 immutable archive 或清除歷史。
3. A 若要依摘要再呼叫原文 reader，模型可見內容必須有可原樣帶回的路由提示／reference；若只放在 `ToolMessage.artifact`，模型根本看不到，無法依它發起下一個 Tool call。DB scope 等可信資料仍不必暴露給模型。[官方 content／artifact 區分](https://docs.langchain.com/oss/python/langchain/messages#tool-message)
4. B Phase 2 的 backend／工具只提供摘要與 Memory，不因摘要附有來源資訊就獲得 raw reader。原文 A 查詢與 B Phase 1 loader 可重用同一資料 reader，但可見能力不同。

**具體情境：**本次抽取的是對話前半段，之後同一 thread 又增加新訊息。A 從某份摘要回查時，reader 必須定位到那份產物實際使用的原始問答，不能改讀最新末尾。若指定範圍不可得，要明確回報，不能改用摘要冒充原文。若後來發生更正，舊摘要仍是當時互動參考，不因較舊就當 current truth；如何在新版 Memory／導覽路由到更正內容，留在後續 current Memory 與 A/B/C 接力，不自行加 stale 欄位。

File reader 的唯讀限制有官方 wrapper／subclass 接點；不是複製檔案引擎。不過官方示例只示範部分 write/edit，實際組裝必須檢查所有可到達的寫入方法及 sync/async 路徑，不能把一個 prompt 寫「請勿修改摘要」當成唯讀保證。[Backend policy hooks](https://docs.langchain.com/oss/python/deepagents/backends#add-policy-hooks)

## 5. 接力示意與本輪不做的事

以下僅展示 **① 選項內部**如何接合，不是目前推薦或已准流程；三方案共同的引用交接核對見 §8。

```text
既有原文保存層
  → 共用 reader 選取範圍（Runtime 知道原文位置）
  → extraction：整理摘要＋候選內容
  → 檢查模型實際解析結果
  → Runtime 附來源位置、用 BaseStore 保存同筆 extraction 產物（若選 ①）
  → B Phase 2 接收同份結果中的候選＋可讀位置（不必為交接重讀 DB）
  → 透過唯讀檔案視圖按需查摘要，整併 Memory
  → 未來 A 同樣按需讀摘要；真正需要時再用直接 reader Tool 回查同源原文
```

這是**依公開元件可組合的接力建議**，不是任何框架開箱即用的完整產品。保存是一般程式 I/O，不新增模型呼叫；亦不代表須等下一次排程，但抽取／整併本身仍有成本。**解析失敗與 Store failure 必須分開**：前者可能沒有可用結果；後者不表示手上抽取內容無效，但不得宣稱已持久保存或提供假成功的可讀 reference。保存失敗時是否先補存再繼續、或當次交接後另行恢復，尚未核准；見 [B §3.5–4](2026-09-05-memory-background-cycle-flow-review.md#35-保存中間結果為了後續補查重用不是才能整併)。已完成 task result 可助恢復，不代表任意跨 Store 副作用 exactly-once 或兩檔交易；錯誤預算及 Q018 不在此偷定。[Functional API 官方恢復範例](https://docs.langchain.com/oss/python/langgraph/functional-api#example)

## 6. 審核收斂與下一步

- **Finding／status：**官方接點與 §3.3 三接法比較保留；**接法仍 OPEN**。上一輪優先依據的修正與 A/B 引用責任見 §7；不把概念同意登記為格式／adapter 核准。
- **Why／sources：**避免誤把框架名詞當作 pipeline；逐項官方文件、固定 source 與既有 OpenAI 研究均貼在對應段落。無新 OpenAI 概念研究。
- **未新增的義務：**無逐句 source／quote／Skill ID schema，無原文副本，無無條件摘要成功／無損承諾，無自訂寫入協調器。
- **Affected：**本輪只更新本子稿、全流程提案的當前建議指路、工作理解流程稿的下一步及 current register；既有 B 與 artifact 詳表維持用途證據，不複製另一份總稿。
- **Next gate：**§8 已完成引用 producer／consumer 的公開接點對照，接續收斂 §3.3 的保存表示與 reader；B 生命週期及 Q018 仍未決。不重問 summary 是什麼、工作理解是否 JD Task 或原文在哪。
- **Reopen：**官方 API／資料流改變、Owner 改目的，或之後最小相容性驗證推翻接法。不是單純出現另一個類似名詞就重做所有研究。
- **驗證範圍：**文件與 source review；沒有執行框架測試、付費 LLM、spike、production 更改、commit 或 push。本文不宣稱最新版本組合已實測成功。

## 7. Owner 指正後的引用流程複核：先還原 OpenAI，再判斷框架缺口

### 7.1 審核修正與效力

**Q017-REF-F01／P2／已修正文檔、接法仍 OPEN：**上一輪由「A 案例沒有出現在工作理解引用裡」推導前台必須直接探索詳記庫，再以此優先①唯讀視圖；這是尚未證成的應用擴充，不能取代已研究的 OpenAI 寫入／引用流程。Owner 要求先回讀既有研究；本輪**撤回依該假設作出的①優先推薦，不改選③，也不刪掉 B 本來就有的補查能力**。三方案仍只在 §3.3 比較，不再以不存在性假設要求 Owner 立即選 adapter。

本輪完整回讀[摘要路由研究](2026-09-05-memory-summary-routing-and-deep-read-source-review.md)、[09-04 progressive-disclosure 研究](2026-09-04-openai-codex-memory-progressive-disclosure-deep-dive.md)，核對 [artifact §4.3–4.5](2026-09-05-openai-memory-artifacts-to-framework-detailed-crosswalk.md#43-phase-1rollout_summaryrollout_slugraw_memory)及已留存固定 Codex source 的相關段落。沒有新做 OpenAI 網路搜尋，不宣稱重新驗證最新 HEAD；以下限既有研究所記錄的公開實作，不推廣成所有 OpenAI 產品的唯一 schema。

### 7.2 引用不是讀取時才補：producer → 保存 → consumer

| 接點 | 已核實的 Codex 做法 | 框架後續要承接的效果，不是本輪新增 schema |
|---|---|---|
| Runtime 提供真實地址 | 將候選內容與實際 `rollout_summary_file`、`rollout_path` 等來源 metadata 一起提供；詳記正文前亦加原文位置 header | 保存整理結果時就保留可用的詳記／原文定位，不叫模型猜 ID、路徑或時間 |
| 整併模型建立語意關聯 | `MEMORY.md` 在各 task-local 區段放相關 `rollout_summary_files` 與辨識性 `keywords`；相關條件成立才合併，可多對多，不依字面相似強制歸類 | 工作理解的相關知識旁保留模型從已提供位置選出的詳記引用及查找線索；不是全篇末尾一張無差別來源清單 |
| 整併模型維護導覽 | `memory_summary.md` 的主題／用途／keywords 必須能對應到正文；抽象合併仍保留具有辨識力的原始用語 | 「前端開發」等工作性質可以去重，但不能因此把必要的案例查找線索全部抹掉 |
| 前台 A 按需深讀 | 本輪問題＋導覽 → 查 `MEMORY.md` → 沿命中區段引用讀相關詳記 → 精確證據不足才查 `rollout_path` | 先核對這條已設計好的引用鏈是否能寫入、傳遞及讀回，不先假定引用不存在 |
| 背景 B 補查 | 已有本批候選、詳記位置及 current Memory；必要時讀對應詳記，檢查實際存在的摘要檔及引用；該 Phase 2 不讀 raw sessions | B 的摘要列舉／查找與引用核對需要保留；與 A 的日常 quick pass 分別配置，不能因 A 精確 reader 已夠就宣稱 B 也全覆蓋 |

直接來源：[Runtime 地址與摘要 header，storage.rs L44–135](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/src/storage.rs#L44-L135)、[主題內引用／keywords，consolidation L203–328](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/templates/memories/consolidation.md#L203-L328)、[導覽與保留查找線索，L568–602](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/templates/memories/consolidation.md#L568-L602)、[A read policy L31–52](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/ext/memories/templates/memories/read_path.md#L31-L52)、[B 輸入／禁止 raw L119–175](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/templates/memories/consolidation.md#L119-L175)、[B workflow／引用核對 L782–880](https://github.com/openai/codex/blob/574a36ff99f0807a24f5b043f593122bf151908d/codex-rs/memories/write/templates/memories/consolidation.md#L782-L880)。

### 7.3 回到網站案例，不先增設繞路

**示意，不是實際輸出或已准欄位：**工作理解可以寫「依客戶需求開發前端網站」並保留 A／B 案例適用差異、可搜尋用語與相應詳記引用。員工再提 A 網站時，模型從導覽／正文找到該工作主題，讀取該段列出的 A 詳記；需要確認員工當時究竟說了什麼，再沿詳記來源定位讀原始問答。不是把兩個網站一律做成兩個 JD Task，也不是模型只有那句抽象結論可用。

**因此應先檢查：**抽取有沒有留下必要素材？整併有沒有保留引用／辨識線索？導覽能否搜尋到正文？reader 能否用返回的地址讀到詳記及原文？不能略過寫入端，直接把問題定義為「少一個全庫搜尋入口」。

但不反向宣稱引用設計保證零漏記。所查 A quick pass 明示避免廣掃所有摘要，無相關命中則停止此次查找、正常繼續，後續遇到困惑可重查；**不是「沒有引用便自動全庫搜尋」的已證實正常政策**。完整細節找回的產品要求仍有效；若後續證明上述鏈仍漏掉必要資料，再定向討論補救，不預先加入搜尋服務／新 Agent 或刪除能力目標。

### 7.4 框架接法的下一個檢查，而非現在選 adapter

接續按 §7.2 每個 producer／consumer 逐項核對現成保存、模型可見引用、精確 reader、B 摘要列舉／查找及原文範圍接點。①視圖、②原生檔案、③紀錄 reader 都不能只憑名稱判定覆蓋；**A/B 使用政策分開，不代表強制兩套重複資料或兩套工具程式**。

已查官方零件仍有效：BaseStore 保存 record；StoreBackend 原生檔案；FilesystemMiddleware／BackendProtocol 工具與擴充；ToolRuntime／主 graph 原文讀取。§3–4 的 scope、分頁、metadata、只讀及成本限制保留，**不因這次校正就批准任何一種接法**。

- **Status：**引用機制回讀完成；上一輪①優先依據已校正，G4 接法 OPEN。
- **Affected：**本子稿 §0／6／7、全流程提案指路、工作理解流程稿下一步與 current register；不另增 OpenAI 研究長稿，不改原始證據結論。
- **Next gate：**先完成「已核實引用鏈＋A/B 各自查找用途」的框架接點核對，再提出缺口和選型；不是要求 Owner 再批准已研究的引用概念。
- **Stop：**不重做 OpenAI 全套；只有既有證據實際回答不了的新問題才補查；不改程式、不測付費模型、不施工。

## 8. 引用接力的框架覆蓋核對

> 2026-09-05 接續 §7；**公開能力＋組合分析，不是已測試實作或選型核准**。OpenAI 記錄完整性見[流程稿 §7](2026-09-05-work-understanding-memory-flow-working-design.md#7-openai-流程細節覆蓋索引)。本節不再另創搜尋目的，僅逐步檢查既有 producer／consumer。

### 8.1 一條引用實際經過哪些接點

| 接力／必要可見內容 | 可重用的框架機制 | 還需要接合，不能稱全自動 |
|---|---|---|
| B1 拿到所選原始問答，Runtime 知道來源位置 | 主對話 graph `aget_state`／history、框架 message objects | 使用主對話而非 B 自己的 state；選定範圍與原文保留配置。詳見[原文 trace §6](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md#6-接續核對同源原文如何供-b-抽取與-a-深查) |
| 抽取同時回傳詳記與候選，Runtime 附可回查位置 | §2 的 structured output 接點；§3 的 Store／backend I/O | domain instructions／小型輸出契約；地址由保存接點產生或確認，不由 LLM 猜；解析結果本身不是發布完成 |
| B2 取得候選＋可供後續使用的詳記地址 | parsed result 可直接交給 `create_agent`；恢復可用 LangGraph task result | 候選與地址需進模型可見 input；不能只塞 `ToolMessage.artifact`，也不須模型再抄一次存檔 |
| B2 查看實際摘要目錄、沿已知地址補查 | 檔案接法用 `ls/glob/read_file`；record 接法用 Store 列舉／`get` 加公開 ToolRuntime reader | ①須實作視圖；②重用原生檔案；③須接目錄與讀取。Store 列舉不是全文搜尋。只做 exact reader 尚未覆蓋 B 的全部讀取責任 |
| B2 在正文相關主題旁保留詳記引用、keywords | `create_agent`＋既定 FilesystemMiddleware／StoreBackend edit | 哪個主題引用哪份詳記由整併 instructions／模型判斷，不是 framework 自動 foreign key 或語意驗證 |
| B2 維護 guide，A 下一次組裝能載入可讀內容 | 同 backend 保存 guide；官方 Store-aware model hook | guide 仍由 B 維護，不新增摘要 Agent；不能將 MemoryMiddleware 已載快取誤稱自動最新。[guide 接點](2026-09-05-openai-shaped-memory-framework-composition-research.md#41-guide-更新後模型如何看到) |
| A 用可搜尋詞命中正文，再沿地址深讀詳記 | filesystem `grep` 命中 path／line／text，再 `read_file`；③改用 exact reader | 保留 §7 的 quick-pass 政策，不因 B 可列舉就要求 A 每輪全庫掃描；回傳內容有界不等於 DB 查詢量有界 |
| A 從詳記提供的位置讀原始問答 | 公開 `@tool`／ToolRuntime＋與 B1 共用的主 graph reader | reference 解讀、問答窗口及模型可見內容；B2 不提供此 Tool。FileData 不會自己讀 messages，也不因這步再建原文副本 |

證據沿用 §2–4 的固定 source；OpenAI 真實地址與主題內引用依據在 §7.2。框架的直接公開契約：[Store](https://docs.langchain.com/oss/python/langgraph/stores)、[backend read／routing／擴充](https://docs.langchain.com/oss/python/deepagents/backends)、[ToolRuntime](https://docs.langchain.com/oss/python/langchain/tools#toolruntime)。**A/B 分別設定可見能力與讀取政策，可以共用保存內容及 reader；不是強制兩份資料或兩套讀取程式。**

### 8.2 接下來真正要選什麼

三方案都能表示同樣的詳記／候選及引用，差別是如何接合，不是誰「天生更懂員工工作」：

- **② 原生檔案：**摘要地址可直接就是 backend path，原生讀取／列舉最直接；Runtime 可加來源 header。仍要決定候選的程式存取格式、header 讀法及只讀限制，不將多檔寫入說成一個原子交易。
- **① Record＋視圖：**一筆 record 可保留候選、詳記與來源的結構，模型仍看檔案；需寫並維護完整唯讀視圖 adapter，不能把它說成已找到官方現成 plugin。
- **③ Record＋reader：**保留結構、用公開 ToolRuntime 直接取內容；A 的引用深讀直接，B 的摘要目錄／必要查找仍需一併接好，不能只比較一個 `get`。

**本節盤點當時不排優先序；接續推薦集中在[原生 backend 審閱 §4](2026-09-05-memory-artifact-native-backend-design-review.md#4-三選項比較與推薦依據)。** 目前以②繼續細化，依 §0 的最新等價實現原則比較完整接力及實際代價，不要求 Owner 逐項選 SDK 接法，也不用假設漏引用、新 Agent、全庫搜尋或相似名稱補理由。來源 locator／reader 已接續至[原文契約 §7](2026-09-05-framework-conversation-source-and-summary-primitives-trace.md#7-原文回查契約來源定位與有界讀取)；Compaction 保留、B 生命週期及 B/C 協調仍須收斂，不能假裝選完表示就自動解決。

**Closure：**OpenAI 流程記錄與 framework 接點對照已完成本輪文件審核；表示、reader、相容 release 組合及恢復契約尚待選定／驗證。只改研究與路由，沒有框架安裝、API 測試、production 更動或新增已准決策。
