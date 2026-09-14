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
| `GOV-Q004` | `OPEN` | 候選試行：短 current index＋一份 coherent Working Design＋按需 Evidence＋ADR／Plan 分流；Program map 只在確有多條 workstream 時選用。 | [跨家官方研究與完整方案](specs/2026-09-04-large-program-documentation-and-decision-governance-research.md)。 | 試行仍造成重複研究、長文失控、矛盾 active 文件或緊密決策被切碎。 | 先在 `LLM-Q001` 試行；尚未 supersede `GOV-D002` 或修改 Accepted process。 |

## 3. Memory 主題目前狀態

### 3.1 現在仍有效的邊界

| ID | 狀態 | 目前結論 | Authority／依據 | 重開條件 | 下一個 gate |
|---|---|---|---|---|---|
| `MEM-D000` | `ACCEPTED` | Production 仍依現行 code、`AGENTS.md` 與 Accepted ADR 0060；2026-08-30～09-02 的 Memory 研究沒有自行改變 production authority。 | [`adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md`](adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md)、現行 code。 | Accepted successor ADR 通過且對應 implementation／verification 完成。 | 在此之前只允許 research／design／明確隔離 spike。 |
| `MEM-D001` | `WORKING` | Memory 的唯一產品目的，是讓長訪談後的 LLM 仍能完整理解員工工作與必要細節，支援產出、修訂及最終檢查高品質 JD；Memory 本身不是產品目的，也不操控 JD。 | [`specs/2026-09-01-framework-independent-memory-contract.md`](specs/2026-09-01-framework-independent-memory-contract.md) 的產品效果；Owner 多輪確認。 | 完美 JD 的產品目的或 Memory 必要效果被明確翻案。 | 作為候選機制與測試的效果門檻。 |
| `MEM-D002` | `WORKING` | 一名員工對應一份隔離文件與一份 JD；第一版每份 JD 只有一個主要持續訪談 thread，長期 Memory 以 JD／document 為 scope，不由 thread 擁有，也不跨 JD 共用。未來若有證據支持，同一 JD 可增加多個 threads 並共用該 JD Memory。 | Owner 明確裁決；[`specs/2026-08-30-caliburn-memory-requirements-mapping-working-research.md`](specs/2026-08-30-caliburn-memory-requirements-mapping-working-research.md)；`MEM-Q005` 於 2026-09-04 G3 核准。 | 產品範圍加入同一 JD 多 conversation、跨員工／跨 JD 知識共享，或代表性實測推翻目前 cardinality。 | 約束 scope／namespace 候選；第一版不展開多 thread 功能。 |
| `MEM-D003` | `WORKING` | 日常回合不必把全部長期 Memory 放進 prompt；但最後全面製作／檢查 JD 時，必須具備可驗證地處理該 JD 全部有效 Memory 的能力。所有員工工作都不得因摘要或召回策略而永久遺失。 | [`specs/2026-09-01-framework-independent-memory-contract.md`](specs/2026-09-01-framework-independent-memory-contract.md) §3.4–3.5、M3／M9。 | 官方能力或代表性實驗證明需採不同效果契約。 | 納入 `MEM-Q001`～`MEM-Q003` 與後續 isolated smoke 的驗收情境。 |

### 3.2 Memory reconciliation 決策

