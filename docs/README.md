# Caliburn — 文檔系統(架構・規則・索引)

> **關於文檔的文檔**:哪種文檔幹嘛、住哪、怎麼寫、怎麼維護,加現行索引。**給人也給 agent**。
> 動到文檔慣例時**同 commit 更新本檔**。為什麼這樣設計 → 兩份研究紀錄(§6)。

Caliburn = 給顧問用的多租戶 B2B SaaS(職能基準 OCS → 職務說明書)。Monorepo:Turborepo + per-app uv。

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

- [`specs/2026-06-27-system-architecture-design.md`](specs/2026-06-27-system-architecture-design.md) — 大框架(monorepo / 契約優先 / 3 bounded context / Hexagonal+DDD / 多租戶)。
- [`specs/2026-07-18-interview-vnext-llm-runtime-architecture-review.md`](specs/2026-07-18-interview-vnext-llm-runtime-architecture-review.md) — **已核准的vNext LLM runtime 2026架構研究 authority**：交叉核對 OpenAI、Anthropic、Google、Microsoft、OpenRouter 與 OpenTelemetry 官方資料及真live診斷，確認deterministic workflow + Context Engine + own LLM Port + provider adapters主線；D1–D8已固化為ADR 0036。
- [`specs/2026-07-16-interview-ai-vnext-greenfield-architecture.md`](specs/2026-07-16-interview-ai-vnext-greenfield-architecture.md) — **vNext 目標架構**：不整合／保留 v3 LLM internals；依 OpenAI、Anthropic、Google、Microsoft 2026 官方方向，採 Evidence-first durable workflow、單一 adaptive conversation owner、typed LLM operations、app-owned state、deterministic reducers/verifiers/projector、provider-neutral Capture/eval；含完整 runtime、資料契約、context、provider、評測與切換／刪舊規格。
- [`specs/2026-07-16-interview-vnext-v2-provider-capture-research.md`](specs/2026-07-16-interview-vnext-v2-provider-capture-research.md) — **V2 實作前 2026 官方差異再驗證**：逐頁核對 OpenAI Responses/state/structured output/compaction/background/cache/eval 及 Anthropic Messages/structured output/stop reason/context/cache/Managed Agents；定義 neutral operation/result/failure、artifact/event/outbox/checkpoint 與 recovery matrix，排除 provider state、client compaction、舊 Evals 平台等過時或錯置做法。
- [`specs/2026-07-16-interview-vnext-v2b-durable-persistence-research.md`](specs/2026-07-16-interview-vnext-v2b-durable-persistence-research.md) — **V2-B durable persistence權威 reference**：依 PostgreSQL 16/18、SQLAlchemy 2.0、Alembic與AWS transactional outbox官方資料，固定八表欄位/constraints/indexes/triggers、canonical TEXT、async UoW/CAS、atomic transaction、`SKIP LOCKED` lease SQL、crash recovery matrix、migration/rollback與22個最低 Postgres tests；實作者不得自行猜 persistence語意。
- [`plans/2026-07-16-interview-ai-vnext-implementation-plan.md`](plans/2026-07-16-interview-ai-vnext-implementation-plan.md) — **vNext 實作順序**：V0–V8 工作包，逐檔案、schema、migration、測試、hard gate、OpenRouter model/endpoint bake-off、必要direct-vendor對照、pilot、rollback 與 v3 刪除條件。
- [`plans/2026-07-16-interview-vnext-v2b-durable-persistence-plan.md`](plans/2026-07-16-interview-vnext-v2b-durable-persistence-plan.md) — **可直接交給下一位實作者的 V2-B 計畫**：拆成 dependency freshness、ports/serialization、0010 migration、repositories/UoW、durable Capture/outbox、checkpoint recovery與final verification七個可 review切片，列明逐檔案工作、SQL邊界、測試與 code-review checklist。
- [`specs/2026-07-17-interview-vnext-v3-fixed-replay-research.md`](specs/2026-07-17-interview-vnext-v3-fixed-replay-research.md) — **已核准的V3 fixed replay權威 reference**：依 OpenAI/Anthropic 2026 現行 Structured Outputs、Context Engineering與eval官方資料，加上O*NET 30.1 task/activity/skill/ability分層，定義正式 ContextBuilder、`turn_interpret`/`episode_code`、proposal ID/span、partial/no-op commit、eval-only Responses adapter、20個 component tasks與多 trial hard gates；明確不依賴將於2026-11關閉的 OpenAI Evals平台。
- [`plans/2026-07-17-interview-vnext-v3-fixed-replay-plan.md`](plans/2026-07-17-interview-vnext-v3-fixed-replay-plan.md) — **已核准執行的V3計畫**：拆成SDK freshness/no-op persisted contract、ContextBuilder、turn extraction、durable executor、eval-only OpenAI adapter、turn gate、episode coding與完整實驗等可 review切片，逐檔案、transaction、測試、live eval與停線條件均已列明。
- [`adr/0035-interview-vnext-openrouter-first-provider-boundary.md`](adr/0035-interview-vnext-openrouter-first-provider-boundary.md) — **OpenRouter-first provider決策**：production/eval主線改測真正gateway；stable Chat作第一基準，exact model/endpoint與routing Capture，官方直連依入選模型作比較／備援。
- [`adr/0036-interview-vnext-provider-binding-conformance-and-idless-turn-v2.md`](adr/0036-interview-vnext-provider-binding-conformance-and-idless-turn-v2.md) — **V3-5A runtime重構決策**：Operation/ProviderBinding/adapter/conformance四層、wire outcome與route eligibility分離、application ordinal identity、qualifier exact support、C1先於C2、migration維持0010。
- [`plans/2026-07-17-interview-vnext-v3-4r-openrouter-first-adapter-plan.md`](plans/2026-07-17-interview-vnext-v3-4r-openrouter-first-adapter-plan.md) — **已完成且live-verified的V3-4R規格／證據**：依OpenRouter官方Chat/Structured Outputs/Models/Endpoints/Routing/Metadata/Errors/Usage/Plugins/Privacy固定direct HTTP、exact model ID+permanent canonical、exact endpoint、fallback/plugins/cache off、single-call與完整Capture；2026-07-18以Claude Sonnet 5 + Anthropic endpoint通過真probe，focused 148、full API/PostgreSQL 762 passed（0 skipped），並記錄真metadata揭露的dual model identity修正。下一步為V3-5 12-case multi-trial品質gate。
- [`plans/2026-07-18-interview-vnext-v3-5-turn-eval-harness-plan.md`](plans/2026-07-18-interview-vnext-v3-5-turn-eval-harness-plan.md) — **E0–E8 executable 已落地、true live 已嘗試但不具品質裁決資格的V3-5詳細規格**：harness與887 passed/0 skipped保留；batch `5bad4e3f-...`因provider route contamination停線，並揭露model-generated proposal identity、unsupported qualifier與offline grader drift三個不同架構缺口。V3-6保持blocked，下一步以2026-07-18 runtime架構審查為準。
- [`plans/2026-07-18-interview-vnext-v3-5a-runtime-contract-reconstruction-plan.md`](plans/2026-07-18-interview-vnext-v3-5a-runtime-contract-reconstruction-plan.md) — **已核准、執行中的V3-5A計畫；R1–R4完成、下一步R5**：R0–R9逐commit，固定binding/projection/execution evidence/conformance契約、checkpoint/taxonomy v2、OpenRouter/OpenAI/scripted adapters、ID-less Turn C1 v2、qualifier support、12-case suite v2、deterministic regrade、real PG/full API與分段true-live gate；不新增0011、不做production route/direct provider。
- [`plans/2026-07-19-interview-vnext-v3-5a-r3-corrective-plan.md`](plans/2026-07-19-interview-vnext-v3-5a-r3-corrective-plan.md) — **已完成的R3 runtime integrity修正與最終證據**：exact adapter/config/projection binding、typed result/evidence/conformance durable gate、所有terminal fresh-process recovery重驗、Capture events與multi-attempt manifest closure；corrective commits `e1716c8`/`2cf3404`/`1eaa774`，real PostgreSQL vNext 653/0 skipped、完整no-network 844/0 fail。R4實作已解鎖，paid live/V3-6仍blocked。
- [`plans/2026-07-19-interview-vnext-v3-5a-r4-provider-evidence-conformance-plan.md`](plans/2026-07-19-interview-vnext-v3-5a-r4-provider-evidence-conformance-plan.md) — **已完成的R4 provider wire/evidence/conformance分離與最終證據（§19）**：adapter只normalize wire facts（pure `openrouter_routing`、official nested/legacy endpoints、pipeline/cache分類、endpoint attestation），eligibility由application `attribution-strict/1.0.0`判定，probe/Capture保存result/evidence/conformance closure，scheduler以`provider.conformance_failed`停線；commits `aee798a`/`a814789`/`067504b`＋R4-C corrective（null pipeline／attempts矛盾／blank-string三個blocker，§19.1），no-network 941/197/0、interview_vnext+real PG 750/0 skipped。R5解鎖，paid live/production仍blocked。
- [`plans/2026-07-17-interview-vnext-v3-4-openai-responses-adapter-plan.md`](plans/2026-07-17-interview-vnext-v3-4-openai-responses-adapter-plan.md) — **已完成的direct OpenAI reference規格**：adapter/mock/live-bundle suite 66 passed、完整API/PostgreSQL 614 passed；官方OpenAI live尚未執行且依ADR 0035降為optional GPT direct comparison，不再阻擋主線。
- [`specs/2026-07-15-evidence-first-stateful-workflow-reconstruction-research.md`](specs/2026-07-15-evidence-first-stateful-workflow-reconstruction-research.md) — **上游研究紀錄／舊漸進路線已被取代**：保留 2025–2026 一手來源、Anthropic Interviewer、職務分析、Evidence/Agenda、eval 與 database audit 證據；不得再依其 C0→C1 指示改 v3 runtime。
- [`specs/2026-07-15-c0-c1-interview-eval-experiment-plan.md`](specs/2026-07-15-c0-c1-interview-eval-experiment-plan.md) — **eval 方法保留／C1 實作路線被取代**：balanced cases、claim gold、fixed/branching eval、多 trial、hard gate 與 v3 black-box baseline 仍有效；不再授權在 v3 內實作 C1 或補深度 provider trace。
- [`design/`](design/) — **子系統端到端設計(agent-facing)**;現有 [`editor-knowledge-pack.md`](design/editor-knowledge-pack.md)(編輯器 × 知識包)、[`interview-engine.md`](design/interview-engine.md)(訪談引擎)。寫法見 [`design/README.md`](design/README.md)。
- [`adr/`](adr/) — Architecture Decision Records(決策的「為什麼」+ 取捨;**0001–0036**)；訪談AI核心架構為[ADR 0034](adr/0034-interview-ai-vnext-greenfield-evidence-workflow.md)，provider主線為[ADR 0035](adr/0035-interview-vnext-openrouter-first-provider-boundary.md)，最新runtime contract決策為[ADR 0036](adr/0036-interview-vnext-provider-binding-conformance-and-idless-turn-v2.md)。
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
