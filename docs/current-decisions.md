# Caliburn Current Decision Register

- 最後核對：**2026-09-04**
- 狀態：**目前決策與閱讀路由的唯一入口**
- 流程：[`decision-process.md`](decision-process.md)

> 本表不取代現行 code、`AGENTS.md` 或 Accepted ADR。它負責指出「現在什麼有效、什麼只是候選、下一步只處理哪一題」。Working Decision 若與 production authority 衝突，必須經 successor ADR 與實作 gate，不能直接施工。

## 1. 閱讀順序

後續討論者、reviewer 與實作者依序閱讀：

1. [`../AGENTS.md`](../AGENTS.md)；
2. 本表；
3. 本表指定的 current ADR／contract／design；
4. 只有需要查理由或重新驗證時，才讀完整 research；
5. 只有進入 implementation gate，才讀對應 plan。

文件標題出現「latest／final／approved」不會自動高於本表與 Accepted ADR。聊天內已同意但未寫回本表的內容，必須先補登記，才能被下一個工作階段當成 durable decision。

## 2. 全域治理決策

| ID | 狀態 | 目前結論 | Authority／依據 | 重開條件 | 下一個 gate |
|---|---|---|---|---|---|
| `GOV-D001` | `WORKING` | 重大研究、設計、review 與施工一律使用 [`decision-process.md`](decision-process.md)；本表是第一閱讀入口。 | Product Owner 2026-09-03 核准；AWS／Microsoft ADR 與 Google review 官方來源見流程文件。 | 實際使用證明流程造成重大阻塞、漏掉關鍵決策，或 Owner 改變治理方式。 | 將現有主題逐一登記；不回頭重寫全部歷史。 |
| `GOV-D002` | `WORKING` | 每輪只能有一個 blocking decision ID；鄰近但不阻塞的問題進 parking lot。每輪結束必須寫回 status、理由、來源、重開條件與 next gate。 | `GOV-D001` 流程。 | 同上。 | 所有新研究立即適用。 |
| `GOV-D003` | `WORKING` | `WORKING` 在被明確 supersede 前約束後續研究／設計；它不能越過 Accepted ADR 或現行 code 授權 production。 | `GOV-D001` authority 分層。 | Owner 調整 Working／Accepted 邊界。 | 架構翻案一律另開 successor ADR。 |

## 3. Memory 主題目前狀態

### 3.1 現在仍有效的邊界

| ID | 狀態 | 目前結論 | Authority／依據 | 重開條件 | 下一個 gate |
|---|---|---|---|---|---|
| `MEM-D000` | `ACCEPTED` | Production 仍依現行 code、`AGENTS.md` 與 Accepted ADR 0060；2026-08-30～09-02 的 Memory 研究沒有自行改變 production authority。 | [`adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md`](adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md)、現行 code。 | Accepted successor ADR 通過且對應 implementation／verification 完成。 | 在此之前只允許 research／design／明確隔離 spike。 |
| `MEM-D001` | `WORKING` | Memory 的唯一產品目的，是讓長訪談後的 LLM 仍能完整理解員工工作與必要細節，支援產出、修訂及最終檢查高品質 JD；Memory 本身不是產品目的，也不操控 JD。 | [`specs/2026-09-01-framework-independent-memory-contract.md`](specs/2026-09-01-framework-independent-memory-contract.md) 的產品效果；Owner 多輪確認。 | 完美 JD 的產品目的或 Memory 必要效果被明確翻案。 | 作為候選機制與測試的效果門檻。 |
| `MEM-D002` | `WORKING` | 一名員工對應一份隔離文件、一個持續訪談 thread 與一份 JD；目前不需要跨 JD 共用員工 Memory。 | Owner 明確裁決；[`specs/2026-08-30-caliburn-memory-requirements-mapping-working-research.md`](specs/2026-08-30-caliburn-memory-requirements-mapping-working-research.md)。 | 產品範圍加入跨員工／跨 JD 知識共享。 | 約束 scope／namespace 候選。 |
| `MEM-D003` | `WORKING` | 日常回合不必把全部長期 Memory 放進 prompt；但最後全面製作／檢查 JD 時，必須具備可驗證地處理該 JD 全部有效 Memory 的能力。所有員工工作都不得因摘要或召回策略而永久遺失。 | [`specs/2026-09-01-framework-independent-memory-contract.md`](specs/2026-09-01-framework-independent-memory-contract.md) §3.4–3.5、M3／M9。 | 官方能力或代表性實驗證明需採不同效果契約。 | 納入 `MEM-Q001`～`MEM-Q003` 與後續 isolated smoke 的驗收情境。 |

