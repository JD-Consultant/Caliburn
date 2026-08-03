# Caliburn — 文檔系統(架構・規則・索引)

> **關於文檔的文檔**:哪種文檔幹嘛、住哪、怎麼寫、怎麼維護,加現行索引。**給人也給 agent**。
> 動到文檔慣例時**同 commit 更新本檔**。為什麼這樣設計 → 兩份研究紀錄(§6)。

Caliburn 現階段的產品目標是**伺服器部署、瀏覽器存取的 AI 職務分析與職務說明書成品**。一個 deployment 先服務一個企業，
可由企業在內網／私有環境自管，或由我們代管；員工裝置不執行完整 stack。repo 仍保留早期 B2B／多租戶程式，但共享 SaaS、
公司／成員／權限／計費不在現行 roadmap；企業自管／我們代管 deployment 不得再被誤判成禁止項。完整範圍見
[`product-notes.md`](product-notes.md)與 [ADR 0044](adr/0044-server-deployed-browser-product.md)。完整 Web 先形成 release candidate；
只有通過真實在職員工以本人工作完成的 R9 端到端 pilot gate，才稱為員工可用成品。
Monorepo:Turborepo + per-app uv。

---

## 1. 文檔類型 taxonomy(先問「我要回答哪種需求」)

**Diátaxis**(Daniele Procida;Django/Cloudflare 等採用)把文檔按**讀者需求**分四型,兩軸交叉:
**習得↔應用**(learning vs working)× **實作↔認知**(action vs cognition)。
**核心鐵律:四型分開,別混在一份**——混型是文檔失敗的頭號主因。套到本 repo:

| 類型 | 回答什麼問題 | 主讀者 | 住哪 | Diátaxis |
|---|---|---|---|---|
| **ADR** | 為什麼這樣**決策**(脈絡 + 取捨) | 人 | `docs/adr/00NN-*.md` | explanation(決策) |
| **spec(研究紀錄)** | 為什麼這樣做(研究/診斷/選項/比對) | 人 | `docs/specs/<date>-*.md` | explanation(研究) |
| **plan** | 怎麼**建**(bite-size 實作步驟) | 人/agent | `docs/plans/<date>-*.md` | how-to(建置) |
| **design** | 這東西**怎麼運作**(端到端、click→request) | **agent**(也人) | `docs/design/`(跨 app)或該 app 底下 | reference + explanation |
| **README(索引)** | 這裡**有什麼、住哪**(地圖) | 人/agent | 各資料夾 / 各 app | reference(導引) |
| **runbook** | 怎麼**操作**(起停/排錯/部署) | 人 | `docs/runbook.md` | how-to(維運) |
| **判準文檔** | **何時選什麼**的判準 | 人 | `docs/contract-strategy.md`、`docs/service-split-framework.md` | explanation(決策輔助) |
| **契約 / schema** | 資料**長什麼樣、什麼規則** | 人/agent | `docs/ocs-schema.md`、`docs/ocs-source-json.md` + `packages/*` | reference |
| **CLAUDE.md / AGENTS.md** | agent **怎麼做事**(orientation + 規則) | **agent** | repo 根 + 各 app | agent instructions |
| **ARCHITECTURE.md** | 跨 app **鳥瞰** | 人/agent | repo 根 | reference/explanation |
| **product-notes** | 產品/UX **決策與延後項** | 人 | `docs/product-notes.md` | explanation |
| **CONTRIBUTING.md** | 新人**上手**(裝、跑、測) | 人 | repo 根 | how-to(onboarding) |

> 沒有「tutorial」型(內部 repo,無教學需求);onboarding 由 CONTRIBUTING.md 兼。

## 2. 擺放規則(blast radius + colocation)

| 文檔涵蓋範圍 | 放哪 |
|---|---|
| 跨 app / seam / 系統級 / 活的設計 | **中央 `docs/`** |
| 單一 app 內部 | **該 app 底下**(`apps/<app>/README.md`、`AGENTS.md`) |
| 歷史(不再維護,僅追溯) | **`docs/archive/`** |

- **monorepo 讓「放哪」只剩整潔問題**:中央 `docs/` 與 `apps/*` 同一棵樹、同一個 commit 就能一起改;
  「不漂」靠 §4 的 living 鐵律,不是資料夾距離(那是 polyrepo 的痛)。
- **可發現性 ≠ 位置**:文檔存在 ≠ 會被讀。跨 app 從根 `CLAUDE.md` 指路;app 內從該 app `AGENTS.md` 指。
  **沒被指到 = 白寫**(agent 不會自己逛到)。

## 3. 寫作規則(一份給人也給 LLM)

- **一份來源,不分叉**:別為 LLM 另寫一份或改寫措辭——那會同時害人也 poison the AI well。
  把 LLM 當**新通路,不是新讀者**。