| ID | 狀態 | 目前決策／待決問題 | Authority／階段 | 重開條件／已有資料 | 下一個 gate |
|---|---|---|---|---|---|
| `MEM-Q001` | `WORKING` | 採用三層責任：LangGraph Checkpointer 保存每份 JD 的完整員工↔顧問 conversation 與 graph/run/interrupt state；PostgreSQL Store 保存可修訂 semantic Memory collection；Memory manager 只產生 extraction／consolidation 候選；每輪 model context 非破壞性地由兩層資料有界組裝。第一版不建立重複 employee-source 文字 leaf；如日後需要 provenance，只引用 canonical message ID。 | Product Owner 2026-09-03 核准；完整證據與三方案比較見 [`specs/2026-09-03-memory-conversation-and-semantic-responsibility-reconciliation.md`](specs/2026-09-03-memory-conversation-and-semantic-responsibility-reconciliation.md)。 | 真 PostgreSQL contract 顯示長 thread 儲存／延遲不可接受；產品加入獨立 event query/export/retention；官方 primitive 改變；或 Owner 改變一 JD／一 thread 邊界。 | 持續約束 `MEM-Q002`／`MEM-Q003` 與 successor ADR；production 現在仍禁止依此施工。 |
| `MEM-Q002` | `WORKING` | 採 canonical conversation＋選擇性 consolidation：全部案例原始對話耐久保留；重複資訊 no-op；同主題通用新細節 update；需要獨立搜尋／修訂且會影響 JD 的重要差異才 add focused Memory；更正 revise、未解衝突保留兩邊；不採每案例固定一筆。長距離案例指涉必須可按需回查 canonical conversation。 | Product Owner 2026-09-03 核准方案 C；完整官方證據、三方案、A／B／更正情境與八項驗收門檻見 [`specs/2026-09-03-memory-similar-case-detail-and-consolidation-reconciliation.md`](specs/2026-09-03-memory-similar-case-detail-and-consolidation-reconciliation.md)。 | 代表性驗證顯示重要案例差異會靜默遺失、同義案例造成近線性膨脹、長距離原始片段無法找回；官方 primitive 改變；或 Owner 改變產品效果。 | 約束 `MEM-Q003`；production 仍須 successor ADR，現在不授權 schema、索引或施工。 |
| `MEM-Q003` | `WORKING` | 採修正後方案 B：Checkpointer 保存 canonical conversation；Semantic Memory／小型導覽先 routing，按需依 canonical message reference 回讀原始問答；未命中才做有界 exact scan／澄清。第一版不替每則 raw message 建 semantic index；只有代表性 smoke 證明重要久遠細節無法找回，才重開 derived raw-conversation／hybrid index。 | Product Owner 2026-09-03 核准；五家官方共同邊界、OpenAI Codex／Agents SDK 與 Anthropic 實際 read path、三方案與限制見 [`specs/2026-09-03-memory-canonical-conversation-search-read-reconciliation.md`](specs/2026-09-03-memory-canonical-conversation-search-read-reconciliation.md)。 | 官方新增原生 Checkpointer conversation search；isolated spike 證明 recall、成本／延遲不可接受；或 Owner 改變完整細節找回要求。 | **G4／G5：**收斂 Semantic Memory routing、canonical reference／read contract 與 isolated spike；production 仍須 successor ADR。 |
| `MEM-Q004` | `WORKING` | G4 read contract 採 progressive disclosure：先由小型、可重建的 Semantic Memory 導覽定向；需要更多內容時，模型使用 `search_semantic_memory(query)`，Runtime 在目前 JD／文件 scope 內回傳少量但逐筆完整、自成一體的 current Semantic Memory，以及輕量 `message_refs[]`；只有需要核對原句或問答脈絡時才以 `read_conversation_context(message_ref)` 深讀 canonical conversation。兩個 Tool 都只有一個 required string；scope／limit／filter／窗口／retry 由 Runtime 管理。第一版不另建 conversation summary。Isolated spike 只替 focused Semantic Memory 啟用 LangGraph Store semantic index／embedding；raw conversation semantic index 維持 deferred。canonical message ID 由可信 Runtime 建立；產品只開放 append，不讓模型／員工／Web 提供既有 ID 或 update／delete 歷史，也不加入 same-ID content comparison guard。名稱、最小結果視圖與 append-only exposed boundary 是 Caliburn mapping，不冒充 vendor 標準。 | Product Owner 2026-09-03 核准 read shape、isolated semantic-index mechanism、兩個 Tool 名稱、trial revision 2 與三次 bounded repair。Revision 2 在 metadata preflight 後因 Windows CLI 預設 `ProactorEventLoop` 不受 Psycopg 支援而停止；沒有 embedding／Luna／tool call 或模型語意輸出，結果維持 `FAIL_UNPROVEN`。其後只獲准的 event-loop repair 已以真 CLI＋Psycopg RED→GREEN 驗證。Product Owner 於 2026-09-04 核准並允許外部傳輸的 **live trial revision 3** 已執行一次：Store 與三個 embedding requests 成功（274 tokens、USD 0.00000548），但第一個 Luna chat request 在任何 model response／tool call 前收到 OpenRouter 404。官方 capability matrix 顯示 frozen `parallel_tool_calls: false`＋`require_parameters: true` 會排除全部 7 個 Luna endpoints；結果仍是 `FAIL_UNPROVEN`，不是 Memory 或 Luna 語意品質結果。官方、框架與實際證據見 [`specs/2026-09-03-memory-routing-canonical-read-and-isolated-spike-research.md`](specs/2026-09-03-memory-routing-canonical-read-and-isolated-spike-research.md) §3、§6、§13～§18 與[實驗報告](experiments/2026-09-03-memory-routing-canonical-read/report.md) §10。 | Isolated spike 證明自然語言 routing、canonical deep-read、scope isolation、成本或延遲不可接受；產品邊界無法阻止 caller 指定既有 ID；官方 primitive 改變；或新 live evidence 改變結論。 | Revision 3 已保存並停止。`LLM-Q001` 已另開 provider capability／invocation lifecycle 研究；Memory 維持暫停，不授權 revision 4、production、merge 或 push。 |
| `MEM-Q005` | `WORKING`；G3 Owner approved | 採方案 A：第一版每份 JD 只有一個主要 conversation thread；長期 Memory 以 JD／document 為 scope，而非由 thread 擁有。未來同一 JD 真有需要時，多個 threads 可共用同一份 Memory；目前不建立多 thread 產品功能。 | Product Owner 於 2026-09-04 核准。OpenAI、Anthropic 與 LangGraph 均把 conversation／session／thread state 和長期 Memory 分開，且支援多個 conversations 使用同一長期 Memory；官方沒有要求單一聊天室產品必須預先建立多 thread。三方案與來源見 [`specs/2026-09-04-jd-memory-and-conversation-thread-cardinality-working-design.md`](specs/2026-09-04-jd-memory-and-conversation-thread-cardinality-working-design.md)。 | 同一 JD 出現多入口、平行 specialist conversations、主管審核獨立 conversation，或單一 thread 實測無法滿足長訪談。 | 已完成；持續約束 thread／Memory scope，不展開多 thread UI／API／routing／merge／並行寫入。 |

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