### 3.2 Memory reconciliation 決策

| ID | 狀態 | 目前決策／待決問題 | Authority／階段 | 重開條件／已有資料 | 下一個 gate |
|---|---|---|---|---|---|
| `MEM-Q001` | `WORKING` | 採用三層責任：LangGraph Checkpointer 保存每份 JD 的完整員工↔顧問 conversation 與 graph/run/interrupt state；PostgreSQL Store 保存可修訂 semantic Memory collection；Memory manager 只產生 extraction／consolidation 候選；每輪 model context 非破壞性地由兩層資料有界組裝。第一版不建立重複 employee-source 文字 leaf；如日後需要 provenance，只引用 canonical message ID。 | Product Owner 2026-09-03 核准；完整證據與三方案比較見 [`specs/2026-09-03-memory-conversation-and-semantic-responsibility-reconciliation.md`](specs/2026-09-03-memory-conversation-and-semantic-responsibility-reconciliation.md)。 | 真 PostgreSQL contract 顯示長 thread 儲存／延遲不可接受；產品加入獨立 event query/export/retention；官方 primitive 改變；或 Owner 改變一 JD／一 thread 邊界。 | 持續約束 `MEM-Q002`／`MEM-Q003` 與 successor ADR；production 現在仍禁止依此施工。 |
| `MEM-Q002` | `WORKING` | 採 canonical conversation＋選擇性 consolidation：全部案例原始對話耐久保留；重複資訊 no-op；同主題通用新細節 update；需要獨立搜尋／修訂且會影響 JD 的重要差異才 add focused Memory；更正 revise、未解衝突保留兩邊；不採每案例固定一筆。長距離案例指涉必須可按需回查 canonical conversation。 | Product Owner 2026-09-03 核准方案 C；完整官方證據、三方案、A／B／更正情境與八項驗收門檻見 [`specs/2026-09-03-memory-similar-case-detail-and-consolidation-reconciliation.md`](specs/2026-09-03-memory-similar-case-detail-and-consolidation-reconciliation.md)。 | 代表性驗證顯示重要案例差異會靜默遺失、同義案例造成近線性膨脹、長距離原始片段無法找回；官方 primitive 改變；或 Owner 改變產品效果。 | 約束 `MEM-Q003`；production 仍須 successor ADR，現在不授權 schema、索引或施工。 |
| `MEM-Q003` | `WORKING` | 採修正後方案 B：Checkpointer 保存 canonical conversation；Semantic Memory／小型導覽先 routing，按需依 canonical message reference 回讀原始問答；未命中才做有界 exact scan／澄清。第一版不替每則 raw message 建 semantic index；只有代表性 smoke 證明重要久遠細節無法找回，才重開 derived raw-conversation／hybrid index。 | Product Owner 2026-09-03 核准；五家官方共同邊界、OpenAI Codex／Agents SDK 與 Anthropic 實際 read path、三方案與限制見 [`specs/2026-09-03-memory-canonical-conversation-search-read-reconciliation.md`](specs/2026-09-03-memory-canonical-conversation-search-read-reconciliation.md)。 | 官方新增原生 Checkpointer conversation search；isolated spike 證明 recall、成本／延遲不可接受；或 Owner 改變完整細節找回要求。 | **G4／G5：**收斂 Semantic Memory routing、canonical reference／read contract 與 isolated spike；production 仍須 successor ADR。 |
| `MEM-Q004` | `WORKING` | G4 read contract 採 progressive disclosure：先由小型、可重建的 Semantic Memory 導覽定向；需要更多內容時，模型使用 `search_semantic_memory(query)`，Runtime 在目前 JD／文件 scope 內回傳少量但逐筆完整、自成一體的 current Semantic Memory，以及輕量 `message_refs[]`；只有需要核對原句或問答脈絡時才以 `read_conversation_context(message_ref)` 深讀 canonical conversation。兩個 Tool 都只有一個 required string；scope／limit／filter／窗口／retry 由 Runtime 管理。第一版不另建 conversation summary。Isolated spike 只替 focused Semantic Memory 啟用 LangGraph Store semantic index／embedding；raw conversation semantic index 維持 deferred。canonical message ID 由可信 Runtime 建立；產品只開放 append，不讓模型／員工／Web 提供既有 ID 或 update／delete 歷史，也不加入 same-ID content comparison guard。名稱、最小結果視圖與 append-only exposed boundary 是 Caliburn mapping，不冒充 vendor 標準。 | Product Owner 2026-09-03 核准 read shape、isolated semantic-index mechanism、兩個 Tool 名稱、trial revision 2 與三次 bounded repair。Revision 2 在 metadata preflight 後因 Windows CLI 預設 `ProactorEventLoop` 不受 Psycopg 支援而停止；沒有 embedding／Luna／tool call 或模型語意輸出，結果維持 `FAIL_UNPROVEN`。其後只獲准的 event-loop repair 已以真 CLI＋Psycopg RED→GREEN 驗證。Product Owner 於 2026-09-04 核准並允許外部傳輸的 **live trial revision 3** 已執行一次：Store 與三個 embedding requests 成功（274 tokens、USD 0.00000548），但第一個 Luna chat request 在任何 model response／tool call 前收到 OpenRouter 404。官方 capability matrix 顯示 frozen `parallel_tool_calls: false`＋`require_parameters: true` 會排除全部 7 個 Luna endpoints；結果仍是 `FAIL_UNPROVEN`，不是 Memory 或 Luna 語意品質結果。官方、框架與實際證據見 [`specs/2026-09-03-memory-routing-canonical-read-and-isolated-spike-research.md`](specs/2026-09-03-memory-routing-canonical-read-and-isolated-spike-research.md) §3、§6、§13～§18 與[實驗報告](experiments/2026-09-03-memory-routing-canonical-read/report.md) §10。 | Isolated spike 證明自然語言 routing、canonical deep-read、scope isolation、成本或延遲不可接受；產品邊界無法阻止 caller 指定既有 ID；官方 primitive 改變；或新 live evidence 改變結論。 | Revision 3 已保存並停止。Owner review 是否另開 provider capability-routing contract design；不授權 revision 4、production、merge 或 push。 |

