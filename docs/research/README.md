# 研究資料

這裡回答「外部怎麼做、有哪些證據、Caliburn 當時如何比較」。與[架構／契約](../specs/README.md)、[分析指南](../guides/README.md)、[實驗結果](../experiments/README.md)分開；**研究完成不等於採用、實作或驗收完成**。

本次歸位的 55 份原研究按四個主題保存，保留原日期、內容、來源與限制。只調整相對連結；原路徑及 Git 基準見[整理紀錄](../archive/document-classification-2026-10-02.md)。不是重新驗證所有歷史論文／API，也不是宣告所有研究仍適用。

## 先依用途找

| 你要找什麼 | 入口 |
|---|---|
| 如何分析員工工作、寫 JD | [分析指南](../guides/README.md)，先用已整理的方法，再查本頁原始研究 |
| 現在採用了哪個方案 | [目前決策](../current-decisions.md) → [目標架構](../target-architecture-map.md)／ADR |
| 真的跑過哪些測試、結果好不好 | [任務驗收證據](../plans/2026-09-29-target-rebuild/evidence/README.md)、[獨立實驗](../experiments/README.md) |
| 教授／推甄報告要引用哪些材料 | [報告與材料入口](../reports/README.md) |

## Agent、Context、Memory 與評測

比較 Agent 執行、模型工具、記憶與品質機制。模型／框架能力只代表各篇查閱時點，採用前須重查目前官方契約。

- [LLM 怎麼接進系統 — 接線層研究(進行中)](agent-systems/2026-07-05-llm-integration-wiring-research.md)
- [AI Agent 應用架構設計 — 2025–2026 主流共識與趨勢研究紀錄](agent-systems/2026-07-12-ai-redesign-raw-agent-architecture.md)
- [主流 agent 系統:組件命名與回合管線 — 研究 + 對照健檢](agent-systems/2026-07-12-ai-redesign-raw-agent-naming-pipeline.md)
- [領先 AI 產品公司的真實系統架構(2024–2026 一手案例)](agent-systems/2026-07-12-ai-redesign-raw-case-architectures.md)
- [Claude Code 與 Codex 的「對話互動層」設計研究](agent-systems/2026-07-12-ai-redesign-raw-claudecode-codex-interaction.md)
- [LLM 應用工程與營運優化技術調查(2025–2026)](agent-systems/2026-07-12-ai-redesign-raw-engineering-optimizations.md)
- [LLM Evals 與 LLM-as-Judge 的「正確設計方法」研究紀錄(2025–2026)](agent-systems/2026-07-12-ai-redesign-raw-evals-design.md)
- [LLM 應用「可靠、可信、可驗證」工程實務研究(2025–2026)](agent-systems/2026-07-12-ai-redesign-raw-llm-reliability.md)
- [2025–2026 提升 LLM 生成品質技術調查](agent-systems/2026-07-12-ai-redesign-raw-quality-techniques.md)
- [2025–2026 官方 AI 應用參考架構研究紀錄](agent-systems/2026-07-12-ai-redesign-raw-reference-architectures.md)
- [實作級技術假設驗證(四項)](agent-systems/2026-07-13-ai-redesign-raw-impl-verification.md)
- [Anthropic strict schema「compiled grammar is too large」：限制查證與修法分析](agent-systems/2026-07-31-anthropic-strict-schema-grammar-limit-research.md)
- [Luna Structured Tools／Context：官方文件審核與修正邊界](agent-systems/2026-08-23-luna-structured-tools-and-context-official-audit.md)
- [Agent Memory 市場流程、共同基線與方案決策工作研究](agent-systems/2026-08-30-agent-memory-landscape-and-decision-working-research.md)
- [OpenAI Codex Memory progressive disclosure 深入查證](agent-systems/2026-09-04-openai-codex-memory-progressive-disclosure-deep-dive.md)
- [LangChain／LangGraph／Deep Agents／LangMem 官方記憶流程事實圖](agent-systems/2026-09-05-langchain-langgraph-deepagents-langmem-official-memory-flow-map.md)
- [OpenAI 對話、Context、Compaction 與 Memory 系統地圖](agent-systems/2026-09-05-openai-conversation-context-and-memory-system-map.md)
- [OpenAI Memory artifacts 對最新框架的逐項實作交叉表](agent-systems/2026-09-05-openai-memory-artifacts-to-framework-detailed-crosswalk.md)
- [OpenAI Memory 流程對最新框架的功能交叉表](agent-systems/2026-09-05-openai-memory-flow-to-latest-framework-functional-crosswalk.md)
- [Q019-MEM-SUMMARY-01：OpenAI 詳記遇到後續更正時如何處理](agent-systems/2026-09-06-openai-rollout-summary-correction-source-review.md)
- [JD AI App：工具執行與可靠性官方證據](agent-systems/2026-09-09-jd-ai-app-runtime-official-evidence.md)
- [Agent 能力與生命週期：跨廠做法研究（候選，非施工設計）](agent-systems/2026-09-25-agent-capabilities-and-lifecycle-patterns-research.md)
- [顧問分析延續：Reasoning、工具結果、Compaction 與 State 的邊界](agent-systems/2026-09-26-reasoning-tool-results-and-state-boundary-research.md)

