# Caliburn Memory 產品效果映射工作研究

- 日期：2026-08-30
- 最後研究更新：2026-08-31
- 現行整理入口：[`2026-09-01-framework-independent-memory-contract.md`](./2026-09-01-framework-independent-memory-contract.md)
- 狀態：**Working Research；只用於白話討論與持續修訂，不是 ADR、實作規格或施工授權**
- 主題：從 Caliburn 的唯一產品成果出發，判斷成熟 LLM Memory 已能完成什麼，以及是否真的還有產品缺口

> **閱讀規則**：本文以最新產品大方向與 Owner 後續明示討論為準。舊元件名稱、舊資料結構、現行程式與歷史施工文檔都不是研究起點。本輪只比較「產出高品質 JD 需要的 Memory 能力」是否被成熟共同能力或差異能力覆蓋；不盤點、保留、替代或刪除舊元件，也不得為了沿用舊架構而扭曲需求。

> **決策規則**：本文的每項「暫時同意」都可以因新證據或後續整體討論翻案，但必須先列出差異、來源與取捨，再與 Owner 討論；不得靜默改寫已對齊的大方向。

> **2026-09-01 閱讀提示**：後續框架討論先讀現行整理入口；本文保留完整研究、候選與翻案歷史。§6～§8 與 §9 的較早候選不能脫離 §9.32～§9.41 單獨當成現行結論。需要追查證據或重新評估時，再回到本文相應段落。

> **北極星（Owner 於 2026-08-30 再校正）**：Caliburn 的目的只有一個——產出能正確、完整反映員工實際工作的高品質職務說明書。Memory、工作理解、待釐清、Focus、Gap、來源歷史與 Context 都只能是達成這項成果的候選方法，不是產品目的，也不是必須保留的架構。若成熟 Memory 已能讓模型在長訪談中保留完整工作細節、正確吸收更正並可靠形成 JD，就不應為了延續舊討論而額外重建自訂工作理解機制。

## 0. 承接來源

本文件承接兩類資料，但不把它們混成同一層：

1. [通用 LLM Memory 市場流程、共同基線與方案研究](./2026-08-30-agent-memory-landscape-and-decision-working-research.md)：提供跨 OpenAI、Anthropic、Google、AWS 與成熟框架的共同必要行為、差異選項、成熟度與過時技術清單。
2. [產出高品質職務說明書所需的 LLM 能力與機制分工](./2026-08-31-perfect-jd-llm-capability-and-mechanism-working-research.md)：提供唯一產品目標、L1～L11、M1～M11，以及 Memory／Skill／Tool／Runtime／員工 authority 的中立責任邊界。

通用研究回答「成熟 LLM Memory 通常需要什麼」；本文回答「其中哪些真的適合 Caliburn、應如何簡化或調整」。

### 0.1 文檔責任矩陣

後續研究固定依下表落位，避免同一事實、需求與方案決策分散在多份文檔後互相失效：

| 文檔 | 唯一主要責任 | 可以寫 | 不應重複寫 |
| --- | --- | --- | --- |
| [`2026-08-30-agent-memory-landscape-and-decision-working-research.md`](2026-08-30-agent-memory-landscape-and-decision-working-research.md) | 通用 Memory 市場與技術事實 | 各家目前公開機制、跨家共同點、差異、成熟度、限制與不能推論的內容 | Caliburn 要選哪個方案、產品專屬 retention／conflict 語意 |
| [`2026-08-31-perfect-jd-llm-capability-and-mechanism-working-research.md`](2026-08-31-perfect-jd-llm-capability-and-mechanism-working-research.md) | 高品質 JD 成果需求 | L1～L11、M1～M11 與 Memory／Skill／Tool／authority 的中立效果邊界 | 廠商比較、框架推薦、正式資料形狀 |
| **本文** | 產品需求對成熟能力的映射與暫定方案 | M1～M11 覆蓋、Caliburn 真缺口、完整候選組合、效果／成本／風險與暫定推薦 | 重抄完整廠商說明、改寫高品質 JD 的定義 |
| 後續 ADR／design／plan | 經 Owner 核准後的正式決策與施工 | 被接受的架構決策、runtime 邊界、實作步驟與驗證 | 尚未核准的工作研究、所有被淘汰候選的完整歷史 |

因此，本文引用另兩份研究而不複製其整章；若通用事實改變，先更新 landscape，再重做本文 mapping；若產品成果定義改變，先更新 perfect-JD 文檔，再重做本文 mapping。研究未核准前不得提前開 ADR 或施工計畫。

## 1. 本輪目的

本輪不先設計 Caliburn 的 Memory，而依下列順序回答：

1. 為了產出完美 JD，長訪談中的模型必須具備哪些可觀察效果；
2. 通用研究中的成熟 Memory 共同能力，能否直接達成這些效果；
3. 不同成熟方案各自還缺什麼、代價是什麼；
4. 只有在成熟方案確實不能達成必要效果時，才定義 Caliburn 必須補的最薄產品機制；
5. 最後才討論框架、資料結構、Context 組裝、工具與實作。

比較的第一順位是最終 JD 品質與長訪談可靠性，其次是功能完整、錯誤率、成本與複雜度；不能以保留舊概念或少改現行程式為理由增加自訂元件。

## 2. 本輪明確不做

- 不先選 LangGraph Checkpoint、Store、LangMem、PydanticAI、Mem0 或其他框架元件；
- 不先寫 schema、狀態 enum、資料表、API、prompt、tool 或 UI；
- 不把 `Work Model`、`Focus`、`Gap`、`Progress`、`Proposal`、`Current JD` 等歷史名稱當成需求；
- 不把「工作理解／Domain Semantic Memory」的既有設計當成必做答案；
- 不依現行程式方便與否降低產品目的；
- 不在 Memory 討論中同時決定 JD 欄位、OPKS 方法或後續招募／KPI／訓練文件；
- 不授權施工。

## 3. 討論順序

| 順序 | 主題 | 要回答的白話問題 | 狀態 |
| --- | --- | --- | --- |
| C1 | JD 成果所需的 Memory 效果 | 長訪談若要形成可靠 JD，模型必須做到哪些事？ | **M1～M11 已確認，見成品能力研究 §5** |
| C2 | 成熟能力覆蓋 | 跨家共同能力與成熟差異能力已能直接完成哪些效果？ | **第二輪 M1～M11 mapping 已完成，見 §9** |
| C3 | 真實缺口 | 哪些必要效果只缺產品語意，哪些需要選用特定成熟能力？ | **第二輪能力級結論已完成，見 §9** |
| C4 | 方案候選 | 哪些成熟方案組合能完整承接必要能力？ | **已形成框架無關主候選，見 §9.32～§9.40** |
| C5 | 方案與框架 | 哪個成熟組合的效果、可靠性、成本與複雜度最好？ | **已有暫定首選，仍待 Owner 核准，見 §9.41** |
| C6 | 實作映射 | 最終方案如何落到 Context、Memory、工具、狀態與驗收？ | **只完成研究級行為契約，未形成 ADR／plan，見 §9.40～§9.41** |

不能先把產品需求拆成工作理解、Gap、Focus 等既有機制，再逐個尋找框架替身；必須先比較「能否可靠產出完美 JD」所需的中立效果。

> **後續討論紀律（Owner 於 2026-08-30 確認）**：每次提出下一個 mapping 問題前，必須先回看本文已記錄的最新結論，必要時再回看通用 Memory 研究與最新產品大方向文檔。不得只靠對話記憶重述需求，也不得重複討論已確認事項；若發現衝突，先列出差異與來源再討論。

## 4. C1：產出可靠 JD 所需的 Memory 效果

### 4.1 目前已知的成果需求

目前只把下列內容視為需求；它們描述結果，不指定實現方式：

1. 長訪談持續數十或更多回合後，模型仍能正確使用員工先前提供的工作細節；
2. 員工補充或更正後，後續訪談與 JD 不再沿用已失效的理解；
3. 模型不知道或證據不足時不捏造工作內容，而能找回相關資訊或向員工釐清；
4. 形成 JD 時能使用足夠完整、彼此一致且與目前員工實際工作相符的資訊；
5. 不以每輪重送全部歷史換取上述效果，避免成本、延遲與無關內容干擾失控。

這些效果仍需逐項確認與補充，但不預設一定由自訂工作理解、完整 conversation store、某種 Gap schema 或特定框架完成。

### 4.2 先前討論內容的目前地位

下列都只是曾提出的候選方法或概念切分，必須等 C2 成熟能力覆蓋後才能決定是否需要：

| 候選方法 | 原先想解決的問題 | 現在是否必做 |
| --- | --- | --- |
| 完整原始訪談另存並按需搜尋 | 找回舊細節、核實更正與避免全量注入 | 未定；先看成熟 Memory／conversation 能力 |
| 自訂工作理解／Domain Semantic Memory | 長期保留員工完整工作細節並持續修訂 | 未定；先驗證成熟 Memory 是否已足夠 |
| Gap／待釐清資料 | 記得資訊不足、衝突或尚未回答處 | 未定；可能由成熟 Memory、conversation 或 agent state 直接承接 |
| Focus | 讓顧問知道這一輪優先處理什麼 | 不在本輪先當成 Memory 需求 |
| JD 與待審 AI 編輯 | 形成並審核產品文件 | 產品需要，但屬文件工作流，不因而自動成為 Memory 元件 |

### 4.3 先前 M1-1／M1-2 的方向校正

先前曾暫時確認「完整聊天獨立保存」及「建立比 JD 更詳細的可修訂工作理解」。Owner 隨後指出，這兩項確認只表達了想解決的問題，不構成對機制的授權：

1. 真正需要的是長訪談不遺失員工完整工作細節；
2. 真正需要的是更正可生效、模型不因歷史過長而忘記或幻覺；
3. 真正需要的是上述資訊足以形成高品質 JD；
4. 若成熟方案已達成這些效果，自訂工作理解及其詳細 schema 可以完全不做；
5. 只有成熟方案留下可證明的效果缺口，才討論 Caliburn 特有補充。

### 4.4 C1-1 長訪談 Memory 核心驗收效果（暫時確認）

Owner 於 2026-08-31 確認，下列是產品需要的效果，而不是對任何 Memory 結構的要求：

> 經過長期訪談後，AI 在製作或修改 JD 時，仍能正確取得員工目前有效且足夠完整的工作細節；不因對話變長而遺漏、不沿用已被更正的說法，也不在資料不足時捏造內容。

若成熟 Memory 方案已能穩定達成這項效果，Caliburn 不另外建立自訂工作理解 Memory；是否需要原始歷史、獨立工作理解、特定索引或其他產品機制，留到成熟能力覆蓋與真實缺口分析後決定。

### 4.5 C1-2 已回答與仍缺資訊的連續性（暫時確認）

Owner 於 2026-08-31 確認，下列也是為了避免最終 JD 遺漏所需的產品效果：

> AI 在長訪談中應記得哪些重要問題已取得答案、哪些會影響 JD 的關鍵資訊仍未取得；不要反覆詢問已回答內容，也不要因員工暫時轉換話題而永久漏掉尚未釐清的部分。

這項效果不授權建立 Gap、待釐清清單、Focus 或另一份 Memory。成熟 Memory、conversation 或 agent runtime 若已能可靠承接，就直接使用成熟能力。

### 4.6 C1-3 關閉與重啟後自然續談（暫時確認）

Owner 於 2026-08-31 確認：

> 員工可以隨時停止傳訊息、關閉頁面或重啟應用；下次打開同一份 JD 時，AI 仍應延續原本訪談，不遺失已取得的工作細節與尚未補齊的關鍵資訊，也不需要「暫停訪談」操作。

這項只要求可恢復的長訪談效果，不指定 Checkpoint、Store、遠端 Conversation、自訂資料或其他持久化機制。

### 4.7 C1-4 一份員工工作對應一份獨立 JD（暫時確認）

Owner 於 2026-08-31 確認：

> 每位員工受訪的這份實際工作對應一份職務說明書 JD。每份 JD 的訪談與相關記憶必須隔離，製作 A 文件時不得誤用 B 文件的員工工作內容；產品不需要跨 JD 共用記憶。

這不是「第一版暫不共用」的延後項目，而是目前產品關係與隔離要求。底層是否以 scope、namespace、thread、document ID 或其他成熟機制承接，留到 C2 之後決定。

## 5. 通用研究對本輪比較的最低限制

不論最後採什麼名稱或表徵，通用研究已給出以下限制：

1. 原始 conversation、active context 與 durable Semantic Memory 不能互相冒充；
2. 長期 Memory 是選取層，不是逐句複製 transcript；
3. Memory 應是多筆可獨立修訂、語意完整的內容，而不是唯一總摘要；
4. 原始來源與衍生理解分層保留，平常不必全量注入；
5. 更正後只有目前有效 head 參與一般召回，舊版本留在預設不注入的歷史；
6. Memory 是可能出錯的低信任資料，不能取代員工權威、系統規則或文件核准；
7. 具體採 topics、JSON collection、Markdown files、hybrid search 或其他框架，仍未決定。

## 6. C2：成熟 Memory 能力覆蓋（第一輪研究；保留作歷史）

> **取代通知（2026-08-31）**：本節至 §8 是在 M1～M11 尚未完整定義前做的第一輪研究，保留其來源與推理過程，但不再作目前裁決。其「兩個真實缺口」、「Caliburn 最薄差額」與舊設計去留等結論，已由 §9 的 M1～M11 第二輪 mapping 取代。後續不得略過 §9，直接把本節當成框架或實作要求。

### 6.1 證據標示與比較邊界

本節固定使用三種覆蓋判斷，避免因官方功能名稱相似就誤判：

- **直接覆蓋**：官方能力本身即可提供該項產品效果，應用只需做正常的可信 scope 綁定與整合；
- **部分覆蓋**：官方已提供必要 primitive，但仍缺產品語意、正確性保證或時序政策；
- **未證明**：目前官方資料不能證明成熟能力能穩定達成，不能用產品展示、框架名稱或推測補空白。

另須把三種證據來源分開：

1. **已出貨消費型產品行為**：例如 Claude 的分類 topics＋past-chat search、Codex 本機 Memories。它能證明大廠確實採用某種產品設計，但不代表 Caliburn 可直接呼叫同一套私有服務。
2. **模型供應商 API primitive**：例如 OpenAI Conversations／compaction、Anthropic Memory Tool／context editing。它可嵌入應用，但通常只提供 persistence、CRUD 或 context 管理，不替產品保證 Memory 內容完整正確。
3. **可嵌入框架能力**：例如 LangGraph Store／checkpoint、LangMem、PydanticAI Harness、Deep Agents。它們可省去 storage、tool、search、OCC、checkpoint 等程式，但不會自動知道「員工完整工作」應包含什麼。

### 6.2 大廠已共同證明的組合，而非單一 Memory

OpenAI、Anthropic、Google、AWS 與成熟框架目前共同指向下列組合：

| 能力層 | 用途 | 官方實例 | C2 判斷 |
| --- | --- | --- | --- |
| Durable conversation／event history | 保存訊息、工具呼叫與結果，跨 session 延續或回查 | OpenAI Conversations、Claude past-chat search、AWS short-term events、Pydantic StepPersistence | 成熟、必要，但不等於整理後的語意 Memory |
| 可修訂 Semantic Memory | 把值得保留的理解整理為 topics、facts、notebook 或 collection | Claude topics、Codex durable entries、Google Memory Bank、LangGraph collection、Pydantic Memory | 成熟方向；內容目的與完整性仍由產品定義 |
| 按需來源搜尋 | 在摘要或 Memory 不夠時找回原始細節 | Claude chat search、Pydantic ConversationSearch、Deep Agents thread search | 成熟方向；搜尋品質、索引與保留政策各有差異 |
| Context 管理 | 只放少量高訊號內容，長對話接近視窗時 compaction／editing | OpenAI compaction、Anthropic context editing／compaction、框架 bounded injection | 成熟方向；compaction 不能冒充精確長期 Memory |
| Trusted scope／namespace | 防止一份工作的資料被另一份工作讀到 | Claude project memory、Google scope、AWS namespace、LangGraph namespace、Pydantic conversation／namespace | primitive 成熟；安全識別必須由 application 注入 |
| 修訂與生命週期 | 新增、更新、刪除、整併、版本或 rollback | Claude topic edit/delete、Google revisions、LangMem insert/update/delete、Pydantic OCC writes | primitive 普遍存在；立即生效與發布 barrier 並非每家都相同 |

因此，**「只保存 conversation」不夠，「只保存語意 Memory」也不夠，「只做 compaction」更不夠**。成熟大廠的共同方向是分層互補，而不是用單一總摘要或單一向量庫取代所有東西。

官方交叉依據：