### 3.3 現有 Memory 文件如何使用

| 類別 | 文件 | 目前效力 |
|---|---|---|
| 產品能力基線 | [`specs/2026-09-01-framework-independent-memory-contract.md`](specs/2026-09-01-framework-independent-memory-contract.md) | `WORKING` requirement input；可用來判斷候選是否覆蓋效果，不授權 mechanism。 |
| 跨家官方研究 | [`specs/2026-08-30-agent-memory-landscape-and-decision-working-research.md`](specs/2026-08-30-agent-memory-landscape-and-decision-working-research.md) | Evidence library；需回到原始官方連結，不能把彙整文字直接當廠商內部事實。 |
| Caliburn 能力 mapping | [`specs/2026-08-30-caliburn-memory-requirements-mapping-working-research.md`](specs/2026-08-30-caliburn-memory-requirements-mapping-working-research.md) | Working analysis；產品需求輸入，不是 framework 決策。 |
| 最新機制重驗 | [`specs/2026-09-02-memory-inventory-versioning-provenance-and-minimal-slice-revalidation.md`](specs/2026-09-02-memory-inventory-versioning-provenance-and-minimal-slice-revalidation.md)、[`specs/2026-09-02-memory-implementation-mechanism-and-framework-consensus-audit.md`](specs/2026-09-02-memory-implementation-mechanism-and-framework-consensus-audit.md) | Evidence／diagnosis；供 `MEM-Q001` 定向核對。 |
| `MEM-Q001` 定向 reconciliation | [`specs/2026-09-03-memory-conversation-and-semantic-responsibility-reconciliation.md`](specs/2026-09-03-memory-conversation-and-semantic-responsibility-reconciliation.md) | **G3 Owner approved**；已成 Working Decision，但仍不授權 production 施工，須由 successor ADR 承接。 |
| `MEM-Q002` 定向 reconciliation | [`specs/2026-09-03-memory-similar-case-detail-and-consolidation-reconciliation.md`](specs/2026-09-03-memory-similar-case-detail-and-consolidation-reconciliation.md) | **G3 Owner approved**；已成 Working Decision，只裁決相似案例細節、共同理解、consolidation 與長距離回查責任，不授權 schema／搜尋索引或施工。 |
| `MEM-Q003` 定向 reconciliation | [`specs/2026-09-03-memory-canonical-conversation-search-read-reconciliation.md`](specs/2026-09-03-memory-canonical-conversation-search-read-reconciliation.md) | **G3 Owner approved**；已成 Working Decision，採 progressive disclosure＋canonical evidence deep-read，不授權 production schema、索引或 tool 施工。 |
| `MEM-Q004` read contract／isolated spike design | [`specs/2026-09-03-memory-routing-canonical-read-and-isolated-spike-research.md`](specs/2026-09-03-memory-routing-canonical-read-and-isolated-spike-research.md) | **G5 revision 3 complete／FAIL_UNPROVEN／Owner review**；§13 Runtime-owned ID、§14 SDK wrapper 與 §16 Windows CLI event-loop bounded repairs 保留；§18 記錄 frozen revision 3 的 capability-routing 404。read shape 與 index 邊界尚未被模型驗證，不授權 production。 |
| `MEM-Q004` isolated spike plan | [`plans/2026-09-03-memory-routing-canonical-read-isolated-spike.md`](plans/2026-09-03-memory-routing-canonical-read-isolated-spike.md)、[`specs/2026-09-03-memory-read-spike-consensus-and-framework-final-audit.md`](specs/2026-09-03-memory-read-spike-consensus-and-framework-final-audit.md) | **Revision 3 已保存／FAIL_UNPROVEN／停止**。Store 與 embedding 成功，chat route 在 model response 前失敗；不授權 revision 4 或 production。 |
| 候選切片與 framework 選擇 | [`specs/2026-09-02-memory-foundation-vertical-slice-design.md`](specs/2026-09-02-memory-foundation-vertical-slice-design.md)、[`specs/2026-09-02-memory-framework-selection-revalidation.md`](specs/2026-09-02-memory-framework-selection-revalidation.md) | **PAUSED**；其中 substrate／authority 結論與後續討論衝突，reconciliation 前不可施工。 |
| Design review packet | [`specs/2026-09-02-memory-foundation-design-review-packet.md`](specs/2026-09-02-memory-foundation-design-review-packet.md) | **PAUSED**；原核准只適用當時候選，不能越過後續重開的 `MEM-Q001`。 |
| Isolated spike plan | [`plans/2026-09-02-memory-foundation-isolated-spike.md`](plans/2026-09-02-memory-foundation-isolated-spike.md) | **PAUSED**；保留內容，不執行。待 `MEM-Q003` 與後續 Manager／Store design 收斂後重寫或 supersede。 |
| Proposed Memory ADR | [`adr/0071-revisable-work-understanding-context-and-review-provenance.md`](adr/0071-revisable-work-understanding-context-and-review-provenance.md)、[`adr/0072-qdrant-derived-memory-hybrid-retrieval-index.md`](adr/0072-qdrant-derived-memory-hybrid-retrieval-index.md) | 仍為 Proposed／deferred；不可當 production authority。 |

