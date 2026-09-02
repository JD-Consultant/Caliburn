# Caliburn Current Decision Register

- 最後核對：**2026-09-03**
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
| 候選切片與 framework 選擇 | [`specs/2026-09-02-memory-foundation-vertical-slice-design.md`](specs/2026-09-02-memory-foundation-vertical-slice-design.md)、[`specs/2026-09-02-memory-framework-selection-revalidation.md`](specs/2026-09-02-memory-framework-selection-revalidation.md) | **PAUSED**；其中 substrate／authority 結論與後續討論衝突，reconciliation 前不可施工。 |
| Design review packet | [`specs/2026-09-02-memory-foundation-design-review-packet.md`](specs/2026-09-02-memory-foundation-design-review-packet.md) | **PAUSED**；原核准只適用當時候選，不能越過後續重開的 `MEM-Q001`。 |
| Isolated spike plan | [`plans/2026-09-02-memory-foundation-isolated-spike.md`](plans/2026-09-02-memory-foundation-isolated-spike.md) | **PAUSED**；保留內容，不執行。待 `MEM-Q003` 與後續 Manager／Store design 收斂後重寫或 supersede。 |
| Proposed Memory ADR | [`adr/0071-revisable-work-understanding-context-and-review-provenance.md`](adr/0071-revisable-work-understanding-context-and-review-provenance.md)、[`adr/0072-qdrant-derived-memory-hybrid-retrieval-index.md`](adr/0072-qdrant-derived-memory-hybrid-retrieval-index.md) | 仍為 Proposed／deferred；不可當 production authority。 |

## 4. Memory 下一輪 preflight

```text
Topic ID: MEM-Q003
Current stage: G3 complete → G4／G5 design and isolated spike
Binding decisions: MEM-D000～MEM-D003、MEM-Q001～MEM-Q003
This turn's only blocking question:
  無；MEM-Q003 已裁決。下一工作段只收斂並驗證核准後的最小 read path，
  不重新比較 conversation-search 架構。
Already reviewed evidence:
  2026-09-03 MEM-Q001 已核准 Checkpointer 是 canonical conversation owner；
  2026-09-03 MEM-Q002 已核准 canonical conversation＋選擇性 consolidation，
  並把長距離案例 search／read 列為必要效果。
  2026-09-03 G2 已確認 OpenAI／Anthropic／Google／AWS／LangGraph
  均把 canonical event list/read 與 semantic retrieval 分離；
  補驗 OpenAI Codex／Agents SDK 與 Anthropic 公開 read path 後，
  Product Owner 已核准 Semantic Memory routing＋canonical evidence deep-read；
  不再預設建立 raw-message search_text 副本。
Out of scope / parking lot:
  semantic Memory schema、Manager prompt／tool schema、Reference RAG、production migration、
  UI、JD 編輯器、跨 JD Memory；方案 B 的 smoke 失敗前，不先決定 embedding、pgvector 或 Qdrant。
```

`MEM-Q003` 已完成並寫回。下一步才收斂 semantic Memory 的正式資料表徵、Manager contract 與 isolated spike；這可避免先寫索引或 schema，再替機制尋找產品理由。
