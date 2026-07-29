# Architecture Decision Records (ADR)

每份 ADR 記錄**一個**重大決策的脈絡、決定、與後果(取捨)。格式採輕量 Nygard 式。
ADR 是「為什麼」層;搭配 `../specs/`(細節設計)與 `../runbook.md`(怎麼操作)。

> 規則:ADR 一旦 Accepted 就**不改內容**;要翻案就新開一份 ADR 標 `Supersedes`/`Superseded by`。

## 索引

| # | 決策 | 狀態 |
|---|---|---|
| [0001](0001-monorepo-with-turborepo.md) | Monorepo（Turborepo + per-app uv），非 polyrepo | Accepted（Phase 1 已實作） |
| [0002](0002-three-bounded-contexts-modular-monolith.md) | 三個 bounded context，各為模組化單體 | Accepted |
| [0003](0003-indexer-stays-separate-service.md) | ocs-indexer 維持獨立服務 | Accepted |
| [0004](0004-contract-first-ocs-contract.md) | 契約優先 `packages/ocs-contract` | Accepted（Phase 2 規劃中） |
| [0005](0005-per-app-uv-defer-workspace.md) | per-app uv 專案;uv workspace 延後 | Accepted（Phase 1） |
| [0006](0006-multitenancy-pool-rls.md) | 多租戶 Pool + Postgres RLS | Accepted（登入時實作） |
| [0007](0007-langgraph-retained-mcp-ready.md) | LangGraph 留用 + 12-factor + MCP-ready | Accepted（LangGraph 留用部分由 0023 翻案:新訪談引擎全新實作,舊圖待清;12-factor 原則沿用且強化） |
| [0008](0008-api-hexagonal-layering.md) | api 六邊形分層:ports→core、adapters→edge、移除反向邊 | Accepted（Phase 3a 已實作） |
| [0009](0009-embedding-version-manifest.md) | embedding 版本 manifest + 查詢前相容驗證;瘦 CLI | Accepted（Phase 3c 已實作） |
| [0010](0010-indexer-contract-shared-package.md) | 契約 #2 indexer 查詢 API：共用 pydantic 套件（非 codegen/Pact） | Accepted（契約 #2 已實作） |
| [0011](0011-web-ocs-types-generated.md) | 契約 #3 Part A：web 改吃 ocs-contract 生成的 TS 型別 | Accepted（契約 #3 Part A 已實作） |
| [0012](0012-embedding-as-a-service.md) | 嵌入服務化：自建 BGE-M3 容器（保留 dense+sparse、torch 移出 app） | Accepted |
| [0013](0013-naming-cleanup-caliburn.md) | 命名整理：web 改 Caliburn、內部去版號（graph_v3→authoring、/v3→/documents）、容器/DB 去 jobintel | Accepted |
| [0014](0014-db-image-stock-postgres.md) | DB image 降回 stock `postgres:16`（移除未使用的 pgvector；D5 後檢索走 Qdrant） | Accepted |
| [0015](0015-document-save-optimistic-concurrency.md) | 文件存檔採樂觀並發（version 守衛）；回合制協作不上 CRDT/OT；minimal 先、逐操作 full 延後 | Accepted（2a-minimal 已實作：雙 token version+revision、409 + ConflictDialog；full 延後） |
| [0016](0016-batch-task-catalog-endpoint.md) | 後端批次 task-catalog 端點（每 ocs_code 撈一次池）；前端 setQueryData 灌快取 | Accepted（模式由 0021 一般化；task-catalogs 端點與前端 seeding 已於 P3 退役） |
| [0017](0017-app-entry-single-composition-root.md) | 後端 app 入口收斂:單一組裝點 + `/healthz` 統一 + 移除 demo app（livez/readyz 待容器化） | Accepted |
| [0018](0018-indexer-dependency-degradation-policy.md) | indexer 依賴降級政策:critical fail-fast vs enrichment 降級 + `meta.partial`（circuit breaker 延後） | Accepted |
| [0019](0019-api-naming-alignment.md) | API 命名對齊:自訂方法 `:verb`、根層 `GET /occupations?q=`、`PUT occupations`（monorepo 原子改名、偏離 AIP-231/132 白紙黑字） | Accepted |
| [0020](0020-interview-authoring-interaction-model.md) | 訪談式撰寫互動模式:混合載體（文件常駐 + 精靈化訪談面板）；實作可重新設計、不受既有資產約束 | Accepted |
| [0021](0021-knowledge-pack-single-sync-point.md) | 知識包：選職類=唯一 knowledge 同步點；indexer 給資料/api 處理/web 讀寫；來源必標的資料基座 | Accepted（P1–P3 已實作：`/knowledge` 端點＋web 全選單切換＋舊四端點退役） |
| [0022](0022-similarity-matching-items-match.md) | 相似比對 `items:match`：indexer 確定性能力、FS 三區分帶、星型非遞移、非破壞呈現；survivorship 在 web；api 純搬運 | Accepted（v1 已實作：端點＋校準＋pack 掛載＋態度收合/任務徽章） |
| [0023](0023-interview-engine-stateless-turns.md) | 訪談引擎骨幹：無狀態回合服務＋軟階段＋指令詞彙表；quote 溯源；停止三重保險；全新實作不整合舊碼（部分翻案 0007） | Partially superseded by 0034（保留 provenance/全新實作原則） |
| [0024](0024-llm-wiring-select-schema.md) | LLM 接線：`LlmPort.select_schema`＋受限解碼路徑判準（OpenRouter strict 起步、對抗性驗收、escalation 槽；內裝首選 Pydantic AI） | Superseded by 0034 |
| [0025](0025-coedit-authority-dual-channel.md) | 人機共編權限：雙通道＋風險分流＋節點批審（分流寫入目的地，取代「人改過只能提議」） | Accepted（2026-07-05；spec/plan 待開） |
| [0026](0026-interview-turn-model-role.md) | 訪談回合獨立模型 role（`model_interview`=gpt-4.1-mini，強推理＋沿用 strict 零逃逸）；延伸 0024 | Superseded by 0034 |
| [0027](0027-interview-engine-v2-consultant-agent.md) | 訪談引擎 v2 四組件：顧問 agent（READ 工具、無寫入權）＋書記（兩通道 strict/quote、跨任務）＋確定性覆蓋帳本（門檻/飽和/閘門）＋backstop；風險分層核准（修正 0025 #1）；單信息源/純文字列 limitations | Superseded by 0034 |
| [0028](0028-interview-flow-shared-ui-curation.md) | 訪談流程 v2.1：AI 驅動既有編輯器 pickers（同 UI、追蹤修訂呈現）＋議程化彈性流程＋官方檢查表缺項探測（實際為準）＋態度收尾 pass（修正 0027 態度通道與 0025 批審載體） | Accepted（2026-07-09；真人實測 eb2af457 驅動） |
| [0029](0029-editor-menus-three-types-decoupling.md) | 編輯器選單三型（控制/參考/素材庫）＝純工具（無自動寫/自訂入口/AI 標記、一律獨立視窗）＋參考集合與文件身分脫鉤（主基準＝表頭職類視窗所選）＋OPLKS 全展開位置碼版式；AI 共編載體延後另裁 | Accepted（2026-07-11；七層設計討論收斂；AI 載體由 0030 定案） |
| [0030](0030-ai-coedit-tracked-changes-one-brain.md) | AI 層 v3：追蹤修訂直寫載體（`_pending` 四態＋條目級綠紅標＋無聲審閱記帳後用）＋一條腦（scribe 唯一寫入、舊 LangGraph/CopilotKit 退役）＋verify 六查＋對話層規則＋品質迴路（黃金範本/雙 suite/promptfoo CI）；部分修正 0025 批審載體與 0028 彈窗載體 | Partially superseded by 0034（保留 Web review/authority/eval 原則） |
| [0031](0031-occupation-suggest-card-refset-source.md) | 職類建議卡進對話流（推翻 0028 D1 職類段；預勾＋理由＋三出口）＋引擎參考碼＝profile∪doc 不變量（修 0029×0030 盲區鬼打牆）＋參考集合維持人選（否決 AI 代寫，記重啟條件）＋dismissed 知情話術；反騷擾緩做 | Accepted（2026-07-13；新手 persona 手測驗屍＋先例研究） |
| [0032](0032-task-carrier-routing.md) | 任務載體路由：有逐字證據→綠字直落（含官方殼）＋盤永遠人開（intake 邀請卡/收尾 offer/自取，AI 彈窗全退役）＋盤無預勾疊加層（curation 端點退役）＋不確定 ≤3→聊天卡；修正 0028 D1 任務段 | Accepted（2026-07-14；維護者質疑 b 案＋Copilot/PAIR/TurboTax/冷啟動先例） |
| [0033](0033-episode-agenda-consultant-tools.md) | 訪談議程 v4：事件（episode）驅動議程＝顧問議程工具（open/close_episode）＋覆蓋 artifact＋事件收割 pass（P 的家）＋guardrail 兜底＋異質模型（顧問升級）；退役 next_gap 梯子；修正 0027 帳本駕駛地位與 0028 議程載體 | Partially superseded by 0034（只保留 episode 概念） |
| [0034](0034-interview-ai-vnext-greenfield-evidence-workflow.md) | Interview AI vNext：greenfield evidence workflow＋單一 adaptive conversation owner＋app-owned state＋provider-neutral Capture/eval；不整合 v3 internals，達 gate 後刪舊 | Accepted（provider直連優先部分由0035修正） |
| [0035](0035-interview-vnext-openrouter-first-provider-boundary.md) | Interview AI vNext provider主線改為OpenRouter-first；Chat Completions作穩定基準、exact routing Capture/eval，直連供應商降為比較與備援 | Accepted（2026-07-17；V3-4R live conformance已完成） |
| [0036](0036-interview-vnext-provider-binding-conformance-and-idless-turn-v2.md) | Interview AI vNext runtime：Operation／ProviderBinding／adapter／conformance分層；wire與eligibility分離；Turn Interpreter v2移除model identity並加入qualifier evidence support | Accepted（2026-07-18；R3/R4已完成） |
| [0037](0037-interview-vnext-question-frame-contextual-evidence-and-employee-authority.md) | Interview AI vNext grounded short answer：persisted QuestionFrame、Evidence.v3 literal/contextual support、receipt、strict CAS與員工文件權威 | Accepted（2026-07-20；R5-BC已完成） |
| [0038](0038-interview-vnext-context-engine-and-professional-consultant-workflow.md) | Interview AI vNext產品工作流：operation-specific Context Engine、Agenda／Sufficiency、JobStateDigest、專業顧問operations、canonical Authoring Core與公版參考邊界 | **Superseded by 0040**（2026-07-26；完整取代。新方向見0040，勿據0038開新工） |
| [0039](0039-local-multi-document-canonical-public-form-workspace.md) | 本機多文件Workspace：單一操作者可保存多份JD、current canonical文件權威、公版樣式UI與autosave；MVP不做revision history | **Superseded by 0043**（原為 Proposed with owner amendment；勿據以施工） |
| [0040](0040-professional-consultant-engine-and-r1-validation-contract.md) | 專業顧問引擎greenfield與R1驗證契約：**Supersedes 0038（完整取代）**；強模型先建天花板+最小harness baseline+model×schema ablation；exit gate須有預先定義的實質改善、持平選簡單者；三層評審者；Current State唯一真相+append-only Journal+runtime外eval capture與Trial Manifest；portable schema+deterministic verifier；K/S/A四級支持度；公版匯出措辭 | **Accepted**（2026-07-26；owner核准＋第二位審查者複審後定案） |
| [0041](0041-r1-p0-closure-first-version-context-and-holdout.md) | R1-P0 結案（**不執行**，理由＝YAGNI＋外部證據，**非實驗結果**；frozen 資產保留）＋第一版 Context 採三層 Hybrid 安全預設（Source／Current Work Model／operation Context Packet，不建 literal-claim layer）＋**0040 六 arm 效力不變**（研究不取代 A/B）＋R1 八案**全數 development set**（答案已在必讀 spec 曝光，不切 holdout；改凍結期望；未曝光評測集延到 20–30 案擴充，以 freeze commit SHA+hash 的時序為憑、不得寫進 authority 文件，一人團隊只能稱 post-freeze fresh challenge set） | **Accepted**（2026-07-27；補充 0040；同日第二次審查兩輪十一項：採納十項、狀態異議經查證駁回並撤回） |