## 4. Memory 下一輪 preflight

```text
Topic ID: MEM-Q004
Current stage: G5 live trial revision 3 已保存為 FAIL_UNPROVEN；Owner review
Binding decisions: MEM-D000～MEM-D003、MEM-Q001～MEM-Q004
This turn's only blocking question:
  是否另開一個 bounded provider capability-routing contract design gate；目前不授權修正或 revision 4。
Already reviewed evidence:
  2026-09-03 MEM-Q001 已核准 Checkpointer 是 canonical conversation owner；
  2026-09-03 MEM-Q002 已核准 canonical conversation＋選擇性 consolidation，
  並把長距離案例 search／read 列為必要效果。
  2026-09-03 G2 已確認 OpenAI／Anthropic／Google／AWS／LangGraph
  均把 canonical event list/read 與 semantic retrieval 分離；
  補驗 OpenAI Codex／Agents SDK 與 Anthropic 公開 read path 後，
  Product Owner 已核准 Semantic Memory routing＋canonical evidence deep-read；
  不再預設建立 raw-message search_text 副本；
  LangMem 官方有 create_search_memory_tool，LangGraph Store 也有 namespace-scoped search，
  但自然語言 similarity search 必須配置 embedding index；
  Product Owner 已核准 isolated spike 只替 focused Semantic Memory 啟用該 index，
  raw conversation semantic index 仍 deferred；
  LangGraph Checkpointer 可取 latest state／state history，沒有公開的 message-id 內容搜尋 primitive；
  Product Owner 已核准 search_semantic_memory(query) 與
  read_conversation_context(message_ref)；兩者只暴露一個 required string，
  其餘已知 scope／policy 由 ToolRuntime 注入；
  框架已覆蓋 typed validation、tool loop、Store search、retry 與 transient context projection，
  只有 exact-scope guard、canonical message window 與安全結果整形保留為薄 adapter。
  最終稽核已確認 read-tool graph 應為不掛 checkpointer 的單次暫態 execution，
  不把 tool chatter 寫回 80 則 synthetic canonical conversation；
  live prompt 不再直接命令工具順序，而由需要精確原話的任務驗證 search／deep-read 選擇；
  expected tool errors 統一走一個 typed ToolNode handler；
  provider 價格無法建立保守上界時不發第一個 paid call；
  LangGraph add_messages 對 same-ID 的官方語意是 update／replace，不是 collision error；
  Product Owner 已核准 Runtime-owned fresh ID＋append-only exposed boundary，且不增加 content comparison guard；
  2026-09-03 bounded repair 已依 TDD 完成：RED 命中舊 prior-state read，GREEN 後 PostgreSQL read path 17 passed，
  完整 isolated deterministic suite 58 passed、1 個 optional LangMem characterization skipped；
  獨立 review 發現並修正兩處 stale transport-idempotency 文字，scoped re-review verdict ready、無剩餘 finding；
  2026-09-03 唯一獲准 live attempt 在 endpoint metadata preflight 停止：OpenRouter SDK 0.10.8
  的 `endpoints.list_async()` 回傳 `operations.ListEndpointsResponse(data=...)`，但隔離 smoke 實驗執行器誤讀
  `response.endpoints`；官方 HTTP contract 同樣把 endpoints 放在 `data.endpoints`。
  此次已發免費 metadata requests，但尚未發 embedding／Luna request、沒有語意輸出，也未產生 trial receipt。
  版本稽核另確認：0.10.8 並非 2026-09-03 最新版，但不是本次錯誤原因；隔離載入最新
  OpenRouter SDK 1.1.113 後，`operations.ListEndpointsResponse` 仍只有 `data`，payload 才有
  `endpoints`。目前 lock 停在 0.10.8，是因 `langchain-openrouter` 0.2.7 要求
  `openrouter>=0.9.2,<1.0.0`，而後續 0.11.46 與最新 1.1.113 均要求
  `pydantic>=2.11.2,<2.13`，與 app 明確固定的 Pydantic 2.13.4 不相容；最新
  `langchain-openrouter` 0.2.8 仍要求 `openrouter<1.0.0`。dependency upgrade 是另一個相容性議題，
  不應混入這次 bounded 實驗執行器 repair。
  bounded repair 以 pinned SDK 真實 `ListEndpointsResponse` 完成有效 RED→GREEN：RED 精確命中
  `response.endpoints` 的 `AttributeError`，修正為 `response.data.endpoints` 後 targeted test 1 passed；
  整份 live-smoke dry-run 27 passed，完整 isolated deterministic suite 59 passed、1 optional skip，
  再以臨時 LangMem 0.0.30 執行被 skip 的 characterization 為 1 passed。未呼叫真實 LLM／embedding。
  2026-09-03 Product Owner 隨後明確核准 trial revision 2；這是 revision 1 plumbing failure 後的
  一次新執行授權，不是無界 retry，也不能外推為完整品質 eval。
  trial revision 2 已依 frozen contract 執行：metadata preflight 完成後，Psycopg 在第一個 async
  connection 拒絕 Windows 預設 ProactorEventLoop。程序 exit 1、2,749 ms；沒有 embedding、
  Luna、tool call、模型語意輸出或 attempt-specific DB write，正常 receipt 未產生。
  Psycopg 官方要求 Windows 使用 SelectorEventLoop；Python 3.13 官方建議以 asyncio.run 的
  loop_factory 配置。DB-only、零 provider request 診斷已在同環境成功。
  2026-09-03 Product Owner review report 後只核准 event-loop bounded repair 與 regression test。
  測試先切回 Windows 預設 Proactor，從真 CLI main 進入實際 Psycopg identity read；有效 RED
  精確重現 revision 2 InterfaceError。Windows asyncio.run 指定 Selector loop 後 targeted test 1 passed，
  整份 live-smoke deterministic 測試 28 passed，完整 isolated suite 60 passed、1 optional skip；
  沒有再次呼叫 provider。
  因 plan §5.2 只明寫「第一個 provider call 前」可把 plumbing defect 升 revision，不能自行把本次情況擴張解讀為可修後重跑。
  2026-09-04 Product Owner 以「OK／繼續」明確核准下一個 gate：live trial revision 3。
  它沿用完全相同的 case、prompt、rubric、Luna medium、embedding model、call/tool/token/cost caps
  與零 retry；只可執行一次，不論 PASS／FAIL／外部錯誤均保存並停止。
  2026-09-04 付款前 preflight 為 60 passed、1 optional skip；三個 frozen hash、專用 DB identity、
  key presence 與 revision 3 path 均通過。外部執行在 process 啟動前被安全 gate 拒絕，因現有授權
  未逐字涵蓋傳送到 OpenRouter；沒有 provider request、費用或 trial artifact。
  Product Owner 隨後明確回覆「同意」，允許將上述匿名 synthetic payload 傳送至 OpenRouter，
  並重申若有新問題須先停止、依既定流程提出討論與研究。
  revision 3 已依 frozen contract 執行一次：Psycopg、Store 與三個 embedding requests 成功；
  embedding 共 274 tokens、已知費用 USD 0.00000548。第一個 Luna chat request 在回傳任何
  model response／tool call 前收到 OpenRouter `NotFoundResponseError`；resolved provider／model
  與 chat usage 均未產生，六項 rubric 全為 NOT_EVALUATED。
  frozen HTTP payload 由 deterministic boundary test 證明含 `parallel_tool_calls: false` 與
  `provider.require_parameters: true`。2026-09-04 OpenRouter 公開 catalog 顯示 Luna 有 7 個 endpoints，
  支援 tools、reasoning 與 max_completion_tokens，但全部未宣告 parallel_tool_calls；官方規則會在
  require_parameters=true 時排除未支援所有 request parameters 的 provider。這充分解釋本次零
  eligible endpoint 的 404；receipt 未保留原始 404 body，故不杜撰其逐字訊息。
Out of scope / parking lot:
  production Semantic Memory schema、Manager prompt／mutation schema、Reference RAG、production migration、
  UI、JD 編輯器、跨 JD Memory、raw-message semantic index；
  production embedding model／top-k／threshold／pgvector／Qdrant；
  HTTP／run 重送的冪等 contract、production 並行 writer 與完整 canonical payload identity 仍不在本輪裁決。
```

`MEM-Q003` 已完成；`MEM-Q004` 的 G4 read shape、isolated semantic-index mechanism、Tool 名稱與最小 contract 已收斂，但 live 模型能力仍未證明。Revision 3 已通過 Windows CLI／Store／embedding，卻被 frozen provider capability filter 在模型回應前拒絕，結果為 `FAIL_UNPROVEN`。下一步只做 Owner review，決定是否另開 bounded routing-contract design；目前不授權修正、revision 4、production、merge 或 push。
