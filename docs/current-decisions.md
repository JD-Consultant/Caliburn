# Caliburn Current Decision Register

- 最後核對：**2026-09-03**
- 狀態：**目前決策與閱讀路由的唯一入口**
- 流程：[`decision-process.md`](decision-process.md)

> **LLM-Q019隔離實驗閱讀入口（2026-09-08）：**本worktree下方登記是建立分支時的歷史快照；這條實驗線持續更新的register位於[主repo目前決策](../../../docs/current-decisions.md)。本輪[CT19](specs/2026-09-08-ct19-routing-regression.md)候選失敗並撤回、G8仍OPEN。不要以本頁下方舊日期或缺少CT19誤判新決策未記錄；production規則仍須循正式ADR／implementation gate。

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
| `MEM-Q004` | `WORKING` | G4 read contract 採 progressive disclosure：先由小型、可重建的 Semantic Memory 導覽定向；需要更多內容時，模型使用 `search_semantic_memory(query)`，Runtime 在目前 JD／文件 scope 內回傳少量但逐筆完整、自成一體的 current Semantic Memory，以及輕量 `message_refs[]`；只有需要核對原句或問答脈絡時才以 `read_conversation_context(message_ref)` 深讀 canonical conversation。兩個 Tool 都只有一個 required string；scope／limit／filter／窗口／retry 由 Runtime 管理。第一版不另建 conversation summary。Isolated spike 只替 focused Semantic Memory 啟用 LangGraph Store semantic index／embedding；raw conversation semantic index 維持 deferred。名稱與最小結果視圖是 Caliburn mapping，不冒充 vendor 標準。 | Product Owner 2026-09-03 核准 read shape、isolated semantic-index mechanism、兩個 Tool 名稱及 Revision 2 G5 隔離實驗；官方、框架及 pinned contract 稽核見 [`specs/2026-09-03-memory-routing-canonical-read-and-isolated-spike-research.md`](specs/2026-09-03-memory-routing-canonical-read-and-isolated-spike-research.md) §3、§6。 | Isolated spike 證明自然語言 routing、canonical deep-read、scope isolation、成本或延遲不可接受；或官方 primitive 改變。 | 執行 G5 隔離實驗並回到 report review；不授權 production。 |

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
| `MEM-Q004` read contract／isolated spike design | [`specs/2026-09-03-memory-routing-canonical-read-and-isolated-spike-research.md`](specs/2026-09-03-memory-routing-canonical-read-and-isolated-spike-research.md) | **G4 complete／G5 authorized**；read shape、focused Semantic Memory semantic index、兩個 Tool 名稱與最小 contract 已核准，raw conversation index 維持 deferred；只授權隔離 spike，不授權 production。 |
| `MEM-Q004` isolated spike plan | [`plans/2026-09-03-memory-routing-canonical-read-isolated-spike.md`](plans/2026-09-03-memory-routing-canonical-read-isolated-spike.md)、[`specs/2026-09-03-memory-read-spike-consensus-and-framework-final-audit.md`](specs/2026-09-03-memory-read-spike-consensus-and-framework-final-audit.md) | **Revision 2／G5 authorized**；已從產品流程、責任層、Context、Tool contract、framework wiring 到實驗參數逐層分類，並修正持久 conversation 與暫態 tool state 混層、強迫 tool call、重疊 error handling及價格上界四項 finding；Product Owner 於 2026-09-03 核准執行，附帶「由廣到細均以可追溯共識為先、未討論自訂不得冒充共識」條件。 |
| 候選切片與 framework 選擇 | [`specs/2026-09-02-memory-foundation-vertical-slice-design.md`](specs/2026-09-02-memory-foundation-vertical-slice-design.md)、[`specs/2026-09-02-memory-framework-selection-revalidation.md`](specs/2026-09-02-memory-framework-selection-revalidation.md) | **PAUSED**；其中 substrate／authority 結論與後續討論衝突，reconciliation 前不可施工。 |
| Design review packet | [`specs/2026-09-02-memory-foundation-design-review-packet.md`](specs/2026-09-02-memory-foundation-design-review-packet.md) | **PAUSED**；原核准只適用當時候選，不能越過後續重開的 `MEM-Q001`。 |
| Isolated spike plan | [`plans/2026-09-02-memory-foundation-isolated-spike.md`](plans/2026-09-02-memory-foundation-isolated-spike.md) | **PAUSED**；保留內容，不執行。待 `MEM-Q003` 與後續 Manager／Store design 收斂後重寫或 supersede。 |
| Proposed Memory ADR | [`adr/0071-revisable-work-understanding-context-and-review-provenance.md`](adr/0071-revisable-work-understanding-context-and-review-provenance.md)、[`adr/0072-qdrant-derived-memory-hybrid-retrieval-index.md`](adr/0072-qdrant-derived-memory-hybrid-retrieval-index.md) | 仍為 Proposed／deferred；不可當 production authority。 |

## 4. Memory 下一輪 preflight

```text
Topic ID: MEM-Q004
Current stage: G5 authorized；isolated spike plan revision 2 開始在隔離 worktree 執行
Binding decisions: MEM-D000～MEM-D003、MEM-Q001～MEM-Q004
This turn's only blocking question:
  無；下一個 blocking gate 是實驗 report 是否支持後續設計，須待 G5 完成後由 Product Owner review。
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
  provider 價格無法建立保守上界時不發第一個 paid call。
Out of scope / parking lot:
  production Semantic Memory schema、Manager prompt／mutation schema、Reference RAG、production migration、
  UI、JD 編輯器、跨 JD Memory、raw-message semantic index；
  production embedding model／top-k／threshold／pgvector／Qdrant 仍不在本輪裁決。
```

`MEM-Q003` 已完成；`MEM-Q004` 的 read shape、isolated semantic-index mechanism、Tool 名稱與最小 contract 均已完成 G4 收斂。Product Owner 已於 2026-09-03 核准 [`isolated spike plan`](plans/2026-09-03-memory-routing-canonical-read-isolated-spike.md) Revision 2 進入 G5；本次只可在隔離 worktree 產生實驗證據，完成後回到 report review，不授權 production、merge 或 push。