| [0042](0042-r1-screening-stop-and-a6-first-version-default.md) | 停止 R1 架構實驗（owner 時程裁決，**非實驗結論、非永久禁令**）＋A6（強模型／light schema／one-stage／full harness）作第一版實作預設；exit gate 暫停阻擋效力但判準未被否決；heavy schema／便宜模型／two-stage 截至第一版未量測；實驗欄位不得當 production contract，須另定 TaskAnalysis v1 契約；verifier／支持度四級／公版措辭等防線一律保留；兩個「三層」拆為 Runtime Context Stack 與 Product Authority Model | **Accepted**（2026-07-28；部分修正 0040 決定 9、0041 決定 11） |
| [0043](0043-job-analysis-local-current-state-persistence-and-authoring-authority.md) | `job_analysis` 本機 Current State persistence：greenfield、不搬／不整合／不雙寫舊資料；Current JD員工權威＋Work Model分析權威；四表hybrid relational/JSONB/Journal；分層編輯器；LLM transaction外、generation/read-set stale保護 | **Accepted**（2026-07-29；完整取代0039） |

完整脈絡見 [`../specs/2026-06-27-system-architecture-design.md`](../specs/2026-06-27-system-architecture-design.md)。
契約怎麼選/怎麼交付的規範見 [`../contract-strategy.md`](../contract-strategy.md)（ADR 0004/0010 的一般化、預答契約 #3）。
