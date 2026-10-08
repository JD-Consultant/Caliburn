# 架構決策紀錄（ADR）

每份 ADR 保存一項重大決策的脈絡、理由及取捨。查現在有效的產品規則，先讀[目前決策](../current-decisions.md)與[架構導覽](../architecture/README.md)，再按本表追溯決策；Accepted 表示當時已核准，不表示所有內容至今仍適用。

## 現行產品的主要決策

- [ADR0079](0079-target-rebuild-production-cutover.md)：正式產品切換與舊程式退役。
- [ADR0080](0080-opt-in-public-reference-agent-tools.md)：明示設定啟用公版工具，RAG 保持獨立。
- [ADR0082](0082-consultant-jd-work-plan.md)：JD 工作計畫的內容及用途；部分取代 [ADR0081](0081-consultant-interview-focus-and-unresolved-plan.md)，仍有效的工具、保存及接續契約見[Plan 規格](../specs/jd-work-plan.md)。

## 完整索引

按編號查歷史演進。下表保留記錄的狀態與接續關係；施工、隔離驗證或 Proposed 紀錄不自行切換 production。完整條件請讀 ADR 原文及所連接的證據。

| # | 決策原題 | 記錄狀態與接續 |
|---|---|---|
| [0001](0001-monorepo-with-turborepo.md) | Monorepo（Turborepo + per-app uv），非 polyrepo | Accepted（Phase 1 已實作） |
| [0002](0002-three-bounded-contexts-modular-monolith.md) | 三個 bounded context,各為模組化單體 | Accepted |
| [0003](0003-indexer-stays-separate-service.md) | ocs-indexer 維持獨立服務(不併進 api) | Accepted |
| [0004](0004-contract-first-ocs-contract.md) | 契約優先 `packages/ocs-contract` | Accepted（Phase 2 規劃中） |
| [0005](0005-per-app-uv-defer-workspace.md) | per-app uv 專案;uv workspace 延後到 Phase 2 | Accepted（Phase 1） |
| [0006](0006-multitenancy-pool-rls.md) | 多租戶 Pool + Postgres RLS | Accepted（登入時實作） |
| [0007](0007-langgraph-retained-mcp-ready.md) | LangGraph 留用 + 12-factor + MCP-ready | Accepted（LangGraph 留用部分由 0023 翻案:新訪談引擎全新實作,舊圖待清;12-factor 原則沿用且強化） |
| [0008](0008-api-hexagonal-layering.md) | api 六邊形分層:ports→core、adapters→edge、移除 services→graph_v3 反向邊 | Accepted（Phase 3a 已實作） |
| [0009](0009-embedding-version-manifest.md) | embedding 版本 manifest + 查詢前相容驗證;瘦 CLI | Accepted（Phase 3c 已實作） |
| [0010](0010-indexer-contract-shared-package.md) | 契約 #2(indexer 查詢 API)用共用 pydantic 套件,非 codegen/Pact | Accepted（契約 #2 已實作） |
| [0011](0011-web-ocs-types-generated.md) | 契約 #3(api⇄web 著作文件 Part A):web 改吃 ocs-contract 生成的 TS 型別 | Accepted（契約 #3 Part A 已實作） |
| [0012](0012-embedding-as-a-service.md) | 嵌入服務化:自建 BGE-M3 容器(FlagEmbedding,保留 dense+sparse) | Accepted |
| [0013](0013-naming-cleanup-caliburn.md) | 命名整理:web 改 Caliburn、內部去版號、容器/DB 去 jobintel | Accepted |
| [0014](0014-db-image-stock-postgres.md) | DB image 降回 stock `postgres:16`(移除未使用的 pgvector) | Accepted |
| [0015](0015-document-save-optimistic-concurrency.md) | 文件存檔採樂觀並發(version 守衛),回合制協作不上 CRDT/OT | Accepted（2a-minimal 已實作：雙 token version+revision、409 + ConflictDialog；full 延後） |
| [0016](0016-batch-task-catalog-endpoint.md) | 後端批次 task-catalog 端點(每 ocs_code 撈一次池) | Accepted（模式由 0021 一般化；task-catalogs 端點與前端 seeding 已於 P3 退役） |
| [0017](0017-app-entry-single-composition-root.md) | 後端 app 入口收斂:單一組裝點 + `/healthz` 統一 | Accepted |
| [0018](0018-indexer-dependency-degradation-policy.md) | indexer 依賴降級政策:critical fail-fast vs enrichment 降級 | Accepted |
| [0019](0019-api-naming-alignment.md) | API 命名對齊:AIP `:verb` + 根層 occupations 搜尋 + PUT occupations | Accepted |
| [0020](0020-interview-authoring-interaction-model.md) | 訪談式撰寫的互動模式:混合載體(文件常駐 + 精靈化訪談面板) | Accepted |
| [0021](0021-knowledge-pack-single-sync-point.md) | 知識包:選職類=唯一 knowledge 同步點;indexer 給資料、api 處理、web 讀寫 | Accepted（P1–P3 已實作：`/knowledge` 端點＋web 全選單切換＋舊四端點退役） |
| [0022](0022-similarity-matching-items-match.md) | 相似比對(items:match):indexer 確定性能力、三區分帶、非破壞呈現 | Accepted（v1 已實作：端點＋校準＋pack 掛載＋態度收合/任務徽章） |
| [0023](0023-interview-engine-stateless-turns.md) | 訪談引擎骨幹:無狀態回合服務 + 軟階段 + 指令詞彙表 | Partially superseded by 0034（保留 provenance/全新實作原則） |
| [0024](0024-llm-wiring-select-schema.md) | LLM 接線:LlmPort 增 select_schema + 受限解碼路徑判準 | Superseded by 0034 |
| [0025](0025-coedit-authority-dual-channel.md) | 人機共編權限:雙通道 + 風險分流 + 節點批審 | Accepted（2026-07-05；spec/plan 待開） |
| [0026](0026-interview-turn-model-role.md) | 訪談回合獨立模型 role(model_interview,強推理 + strict) | Superseded by 0034 |
| [0027](0027-interview-engine-v2-consultant-agent.md) | 訪談引擎 v2:顧問 agent + 書記 + 確定性覆蓋帳本(四組件) | Superseded by 0034 |
| [0028](0028-interview-flow-shared-ui-curation.md) | 訪談流程 v2.1:AI 驅動共用編輯 UI(追蹤修訂)+ 議程化彈性流程 + 完整性檢查表 + 態度收尾 | Accepted（2026-07-09；真人實測 eb2af457 驅動） |
| [0029](0029-editor-menus-three-types-decoupling.md) | 編輯器選單三型＝純工具;參考集合與文件身分脫鉤 | Accepted（2026-07-11；七層設計討論收斂；AI 載體由 0030 定案） |
| [0030](0030-ai-coedit-tracked-changes-one-brain.md) | AI 層 v3:追蹤修訂直寫載體+一條腦+品質迴路 | Partially superseded by 0034（保留 Web review/authority/eval 原則） |
| [0031](0031-occupation-suggest-card-refset-source.md) | 職類建議卡進對話流;引擎參考碼=profile∪doc;參考集合維持人選 | Accepted（2026-07-13；新手 persona 手測驗屍＋先例研究） |
| [0032](0032-task-carrier-routing.md) | 任務載體路由:證據→綠字直落、盤=人拉(intake/自取)、不確定→卡片 | Accepted（2026-07-14；維護者質疑 b 案＋Copilot/PAIR/TurboTax/冷啟動先例） |
| [0033](0033-episode-agenda-consultant-tools.md) | 訪談議程 v4:事件驅動議程=顧問議程工具+覆蓋 artifact+事件收割 pass(退役 next_gap 梯子) | Partially superseded by 0034（只保留 episode 概念） |
| [0034](0034-interview-ai-vnext-greenfield-evidence-workflow.md) | Interview AI vNext：greenfield evidence workflow，不整合 v3 LLM internals | Accepted（provider直連優先部分由0035修正） |
| [0035](0035-interview-vnext-openrouter-first-provider-boundary.md) | Interview AI vNext：OpenRouter-first provider boundary，直連供應商降為比較與備援 | Accepted（2026-07-17；V3-4R live conformance已完成） |
| [0036](0036-interview-vnext-provider-binding-conformance-and-idless-turn-v2.md) | Interview AI vNext：runtime binding/conformance 分層與 ID-less Turn Interpreter v2 | Accepted（2026-07-18；R3/R4已完成） |
| [0037](0037-interview-vnext-question-frame-contextual-evidence-and-employee-authority.md) | Interview AI vNext：QuestionFrame、分型 Evidence 與員工文件權威 | Accepted（2026-07-20；R5-BC已完成） |
| [0038](0038-interview-vnext-context-engine-and-professional-consultant-workflow.md) | Interview AI vNext：Context Engine、專業顧問工作流與文件共編權威 | **Superseded by 0040**（2026-07-26；完整取代。新方向見0040，勿據0038開新工） |
| [0039](0039-local-multi-document-canonical-public-form-workspace.md) | 本機多文件 Workspace、Canonical 文件權威與公版樣式 UI | **Superseded by 0043**（原為 Proposed with owner amendment；勿據以施工） |
| [0040](0040-professional-consultant-engine-and-r1-validation-contract.md) | 專業顧問引擎 greenfield 與 R1 驗證契約 | **Accepted**（2026-07-26；owner核准＋第二位審查者複審後定案）**決定 29–30 的「四級支持度」已由 0048 翻案**（改兩正交軸），決定 31–34 不變且被 0048 強化 |
| [0041](0041-r1-p0-closure-first-version-context-and-holdout.md) | R1-P0 結案、第一版 Context 表示與 R1 holdout | **Accepted**（2026-07-27；補充 0040；同日第二次審查兩輪十一項：採納十項、狀態異議經查證駁回並撤回） |
| [0042](0042-r1-screening-stop-and-a6-first-version-default.md) | 停止 R1 架構實驗、A6 作第一版實作預設 | **Accepted**（2026-07-28；部分修正 0040 決定 9、0041 決定 11）其中「支持度四級」一詞**已由 0048 翻案為兩正交軸**；該防線的**意圖**（無來源不得入正式 JD）保留且被 0048／0049 強化 |
| [0043](0043-job-analysis-local-current-state-persistence-and-authoring-authority.md) | `job_analysis` 本機 Current State 持久化與編輯權威 | **Accepted**（2026-07-29；完整取代0039） |
| [0044](0044-partial-jd-task-reconciliation-and-human-confirmation.md) | 不完整 JD Task 的明確對齊與員工確認 | **Accepted**（2026-07-30；補充0043） |
| [0045](0045-job-analysis-local-web-contract-and-shared-authority-commit.md) | `job_analysis` 本機 Web 契約與共用 authority commit seam | **Accepted**（2026-07-30；owner 核准＋closure review） |
| [0046](0046-professional-consultant-minimal-durable-loop.md) | 專業顧問第一個最小 durable Task 訪談迴圈 | **Accepted**（2026-07-30；owner 授權 strongest-case 自審後施工） |
| [0047](0047-model-owned-open-issue-closure.md) | 模型可關閉自己提出的 open issue | **Accepted**（2026-07-31；補充 0044；付費 live run 撞出，owner 授權自審自決） |
| [0048](0048-opks-evidence-axes-and-document-level-competencies.md) | OPKS：證據兩軸、文件層 K/S/A、與外部指涉的門檻規則 | **Accepted**（2026-08-01；**部分翻案 0040 決定 29–30**，決定 31–34 不變且被強化；外部審查兩輪收斂）**部分由 0049 修正實作形狀** |
| [0049](0049-opks-derived-axes-evidence-whitelist-and-document-authority.md) | OPKS 修正：兩軸改為投影、Evidence 來源白名單、文件層 identity 與權威流程 | **Accepted**（2026-08-01；修正 0048 決定 1–4／20／22／23 並補其未定義處；0048 概念裁決全部維持）**其 Proposal 形狀由 0050 定案** |
| [0050](0050-opks-proposal-minimal-shape.md) | OPKS Proposal 的最小形狀：獨立、薄、每項一筆 | **Accepted**（2026-08-01；補充 0049 決定 8／11／13）**其 `status` 沿用與 `target_id` 選填兩處已由 0051 修正**——狀態機與 `entity_id` 一律以 0051 為準 |
| [0051](0051-opks-proposal-status-machine-and-stable-entity-id.md) | OPKS Proposal 的自有狀態機與穩定 entity ID | **Accepted**（2026-08-01；修正 0050 兩處契約不自洽，0050 其餘決策不變） |
| [0052](0052-jd-readiness-assessment-and-official-code-boundaries.md) | JD 完整度評估的歸屬與兩種「代碼」的權責分界 | **Accepted**（2026-08-02；依 2026-01-27 官方手冊逐字核對，見 [`specs/2026-08-02-icap-2026-quality-manual-form-authority.md`](../research/work-analysis/2026-08-02-icap-2026-quality-manual-form-authority.md)；延續 0040 決定 33–34 與 0048 的 Attitude 可空，未翻案任何既有 ADR） |
| [0053](0053-jd-header-authority-boundary-and-readiness-scope.md) | JdHeader 的 authority 邊界與 readiness 第一版範圍 | **Accepted**（2026-08-02；補充 0045 的 authority 邊界、修正 0052 決定 11 未指名 seam 與決定 15–16 漏列條件式欄位，**兩者其餘決策全部不變**） |
| [0054](0054-opks-progressive-elicitation-and-scheduled-child-operation.md) | OPKS 漸進式蒐集：自動排定的 child operation 與可持久的缺口 | **Accepted**（2026-08-05；依 [`specs/2026-08-04-opks-progressive-elicitation-research.md`](../history.md#source-d0604cda1359b341dcb0)；延續 0047／0048 決定 6·14·24–25／0049 決定 13–14／0052 決定 1·7·15，未翻案 0048–0051 的 OPKS 概念與持久化形狀） |
| [0055](0055-opks-gap-does-not-block-reanalysis.md) | 未解的 OPKS 缺口不再阻擋再分析 | **Rejected**（2026-08-06；暫不採用，0054 決定 3 維持原樣） |
| [0056](0056-strict-public-jd-xlsx-export.md) | 嚴格公版職務說明書 XLSX 匯出 | **Accepted**（2026-08-09；owner 明確核准選擇性移植與嚴格公版形狀） |
| [0057](0057-current-only-runtime-and-data-boundary.md) | Current-only runtime 與資料邊界 | **Proposed**（2026-08-10 提出；2026-08-11 依 owner RAG 保留裁決修正 Decision 5／Consequences，ADR 內容仍待 owner 定案 Accepted） |
| [0058](0058-current-api-functional-modules-and-dependency-rules.md) | Current API 採功能模組與可執行依賴規則 | **Accepted；部分被 0060 取代**（2026-08-14） |
| [0059](0059-core-shared-kernel-boundary-clarifications.md) | `core` shared-kernel 邊界澄清：root-only 例外、`opks_integrity.py` 例外、guard 掃描範圍 | **Accepted；部分被 0060 取代**（2026-08-14） |
| [0060](0060-langchain-langgraph-consultant-runtime-and-durable-authority.md) | LangChain／LangGraph 職務顧問 runtime 與單一 durable authority | **Accepted**（2026-08-14） |
| [0061](0061-compact-consultant-wire-progressive-skills-and-tools.md) | 精簡顧問 provider wire；Skill／Tool 邊界另議 | **Accepted**（2026-08-14；provider channel 選擇於 2026-08-15 被 0063 部分取代） |
| [0062](0062-bounded-consultant-read-tools-and-structured-authority.md) | 受限顧問唯讀 Tool 與 structured authority 邊界 | **Accepted**（2026-08-14；決定 5 與決定 8 的固定三次 model-call 上限於 2026-08-15 被 0063 取代） |
| [0063](0063-hybrid-candidate-edit-tool-and-structured-final-response.md) | 候選文件編輯 Tool 與 Structured Final Response 混合迴圈 | **Accepted**（2026-08-15；部分取代 0061／0062 的 provider channel 與固定三次 model-call 上限） |
| [0064](0064-deep-agents-virtual-jd-workspace-and-deterministic-evidence-anchor.md) | Deep Agents 虛擬 JD 工作區與確定性 Evidence Anchor | **Accepted**（2026-08-21；取代 0060 的 read-file-only 限制、0061 的 model-facing fixed payload／offset 表示、0062 的自寫來源 Tool shape，以及 0063 的 mega-form／Tool surface／初始五步上限） |
| [0065](0065-interactive-consultant-finalization-and-token-budget.md) | 互動顧問 finalization 與累計 Token 預算校準 | **Accepted**（2026-08-22；只取代 0064 決定 12 的八-call operational profile，其餘 authority／VFS／Evidence 決策不變） |
| [0066](0066-persistent-ai-jd-working-draft-and-semantic-review.md) | 持久 AI JD 工作草稿與語意審核 | **Accepted；部分被 0067 取代**（2026-08-22；取代 0064 的 run-scoped candidate、model-facing check／publication receipt 與第二份 pending lifecycle） |
| [0067](0067-deep-agents-store-backed-jd-working-draft.md) | Deep Agents Store-backed JD working draft | **Accepted**（2026-08-22；取代 0066 對workspace使用`StateBackend`的mapping，其餘產品決策不變） |
| [0068](0068-framework-run-budgets-replace-lookup-wave-cap.md) | 以 framework run budgets 取代自訂 lookup-wave 上限 | **Accepted**（2026-08-23；取代 0062 決定 8、0065 決定 4 與 0067 沿用的固定兩波限制） |
| [0069](0069-shared-current-jd-working-copy-and-semantic-approval.md) | 共用目前 JD 工作副本與語意核准 | **Accepted**（2026-08-26；部分取代 0066／0067 的雙編輯面、direct-edit rebase conflict 與 defer lifecycle） |
| [0070](0070-consultant-workspace-ui-and-explicit-pending-edit-approval.md) | 顧問工作區 UI 與待審編輯仍需明確核准 | **Proposed**（2026-08-27；owner 已核准施工，待 implementation gate 後 Accepted；屆時部分取代 0069 決定 6／7／13 並澄清 10／12） |
| [0071](0071-revisable-work-understanding-context-and-review-provenance.md) | 可修訂工作理解、最小 Context 與待審變更來源分層 | **Proposed；待整體重寫或 successor**（產品目的仍可參考，但任何 Memory authority 變更必須明確取代 Accepted ADR 0060；以 framework-independent contract、最新重驗與最小切片設計為目前研究入口） |
| [0072](0072-qdrant-derived-memory-hybrid-retrieval-index.md) | PostgreSQL 權威與 Qdrant 衍生 Memory 混合召回索引 | **Proposed；deferred candidate**（2026-09-02；窄 dense compatibility smoke 只保留為候選證據，尚未授權 Qdrant、Voyage、outbox、CAS、revision 或 manifest 施工；需 recall trigger＋可重跑 hybrid integration smoke＋successor 邊界後再審） |
| [0073](0073-plate-jd-app-working-document-and-revision-authority.md) | Plate JD App、同一工作稿與文件修訂 authority | **Proposed；active candidate 已由 0075 取代**（2026-09-12 Owner 要求 relational rows；0073 從未改production） |
| [0074](0074-tested-consultant-runtime-source-and-memory-adoption.md) | 採用已驗顧問 runtime、原始訪談與 Memory authority | **Proposed**（2026-09-10；2026-09-16 依 Owner `CTX-C001` 修訂；成品P4/R5候選，待G6；不重做Memory，不憑總計畫跳過core驗收） |
| [0075](0075-relational-jd-authority-and-structured-editor.md) | 關聯式 JD authority 與結構化管理編輯器 | **Proposed**（2026-09-12；Owner要求後的G4 draft；D01 duty刪除效果與外部review未閉合，未建表／改production） |
| [0076](0076-jd-background-admission-record.md) | 新 JD App 的背景准入列 | **Proposed**（2026-09-14；缺口已在真PG逐欄實測，十三張JD內容表不變但App總表數增為十四；不改production authority） |
| [0077](0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md) | 關聯式 JD App 正式權責與 pnpm 單一入口 | **Accepted**（2026-09-22；Owner 核准不保留舊程式或舊資料相容性；取代 0060／0066／0067／0069 的舊 production authority，並採用 0074–0076 已驗實作）；**2026-10-02 起 Superseded by 0079** |
| [0078](0078-current-jd-read-only-locator.md) | 同版 JD 唯讀定位與完整正文讀取 | **Proposed**（2026-09-24；分支內施工、離線與窄真模型定位通過，完整旅程／品質仍待驗收） |
| [0079](0079-target-rebuild-production-cutover.md) | 新目標重建的正式切換與舊程式退役 | **Accepted**（2026-10-02；Owner 放行；取代 0077 的正式實作與入口，舊程式已退役） |
| [0080](0080-opt-in-public-reference-agent-tools.md) | 以明示設定接入公版參考工具 | **Accepted**（2026-10-05；Owner 授權接線，現有共用服務不重啟；實作驗證依施工紀錄） |
| [0081](0081-consultant-interview-focus-and-unresolved-plan.md) | 顧問長訪談的焦點與未釐清筆記 | Accepted（2026-10-07）；決定 1 的內容限定由 [0082](0082-consultant-jd-work-plan.md)部分取代，其餘工具、保存與採用責任保持 |
| [0082](0082-consultant-jd-work-plan.md) | 顧問以 JD 工作計畫延續長任務 | Accepted（2026-10-08）；部分取代 0081 決定 1；工程與有限比較的結果及限制見[證據](../plans/evidence/jd-work-plan-2026-10-08.md) |

## 維護與延伸閱讀

ADR 採輕量 Nygard 格式。Accepted 正文保留原意；改向時新增 ADR，以 `Supersedes`／`Superseded by` 記接續關係，依[決策流程](../decision-process.md)處理。

詳細行為沿[規格](../specs/README.md)，操作沿 [runbook](../runbook.md)，契約選擇沿[契約策略](../contract-strategy.md)。早期整體設計可從[歷史原件](../history.md#source-f661c579036f7cefc3f9)取回。