## 4. LLM／Agent 系統目前狀態

### 4.1 目前決策

| ID | 狀態 | 本輪唯一問題 | 已完成證據／選項 | 下一個 gate |
|---|---|---|---|---|
| `LLM-Q014` | `WORKING`；G3 parent direction approved；G4.1 待 Owner | 採方案 A 的父層方向：對人回覆走 canonical assistant message；需要讀寫應用狀態的 machine effects 走 framework-native Tool；可由程式推導的狀態不讓模型填；structured output 只保留給確有單一 machine-readable artifact 的窄任務。跨廠共識只到責任分界；「Caliburn 採 Tool-first」是產品選擇，不冒充廠商共同架構。G4.1 已完成 Semantic Memory writer／timing 的定向重驗，建議沿用一套 Manager 的 dependency-aware sync／background 排程，並將 Manager mutation 視為窄 structured artifact，不塞入主顧問 final schema。 | Product Owner 於 2026-09-04 核准父層方向；G4.1 的 OpenAI／Anthropic／Google／AWS／LangChain／LangMem 官方事實、非共識、三方案與 Caliburn mapping 見 [`specs/2026-09-04-llm-machine-effects-responsibility-working-design.md`](specs/2026-09-04-llm-machine-effects-responsibility-working-design.md) §2。 | **G4.1 Owner gate：**確認 Semantic Memory 方案 C 與 responsibility mapping；未核准前不進 Tool schema、排程實作或下一個 machine effect。現在不施工。 |
| `LLM-Q013` | `WORKING`；G3 Owner approved | 採方案 B：一般訪談問題只存在 canonical assistant message；只有會影響未來 JD 的未解工作資訊，才透過既有 content-only Semantic Memory 保存。第一版不建立專用 question schema、pending state 或 answer／resume lifecycle；未來問題卡只可作 UI presentation。 | Product Owner 於 2026-09-04 明確回覆「同意」。已核對 OpenAI Responses／最新 model guidance、Anthropic Messages／stop reasons／structured outputs、LangChain Messages／Agents／Structured Output，以及既有 Memory contract 與現行 code duplication。官方事實、Caliburn 推論、三方案與驗收情境見 [`specs/2026-09-04-normal-turn-question-and-unresolved-ambiguity-contract-working-design.md`](specs/2026-09-04-normal-turn-question-and-unresolved-ambiguity-contract-working-design.md)。 | 另開 machine-effects 最小契約；收斂後以 successor ADR 精確取代 ADR 0060 的 required-clarification 部分。現在不施工。 |
| `LLM-Q012` | `WORKING`；G3 Owner approved | 採方案 B：第一版沒有員工輸入型 unfinished workflow。所有訪談問題都以 normal assistant completion 結束；員工下一則文字啟動新的 bounded invocation。未解歧義保存為 conversation／Semantic Memory，而不是 pending execution；JD review、direct edit、刪除／匯出確認與 retry 保持各自 application lifecycle。第一版不建立模型可觸發的 ask-user interrupt path。 | Product Owner 於 2026-09-04 明確回覆「同意」。OpenAI、Anthropic、Google、LangGraph／LangChain、Microsoft 官方判準、完整情境 inventory、現行 code fact 與 ADR 衝突見 [`specs/2026-09-04-first-version-unfinished-workflow-inventory-working-design.md`](specs/2026-09-04-first-version-unfinished-workflow-inventory-working-design.md)。 | G4 定義 normal-turn question 的最小 contract 與受控替換設計；其後以 successor ADR 精確取代 ADR 0060 的 required-clarification 部分。現在不施工。 |
| `LLM-Q011` | `WORKING`；G3 Owner approved；application resolved by `LLM-Q012` | 採方案 C：員工訪談問題預設 normal completion；只有產品／Runtime 明確宣告「取得特定外部輸入後必須自動接續同一 workflow」的 unfinished workflow，才建立 durable external-input request。它可包含 request-info、approval 或 Tool result；不能只因問題重要或使用 Tool 就 pause。`LLM-Q012` 已確認第一版沒有代表性 workflow，因此不向模型暴露通用 ask-user interrupt Tool。 | Product Owner 於 2026-09-04 明確回覆「同意」。已核對 OpenAI Responses conversation／required-input continuation、Anthropic normal turn／`AskUserQuestion`／Managed Agents、Google Workflow Builder request-info／approval、LangGraph interrupts／double texting，以及 Microsoft Agent Framework；事實、三方案與 Caliburn 推論見 [`specs/2026-09-04-conversational-question-vs-durable-interrupt-revalidation.md`](specs/2026-09-04-conversational-question-vs-durable-interrupt-revalidation.md)。 | 約束 G4 normal-turn contract；未來只有出現具體 unfinished workflow 才重開 durable external-input request。 |
| `LLM-Q010` | `SUPERSEDED`；first-version interview only | 原暫時方案以「訪談澄清透過專用 confirmation Tool」為父前提；`LLM-Q012` 已決定第一版沒有該 interrupt path，因此 trigger instruction 與 Tool visibility 不再作第一版實作依據。 | 原研究與來源保留於 [`specs/2026-09-04-required-confirmation-tool-trigger-instructions-working-design.md`](specs/2026-09-04-required-confirmation-tool-trigger-instructions-working-design.md)；`LLM-Q012` 記錄 supersession 理由。 | 未來加入具體 unfinished workflow 時，依該 workflow 重新研究，不直接復活舊 trigger。 |
| `LLM-Q009` | `SUPERSEDED`；first-version interview only | 原 confirmation Tool／一次一題 interrupt schema 不進第一版。選項＋自由文字仍可作 normal-turn UI／output 能力，但不代表 pending run。 | 原研究與來源保留於 [`specs/2026-09-04-required-confirmation-tool-minimal-contract-working-design.md`](specs/2026-09-04-required-confirmation-tool-minimal-contract-working-design.md)；`LLM-Q012` 已選 normal completion。 | G4 另定義最小 normal-turn question contract；不得沿用 interrupt lifecycle 欄位。 |
| `LLM-Q008` | `SUPERSEDED`；first-version interview only | 第一版不把 blocking question 映射成模型 Tool 內 `interrupt()`；問題的重要性、卡片形式或 Tool 使用都不創造 unfinished workflow。 | 原研究與來源保留於 [`specs/2026-09-04-required-confirmation-model-control-channel-working-design.md`](specs/2026-09-04-required-confirmation-model-control-channel-working-design.md)；官方與產品盤點見 `LLM-Q011`／`LLM-Q012`。 | 未來只有具體 workflow 能說明 continuation／取消／新訊息語意時才重開。 |
| `LLM-Q007` | `SUPERSEDED`；first-version interview only | LangGraph interrupt 仍是成熟 framework capability，但第一版訪談沒有需要恢復同一 invocation 的情境，因此不建立 required-confirmation pause/resume path。 | 原研究與來源保留於 [`specs/2026-09-04-required-confirmation-framework-pause-resume-working-design.md`](specs/2026-09-04-required-confirmation-framework-pause-resume-working-design.md)；`LLM-Q012` 的 inventory 找不到代表性 unfinished workflow。 | 未來加入需批准後執行的 Tool action或固定 request-info workflow 才重開。 |
| `LLM-Q006` | `WORKING`；G3 Owner approved；application resolved by `LLM-Q012` | 普通訪談問題正常完成，員工可稍後回答、改談別題或關閉後再回來。第一版沒有員工輸入型 durable interrupt；只有未來明確新增、答案後須自動接續的 workflow 才可能使用。 | Anthropic／Google 證明 request-info 可以 interrupt，但 `LLM-Q012` 逐項盤點後確認第一版沒有此需求；不能只因問題重要、顯示問題卡或模型使用 Tool 就建立 pending execution。 | 約束 G4 normal-turn contract；未來符合 `LLM-Q012` 重開條件才重新設計 interrupt。 |
| `LLM-Q005` | `WORKING`；G3 Owner approved | 採方案 A：正常完成、等待員工、模型可修正錯誤、暫時性 retry、達限／取消與不可恢復失敗，依「誰能恢復」映射到 framework-native completion、durable interrupt、Tool error、allowlisted bounded retry、limit／cancel 與 terminal failure；最薄產品 boundary 只做安全投影，不能把它們混成同一個「分析錯誤，請重試」。 | Product Owner 於 2026-09-04 核准；OpenAI／Anthropic／LangChain／LangGraph 證據、三方案與邊界見 [`specs/2026-09-04-llm-invocation-outcome-and-error-boundary-working-design.md`](specs/2026-09-04-llm-invocation-outcome-and-error-boundary-working-design.md)。 | 官方 API 改變、代表性情境證明分類不足、跨 provider 無法穩定映射，或 Owner 改變員工體驗。 | 進入 `LLM-Q006`；不授權具體 enum、retry 數字、UI、schema 或 production。 |
| `LLM-Q004` | `WORKING`；G3 Owner approved | 採方案 A：第一版一份 JD 一個主要持久 thread；每則被接納的新員工訊息啟動一次有界 logical invocation，內部可有多次 model／Tool step；必要輸入可以 checkpoint 後 resume；第一版不採 active steering，也不把每輪硬拆成固定 stages。依 `MEM-Q005`，一個主要 thread 是目前產品 cardinality，不是 Memory ownership。 | Product Owner 於 2026-09-04 核准。OpenAI／Anthropic／LangChain／LangGraph 均區分持久 conversation／session／thread 與一次 run，並提供 bounded loop、stream、pause／resume 及分類失敗的成熟 primitive。見[有界 Invocation Working Design](specs/2026-09-04-llm-bounded-invocation-lifecycle-working-design.md)與[`MEM-Q005`](specs/2026-09-04-jd-memory-and-conversation-thread-cardinality-working-design.md)。 | `LLM-Q005` 已完成，進入 `LLM-Q006`。若後續 Tool／Memory／JD authority、必要澄清、成本實測或代表性情境符合文件 §6，明確重開；目前不授權 schema、spike 或 production 施工。 |
| `LLM-Q003` | `WORKING`；G3 Owner approved | 第一版採方案 A：以一個 `create_agent` compiled graph 作唯一根 runtime；第一版不再包自訂 `StateGraph`，也不以 Functional API 作根 workflow。這是最小方向，不把後續細節永久寫死。 | LangChain 官方將 `create_agent` 定位為 production-ready、建於 LangGraph 的標準 agent loop；明確 Graph 適用複雜分支、共享 state 與平行匯流；Functional API 適用既有程序式、線性或簡單分支。依 `S1`～`S7` 與 P3，A 最貼合動態單一顧問，且日後仍能將 agent 放入窄 StateGraph 或 Functional batch workflow。見[最小 Runtime Working Design](specs/2026-09-04-langchain-langgraph-minimal-runtime-shape-working-design.md)。 | 進入 `LLM-Q004`。若代表性情境、官方 API 或後續細節證明需要固定複雜拓撲，依文件 §8 重開；目前仍不授權 schema、spike 或 production 施工。 |
| `LLM-Q002` | `WORKING`；父層、`S1`～`S7`、雙軸證據分類、P3 responsibility placement 與精簡版方案 A 已 G3 | Product Owner 於 2026-09-04 核准第一版採 **LangChain stable 1.x＋LangGraph stable 1.x** 作 framework／durable-runtime 方向；不整包採 Deep Agents，不引入第二套 agent loop 或 durable owner。 | 官方能力逐項比較結果：兩案都能覆蓋 bounded agent loop、Tools、structured output、HITL、provider swap、context 與 tracing；A 能以一套 stable runtime 直接承接長期 thread、server-held state、PostgreSQL persistence 與 resume，B 在 typed Capability／成本治理較強，但需跨 Core、0.x Harness 與另一 durable engine，留下較多未證明 integration seam。A 是 Caliburn inference，不冒充跨廠共同選型。見[完整 Working Research §9](specs/2026-09-04-cross-vendor-llm-agent-system-and-framework-working-research.md)。 | 進入 G4：定義最小 runtime contract、責任邊界及少量 bounded characterization；仍不授權版本 pin、schema、spike 或 production 施工。 |
| `LLM-Q001` | `PAUSED`；G5 dependency preflight PASS 已保存 | 原題只涵蓋 provider capability contract 與 Tool loop。`LLM-Q002` 已核准 LangChain／LangGraph 方向，但 G4 最小 runtime contract、provider gateway 與模型 capability 尚未決定，因此不能把原 OpenRouter／LangChain 組合原樣固化成完整架構。 | 既有研究、dependency preflight、`258 passed, 29 skipped` 與無 live model request 的證據均保留，不判定為錯誤。見[跨家證據附錄](specs/2026-09-04-llm-tool-loop-and-runtime-responsibility-cross-vendor-evidence.md)與[原 Working Design](specs/2026-09-04-llm-invocation-lifecycle-and-provider-capability-contract-research.md)。 | G4 若確認原 contract 仍符合精簡版 A，再決定恢復或 supersede；目前不實作 G5 tests、不做 live API、Memory revision 4、merge 或 push。 |