## 工作分析、訪談與 JD 內容

保存 iCAP、國際職能標準、訪談方法、OPKS 與雇主文件比較。用於指南、Prompt 與報告的依據，不把外部職稱範例當成受訪者事實。

- [LLM 訪談式撰寫職務說明書 — 終局藍圖研究](work-analysis/2026-07-02-llm-interview-authoring-research.md)
- [訪談對話品質研究紀錄(真人試訪根因#3;顧問「像機器人、不理員工」)](work-analysis/2026-07-06-interview-conversation-quality-research.md)
- [AI 主導訪談 / 資訊蒐集對話設計 — 權威做法研究紀錄](work-analysis/2026-07-12-ai-redesign-raw-interview-conversation-design.md)
- [產出專業級文件的 AI 應用怎麼蓋(2024–2026)](work-analysis/2026-07-12-ai-redesign-raw-professional-docgen.md)
- [iCAP 職能基準表逐欄位官方標準（研究原料）](work-analysis/2026-07-13-ai-redesign-raw-icap-field-standards.md)
- [國際主要職能/職業標準體系的欄位定義與撰寫標準](work-analysis/2026-07-13-ai-redesign-raw-intl-competency-standards.md)
- [OPKS 原始生成與 grounding 的證據基礎](work-analysis/2026-08-01-opks-raw-llm-generation-grounding.md)
- [行為指標（P）的撰寫紀律與數值門檻（研究原料）](work-analysis/2026-08-01-opks-raw-performance-indicators.md)
- [O/P/K/S 原料研究 —— taxonomy 現況、業界綁定做法與繁中可行性](work-analysis/2026-08-01-opks-raw-skills-taxonomies.md)
- [OPKS 效度、自評偏誤與 AI 法規](work-analysis/2026-08-01-opks-raw-validity-and-ai-regulation.md)
- [工作產出（O）的權威處理（研究原料）](work-analysis/2026-08-01-opks-raw-work-outputs.md)
- [實際雇主職位文件與 Caliburn 樣稿比較](work-analysis/2026-09-09-employer-job-document-comparison.md)
- [工作分析與 JD 內容的跨國證據](work-analysis/2026-09-09-job-analysis-international-evidence.md)

## 工程架構、文件與編輯互動

保存模組、命名、資料存取、文件組織與共編介面研究。舊 App 名稱與已拍板方向均保留當時語境，不由此恢復舊架構。

- [Phase 3a Research Record — `apps/api` Hexagonal Untangle (core/ports · adapters · kill the graph↔s](engineering/2026-06-28-api-hexagonal-untangle-research.md)
- [Contract #3 Research Record — api ⇄ web Authored Document](engineering/2026-06-28-contract-3-api-web-document-research.md)
- [命名規範研究紀錄 — web 改名 / v3→v4 / docker 命名](engineering/2026-06-29-naming-conventions-research.md)
- [DB image 去 pgvector 研究紀錄 — `pgvector/pgvector:pg16` → `postgres:16`](engineering/2026-06-30-db-image-drop-pgvector-research.md)
- [Web 資料層優化研究紀錄 — 快取/預抓/持久化、存檔並發、項目穩定身分](engineering/2026-06-30-web-data-layer-optimization-research.md)
- [API 命名對齊 — 研究(F3 / F4 / F7 / F5 落實前置)](engineering/2026-07-02-api-naming-alignment-research.md)
- [App 組裝點 / health / 降級政策 — 架構研究(F1 + F2 落實前置)](engineering/2026-07-02-app-composition-health-degradation-research.md)
- [研究紀錄:給 LLM 看的文檔怎麼寫(agent-facing docs / context engineering)](engineering/2026-07-03-agent-facing-docs-research.md)
- [研究紀錄:per-app 開發者文檔怎麼寫(README 補齊前的寫法研究)](engineering/2026-07-03-app-developer-docs-research.md)
- [AI 與人共同編輯文件／結構化內容的互動設計(UX)——2025–2026 主流做法與趨勢研究](engineering/2026-07-12-ai-redesign-raw-coediting-ux.md)
- [研究紀錄:AI 共編產品中「審閱動作(accept/reject)之後的系統與 AI 行為語意」](engineering/2026-07-12-ai-redesign-raw-review-event-semantics.md)
- [JD 文件內容模型：官方證據與適用邊界](engineering/2026-09-09-jd-document-model-official-evidence.md)
- [JD 編輯框架：原生能力、細節差距與選型證據](engineering/2026-09-09-jd-editor-framework-comparison.md)

## 檢索、OCS 與文件處理

保存 PDF／OCS、embedding、indexer 與檢索比較。這是獨立 RAG 範圍的研究，不是新 JD App 必裝依賴。

- [Contract #2 Research Record — Indexer Query API (ocs-indexer ⇄ api)](retrieval/2026-06-28-contract-2-indexer-query-api-research.md)
- [Phase 3c Research Record — `apps/ocs-indexer` Embedding-Version Tag + Thin CLI](retrieval/2026-06-28-ocs-indexer-embedding-version-thin-cli-research.md)
- [研究紀錄 — pdf-to-json `ocs_transformer.py` god-file 拆解(Phase 3b)](retrieval/2026-06-28-pdf-to-json-transformer-decomposition-research.md)
- [Research Record — Embedding as a Service (self-built BGE-M3 container, keep dense+sparse)](retrieval/2026-06-29-embedder-service-bge-m3-research.md)
- [研究紀錄 — 多職類參考下的候選近重複:去重不是唯一解](retrieval/2026-07-02-multi-ocs-candidate-dedup-research.md)
- [檢索/知識層前沿技術調查(2025–2026)](retrieval/2026-07-12-ai-redesign-raw-retrieval-frontier.md)

## 混合文件與後續研究

有些歷史檔名含 `research`，但已承擔產品規則，仍留在原責任路徑。例如[工具共同規範](../specs/2026-09-27-agent-tool-contract-design-research.md)、[工作分析方法入口](../specs/2026-09-09-job-analysis-and-jd-content-research.md)。它們不能只因檔名就降格為參考資料；沿[規格入口](../specs/README.md)與最新決策判讀。

新增純研究先選上述主題；沿用 `YYYY-MM-DD-明確主題.md`，記錄問題、來源／查閱日、事實與推論、比較、限制及決策去向。研究結論被採用後，規則在責任文件維護，研究保留推導經過，不另抄第二份現行契約。寫法與討論門檻依[既有討論規範](../architecture-discussion-standard.md)。