- **內容寫給人,結構服從機器**:agent 會分塊檢索、會截斷、看不到視覺排版。
- **別把 Diátaxis 四型混在一份**(§1):要「為什麼」連去 ADR/spec,別把決策脈絡塞進 reference。
- **過關清單**(結構層,dual-audience)——完整版與爛/好對照見
  [`design/README.md`](design/README.md):
  - [ ] 每節自足(front-load context) [ ] 明講不靠推論(前提/真名/預設值)
  - [ ] 語意化階層(標題達意、清單優先) [ ] 表格 row-atomic(每列自成一句)
  - [ ] 關鍵資訊別藏(不只圖/摺疊/tab;附可複製範例)
- **自檢一問**:一個沒看過 code 的 LLM 讀完這段,會不會去**發明一個不存在的端點/欄位**?會 → 還不夠具體。

## 4. 維護規則(living / docs-as-code)

- **跟碼同 commit**:結構性改動就更新對應文檔,**放進同一個 PR**,當作 code review 的正式檢查點
  (docs-as-code:文檔跟碼同工作流、同 review)。
- **fossilization 是頭號壞味道**:沒跟碼走的文檔 → agent 拿舊資訊亂做/救回退役路徑。
  **過時的段落直接刪或修**;壞文檔比沒文檔糟。
- **owner = 動那條線的人**:「大家的事 = 沒人的事」;改子系統的人負責更新它的文檔。
- **能生成就別手寫**:codegen 擁有的別手維護(如 `packages/ocs-contract` 的 JSON-schema → TS 型別,
  比對用 `git diff`)。
- **定期審查**:高頻/關鍵文檔隨碼審;其餘偶爾巡,別等到明顯過時。

## 5. 索引(現行)

### 中央系統文檔