## 5. 目前唯一 preflight

```text
Topic ID: LLM-Q014
Current stage: G3 parent direction complete；進入 G4 effect inventory／responsibility mapping
Binding decisions:
  - Production 仍受現行 code、AGENTS.md 與 Accepted ADR 0060 約束。
  - MEM-Q004 維持 FAIL_UNPROVEN；Memory read shape 不翻案，也不授權 revision 4。
  - 產品仍是一位顧問、一位員工／JD 對應一份隔離文件與一個目前可見的長期聊天室；Memory ownership 已由 `MEM-Q005` 定為 JD／document scope，而非 thread scope。
  - 不整合或逐項 mapping 舊元件；先以產品成果與跨廠成熟 primitive 建立目標架構。
  - 19 層父層責任地圖已獲 Owner 同意；LLM 控制 JD App 必須納入 Application workspace／Tools 層。
  - §6.1 已獲 Owner 同意：框架承接 Tool／agent-loop／approval 共識機制；Caliburn 定義 JD／職務分析語意。
  - Capability Catalogue 不得只列員工看得到的功能，也必須盤點共同的觀測、可靠性、成本、安全與演進能力。
  - S1～S7 只固定目前產品效果與禁止失敗；詢問方式、工作理解表徵、共同編輯底層、審核粒度、UI 與模型呼叫數仍未決定。
  - JD 是從長訪談形成的職務全貌中萃取，不是每則訊息或每個案例的紀錄；AI 與員工處理最新工作內容，但 AI 變更不得跳過員工審核。
  - S6 與 Accepted ADR 0060 §5 決定 13 對 AI 分析期間能否直接編輯／匯出的方向不同；目前只記錄 Working 方向，production 仍依 ADR 0060，日後須 successor ADR 才能改變。
  - `LLM-Q001` 的 dependency preflight 與變更原樣保存，但 G5 實作暫停。
  - P3 是符合跨廠共同責任與強趨勢的 Caliburn synthesis；不得宣稱 `P3` 名稱、四欄配置或全 JD 審核政策本身是廠商共同標準。
  - 方案 A 是依共同責任與產品情境作出的 Caliburn inference，不是「各家大廠共同選用 LangChain／LangGraph」；Owner 已核准其作第一版 framework／durable-runtime 方向。
  - 不整包採 Deep Agents，不同時引入 PydanticAI Agent 或第二套 durable owner；精確版本、Tool／Skill／Prompt schema、模型與 production 施工仍未核准。
  - `create_agent`、明確 `StateGraph` 與 Functional API 共用 LangGraph runtime；本題只選根骨架，不把三者誤當三套 framework。
  - 一般 AI JD 待審變更不預設等同阻塞整個 run 的 HITL interrupt；必要澄清與日常審核的恢復語意留給後續子決策。
  - `LLM-Q003` 已採一個 `create_agent` compiled graph 作第一版唯一根 runtime；這是可由新證據重開的 Working Decision，不是永久寫死或 production 授權。
  - `LLM-Q004` 已採第一版一份 JD 一個主要持久 thread、每則新員工訊息一個有界 logical invocation；內部可有多次 model／Tool step，必要輸入可 durable resume。這是目前產品 cardinality，不預先等同 Memory ownership。
  - `MEM-Q005` 已採第一版一個主要 thread＋JD-scoped Memory；多 thread 產品功能維持 out of scope。
  - `LLM-Q005` 已採依恢復責任分流到 framework-native primitive；不得把正常完成、等待員工、可修正、retry、達限、取消與 terminal failure 混成同一個錯誤。
  - `LLM-Q006` 的「普通訪談問題正常結束、不鎖聊天室」仍有效；第一版沒有員工輸入型 pending execution。
  - `LLM-Q007`～`LLM-Q010` 中「訪談澄清＝confirmation Tool＋durable interrupt」已被 `LLM-Q012` supersede for first-version interview；只保留為未來 explicit workflow 的歷史研究。
  - OpenAI、Anthropic、Google、LangGraph 與 Microsoft 的共同邊界是 completed conversation turn 與 explicit unfinished workflow continuation 分離；clarification 可落在任一種，沒有跨廠共識能只靠「問題重要」或「用了 Tool」決定是否 pause。
  - UI 仍可顯示問題卡、選項與自由文字；是否是卡片，不決定 Runtime 是否有 pending invocation。
  - `LLM-Q011` 已由 Product Owner 核准方案 C；第一版是否實際存在 unfinished workflow 由 `LLM-Q012` 逐項盤點。
  - `LLM-Q012` 已由 Product Owner 核准方案 B：第一版沒有員工輸入型 unfinished workflow；自然訪談／歧義以 normal completion 處理，JD review、direct edit、刪除／匯出確認與 retry 各有獨立 lifecycle。
  - `LLM-Q013` 已由 Product Owner 核准方案 B：一般問題只存在 canonical assistant message；只有影響未來 JD 的未解工作資訊進既有 content-only Semantic Memory，不建立專用 question schema 或 pending lifecycle。
  - `LLM-Q014` 已由 Product Owner 核准方案 A 的父層方向：message 對人、Tool 執行應用讀寫、deterministic code 推導可計算狀態、structured output 只承接單一窄 machine-readable artifact。
  - 上述跨廠共識只到「對話／動作／最終結構化成果的責任分界」；Tool-first 的 Caliburn 配置是依產品需求做出的 inference，後續不得宣稱廠商採相同完整架構。
  - 現行 code 的 required-clarification answer 會保存來源並 resume graph，但 resume 只清除 blocker 後到 END，不會自動啟動 model analysis；它沒有實現「答案後接續原分析」的典型 HITL 收益。
  - Accepted ADR 0060 與 production 目前仍要求 required-clarification interrupt；Owner 雖已採 `LLM-Q012` 方案 B，仍必須先開 successor ADR，不能由研究稿或實作者直接翻案。
This turn's only blocking question:
  - `LLM-Q014` G4.1：是否接受 Semantic Memory 由同一套 Manager 依資料依賴同步／背景排程，Manager 產生窄 mutation artifact、Runtime／Store 實際寫入，而主顧問 final response 不承載 Memory mutation？
Already reviewed evidence:
  產出高品質 JD 的 L1～L11；OpenAI Responses／Agents SDK、Anthropic Messages／Agent SDK／Managed Agents、
  Google Gemini／ADK、AWS AgentCore、Microsoft Agent Framework、LangChain／LangGraph／Deep Agents、
  PydanticAI Core／Harness／durable integrations；以及 `LLM-Q001` 既有 provider／Tool-loop 證據。
  另以 OpenAI model guidance、Anthropic Building Effective Agents／agent evals、AWS GenAI lifecycle／PoC、
  Google agent design patterns、Microsoft Agent Design Framework／flow mapping 與 Google review practices
  完成從 outcome 到垂直切片的流程交叉審核。
  `LLM-Q008` 另核對 OpenAI Function calling／required input、Anthropic `AskUserQuestion`／Tool use、
  LangGraph Tool 內 interrupt 與 LangChain final structured output；證據與方案已寫入本題 Working Design。
  `LLM-Q009` 另核對 OpenAI 不讓模型填已知參數／保持 Tool 精簡／strict schema、Anthropic 問題／選項／自由文字、
  LangChain `ToolRuntime` 隱藏注入與 Tool return；證據與方案已寫入本題 Working Design。
  `LLM-Q010` 另核對 OpenAI function instructions／Tool choice／strict、Anthropic Tool description／troubleshooting／auto，
  以及 LangChain system prompt／Tool description；證據與方案已寫入本題 Working Design。
  `LLM-Q011` 重驗另核對 OpenAI Responses conversation／required-input continuation、Anthropic normal turn／`AskUserQuestion`／Managed Agents、
  Google Workflow Builder request-info／approval、LangGraph interrupts／double texting 與 Microsoft Agent Framework interactive handoff／RequestPort；證據、三方案及員工不回答的生命週期已寫入本題 Working Design。
  `LLM-Q012` 另逐項核對第一版產品情境、現行 required-clarification code path、OpenAI Agents SDK 與 LangChain HITL 的「決定後執行原 Tool／run」生命週期；inventory、三方案與 ADR 衝突已寫入本題 Working Design。
  `LLM-Q013` 另核對 OpenAI Responses／最新 model guidance、Anthropic Messages／stop reasons／structured outputs、
  LangChain Messages／Agents／Structured Output，以及既有 content-only Memory contract 與現行 question duplication；三方案與推論已寫入本題 Working Design。
  `LLM-Q014` 回讀既有跨廠 Tool-loop／runtime evidence，並補驗 OpenAI Responses／latest model guidance、
  Anthropic Tool contract／Claude Code edit flow、Google Function Calling vs Structured Output、LangChain Tools／Structured Output／Context Engineering。
  `LLM-Q014` G4.1 另核對 OpenAI Codex 背景 extraction／consolidation、Anthropic Memory Tool hot path、
  Google Memory Bank／AWS AgentCore 背景 formation，以及 LangChain／LangMem 對 hot path 與 background 的正式雙模式與取捨；
  官方資料確認寫入時機不是跨廠單一共識，詳細見 machine-effects Working Design §2。
  A／B 另核對 LangChain 1.4、LangGraph 1.2、PydanticAI Core V2、Harness 0.29、Deferred Tools、
  Step Persistence 與 DBOS／Temporal 等 durable integration 的官方責任與限制；細節見研究稿 §9。
  `LLM-Q003` 另核對 LangChain Agents／Middleware／LangGraph overview、Graph vs Functional API、Persistence、
  Interrupts 與 HITL，以及 Anthropic workflow／agent 分界與 OpenAI 最新 Agents SDK guidance。
  `LLM-Q004` 另核對 OpenAI Agents SDK／Responses 的 run、session、stream、interrupt 與 limit；
  Anthropic Managed Agents／Tool Runner 的 session、idle、requires_action 與 budget；LangChain／LangGraph 的
  thread、run、checkpointer、interrupt、stream、fault tolerance、call limits 與 double-texting scope。
  `MEM-Q005` 另核對 OpenAI Agents SDK Session／Sandbox Memory、Anthropic Managed Agents Session／Memory Store，
  以及 LangGraph Checkpointer／Store 的 scope 與 lifecycle 分離。
  `LLM-Q006`／`LLM-Q011` 另核對 completed turn 與 explicit unfinished workflow continuation 的分界；Anthropic／Google 證明 clarification／request-info 也可 pause，
  因此不能把 durable input 限縮成只有 Tool approval，也不能把所有重要問題自動視為 pending execution。
  `LLM-Q007` 另核對 OpenAI client-owned Tool／approval required input、Claude Agent SDK `AskUserQuestion`／`defer`，
  以及 LangGraph Checkpointer、`interrupt()`、`Command(resume=...)` 與 node replay 規則。
Out of scope / parking lot:
  同一 JD 多 thread UI／API、並行 merge／routing、跨 JD Memory、exact default model、付費 model characterization、
  framework spike、Memory revision 4、各 machine effect 的具體 Tool 名稱／參數／批次粒度、具體 Skill／Prompt schema、
  JD 編輯器 UI 與資料結構、RAG、production 施工、merge、push。
```