- [OpenAI — Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)：Conversation 是帶 durable identifier 的長期物件，可跨 session／device／job 保存 messages、tool calls 與 tool outputs；它提供連續性，不自動整理語意 Memory。
- [OpenAI — Codex Memories](https://learn.chatgpt.com/docs/customization/memories)：本機 Codex Memory 包含 summaries、durable entries、recent inputs 與 supporting evidence；官方明示它只是 helpful recall layer，必須成立的規則仍放受控文件。
- [Anthropic — Claude chat search and memory](https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context)：現行 Claude 同時提供可持續更新的個別 topics 與獨立 past-chat RAG search，搜尋結果可連回原始聊天；每個 project 有隔離的 memory space。
- [Anthropic — Memory Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)：Claude 只提出檔案 CRUD，實際 storage 與 scope 由應用控制；官方建議長任務可把 Memory 與 compaction／context editing 組合使用。
- [LangGraph／LangChain — Memory overview](https://docs.langchain.com/oss/python/concepts/memory)：明確區分 thread-scoped short-term state 與 Store-backed long-term Memory，並比較單一 profile 與多筆 collection。
- [PydanticAI Harness — Memory](https://pydantic.dev/docs/ai/harness/memory/) 與 [Conversation Search](https://pydantic.dev/docs/ai/harness/conversation-search/)：分別承接 bounded notebook 與持久 conversation 搜尋，證明兩層不必自行從零實作。

### 6.3 各方案能直接提供什麼，不能宣稱什麼

| 方案 | 可直接取得的成熟能力 | 不能因此宣稱的能力 | 成熟度判斷 |
| --- | --- | --- | --- |
| OpenAI Conversations＋compaction | 持久 conversation、跨 session 繼續、完整 items、長 Context 壓縮 | 不會自動建立可修訂的員工工作理解；compaction 不保證早期精確細節 | 官方穩定 API primitive |
| Codex Memories | 背景抽取、整併、持久條目與 supporting evidence | best-effort 背景更新不保證下一個相依分析前已發布，也不是可嵌入的公開 semantic-memory API | 已出貨產品行為，可作設計證據 |
| Claude 現行 Memory＋chat search | 對話中更新分類 topics、自然語言更正／忘記、project 隔離、來源聊天 RAG 與引用 | 私有 topic schema、ranking、抽取完整率與底層索引未公開，不能直接移植 | 已出貨產品行為，可作強設計證據 |
| Anthropic Memory Tool＋context management | 模型可按需 read／create／update／delete；應用自管 storage；搭配 context editing／compaction | 仍要由應用實作 backend、安全 scope、內容政策；不自動保證事實真實或完整 | 官方 API primitive；不是託管 Memory service |
| LangGraph 1.x | thread checkpoint、Store、namespace、filter／semantic search、hot/background 更新入口 | Store 不會自動抽取、整併或知道哪些職務資訊重要 | **1.0 LTS、stable API 可作 production substrate** |
| LangMem | 一次呼叫或多步 manager 產生 insert／update／delete，可依 schema／instruction 整理 semantic memory | 不會自動定義產品完整性；模型整理仍可能錯；套件本身成熟度較低 | 0.0.x、GitHub 無正式 release；功能貼近但不能只憑功能採信 |
| PydanticAI Harness Memory＋ConversationSearch | bounded notebook、按需 CRUD／search、OCC／idempotency、runtime namespace、conversation-scoped BM25 回查 | Memory 沒有內建 verified provenance 或 semantic ranking；ConversationSearch 每次重建 corpus，早期 snapshots 被清除就只能部分找回 | PydanticAI V2 stable；**Harness 仍為 0.x，官方允許 minor API 變動** |
| Deep Agents Memory | filesystem-backed Memory、預載或按需 read、StoreBackend、background consolidation、thread history search 範例 | 檔案型態不保證語意完整；同檔 concurrent write 可 last-write-win；不是產品品質保證 | **pre-1.0、API 可在 minor 版改動** |
| Google Memory Bank／AWS AgentCore | managed extraction、consolidation、scope、async generation；Google 有 revisions／rollback，AWS 分 raw events 與 long-term records | 雲端託管行為不能直接等同本機框架，也不保證每個有用細節都被抽取 | 強機制佐證；產品適配與服務成熟度另判斷 |

版本依據：

- [LangChain release policy](https://docs.langchain.com/oss/python/release-policy)：LangGraph 1.0 為 LTS；同頁明示 Deep Agents 尚在 pre-1.0，minor release 可能 breaking。
- [Pydantic AI version policy](https://pydantic.dev/docs/ai/project/version-policy/)：Pydantic AI V2 是 stable。
- [PydanticAI Harness version policy](https://pydantic.dev/docs/ai/harness/)：Harness 的 0.x 是 API stability 聲明；功能可用於 production，但 minor API 仍可能移動。

### 6.4 C1 逐項覆蓋矩陣

| C1 效果 | 成熟能力可覆蓋的部分 | 目前判斷 | 仍未被證明的部分 |
| --- | --- | --- | --- |
| C1-1：長訪談後仍取得目前有效且足夠完整的工作細節 | Durable conversation、可修訂 topics／collection、按需來源搜尋與 bounded Context 都有成熟實例；多家支援 update/delete/consolidation | **部分覆蓋** | 沒有任何官方資料保證自動 Memory 會保存「員工全部重要工作細節」；OpenAI 明示 Memory 只是 recall layer，Google／AWS／Codex 也只選取值得保存的內容。資料不足時不捏造也不是 storage framework 能單獨保證 |
| C1-2：記得重要資訊已回答或仍未取得 | 已回答的事實可放可修訂 Memory；未解內容可以保存於 conversation、thread state、notebook 或 collection | **部分覆蓋** | 通用 Memory 不知道職務分析中「什麼資訊重要、何時算已足夠、哪個問題仍會影響 JD」；成熟框架能存，不能替產品判定 |
| C1-3：關閉／重啟後自然續談 | OpenAI Conversation、LangGraph checkpoint、Pydantic persistence、Claude project／chat continuity 都直接支援 | **直接覆蓋** | 只剩正常的持久化、恢復與故障驗證，不需自創「暫停訪談」語意 |
| C1-4：每份員工工作／JD 隔離，不跨 JD 共用 | Claude project memory、Google scope、AWS namespace、LangGraph namespace、Pydantic conversation／namespace 均有成熟 scope primitive | **直接覆蓋** | 應用仍須用可信 JD identity 綁定 scope；不可讓模型填 ID，也不能使用隱含 global fallback |

### 6.5 對「是否可刪掉自訂工作理解」的目前答案

現在不能回答「全部刪」或「一定保留」，但已能排除兩個錯誤方向：

1. **不需要自寫底層 Memory 基礎設施才算有工作理解。** 持久 conversation、namespace、可修訂 collection／notebook、搜尋、OCC、checkpoint 與 compaction 都已有成熟 primitive；後續不能再以舊 class／table 名稱重建同功能。
2. **也不能只打開某個 Memory 開關就宣稱產品需求已完成。** 大廠消費型產品的抽取政策是私有的；框架只提供容器與操作。尤其「員工工作細節是否完整」及「尚缺哪些會影響 JD 的資訊」仍沒有通用框架保證。

C2 因此留下的不是「要不要保留舊 Work Understanding」，而是兩個中立問題，留給 C3 驗證：

- **完整性缺口**：如何知道成熟 Memory 沒漏掉會改變 JD 的員工工作細節？
- **訪談充分性缺口**：如何知道哪些重要資訊仍未取得，而不是只記住模型碰巧選中的 facts？

這兩題在 C3 被證明之前，不得先設計自訂 schema、Gap、Focus 或第二份 semantic store。

### 6.6 C2 第一輪結論

1. **沒有單一成熟產品或框架完整覆蓋 C1。** 最成熟的公開做法是分層組合，不是單一 Memory 資料庫。
2. **C1-3 與 C1-4 已有成熟 primitive 直接承接。** 之後不應自行發明暫停狀態或跨文件記憶系統。
3. **C1-1 與 C1-2 只有部分覆蓋。** 問題不在缺 storage／search，而在「職務工作資訊的完整性與充分性」是領域語意，通用 Memory 不知道判準。
4. **原始 conversation 回查不是過度設計，但不必自建第二套權威資料。** Claude 現行產品、Pydantic Harness 與 Deep Agents 都把來源聊天搜尋和整理後 Memory 分開；後續應優先評估能直接覆蓋既有 durable conversation 的成熟搜尋能力。
5. **消費型產品是設計證據，不是可直接採用的框架。** Claude topics 與 Codex Memories 證明產品形狀有效，但其私有 extraction／ranking 不能當成 Caliburn 已取得的能力。
6. **成熟度必須與功能完整分開。** LangGraph 1.0 LTS 可作穩定 substrate；LangMem、Deep Agents、PydanticAI Harness 雖功能更接近完整 harness，仍有 pre-1.0／0.x 版本風險。C2 不因此淘汰它們，也不先選它們。
7. **尚未進入框架決策。** 下一步 C3 只研究上述兩個真實效果缺口；若成熟能力或產品方法已能補足，就不建立 Caliburn 特有 Memory 機制。

## 7. C3：真實缺口（第一輪研究）

### 7.1 先把「Memory 完整」拆成五種不同問題

若只問「Memory 能不能保留完整細節」，很容易把不同責任混在一起。本輪依官方能力重新拆成五層：

| 層次 | 白話問題 | 成熟能力現況 | C3 判斷 |
| --- | --- | --- | --- |
| 來源保存完整性 | 員工實際說過的訊息是否還在，關頁或重啟後能否回查？ | OpenAI Conversation、AWS immutable events、LangGraph checkpoint／message state 等已有 durable primitive | **直接覆蓋**；不需第二套 Caliburn source store |
| 語意選取完整性 | 整理為長期 Memory 時，有沒有漏掉日後會改變 JD 的重要細節？ | Claude topics、Codex Memories、Google／AWS strategies、LangMem 都是選擇性抽取，不保存 transcript 全副本 | **未被成熟方案保證** |
| 更正一致性 | 員工更正後，舊理解是否退出一般使用，新理解是否在下一個相依判斷前可用？ | 多家有 update／delete／revision；Google／AWS 背景生成及 Codex background Memory 不能保證立即發布 | primitive 已成熟；**需要明確 correctness deadline，但不構成自建 Memory 理由** |
| 召回完整性 | 需要舊細節時，是否一定找得到並放進當前 Context？ | Claude chat RAG、LangGraph semantic search、Pydantic BM25 等可按需搜尋，但任何 top-k／lexical／semantic retrieval 都沒有零漏召回保證 | **部分覆蓋**；應有來源回查降級路徑，不能把搜尋當絕對保證 |
| 職務內容完整性 | 即使所有已知資料都沒遺失，AI 是否知道還有哪些重要工作根本尚未問到？ | 通用 Memory 只處理已出現的資料；OPM、O*NET、iCAP 與 Anthropic Interviewer 都另外使用職務分析域、方法或訪談 rubric | **真實領域缺口**，不屬於 storage／retrieval 問題 |

這項拆分排除兩個常見誤判：

1. 保存完整 transcript，不代表已訪談到完整工作；
2. 建立很詳細的 semantic Memory，也不代表抽取政策沒有漏掉職務上重要、但通用個人化 Memory 認為不重要的內容。

官方依據：

- [OpenAI — Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)：Conversation 可跨 session／device／job 持久保存 messages、tool calls 與 tool outputs；items 不受一般 response 的 30 日 TTL 限制。
- [OpenAI — Codex Memories](https://learn.chatgpt.com/docs/customization/memories)：Memory 是 helpful recall layer；生成會跳過部分 session，且可能延後或因 quota 跳過背景處理，不能當作唯一必然完整來源。
- [Anthropic — Claude chat search and memory](https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context)：現行產品把可修訂 topics 與 past-chat RAG search 分開，並可由引用回到原始聊天。
- [Anthropic — Context editing](https://platform.claude.com/docs/en/build-with-claude/context-editing)：應用仍保存完整、未修改 history；server-side context editing 只決定 Claude 當下看到什麼。官方也明示 summary compaction 不適合需要精確回想早期細節或維持大量精確變數的工作。
- [Google — Memory Bank troubleshooting](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/agent-engine/memory-bank/troubleshooting)：來源內容沒有通過「值得長期保存」與 topic 判斷時，成功結果可以是零筆 Memory。
- [AWS — AgentCore Memory types](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-types.html)：raw events 與非同步抽取的 long-term key insights 是兩層；long-term Memory 明確只保存選出的 summaries、facts、knowledge 或 preferences。

### 7.2 「訪談充分」也不是單一布林值

本輪把 C1-2 拆成四個可觀察效果：

| 效果 | 成熟 Memory 能做什麼 | 成熟 Memory 不能替產品做什麼 |
| --- | --- | --- |
| 記住已回答資訊 | 保存目前有效 facts／topics，必要時回查來源對話 | 不能只靠「曾出現相似句子」判斷該問題已被充分回答 |
| 記住尚未取得資訊 | 能把未解問題當一般 thread state、Memory entry 或 conversation item 保存 | 不會自行知道哪個未知會實質影響 JD |
| 發現未覆蓋的重要工作面向 | 可保存分析結果並在後續取回 | 通用 Memory 沒有職務分析 coverage ontology 或訪談方法 |
| 判斷目前是否足以形成／更新 JD | 能提供目前資料給模型 | 沒有跨職務通用的完成百分比或「欄位填滿即完成」規則 |

權威資料呈現的共同方向不是固定欄位完成率，而是**先有分析範圍與方法，再依實際回答自適應深入**：

- [OPM — Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/) 把 job analysis 定義為系統性理解 tasks、competencies 與兩者關聯；資料也要支援 training、performance appraisal 等後續用途。
- [OPM — Job Analysis FAQ](https://www.opm.gov/frequently-asked-questions/assessment-policy-faq/job-analysis/) 明示 critical task／competency 的判定取決於採用的 job-analysis method；是否收集 importance／criticality rating 也依方法與目的決定，沒有單一通用百分比。
- [O*NET — Data Collection Overview](https://www.onetcenter.org/dataCollection.html) 使用 incumbents、occupational experts、analyst ratings、AI／SME、job postings、政府資料等多種來源，證明職務資訊的完整性要靠分析方法與資料域交叉檢查，而不是靠 Memory 容量推定。這項引用不表示 Caliburn 要增加跨員工或跨 JD 資料來源。
- [O*NET — Content Model](https://www.onetcenter.org/content.html) 把工作資訊分成 tasks、work activities、work context、knowledge、skills、experience 等多個面向；它可作檢查範圍的證據，但不代表 Caliburn 必須複製 O*NET schema。
- [iCAP — 職能分析方法簡介](https://icap.wda.gov.tw/ap/knowledge_method.php) 列出訪談、調查、集會與其他類共多種方法；一般訪談用於收集職務、責任、任務與關鍵能力的深入資料，亦沒有宣稱 Memory 本身可判定訪談完成。
- [Anthropic — Interviewer](https://www.anthropic.com/research/anthropic-interviewer) 採 planning／interviewing／analysis 三階段：先建立涵蓋整體研究問題的 rubric，再在訪談中依回答動態追問與容納岔題；這證明「固定方向＋自適應深入」是現行大廠做法，但它是訪談方法，不是 Memory 功能。

因此，Caliburn 未來若要顯示「訪談進度」或判斷「目前足夠」，不能偽造一個精確百分比，也不能以 OPKS 欄位是否全滿代替。第一輪能成立的中立效果是：

> AI 應能對照一套經研究的職務分析範圍，辨認哪些會實質改變 JD 的工作面向已有足夠具體資訊、哪些仍模糊、矛盾或未觸及；這個判斷可隨後續訪談重新打開，不是一次性完成狀態。

這句只定義成果，不授權建立 `Gap`、`Progress`、`Focus`、固定 stage 或任何特定 schema。

### 7.3 各家特殊能力能補到哪裡

共同基線以外，各家差異能力可降低風險，但沒有一項能單獨消除兩個真實缺口：

| 特殊能力 | 能改善什麼 | 仍解決不了什麼 | 目前地位 |
| --- | --- | --- | --- |
| Claude topics＋past-chat RAG citation | 語意理解與原始來源分層；需要時回到原話 | 私有 extraction／ranking 未公開；不會知道職務上沒問到什麼 | 強產品設計證據，不是可直接嵌入服務 |
| Codex background extraction＋consolidation＋supporting evidence | 證明摘要、durable entries、recent inputs、來源佐證可以分層 | best-effort／背景處理，不適合單獨承擔下一個必須使用更正的 JD 判斷 | 強產品設計證據，不是 completeness 保證 |
| Google Memory Bank topics＋revisions／rollback | topic 限定抽取範圍；可檢查 create／update／delete 歷史並回退錯誤修訂 | 沒被 topic 定義的工作細節仍可能不保存；公開 API 與文件仍快速演進，成熟度須與功能分開評估 | 可選治理與修訂能力 |
| AWS raw events＋strategies | 原始事件與衍生理解分層；策略可限定抽取內容 | 非同步 long-term generation；策略仍要先知道應抽哪些職務資訊 | 可選託管抽取能力 |
| LangGraph collection＋semantic search | 多筆 Memory 通常比單一大 profile 有較高 recall，並可使用成熟 namespace／search | collection 的更新、搜尋與 Context 組裝更難；框架不提供職務完整性判準 | 成熟 substrate 能力，不是產品答案 |
| LangMem reconcile | 可依 instructions／schema 對既有 Memory insert／update／delete，處理自然更正 | 0.0.x；LLM 仍可能漏抽或誤改，也不知道訪談何時充分 | 功能接近需求，但成熟度與效果需後續比較 |
| PydanticAI ConversationSearch | 可從已持久 snapshots 做 conversation-scoped BM25 回查 | lexical search、每次重建 corpus、舊 snapshots 若已清除即找不回；Harness 仍為 0.x | 可選 source-recall 實作，不是零漏召回保證 |
| temporal／knowledge graph | 可表達複雜時間演變與關係 | 引入抽取、關係、時間與矛盾解析成本；目前沒有證據顯示是單一員工 JD 的必要條件 | **目前排除，不因功能多而採用** |

框架官方依據：

- [LangGraph／LangChain — Memory overview](https://docs.langchain.com/oss/python/concepts/memory)：單一 profile 變大後整份更新容易出錯；collection 通常提高 recall，但更難更新、搜尋與組裝 Context。
- [LangMem — Memory API](https://langchain-ai.github.io/langmem/reference/memory/)：manager 可分析新 conversation 與既有 memories，產生 insert／update／delete；這是 reconcile primitive，不是 completeness validator。
- [LangMem — Extract semantic memories](https://langchain-ai.github.io/langmem/guides/extract_semantic_memories/)：一次呼叫處理大量新資訊可能讓模型多工過重，也可改用多步 agent；兩者都沒有職務領域的完成判準。
- [Google — Memory Bank revisions API](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/reference/rpc/google.cloud.aiplatform.v1)：每次 create／update／delete 有 revision，`previous_revision` 可供 rollback。
- [AWS — Memory strategies](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-strategies.html)：strategy 決定從 raw conversation 抽取何種 long-term information；沒有 strategy 就不抽取 long-term Memory。

### 7.4 第一輪確認的真實缺口

目前只確認兩個必要、且沒有成熟通用 Memory 自動完成的產品效果缺口：

#### G1：職務細節重要性判斷

AI 必須知道哪些員工工作資訊即使不常出現，仍可能實質改變 JD，因此不能被通用「值得記住」分類漏掉。例子包括低頻高影響事件、責任邊界、決策權、例外流程、工作情境、成果標準與任務所需能力。

這個缺口不表示要建立一份名為 Work Understanding 的資料；它只表示**持久 Memory 的 admission／更新政策需要職務分析方法提供語意**。最後可能由 Skill／instruction、managed topic、custom strategy 或其他成熟擴充點承接，留到 C4／C5 比較。

#### G2：訪談覆蓋與充分性判斷

AI 必須知道哪些重要工作面向仍未取得足夠具體資料，避免只記住已知 facts 就誤以為訪談完整。這不是記憶容量問題，而是職務分析方法對 coverage、criticality、矛盾與未知的判斷。

這個缺口也不表示必須建立 Gap table、固定進度百分比或線性 stage。成熟 agent state／Memory 已能保存判斷結果；真正需要補的是**怎麼判斷**，不是再造一個保存容器。

### 7.5 已排除為「自訂缺口」的項目

下列能力已有成熟 primitive，後續若採自訂方式重做，必須提出額外產品證據：

1. durable conversation／event persistence；
2. 關頁、重啟與同一長訪談恢復；
3. 一份 JD 一個可信 scope／namespace／thread 的隔離；
4. 多筆 semantic Memory 的 CRUD、修訂與搜尋；
5. compaction／bounded context；
6. 原始 conversation 與衍生 Memory 分層；
7. hot-path 更正與 background consolidation 的執行入口；
8. optimistic concurrency、revision 或等價的防覆蓋機制。

### 7.6 C3 第一輪結論

1. **兩個真實缺口都不是「缺 Memory 框架」。** 缺的是職務分析領域對「什麼不能漏」及「什麼尚未充分」的判準。
2. **成熟 Memory 共同基線仍是必要底座。** Durable source、可修訂 semantic Memory、按需來源搜尋、有界 Context、scope 與 revision 缺一都會降低長訪談可靠性。
3. **目前沒有證據支持完整重建舊 Work Understanding／Gap／Focus。** 這些名稱可能完全消失；若 C4 需要補差額，也應優先用成熟 Memory 的 topic／strategy／collection／agent state 擴充點。
4. **不能承諾絕對完整。** 單一員工可能遺漏、概括或前後矛盾；產品可承諾的是系統性覆蓋、看得見的重要未知、可更正與可重新打開，而不是宣稱 AI 已知道員工未說出口的一切。
5. **下一步 C4 只回答最薄差額。** 先研究能否把 G1／G2 主要放入已驗證的職務分析 Skill／訪談 rubric，並讓成熟 Memory／runtime 保存結果；在證明不足前，不新增第二份 semantic store 或專用 workflow 系統。
6. **尚未選框架，也未授權實作。** Google／AWS 的 managed Memory、LangGraph／LangMem、PydanticAI 等留到 C5，以最終 JD 效果、錯誤率、功能、成熟度、成本與複雜度比較。

## 8. C4：Caliburn 最薄差額（第一輪歷史研究；目前不採為結論）

### 8.1 先講結論：缺的是職務分析方法，不是另一套 Memory 產品

C3 的 G1／G2 可以由「成熟 Memory／agent runtime＋Caliburn 的職務分析方法」承接，不需要完整重建舊的 Work Understanding、Gap、Focus 或 Progress 機制。

目前證據支持的最薄組合是：

1. **成熟通用底座**繼續負責 durable conversation、可修訂 semantic Memory、source search、scope、revision、bounded Context 與恢復；
2. **版本化、按需載入的職務分析 Skill／rubric**只提供領域方法：哪些工作資訊值得保存、哪些工作面向尚未問清楚、下一個最有價值的追問是什麼，以及目前資訊是否足以提出某一項 JD 變更；
3. **Memory admission／更新使用成熟擴充點**：依最後選定框架映射成 custom topic、memory strategy、manager instructions／schema 或模型可用的 Memory CRUD tool，不另外建立 Caliburn 專用 Memory 引擎；
4. **訪談 coverage 預設即時計算**；只有「若不保留就會在話題切換、關頁或重啟後遺失，且會影響 JD」的未解問題，才使用同一套成熟 Memory／runtime 持久化。回答後更新或移除，不建立第二份 Gap ledger；
5. **當前注意力與員工可見進度是 projection**：由目前 conversation、semantic Memory、未解問題與 JD 狀態組成，不是新的可寫權威資料。

這不是框架決策，也沒有授權實作。它先把 Caliburn 必須保留的自訂內容縮到「職務分析方法」，其餘優先交給成熟元件。

### 8.2 G1：哪些工作細節不能漏，成熟機制已能承接「怎麼保存」

G1 其實有兩層：

- **機制層**：抽取、更新、刪除、整併、版本、搜尋與 scope；成熟 Memory 已有；
- **領域判準層**：什麼工作細節對形成 JD 有價值；這只能由職務分析方法定義。

目前官方產品提供的擴充點已足以把兩層接起來：

| 成熟能力 | 官方可驗證行為 | 對 G1 的含意 |
|---|---|---|
| [OpenAI Agent Skills](https://developers.openai.com/api/docs/guides/tools-skills) | Skill 是可版本化的檔案 bundle，可封裝流程與慣例，並掛載到 hosted／local shell 環境 | 職務分析方法可以是可替換、可版本化的能力內容，不必散落在巨大 system prompt 或自寫 loader |
| [Anthropic Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) | 只先提供 skill metadata；相關時才讀完整 `SKILL.md`，更細資料再按需讀取；可同時封裝 deterministic code | 已驗證的職務分析方法可以 progressive disclosure，不必每輪把 Task／Duty／OPKS 全部塞進 Context |
| [Google Memory Bank custom topics](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/setup#configuring_memory_topics) | custom topic 的 label／instructions 直接進 extraction prompt；官方建議用正、負 few-shot 示範應保存與不應保存的內容 | 可以用職務分析語意定義「有意義的工作細節」，連「不應產生 Memory」也能示範，不需自寫 extraction pipeline |
| [AWS AgentCore Memory strategies](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-custom-strategy.html) | built-in override 可加入 domain-specific extraction 與 granularity 規則，仍沿用 managed extraction／consolidation；需要改 schema 才用 self-managed strategy | 領域抽取不等於從零自建；先用 managed pipeline＋窄規則，只有證明 schema 不足才升級 |
| [LangMem semantic memory manager](https://langchain-ai.github.io/langmem/guides/extract_semantic_memories/) | `instructions`／可選 schema 控制抽取，manager 處理 insert／update／delete，並可直接接 LangGraph Store | 若採 OSS，本專案只需提供方法與少量形狀；CRUD／reconciliation／storage integration 不必重寫 |

因此，G1 最薄解法不是設計完整 `WorkUnderstanding` schema，而是把既有、研究過的職務分析判準整理成 **Skill 的單一方法來源**，再由框架 adapter 映射到其 topic／strategy／instructions。模型不應自行回報「用了哪個 Skill」或填 framework metadata；實際載入與執行紀錄由 runtime 產生。

這個 Skill 至少要能辨識下列高價值資訊，但本節不先固定最終欄位：穩定責任、例行與週期工作、低頻高影響工作、輸入／輸出與接收者、判斷與責任邊界、協作與交接、工作條件、頻率與重要性、例外事件、工具只是方法還是獨立責任，以及否定／更正／不確定。這些是既有職務分析研究的**方法內容**，不是新的 persistence model。

### 8.3 G2：訪談充分性由 rubric 判斷，容器交給成熟 runtime

權威資料沒有提供一個跨職務通用的「完成百分比」，但已提供成熟方法形狀：

- [OPM Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/) 要求理解 Task、competency 與兩者連結，並指出資料可用於工作要求、訓練與績效；OPM 的現行 FAQ 也明示 criticality 取決於所採 job-analysis method，而不是固定全域門檻；
- [O\*NET Content Model](https://www.onetcenter.org/content.html) 把工作內容分成 Task、work activities、work context、knowledge、skills、experience 等多個面向，證明 coverage 必須跨工作與任職需求，但不表示每份 JD 都要機械填滿所有 O\*NET 欄位；
- [Anthropic Interviewer](https://www.anthropic.com/research/anthropic-interviewer) 先用 rubric 維持整體研究問題，再依個別回答自適應追問與容納岔題；analysis 階段仍回看初始 plan。這支持「固定方法範圍＋動態深入」，不是線性 wizard 或固定題庫；
- [LangGraph 官方設計指南](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph) 建議需要跨 step 的資料才放 state，可由其他資料推導的結果按需計算；state 保存 raw data，prompt 在 node 內組裝。這支持不把每一輪 coverage 判斷都永久複製成另一份權威資料。

G2 因此拆成兩種結果：

1. **本輪暫時判斷**：目前回答補了什麼、下一題最值得問什麼、是否已有足夠支持提出某一項 JD 變更。這是 runtime decision，預設不另存成長期 Memory；
2. **需跨回合存續的未解問題**：例如關鍵責任邊界互相衝突、員工暫未回答一項會改變 JD 的問題，或話題切換後仍不可遺漏的高影響未知。這類才透過同一 Memory／runtime 的一般 update／delete 能力保留，回答後即更新或退出 active recall。

這裡的「未解問題」只是效果描述，不是新資料表或固定 schema 名稱。它也不必綁 Task／Duty／OPKS ID，因為真正尚未理解的內容可能還不能合法歸類。若最後採用的成熟 Memory 能以自然語言 topic／entry 保存，就直接使用；若 agent runtime 的 typed state 更適合，就用同一 runtime state。C5 才比較哪個 primitive 的效果與成本最好。

### 8.4 三個方案比較

| 方案 | 作法 | 效果 | 成本／複雜度 | 第一輪判斷 |
|---|---|---|---|---|
| A. 只有 managed Memory topic／strategy | 只告訴 Memory 哪些已出現資訊值得保存 | G1 可大幅覆蓋；無法自行知道員工從未提到的重要工作面向，G2 不足 | 最低 | 不足以單獨產出可靠 JD |
| B. Skill／rubric 每輪全部重算 | Memory 只存已知工作資訊；每輪從頭比較完整 coverage | 不新增持久狀態，但長訪談容易重複分析，未解問題可能因 Context 選取而消失 | 模型成本與延遲較高；程式最少 | 可當 fallback，不宜是唯一連續性機制 |
| C. Skill／rubric＋同一成熟 Memory／runtime 的選擇性持久化 | 已知工作由 Memory 管；coverage 每輪按需算；只有高影響、需跨回合的未知保留在同一 substrate | 同時覆蓋 G1、G2、話題岔出與重啟；不需第二套 truth | 低至中；只增加領域 Skill、few-shot／instructions 與很薄的映射 | **推薦進 C5 比較** |

不列為候選的方案是「完整復活舊 Work Understanding＋Gap ledger＋Focus entity＋Progress state machine」。目前沒有證據顯示它比 C 更能提升 JD 效果，卻會重做成熟 Memory／runtime 已提供的 CRUD、revision、search、state 與 projection。

### 8.5 成熟元件與 Caliburn 自訂內容的最薄邊界

| 所需效果 | 優先交給成熟元件 | Caliburn 只保留什麼 |
|---|---|---|
| 長訪談來源、恢復、隔離 | conversation／event store、scope／thread／namespace | 一份員工工作對應一份 JD 的產品 scope 規則 |
| 可修訂工作知識 | managed topic／strategy 或 LangMem collection＋CRUD／revision | 哪些職務資訊重要的 Skill 內容與 examples |
| 更正與衝突 | Memory update／delete／revision＋source search | 員工說法不明或衝突時應追問、不得擅自選邊的領域規則 |
| 職務 coverage | Agent Skill／rubric＋模型推理 | 經研究驗證的工作週期、責任、Task 邊界、OPKS 等分析方法 |
| 未解高影響問題 | 同一 semantic Memory 或 agent state 的普通可修訂 entry | 哪些未知值得跨回合保留的判準 |
| 目前注意力 | runtime 每輪依 current input、Memory 與 rubric 選擇 | 不建立永久 Focus entity；只保留選擇方法 |
| 員工可見進度 | 對已知內容、未解高影響問題與文件狀態做 projection | 白話呈現 coverage／深度／待確認，不造假百分比 |

### 8.6 可以刪除或不再預設保留的舊設計

C4 第一輪研究沒有找到必須保留以下機制的證據：

- 第二份名為 Work Understanding／Work Model 的自訂 semantic store；
- 獨立 Gap table、gap ledger 或每欄完成旗標；
- 永久 Focus entity 或線性 stage machine；
- 另一份 Progress authority 或固定完成百分比；
- 讓模型填 Skill ID、Memory ID、版本、時間與 runtime metadata；
- 每輪固定載入 Task／Duty／O／P／K／S 全部方法；
- 為 coverage 另建 planner／todo 系統。Pydantic Harness Planning 等成熟元件適合長任務執行步驟，但訪談未知不是必須依序完成的 task list；沒有證據顯示導入 planner 會比同一 Memory／runtime 的選擇性 entry 更準。

這些是**研究上的候選刪除**，不是修改現行 code／ADR 的授權。若 C5 的框架比較或實測發現某項效果無法由成熟 primitive 達成，再提出可驗證的最薄補件，不能靜默把整套舊設計帶回來。

### 8.7 C4 第一輪結論與下一步

1. **G1 幾乎可由成熟 Memory 擴充點直接承接。** Caliburn 只需提供職務分析 admission 方法與 examples，不需自寫抽取／整併引擎。
2. **G2 不能只靠 Memory 自動抽取，但可由版本化 Skill／rubric 完成判斷。** 保存則使用既有 Memory／runtime；不需要專用 Gap 系統。
3. **推薦最薄方案 C。** Coverage 預設按需計算；只有會影響 JD 且需跨回合存續的未知才持久化；回答後更新或移除。
4. **Skill 是方法 SSOT，不是另一個 agent。** 可用一個核心 Skill 搭配按需子資源，或拆成 Task／Duty／OPKS Skills；數量與打包方式留到 C5，以 Context 成本、觸發正確率與維護性比較。
5. **沒有新增模型 call 的硬要求。** 這些判斷可在主顧問既有 run 中完成；managed background extraction 是否另耗模型 call，屬 C5 的成本比較，不能現在假定免費。
6. **下一步 C5 才選框架／primitive。** 應以 JD 效果與錯誤率為第一順位，再比較成熟度、長訪談成本、延遲、本機適配、可替換性與自寫程式量；不能只因某框架功能表最多就採用。

## 9. M1～M11 對共同基線與差異能力的第二輪 mapping（目前裁決）

### 9.1 本輪方法與判斷標籤

本輪不再從「要不要保留工作理解」或「哪個舊元件可刪」出發，而只做下列映射：

```text
高品質 JD 所需的 M1～M11
        ↓
跨 OpenAI／Anthropic／Google／AWS／成熟框架的共同 Memory 能力
        ↓
共同能力已完整覆蓋？
        ├─ 是：列為共同基線直接承接
        ├─ 只有機制：列出仍需由產品定義的語意，但不預設自建引擎
        └─ 否：只比較已出貨或官方公開的成熟差異能力
```

覆蓋判斷固定使用三種標籤：

- **共同基線直接承接**：跨家公開能力已提供該效果；產品只需作正常整合與驗證。
- **共同 primitive＋產品語意**：成熟系統已提供儲存、CRUD、搜尋、版本或擴充介面，但不可能替職務產品定義「哪些內容不能漏、何者仍未釐清」。這表示要設定 domain policy／instructions／topic／strategy，不表示要自建 Memory 引擎。
- **成熟差異能力必選**：不是所有家都提供，但已有多個官方成熟 primitive；因 Caliburn 的成果要求需要，日後選型必須挑一個能承接者，不能用 generic top-k 冒充。

另有一條證據紀律：供應商提供 `schema`、file、topic 或 strategy 擴充點，只能證明產品可以定義語意，不能證明「打開 Memory」後已自動知道完整員工工作。

### 9.2 跨家共同基線：本輪可以直接採信什麼

通用研究 §6、§9 與 §13 已核實下列共同方向；本輪只把它們正規化成 mapping 所需能力：

| 共同能力 | 已公開的跨家形狀 | 本輪可宣稱 | 本輪不可宣稱 |
| --- | --- | --- | --- |
| 分層持久來源 | Durable conversation／events 與衍生 Semantic Memory 分開 | 原始訪談可長期保存、回查，不必每輪全塞入 Context | 衍生 Memory 一定保留了所有原始細節 |
| 選擇性且可修訂的 Semantic Memory | topics、facts、records、collections、text files；可 create／update／delete／skip | 可維持目前有效理解、修訂過時內容；無變更是合法結果 | 通用抽取政策自動知道 JD 需要的所有資訊 |
| 有界 Context 與按需深入 | 少量自動召回、exact／filter／semantic search、read 詳細內容、必要時回查來源 | 日常 run 不必注入全部歷史；需要時能往下找細節 | top-k 或 compaction 可證明完整盤點 |
| Trusted scope | conversation、project、workspace、namespace、store 等由 runtime 綁定 | 可隔離單一員工／JD；模型不應填 principal、scope 或安全 ID | 同名 namespace 本身等於完整 AuthN／AuthZ |
| 修訂與治理 | current head、revision／version、delete、rollback／OCC 或等價能力 | 可區分目前有效內容與歷史；更新衝突可被偵測 | 各家都保證跨多筆 Memory 的 ACID transaction |
| 領域擴充介面 | OpenAI `extra_prompt`／受控文件、Anthropic app prompt／files、Google topics＋few-shot、AWS strategy override、LangMem instructions／schema | 可以用成熟 pipeline 承接職務領域保存語意 | 任何一家的預設個人化 Prompt 就足以形成完整職務 Memory |
| 系統欄位由 runtime 管 | record ID、scope、revision、timestamp、版本、ACL 由平台／應用產生 | 模型只需處理語意內容與有限 mutation intent | 讓模型填更多 metadata 會提高正確性 |

這些共同點代表高可信工程基線，但不代表各家使用同一底層資料庫、Prompt 或索引。

### 9.3 共同基線以外，已證明存在的成熟差異能力

| 差異能力 | 官方實例 | 能解的問題 | 限制 |
| --- | --- | --- | --- |
| Scope 內完整列舉／分頁 | Google Memory Bank 取全部；AWS `ListMemoryRecords`；Anthropic Memory Store list；LangGraph Store namespace search/list | M9 的「所有目前有效 Memory 都進入盤點」 | 只能保證列出**已成功保存**的 Memory，不能補回 admission 時已漏掉的工作內容 |
| Immutable revision／OCC／rollback | Anthropic immutable versions＋content hash；Google revisions／rollback | 防止靜默覆蓋、回查修訂、恢復錯誤 head | 不是每個開源框架都內建同樣治理；也不自動判斷新舊說法誰正確 |
| 可保留複雜語意的表徵 | Anthropic path-addressed text documents；LangMem custom schema／triples；LangChain profile／collection | M5／M6 可明確表達未解、關係與脈絡 | 沒有跨家唯一最佳 schema；collection 可能丟失跨項關係，單一大 profile 又較難安全更新 |
| 事件／案例與抽象知識分層 | AWS episodic memory＋reflection；OpenAI／Anthropic 的來源細節＋整理後 Memory | M7 同時保留案例與較穩定理解 | 從案例歸納工作仍是 LLM＋職務分析 Skill 的責任，不是 Memory 自動事實 |
| 背景抽取與 hot-path 修正並存 | OpenAI Codex、Google／AWS background；Anthropic Memory Tool、LangMem hot path | 在成本、延遲與「下一次依賴前必須生效」間取捨 | 寫入工作被接受不等於已發布；具體 correctness deadline 尚未選 |

上述能力是後續方案比較的候選，不表示本輪已選 Google、AWS、Anthropic、LangMem、file、triple 或 graph。

### 9.4 M1～M11 覆蓋矩陣

| 必要能力 | 共同基線已提供 | 目前覆蓋判斷 | 還需要什麼；責任邊界 |
| --- | --- | --- | --- |
| **M1 長期連續性** | Durable conversation、Semantic Memory、bounded Context、恢復 | **共同 primitive＋產品語意** | 關頁／重啟與跨回合延續已成熟；但哪些「重要背景／高影響未解」必須進 durable Memory，仍需職務領域保存政策，不能靠一般個人化抽取猜 |
| **M2 細節保真** | 原始來源不丟、可保存多筆語意完整內容、詳細內容按需 read | **共同 primitive＋產品語意** | 通用抽取通常是選擇與壓縮，不保證保留頻率、例外、責任邊界等 JD 關鍵細節；需要 domain retention instructions／examples。原始來源是查錯 fallback，不應每輪全量注入 |
| **M3 廣度與完整可得性** | 多筆 collection／files／records、可修訂 Memory | **共同 primitive＋產品語意；並依賴 M9** | 必須定義「員工已提供的哪些工作範圍都應進 active Memory」。完整列舉只能盤點已保存項目，無法彌補 admission 已漏掉的內容；員工從未說過的工作仍只能靠訪談發現 |
| **M4 可修訂的目前理解** | create／update／delete／skip、current head、revision／version | **共同基線直接承接** | 成熟生命週期已足夠承接修訂；辨識員工是在更正、補充或描述不同時點仍由模型依 Context 判斷，不由 storage 猜。正常召回只用 current head，舊版供回查 |
| **M5 不確定性與衝突不被抹平** | 可修訂內容與 flexible representation | **共同 primitive＋產品語意；預設行為不足** | 不少 managed consolidation 會選一邊、合併或依語氣信心取捨。Caliburn 需要明示「未解／衝突可以合法存在，不得自動升格成事實」；可用現有 topic／file／schema／instructions 表達，尚未證明需要自建引擎 |
| **M6 語意關係不丟失** | 自包含 records、text documents、custom schema，來源仍可回查 | **共同 primitive＋成熟差異能力候選** | Generic fact collection 不保證保留「誰產生什麼成果、K／S 支援哪段工作」等關係；後續必須比較統一文件、linked records、custom schema 等成熟表徵。沒有證據要求先上 knowledge graph |
| **M7 案例細節與穩定工作雙重可用** | 原始 conversation／events 與整理後 Semantic Memory 分層 | **共同 primitive＋產品語意** | 兩層已能同時保留案例與目前理解；案例何時只是案例、何時支持修訂穩定工作，仍由 LLM＋Skill 判斷。AWS episodic/reflection 是成熟可選補強，不是第一版必選 |
| **M8 相關且有界的日常召回** | Scope-first、exact/filter、bounded semantic／keyword recall、模型按需 search/read | **共同基線直接承接** | 檢索引擎與 ranking 仍待方案比較；但「少量自動召回＋需要時擴展」已是共同方向。Retrieval score 不能冒充真實性 |
| **M9 可驗證的完整盤點** | 共同 baseline 的 top-k 不夠；多家另有 scope list／pagination | **成熟差異能力必選** | 後續選用的 substrate 必須能在可信 scope 內列出所有 active Memory、分頁至結束，並讓 runtime 證明每頁已處理。只有 vector top-k 的方案不合格；這不要求一次塞進單一 Prompt |
| **M10 原始來源可回查** | Durable conversation／events 與衍生 Memory 分層；可按需 retrieve／search | **共同基線直接承接** | M10 目前只要求可回查，不要求模型為每筆 Memory 填逐字 quote。若日後需要一鍵跳到精確來源，再比較 supporting-evidence link；目前不把它誤設為所有 Memory 的必填 schema |
| **M11 單一員工／JD 可信隔離** | Trusted runtime scope／namespace／conversation／store | **共同基線直接承接** | 每份 JD 的可信識別由 application 注入；不得讓模型生成、切換或猜測 scope，也不得有隱含 global fallback。產品不需要跨 JD 共用 Memory |

### 9.5 第二輪當時尚未收斂的五個能力問題（後續研究已完成）

下列是第二輪 mapping 完成時的研究佇列，不是目前仍未完成的清單。Retention／admission 與 M5 已於 §9.9～§9.21 處理；M6、M9、M7、完整候選與最低驗證已於 §9.22～§9.30 處理。當時尚未收斂的不是「要不要有 Memory」，也不是舊元件去留，而是五個能力級問題：

1. **Retention／admission 語意（M1～M3）**：如何告訴成熟 Memory pipeline 哪些職務細節即使低頻也不能漏；這要比較 topic、strategy、instructions、few-shot 與 Skill 的責任分界。
2. **未解與衝突語意（M5）**：如何讓「不知道／互相衝突／待確認」保持合法 current knowledge，而不是被 consolidation 選邊或抹平。
3. **關係保真表徵（M6）**：哪種成熟表徵能在不過度設計的前提下保留工作脈絡；尚未選 file、profile、collection、linked record、triple 或 graph。
4. **完整盤點 primitive（M9）**：方案必須支援 scope 內全量列舉與分頁；這是選型硬條件，不是由 Prompt 補救的功能。
5. **案例與穩定工作之間的界線（M7）**：Memory 只確保兩者可取得；抽象、合併、去重與是否改 JD，仍屬職務分析 Skill／LLM。

其中 1、2、3、5 都可由成熟產品提供的 domain extension seam 承接；目前**沒有證據要求新建 Caliburn 專用 Memory storage／CRUD／search engine**。但這也不代表 generic Memory 預設值已足夠：若沒有職務領域 retention 與 conflict instructions，M2、M3、M5 很可能失敗。

### 9.6 三個容易混淆、必須固定的結論

#### 完整保存不等於完整盤點

- M3 解決「應保存的工作範圍有沒有真的進 Memory」；
- M9 解決「已進 Memory 的全部 active 項目有沒有全被盤點」；
- M10 解決「需要查錯時能否回到原始來源」。

三者互補，不能拿任一個冒充另外兩個。即使 M9 完美列舉，也無法找回 M3 在抽取時已漏掉的內容；即使 M10 保存完整 transcript，也不表示 LLM 已分析過每段內容。

#### 可修訂不等於可自動解決衝突

CRUD、current head、revision 與 rollback 只提供生命週期。新舊說法是更正、不同案例、不同時點或尚未釐清，仍需語意判斷。AWS 最新公開 semantic-memory Prompt 甚至會依語句信心選擇 update 或 skip，證明「成熟 managed default」可能主動消解衝突；這與 M5 的產品要求不同，必須顯式覆寫，而不是盲用預設。

#### Memory 完整不等於 JD 自動正確

M1～M11 只保證 LLM 能長期取得足夠、目前有效、可盤點的員工工作資訊。Task／Duty 邊界、案例抽象、去重、完成標準、K／S 與 JD 編輯仍由職務分析 Skill＋LLM 完成；runtime 只保證輸入與工具結果，不替模型做專業判斷。

### 9.7 第二輪階段性結論（後續進度見 §9.9～§9.30）

1. **跨家共同基線直接承接 M4、M8、M10、M11 的核心效果。** 不需要為修訂生命週期、有界召回、原始來源回查與單一 JD 隔離發明新機制。
2. **M1、M2、M3、M5、M6、M7 不是 storage 缺口。** 成熟系統有 persistence、CRUD、source、search 與 domain extension seam；缺的是職務領域保存、衝突與關係語意，後續應比較如何配置成熟 pipeline，而不是先畫自訂資料表。
3. **M9 是唯一明確需要把「差異能力」升格成選型硬門檻的項目。** 後續候選若只能 top-k 召回、不能在可信 scope 中完整列舉 active Memory，即使一般聊天效果很好，也不足以支援 JD 全域涵蓋／去重盤點。
4. **目前不能宣稱某個單一框架完整覆蓋 M1～M11。** Google、AWS、Anthropic、LangGraph／LangMem 各覆蓋不同部分；OpenAI／Claude 消費型產品可作強設計證據，但私有抽取與 ranking 不能當成可直接採用的 API。
5. **第二輪當時不選框架、不選 schema、不決定 Prompt／Tool，也不授權實作。** 其後已按 §9.5 五題完成差異能力與候選比較；目前仍只有 §9.27 的暫定推薦，尚未成為 ADR 或施工授權。

### 9.8 本輪主要官方來源

- [OpenAI — Responses：Conversation items 會自動加入持久 Conversation](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)
- [OpenAI — Codex Memories：summary、durable entries、recent inputs 與 supporting evidence 分層](https://learn.chatgpt.com/docs/customization/memories)
- [Anthropic — Managed Agents Memory：path-addressed text documents、完整 list、immutable versions 與 recovery](https://platform.claude.com/docs/en/managed-agents/memory)
- [Anthropic — Memory Tool：模型提出有限 file CRUD、應用執行 storage／scope](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- [Anthropic — Context engineering：小型高訊號 Context、JIT retrieval 與按需讀取](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Google — Generate memories：topics、extraction、consolidation、create／update／delete 與合法空結果](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories)
- [Google — Fetch memories：exact scope 下取全部、filter 或 similarity](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/fetch-memories)
- [Google — Memory revisions：current state、immutable revisions 與 rollback](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/revisions)
- [AWS — AgentCore Memory terminology：raw events、strategies、records、actor／session／namespace](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-terminology.html)
- [AWS — ListMemoryRecords：namespace／namespacePath 下完整列舉與分頁](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_ListMemoryRecords.html)
- [AWS — Semantic Memory Prompt：保留細節、處理模糊與依信心消解衝突的官方預設](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-system-prompt.html)
- [LangChain／LangGraph — Memory overview：thread state、Store、profile／collection 與完整 Context 取捨](https://docs.langchain.com/oss/python/concepts/memory)
- [LangGraph — Persistence：namespace Store、filter／semantic search 與 checkpointer](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangMem — Semantic memories：custom schema／instructions 與 insert／update／delete manager](https://langchain-ai.github.io/langmem/guides/extract_semantic_memories/)

### 9.9 Retention／admission 深挖：真正要回答的不是「每輪要不要存」

本節只收斂 §9.5 第 1 題，仍不選框架、資料形狀、Prompt 文字或執行時機。跨家官方機制顯示，`admission` 不能被壓成一個模糊的「重要就記住」判斷，至少要分成三道不同責任：

1. **來源資格（source eligibility）**：這段 conversation／event 是否允許成為未來 Memory 的輸入。Codex 可逐 chat 控制是否使用 Memory、是否貢獻未來 Memory，且會略過 active／short-lived sessions；Claude 有 Pause、Incognito 與 project 隔離。這一層回答「能不能學這段來源」，不是「哪個工作細節重要」。
2. **語意 admission（semantic admission）**：來源中哪些內容對未來任務有持續價值、符合產品目的，應形成或修訂 durable Memory。Google 用 topics＋instructions＋few-shot；AWS 用 strategy／override；Anthropic Memory Tool 與 LangMem 都把 instructions 留給應用。這一層回答「值得把哪個語意帶到未來」。
3. **持久化政策（persistence policy）**：即使內容有用，是否因 secrets、敏感資料、保留政策或產品控制而不得保存。Codex 會 redaction；Claude 消費型產品對敏感 topics 另設 opt-in 與永不保存類別；Anthropic API Memory Tool 明示更強保證要由應用在 write 前 validation。

通過三道 gate 後，才進入 **validation＋consolidation**：決定 add／update／delete／skip、去重與修訂 current head。Consolidation 不是 admission；它不能找回 extraction 已漏掉的低頻工作細節，也不能替 owner 決定哪些資料允許持久化。

### 9.10 各家公開機制逐項比較

| 方案 | 來源資格 | 語意 admission 如何定義 | 無內容可存時 | 成熟 pipeline 負責什麼 | 官方未保證什麼 |
| --- | --- | --- | --- | --- | --- |
| **OpenAI Codex Memories** | chat 可分別決定是否使用／貢獻 Memory；略過 active、short-lived，亦可設定排除曾用 external context 的 chat | 私有 extraction 從 eligible prior chats 選 `useful context`；公開設定可分別指定 extraction／consolidation model | 背景 pass 可因 idle／quota 條件略過 | 本機 generated state、summary／durable entry／recent input／supporting evidence、背景 extraction／consolidation、secret redaction | `useful` 的內部 Prompt、職務領域完整率與可供第三方設定的 topic API；OpenAI 反而要求必須遵守的規則放 `AGENTS.md`／正式文件，不把 Memory 當唯一權威 |
| **Claude 消費型 Memory** | Pause／Incognito／project space；敏感 topics 有獨立控制 | 私有模型保存有助後續協作的個別 topics，也接受 explicit remember | 公開產品說明未提供每輪空結果 API | topic 自動更新、使用者 edit／delete／change／forget、past-chat search 與來源 citation | topic extractor、ranking、schema 與完整率；這是已出貨產品行為，不是可直接嵌入的 API |
| **Anthropic API Memory Tool** | 應用決定是否提供 tool、如何切 store／scope 與 retention | Anthropic schema 提供 file CRUD；應用可在 Prompt 明示「只寫與某 topic 有關的資訊」，模型決定何時 view／create／edit／delete | 可以不寫檔 | 訓練過的 tool contract、JIT read、SDK handler／tool loop；儲存與 validation 由應用掌握 | 不提供 managed semantic extractor、domain admission policy 或自動敏感資料強保證；官方明示應用要自行驗證 write |
| **Google Memory Bank** | 應用選 source、scope、allowed topics | 只有匹配至少一個 managed／custom topic、且判定對未來有價值的資訊才保存；custom topic 由 label／instructions 定義，官方建議一律配正、負 few-shot | **空結果是正常成功**；負例應示範空 `generated_memories` | extraction、同 scope consolidation、create／update／delete、revision；也可只交 pre-extracted memories 給 managed consolidation | topic 沒定義的內容不會自動保存；敏感資料排除不是絕對保證；完整職務語意仍由產品提供 |
| **AWS AgentCore Memory** | 應用選 event、actor／session、namespace 與是否掛 strategy | 沒有 strategy 就不產生 long-term record；built-in strategy 決定類型，override 可加 domain extraction／granularity instructions，必要時才 self-managed | 官方 semantic Prompt 規定沒有 relevant／noteworthy information 就回空列表 | 非同步 extraction／consolidation、record lifecycle；built-in／override 可沿用 managed pipeline | generic semantic default 不會知道 JD 低頻關鍵細節；其預設 contradiction 甚至可能依措辭信心選邊，不能直接冒充 Caliburn 政策 |
| **LangMem** | 應用選哪些 messages、namespace、hot path／background | manager 的 `instructions` 與可選 schema 決定抽取內容；預設偏好 surprising／persistent 資訊，可完整覆寫；工具版也允許自訂何時 create／update／delete | 無新資訊可 no-op | 搜尋既有 Memory、LLM extraction、insert／update／delete、store upsert 與 version history | 預設 instructions 不保證職務細節；官方還明示 under-extraction 會造成 low recall，應用必須調整 instructions／representation |

這張表支持的是**責任分界**，不是某個供應商勝出：成熟方案普遍已把來源、抽取、修訂與儲存拆開，也普遍保留一個由產品定義「什麼值得保存」的 seam。沒有一家公開系統把「開啟 Memory」等同於「已理解 JD 需要的全部工作細節」。

### 9.11 三個 retention 候選及失敗模式

#### 候選 A：完全使用 generic default

只採供應商預設的 `useful`、`noteworthy`、`surprising`、`persistent` 判準，不提供職務領域語意。

- **優點**：整合最少、Prompt 最短、最快開始。
- **致命風險**：低頻但高影響的工作細節，例如年度一次的核准責任、例外處理、風險升級或責任邊界，可能不「常出現」、不「令人意外」，仍直接改變 JD。generic default 沒有官方完整率保證。
- **裁決**：不符合 M2／M3，不能作正式方案。

#### 候選 B：把完整 transcript 全部複製成 durable Semantic Memory

不做語意 admission；每段員工對話都當成長期 Memory。

- **優點**：表面上不漏來源文字。
- **致命風險**：把 source history 與 Semantic Memory 混成同一層，導致寒暄、口誤、舊說法、助理建議與重複敘述持續污染日常召回；成本與 Context 噪音隨訪談成長。它仍沒有完成更正、抽象、去重與 current-head 管理。
- **裁決**：M10 已由 durable conversation／events 處理；不應用複製 transcript 冒充 M1～M3。

#### 候選 C：可信 runtime gate＋產品定義的語意 admission＋成熟 consolidation

由 runtime 決定可信 scope、來源許可與安全 policy；由受控 domain instructions／topic／strategy＋正負 examples 定義哪些員工資訊會影響現在或未來的 JD 分析；由成熟 pipeline 做 extraction、CRUD、去重與 consolidation；原始來源獨立保留供回查。

- **優點**：與 Google topics＋few-shot、AWS override、Anthropic app prompt、LangMem custom instructions 的共同擴充模式一致；不需要自建 storage／CRUD／search engine，又能把低頻職務細節納入。
- **主要風險**：domain instructions 本身仍可能 under-extract；managed consolidation 也可能錯誤合併。必須允許空結果，但不能把「模型沒有輸出」直接當成「本輪沒有新工作資訊」。
- **裁決**：目前唯一同時符合 M1～M3、成熟機制優先與不複製 transcript 的候選；**暫定採用其責任分界，尚未選實作。**

另有一個不採的變體：用大量 deterministic keyword／欄位規則判定所有職務 admission。規則適合 scope、權限、敏感資料與 schema validation，但不足以判斷自然語言中的工作目的、例外、責任邊界與隱含更正。除非後續實測證明某個窄錯誤可由規則穩定攔截，否則不建立第二套 domain classifier。

### 9.12 暫定的產品語意：Retention 不能以出現頻率為門檻

目前只固定效果，不固定 Prompt 文案或 record schema：

1. **應進入／修訂 durable Semantic Memory 的候選**：員工已提供、而且可能改變目前或未來 JD 分析的工作資訊；包含工作行動、對象、目的／成果、輸入輸出、頻率、情境、例外、工具／方法、判斷、協作／交接、責任／核准邊界與 K／S 線索。
2. **低頻不等於不重要。** 一次性、季度性、年度性或只在異常事件出現的工作，只要影響責任、成果、風險或職務邊界，就不能因不常出現而被 generic `persistent／frequent` 規則排除。
3. **未知、矛盾與待確認也是有未來價值的資訊。** Admission 不能因它尚未成為肯定事實就丟掉；如何表徵與 consolidation 不選邊，留給 §9.5 第 2 題研究。
4. **員工訊息是職務事實來源；助理訊息只作解讀上下文。** 若員工只回答「對／不是這樣」，可以用前後對話解析其確認或否定的完整語意，但不能把未經員工確認的助理建議自行升格為員工工作事實。這與 AWS 官方 Prompt「以 user／結構事件為事實來源，assistant 只作 supporting context」一致。
5. **可合法不產生 Memory**：寒暄、純 UI／流程控制、沒有新增語意的重複、只屬當輪推理的中間文字，以及未經員工支持的助理提議，不必形成新 durable Memory。
6. **明確更正具有高 admission 優先級，但不代表直接覆寫。** 它必須進修訂流程並在下一次依賴前反映 current understanding；是否為真正取代、不同案例或不同時點，仍是下一題的衝突／修訂語意。
7. **原始對話獨立保留。** 語意 admission 漏掉內容時仍可查回來源，但 source fallback 不能被誤寫成「Semantic Memory 已完整」。

這裡使用「可能改變 JD 分析」作目的邊界，不表示 admission 階段要先生成 Duty／Task／OPKS，也不要求模型填 Skill ID。職務分析方法應提供保存判準與 examples；Memory pipeline 負責執行抽取／修訂，不讓模型回報 framework metadata。

### 9.13 仍未決定，禁止提前施工的項目

本節沒有決定：

- 正式採 Google、AWS、Anthropic Memory Tool、LangMem 或其他框架；
- admission 在 hot path、background 或混合執行；
- 使用單一 topic、多 topic、自然語言文件或 structured schema；
- 一次模型 run 或獨立 extraction run；
- 正式 Prompt、few-shot 數量、token budget、model 或 retry；
- 如何保存未知／衝突、如何做 M9 完整盤點，以及如何把案例抽象成穩定工作。

其中 hot path／background 只影響何時生效、成本與失敗恢復，不改變本節的 admission 語意。後續實作候選必須能接受產品定義的 instructions／topic／strategy、允許 no-op，並把 runtime scope／安全 policy 與模型語意判斷分開。

### 9.14 Retention／admission 主要官方來源

- [OpenAI — Codex Memories：eligible chats、useful context、背景 extraction／consolidation、secret redaction 與 per-chat 控制](https://learn.chatgpt.com/docs/customization/memories)
- [Anthropic — Claude 現行 Memory：個別 topics、Pause／Incognito、敏感 topic policy、explicit remember 與使用者 edit／delete](https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context)
- [Anthropic — API Memory Tool：client-side file CRUD、JIT read、application-guided topic 與 write validation](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- [Google — Generate memories：valuable information、topic gate、consolidation、allowed topics 與 pre-extracted memories](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories)
- [Google — Set up Memory Bank：custom topic instructions 與正、負 few-shot](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/setup)
- [Google — Memory Bank troubleshooting：不符合 topic／價值時，零 Memory 是正常成功](https://docs.cloud.google.com/gemini-enterprise-agent-platform/troubleshooting/memory-bank)
- [AWS — Memory strategies：沒有 strategy 就沒有 long-term extraction；built-in、override 與 self-managed 分層](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-strategies.html)
- [AWS — Built-in override：保留 managed pipeline，只覆寫 domain extraction／consolidation instructions](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-configuring-custom-strategies.html)
- [AWS — Semantic Memory system Prompt：user／structured event 來源、空結果、細節保留與 Add／Update／Skip](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-system-prompt.html)
- [LangMem — Semantic Memory extraction：custom instructions／schema、collection manager 與 under-extraction 風險](https://langchain-ai.github.io/langmem/guides/extract_semantic_memories/)
- [LangMem — Memory manager API：instructions、search、insert／update／delete 與 version history](https://langchain-ai.github.io/langmem/reference/memory/)

### 9.15 M5 深挖：這不是重做通用 D4

本節只處理 §9.5 第 2 題：「不知道、互相衝突、待確認與已更正的內容，如何在成熟 Memory pipeline 中合法存在？」研究時先回讀通用 Memory 文檔 D4／D4-b 與本文 M5，再核對截至 2026-08-31 的官方資料。既有通用裁決已經回答 active head、revision history、未解衝突與時間變化；本節補的是 **Caliburn 所需效果能否由成熟 primitive 承接，以及哪些語意不能沿用 managed default**。

本節沿用本文與通用 Memory 文檔的研究紀律：

1. 只採官方產品、官方文件、官方工程資料與官方框架文件；
2. 明確分開「平台真的公開什麼」、「由多家行為能推得的共同 primitive」、「目前產品 mapping」與「尚未決定的實作」；
3. CRUD、current head、revision 與 rollback 只算生命週期能力，不冒充衝突判斷；
4. 官方未公開的內部 contradiction policy 明記為未知，不用大廠名稱替推論背書；
5. 本節不選 schema、framework、Prompt、Tool、資料表、狀態 enum 或 UI。

### 9.16 各家最新公開行為：共同有修訂，沒有共同的未解衝突預設

| 來源 | 官方目前公開的行為 | 對 M5 能下的結論 | 不能下的結論 |
| --- | --- | --- | --- |
| OpenAI Codex | eligible prior chats 經背景 extraction 與獨立 consolidation；本地檔案分 summaries、durable entries、recent inputs 與 supporting evidence | 證明 Memory 不是 transcript 重播，也會形成可更新的整理結果 | 官方頁未公開 contradiction、unknown、revision 或「哪個說法勝出」規則；不能宣稱 Codex 已提供可直接採用的 M5 policy |
| Anthropic Claude 消費型 Memory | Memory 以個別 topics 保存；使用者可在自然對話要求 remember／change／forget，也可檢視、編輯或刪除 topic；修改用於後續對話 | 支持一般聊天自然更正與 active understanding 更新；不需要專用「更正原話」操作 | 產品沒有公開 topic 內部如何偵測、分類或保留未解衝突 |
| Anthropic Memory Tool | Claude 以 client-side tool 要求 read／create／update／delete path-addressed files，application 執行並驗證；可由 Prompt 指示保持內容 coherent／up-to-date | 提供成熟 CRUD、按需讀取與可自訂語意承載面，足以實作 domain conflict policy | Tool protocol 本身沒有替產品決定「更正／時間變化／不同案例／未解衝突」 |
| Anthropic Managed Agents Memory | live retrieve 讀最新 head；每次非 no-op mutation 產生 immutable version；支援 OCC、稽核、回復與 redaction | 直接承接 current head、歷史版本分離與避免 concurrent overwrite | version 是 mutation history，不是自動的 truth-maintenance 或現實有效時間；它不判定哪種說法正確 |
| Google Memory Bank | GenerateMemories 先抽取再 consolidation；同 scope 會檢查重複與矛盾並 create／update／delete；每次 mutation 可有 immutable revision，預設看 latest，也可增加歷史 revisions 做 corroboration | 直接承接 managed consolidation、最新版本、歷史檢視與 rollback | 公開 API 沒有「unresolved contradiction」結果；矛盾資料可能使舊 Memory 被更新或刪除，不能直接假設 M5 已完成 |
| AWS AgentCore Semantic Memory | 最新 canonical English system Prompt 明示 ambiguity 不可擅自解指；consolidation 採 Add／Update／Skip，矛盾時預設依語句 confidence cues 決定 update 或 skip；可 override extraction／consolidation instructions | 證明 managed default 會主動消解衝突，也證明官方提供 domain override seam | `seems`／`definitely` 等語氣不是員工工作事實的 authority，不能直接沿用為 Caliburn 真實性規則 |
| LangMem | manager 以 LLM 讀 conversation＋existing memories，依 custom instructions／schema insert、update、delete；可把 outdated／contradicted memory 更新或移除 | 提供成熟的可配置 consolidation 與 storage integration，不必自建 CRUD engine | 預設 manager 沒有跨產品通用的 unknown／unresolved-conflict policy；revision 能力取決於 substrate |

資料時效注意：AWS canonical English 頁目前的 contradiction 規則與較舊、仍可被搜尋到的部分本地化／PDF內容不完全相同。本研究依「目前 canonical 官方頁優先」原則採用最新 English 頁，不把舊版行為當現行基線。這也再次證明 Memory default 會變，產品 truth policy 不應默認綁死在供應商未版本化的 Prompt 行為上。

### 9.17 先正規化問題，不把所有「前後不一樣」都叫衝突

M5 需要的是可觀察語意，不是預先決定欄位。至少要區分下列情況：

| 情況 | 白話例子 | 正常 current understanding 應有的效果 |
| --- | --- | --- |
| 尚未取得／員工不知道 | 「這項報表多久做一次我不確定」 | 合法保留「目前不知道」；不得補成推測值，也不得把缺資料當否定事實 |
| 指涉或語意不清 | 「那個系統也是我維護」，但當下有兩個系統 | 保留不清楚之處；上下文不能唯一解出時詢問，不把任一候選升格成事實 |
| 未解矛盾 | 同一工作、同一時點與條件下，先說每週、後說每月，但沒有說哪個才對 | active recall 必須讓 LLM 看見「兩種說法尚未裁決」；不得只因較新、語氣較強或模型較有信心就選邊 |
| 明確更正 | 「我剛才說錯了，不是每週，是每月」 | 新理解成為 current head；舊理解退出一般 recall，但 conversation／revision 仍可按需回查 |
| 真實時間變化 | 「以前每週，七月起改成每月」 | 不是邏輯矛盾；current 以每月為主，必要時保留明確的轉換脈絡；不可用 Memory 寫入時間冒充生效時間 |
| 不同案例／條件 | 平常自己核准，金額超過門檻時由主管核准 | 不是矛盾；兩者必須保留各自條件，不能 consolidation 成一條失去例外的泛化句 |

這個分類不要求模型輸出六個 enum。它先固定行為驗收邊界：日後不論採 topic、file、profile、collection 或 custom schema，都必須能讓下游 LLM 分清「目前成立」、「目前未知」、「仍有衝突」、「已被更正」與「只是在不同時間／條件成立」。

### 9.18 四種候選行為

| 方案 | 行為 | 優點 | 主要問題 | 本輪判斷 |
| --- | --- | --- | --- | --- |
| A. 直接採 managed default | 讓 Google／AWS／其他 manager 自行 update、delete、skip 或按 confidence 選邊 | 最少配置 | 可能把未解衝突消掉；供應商預設與版本變更會變成產品 truth policy | **不採為 M5 基線** |
| B. 所有說法都 append 成 current facts | 舊新說法都保留，交給主模型自己理解 | 不會刪錯 | 一般 recall 會同時出現未標示的互斥事實；成本、混淆與誤用隨訪談增長 | **不採** |
| C. 成熟 lifecycle＋產品 conflict policy | 沿用成熟 extraction／CRUD／revision／search，只以 domain instructions／representation 區分更正、時間／條件差異、unknown 與未解衝突 | 保留成熟框架能力，又避免 managed default 偷選邊；對應既有 D4 | 仍需後續比較哪種 extension seam 效果最好 | **目前推薦，待 Owner 討論確認** |
| D. 全面 temporal／knowledge graph | 每個 claim 建有效期間、關係與失效邊 | 歷史與關係推理最完整 | 抽取、時間解析、圖維護與錯誤面顯著增加；M5 沒有證據要求全面採用 | **不列第一版基線** |

方案 C 的重點不是自建一套 Memory 系統，而是**不把產品真實性規則交給 generic consolidation default**。Anthropic Memory Tool、AWS override 與 LangMem instructions／custom schema 直接提供 domain conflict policy 的 extension seam；Google 公開的 topics／few-shot 主要控制 extraction，不能宣稱可覆寫 managed contradiction policy，但可用 direct CRUD、pre-extracted memories 或停用 consolidation 避免盲用該預設。正式選哪條成熟路徑仍留待後續框架比較。

### 9.19 M5 目前產品 mapping（研究判斷，尚未成為 ADR）

1. **未知與未解衝突都是合法的 current knowledge。** Memory 不只保存肯定事實；它必須讓後續分析知道哪些地方目前無答案或有互斥說法。
2. **一般 recall 只提供 current understanding 與仍相關的未解問題。** 已被明確更正的舊 head 不得平行注入；需要核實時才回查 conversation／revision。
3. **自然對話就是主要更正入口。** 員工可直接說「我剛才說錯了」；上下文能唯一判定時更新理解，不確定才追問。這不新增「更正這段原話」按鈕。
4. **明確更正、時間變化、條件差異與未解矛盾不得混用同一規則。** recency 只能表示訊息較新，不能單獨證明真實；語氣強弱與模型 confidence 也不能當 authority。
5. **只有員工的明確澄清，或在同一上下文中沒有其他合理解讀的陳述，才能把未解衝突轉成 current fact。** 模型可指出最可能解讀，但不能在 Memory 層把推論偷偷升格。
6. **Memory 負責保存與召回未解狀態，不決定每個未解問題是否阻擋 JD。** 是否要立即詢問、可否繼續其他訪談、能否形成某項 JD 變更，仍是職務分析 Skill／LLM 的決策；storage score 不得冒充這個判斷。
7. **原始 conversation 與 Memory revision 仍分層。** M5 不要求每筆 current understanding 都由 LLM 填 quote／UUID；需要查錯、更正或釐清時，依 M10 按需回查可信 source history。
8. **M5 不要求另建一套 Caliburn Memory engine。** 成熟方案的 CRUD、current head、revision、search 與 domain extension seam 已足夠作候選 substrate；真正要保留的是上述產品效果。

### 9.20 本輪仍未決定

本輪刻意不決定：

- `unknown`／`conflict` 是自然語言、topic、file 區段、profile 欄位、collection item 或 typed schema；
- 要使用 Anthropic Memory Tool、Managed Agents、Google Memory Bank、AWS override、LangMem 或其他框架；
- consolidation Prompt、few-shot、模型、token budget、hot path／background 時機與 retry；
- 每個未解問題何時成為強制確認、何時只作一般待釐清；
- revision 保存多久、是否需要精確 quote link 或獨立 conflict entity；
- temporal grounding 是否超出 D4-b 已確認的選擇性範圍。

後續框架候選若只能把內容整理成一組「看起來確定的 facts」，且無法可靠承載 unknown／unresolved conflict，則即使 CRUD、vector search 與 revision 很完整，也不能通過 M5。

### 9.21 M5 主要官方來源

- [OpenAI — Codex Memories：背景 extraction／consolidation 與 summaries、durable entries、recent inputs、supporting evidence](https://learn.chatgpt.com/docs/customization/memories)
- [Anthropic — Claude 現行 Memory：individual topics、自然語言 change／forget、直接 edit／delete 與 past-chat citations](https://support.claude.com/en/articles/11817273-use-claude-s-chat-search-and-memory-to-build-on-previous-context)
- [Anthropic — API Memory Tool：client-side file CRUD、按需讀取、應用端 storage／validation 與 Prompt guidance](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- [Anthropic — Managed Agents Memory：latest head、immutable versions、OCC、稽核、回復與 redaction](https://platform.claude.com/docs/en/managed-agents/memory)
- [Google — Generate memories：duplicate／contradiction-aware consolidation 與 create／update／delete](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories)
- [Google — Memory revisions：current Memory、immutable revision、rollback 與 deletion recovery](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/revisions)
- [Google — Set up Memory Bank：topics、few-shot、latest／historical revision consolidation 與成本取捨](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/setup)
- [AWS — 最新 Semantic Memory system Prompt：ambiguous referent、temporal grounding 與 confidence-based contradiction resolution](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-system-prompt.html)
- [AWS — Built-in override：保留 managed pipeline、覆寫 extraction／consolidation instructions](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-configuring-custom-strategies.html)
- [LangMem — Semantic Memory extraction：custom schema／instructions 與 insert／update／delete](https://langchain-ai.github.io/langmem/guides/extract_semantic_memories/)
- [LangMem — Memory manager API：outdated／contradicted memory 的 update／delete 開關](https://langchain-ai.github.io/langmem/reference/memory/)

### 9.22 M6 深挖：保留工作關係不等於必須上 Knowledge Graph

#### 9.22.1 官方已出貨的三種成熟形狀

| 形狀 | 目前官方實例 | 能保留什麼 | 主要失敗模式 |
| --- | --- | --- | --- |
| 聚焦文字文件／profile | OpenAI Sandbox Memory 的 `MEMORY.md`＋rollout summaries；Anthropic path-addressed memory documents | 一段工作脈絡可用自然語言完整保留流程、成果、例外、協作與責任，不必把每個語意拆成欄位 | 跨文件關聯沒有 referential integrity；文件過大時更新與召回變差 |
| 自包含 JSON records／custom schema | Google／AWS records；LangGraph `namespace/key/value`；LangMem Pydantic schema／triple 範例 | 可驗證欄位、精準更新、篩選與明示關係；可在同一 record 內保存完整脈絡 | schema 太細會增加模型填錯、遷移與關聯維護；atomic fact bag 容易把脈絡切碎 |
| Temporal knowledge graph | Graphiti 的 entity／edge／episode／valid-time model | 顯式關係、歷史變化、graph traversal 與來源 episode | 額外 graph database、entity resolution、edge extraction、時態與重複治理；0.x 框架仍快速變動 |

這三種都是真實成熟做法，但沒有官方證據證明「只要工作有關聯，就應採 graph」。Anthropic 目前反而建議將 Memory 拆成多個小而聚焦的文字文件；LangMem 的 triple 也只是可選 custom schema 範例；Graphiti 適合必須查多跳、時間關係與 entity network 的問題，而不是一般 rich work context 的預設答案。

#### 9.22.2 對 M6 的暫定裁決

M6 真正要求的是：模型取回一項工作時，不能只看到互不相干的 facts，而要看得出「工作／流程 → 成果／標準 → 例外／協作／責任 → 所需 K／S」的脈絡。第一版暫定採下列效果，不預先固定程式名稱：

1. 以**多筆聚焦、語意自包含的工作理解文件／records**作主要表徵；每筆可有一段完整 rich text，而不是把所有細節強迫原子化；
2. 只保留少量 runtime 可驗證的 envelope，例如 trusted scope、runtime ID、revision、current status；模型不填 scope、ID、時間與版本；
3. 若一個語意必須跨記錄查找，可由小型 relation reference 或同一工作脈絡中的明文關係承接；是否需要 typed link 留到 schema spike，而不是先升級成 graph；
4. Knowledge Graph／Graphiti 暫列**條件式候選**：只有代表性資料證明 bounded document／record 無法可靠完成跨項關係查找、去重或修訂時才重開；目前不上第一版主路徑。

這項裁決保留成熟 framework extension seam，但避免把 M6 誤做成一套新的 ontology／graph 產品。

### 9.23 M9 深挖：完整盤點是 deterministic inventory，不是更大的 semantic top-k

#### 9.23.1 多家官方確實提供 list-all primitive

| 方案 | 官方全量能力 | 分頁／邊界 | 研究判斷 |
| --- | --- | --- | --- |
| Anthropic Managed Agents Memory | `List memories` 可遞迴列出 path tree，`view=full` 可批次取內容 | 穩定 server-defined order、opaque `next_page`；一般最多 100，full view 最多 20 | 能作可信 inventory；目前仍是 beta／provider-specific |
| Google Memory Bank | exact-scope `RetrieveMemories` 不帶 similarity 可取該 scope 全部 | 每頁最多 100；SDK pager 可走完所有頁 | 能清楚分開「全量」與「相似 top-k」 |
| AWS AgentCore Memory | `ListMemoryRecords` 依 namespace／namespacePath 列出 | `nextToken`，每頁 1～100；null 表示結束 | GA managed primitive；另有服務與模型成本 |
| LangGraph Store | `search(namespace, query=None, filter=None)` 是 listing mode | `limit/offset`；超過 limit 靜默截斷，backend order 不保證一致 | 可用，但 runtime 必須自己走完 offset 並處理變更一致性 |

因此 M9 不要求自建 search engine；成熟 substrate 已提供 inventory。真正不能交給模型的是：scope、分頁迴圈、處理帳與「是否真的走到最後一頁」。

#### 9.23.2 仍存在的共同限制

目前查到的公開文件都沒有保證：當 inventory 跨多頁進行時，其他 writer 同時增刪／更新資料，所有頁仍代表同一個資料快照。Anthropic 提供 stable order，Google／AWS 提供 pager／token，LangGraph 提供 offset；這些都不是公開的 cross-page snapshot-isolation 承諾。

M9 因此需要以下**行為契約**，但尚不固定 API 名稱：

1. runtime 綁定單一 JD 的 trusted scope；模型不能自行填 scope；
2. runtime 以 list mode 走完每頁，保留已處理的 runtime ID／revision manifest；
3. 全域盤點期間使用穩定 revision：單一操作者產品可在該段分析期間暫停 Memory／JD mutation；若 head revision 改變，盤點作廢並重啟；
4. 能塞進單一 Context 時直接完整分析；超過 budget 才分批，並由 runtime 確保每個 manifest item 恰好被處理，最後再作跨批次整合；
5. semantic search 仍服務日常相關召回，不能拿 top-k、最近 N 筆或「模型覺得看夠了」冒充 M9；
6. M9 只在需要全域涵蓋／去重的 JD 分析或正式匯出前使用，不必每則員工訊息都付全量成本。

### 9.24 M7 深挖：員工工作案例不是 agent execution episode

> 閱讀提示：§9.24～§9.31 是前一輪候選研究，其中把 `durable conversation＋current Semantic Memory` 寫得過於接近既定答案。Owner 已在 §9.32 校正：案例、理解與 JD 是認知角色，不是固定 storage pipeline；物理表徵與暫定推薦以 §9.32～§9.37 為準。

AWS Episodic Memory 是真實成熟能力，但其官方 episode 主要描述 agent trajectory：situation、intent、turns／actions、assessment、justification、outcome 與 reflection；它在偵測一段 episode 完成後才產生，並以相似 episode／reflection 改善未來 agent 行為。這不等於 Caliburn 的「員工舉了一個工作案例」。若直接套用，容易把顧問工具使用經驗與員工實際工作混成同一種記憶。

跨 OpenAI／Anthropic／Google／AWS 的較穩定共同分層已足以承接第一版 M7：

1. durable conversation／events 保存員工具體案例及原始脈絡；
2. current Semantic Memory 保存從案例中已成立、會影響職務理解的流程、例外、責任與模式；
3. 新案例出現時，日常 recall 取回相關目前理解，必要時再 search／read 原始案例；
4. 「兩個案例是否其實是同一穩定工作」「應修訂既有 Task 還是只保留案例」仍由 LLM＋職務分析 Skill 判斷；Memory manager 不自動發布 Task；
5. 不建立第三套 episodic store 作第一版必要元件。只有後續證明原始 conversation 的案例查找不足，或需要跨大量案例產生可重用 reflections，才評估 AWS episodic／Graphiti episode／獨立 case collection。

這同時保留案例細節與穩定工作，又不讓每個案例永久膨脹 JD。

### 9.25 M1～M11 整體一致性複審

| 能力群 | 複審後承接方式 | 是否仍有未解架構缺口 |
| --- | --- | --- |
| M1／M4 長期連續與修訂 | durable conversation＋current Semantic Memory＋revision lifecycle | 無；只需產品 admission／conflict instructions |
| M2／M3 細節與廣度 | rich self-contained records＋原始來源 fallback＋domain retention policy | 無新 storage 缺口；抽取完整性仍須由職務分析內容約束 |
| M5 未知／衝突 | 成熟 CRUD／revision＋產品 truth policy | 不需新 engine；需在 Memory instructions／representation 明示合法 unresolved state |
| M6 關係 | bounded rich document／record 優先，必要時少量 link | 第一版不需 graph；schema 尚待小型 spike |
| M7 案例／穩定工作 | source events＋current semantic layer；抽象交給 Skill | 第一版不需第三層 episodic engine |
| M8 日常召回 | 小量自動混合召回＋模型按需 search／read | 無；需 retrieval budget 與工具錯誤契約 |
| M9 完整盤點 | exact-scope list-all＋pagination＋stable revision＋runtime manifest | 是硬選型條件，但成熟 substrate 已有 primitive |
| M10 來源回查 | conversation／events 獨立保存、按需查詢 | 無；不要求模型填 quote／source UUID |
| M11 隔離 | trusted per-JD namespace／scope | 無；不做跨 JD Memory |

複審沒有發現 M1～M11 需要恢復舊 Work Model／Focus／Gap 系統，也沒有理由建立第二份「工作理解地圖」作另一個權威。日常入口索引、manifest 或目錄若存在，只能是可重建的 retrieval projection，不是第二份 Memory。

### 9.26 完整成熟方案候選

#### 候選 A：LangGraph 1.x LTS＋Postgres Store／Saver＋LangChain Tool／Structured Output（暫定首選）

- **效果**：LangGraph 1.x 是 LTS；Store 原生提供 namespace、JSON value、exact get、listing、filter，以及在設定 search index 後的 semantic search，Postgres backend 可持久化；LangGraph runtime 承接 thread execution／interrupt／resume，Saver 持久化 checkpoints，Store 承接跨回合 Semantic Memory，兩者責任可分清。Trusted JD scope 仍由 Caliburn runtime 注入，不能把 namespace primitive 誤稱為 AuthZ。
- **M6／M9**：JSON value 可承載 rich document 或薄 schema；`query=None` listing 加 runtime pagination 可完成 M9。
- **模型可替換性**：LangChain model interface 不綁 OpenAI／Anthropic；符合日後可換模型與參數的方向。
- **自訂範圍**：仍需職務領域 retention／conflict instructions，以及很薄的 Memory read／search／mutation tools；這是產品語意，不是重寫 persistence／orchestration。
- **風險**：LangGraph offset listing 在資料同時變動時不提供公開 snapshot 保證，需使用 stable revision／短暫鎖；語意品質仍取決於 Prompt／Skill。

#### 候選 B：AWS AgentCore Memory managed strategies

- **效果**：GA、raw events、semantic／summary／preference／episodic／custom strategies、namespace、metadata filter、list pagination 與觀測都完整；可大幅少寫 Memory 基礎設施。
- **限制**：內建 generic semantic／episodic policy 不等於職務理解；要符合 M2／M5／M6 仍需 override 或 self-managed strategy。服務按 event、stored record、retrieval 與所用模型計費，另增加 AWS IAM／region／data lifecycle 與 cloud dependency。
- **判斷**：若未來產品接受 AWS managed control plane，這是強力替代候選；目前不因功能表最多就優先於本機 Postgres 路徑。

#### 候選 C：Google Memory Bank

- **效果**：topics＋few-shot、exact scope、similarity、full-scope paging、revision／rollback 與 managed generation 很完整。
- **限制**：主要表徵是 standalone fact；M6 rich relationship 與 M5 unresolved state 需額外 topic／fact convention，且綁 Google Cloud。Memory generation／embedding token、storage 與 read/write operations 另外計費。
- **判斷**：適合 atomic user facts／personalization；對 Caliburn rich work understanding 的表徵不如 A 直接。

#### 候選 D：Anthropic Managed Agents／Memory Tool

- **效果**：file-based just-in-time retrieval、stable list cursor、full-content bulk read、immutable versions、OCC 與 point-in-time recovery 很符合 M2／M6／M9。
- **限制**：Managed Agents／Memory Store 仍是 beta，綁 Claude agent harness；Managed Agents 另有 token＋session runtime 成本。Client-side Memory Tool 可自管 storage，但其 schema／consolidation policy仍由應用定義。
- **判斷**：是最佳設計參考與 Claude-only 候選，但目前不是 provider-neutral production 首選。

#### 不列第一版主路徑

- **LangMem**：功能形狀很貼近需求，但 PyPI 最新穩定版仍是 `0.0.30`（2025-10-27），沒有 LangChain／LangGraph 的 1.x LTS 承諾；可作 Prompt／Tool／schema spike 或參考實作，不能在未驗證相容性與維護狀態前成為唯一 production owner。
- **Graphiti**：專案仍活躍且 temporal relationship 能力最強，但目前是 0.x，並增加 graph database、entity／edge extraction 與 temporal governance。沒有 M6 實證缺口前屬過度設計。

PydanticAI Harness、DBOS 與其他 agent／durable-workflow 框架本輪不列入 Memory 決賽：這不是判定它們不好，而是 M1～M11 的差異比較沒有產生必須再引入第二套 runtime 才能補上的已證實缺口。若未來因整體 agent runtime 選型重新比較，應另以該框架當時的官方 contract 評估，不在本文用「未被研究的缺點」排除。

### 9.27 暫定推薦：採成熟底座，不採 managed default 語意

> 歷史候選提示：本節的底座比較仍可作框架資料，但資料層與 Prompt／Tool 形狀已由 §9.32 起重新開啟；不得把本節直接當作核准方案或施工規格。

在效果、成熟度、模型可替換、本機產品邊界、成本與複雜度一起考量後，目前暫定推薦候選 A：

```text
durable conversation／events
        +
LangGraph 1.x LTS thread runtime／checkpoint
        +
LangGraph Postgres Store（每份 JD 的 trusted namespace）
        +
多筆聚焦、rich self-contained Semantic Memory records
        +
日常 bounded retrieval ＋ model-initiated search/read
        +
全域 list-all inventory（只在 JD 全域分析／匯出前）
        +
職務分析 Skill／Memory instructions／JD editor authority
```

這不是為了保留現行架構，而是因為它是唯一同時滿足以下條件的完整候選：

1. 不綁單一模型供應商；
2. 使用 LTS orchestration 與成熟 Postgres persistence，而不是自建 Memory database；
3. M6 可先用 rich document／record，不被 atomic fact 或 graph 強迫；
4. M9 有 deterministic list primitive；
5. 單一員工／JD scope 能本機隔離，不新增 managed cloud control plane；
6. 未來若實證需要，可局部換成 LangMem manager、Anthropic files、AWS strategy 或 Graphiti，而不改產品成果定義。

這仍是 Working Research，不是 ADR。Owner 核准前不得把它當既定施工方向。

### 9.28 Memory Prompt、Tool 與 Context 組裝的最薄建議

#### Memory Prompt／instructions

Memory 指令只描述 selection／consolidation 語意：保存所有可能改變 JD 的員工工作資訊，包括低頻高影響工作、流程、成果、頻率、例外、協作、責任與 K／S 線索；允許 unknown／unresolved conflict；明確更正取代 active head；不把猜測補成事實；無新內容可回 no-op。它不要求模型填 runtime ID、scope、revision、時間、Skill ID 或 quote UUID。

#### Model-facing Memory tools

第一版只需要小而穩定的能力面，不把整個 Store API 暴露給模型：

1. `search_memory(query, limit)`：找相關目前理解；
2. `read_memory(handle)`：讀完整內容／目前 revision；
3. 一個窄的 mutation tool：create／replace-current／delete 或等價受限操作；create 的 ID 由 runtime 建立，update 的 handle 必須來自真實 read／search；
4. 完整 list／pagination、scope、OCC、manifest 與批次遍歷由 runtime 執行，不要求模型自己記 page token；
5. typed error 至少區分 not found、stale revision、invalid scope、validation failed 與 transient failure，並限制修正次數。

若 LangMem compatibility spike 通過，可讓它提供 manager／tool 實作；否則用 LangChain 1.x tool＋Structured Output 包一層 LangGraph Store。兩者產品 contract 相同，不把 LangMem package 當必要權威。

#### 每個實質訪談回合的 Context

```text
穩定 base policy／必要 tool definitions（可快取）
+ 當前員工訊息與最近對話
+ runtime 自動召回的小量相關 current Memory
+ 與當前工作相關的 JD 片段／待審 working state
+ 按需載入的職務分析 Skill
+ 模型視需要 search／read 更久遠 Memory 或原始 conversation
```

不把所有 Memory、完整 transcript、完整 JD、全部 Skills 與全部 Tools 每輪塞入。只有 global JD audit 才讀完整 Memory inventory 與完整 JD；若超過 Context，採 runtime-controlled 分批盤點。這符合 OpenAI retrieval budget／tool search／structured output guidance，以及 Anthropic just-in-time retrieval／progressive disclosure／prompt caching。

#### 更新與 JD 分析順序

每次有實質新工作資訊時，Semantic Memory 必須先形成可驗證的 current revision；後續若同一 run 要修改 JD，必須讀到這個已發布 revision。這可以是同一 LangGraph run 中的多個 state／tool step，不代表固定呼叫模型兩次。若該回合只是一般澄清而不需要 JD 變更，完成 Memory update 與顧問回答即可；不強迫每輪做全域 JD 分析。

### 9.29 成本與過度設計審核

1. **最大節省來自不全量重播。** 日常只取 recent conversation＋少量相關 Memory；全量 inventory 只在真正需要全域 JD 判斷時執行。
2. **先啟用 prompt caching。** 靜態 tools／base policy／穩定 Skill 放前綴，動態 Memory／JD 放後面；Anthropic 官方定價將 cache read 列為基礎 input token 價格的 0.1 倍，OpenAI 也建議 static-first prompt layout。實際節省仍取決於前綴穩定度與供應商模型，不能只靠功能已開啟就假設命中。
3. **不預設第二個 agent 或昂貴 reflection。** 單一主顧問以 framework tool loop 完成 search／update／JD edit；只有明確品質缺口才新增專用 manager call。
4. **不預設 graph／episodic engine。** M6／M7 第一版已有較薄成熟做法；先用代表性資料驗證，再以失敗證據升級。
5. **不要只追求少寫程式。** AWS／Google 可少寫 persistence，但增加雲端依賴、每事件／record／retrieval／token 成本；首選應是最終 JD 效果與可靠性，再比較成本與程式量。

### 9.30 最低驗證策略（不提前建完整 eval）

本輪不授權實作，也不建立大型 eval。未來方案 spike 只需先證明五個高風險行為：

1. 低頻高影響工作會進 current Memory，不因只出現一次被忽略；
2. 員工明確更正後，active head 更新，舊說法不再正常召回；
3. 兩個未解矛盾能同時存在，不被 manager 自動選邊；
4. 兩個相似案例可取回並由 Skill 判斷是否屬同一穩定工作，而不是自動建立兩個 Task；
5. 資料量超過一頁時，global audit 能證明所有 active runtime ID／revision 都被處理一次，且分析期間變更會使 audit 重啟或失效。

通過這五項只證明底層方案適合進產品實作，不代表最終 JD 已完成正式 eval；完整效果評估依 Owner 先前決定，留到產品主體完成後。

### 9.31 本輪新增主要官方來源

- [OpenAI Agents SDK — Sandbox Agent memory：conversation 與 distilled files 分層、progressive disclosure、兩階段 generation](https://openai.github.io/openai-agents-python/sandbox/memory/)
- [OpenAI — 最新 model guidance：structured outputs、tool search、retrieval budget、compaction 與 Agents SDK](https://developers.openai.com/api/docs/guides/latest-model)
- [Anthropic — Managed Agents Memory](https://platform.claude.com/docs/en/managed-agents/memory)
- [Anthropic API — List memories：stable order、recursive path、cursor、full view](https://platform.claude.com/docs/en/api/http/beta/memory_stores/memories/list)
- [Anthropic — Memory Tool：file CRUD 與 just-in-time retrieval](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- [Anthropic — Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Anthropic — Prompt caching 與 deferred tool loading](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-use-with-prompt-caching)
- [Anthropic — Pricing：prompt-cache write／read 與 Managed Agents 成本](https://platform.claude.com/docs/en/about-claude/pricing)
- [Google — Fetch memories：exact scope all-pages 與 similarity top-k 分開](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/fetch-memories)
- [Google — Memory Bank setup：topics、few-shot 與 consolidation](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/setup)
- [Google — Agent Platform release notes：各項 Memory Bank 能力的 GA／Preview 狀態](https://docs.cloud.google.com/gemini-enterprise-agent-platform/release-notes)
- [AWS — ListMemoryRecords：namespace、nextToken 與 page size](https://docs.aws.amazon.com/bedrock-agentcore/latest/APIReference/API_ListMemoryRecords.html)

### 9.32 重要校正：案例、理解與 JD 是認知關係，不是預設 storage pipeline

Owner 於 2026-08-31 校正：本產品唯一目的仍是產出高品質 JD。「工作案例 → 工作理解 → JD」只是專業顧問如何從具體敘述形成目前認識，再萃取正式文件的白話認知過程；不代表每個概念都要存資料、不代表三套 schema／store，也不代表固定三個 stage 或三次模型呼叫。

更精確地說，Caliburn 不需要為了證明流程存在，而產出「工作案例文件」或「工作理解文件」兩個中間產品。衡量標準只看底層方案能否讓顧問長期記住必要細節、修訂錯誤理解、找回相關資訊、完整盤點工作範圍，並據此產出與維護高品質 JD；中間認知可由一個成熟 Memory substrate 的不同操作、同一 collection 的不同內容、conversation＋Memory，甚至當輪 Context 承接。

這項校正重新開啟 §9.24、§9.27～§9.28 中過早固定的資料層假設：`durable conversation＋current Semantic Memory` 仍是強候選，但「案例只放 conversation」「穩定理解一定另存 records」不能再冒充已核准產品事實。後續只以 M1～M11 與高品質 JD 的可觀察效果比較資料形狀。

名詞在本節只作語意辨識：

- **具體工作資訊／工作案例**：員工描述某次、某類或某條件下實際做過的工作；它可揭露流程、例外、結果與責任，不必成為獨立 entity。
- **目前工作理解**：顧問此刻對員工工作全貌的有效認識；它可能來自 conversation、Memory records、profile、文件或當輪 Context 組合，不預設產品／程式名稱。
- **JD**：員工主要閱讀、編輯、審核與匯出的正式工作文件；它是較完整工作資訊經抽象、合併、去重與品質審查後的成果，不是 Memory dump。

### 9.33 四種物理表徵候選重新比較

| 候選 | 實際形狀 | 優點 | 主要風險 | 成熟方案依據 | 本輪判斷 |
| --- | --- | --- | --- | --- | --- |
| **A. 單一大型 current profile／document** | 所有目前理解與重要案例都反覆改寫進一份文件 | 每次容易取得全貌；完整盤點最直接 | 隨內容成長，更新容易重寫漏細節或局部覆蓋；LangChain 官方也警告大型 profile 更新會變得 error-prone | Google structured profile、LangMem profile、Anthropic file | 不作第一版首選；可作小型 scope 的 projection |
| **B. 同一 collection，不同語意角色** | 多筆 records 可分別承載穩定工作、具體細節／案例、未知或衝突；仍在同一 trusted scope | recall 與全量盤點佳；不需多個 store；可保留大量細節 | 角色、合併／拆分與 current head 仍需模型／manager 判斷；records 過碎會變 fact bag | Google natural-language memories、LangMem collection、AWS semantic/custom records | 強候選；但不先固定 role enum 或 case schema |
| **C. conversation 保留具體內容，semantic collection 只保留目前理解** | 原始訊息耐久保存；多筆 current records 保存足以支援後續工作的整理知識 | 最薄、最接近多家 source＋derived 共同模式；不用第三套 case store | 若 consolidation 過度摘要，具體細節只剩 transcript，相關回查成本與漏找風險上升；需證明所有會影響 JD 的資訊都被吸收或可找回 | OpenAI conversation／compaction、Anthropic Memory files、Google events→memories、AWS events→semantic records | 第一版基線候選，但必須加「細節不可丟」的 admission／retention 約束 |
| **D. 顯式 episode／case＋derived fact／graph** | 原始 episode、derived facts／entities／summaries 及來源關係分層 | provenance、時間變化、跨案例關係與查詢最完整 | 額外 LLM ingestion、entity resolution、graph database、時間／關係治理與成本；AWS episodic 的 agent trajectory 也不等於員工案例 | Zep／Graphiti、AWS episodic＋reflection | 只有 C／B 實證無法保留或找回必要細節時才升級 |

#### 目前較薄的組合 C+

目前最少假設且不犧牲 M1～M11 的候選是 **C+**：

```text
durable conversation／events（可信原始來源）
        +
同一 JD scope 下多筆 rich、self-contained 的 current semantic records
        +
需要時 search／read 原始 conversation
        +
exact-scope list-all 作完整 JD 盤點
```

`C+` 不建獨立「工作案例庫」。若某個案例中的流程、例外、責任或成果會影響日後 JD 判斷，該**有意義的細節**要留在 rich current record；逐字表達與周邊脈絡仍在 conversation。只有後續代表性資料證明大量案例必須被逐件取回、比較或計數，才把個別案例提升成同 collection 的 records，或評估 D。

### 9.34 十個訪談情境壓測

| 情境 | 高品質 JD 所需效果 | C+ 的最低行為 | 何時代表 C+ 不夠 |
| --- | --- | --- | --- |
| 1. 連續出現兩個相似案例 | 不重複建立兩個 Tasks；保留第二例新增的細節 | 取回相關 current record，比較共同點／差異；只有新細節才更新 record，原始兩段話仍在 conversation | 無法找回第一個案例造成錯誤新增 Task |
| 2. 後續案例補充例外或責任邊界 | 既有理解被補強，JD 視資訊價值修訂 | update current record 而非盲目 append；保留例外條件 | 更新時覆蓋掉舊流程、成果或頻率 |
| 3. 員工提出全新工作 | 不被既有相似工作吞掉，也不一定立刻進 JD | 建立新的 current record；由 JD Skill 判斷是否穩定／重要及是否新增正式內容 | semantic search 只召回舊工作，導致新工作未進 scope inventory |
| 4. 員工明確更正 | 新說法成為 current；舊說法不污染一般分析 | replace／revise current head；conversation／revision 仍可回查 | managed default 把更正誤當另一案例或同時召回新舊 head |
| 5. 前後矛盾但未裁決 | 不選邊、不生成錯誤 JD | current knowledge 保留 unresolved 狀態並詢問；相依 JD 變更暫停 | manager 依 recency／confidence 自動刪掉其中一邊 |
| 6. 一次性特殊事件 | 保留有用例外，但不冒充 recurring Task | 具體脈絡可留 conversation；只有會界定長期職責的部分進 current record | 每個事件都永久膨脹 current records／JD |
| 7. 同類案例大量增加 | 模型仍能知道共同模式與重要差異，不需重播全部 | current rich record 持續 consolidation；必要時搜尋代表性原始案例 | 需要逐件比較／計數但 conversation search 無法可靠完成，才升級 case collection／episode |
| 8. 原有理解需要合併或拆分 | 理解可重組，穩定 ID／revision 由 runtime 管理 | manager 對 current records 做 create／replace／delete；舊 revision 不進一般 recall | records 過碎、關聯丟失，無法安全判斷 merge／split |
| 9. 要證明員工工作已完整盤點 | 不能用 top-k 冒充全部 | runtime 走完 exact-scope current records；必要時對 ingestion／admission receipt 查漏 | 有工作相關 source 從未被吸收，且沒有任何可重建／查漏途徑 |
| 10. 新資訊是否需要改 JD | LLM 可判斷 no-op／修訂／新增／移除，不把案例直接發布 | Runtime 向 LLM＋JD Skill 提供目前有效 Memory 與相關或完整 JD，由 LLM 做 duplicate／overlap／new／conflict 判斷 | Memory manager 直接把 record 映射成 Task，或 LLM 改動 JD 時未取得必要 Memory／現有 JD |

情境 9 的「receipt 查漏」只表示 application 能知道哪些 source events 已完成 Memory processing，以及該次處理是否成功／no-op；它不是另一份工作理解，也不保證模型的語意抽取百分之百正確。第一版最低驗收應以代表性訪談資料確認低頻高影響工作與細節不會被錯誤 no-op。

### 9.35 LLM 如何使用 Memory 判斷與編輯實際 JD

這不是「Memory 與 JD 互相控制」的關係。Memory 是資訊能力；LLM＋職務分析 Skill 是判斷者；JD Editor Tool／Runtime 是受限執行者；員工是最終 authority。以下各節只討論模型取得 Memory 與目前 JD 後，如何避免錯誤投影與過時操作。

#### 9.35.1 不是一對一 mapping

一筆具體資訊可能：

- 只補充既有工作理解，JD 不需改；
- 與現有 Task 完全重複，JD no-op；
- 與現有 Task 重疊但提供重要新細節，應修訂；
- 與所有現有工作不同，可能新增 Task／Duty；
- 只是案例、工具、步驟或低價值細節，不應進正式 JD；
- 揭露衝突或未知，必須先詢問而不能寫 JD。

反過來，一個 JD Task 也可能由多輪敘述、多個案例與數筆 current records 綜合而成。故不應要求每筆 Memory 永久連一個 JD 欄位，也不應要求每個 JD 欄位永久攜帶全部來源。

O\*NET 2025 Emerging Tasks 流程提供最接近的職務分析證據：分析員先熟悉既有 published task list，再把新 write-in statements 判為 duplicate、overlap 或其他結果；duplicate 不再新增，overlap 但有新 nuance 可用來修訂既有 Task，多筆相似新陳述則綜合共同點與差異形成新 Task，最後仍經 Center／SME 審查。它支持「新工作理解＋目前正式內容共同進入判斷」，而非 direct projection。

#### 9.35.2 建議的概念流程（不是固定模型 call 數）

下圖中的「整理／修訂目前有效工作知識」是認知責任位置，不表示必須生成一份名為「工作理解」的文件或另建資料層。

```text
員工訊息先耐久保存
        ↓
目前 Memory＋相關 conversation＋本輪訊息＋目前 JD workspace
        ↓
形成並驗證本輪語意理解
        ├─ Memory add／update／remove／no-op
        └─ optional JD no-op／修改／新增／移除／先澄清
                            ↓
                  AI working diff，員工審核後才改 approved JD
```

這可以在一個主顧問 run 的一或多個 framework steps 完成，也可以讓非相依 Memory 整理在背景處理。2026-09-04 `MEM-Q005` 已校正時序：某項後續判斷只有在必須重新讀取新 Memory head 時才等待發布；同一 Context 與同一份已驗證理解形成的 Memory mutation 和 JD 待審變更是並列 effects，不要求 Memory 先寫入 Store，也不要求固定兩次 LLM call。詳見 [`2026-09-04-memory-persistence-and-jd-effect-reconciliation.md`](./2026-09-04-memory-persistence-and-jd-effect-reconciliation.md)。

#### 9.35.3 兩邊如何避免互相偷偷覆蓋

1. **Memory 變了不會自行操作 JD。** 下一次需要判斷時，LLM 取得更新後的 Memory 與目前 JD，再自行決定 no-op、局部比較或全域比較；任何 JD 變更仍先成為 AI working diff，經員工審核才核准。
2. **員工直接改 JD 不自動改理解。** 下一輪顧問取得 JD delta；若只是文件表達調整，保留理解；若透露新的工作事實或與目前理解衝突，透過一般訪談確認後再修訂理解。
3. **待審變更需由 Runtime 保留建立時的 JD base 與本輪 Context 身分。**這是 stale-safety metadata，不是 JD 欄位，也不要求模型填 ID／version。Memory 技術性持久化失敗本身不使候選 stale；只有重新分析後的工作理解或 JD base 實質改變時，application 才重新驗證或標示 stale。
4. **接受後不把理由塞進正式 JD。** 待審期間可顯示模型以工作理解撰寫的簡短理由；員工接受後，正式 JD 只保留成品內容。是否保留非權威 audit receipt 由 review lifecycle 決定，不得成為第二份工作真相。
5. **拒絕 JD 變更不等於否定工作事實。** 沒有員工新說明時，只撤回該 working diff；顧問可在後續自然對話中釐清拒絕是否代表文件寫法、抽象層級或工作理解有誤。

#### 9.35.4 局部分析與全域盤點

- **日常局部路徑**：本輪訊息＋近期對話＋相關 current records＋相關 JD 區塊，成本較低；適合持續訪談與局部修訂。
- **全域品質路徑**：exact-scope 列舉全部 current records＋完整目前 JD，逐項判斷 covered／partial／missing／conflict，再跨 JD 做 duplicate／overlap／boundary 檢查；只在需要完整性結論、重大重整或匯出前使用。

兩條路徑都使用同一份 current knowledge 與同一份 JD，不新增「coverage truth」或「工作理解地圖」作第二 authority。Runtime 可保留可重建 manifest 證明全量已走完，但語意判斷仍由 JD quality Skill／LLM 完成並由員工審核。

### 9.36 本輪暫定推薦與仍未決事項

#### 暫定推薦（待 Owner 檢視，不是 ADR）

1. 保留 durable conversation／events 作可信來源；
2. 採一個 trusted per-JD semantic collection 保存多筆 rich、self-contained current records；不先另建 case store、巨大 profile 或 graph；
3. 「工作案例」「目前理解」只先作 Prompt／Skill 的語意概念，不做強制 type；有長期價值的案例細節留在 current record，逐字內容按需回查 conversation；
4. 日常採 bounded retrieval＋按需 search／read；完整 JD 品質盤點採 exact-scope list-all；
5. JD 與 Memory 不做永久逐欄位 linkage；只有 pending review 使用 runtime 建立的 read-set／revision 保障 stale safety；
6. 現有 LangGraph 1.x LTS＋Postgres Store／Saver 仍是 substrate 首選候選；LangMem manager 是否接手 extraction／consolidation，要以相容性與代表性資料的簡單 spike 判斷，不因 package 名稱直接採用；
7. 若代表性資料證明 C+ 無法可靠取回大量案例、跨記錄關係或時間變化，再依失敗類型升級成 B 的明示角色 records、Google profile＋natural memories、AWS custom／episodic strategy 或 Graphiti；不得預先全部導入。

#### 仍未決定

- current record 的正式內容形狀、最大粒度與拆分規則；
- 哪些案例細節必須提升進 current record，哪些只需留 conversation；
- Memory update 採主顧問 hot path、background manager 或依賴式混合；
- unknown／conflict 使用自然語言、薄欄位或特定 record；
- LangMem 0.x 是否能通過現行 LangGraph／Postgres／provider 組合的 compatibility spike；
- pending read-set 保留到何時、是否只存 digest／revision manifest；
- 全域盤點的觸發時機與實際 token／延遲門檻。

### 9.37 本輪新增主要官方來源

- [OpenAI Responses — Conversation 與 Tools](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)
- [OpenAI — Compaction](https://developers.openai.com/api/reference/java/resources/responses/methods/compact)
- [OpenAI — 最新 model guidance](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.5)
- [Anthropic — Memory Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- [Anthropic — Managed Agents Memory](https://platform.claude.com/docs/en/managed-agents/memory)
- [Anthropic API — List memories](https://platform.claude.com/docs/en/api/http/beta/memory_stores/memories/list)
- [Anthropic — Effective Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Google — Generate memories](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories)
- [Google — Memory Profiles](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/profiles)
- [Google — Fetch memories](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/fetch-memories)
- [Google — Memory revisions](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/revisions)
- [AWS — Memory strategies](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-strategies.html)
- [AWS — Episodic memory strategy](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/episodic-memory-strategy.html)
- [AWS — List memory records](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-list-memory-records.html)
- [LangChain — Memory overview](https://docs.langchain.com/oss/python/concepts/memory)
- [LangGraph — Persistence／Store](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangMem — Extract semantic memories](https://langchain-ai.github.io/langmem/guides/extract_semantic_memories/)
- [LangMem — Memory manager API](https://langchain-ai.github.io/langmem/reference/memory/)
- [Zep／Graphiti — Episodes](https://help.getzep.com/episodes)
- [Zep／Graphiti — How graph creation works](https://help.getzep.com/how-graph-creation-works)
- [O\*NET — Identification of Emerging Tasks: A Revised Approach (2025)](https://www.onetcenter.org/dl_files/EmergingTasks_RevisedApproach.pdf)
- [AWS — Episodic Memory strategy](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/episodic-memory-strategy.html)
- [AWS — AgentCore pricing](https://aws.amazon.com/bedrock/agentcore/pricing/)
- [LangChain — LangGraph Store：listing、pagination、namespace 與 persistent backends](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangChain — LangGraph release policy：1.0 LTS](https://docs.langchain.com/oss/python/release-policy)
- [LangMem — custom semantic Memory schema／triple](https://langchain-ai.github.io/langmem/guides/extract_semantic_memories/)
- [PyPI — LangMem release history](https://pypi.org/project/langmem/)
- [Graphiti — temporal context graph overview](https://help.getzep.com/graphiti/getting-started/overview)
- [Graphiti — current release history](https://github.com/getzep/graphiti/releases)

### 9.38 Memory 目前決策表（2026-08-31 收斂版）

本表只整理既有研究，不新增架構。若前文個別句子與本表衝突，先依本表辨識其狀態，再回到原始來源與 Owner 討論；不得把暫定候選寫成正式決策。

#### 已確認的產品效果與責任邊界

| 項目 | 目前確認內容 |
| --- | --- |
| 唯一成果 | 產品目的是產出高品質、由員工核准的 JD；Memory、工作案例與工作理解都不是產品成果 |
| Memory 責任 | 保存、修訂、搜尋與取回 LLM 判斷所需的員工工作資訊；保留必要細節、更正、未知與未解衝突 |
| LLM 責任 | 在職務分析 Skill 約束下，使用 Memory＋目前 JD 判斷 no-op、追問、修改、新增或移除，並撰寫候選變更 |
| Tool／Runtime 責任 | 提供可信 scope、Context、搜尋／讀取與受限 JD 操作，驗證結構、版本與執行結果；不替 LLM 作職務判斷 |
| 員工責任 | 接受、拒絕或編輯 AI 變更；只有核准後才成為正式 JD |
| 原始資訊 | 長期訪談／來源必須可持久保存並按需回查，但不要求每輪全量注入 Context |
| 長期記憶效果 | 必須能持續修訂目前有效資訊，且不能因整理而不可逆丟失會影響 JD 的工作細節 |
| 召回效果 | 日常應取得有界且相關的資訊；完整性判斷時必須能讓 LLM 處理 scope 內全部會影響 JD 的有效資訊，不能用 top-k 冒充全量 |
| 隔離 | 每位員工／JD 的 Memory scope 彼此隔離；目前沒有跨 JD 共用工作記憶需求 |

#### 暫定候選，尚未核准

| 候選 | 暫定理由 | 尚未成為決策的原因 |
| --- | --- | --- |
| C+：durable conversation＋rich current semantic records＋按需來源回查＋全量盤點 | 在細節、修訂、日常成本與完整盤點間較平衡，不需預先建立案例庫或 graph | 尚未決定 record 形狀、粒度、更新規則，也尚未以代表性訪談驗證 |
| 一個 per-JD semantic collection | 可使用成熟 collection／Store primitive，同時支援 search 與 listing | 單一 profile、profile＋collection 或其他成熟表徵仍未被正式淘汰 |
| LangGraph 1.x LTS＋Postgres Store／Saver 作 substrate | 已有 durable runtime、namespace、listing、search 與本機 Postgres backend | 尚未完成正式方案核准；LangMem manager、provider managed Memory 等仍是候選 |
| 日常 bounded recall＋必要時模型按需 search／read | 接近 OpenAI／Anthropic 的 just-in-time context 方向，可控制長訪談成本 | 自動召回量、工具使用時機與漏召回保護尚未定案 |

#### 尚未決定，後續只討論這些問題

1. Memory 的正式物理表徵：單一 profile、多筆 rich records、混合表徵或其他成熟方案；
2. current record 的內容形狀、粒度、合併／拆分規則，以及案例細節何時值得進入整理後 Memory；
3. Memory 更新採主顧問同一 run、背景 manager 或依賴式混合，以及何時 create／update／delete／no-op；
4. unknown／conflict 如何表示，既不逼模型選邊，也不增加不必要 schema；
5. LangMem 是否接手 extraction／consolidation，或只使用 LangGraph Store／Tool primitive；
6. 日常自動召回、模型按需搜尋與全量盤點的觸發條件、token／延遲門檻及最小驗證。

#### 已排除或已被最新討論推翻

- Memory 自行判斷、觸發、撰寫或核准 JD；
- 每個工作案例必須成為一筆獨立資料；
- 必須建立一份名為「工作理解」的中間文件或獨立 store；
- 「工作案例 → 工作理解 → JD」等於固定三層 storage、三個 stage 或三次模型呼叫；
- 每筆 Memory 永久對應某個 Task／Duty／OPKS／JD 欄位；
- 第一版預設導入 graph、獨立 episodic engine 或跨 JD Memory；
- 只靠 semantic top-k、最近 N 筆或模型自行宣稱完成，證明 JD 已完整盤點。

### 9.39 第二層比較：共同 primitive 相同，實際表徵與讀取路徑不同

本節依 Owner 指示，把 OpenAI 與 Anthropic 放在主軸，並用 Google、AWS、LangChain／LangMem 的最新官方公開機制交叉核對。目的不是選供應商，也不是把 coding-agent 的檔案名稱照搬進 Caliburn；本節只回答：M2／M3／M5／M6／M7／M9 尚未完全由共同基線承接時，成熟產品實際上如何組合資料粒度、導覽、詳細讀取與完整列舉。

#### 9.39.1 各家目前公開的第二層做法

| 來源 | 主要整理後表徵 | 平常如何讀 | 完整或深入時如何讀 | 對本輪能成立的結論 |
| --- | --- | --- | --- | --- |
| [OpenAI Agents SDK Sandbox Memory](https://openai.github.io/openai-agents-python/sandbox/memory/) | `memory_summary.md`＋可搜尋 `MEMORY.md`＋逐次 rollout summaries／raw extracts；conversation session 另存 | 每次 run 先注入小型 summary；相關時才搜尋 index | 需要細節才開 rollout summary；兩階段 extraction／consolidation 可再回看 conversation summary | 直接證明「小型導覽＋可搜尋整理知識＋按需深入」是 OpenAI 已出貨的 developer pattern；但功能仍為 Beta、偏 prior-run lessons，且預設 raw-memory 上限會按新舊淘汰，不能直接當成 Caliburn 的完整性政策 |
| [Anthropic Managed Agents Memory](https://platform.claude.com/docs/en/managed-agents/memory)／[Memory Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool) | path-addressed text documents；官方建議 many small focused files；每次 mutation 有 immutable version | store description／mount 提醒 agent 何處查；agent just-in-time list／read／search | 可讀指定文件、列舉路徑與版本；應用可控制 read-only／read-write、OCC 與 recovery | 支持「聚焦且自足的多文件」而非巨大 profile；不要求額外 current profile，也不替應用定義哪些工作細節必須保存 |
| [Google Memory Bank natural memories](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories)＋[profiles](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/profiles) | 同 scope 下自然語言 memories；可另加 application-defined structured profile | profile 可低延遲取得 current view；natural memories 可 similarity retrieval | [exact-scope retrieve](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/fetch-memories) 可不帶 similarity 逐頁取得全部 memories | 支持「current overview＋細粒度 memories」的混合，但 profile 與 memories 都可能被 managed consolidation 更新；若兩者同時作權威，應用必須處理一致性 |
| [AWS AgentCore Memory](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-strategies.html) | semantic、summary、preference、episodic 或 custom records；同一 Memory resource 可組合策略 | 依 strategy／namespace 取得所需 records | semantic listing 與其他策略可分開處理；custom strategy 可自訂 schema／consolidation | 支持多粒度、多策略組合；但每種 strategy 有自己的 output schema，built-in consolidation 也不能自動冒充 Caliburn 的衝突與完整性政策 |
| [LangChain Memory](https://docs.langchain.com/oss/python/concepts/memory)／[LangMem](https://langchain-ai.github.io/langmem/guides/extract_semantic_memories/) | 單一 profile 或持續更新的 document collection；Store value 可為 JSON／Pydantic schema | Store semantic search／filter；profile 可一次取得全貌 | collection 可列舉並由 manager insert／update／delete；完整 Context 仍由 application 組裝 | 官方明示：profile 變大後更新容易出錯；collection 通常較不易丟資訊、recall 較高，但跨記錄關係與全貌較弱。因此成熟框架提供選項，沒有一個預設形狀能自動滿足所有 domain |

#### 9.39.2 對尚未完整覆蓋能力的比較

| 物理方案 | M2 細節 | M3 廣度 | M5 未解衝突 | M6 關係脈絡 | M7 案例／穩定工作 | M9 全量盤點 | 主要代價 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 單一大型 profile | 中；容易被壓縮或局部覆寫 | 中；全貌直觀但成長後更新脆弱 | 可用欄位表示，但大型 patch 容易誤改鄰近內容 | 同文件內較好 | 容易把案例與抽象理解混在一起 | 強；單次可讀完，但只限仍能放進 Context 的規模 | 更新風險與 token 隨內容線性成長 |
| 純 collection／focused records | 強；可保留多筆自足細節 | 強；可持續擴充 | 可讓兩筆未解內容並存 | 中；records 過碎時容易成 fact bag | 強；可保留不同粒度，但合併／拆分需 manager 判斷 | 強，前提是底層能 exact-scope list-all＋走完分頁 | 日常需要 search／ranking；缺少快速全貌 |
| 小型導覽＋focused records／documents | 強；詳細內容留在 records，不塞進導覽 | 強；導覽只提供入口，全量仍靠 inventory | 強，前提是導覽不自行消解衝突、詳細 records 可承載 unresolved | 強；導覽可指出相關 records，record 本身保存 bounded context | 強；案例可留 source 或 record，穩定理解可持續 consolidation | 強；完整盤點必須繞過導覽，直接列舉全部 current records | 多一份可重建 projection；若誤當第二 authority 會產生漂移 |
| structured profile＋natural memories | 強 | 強 | 中；需定義 profile 與 memories 遇到未解衝突時誰代表 current | 強 | 強 | 強 | 同時維護兩種持久表徵，權威與同步成本較高 |
| episode／temporal graph | 最強 | 強 | 最強 | 最強 | 最強 | 強 | ingestion、entity resolution、時間／圖治理、成本與錯誤面最高 |

#### 9.39.3 研究判斷：目前最值得進下一輪的不是第二份 profile，而是可重建導覽

目前證據使原 C+ 候選得到一項重要補強，但**仍不是正式決策**：

```text
durable conversation／source
        +
同一 per-JD scope 的 focused、rich、current semantic records／documents
        +
由 current records 可重建的小型導覽／索引（不是第二 authority）
        +
日常 bounded retrieval＋模型按需 search／read
        +
需要完整 JD 盤點時直接 exact-scope list-all，不經 summary 或 top-k
```

這個形狀綜合了 OpenAI 的 progressive disclosure、Anthropic 的 many small focused files、Google 的 similarity／all-scope 雙路徑，以及 LangChain 對 profile／collection 取捨的明示警告。它沒有把 OpenAI 的 coding／sandbox 檔名、Google profile schema 或 AWS strategy 名稱搬進產品，也沒有新增第二份「工作理解真相」。小型導覽若存在，只能從 current records 重建；遺失、過時或與 records 不一致時，以 records 為準。

這項補強的目的只有兩個：

1. 日常 run 不必先用 semantic search 猜完所有工作範圍，模型先取得小型全貌與可深入的入口；
2. 詳細內容不因為導覽要短而被永久壓縮，M2／M3 仍由 rich records＋source fallback 承接。

它仍不能單獨解決：哪些職務細節值得 admission、未解衝突的 domain 語意、案例何時應更新既有理解，以及 JD 是否完整。這些仍屬職務分析指令／Skill 與 LLM 判斷；M9 則由 runtime 的 deterministic inventory 保證，不由導覽宣稱。

#### 9.39.4 Owner 已確認的下一輪主候選

Owner 於 2026-08-31 同意以「小型可重建導覽＋focused rich records」取代原本較純的 C+，作下一輪唯一主候選。這是**可由後續證據翻案的研究核准**，不是 ADR，也未授權實作。下一輪只深入下列問題：

1. 導覽是每次依 records 即時計算、Memory manager 維護的衍生檔，或先不持久化；
2. focused record 的語意粒度與最低內容要求；這不能照抄 OpenAI rollout、Google atomic fact 或 LangMem triple；
3. Memory update／consolidation 的 hot path、background 或 dependency-aware hybrid；
4. 使用成熟 manager 時，如何關閉／覆寫按 recency 遺忘、過度摘要與自動選邊衝突等不符合 M2／M3／M5 的預設；
5. Memory Prompt、Tool、Context 與 typed failure contract 應如何分工，避免再次讓模型填 system-owned 欄位或巨大 schema。

### 9.40 主候選深挖：更新、Prompt、Tool、Context 與失敗契約

本節是 §9.39 主候選的第一輪實作細節研究，仍屬可翻案方案，不是施工規格。研究優先核對 OpenAI／Anthropic 的公開實際做法，再以 Google、AWS、LangChain／LangMem 檢查是否為單一供應商特例。

#### 9.40.1 focused rich record 的最低語意，不先固定巨大 schema

成熟資料顯示兩個方向同時成立：

1. OpenAI Codex 的 [`MEMORY.md` consolidation Prompt](https://github.com/openai/codex/blob/main/codex-rs/memories/write/templates/memories/consolidation.md) 要求每個 block 可搜尋、可獨立重用、保有 scope／boundary、具體 trigger、decision point、failure 與 uncertain outcome；它不是 atomic fact dump。
2. Anthropic 建議 [many small focused files](https://platform.claude.com/docs/en/managed-agents/memory)，LangMem 也要求每筆內容在單獨取回時仍 sufficiently informative；AWS built-in semantic schema 則只保證 standalone fact，證明「managed default 能存資料」不等於已保留職務脈絡。

因此第一輪只要求一筆 record 表達**一個可獨立取回與修訂的連貫工作主題**，而不是一則訊息、一個句子或一個 JD 欄位。語意內容至少要能保留已知時的行動、對象、目的／成果、條件／情境、頻率／例外、協作與責任邊界；不知道的部分保持不知道，不為湊欄位而猜。

暫不要求模型填下列欄位：record ID、scope、namespace、revision、version、timestamp、source event ID、embedding、TTL、處理狀態或 Skill ID。這些由 runtime／storage 產生或已知；模型只產生語意內容與有限 mutation intent。這符合跨家共同責任分配，也避免再次建立巨大 strict schema。

#### 9.40.2 導覽只作 routing projection

OpenAI 公開 Prompt 把 `memory_summary.md` 定位為 prompt-loaded、high-signal-per-token 的 routing／index layer，詳細內容留在 `MEMORY.md`、skills 或 rollout summaries；並要求 summary 在詳細 Memory 完成後最後更新。Anthropic 則以 store description／mount 告知 agent 到哪裡讀，並不要求另一份 profile。兩者共同支持「先看入口、再按需深入」，但不證明入口必須是第二份持久 profile。

主候選因此採下列行為契約：

1. 導覽只列出目前有哪些工作主題、短描述與可搜尋關鍵詞／record reference；
2. 導覽不能保存只存在於自身、records 找不到的工作事實；
3. 導覽綁定產生時的 record revision manifest，可隨時從 current records 重建；
4. record 更新成功後才更新導覽；導覽重建失敗不回滾已正確發布的 records，但下次讀取應偵測版本落後並繞過／重建；
5. M9 全量盤點直接列舉 current records，永遠不以導覽覆蓋率作完成證明。

目前不必先決定導覽是單一 Markdown、JSON projection 或每次即時計算；這是下一輪框架／成本比較，而不是 Memory 語意決策。

#### 9.40.3 更新時機採 dependency-aware hybrid，而非每回合固定同步或固定背景

官方做法本來就混合兩種時機：

- OpenAI Agents SDK Sandbox Memory 在 session／run 累積後做兩階段 extraction／consolidation，另允許讀取時 live update stale Memory；
- Anthropic agent 可在工作中局部寫 Memory，研究預覽的 [Dreams](https://platform.claude.com/docs/en/managed-agents/dreams) 則以背景 job 從 store＋transcripts 產生另一個重整後 store供檢視；
- Google 明示 production 通常把 [`GenerateMemories` 背景執行](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories)，也提供 `IngestEvents` 解耦 ingestion；
- AWS 將長期 Memory extraction／consolidation 定位為 `CreateEvent` 後的背景非同步流程；
- LangChain 將 hot path 與 background 都列為正式策略，前者能立即使用但增加延遲與多任務負擔，後者降低主流程延遲但會有新 Memory 尚未可見的窗口。

主候選的時序原則因此是：

```text
來源訊息：先耐久保存
        ↓
同一 Context／理解可形成 Memory mutation 與 optional JD 待審變更
        ├─ 真正要重新讀取新 Memory head 的下一步：等待發布
        └─ sibling effect／去重／重整／導覽更新：各自驗證或背景處理
```

這裡的 hot／background 是實際 read dependency，不是「某一類資料永遠同步」。員工明確更正或本輪新資訊可以直接進入同一 run 的已驗證暫時理解；若後續步驟必須從 Store 重新讀取 new head 才能計算，就等待發布。由同一份理解形成的 JD 待審變更不因 Memory 技術性持久化失敗而丟棄；普通整理與導覽重建也不應阻塞員工每一則訊息。

#### 9.40.4 Memory Prompt 應定義語意政策，不承擔系統欄位

跨家都保留 domain instruction seam：OpenAI `extra_prompt`、Anthropic agent／store instructions、Google custom topics＋few-shot、AWS built-in override／custom strategy、LangMem instructions＋schema。故 Caliburn 真正需要提供的是職務資訊保存政策，而不是重寫 storage engine。

第一輪 Memory Prompt 只需約束下列判斷：

1. 保存所有可能改變 JD 判斷的實際工作資訊，包含低頻但高影響的例外、責任邊界與成果標準；
2. 新資訊與既有 record 是新增主題、補充、明確更正、不同案例、未解衝突或 no-op；
3. 更新時保留仍成立的原內容，不因加入一項細節重寫掉其他細節；
4. 資訊不足或指涉不明時不猜；必要時 no-op／保留 unresolved，交由一般顧問對話釐清；
5. 不把一次案例自動一般化成長期工作，也不在 Memory 層產生 Duty／Task／OPKS；
6. 空 mutation 是合法結果。

少量 few-shot 應優先覆蓋高風險邊界：低頻高影響資訊、補充既有工作、明確更正、兩個相似案例、尚未裁決的矛盾與完全無新資訊。Google 官方也明確建議 custom topics 搭配 few-shot；這比增加大量 optional 欄位更直接約束語意。

#### 9.40.5 Tool 應薄、可組合，完整盤點由 runtime 控制

成熟工具契約支持把模型操作縮成少數能力：OpenAI Agents SDK 會從 Python type／Pydantic 產生 strict schema並驗證輸出；Anthropic 提供受訓練的 Memory Tool schema，並把 client tool 定位為「模型提出結構化請求、application 執行、結果回到模型」；LangMem manager 以平行 tool calls 產生 insert／update／delete，而 Store manager 承接搜尋與持久化。

主候選只需要下列概念工具，不代表最後一定拆成四個公開 tool：

| 能力 | 模型可提供 | runtime／framework 必須提供 |
| --- | --- | --- |
| `search_memory` | 自然語言 query | per-JD scope、ranking、limit、結果 reference |
| `read_memory` | 已取得的 record reference | current revision、完整內容、not-found／stale 錯誤 |
| `manage_memory` | add／revise／remove／no-op intent、語意內容、既有候選 reference | ID、scope、revision、OCC、實際 mutation 與 audit result |
| `inventory_memory` | 不讓模型自行宣稱完成 | runtime exact-scope pagination、stable manifest、逐批處理帳 |

`inventory_memory` 可完全是內部 framework step，不必放進每輪 tools array。模型也不應填 canonical ID；它只能引用本輪 Context／Tool result 已提供的短期 reference，runtime 再映射到真實 record。

#### 9.40.6 Context 組裝採 progressive disclosure

日常訪談的最小組合暫定為：

1. 穩定的顧問規則與本輪需要的 Skill；
2. 本輪員工訊息與足以解析指涉的近期 conversation；
3. 小型 Memory 導覽；
4. runtime 自動召回的少量相關 current records；
5. 模型需要時再 `search_memory`／`read_memory`；
6. 只有查錯、更正指涉或需要原句時才回查 durable source。

OpenAI Codex 的公開 read path 也採 summary → `MEMORY.md` → 1～2 份詳細資料，並設置小型 lookup budget；Anthropic Memory Tool 主張 just-in-time retrieval。這支持「導覽＋自動少量召回＋按需深入」，但 Caliburn 不照抄 OpenAI 的固定步數或 coding 關鍵字搜尋。

完整 JD 品質盤點是另一條路徑：runtime 以 exact-scope inventory 逐批提供所有 current records 與目前 JD，保留 deterministic manifest，直到全部處理完成；不能把日常 Context 變大來冒充完整盤點。

#### 9.40.7 typed failure contract：錯誤可修正，但不讓模型猜成功

OpenAI Agents SDK 支援 strict tool input／output、schema validation，以及把可恢復的 tool error 回傳模型繼續 run；Anthropic 要求每個 `tool_use` 對應 `tool_result`，執行錯誤用 `is_error: true` 回傳；LangGraph `ToolNode` 也提供 tool execution 與 error handling。這些成熟 primitive 足以承接失敗回路，不需用自由文字解析成功與否。

第一輪只保留五類結果：

| 結果 | 意義 | 模型下一步 |
| --- | --- | --- |
| `ok` | mutation／read 已完成；回傳 runtime 產生的 current reference／revision | 繼續 |
| `no_change` | 合法 no-op，資料已涵蓋或沒有可保存內容 | 不重試 |
| `invalid_input` | 不符合小型 wire contract、內容空白或操作不合法 | 依欄位錯誤修正一次 |
| `not_found_or_stale` | 引用不存在或 revision 已變 | 重新 read／search，不得猜 ID |
| `retryable_failure` | transient storage／provider failure，尚未發布 | 由 runtime 有界重試；依賴它的後續判斷暫停 |

錯誤結果應包含 machine-readable code、簡短的人類可讀訊息，以及必要時的 allowed operations／fresh references；不得傾倒 stack trace、要求模型填系統欄位或把失敗偽裝成成功。修正次數有界，仍失敗時保留已耐久化 source，讓後續重試／恢復，不產生依賴未發布 Memory 的 JD 變更。

#### 9.40.8 本輪成本與複雜度判斷

這個方案的新增成本主要是一次 Memory extraction／consolidation 與少量 search/read；小型導覽降低每輪 Context，完整 inventory 又只在全域品質檢查使用。它沒有要求多 agent、graph、每輪全 transcript、每輪全 Memory 或每回合完整 JD audit。

目前仍不應宣稱成本一定低於所有替代方案；真正需要後續小型 spike 量測的是：

- 每輪自動召回與 guide 的 token；
- hot mutation 造成的額外 latency；
- background consolidation 的模型成本與完成延遲；
- records 成長後 search precision 與 exact-scope audit 批次數；
- 導覽是否實際減少 search tool calls，而沒有造成漏查。

本輪尚未選擇 OpenAI Sandbox Memory、Anthropic Managed Agents、Google Memory Bank、AWS AgentCore 或 LangMem 作正式 backend；其公開做法只用來確立行為契約。框架選擇必須以本機、PostgreSQL、provider-neutral、完整列舉、版本一致性與上述五個高風險行為共同判斷。

### 9.41 框架正式比較：不能以單一 Memory 元件代替整套產品判斷

本節承接 §9.39～§9.40，第一次把「哪個 Memory 元件功能最多」與「哪一組 framework 能可靠承接 Caliburn 全流程」分開比較。這仍是 **Working Research 的推薦**，不是 ADR，也未授權施工。比較不因現行程式已使用 LangGraph 而加分；現行相依套件只列為遷移事實。

#### 9.41.1 先修正兩個容易誤判的結論

1. **Pydantic AI Harness Memory 已不是簡單範例。**截至 2026-08-31，官方 Memory 已提供 Markdown notebook、bounded injection、按需 read／search、application-resolved namespace、PostgreSQL backend、compare-and-swap（CAS）與 operation idempotency。這些能力在單一 Memory 元件上，確實比 LangGraph `BaseStore.put` 的一般 upsert 更完整。
2. **單一元件較完整，不等於整套 runtime 較適合。**Caliburn 還需要長訪談保存、PostgreSQL、模型可替換、完整盤點、員工審核、跨關閉恢復、typed failure 與低成本 Context。Pydantic AI Core V2 已穩定，但 Harness 仍為 0.x；其 Conversation Search 依賴 Step Persistence，而官方明示本版 Step Persistence 尚未提供 PostgreSQL backend；Harness Memory 的 DBOS tool calls 也不會自動成為 durable steps。若選這組，仍需額外 durable engine、Postgres StepStore 或其他 conversation persistence，以及 Memory tool durable wrapper。

相反地，LangGraph 1.x 的 Store 不內建 domain Memory manager、CAS 或 immutable current-head revision；但它在同一套 LTS runtime 內已直接提供 PostgreSQL checkpointer／Store、thread resume、interrupt、fault tolerance、semantic search 與 exact listing。故本節必須比較**整套產品效果**，不能用「目前已裝哪個」或「哪個元件功能表較長」裁決。

#### 9.41.2 不可妥協的框架硬門檻

| 硬門檻 | 原因 |
| --- | --- |
| 本機、自架、PostgreSQL | 現行產品邊界；不能為 Memory 強迫導入雲端 control plane 或第二個預設基礎服務 |
| Provider／model 可替換 | 主顧問與專項工作日後可換模型、參數或 provider；Memory 不得綁死某一家模型 API |
| Durable conversation／resume | 員工可以關閉後再回來，長訪談不能依賴單一 process 或 browser connection |
| Durable human review | AI 寫入待審工作區；員工可接受、編輯後接受或拒絕，未處理內容可跨關閉保留 |
| Bounded recall＋按需深入 | 多輪訪談不能每回合塞入全部 conversation、Memory 與 JD |
| Exact-scope inventory | 全域 JD 品質盤點必須能列舉全部 current Memory；semantic top-k 不合格 |
| Stale／重放保護 | 長時間待審、重試或重放不能靜默覆蓋新版本或重複套用副作用 |
| Typed tool／failure contract | 模型只填語意參數；scope、ID、version 與 retry policy 由 runtime 管理 |
| 可維護的正式版本政策 | 第一版不能把核心 authority 建在停止維護或高頻破壞 API 的套件上 |

#### 9.41.3 最終候選矩陣

符號：`✓` 代表官方目前直接承接；`△` 代表可承接但需額外 framework／adapter／產品 policy；`✗` 代表與目前產品硬邊界衝突。

| 候選 | 本機＋Postgres | Provider-neutral | conversation／resume | 員工審核 | Memory search／全量 | 版本／冪等 | 成熟度 | 整體判斷 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| **LangChain 1.x＋LangGraph 1.x LTS＋Postgres Saver／Store** | ✓ 同套官方 backend | ✓，含 OpenRouter partner integration | ✓ checkpoint、thread、interrupt、fault tolerance | ✓ interrupt；LangChain HITL 已有 approve／edit／reject | ✓ semantic search；`query=None` listing＋offset，但 application 必須走完 | △ checkpoint／task replay 成熟；Store item CAS 需薄 adapter 或以 serial authority boundary 保護 | **高**；LangGraph 1.0 是 ACTIVE LTS | **整套 runtime 覆蓋最完整，暫定首選** |
| **Pydantic AI V2＋Harness Memory＋durable engine** | △ Memory 有 Postgres；Step Persistence 本版沒有 Postgres | ✓，官方支援 OpenRouter | △ Core 有 message history，durability 要接 Temporal／DBOS／Prefect／Restate；Postgres conversation store 仍需補 | ✓ Deferred Tools／Guardrail 可 approve／deny／override args | △ notebook read/search 很好，但內建僅 literal search；`list_paths` 有 limit，官方未文件化 cursor／offset 完整遍歷 | ✓ Memory Store 原生 CAS＋idempotency | Core V2 高；**Harness 0.x／PyPI Alpha、API 高速變動** | **單一 Memory 元件最強，但整套產品仍有三個接縫；正式第二名** |
| **LangGraph＋LangMem manager** | ✓ | ✓ | ✓ | ✓ | ✓，繼承 Store | △ manager 有 insert／update／delete，未提供完整 OCC contract | **低至中**；LangMem 最新仍為 0.0.30（2025-10） | manager 思路可參考；不應成為第一版 authority 基礎 |
| **Deep Agents＋LangGraph** | ✓ | ✓ | ✓ | ✓，繼承 LangGraph | △ file workspace／Store；同檔 concurrent write 為 last-write-wins | △ | **低至中**；官方仍 pre-1.0 | 偏 coding-agent workspace，增加不必要 agentic 層；不選 |
| **OpenAI Agents SDK＋Sandbox Memory** | △ Memory 依 sandbox workspace／snapshot | △ SDK 可擴充模型，但 Memory 與 hosted能力偏 OpenAI | ✓ Session／RunState | ✓ approval interruption | △ progressive disclosure 很好；預設 raw memories 會依 recency 上限淘汰 | △ | Memory／Sandbox 為 Beta | 作法可學習；不能承擔 Caliburn 完整性與 provider-neutral hard gate |
| **Anthropic Managed Agents Memory** | ✗ 雲端 managed service | ✗ | ✓ managed session | ✓ agent tool approval pattern | ✓ path list／read、cursor、versions | ✓ immutable versions＋OCC | Beta | Memory 文件模型成熟，但 provider／service lock-in 不符產品邊界 |
| **Google Memory Bank** | ✗ 雲端 managed service | ✗ | ✓ platform session | △ 需另接 agent runtime | ✓ similarity retrieval＋exact-scope pager | ✓ revisions／managed consolidation | 部分能力 GA、部分仍分版本 | managed Memory 覆蓋廣，但 provider lock-in、成本與 domain policy 不透明 |
| **AWS AgentCore Memory** | ✗ 雲端 managed service | ✗ | ✓ raw events／runtime | △ 需另接 agent runtime | ✓ retrieval＋namespace listing | △ 依 strategy／service | GA | 可組合 strategy 最多，但雲端鎖定且不是本機 current 產品 |

#### 9.41.4 M1～M11 的實際覆蓋比較

| 能力 | LangGraph 主候選 | Pydantic AI＋Harness 挑戰者 | 仍屬產品／職務領域責任 |
| --- | --- | --- | --- |
| M1 長期連續性 | Postgres checkpointer＋Store | message history＋durable engine＋Memory；Postgres StepStore 要補 | retention／admission policy |
| M2 細節保真 | rich JSON documents；內容形狀由 application 定義 | focused Markdown files、bounded read | 哪些職務細節不可丟、不可過度摘要 |
| M3 廣度完整性 | namespace exact listing＋pagination | bounded `list_paths`，完整 pagination 未文件化 | admission 與全量盤點 manifest |
| M4 可修訂 current understanding | Store CRUD；current revision policy 要補 | 原生 CAS／idempotent file edit | add／supplement／correction／different-case／conflict 語意 |
| M5 未知／衝突不壓平 | 可保存任意 JSON／text | 可保存任意文件 | conflict policy；兩者都不會自動懂職務真相 |
| M6 關係脈絡 | rich records＋filter／semantic search | focused documents＋literal search | 工作脈絡與抽象層級的 Prompt／Skill |
| M7 案例與穩定工作雙層可用 | checkpoint conversation＋Store records | Step Persistence／Conversation Search＋Memory notebook | 何時只留 source、何時更新 current Memory |
| M8 有界相關召回 | semantic search、filter、limit | bounded injection＋read／literal search；semantic backend 要自訂 | 自動召回量與 JIT 使用 policy |
| M9 可驗證完整盤點 | **直接具備 listing／offset primitive** | **目前缺少文件化完整遍歷契約** | runtime 完成帳與 JD quality Skill |
| M10 原始來源回查 | checkpoint history／state history | Conversation Search 可回查 snapshot；Postgres backend 要補 | 不要求模型手填 quote／source UUID |
| M11 per-JD 隔離 | trusted thread ID＋namespace | application-resolved namespace＋conversation ID | application 驗證 identity；不能讓模型選 scope |

這張表顯示：兩組都不能自動產生「正確職務理解」，都仍需要 Caliburn 的職務分析 Prompt／Skills；差別在於 LangGraph 已用同一個成熟 runtime 接起 conversation、resume、review、search 與 inventory，而 Pydantic 的最佳功能目前分散在 Core、Harness Memory、Step Persistence 與另一個 durable engine。

#### 9.41.5 效果優先的推薦

目前正式研究推薦為：

```text
LangChain 1.x
  + LangGraph 1.x LTS
  + PostgreSQL Saver／Store
  + LangChain Structured Output／Tools／HITL
  + Caliburn 職務分析 Skills 與最薄 Memory domain policy
```

這不是「保留舊元件」的決定。`Work Model`、`Focus`、`Gap`、`Proposal` 等舊名稱與舊機制不構成選型條件；可由 LangGraph state、interrupt、Store、runtime projection 或直接按需計算達成同一產品效果時，就使用 framework primitive。真正不能由 generic framework 代替的只剩：

1. 哪些員工工作資訊會影響 JD、必須保留；
2. 補充、更正、不同案例、未知與未解衝突的職務語意；
3. 如何把全部工作資訊轉成不重複、完整且抽象層級正確的 JD；
4. 員工核准後才成為正式 JD 的 domain authority rule。

這些是產品方法與治理，不是因框架功能不足而復活舊架構。

#### 9.41.6 第一版不採用的組件

- **不把 LangMem 放進 authority hot path。**它的 manager API 能節省 extraction／consolidation code，但版本停在 0.0.x，且沒有補上 Store item OCC、來源保真與完整盤點；現階段收益不足以抵銷核心依賴風險。可保留為未來 isolated spike。
- **不加入 Deep Agents。**Caliburn 需要的是專業訪談與 JD workspace，不需要 coding-agent 的 filesystem／subagent 全套；它仍 pre-1.0，file Memory 的 last-write-wins 也弱於本案需求。
- **不混接 Pydantic Harness Memory 到 LangGraph。**官方沒有這組整合契約；為取得 CAS 而建立跨框架 adapter，會形成比薄版本 adapter 更難維護的 Frankenstein stack。
- **不採 provider-managed Memory 作 primary authority。**OpenAI、Anthropic、Google、AWS 的作法可作 Prompt、Context、revision 與 retrieval 參考，但目前產品的本機、PostgreSQL、模型可替換與資料邊界優先。
- **不先加入 knowledge graph、episodic engine 或 RAG。**M1～M11 第一版可由 durable conversation＋rich records＋bounded retrieval＋exact inventory 承接；沒有證據要求先增加這些成本。

#### 9.41.7 LangGraph 主候選仍必須正視的兩個缺口

1. **Store item 沒有文件化 CAS／expected-version。**`BaseStore.put(namespace, key, value)` 是一般 upsert。正式施工若允許同一 JD 同時存在多個 writer，必須以 PostgreSQL transaction、expected revision 或現有 serial authority boundary 防止 lost update；不能把 `updated_at` 當 CAS。這是很薄但必要的一致性 seam。
2. **LangGraph／LangChain 不提供 Caliburn-ready Memory manager。**Store 只保存 application-defined JSON，generic semantic-memory 指南不會知道工作分析完整性。第一版應讓主顧問在同一 run 透過小型 Memory tools 執行 add／revise／remove／no-op，runtime 管 scope／ID／revision／錯誤；不另造多 agent 或巨大 schema。等代表性訪談顯示 hot-path 負擔過高，才 spike 背景 manager。

這兩點不推翻主候選，因為其他候選即使補上其中一點，也同時增加更大的 conversation persistence、inventory、durability、provider lock-in 或版本穩定性缺口。

#### 9.41.8 Pydantic 組合何時值得翻案

若後續 Pydantic AI Harness 同時滿足下列條件，應重新比較，不得因本節推薦永久排除：

1. Harness Memory／Conversation Search／Step Persistence 進入穩定版本政策；
2. 官方 PostgreSQL StepStore 或等價 conversation persistence 出貨；
3. Memory Store 提供文件化 exact inventory pagination 與 semantic／hybrid search；
4. DBOS 或其他本機友善 durable integration 能直接包住 Memory tools 與 deferred review，不需 application 自行補 durability；
5. 代表性長訪談證明其 focused notebook 在 M2／M3／M5／M9 的效果明顯優於 LangGraph 主候選。

#### 9.41.9 主要官方來源

- [OpenAI Agents SDK — Human-in-the-loop](https://openai.github.io/openai-agents-python/human_in_the_loop/)
- [OpenAI Agents SDK — Sandbox Agent Memory](https://openai.github.io/openai-agents-python/sandbox/memory/)
- [OpenAI Agents SDK — Tools／deferred tool loading](https://openai.github.io/openai-agents-python/tools/)
- [Anthropic — Managed Agents Memory](https://platform.claude.com/docs/en/managed-agents/memory)
- [Anthropic — Memory Tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool)
- [Google — Generate memories](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories)
- [Google — Fetch memories](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/fetch-memories)
- [AWS — AgentCore Memory strategies](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory-strategies.html)
- [AWS — List memory records](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/long-term-list-memory-records.html)
- [LangGraph — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangGraph — Fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance)
- [LangChain — Human-in-the-loop middleware](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)
- [LangChain — Long-term Memory／Postgres Store](https://docs.langchain.com/oss/python/langchain/long-term-memory)
- [LangChain — ChatOpenRouter integration](https://docs.langchain.com/oss/python/integrations/chat/openrouter)
- [LangChain／LangGraph — Release policy](https://docs.langchain.com/oss/python/release-policy)
- [LangGraph — `BaseStore` reference](https://reference.langchain.com/python/langgraph.store/base/BaseStore)
- [LangMem — Memory manager](https://langchain-ai.github.io/langmem/reference/memory/)
- [PyPI — LangMem release history](https://pypi.org/project/langmem/)
- [Pydantic AI — V2 version policy](https://pydantic.dev/docs/ai/project/version-policy/)
- [Pydantic AI — Deferred Tools／HITL](https://pydantic.dev/docs/ai/tools-toolsets/deferred-tools/)
- [Pydantic AI — OpenRouter provider](https://pydantic.dev/docs/ai/models/openrouter/)
- [Pydantic AI — Durable execution](https://pydantic.dev/docs/ai/capabilities/durable_execution/overview/)
- [Pydantic AI — DBOS integration](https://pydantic.dev/docs/ai/capabilities/durable_execution/dbos/)
- [Pydantic AI Harness — Memory](https://pydantic.dev/docs/ai/harness/memory/)
- [Pydantic AI Harness — Conversation Search](https://pydantic.dev/docs/ai/harness/conversation-search/)
- [Pydantic AI Harness — Step Persistence](https://pydantic.dev/docs/ai/harness/step-persistence/)
- [Pydantic AI Harness — Version policy／capability catalog](https://pydantic.dev/docs/ai/harness/)
- [PyPI — Pydantic AI Harness 0.27.0](https://pypi.org/project/pydantic-ai-harness/0.27.0/)

### 9.42 2026-09-01 框架現況重核：第一組「長訪談生命週期」

本節承接 [`2026-09-01-framework-independent-memory-contract.md`](./2026-09-01-framework-independent-memory-contract.md) 的 12 項硬門檻，使用截至 2026-09-01 的最新官方文件重新比較候選。比較單位已由 Owner 確認為**完整顧問 runtime 組合**，不是只挑單一 Memory 元件；但能由成熟 framework primitive 完整承接的機制仍應直接使用 framework，不保留舊名稱或舊實作。

本節只完成第一組：durable conversation、關閉後續談、失敗恢復與員工審核。它不是最終框架裁決。

#### 9.42.1 先拆開兩種不同的員工互動

1. **一般 AI JD 變更**：變更留在共同 working document 中待審，但不阻止員工繼續聊天、關閉或下次續談。它是可跨關閉保存的 working state，不應一律套成 blocking interrupt／deferred approval。
2. **無法安全繼續的必要澄清**：只有遇到未解衝突、語意歧義或缺少不可替代的員工決定時，才暫停相依分析並要求員工回答。LangGraph interrupt 與 Pydantic Deferred Tool 都能承接這種互動。

這項區分防止重新引入「只要有待審變更，就鎖住聊天室直到員工處理」的錯誤產品行為。一般待審內容的接受、拒絕或編輯後接受仍是 application 的 deterministic authority command；framework HITL primitive 只提供持久暫停／恢復能力，不自行定義 Caliburn 的審核政策。

#### 9.42.2 最新官方能力比較

| 能力 | LangChain 1.x＋LangGraph 1.x | Pydantic AI V2＋Harness＋DBOS |
| --- | --- | --- |
| 長訪談、關閉後續談 | PostgreSQL checkpointer＋穩定 `thread_id` 直接保存 thread state | 可由 conversation／message history＋durable engine 完成；需把相應狀態交給 DBOS 或其他 durable integration |
| 中斷／失敗恢復 | checkpoint 保存執行位置；相同 `thread_id` 原地 resume | DBOS 從最後完成的 durable step 恢復；workflow 與有 I/O 的自訂 tool 需遵守 deterministic／step 邊界 |
| 必要澄清 | `interrupt()` 可保存 graph state、無限等待並以 `Command(resume=...)` 繼續 | Deferred Tool 可結束本次 run，外部 UI 收集回答後，以原 message history＋deferred result 開新 run；以 `conversation_id` 維持關聯 |
| 一般待審 JD 變更 | 存入 durable working state；不應全面使用 interrupt | 同樣需保存 durable working state；不能只依 deferred approval request |
| PostgreSQL 邊界 | Checkpointer／Store 都有官方 PostgreSQL backend | Harness Memory 有 PostgreSQL backend；Harness Step Persistence 本版只內建 memory／file／SQLite／Mongo，PostgreSQL 明列為 out of scope；可改由 DBOS 的 PostgreSQL system database 承接 workflow durability |
| Tool 副作用恢復 | framework 有 checkpoint replay 與 interrupt 的 idempotency 規則；副作用仍須可冪等 | `DBOSDurability` 自動包 model／MCP steps；直接註冊的 function tools 不會自動包裝，有 I/O 時需明確設為 DBOS step |

#### 9.42.3 本組暫時裁決（Owner 已確認）

- 兩組都能達到產品效果，Pydantic 組合沒有因本組失格。
- 第一組由 **LangGraph 勝出**：conversation、resume、必要澄清與 PostgreSQL durability 已落在同一套正式 runtime 與一致性邊界。這是可靠性判斷，不是以少寫 code 為主的判斷。
- Pydantic 組合需要接 Harness Memory、Deferred Tools、DBOS／其他 durable engine，並明確包裝有副作用的 tools；接縫較多，但其 Memory 元件能力仍須在下一組獨立比較。
- 修正 §9.41 的成熟度措辭：Pydantic AI Harness 雖仍使用 `0.x`、minor version 可能調整 API，但官方現行版本政策明確稱 capabilities 經端到端測試且預期用於 production。不能只用 `0.x`／PyPI classifier 將其判定為不可用；應把它視為「production-intended、API 尚未穩定」。
- 本組勝負**不是最終框架裁決**；後續仍須比較 Memory 保存／修訂／召回／全量盤點、版本一致性、typed failure、觀測性、成本及長期維護。

本組主要官方來源：

- [LangGraph — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangChain — Human-in-the-loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)
- [LangChain／LangGraph — Release policy](https://docs.langchain.com/oss/python/release-policy)
- [Pydantic AI — Deferred Tools](https://pydantic.dev/docs/ai/tools-toolsets/deferred-tools/)
- [Pydantic AI Harness — Step Persistence](https://pydantic.dev/docs/ai/harness/step-persistence/)
- [Pydantic AI — Durable Execution with DBOS](https://pydantic.dev/docs/ai/capabilities/durable_execution/dbos/)
- [Pydantic AI Harness — Memory](https://pydantic.dev/docs/ai/harness/memory/)
- [Pydantic AI Harness — Version policy](https://pydantic.dev/docs/ai/harness/)

### 9.43 2026-09-01 框架現況重核：第二組「Memory 本體」

本組只比較 [`2026-09-01-framework-independent-memory-contract.md`](./2026-09-01-framework-independent-memory-contract.md) 已確認的 Memory 效果：完整訪談來源、聚焦且可修訂的 rich Semantic Memory、小型可重建導覽、日常有界召回、可驗證全量盤點，以及 scope／version／replay 保護。它不判斷 JD 寫法，也不是最終框架裁決。

#### 9.43.1 最新官方能力比較

| 能力 | LangChain 1.x＋LangGraph 1.x | Pydantic AI V2＋Harness＋DBOS |
| --- | --- | --- |
| 完整訪談來源與回查 | PostgreSQL Checkpointer 保存 thread state；同一 PostgreSQL Store 可用獨立、受信任 namespace 保存逐字來源並提供 exact／semantic retrieval | `StepPersistence` snapshots＋`ConversationSearch` 可 BM25 回查被 compaction 移出的原文；但目前沒有內建 PostgreSQL Step Store，且每次搜尋會重讀 scope 內 snapshots，完整性取決於早期 snapshots 未被裁掉 |
| 聚焦、詳細、可修訂 Memory | Store 原生保存 namespaced JSON documents，支援 PostgreSQL、key CRUD、filter 與 optional semantic index；內容形狀與職務領域更新政策需由應用程式／Memory manager 指定 | Memory notebook 原生提供 `MEMORY.md`、聚焦 Markdown files、read／write／delete／search、PostgreSQL backend、optimistic CAS 與 operation idempotency；單看 Memory 元件完整度較高 |
| 小型可重建導覽 | 沒有固定導覽 primitive；需由 current Store items 的 metadata 建立可重建 projection | 有界注入 `MEMORY.md` excerpt 與檔名清單天然接近導覽；但 framework 不保證 `MEMORY.md` 沒有獨有事實，因此仍須把它限制為可重建 projection，而不是第二份權威 |
| 日常有界召回 | Store 支援 limit／filter 與 PostgreSQL pgvector semantic search；送入模型的 context 組裝需由 runtime 明確控制 | 預設約 2,000 token 有界注入，也可完全關閉自動注入而只保留按需 read／search；內建搜尋是 bounded lexical search，semantic ranking 需自訂 `SearchableMemoryStore` |
| Exact-scope 全量盤點 | `BaseStore.search(query=None, limit, offset)` 可逐頁列舉；namespace 是 prefix match，實作時仍須固定 exact JD namespace 或檢查回傳 item namespace | 正式 `MemoryStore.list_paths(prefix, limit)` 沒有 cursor／offset；PostgreSQL backend 也是單次 `ORDER BY path LIMIT`。它可判斷「可能還有更多」，卻無法透過正式介面取得下一頁，因此不能直接建立可驗證的全量 manifest |
| Version／stale／replay | Store item 只有 key、value、created／updated timestamp；`put` 沒有 expected-version CAS。第一版必須使用每 JD 單一 writer、穩定 operation key 與盤點期間禁止並行 mutation；否則不通過門檻 | Store contract 原生要求 expected-version CAS 與 operation idempotency；過期寫入會衝突，重放同一 operation 不會重複套用，本項明顯較完整 |
| 單一 JD 隔離 | namespace／thread id 由可信 runtime 注入；模型-facing tool 不得接受 scope | namespace resolver 從 typed dependencies 解析且不出現在 tool schema；直接符合可信 scope 要求 |

#### 9.43.2 重要限制與不能誤讀之處

1. **Pydantic Harness 的 notebook 比 LangGraph Store 更接近完成品。**這是功能與可靠性優勢，不只是少寫 code；尤其 CAS、冪等、有界注入與按需讀取都已有正式 primitive。
2. **LangGraph 的 exact pagination 是產品硬門檻優勢。**Caliburn 的完整 JD 製作／全面檢查必須證明全部 current Memory 已處理；提高 Pydantic `list_paths` 的單次 limit 只能降低漏資料機率，不能證明完整。
3. **兩者都不會自動知道哪些員工工作細節必須保存。**職務資訊 admission、衝突語意與 Memory 粒度仍屬 Caliburn 的職務分析方法；framework 負責 storage／retrieval／concurrency primitive，不能冒充領域正確性。
4. **兩者的導覽都不能直接當第二份真相。**Pydantic 已有合適的 notebook／file-listing 形狀，LangGraph 則有中立 Store；不論選誰，導覽都必須可由 current Memory 重建，全面盤點也必須直接讀 Memory。
5. **LangGraph 的 CAS 缺口不能被隱藏。**目前可接受的最薄方案是沿用單一 JD 分析期間的 serial writer、stable operation key 與 runtime manifest；若後續框架比較證明無法可靠防止 lost update／replay duplicate，必須重開本組裁決。

#### 9.43.3 本組暫時裁決（Owner 已確認）

- 若只比較現成 Memory 元件，**Pydantic AI Harness Memory 勝出**：notebook、bounded injection、on-demand tools、PostgreSQL、CAS 與冪等較完整。
- 若比較 Caliburn 的完整硬契約，**LangGraph 組合小幅勝出**：它把 PostgreSQL conversation durability、Store、semantic retrieval 與 exact pagination 放在同一 runtime；其中 exact inventory 與完整來源是不可妥協效果。
- Pydantic 組合仍保留為正式第二名；要翻案勝出，至少需有可維護的 exact inventory pagination，以及 PostgreSQL conversation persistence／search 路徑，不得用「把 limit 設很大」代替證明。
- 本組不授權自行重建完整 Memory framework。若最終選 LangGraph，應優先使用 Saver／Store／search／pagination 等成熟 primitive；只保留職務領域 policy 與其 CAS／manifest 真缺口所需的最薄邏輯。
- 本組勝負仍不是最終框架選擇；下一組比較 typed tools、bounded repair、failure contract 與觀測性。

本組主要官方來源：

- [LangGraph — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph — Long-term memory](https://docs.langchain.com/oss/python/langchain/long-term-memory)
- [LangGraph `BaseStore.search` — limit／offset](https://reference.langchain.com/python/langgraph.store/base/BaseStore/search)
- [LangGraph `BaseStore.put` — no expected-version parameter](https://reference.langchain.com/python/langgraph.store/base/BaseStore/put)
- [Pydantic AI Harness — Memory](https://pydantic.dev/docs/ai/harness/memory/)
- [Pydantic AI Harness — Conversation Search](https://pydantic.dev/docs/ai/harness/conversation-search/)
- [Pydantic AI Harness `MemoryStore` source — bounded `list_paths`](https://github.com/pydantic/pydantic-ai-harness/blob/main/pydantic_ai_harness/memory/_store.py)
- [Pydantic AI Harness `PostgresMemoryStore` source — `LIMIT` without pagination](https://github.com/pydantic/pydantic-ai-harness/blob/main/pydantic_ai_harness/memory/_postgres.py)

### 9.44 2026-09-01 框架現況重核：第三組「Typed Tools、Bounded Repair、Failure Contract 與觀測性」

本組承接 [`2026-09-01-framework-independent-memory-contract.md`](./2026-09-01-framework-independent-memory-contract.md) §7～§8：模型只產生語意內容與有限 mutation intent；scope、正式 ID、revision、timestamp、retry policy 與實際執行結果都由可信 runtime 管理。比較目標是降低錯誤率、避免無界重試並保留可診斷性，不以少寫幾行程式為主要標準。

#### 9.44.1 先確定錯誤不能全部交給模型重試

最新 OpenAI、Anthropic、Pydantic AI 與 LangGraph 官方做法共同指向「分層處理」，不是遇到任何失敗都再呼叫一次模型：

| 結果／錯誤類型 | 正式處理方式 | 是否增加模型 round trip |
| --- | --- | --- |
| 成功 | 回傳 typed success 與實際結果 | 否 |
| 合法 no-op | 明確回傳 `no_op`，不得偽裝成寫入成功 | 否 |
| Schema／參數格式錯誤 | strict schema／Pydantic validation 先攔截；把可修正欄位與錯誤原因回給模型 | 最多一次有界修正 |
| 關聯不合法／未知本輪參照 | 回傳 sanitized、machine-readable domain error 與可用本輪參照；模型不得猜正式 ID | 最多一次有界修正 |
| Stale revision／工作區已改變 | 中止原 mutation，runtime 重新讀取 current head，再由模型重新判斷；不得靜默覆蓋 | 視需要最多一次重新判斷，不是盲重試 |
| 需要員工決定 | 保存必要澄清，停止相依操作，交由「需要你的確認」 | 否；等員工回答後才是新 run |
| 網路、限流、5xx、連線重設 | transport／runtime 依 `Retry-After` 與退避政策重試 | 否，模型不應看到每次 transport attempt |
| 未知程式錯誤 | 停止 run、保留 trace／correlation ID，向 UI 回報可重試狀態 | 否；不得把 stack trace 丟給模型猜 |

這個分類不是 Caliburn 自行發明的重試引擎。Pydantic AI 官方把 transport、model fallback、tool correction、output correction 與 request hook 分成不同預算，並明示後三者才會多一次模型呼叫；LangGraph 官方也把 transient、LLM-recoverable、user-fixable 與 unexpected errors 分流。OpenAI 最新模型指南要求 tool contract 寫清楚回傳型別、錯誤行為、重試與停止條件；Anthropic 則使用 strict tool schema 與 `tool_result is_error` 讓模型取得受控錯誤，而非原始 exception。

#### 9.44.2 模型與 Runtime 的 typed boundary

模型可見 schema 第一版只包含：

1. 語意內容；
2. 操作種類；
3. 當輪已提供的穩定 local handle；
4. 操作真正需要的少量選項。

下列欄位不得要求模型產生：正式資料庫 ID、JD／員工 scope、namespace、revision、timestamp、operation key、actor、retry 次數、permission、實際 Skill receipt、source UUID、embedding 或 TTL。它們由 runtime 從 trusted run context 注入並驗證。

工具定義使用 provider-native strict schema；schema 說明放在 tool description，Prompt 不重複貼整份 schema。當輪只暴露相關工具。第一版核心 edit／Memory tool surface 不足以合理化額外的 LLM Tool Selector；只有日後工具目錄真的擴大時，才評估 provider-native tool search，避免為「選工具」額外付一次模型推理與 cache 失效成本。

#### 9.44.3 最新 framework 能力比較

| 能力 | LangChain 1.x＋LangGraph 1.x | Pydantic AI V2＋Harness＋DBOS | 本組判斷 |
| --- | --- | --- | --- |
| Typed tool／strict schema | Pydantic model／JSON Schema、provider structured output、`ToolRuntime` trusted injection | Python signature＋Pydantic validation、provider strict、自動隱藏 runtime dependencies | **Pydantic 小勝**：模型修正體驗最直接 |
| 可由模型修正的錯誤 | `ToolErrorMiddleware` 可把受控 exception 變成 `ToolMessage(status="error")`；graph loop 可重判 | `ValidationError`／`ModelRetry` 直接產生 retry prompt；`ToolFailed` 表示可供模型調整但不消耗 retry budget | **Pydantic 勝**：語意較完整 |
| 暫時性錯誤與退避 | `ToolRetryMiddleware`、`ModelRetryMiddleware`、LangGraph retry policy 可依 exception 分類、退避、jitter | transport retries 完整；DBOS step retries 可用，但 DBOS 無 selective non-retryable exception，且官方警告不可疊加 provider／Pydantic／DBOS 多層重試 | **LangChain／LangGraph 勝** |
| Durable tool side effect | completed task／checkpoint replay 已在同一 runtime；副作用仍須 idempotent | model／MCP 可由 DBOS 包裝；直接註冊 function tool 不會自動 durable，有 I/O 者需明確 `@DBOS.step` | **LangGraph 勝** |
| Run／成本上限 | model／tool call limit middleware 可按 run／thread／tool 限制 | `UsageLimits` 可限制 request、成功 tool call、input／output／total tokens 與 cost；但反覆 `ToolFailed` 主要靠 request limit 約束 | **各有優勢**；正式契約仍需總 run 預算 |
| 觀測性 | LangSmith 自動 nested traces，也可透過 OpenTelemetry 送到其他 OTLP backend | 原生 OpenTelemetry spans／metrics；可使用任意 OTLP backend，不必使用 Logfire | **Pydantic 小勝於本機中立性**；兩者都通過 |

需特別修正版本措辭：如果採用 LangChain 組合，不能只寫模糊的「1.x」。本組使用的 `ToolErrorMiddleware` 需要 `langchain>=1.3.14`，預設 retryable／non-retryable model error 分類修正需要 `langchain>=1.3.16`；正式版本下限應在施工計畫按當時 release policy 重核。

#### 9.44.4 觀測性最低契約

不論最終選哪組，OpenTelemetry 是 Caliburn 的 framework-independent observability boundary；不得要求雲端 LangSmith 或 Logfire 才能診斷本機產品。每個 run 至少可追蹤：

- run／model request／tool call／durable step 的 parent-child 關係；
- model、reasoning setting、input／output／reasoning／cached tokens；
- 預估成本、延遲、重試層級、重試原因與最後狀態；
- tool 名稱、結果分類、sanitized error code、stale／employee-confirmation 原因；
- prompt／員工原話與 tool arguments 的內容預設不進一般 log，必要診斷另走受控開關。

這裡的 trace 是開發與故障診斷，不是另一份 conversation／Memory／JD authority。

#### 9.44.5 本組暫時裁決（Owner 已確認）

- **Typed tool 與模型可修正錯誤：Pydantic AI 勝。**`ModelRetry`／`ToolFailed` 與 Pydantic validation 對這個問題提供較完整的現成語意。
- **完整 durable error routing：LangChain／LangGraph 勝。**它把 graph state、durable task、retry policy、error middleware 與 run／thread limits 放在同一 runtime；Pydantic＋DBOS 仍要明確包裝直接 function tools，且 DBOS retry 分類有正式限制。
- **觀測性兩者都合格。**Pydantic AI 的 OpenTelemetry 原生路徑更中立；LangChain 的 LangSmith UX 較完整但非必要，亦可輸出到其他 OTLP backend。
- 綜合產品硬契約，本組由 **LangChain／LangGraph 小幅勝出**；Pydantic AI 在 typed ergonomics 與 OTel-native 方面明顯值得保留為翻案依據。
- 本組不授權自建 generic retry／tracing framework。Caliburn 只需定義不可被 generic framework 推導的少量 domain error code（例如 invalid relation、stale revision、needs employee decision）與安全訊息；其餘 validation、retry、call limits、durable replay 與 tracing 優先使用 framework primitive。

#### 9.44.6 主要官方來源

- [OpenAI — GPT-5.6 model guidance](https://developers.openai.com/api/docs/guides/latest-model)
- [OpenAI — Responses API／strongly typed function tools](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)
- [Anthropic — Strict tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use)
- [Anthropic — Handle tool calls／`is_error`](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)
- [LangChain — Prebuilt middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)
- [LangChain — Tools／`ToolRuntime`](https://docs.langchain.com/oss/python/langchain/tools)
- [LangChain — Structured output](https://docs.langchain.com/oss/python/langchain/structured-output)
- [LangGraph — Thinking in LangGraph／error classification](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph)
- [LangGraph — Fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance)
- [LangSmith — Trace with OpenTelemetry／alternate providers](https://docs.langchain.com/langsmith/trace-with-opentelemetry)
- [Pydantic AI — Retries](https://pydantic.dev/docs/ai/core-concepts/retries/)
- [Pydantic AI — Advanced tools／validation、`ModelRetry`、`ToolFailed`](https://pydantic.dev/docs/ai/tools-toolsets/tools-advanced/)
- [Pydantic AI — Usage limits](https://pydantic.dev/docs/ai/core-concepts/agent/#usage-limits)
- [Pydantic AI — Durable execution with DBOS](https://pydantic.dev/docs/ai/capabilities/durable_execution/dbos/)
- [Pydantic AI — OpenTelemetry／alternative backends](https://pydantic.dev/docs/ai/integrations/logfire/)

### 9.45 2026-09-01 框架現況重核：第四組「Context、Skill／Tool 漸進揭露、快取、壓縮與成本」

本組承接 [`2026-09-01-framework-independent-memory-contract.md`](./2026-09-01-framework-independent-memory-contract.md) §3.4、§7～§10，先用 [`2026-08-30-agent-memory-landscape-and-decision-working-research.md`](./2026-08-30-agent-memory-landscape-and-decision-working-research.md) §6、F8～F9、§9、§13.10～§13.16 的跨家共同基線校正，再比較 framework。目標是讓長訪談持續取得正確 Context，同時控制成本、避免工具選錯與不可逆細節遺失；不是單純追求最少程式碼。

#### 9.45.1 先以跨家共同基線約束比較

OpenAI、Anthropic、Google、AWS 與成熟框架反覆出現的共同做法如下：

1. Active context、完整 conversation source 與 durable Semantic Memory 分層；三者互補但不能互相冒充。
2. 保存、整理、召回與 Context injection 是不同步驟；資料存在不代表每輪都要送入模型。
3. 一般回合只做 scope-first、有界召回；模型需要時再 exact lookup／search／read。
4. 小型入口／目錄／summary 只負責導覽，詳細內容按需讀取；導覽不能成為第二份真相。
5. Hot path 只承擔下一個相依判斷真正需要的更新；廣泛 consolidation、重分類與壓縮可依正確性期限背景化。
6. Context、recall、cache、compaction、成本、延遲與失敗必須可觀察。

下列內容**不是**跨家共同結論：固定的 Skill package 格式、固定 tool-search 門檻、每輪摘要、固定 Context token 數、哪種 embedding／hybrid ranking 最佳，以及 Skill 載入後是否跨使用者回合保持可見。這些只能依產品效果與 framework 實際行為決定，不能把單一供應商預設升格為 Caliburn 契約。

#### 9.45.2 正式 Context 分層

每個一般訪談回合採四層組裝：

| 層 | 內容 | 規則 |
| --- | --- | --- |
| 穩定、可快取前綴 | 產品目標、核准邊界、最小顧問規則、少量核心工具、Skill 名稱與簡介 | 保持順序與內容穩定；同一規則只寫一次 |
| 本輪動態尾端 | 員工本輪訊息、足以解析指涉的近期對話、小型 Memory 導覽、少量相關 Memory、真正需要的 JD 局部投影 | 有筆數與 token budget；不預設全量注入 |
| 按需深入 | Task／Duty／O／P／K／S Skill、更多 Memory、原始 conversation、其他 JD 區段 | 由模型透過受限 read／search／load 能力取得 |
| 全量盤點 | 全部 current Memory、stable revision、pagination 與 manifest | 只用於完整 JD 製作、重大重整與全面檢查；不能用 semantic top-k 代替 |

因此不得把完整 transcript、全部 Memory、完整 JD 或所有分析 Skill 每輪一起送入模型。超大 context window 是容量上限，不是 context selection 策略。

#### 9.45.3 Skill 與 Tool 的漸進揭露

- Task、Duty、O、P、K、S 分析方法是適合漸進揭露的獨立 Skill；初始 Context 只放名稱與清楚 description，命中需要時才載入完整方法。
- Skill 保存「如何分析」；員工資料仍在 conversation／Memory，JD 仍是受審文件。Skill 載入狀態只是執行 Context，不得成為 Semantic Memory 或業務 authority。
- 第一版核心編輯與 Memory tool surface 很小，沒有證據需要額外 LLM Tool Selector。少量高頻核心工具直接可見；只有日後工具目錄真的擴大時，才使用 provider-native Tool Search。
- Provider-native Tool Search 優先於額外 selector model call；不支援時才考慮 framework fallback。Tool discovery 不得改變工具權限、scope 或員工核准邊界。
- Pydantic AI On-Demand Capability 預設會從 message history 重建已載入能力，甚至跨 run 保持；這是 framework execution state，不是跨家共同產品語意。正式施工前仍須決定載入內容何時可從 model-facing Context 移除，不能任其在長訪談中永久累積。

#### 9.45.4 Prompt caching、compaction 與成本邊界

1. Prompt caching 使用 provider 官方能力；不自建另一套 cache store，也不能把 cache 當 correctness 或 Memory 機制。
2. 穩定內容放前、動態內容放後，觀察 provider 回報的 cache read／write tokens、總 input／output／reasoning tokens、延遲與實際成本。
3. Conversation compaction 只處理 active conversation／reasoning／舊 tool results；不能把 Semantic Memory、完整訪談來源或 JD authority 壓成不可檢查摘要。
4. 優先使用 OpenAI／Anthropic provider-native compaction；跨 provider 才採 framework fallback。便宜的 deterministic tool-result clearing 可先於 LLM summarization，但必須衡量清理造成的 cache bust。
5. 不每輪摘要。只有接近 context threshold 或明確里程碑才壓縮；LLM summarization 是額外模型 request，必須計入成本與 request limit。
6. 不以「model call 次數較少」單獨宣稱更省；以完成任務的品質、總 tokens、延遲、成本、重試與員工可理解性一起判斷。

OpenAI 最新 model guidance 建議精簡 Prompt、只暴露當前相關工具、使用 Responses API 的 prompt caching／tool search／compaction，並實際追蹤 cache 與總成本。Anthropic 的官方成本研究也把 prompt caching 列為其測試中最大的 agent-loop 成本槓桿，但同時指出 context editing 在其某次測試中反而花得比省得多；因此本組採「開啟並觀測」，不採「看到功能就全面啟用」。

#### 9.45.5 最新 framework 能力比較

| 能力 | LangChain 1.x＋LangGraph 1.x | Pydantic AI V2＋Harness＋DBOS | 本組判斷 |
| --- | --- | --- | --- |
| 整組能力按需載入 | 完整 Agent Skills 位於 Deep Agents：metadata 先行，命中後讀 `SKILL.md`，再按需讀 references／scripts／assets；需引入 Deep Agents／filesystem backend | Core `Capability` 可把 instructions、tools、settings、hooks 綁成一個 deferred bundle；所有 provider 可用 | **Pydantic 勝**：較直接符合職務分析 Skill |
| 個別工具按需載入 | `ProviderToolSearchMiddleware` 使用 OpenAI／Anthropic server-side search；其他 provider 會失敗，fallback `LLMToolSelectorMiddleware` 會多一次 model call | `ToolSearch` 在 OpenAI／Anthropic 使用原生 search，其他 provider 自動退回 local keywords／自訂 search | **Pydantic 勝**：provider fallback 較完整 |
| Skill package 完整度 | Deep Agents 可按需讀 supporting files／scripts／assets | Harness `Skills` 目前只載入 `SKILL.md` 指令；不讀或執行 bundled files，部分 Agent Skills 行為欄位只接受但不實作 | **LangChain／Deep Agents 勝**，但第一版尚無硬需求引入整套 filesystem agent |
| Context 清理與摘要 | `ContextEditingMiddleware`、`SummarizationMiddleware`、call limits 已正式提供 | Provider-native OpenAI／Anthropic compaction＋model-agnostic tiered strategies、usage reporting、cache-bust 門檻 | **Pydantic 小勝**：選項與 provider adaptive 路徑較完整 |
| Prompt cache 診斷 | 主要靠 provider usage＋OTel／LangSmith 自行觀測 | Harness 有基於 provider usage 的 cache-bust warning；但仍為 0.x capability | **Pydantic 小勝**；只列 optional observability，不列第一版 correctness 依賴 |
| 維護成熟度 | LangChain／LangGraph 版本政策較穩定；Deep Agents 是另一層正式套件 | Core 能力完整；Harness production-intended 但仍為 0.x，minor version 可能調整 API | **LangChain 勝** |

#### 9.45.6 本組暫時裁決（Owner 已確認）

- **第四組由 Pydantic AI 組合小幅勝出。**主要原因是 On-Demand Capability、provider-adaptive Tool Search、原生／跨 provider compaction 與 usage control 對本組功能形成較完整組合，不是因為少寫 code。
- 若最終選 Pydantic 組合，第一版優先使用 Core `Capability`／`ToolSearch`／provider-native compaction；Harness `Skills`／cache warning 只作可替換 leaf capability，必須鎖版本，不讓 0.x API 外溢成產品契約。
- LangChain／LangGraph 仍完全合格；若後續證明 production Skill 必須大量使用 references、scripts 或 assets，Deep Agents 的完整 Agent Skills 支援足以重開本組裁決。
- Prompt caching 屬 provider optimization，不屬 framework authority；透過 adapter 使用，並以實際 cache usage／成本判斷是否增加 explicit breakpoints 或延長 TTL。
- 第一版不採 LLM Tool Selector、不每輪做摘要、不把全部內容塞進長 context，也不把載入過的 Skill 當永久 Memory。
- 本組勝負仍不是最終框架裁決；下一步必須把四組結果與 [`2026-09-01-framework-independent-memory-contract.md`](./2026-09-01-framework-independent-memory-contract.md) 的 12 項硬門檻整體對照，避免用單項優勢掩蓋 lifecycle、exact inventory 或 durable error routing 的缺口。

#### 9.45.7 主要官方來源

- [OpenAI — GPT-5.6 model guidance](https://developers.openai.com/api/docs/guides/latest-model)
- [OpenAI — GPT-5.5 model guidance／tool search、compaction、prompt caching](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.5)
- [OpenAI — Responses API／tool search、prompt cache options、context management](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)
- [OpenAI — Compact a response](https://developers.openai.com/api/reference/java/resources/responses/methods/compact)
- [Anthropic — Tool Search](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool)
- [Anthropic — Tool use with prompt caching](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-use-with-prompt-caching)
- [Anthropic — Context editing](https://platform.claude.com/docs/en/build-with-claude/context-editing)
- [Anthropic — Optimizing for cost and intelligence](https://platform.claude.com/docs/en/about-claude/models/optimizing-for-cost-and-intelligence)
- [LangChain — Prebuilt middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)
- [LangChain Deep Agents — Skills](https://docs.langchain.com/oss/python/deepagents/skills)
- [Pydantic AI — On-Demand Capabilities](https://pydantic.dev/docs/ai/capabilities/on-demand/)
- [Pydantic AI — Tool Search／Capabilities](https://pydantic.dev/docs/ai/core-concepts/capabilities)
- [Pydantic AI Harness — Skills](https://pydantic.dev/docs/ai/harness/skills/)
- [Pydantic AI Harness — Compaction](https://pydantic.dev/docs/ai/harness/compaction/)
- [Pydantic AI — OpenAI provider-native compaction](https://pydantic.dev/docs/ai/models/openai/)

### 9.46 2026-09-01 四組整合與框架總決選（Owner 已確認）

本節的精簡、可獨立回讀版本與 2026-09-02 security／version 複核，見 [`2026-09-02-memory-framework-selection-revalidation.md`](./2026-09-02-memory-framework-selection-revalidation.md)。完整推導與歷史仍保留在本節，不以精簡版覆寫。

本節整合 §9.42～§9.45，並再次回讀下列兩份上位約束後才下結論：

1. [`2026-09-01-framework-independent-memory-contract.md`](./2026-09-01-framework-independent-memory-contract.md)：產品效果、M1～M11 與 12 項不可妥協門檻；
2. [`2026-08-30-agent-memory-landscape-and-decision-working-research.md`](./2026-08-30-agent-memory-landscape-and-decision-working-research.md)：OpenAI、Anthropic、Google、AWS 與成熟框架的 B1～B14 共同基線、差異設計、Memory 表徵、Prompt／Tool／Runtime 責任。

因此本節不是以目前程式、舊元件名稱、少寫多少 code 或單一功能表裁決。框架必須先完整承接產品契約；單項人體工學優勢只能在硬門檻都通過後作次級比較。

#### 9.46.1 四組結果

| 比較組 | 本組結果 | 對總決選的實際權重 |
| --- | --- | --- |
| 長訪談生命週期、關閉後續談、必要澄清、持久審核 | **LangGraph 勝** | 高；屬正確性與 durable authority 硬門檻 |
| Semantic Memory 本體、CAS、bounded notebook | Pydantic 單一元件勝；完整產品契約由 **LangGraph 小幅勝** | 高；必須同時看 exact inventory、conversation 與 Postgres runtime |
| Typed Tool、bounded repair、failure routing、觀測性 | Pydantic typed ergonomics 勝；完整 durable error routing 由 **LangGraph 小幅勝** | 高；不能以方便重試換取副作用或狀態不一致 |
| Context、Skill／Tool 漸進揭露、cache、compaction、成本 | **Pydantic 小幅勝** | 中；兩組都合格，且部分能力屬 provider optimization |

四組不是一人一票。長訪談持久性、完整盤點、員工審核、版本／重放與 durable error routing 是產品不能失敗的骨架；Context 與 Capability 人體工學可以在骨架合格後再優化。依此權重，Pydantic AI 在數個 leaf capability 上較佳，仍不足以抵銷其完整組合需要跨 Harness、DBOS／其他 durable engine、conversation persistence 與 inventory adapter 的接縫。

#### 9.46.2 Owner 核准的總決選

目前正式研究選擇為：

```text
LangChain 1.0 LTS（採相容的 1.x minor）
  + LangGraph 1.0 LTS（採相容的 1.x minor）
  + 官方 PostgreSQL Checkpointer／Store
  + LangChain stable Tools／Structured Output／Middleware
  + OpenTelemetry framework-independent observability
  + provider adapter 使用各 provider 原生 cache／compaction／tool search
```

Pydantic AI V2＋Harness＋DBOS 保留為正式第二名與翻案候選，但第一版不把兩套完整 agent runtime 混用。這項裁決由 Owner 於 2026-09-01 核准，可因新官方能力、代表性產品證據或後續設計發現經討論翻案；在開 ADR 前仍屬 Working Research，不授權施工。

選擇 LangChain／LangGraph 的主要原因是：

1. LangChain 1.0 與 LangGraph 1.0 均有正式 LTS／SemVer 政策；LangGraph 1.0 在 2.0 前維持 ACTIVE，之後至少一年 MAINTENANCE；
2. 同一套 runtime 已提供 thread checkpoint、PostgreSQL persistence、interrupt／resume、fault tolerance、pending writes、Store namespace、semantic search 與 listing primitive；
3. 一般待審文件可作 durable working state 繼續訪談，只有真正無法安全前進的必要澄清才使用 interrupt；
4. exact-scope inventory 可由 runtime 走完 Store listing／pagination 並建立 manifest，不必要求模型或 semantic top-k 宣稱完整；
5. LangChain stable middleware 已能承接 typed tools、structured output、錯誤分類、retry、call limits、動態 Context／Tool 暴露與 tracing；不足處只留下產品領域 policy，而不是再造 generic framework。

#### 9.46.3 框架選擇不得改寫已收斂的 Memory 形狀

選定 LangGraph 不表示採用「checkpoint 裡放一份大摘要」，也不表示 `Store.put()` 的任意 JSON 就已自動成為正確 Memory。正式設計仍必須保留以下框架無關契約：

```text
完整、可回查的訪談來源
        ＋
同一 JD scope 內多筆聚焦、詳細、自足、可修訂的 current Semantic Memory
        ＋
只作 routing、可由 current Memory 重建的小型導覽
        ＋
一般回合有界召回，模型需要時再 search／read
        ＋
製作、重大重整或全面檢查 JD 時 exact-scope 列舉全部 current Memory
```

其中一筆 Semantic Memory 仍以「一個可獨立取回與修訂的連貫工作主題」為最低語意，不是一則訊息、一個原子詞彙、一個 JD 欄位或一份巨大 profile。內容在已知時保留行動、對象、目的／成果、條件／情境、頻率／例外、協作與責任邊界；不知道的地方維持不知道。這是現行語意契約，不是已核准的資料庫 schema。

下列事項仍未因選框架而自動定案：正式 record schema、粒度門檻、導覽物理格式、recall 排序、embedding／hybrid strategy、unknown／conflict 薄欄位、stable inventory snapshot，以及 CAS／serial-writer 的最終做法。它們必須在下一階段以跨家共同基線與產品效果逐項決定。

#### 9.46.4 各成熟元件的預定責任邊界

本節只固定責任，不提前固定 graph node、table 或 API：

| 效果 | 優先使用的成熟機制 | 仍需後續設計的最薄產品部分 |
| --- | --- | --- |
| 長訪談與關閉後續談 | LangGraph thread＋PostgreSQL checkpointer | thread／JD identity 與 source retention 契約 |
| 可修訂 Semantic Memory | LangGraph PostgreSQL Store、namespace、filter／search／listing | 職務資訊 admission、補充／更正／不同案例／unknown／conflict 語意；current-head／CAS 邊界 |
| 一般 Context | LangChain middleware＋LangGraph state／Store reads | token budget、recent-window 與 automatic recall policy |
| 按需 Skill／Tool | LangChain stable dynamic prompt／tool middleware；provider 支援時使用原生 tool search | 版本化職務分析 Skill 內容與觸發描述 |
| 完整盤點 | Store exact listing＋runtime pagination／manifest | stable revision、分批處理與 JD quality Skill |
| 必要澄清 | LangGraph durable interrupt／resume | 何時真的 blocking，以及員工可讀問題內容 |
| 一般 AI 待審變更 | durable working state＋deterministic review command | 變更群組與正式 JD authority policy |
| 驗證、錯誤與恢復 | LangChain middleware＋LangGraph retry／fault-tolerance／limits | 少量 domain error code 與 sanitized message |
| 成本與診斷 | provider usage＋OpenTelemetry；provider-native cache／compaction | 預算、門檻與內容記錄安全政策 |

Deep Agents 的 Agent Skills 可完整支援 `SKILL.md`、references、scripts 與 assets，但官方目前仍明列 pre-1.0、minor version可能破壞 API。第一版不為了 Skill 檔案格式引入整套 Deep Agents；先使用 LangChain 1.x 的 stable middleware／動態 Context primitive 承接按需載入。若職務分析 Skills 後續確實需要大量 bundled resources 或 executable assets，再以鎖版本的 leaf integration 重新評估，不能把 pre-1.0 套件擴張成 authority。

#### 9.46.5 明確不採與翻案條件

第一版不採：

- 同時混用 LangGraph agent runtime 與 Pydantic AI agent runtime；
- 以 LangMem 0.0.x manager、Deep Agents pre-1.0 或 Harness 0.x 作 semantic authority；
- provider-managed Memory 作本機產品的 primary authority；
- 每輪固定第二模型、每輪摘要、額外 LLM Tool Selector；
- 巨大 profile、只追加 facts、semantic top-k 冒充完整盤點；
- 第一版 knowledge graph、episodic engine、RAG 或跨 JD Memory。

下列任一條件成立時應重開選型，而不是永久綁死：

1. Pydantic Harness 出貨穩定的 PostgreSQL conversation／step persistence、exact inventory pagination 與一體化 durable tool contract；
2. 代表性長訪談證明 Pydantic focused notebook 在細節、衝突與完整盤點效果上明顯優於主選；
3. Deep Agents 進入穩定版本，且完整 Skill package 能力成為第一版的實際硬需求；
4. LangGraph 無法在不建立厚自訂層的情況下滿足 current-head consistency、exact inventory 或長訪談成本門檻。

#### 9.46.6 本輪官方來源

- [LangChain／LangGraph — Release policy](https://docs.langchain.com/oss/python/release-policy)
- [LangGraph — Persistence、checkpoints、Store 與 PostgreSQL](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangGraph — Fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance)
- [LangChain — Human-in-the-loop middleware](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)
- [LangChain — Tools／ToolRuntime／Store](https://docs.langchain.com/oss/python/langchain/tools)
- [LangChain — Prebuilt middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)
- [Pydantic AI Harness — Capability catalog／version boundary](https://pydantic.dev/docs/ai/harness/)
- [Pydantic AI Harness — Memory](https://pydantic.dev/docs/ai/harness/memory/)
- [Pydantic AI — Durable execution](https://pydantic.dev/docs/ai/capabilities/durable_execution/overview/)

### 9.47 第一個詳細架構決定：執行狀態與長期 Memory 分工（Owner 已確認）

本節先固定「哪一類成熟元件負責哪一類資料」，不提前決定正式 table、record schema、graph node 或 API。Owner 確認採下列分工：

```text
LangGraph Checkpoint
  = 目前 thread／run 的執行進度、短暫工作結果、interrupt／resume、待審工作流狀態

LangGraph PostgreSQL Store（每份 JD 獨立 namespace）
  = 完整可回查的訪談來源
  + 多筆聚焦、詳細、自足、可修訂的 current Semantic Memory

Checkpoint 只保存本輪需要的 Memory references／已組裝 Context，
不再複製一份完整 Semantic Memory。
```

選擇理由：

1. Checkpoint 的官方語意是 thread 在各 step 的狀態快照，適合 durable execution、interrupt、resume、time travel 與 fault tolerance；它不等於一個可獨立查詢、列舉與修訂的長期知識集合。
2. Store 提供 namespace、key、JSON document、filter／search 與跨 checkpoint 存取，較適合每份 JD 內多筆 Semantic Memory 與來源資料；完整盤點時也能直接 exact-scope listing，而不是依賴 top-k recall。
3. 兩者不雙寫同一份權威內容。Checkpoint 可以記住「本輪用了哪些 Memory」及短暫結果，但 Semantic Memory 的 current head 只存在 Store，避免兩份資料互相失效。
4. 每份 JD 使用獨立 namespace；不做跨 JD Memory，共用知識也不在本輪範圍。

這項決定會改變 ADR 0060 與現行 `AGENTS.md` 中「Checkpoint 擁有可修訂理解、Store 只擁有逐字來源」的 authority 分界，因此日後不能用一般重構偷偷改掉。完整設計核准後必須另開 successor ADR，明確取代相衝突段落；在 successor ADR Accepted 前，現行程式仍遵守 ADR 0060。

本節當時尚未決定 Semantic Memory record 內容；後續 §9.48 已確認 A+ 邏輯表徵。來源與 Memory 是否使用同一 namespace、revision／CAS、unknown／conflict 表徵、導覽投影、召回排序及 inventory snapshot 仍未決定，必須逐項往下收斂。

官方依據：

- [LangGraph — Persistence、checkpoint 與 Store](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph — Memory overview](https://docs.langchain.com/oss/python/concepts/memory)
- [OpenAI — Codex Memories](https://learn.chatgpt.com/docs/customization/memories)

### 9.48 第二個詳細架構決定：A+ 單筆 Semantic Memory 邏輯表徵（Owner 已確認）

本節承接 §9.47 的 Checkpoint／Store 分工，只決定「Store 中一筆 Semantic Memory 在語意上應長什麼樣」。它不是完整 Memory 架構、不是正式資料庫 schema，也不取代框架無關五段式契約。Owner 於 2026-09-01 確認 A+ 作目前可翻案的設計基線；若後續官方能力、代表性產品證據或細節研究顯示更佳方案，必須列出證據與影響後再討論，不能靜默改寫。

#### 9.48.1 A+ 的邏輯形狀

```text
一筆 Semantic Memory（邏輯檢視）
├─ Store 原生且可信的 identity／metadata
│  ├─ namespace：由 Runtime 固定為該 JD scope
│  ├─ key：由 Runtime 產生的 stable memory key
│  └─ created_at／updated_at：由 Store 管理
│
├─ 極薄的 Runtime safety metadata
│  ├─ schema version
│  └─ current-head、revision／hash、operation lineage 等真正需要的安全資訊
│     （物理位置與一致性作法仍未決定，且一律不是模型欄位）
│
└─ 模型產生、視為不可信資料的 semantic document
   ├─ title／topic：供人與檢索辨識的簡短標籤，不是 identity
   └─ content：一項聚焦、自足、保留必要細節的連貫工作主題
```

Store 已經擁有 namespace、key 與建立／更新時間時，不得在 JSON value 再複製另一份同義 ID、scope 或 timestamp；否則兩份 metadata 可能漂移。模型只提供 semantic title／content 與受限 mutation intent，不填 canonical ID、scope、版本、時間、來源 UUID、Skill receipt、生命週期或並行控制欄位。

#### 9.48.2 內容與粒度規則

1. 一筆 Memory 表達一項可以被獨立搜尋、理解與修訂的連貫工作主題；不是一則訊息、一個原子 fact、一個 JD 欄位或整名員工的巨大 profile。
2. 兩部分若可能獨立改變，或日後需要分別搜尋／修訂，才拆成不同 Memory；若拆開會破壞條件、例外、責任邊界或因果關係，就保留在同一筆。
3. 在已知時，content 保留會影響 JD 判斷的行動、對象、目的／成果、條件／情境、頻率／例外、協作與責任邊界；不知道的內容維持不知道，不能為了填滿結構而猜。
4. title／topic 只是導覽與 routing label，改名不等於換 identity；正式 stable key 由 Runtime 管理。
5. 本輪不設定任意 token／字數門檻，也不因跨 record 關係問題預先導入 knowledge graph。真正粒度門檻需由後續代表性訪談資料驗證。

#### 9.48.3 A+ 能做什麼、不能做什麼

A+ 直接承接 M2 細節保真與 M6 單筆內關係不丟失，並為 M3 廣度、M4 修訂、M5 未知／衝突及 M7 案例／目前理解雙層可用性提供合適內容載體。但它只是一筆 Semantic Memory 的內容表徵，不能單獨完成：

- M1 的完整 conversation persistence 與跨關閉恢復；
- M8 的 bounded recall、搜尋與按需讀取；
- M9 的 exact-scope 全量列舉、stable inventory 與完成 manifest；
- M10 的原始來源回查與可信 generation lineage；
- M11 的 per-JD isolation；
- current-head 發布、CAS／lost-update 防護、冪等、重放與 stale 處理；
- 小型可重建導覽與跨 record 關係的召回。

因此正式完整形狀仍是：durable conversation source＋A+ Semantic Memory collection＋可重建導覽＋日常有界召回／按需深入＋exact-scope 全量盤點＋Runtime version／current-head 管理。A+ 不得被簡寫成「有 title／content 就已完成 Memory」。

#### 9.48.4 已確認的問題與最低修正

1. **CAS 不是 Store `put` 自動提供。**LangGraph `BaseStore.put(namespace, key, value, ...)` 是一般 upsert，沒有文件化的 expected-version precondition。若只在 value 內放 revision 而沒有原子比較，就是假的並行安全。正式設計必須在 per-JD serial writer 或極薄 transactional expected-revision seam 中擇一；此處尚未裁決。
2. **正常召回只能看到 current head。**明確更正、淘汰或合併後，舊版本不得與新版本一起進入一般 Context；revision history 只供回查、復原與診斷。current-head 的物理實現仍未決定。
3. **跨 record 關係不能由 A+ 自動保證。**第一版先用 rich self-contained content、hybrid／semantic retrieval、小型導覽與全量盤點承接；只有代表性資料證明關係持續遺失時，才討論極薄的衍生 relationship projection，不先建立 graph 或模型手填永久 ID 關聯。
4. **A+ 不保證所有工作已保存或已處理。**來源 ingestion／Memory processing 必須可觀察；完整 JD 作業仍需 exact-scope 列舉所有 current Memory，不能依 top-k、summary 或模型自述「都看過」。
5. **來源與引用維持分層。**原始 conversation 與 Runtime 建立的 generation lineage 獨立保存；不要求模型把 source UUID 或整段 quote 塞進 semantic content。需要核實時再按需回查來源。
6. **模型寫入內容是不可信資料。**title／content 只能以資料權限進入 Context，不得覆蓋 system policy、工具權限或職務分析 Skill。

#### 9.48.5 仍未決定的下一組問題

1. semantic document 是否只需 `title＋content`，或未知／未解衝突需要一個極小、機器可讀且由 Runtime 驗證的語意狀態；
2. current head、歷史 revision 與 tombstone／delete 的物理表示；
3. per-JD serial writer 是否已足以滿足第一版，或必須補 expected-version／hash CAS；
4. exact inventory 在盤點期間使用 lock、revision manifest、snapshot 或遇變更重啟；
5. 來源與 Semantic Memory 是否使用同一 Store namespace 下的不同 prefix，或不同 namespace；
6. 粒度何時拆分／合併，以及何時需要更新小型導覽。

下一輪先只討論第 1 題，不能因 A+ 已確認就同時把其餘實作細節視為定案。

#### 9.48.6 官方依據與證據邊界

- [OpenAI — Codex Memories](https://learn.chatgpt.com/docs/customization/memories)：公開 local memory 由 summaries、durable entries、recent inputs 與 supporting evidence 等生成狀態組成，並將 extraction／consolidation 分開；支持「Memory 內容不是整套 runtime」與分層處理，但沒有公開可直接照搬的 Caliburn record schema。
- [Anthropic — Managed Agents Memory](https://platform.claude.com/docs/en/managed-agents/memory)：Memory store 是多份 text documents；官方建議 many small focused files，並提供 immutable versions、latest-head retrieval 與 content-hash optimistic concurrency。這直接支持聚焦 documents、current head 與 CAS 需求，但其 file path／雲端服務不是 Caliburn 必須照搬的物理形式。
- [LangChain — Memory overview](https://docs.langchain.com/oss/python/concepts/memory)：區分 profile 與 collection，並說明 collection 的召回優勢及更新、搜尋與跨記錄關係成本；支持 A+ collection 而非巨大 profile，也證明 A+ 仍需周邊 retrieval／relation policy。
- [LangGraph — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)：Checkpoint 與 Store 的官方責任邊界；支持 §9.47 分工。
- [LangGraph — BaseStore `put`](https://reference.langchain.com/python/langgraph.store/base/BaseStore/put)：Store item 的一般 upsert primitive；目前沒有文件化 expected-version CAS，因此不能宣稱框架已自動解決 lost update。
- [Google — Memory Bank generate memories](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale/memory-bank/generate-memories)：extraction／consolidation 會檢查同 scope 既有 Memory 的重複與矛盾；支持更新需看既有範圍，但其 managed policy 不等於 Caliburn 的未知／衝突語意。
- [Pydantic AI Harness — Memory](https://pydantic.dev/docs/ai/harness/memory/)：bounded notebook、聚焦文件、按需工具、PostgreSQL、optimistic CAS 與不可信 Memory 的安全邊界；用來驗證成熟 primitive，而不是改採第二套 agent runtime。

## 10. 討論紀錄

### 2026-09-01：A+ 單筆 Semantic Memory 邏輯表徵獲 Owner 核准

Owner 確認 A+ 作目前可翻案的設計基線：Store 原生可信 identity／metadata＋極薄 Runtime safety metadata＋模型只撰寫 `title／topic＋rich self-contained content`。本輪明確限制 A+ 只是一筆 Semantic Memory 的邏輯表徵，不是完整架構或正式 schema；CAS、current-head、unknown／conflict、跨 record 關係、stable inventory 與來源分層仍是周邊 Runtime／後續設計責任。下一輪先討論 semantic document 是否需要任何極小的機器可讀語意欄位，未授權施工。

### 2026-09-01：四組框架總決選獲 Owner 核准

Owner 核准以 `LangChain 1.0 LTS＋LangGraph 1.0 LTS（採相容的 1.x minor）＋官方 PostgreSQL Checkpointer／Store` 作目前正式研究選擇，Pydantic AI V2＋Harness＋DBOS 保留第二名與翻案候選。本輪再次確認：選框架不能降低 B1～B14、M1～M11 與框架無關五段式 Memory 契約，也不能把框架預設當成職務分析語意。下一步先做成熟元件與現行契約的詳細架構對照，再分段審核；未開 ADR、未寫施工計畫、未授權實作。

### 2026-09-01：Checkpoint／Store 責任分工獲 Owner 核准

Owner 核准 Checkpoint 只承接 thread／run 執行進度與待審工作流，完整訪談來源與可修訂 Semantic Memory 則放入每份 JD 隔離的 PostgreSQL Store namespace；Checkpoint 可保存本輪引用，但不得複製另一份 Semantic Memory authority。此分工與 ADR 0060 的現行 authority 邊界不同，完整方案核准後必須以 successor ADR 正式翻案，不能在普通重構中靜默改寫。

### 2026-08-30：建立產品 Memory mapping 文檔

Owner 確認在通用 LLM Memory 研究完成後，另開新文檔討論 Caliburn mapping。現階段先從 M1「要記得什麼」開始，不直接進入框架或實作。

### 2026-08-30：M1-1 原始訪談紀錄暫時確認

完整聊天作為獨立、可按需回查的 source history；平常不全量注入，也不冒充整理後的長期工作理解。Owner 另要求後續每項 mapping 都先回看本文與必要來源文檔，避免依對話記憶遺漏或重複討論。

### 2026-08-30：M1-2 工作理解核心目的暫時確認

工作理解是 AI 可持續修訂、比 JD 更詳細的員工實際工作全貌；主要供長期訪談與形成 JD 使用，不是聊天摘要，也不預先等同 Duty／Task／OPKS schema。

### 2026-08-30：改採成果／能力優先 mapping

Owner 校正：Caliburn 唯一產品目的為產出完美職務說明書；Memory 與工作理解都只是候選方法。前兩項 M1 討論保留為問題背景，但不再當作必做架構。後續先列出高品質 JD 對長訪談 Memory 的中立效果，再檢查成熟方案是否已完整覆蓋；只有可證明的缺口才允許自訂機制。

### 2026-08-31：C1-1 長訪談核心效果暫時確認

Owner 確認：真正需要的是模型在長訪談後仍能取得目前有效且完整的員工工作細節，正確吸收更正並避免資料不足時捏造；若成熟方案已達成，不另做自訂工作理解 Memory。

### 2026-08-31：C1-2 訪談資訊連續性暫時確認

Owner 確認：為避免最終 JD 遺漏，AI 應記得重要內容是否已取得，避免重複詢問，也不能因話題切換而永久遺漏尚未取得的關鍵資訊；實現方式尚未決定。

### 2026-08-31：C1-3 自然續談暫時確認

Owner 確認：員工可隨時停止、關頁或重啟，之後開啟同一份 JD 應自然延續原訪談與必要資訊；不建立「暫停訪談」產品操作，底層恢復機制尚未決定。

### 2026-08-31：C1-4 JD 隔離與產品關係暫時確認

Owner 確認：每位員工受訪的這份工作對應一份獨立 JD，不需要跨 JD 共用記憶；不同 JD 的訪談內容不得互相污染。這是產品關係，不只是第一版簡化。

### 2026-08-31：C2 成熟能力覆蓋第一輪研究完成

本輪重讀通用 Memory 研究與最新產品北極星，並重新核對 OpenAI、Anthropic、LangGraph／LangMem、PydanticAI Harness、Deep Agents、Google 與 AWS 官方資料。第一輪結論是成熟系統普遍採 durable conversation、可修訂 Semantic Memory、按需來源搜尋、Context 管理與 trusted scope 的組合；不存在一個公開 primitive 能單獨保證員工全部工作細節完整保存或自動判斷職務訪談充分性。

C1-3 自然續談與 C1-4 JD 隔離已有成熟 primitive 直接覆蓋；C1-1 細節完整性／更正／避免捏造及 C1-2 已回答／仍缺資訊只有部分覆蓋。後續 C3 應先驗證「完整性」與「充分性」兩個中立缺口，不得先把舊 Work Understanding、Gap 或 Focus 當成答案。此研究沒有選框架、沒有授權實作，也沒有修改現行 authority。

### 2026-08-31：C3 真實缺口第一輪研究完成

本輪完整回讀通用 Memory 研究、最新產品大方向及既有職務分析／OPKS 研究，並重新核對 OpenAI、Anthropic、Google、AWS、LangGraph／LangMem、OPM、O*NET 與 iCAP 官方資料。研究把「完整」拆成來源保存、語意選取、更正一致、召回與職務內容五層，也把「充分」拆成已回答、未取得、未覆蓋面向與可形成 JD 四種效果。

結論是成熟能力已直接承接 source persistence、恢復、隔離、CRUD、revision、search 與 context management；真正未被通用 Memory 自動完成的只有兩項領域判斷：哪些工作細節重要到不能漏，以及哪些會改變 JD 的工作面向尚未訪談充分。這不授權復活舊 Work Understanding／Gap／Focus，也不表示需要新資料庫；C4 應先比較能否以職務分析 Skill／rubric 加成熟 Memory 擴充點完成最薄差額。

### 2026-08-31：C4 Caliburn 最薄差額第一輪研究完成

本輪重新核對 OpenAI／Anthropic Agent Skills、Google Memory Bank custom topics／few-shot、AWS AgentCore custom strategy、LangMem memory manager、LangGraph state、Anthropic Interviewer、OPM 與 O\*NET 官方資料。第一輪結論是 G1 的抽取／更新機制可直接由成熟 Memory 承接，Caliburn 只需提供職務分析領域方法；G2 由版本化 Skill／rubric 判斷，coverage 預設按需計算，只有會影響 JD 且需跨回合保留的未解問題才使用同一 Memory／runtime 持久化。

推薦進 C5 比較的不是新 Work Understanding／Gap／Focus 系統，而是「職務分析 Skill／rubric＋成熟 Memory／runtime 的最薄映射」。本輪沒有選框架、沒有修改 authority，也沒有授權實作；所有結論仍屬可經後續證據與 Owner 討論翻案的研究判斷。

### 2026-08-31：M1～M11 第二輪成熟能力 mapping 完成

Owner 校正研究順序：不得再以舊元件去留或第一輪「兩個缺口」作分析主軸，必須把已確認的 M1～M11 逐項對照跨家共同能力；共同能力不足時，才比較官方已出貨的差異能力。本輪因此將 §6～§8 標為歷史，新增 §9 作目前裁決。

第二輪結論是：共同基線直接承接修訂生命週期、有界日常召回、原始來源回查與單一 JD 隔離；長期連續性、細節、廣度、衝突、關係與案例雙層可用性已有成熟 primitive，但仍需職務領域保存／衝突／關係語意，不能誤稱 generic Memory 預設已完成。M9「完整盤點」則必須把 scope 內 list-all／pagination 升格為未來選型硬條件；semantic top-k 不能替代。

本輪重新核對 OpenAI Responses／Codex Memories、Anthropic Managed Agents／Memory Tool／Context Engineering、Google Memory Bank、AWS AgentCore、LangGraph／LangMem 官方資料。所有結論仍屬可經新證據與 Owner 討論翻案的能力研究；未選框架、未選 schema、未設計 Prompt／Tool，也未授權實作。

### 2026-08-31：Retention／admission 差異方案研究完成

本輪只處理 §9.5 第 1 題。研究把 admission 拆成來源資格、語意 admission、持久化政策三道 gate，並把其後的 validation／consolidation 與 admission 明確切開。OpenAI Codex、Claude、Google、AWS 與 LangMem 的共同證據是：durable Memory 是選擇層；產品目的要透過 topic／strategy／instructions／examples 注入；空結果合法；安全 policy 不能只靠 extraction model。

Owner 尚未裁決正式方案。研究暫定候選 C「可信 runtime gate＋產品定義的語意 admission＋成熟 consolidation」最符合 M1～M3：不以頻率判斷重要性，保存所有可能改變 JD 的員工工作資訊，讓低頻高影響細節、未知與衝突都有機會進修訂流程；原始 conversation 仍獨立保留。本輪未選框架、schema、Prompt、Tool、hot／background 時機，也未授權實作。

### 2026-08-31：第二層表徵主候選確認

本輪把 OpenAI Agents SDK Sandbox Memory、Anthropic Managed Agents／Memory Tool、Google Memory Bank、AWS AgentCore 與 LangChain／LangMem 的資料粒度與讀取路徑重新攤開比較。Owner 同意「durable source＋focused rich current records／documents＋小型可重建導覽＋按需深入＋exact-scope 全量盤點」作下一輪唯一主候選。導覽只能是可重建 retrieval projection，不能成為第二份權威；完整盤點必須直接列舉 current records，不能靠 summary 或 semantic top-k。下一輪將深入更新、Prompt、Tool、Context 與 failure contract，尚未選框架或授權施工。

### 2026-08-31：M5 未解、衝突與更正語意研究完成

本輪沒有重做通用 D4，而是按本文研究紀律重新核對 OpenAI Codex、Claude 消費型 Memory、Anthropic Memory Tool／Managed Agents、Google Memory Bank、AWS AgentCore 與 LangMem 最新官方資料，再把既有通用行為映射至 M5。研究確認成熟方案普遍提供 CRUD、current head、revision 或 domain extension seam，但沒有共同的 unresolved-conflict default；Google／AWS 等 managed default 甚至可能更新、刪除或依語句 confidence 消解矛盾。

目前推薦候選 C「成熟 lifecycle＋產品 conflict policy」：未知與未解矛盾可作合法 current knowledge；明確更正只留下新 active head；時間變化與不同條件不誤判為衝突；模型不得只依 recency、語氣或 confidence 選邊；原始 conversation／revision 只在需要時回查。此結論仍待 Owner 確認，且沒有選 framework、schema、Prompt、Tool、blocking policy 或授權實作。

### 2026-08-31：M6／M9／M7 與完整方案研究完成

本輪依文檔責任矩陣先回讀高品質 JD 的 M1～M11，再核對 OpenAI Agents SDK／model guidance、Anthropic Managed Agents／Memory Tool／Context Engineering、Google Memory Bank、AWS AgentCore、LangGraph／LangMem、Graphiti 與各方案最新成熟度／定價資料。通用事實留在 landscape；本文只記錄產品 mapping 與暫定取捨。

研究結論是：M6 第一版以 rich self-contained bounded documents／records 已可保留工作脈絡，沒有證據要求先上 knowledge graph；M9 必須採 exact-scope list-all／pagination、stable revision 與 runtime manifest，semantic top-k 不合格；M7 由 raw conversation／events＋current Semantic Memory 已能同時保留案例與穩定理解，AWS episodic agent trajectory 不應直接冒充員工工作案例層。

完整候選比較後，暫定首選為 LangGraph 1.x LTS＋Postgres Store／Saver＋LangChain tools／Structured Output：它以成熟 framework 承接 runtime、persistence、namespace、search、listing 與 resume，Caliburn 只提供職務領域 retention／conflict／relation 語意。AWS、Google、Anthropic 都是正式備選；LangMem 與 Graphiti 因版本成熟度或架構重量，只列條件式 spike。這仍是 Working Research，未核准 ADR、schema 或施工。

### 2026-08-31：案例／理解／JD 表徵與關係重新開啟研究

Owner 校正「工作案例 → 工作理解 → JD」是顧問認知過程，不是三層 storage pipeline；案例與理解是否持久化、是否同 collection、是否只靠 conversation＋Memory，均須由滿分 JD 的效果證明。本輪重新核對 OpenAI Responses／compaction、Anthropic Memory Tool／Managed Agents、Google natural memories／profiles、AWS semantic／episodic strategies、LangMem profile／collection、Zep／Graphiti episodes／facts，以及 O\*NET 2025 Emerging Tasks 流程。

研究結果寫入 §9.32～§9.37，並明示取代 §9.24、§9.27～§9.28 中過早固定的資料層假設。目前較薄候選為 C+：durable conversation＋同一 JD scope 的 rich current semantic records＋按需來源回查＋exact-scope 全量盤點；不先建 case store、巨大 profile、永久 Memory→JD linkage 或 graph。這仍是暫定研究方向，未選 schema、Memory Prompt、更新時機或正式框架接線，也未授權施工。

### 2026-08-31：Memory 與 JD 的責任主詞校正並建立決策表

Owner 校正：Memory 只是記憶能力，不能決定或操控 JD；決定是否操作、如何操作及如何撰寫 JD 的主體是 LLM＋職務分析 Skill。Tool／Runtime 只提供受限操作與 deterministic validation，員工保有最終核准權。本輪已同步修正 §9.34～§9.35，並新增 §9.38，將既有研究分成已確認、暫定候選、尚未決定與已排除四類，避免後續重複研究或把候選誤寫成架構決策。

### 2026-08-31：完整 framework 比較完成，提出待核准推薦

本輪沒有以現行 LangGraph 程式為答案，而是重新比較 LangChain／LangGraph、Pydantic AI V2／Harness、LangMem、Deep Agents、OpenAI Agents SDK、Anthropic Managed Agents、Google Memory Bank 與 AWS AgentCore。新增證據確認 Pydantic Harness Memory 已原生提供 PostgreSQL、CAS、冪等與 bounded notebook，但其整套組合仍缺官方 PostgreSQL Step Persistence、內建 semantic search、文件化 exact inventory pagination，且 DBOS 不會自動把普通 Memory tools 變成 durable steps；Harness 本身仍為 0.x 高速變動套件。

依 M1～M11、產品硬門檻與整套 runtime 而非單一元件功能表比較後，§9.41 推薦 `LangChain 1.x＋LangGraph 1.x LTS＋PostgreSQL Saver／Store` 為暫定首選，Pydantic AI V2＋Harness 為正式第二名與未來翻案候選。LangGraph 的 Store item CAS 與職務領域 Memory policy 是已明示的兩個缺口；前者只允許最薄一致性 adapter，後者屬產品方法，不能冒充 generic framework 功能。此推薦仍待 Owner 核准，不是 ADR、未授權施工。