- [`specs/2026-06-27-system-architecture-design.md`](specs/2026-06-27-system-architecture-design.md) — **Historical foundation**：monorepo／契約優先／3 bounded context／Hexagonal+DDD仍保留；早期共享多租戶產品假設沒有恢復，現行是 ADR 0044 的單企業 deployment。
- [`specs/2026-08-02-r0-architecture-truth-and-production-cutover-research.md`](specs/2026-08-02-r0-architecture-truth-and-production-cutover-research.md) — **R0 切換 authority**：實際 router／三代資料真相比對、Strangler Fig／Parallel Change／PostgreSQL 研究、以整份document單寫者並存、PV1 outcome、inventory／單向匯入、rollback與G0–G5退役gate；員工電腦／localhost部署假設已由ADR 0044取代，single-writer決策見ADR 0041。
- [`specs/2026-07-18-interview-vnext-llm-runtime-architecture-review.md`](specs/2026-07-18-interview-vnext-llm-runtime-architecture-review.md) — **已核准的vNext LLM runtime 2026架構研究 authority**：交叉核對 OpenAI、Anthropic、Google、Microsoft、OpenRouter 與 OpenTelemetry 官方資料及真live診斷，確認deterministic workflow + Context Engine + own LLM Port + provider adapters主線；D1–D8已固化為ADR 0036。
- [`specs/2026-07-20-interview-vnext-professional-job-analysis-and-short-answer-architecture-research.md`](specs/2026-07-20-interview-vnext-professional-job-analysis-and-short-answer-architecture-research.md) — **已核准研究（Revision 6；R5 authority 見 ADR 0037／amendment。⚠ 原「post-R5 product authority 見 ADR 0038」已由 [ADR 0040](adr/0040-professional-consultant-engine-and-r1-validation-contract.md)（Accepted，2026-07-26）完整取代；post-R5 方向以0040與2026-07-25／26四份顧問文件為準，**本文件的post-R5段落已失效**）**：產品是「員工與 AI 顧問對話 + 同步 JD canvas」，員工 direct edit 是 draft truth，AI 只能建立可接受／修改／拒絕的 proposal；第一版不做 SaaS、公司 catalog 或多人協作。R5 使用 QuestionFrame + AnswerBinding + Evidence.v3 literal/contextual support與 frequency/current 分離。
- [`specs/2026-07-23-interview-vnext-question-selection-context-loop-research.md`](specs/2026-07-23-interview-vnext-question-selection-context-loop-research.md) — **已核准並落地的下一題選擇研究**：以2026現行OpenAI prompt guidance、Anthropic context/workflow/eval與Microsoft workflow官方方向核對，固定deterministic Agenda＋bounded Context＋typed question.select＋application QuestionFrame／command materialization；明確不採mega-prompt、planner agent、完整transcript、通用graph或SaaS。
- [`specs/2026-07-23-local-multi-document-jd-workspace-and-public-form-ui-research.md`](specs/2026-07-23-local-multi-document-jd-workspace-and-public-form-ui-research.md) — **Historical本機成品架構研究**：多文件、Interview／Authoring真相分離、公版欄位UI與Web資產仍可參考；員工電腦localhost與revision persistence分別由ADR 0044及2026-07-24 current-row裁決取代。
- [`specs/2026-07-24-job-authoring-v2-relational-storage-research.md`](specs/2026-07-24-job-authoring-v2-relational-storage-research.md) — **Active current-JD 內部表研究**：第一個成品不做版本歷史；每份 JD 只保存目前 relational state。此模型與deployment topology無關；內部另保留Task purpose/context/frequency/ownership/importance/typicality與選填工時比重，AI只可提出proposal，由員工accept/edit/reject。
- [`specs/2026-07-25-professional-job-analysis-consultant-process-final-red-team.md`](specs/2026-07-25-professional-job-analysis-consultant-process-final-red-team.md) — **顧問流程最終反方審查**：以單一員工自述偏差、職業與公版錨定、故事偏差、Task邊界、工具升格、長期Context偏差、O/P/K/S虛構與過早完成逐項攻擊既有方向；最終保留「固定分析責任、彈性訪談路徑、全域理解、跨故事整併、反證檢查」，並定義完整顧問循環、16類精簡capability cases與第一版品質gate。
- [`specs/2026-07-25-professional-job-analysis-consultant-llm-architecture-red-team.md`](specs/2026-07-25-professional-job-analysis-consultant-llm-architecture-red-team.md) — **顧問流程的 greenfield LLM 程式架構（Revision 3）**：不受 vNext／舊 API／既有資料表約束，先以最強反方攻擊單一大 Agent、固定欄位流水線、Planner／多 Agent與Graph複雜度，再收斂為「受約束的自適應顧問核心」；明確區分Source／Work／Document三層、Work Graph（知道什麼）與Execution Graph（接下來做什麼），採resident state＋ephemeral LLM operations、普通application controller與選擇性Reviewer，不把Graph新名詞誤做成第一版框架。
- [`specs/2026-07-25-professional-consultant-architecture-realization-roadmap.md`](specs/2026-07-25-professional-consultant-architecture-realization-roadmap.md) — **顧問核心最終架構實現路線圖（已含2026-07-26與2026-08-03修訂）**：採R0–R9薄垂直切片；先以R1 Task Discovery證明工作邊界，再依序完成多輪Context／Loop、恢復、Duty與O/P/K/S/A、Proposal／Current JD、公版challenger、完成反方檢查與server-deployed Web。R8只形成release candidate，R9真實員工pilot是第一版發布gate；不先做共享SaaS、Graph runtime或多Agent。模型與評測仍採最強模型天花板、model×schema ablation、分階段案例與critical pass³。
- [`specs/2026-07-25-professional-consultant-r1-task-discovery-deep-research.md`](specs/2026-07-25-professional-consultant-r1-task-discovery-deep-research.md) — **R1 Task Discovery 深入研究（Task粒度與混合式路線已確認；實作plan已於2026-08-03建立）**：交叉閱讀iCAP、O*NET、OPM及OpenAI／Anthropic現行官方方法，拒絕「一句話直接抽Task」與工具／步驟升格，定義Message→Claim→Story／Work Unit→Task Candidate的專業語意、Task六項判準、8個capability cases（快速篩選）、baseline比較、strongest-case反方與Stop／Rework條件；未有獨立plan前不接Web、資料庫、OPKS、Graph runtime或多Agent。**「兩次模型呼叫」已降級為待實驗假說**（持平時選一次呼叫），且Structured Output契約改為portable subset＋deterministic verifier＋endpoint pinning；混合式路線見ADR 0042。
- [`specs/2026-07-26-professional-consultant-r1-red-team-review-and-corrections.md`](specs/2026-07-26-professional-consultant-r1-red-team-review-and-corrections.md) — **上列四份顧問文件的外部紅隊複審與修訂裁決（C-01～C-09）**：以2026大廠工程文件（OpenAI model selection／Anthropic harness design、demystifying evals、managed agents／OpenRouter structured outputs）、法規（職能發展及應用推動要點）與同行審查文獻（Morgeson et al. 2004、Fowler）逐項攻擊；裁定模型策略反轉、exit gate加硬、案例三階段、評審者三層、Current State＋append-only Journal＋runtime外eval capture、portable schema責任表、K/S/A四級支持度與公版匯出措辭。含**被撤回主張表**與帶日期的provider附錄。決策見ADR 0040。
- [`specs/2026-08-03-r1-offline-contract-verifier-implementation-research.md`](specs/2026-08-03-r1-offline-contract-verifier-implementation-research.md) — **R1 T1 實作研究**：依 Pydantic 2／Python JSON／OpenRouter 官方文件比較 strict frozen contract、portable schema、deterministic verifier 與 fixture 隔離；裁定新 `app.professional_consultant` 不重用 vNext domain/eval authority，runtime loader 不讀 expectations/adjudication。
- [`specs/2026-08-03-r1-t2-prompt-schema-scripted-runner-research.md`](specs/2026-08-03-r1-t2-prompt-schema-scripted-runner-research.md) — **R1 T2 實作研究**：依 Pydantic／OpenRouter／Python 官方文件固定同 shape 的 light structural-only／heavy descriptions schema、neutral async Protocol、strict JSON→schema→verifier 邊界與四類 failure；OpenRouter wire/preflight 留在 T4。
- [`specs/2026-08-03-ai-conversational-job-analysis-discovery-route-research.md`](specs/2026-08-03-ai-conversational-job-analysis-discovery-route-research.md) — **混合式職務發現研究**：以 iCAP、O*NET、OPM 第一方資料比較純上而下、純故事式與混合式；裁定暫定框架＋開放敘事＋定向補漏，跨敘事形成 Task、再歸納 Duty，Task 穩定後共同定義 O/P 並連結 KSA。決策見 ADR 0042。
- [`specs/2026-08-03-real-employee-pilot-release-gate-research.md`](specs/2026-08-03-real-employee-pilot-release-gate-research.md) — **真實員工試用發布門檻研究**：以 iCAP、OPM／O*NET、GOV.UK、NIST 與 OpenAI 第一方資料區分工程 eval、真人 pilot 與 release decision；定義 actual incumbent、五類觀察面、pass／rework／invalid 結構及最小稽核 artifacts，樣本與數值門檻留待 pilot 前核准。決策見 ADR 0043。
- [`specs/2026-08-03-server-deployed-browser-product-scope-research.md`](specs/2026-08-03-server-deployed-browser-product-scope-research.md) — **Server deployment 範圍校正**：區分員工個人localhost與企業本地伺服器；採單企業deployment，可由企業自管或我們代管；development localhost不是產品boundary，共享多租戶與access model另案。決策見ADR 0044。
- [`specs/2026-07-16-interview-ai-vnext-greenfield-architecture.md`](specs/2026-07-16-interview-ai-vnext-greenfield-architecture.md) — **vNext 目標架構**：不整合／保留 v3 LLM internals；依 OpenAI、Anthropic、Google、Microsoft 2026 官方方向，採 Evidence-first durable workflow、單一 adaptive conversation owner、typed LLM operations、app-owned state、deterministic reducers/verifiers/projector、provider-neutral Capture/eval；含完整 runtime、資料契約、context、provider、評測與切換／刪舊規格。
- [`specs/2026-07-16-interview-vnext-v2-provider-capture-research.md`](specs/2026-07-16-interview-vnext-v2-provider-capture-research.md) — **V2 實作前 2026 官方差異再驗證**：逐頁核對 OpenAI Responses/state/structured output/compaction/background/cache/eval 及 Anthropic Messages/structured output/stop reason/context/cache/Managed Agents；定義 neutral operation/result/failure、artifact/event/outbox/checkpoint 與 recovery matrix，排除 provider state、client compaction、舊 Evals 平台等過時或錯置做法。
- [`specs/2026-07-16-interview-vnext-v2b-durable-persistence-research.md`](specs/2026-07-16-interview-vnext-v2b-durable-persistence-research.md) — **V2-B durable persistence權威 reference**：依 PostgreSQL 16/18、SQLAlchemy 2.0、Alembic與AWS transactional outbox官方資料，固定八表欄位/constraints/indexes/triggers、canonical TEXT、async UoW/CAS、atomic transaction、`SKIP LOCKED` lease SQL、crash recovery matrix、migration/rollback與22個最低 Postgres tests；實作者不得自行猜 persistence語意。
- [`plans/2026-07-16-interview-ai-vnext-implementation-plan.md`](plans/2026-07-16-interview-ai-vnext-implementation-plan.md) — **vNext 實作順序**：V0–V8 工作包，逐檔案、schema、migration、測試、hard gate、OpenRouter model/endpoint bake-off、必要direct-vendor對照、pilot、rollback 與 v3 刪除條件。
- [`plans/2026-07-16-interview-vnext-v2b-durable-persistence-plan.md`](plans/2026-07-16-interview-vnext-v2b-durable-persistence-plan.md) — **可直接交給下一位實作者的 V2-B 計畫**：拆成 dependency freshness、ports/serialization、0010 migration、repositories/UoW、durable Capture/outbox、checkpoint recovery與final verification七個可 review切片，列明逐檔案工作、SQL邊界、測試與 code-review checklist。
- [`specs/2026-07-17-interview-vnext-v3-fixed-replay-research.md`](specs/2026-07-17-interview-vnext-v3-fixed-replay-research.md) — **已核准的V3 fixed replay權威 reference**：依 OpenAI/Anthropic 2026 現行 Structured Outputs、Context Engineering與eval官方資料，加上O*NET 30.1 task/activity/skill/ability分層，定義正式 ContextBuilder、`turn_interpret`/`episode_code`、proposal ID/span、partial/no-op commit、eval-only Responses adapter、20個 component tasks與多 trial hard gates；明確不依賴將於2026-11關閉的 OpenAI Evals平台。
- [`plans/2026-07-17-interview-vnext-v3-fixed-replay-plan.md`](plans/2026-07-17-interview-vnext-v3-fixed-replay-plan.md) — **已核准執行的V3計畫**：拆成SDK freshness/no-op persisted contract、ContextBuilder、turn extraction、durable executor、eval-only OpenAI adapter、turn gate、episode coding與完整實驗等可 review切片，逐檔案、transaction、測試、live eval與停線條件均已列明。
- [`adr/0035-interview-vnext-openrouter-first-provider-boundary.md`](adr/0035-interview-vnext-openrouter-first-provider-boundary.md) — **OpenRouter-first provider決策**：production/eval主線改測真正gateway；stable Chat作第一基準，exact model/endpoint與routing Capture，官方直連依入選模型作比較／備援。
- [`adr/0036-interview-vnext-provider-binding-conformance-and-idless-turn-v2.md`](adr/0036-interview-vnext-provider-binding-conformance-and-idless-turn-v2.md) — **V3-5A runtime重構決策**：Operation/ProviderBinding/adapter/conformance四層、wire outcome與route eligibility分離、application ordinal identity、qualifier exact support、C1先於C2、migration維持0010。
- [`adr/0037-interview-vnext-question-frame-contextual-evidence-and-employee-authority.md`](adr/0037-interview-vnext-question-frame-contextual-evidence-and-employee-authority.md) — **R5 grounded short-answer與未來共編authority**：persisted QuestionFrame、Evidence.v3 discriminated support、每turn receipt、frequency/time分離、state-version CAS；員工是文件authority，R5不依賴editor，migration維持0010。
- [`adr/0038-interview-vnext-context-engine-and-professional-consultant-workflow.md`](adr/0038-interview-vnext-context-engine-and-professional-consultant-workflow.md) — **⚠ Superseded by 0040（2026-07-26）；勿據此開新工**。原內容：固定application workflow、operation-specific Context Engine、Agenda／Sufficiency、deterministic JobStateDigest、canonical Authoring Core、task-centered proposal、公版參考與R5-D bounded closure。新方向見ADR 0040與2026-07-25／26四份顧問文件。
- [`adr/0040-professional-consultant-engine-and-r1-validation-contract.md`](adr/0040-professional-consultant-engine-and-r1-validation-contract.md) — **專業顧問引擎greenfield與R1驗證契約（Accepted，2026-07-26）**：**完整取代0038**；R1六個arm的快篩矩陣（A1最強＋輕＋一次呼叫＋minimal harness／A2–A5兩階段model×schema 2×2／A6最強＋輕＋一次呼叫＋full harness，各比較只動一個變因，持平選簡單者）、exit gate須有預先定義的實質改善、案例三階段與`case_family_id`／`source_type`、三層評審者（Rubric資產／blind grader／product challenger）、Current State唯一真相＋同交易append-only Journal＋runtime外eval capture與Trial Manifest、portable schema＋deterministic verifier＋endpoint pinning、K/S/A四級支持度、公版匯出措辭。
- [`adr/0041-document-boundary-single-writer-cutover.md`](adr/0041-document-boundary-single-writer-cutover.md) — **production cutover／退役決策（Accepted，2026-08-02）**：以整份`document_id`為切換單位、同一文件單一writer；v3 maintenance-only；R1–R5過gate才掛PV1；禁止OCS/current-row dual-write；inventory／單向匯入後分task移除舊Web、route、code與table。
- [`adr/0042-hybrid-job-discovery-and-ttop-formation.md`](adr/0042-hybrid-job-discovery-and-ttop-formation.md) — **混合式職務發現決策（Accepted，2026-08-03）**：暫定職務框架與reference只作假說；開放敘事加定向補漏、跨敘事形成Task後歸納Duty，Task穩定後共同定義O/P，KSA須有linkage／支持度並經人確認。
- [`adr/0043-real-employee-pilot-release-gate.md`](adr/0043-real-employee-pilot-release-gate.md) — **真實員工試用發布門檻（Accepted，2026-08-03）**：R8是Web release candidate，R9必須由實際在職員工以本人工作完成端到端pilot；合成eval、高擬真transcript、內部自測與非操作者專家審閱不能取代。其localhost部署字句由ADR 0044取代，真人gate保留。
- [`adr/0044-server-deployed-browser-product.md`](adr/0044-server-deployed-browser-product.md) — **Server-deployed browser product（Accepted，2026-08-03）**：企業自管或我們代管同一套單企業deployment；R8補production Compose／TLS／維運gate，員工電腦localhost假設失效，共享多租戶與identity另案。
- [`adr/0039-local-multi-document-canonical-public-form-workspace.md`](adr/0039-local-multi-document-canonical-public-form-workspace.md) — **Proposed with owner amendment**：一次開一份、可保存多份JD；公版樣式canvas是canonical view，舊profile/OCS PATCH不回核心。current-row由2026-07-24 amendment固定，員工電腦localhost topology由ADR 0044取代。
- [`plans/2026-07-17-interview-vnext-v3-4r-openrouter-first-adapter-plan.md`](plans/2026-07-17-interview-vnext-v3-4r-openrouter-first-adapter-plan.md) — **已完成且live-verified的V3-4R規格／證據**：依OpenRouter官方Chat/Structured Outputs/Models/Endpoints/Routing/Metadata/Errors/Usage/Plugins/Privacy固定direct HTTP、exact model ID+permanent canonical、exact endpoint、fallback/plugins/cache off、single-call與完整Capture；2026-07-18以Claude Sonnet 5 + Anthropic endpoint通過真probe，focused 148、full API/PostgreSQL 762 passed（0 skipped），並記錄真metadata揭露的dual model identity修正。下一步為V3-5 12-case multi-trial品質gate。
- [`plans/2026-07-18-interview-vnext-v3-5-turn-eval-harness-plan.md`](plans/2026-07-18-interview-vnext-v3-5-turn-eval-harness-plan.md) — **E0–E8 executable 已落地、true live 已嘗試但不具品質裁決資格的V3-5詳細規格**：harness與887 passed/0 skipped保留；batch `5bad4e3f-...`因provider route contamination停線，並揭露model-generated proposal identity、unsupported qualifier與offline grader drift三個不同架構缺口。V3-6保持blocked，下一步以2026-07-18 runtime架構審查為準。
- [`plans/2026-07-18-interview-vnext-v3-5a-runtime-contract-reconstruction-plan.md`](plans/2026-07-18-interview-vnext-v3-5a-runtime-contract-reconstruction-plan.md) — **V3-5A mother plan；R1–R4完成、R5新authority已核准**：provider runtime條文仍有效；舊§9/R5由2026-07-20 amendment取代；不新增0011、不做production route/direct provider。
- [`plans/2026-07-20-interview-vnext-v3-5a-r5-grounded-short-answer-amendment-plan.md`](plans/2026-07-20-interview-vnext-v3-5a-r5-grounded-short-answer-amendment-plan.md) — **Approved的R5總體authority；R5-A／R5-BC／R5-D均已完成**：逐欄QuestionFrame／Evidence.v3／receipt／State.v3／commands/events、Context/Input/Output/Verifier 2.0.0、frequency policy、stale CAS、persistence/recovery/Capture closure、20-case matrix與交付格式。
- [`plans/2026-07-22-interview-vnext-v3-5a-r5-bc-domain-context-hard-cut-plan.md`](plans/2026-07-22-interview-vnext-v3-5a-r5-bc-domain-context-hard-cut-plan.md) — **已完成的R5-BC母施工authority（最終證據見§23）**：Evidence/State/commands/events、Context/Input/Output/Verifier、每turn receipt、CAS/recovery、Capture minimum closure及12-case eval v2 hard cut已原子落地；TI-09/TI-10使用interleaved deterministic eval-only prior seed，不放寬State invariant、不改transcript語意。full API no-network `1071/198/0`，full API＋real PostgreSQL `1269/0/0`；Alembic仍0010，無新dependency、paid live或production/Web/editor改動。
- [`plans/2026-07-22-interview-vnext-v3-5a-r5-d-bounded-correctness-closure-plan.md`](plans/2026-07-22-interview-vnext-v3-5a-r5-d-bounded-correctness-closure-plan.md) — **已完成的R5-D bounded closure（交付證據見§17）**：Turn Interpreter terminal root closure、ArtifactRecord／manifest artifact離線重驗、committed／receipt-only／stale／schema-invalid損毀矩陣、實體bundle雙寫byte identity與既有12-case frozen gate均已封口；未動domain/schema/migration/provider/case，suite hash未變。full API no-network `1071/211/0`（+13為新real-PG test nodes），full API＋real PostgreSQL `1282/0/0`；下一步最小Authoring Core。
- [`plans/2026-07-23-interview-vnext-minimal-authoring-core-plan.md`](plans/2026-07-23-interview-vnext-minimal-authoring-core-plan.md) — **已完成的歷史A1 prototype（交付證據見§21）**：獨立`job_authoring`、task＋optional outputs snapshot revision、employee direct edit、scripted proposal accept/edit/reject/stale與digest；migration 0011三表保留，但revision authority已被current-row v2裁決取代。當時記載的後續workspace順序已失效，現行下一步是ADR 0040 R1。
- [`plans/2026-07-23-interview-vnext-question-select-context-loop-plan.md`](plans/2026-07-23-interview-vnext-question-select-context-loop-plan.md) — **已完成的`question.select/1.0.0`最小垂直切片（交付證據見§7）**：最多三個高價值gap、Evidence／JobStateDigest bounded Context、精簡prompt、portable output、local verifier、output/purpose slot QuestionFrame、broaden/open episode與existing gap asked command plan；code commit `ba1e4b8`，full no-network `1166/217/0`，無migration/provider live/Web/SaaS。
- [`plans/2026-07-23-interview-vnext-production-openrouter-consultant-loop-plan.md`](plans/2026-07-23-interview-vnext-production-openrouter-consultant-loop-plan.md) — **已完成的歷史 backend donor vertical（交付證據見§5）**：OpenRouter wire、`turn.interpret`／`question.select`、atomic question command、STOP／explicit-shift與固定 GPT-5.4 mini `openai/flex` 均已測；但未掛正式router，operation/state已失去產品authority。當時「下一步接localhost Web」已被ADR 0040取代，現行下一步是新R1 Task Discovery。
- [`plans/2026-08-03-real-employee-pilot-release-gate-decision-plan.md`](plans/2026-08-03-real-employee-pilot-release-gate-decision-plan.md) — **已完成的發布門檻決策紀錄**：同步 ADR 0043、產品／架構／roadmap 語意與 glossary；不執行 pilot，也不代定樣本數或數值門檻。
- [`plans/2026-07-23-local-web-jd-workspace-plan.md`](plans/2026-07-23-local-web-jd-workspace-plan.md) — **Superseded，禁止施工**：revision authority與員工電腦localhost topology均已失效；不得據此建立新 route。
- [`plans/2026-08-02-professional-consultant-production-cutover-plan.md`](plans/2026-08-02-professional-consultant-production-cutover-plan.md) — **現行 PV1／退役施工順序**：R0文件鎖、R1–R5前置gate、cross-language contract、current-row persistence、`job_workspace`、API/Web、inventory／可選importer、新文件cutover與三段legacy退役；每段列明測試與停線條件。
- [`plans/2026-08-03-r1-task-discovery-offline-implementation-plan.md`](plans/2026-08-03-r1-task-discovery-offline-implementation-plan.md) — **R1 現行施工計畫**：T1 authority bundle 與 T2 prompt/schema/scripted runners 已實作；下一步是 A1–A6 harness/Capture，再做 blind grader/CLI/preflight，另有付費授權時才做 live eval；未通過 gate 不進 R2。
- [`plans/2026-08-03-server-deployed-browser-scope-correction-plan.md`](plans/2026-08-03-server-deployed-browser-scope-correction-plan.md) — **部署範圍校正施工紀錄**：同步ADR 0044、active authority、R8與runbook；不改runtime或提前實作identity／共享SaaS。
- [`plans/2026-07-22-interview-vnext-v3-5a-r5-bc-phase-3-5-corrective-plan.md`](plans/2026-07-22-interview-vnext-v3-5a-r5-bc-phase-3-5-corrective-plan.md) — **已完成的R5-BC code-review corrective**：Evidence.v3 consumer、Context source hash、verifier marker／false-specificity／duplicate all-drop／system insufficiency、transaction內typed stale CAS、outcome與Capture roots均已封口；最終執行紀錄含C4–C6、Phase 4與exact gates，不新增migration、dependency、provider行為或通用框架。
- [`plans/2026-07-21-interview-vnext-v3-5a-r5-a-corrective-contract-closure-plan.md`](plans/2026-07-21-interview-vnext-v3-5a-r5-a-corrective-contract-closure-plan.md) — **已完成的R5前置corrective（commit `09f406a`，執行結果見§15）**：QuoteSpan／QuoteMatch ownership移到support模組，建立`support -> identifiers/base`、`evidence -> support`單向依賴，AST guard＋fresh-process測試禁止late-import cycle與雙份class；QuestionFrame補`closed_at >= opened_at`（equal合法）。no-network `1020/197/0`、real PostgreSQL focused `64/0/0`、`*.schema.json`零diff、Alembic仍0010；後續施工單位為R5-BC。
- [`plans/2026-07-19-interview-vnext-v3-5a-r3-corrective-plan.md`](plans/2026-07-19-interview-vnext-v3-5a-r3-corrective-plan.md) — **已完成的R3 runtime integrity修正與最終證據**：exact adapter/config/projection binding、typed result/evidence/conformance durable gate、所有terminal fresh-process recovery重驗、Capture events與multi-attempt manifest closure；corrective commits `e1716c8`/`2cf3404`/`1eaa774`，real PostgreSQL vNext 653/0 skipped、完整no-network 844/0 fail。R4實作已解鎖，paid live/V3-6仍blocked。
- [`plans/2026-07-19-interview-vnext-v3-5a-r4-provider-evidence-conformance-plan.md`](plans/2026-07-19-interview-vnext-v3-5a-r4-provider-evidence-conformance-plan.md) — **已完成的R4 provider wire/evidence/conformance分離與最終證據（§19）**：adapter只normalize wire facts（pure `openrouter_routing`、official nested/legacy endpoints、pipeline/cache分類、endpoint attestation），eligibility由application `attribution-strict/1.0.0`判定，probe/Capture保存result/evidence/conformance closure，scheduler以`provider.conformance_failed`停線；commits `aee798a`/`a814789`/`067504b`＋R4-C/R4-C2 correctives（null pipeline／attempts矛盾／blank-string／usage-cost數值外洩，§19.1–§19.2），no-network 951/197/0、interview_vnext+real PG 760/0 skipped。R5解鎖，paid live/production仍blocked。
- [`plans/2026-07-17-interview-vnext-v3-4-openai-responses-adapter-plan.md`](plans/2026-07-17-interview-vnext-v3-4-openai-responses-adapter-plan.md) — **已完成的direct OpenAI reference規格**：adapter/mock/live-bundle suite 66 passed、完整API/PostgreSQL 614 passed；官方OpenAI live尚未執行且依ADR 0035降為optional GPT direct comparison，不再阻擋主線。
- [`specs/2026-07-15-evidence-first-stateful-workflow-reconstruction-research.md`](specs/2026-07-15-evidence-first-stateful-workflow-reconstruction-research.md) — **上游研究紀錄／舊漸進路線已被取代**：保留 2025–2026 一手來源、Anthropic Interviewer、職務分析、Evidence/Agenda、eval 與 database audit 證據；不得再依其 C0→C1 指示改 v3 runtime。
- [`specs/2026-07-15-c0-c1-interview-eval-experiment-plan.md`](specs/2026-07-15-c0-c1-interview-eval-experiment-plan.md) — **eval 方法保留／C1 實作路線被取代**：balanced cases、claim gold、fixed/branching eval、多 trial、hard gate 與 v3 black-box baseline 仍有效；不再授權在 v3 內實作 C1 或補深度 provider trace。
- [`design/`](design/) — **子系統端到端設計(agent-facing)**；現有 [`editor-knowledge-pack.md`](design/editor-knowledge-pack.md)、[`interview-engine.md`](design/interview-engine.md)（ACTIVE／TRANSITIONAL）與 [`professional-consultant-engine.md`](design/professional-consultant-engine.md)（R1 T2 partial；新route未實作）。寫法見 [`design/README.md`](design/README.md)。
- [`adr/`](adr/) — Architecture Decision Records(決策的「為什麼」+ 取捨；**0001–0044**)；AI方向以[ADR 0040](adr/0040-professional-consultant-engine-and-r1-validation-contract.md)為準，production切換／退役以[ADR 0041](adr/0041-document-boundary-single-writer-cutover.md)為準，職務發現語意以[ADR 0042](adr/0042-hybrid-job-discovery-and-ttop-formation.md)為準，deployment boundary以[ADR 0044](adr/0044-server-deployed-browser-product.md)為準。0038已被0040取代。
- [`specs/`](specs/) — 研究紀錄(研究/診斷/選項/比對)。
- [`plans/`](plans/) — bite-size 實作計畫。
- [`ocs-schema.md`](ocs-schema.md) — OCS **著作產出**文件 JSON 結構與代碼規則(T/P/O/K/S/A);`packages/ocs-contract` 依據。
- [`ocs-source-json.md`](ocs-source-json.md) — OCS **來源**(PDF→JSON)契約注意事項:欄位基數、indexer 取用。
- [`contract-strategy.md`](contract-strategy.md) — 替 seam 選契約機制的判準(#1 JSON-schema、#2 共用 pydantic、預答 #3)。
- [`service-split-framework.md`](service-split-framework.md) — 何時拆「服務」vs 拆「repo」vs 留模組。
- [`product-notes.md`](product-notes.md) — 產品/UX 決策與延後項。
- [`runbook.md`](runbook.md) — 維運:起停、重啟紀律、故障排除、部署。
- 根目錄 [`../ARCHITECTURE.md`](../ARCHITECTURE.md)(跨 app 鳥瞰)· [`../CONTRIBUTING.md`](../CONTRIBUTING.md)(上手)· [`../CLAUDE.md`](../CLAUDE.md)(agent orientation,含指路)。

### 各 app 自帶文檔(colocated)

各 app 的 README 含:定位一句 / 跑・測試 / codemap / 關鍵流程(runtime view)/ 不變量 /
介面 reference / 指路(embedder 服務簡單,README 亦精簡)。寫法依據見 [`specs/2026-07-03-app-developer-docs-research.md`](specs/2026-07-03-app-developer-docs-research.md)。

- [`apps/api/README.md`](../apps/api/README.md) — FastAPI + 訪談引擎:六邊形 codemap、REST 端點面、文件 of-record 生命週期。
- [`apps/web/README.md`](../apps/web/README.md) — Next.js:query 資料層、autosave/409 流程、選擇性持久化。
- [`apps/ocs-indexer/README.md`](../apps/ocs-indexer/README.md) — Qdrant 知識/查詢服務:v4 payload、index/查詢流程、查詢 API 面。
- [`apps/embedder/README.md`](../apps/embedder/README.md) — BGE-M3 GPU 嵌入容器(ADR 0012)。
- [`apps/pdf-to-json/README.md`](../apps/pdf-to-json/README.md) — OCS PDF→JSON ETL(Pipes-and-Filters);其 §1–10 亦為**權威 OCS 來源 JSON 契約**。

### 歷史

- [`archive/jobintel-v3/`](archive/jobintel-v3/) — 併入 monorepo 前的 jobintel-ai v3 設計/決策/計畫(2026-06-14～06-27),供追溯。

## 6. 為什麼這樣設計(研究來源)

- [`specs/2026-07-03-agent-facing-docs-research.md`](specs/2026-07-03-agent-facing-docs-research.md) — agent-facing + dual-audience(Anthropic context engineering / AGENTS.md / llms.txt / config-smells / Mintlify / passo.uno / kapa / State of Docs / Diátaxis)。
- [`specs/2026-07-03-app-developer-docs-research.md`](specs/2026-07-03-app-developer-docs-research.md) — 人向 per-app README(matklad / Diátaxis / arc42 / Google)。
