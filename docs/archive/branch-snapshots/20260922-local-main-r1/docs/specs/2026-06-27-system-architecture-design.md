# Caliburn 系統架構設計（大框架）

> **產品名**：**Caliburn**（Excalibur 的古名 Caliburnus；寓意「卓越 + caliber／能力基準」）。新 monorepo 即以此命名；舊三 repo 併入後封存。

> **狀態**：設計定稿待審。經 2026-06-27 廣度+深度研究（大公司／熱門專案／權威資料）後拍板。落成後依此寫各階段實作 plan。
> **語言**：工作語言中文。
> **權威出處**：見文末「References」。

## 目標

把現有三個獨立 repo（`jobintel-ai`、`jd-ocs-indexer`、`jd-pdf-to-json`）整理成一套**主流、最新、權威**的架構，作為產品 **Caliburn**（給顧問用的多租戶 B2B SaaS）的長期地基，並讓未來擴充（登入、匯出、新知識源、新 agent 能力）好加。

## 產品定性（驅動架構）

多租戶 **B2B SaaS**：顧問是操作者、可跨多家客戶公司（Organizations 模型）；客戶公司＝租戶，公司員工寫職務說明書；**公司間資料隔離**。後端全由我方託管，客戶用瀏覽器連網址（SaaS 交付）。部署偏好：**先自架**（基礎設施可自架，auth 真要做時用 Keycloak 等成熟 IdP，別手刻；生產 Postgres 有真實客戶資料後再評估託管）。

---

## 一、核心架構決定

### 1.1 主流架構＝Hexagonal/Clean + DDD + Modular Monolith

2026 權威共識：**Hexagonal、Clean、Onion 是同一個概念的不同名字**——領域邏輯置中、與外界（DB/HTTP/佇列）隔離，外界透過 ports（介面）+ adapters（實作）連入，**依賴一律往內指**。趨勢不是選哪一個，而是把「依賴反轉 + 領域隔離」這套統一原則套到團隊規模上。1–5 人 → **Modular Monolith + Hexagonal/DDD**（正中單人）。[R1][R2][R3]

**右尺寸原則**：hexagonal 嚴謹只用在「複雜邏輯／多整合」的接縫，單純 CRUD 不套（避免過度設計）。[R4]

### 1.2 拓撲＝polyglot monorepo（非 polyrepo、非微服務）

- **monorepo**：一份 repo、`apps/` + `packages/`。原子化跨切變更（一個 PR 同時改契約+生產者+消費者），Turborepo 的 affected-only 讓笨重服務只在自己變動時重建。熱門專案實證：LangChain.js = pnpm+Turborepo；Next+FastAPI 範本 = Turborepo。[R5][R6]
- **不走微服務（在各服務內部）**：在團隊規模門檻之下，微服務只增協調與營運成本而無回報——Fowler「先單體（MonolithFirst）」、微服務有其前提門檻；Sam Newman《Building Microservices》同調。[R7]
- **合併三 repo 要保留各自 git 歷史 + 文件**（`git subtree`）。

### 1.3 三個 bounded context：維持、不更細、不合併

語言在三處切換（**解析 / 檢索 / 著作**），對齊 DDD bounded context。各 app = 模組化單體。[R9]

| context | 角色 | 多租戶？ |
|---|---|---|
| pdf-to-json | PDF→OCS JSON 的 ETL（離線批次） | 否（全域，處理官方 PDF） |
| ocs-indexer | Qdrant+BGE-M3 知識/查詢服務 | 否（全域，官方目錄人人同一份） |
| jobintel-ai（api+web） | 著作 app + agent | **是（租戶隔離在此）** |

**indexer 維持獨立服務、不併進 api**：決定性理由＝ML runtime（BGE-M3 重、冷啟慢、需獨立擴展）+ 全域 vs 多租戶角色不同。符合「合法該拆服務」的判準。[R10]

### 1.4 契約優先（packages/ocs-contract）＝最高價值跨切

OCS 契約現為 prose（README）+ 在三處各自重編（transformer/normalizer/exporter）→ 飄移 bug（D29 `job_categories` 多值掉值）。改為**契約優先單一事實來源**：

- `schema/*.schema.json`（JSON-Schema）= 權威來源。
- `datamodel-code-generator` 生 Pydantic v2、`json-schema-to-typescript` 生 TS。[R11]
- **每 PR schema-diff**（provider-owned 契約 + 差異檢查）。[R12]
- 效果：`ocs_transformer.py`（pdf-to-json）與 `normalizer.py`（indexer）是契約兩端，共用型別後**同時縮小 + 對齊**。

### 1.5 Agent：LangGraph 留用 + 12-factor + MCP-ready

- LangGraph 1.0 是一線框架，**不換** ADK / MS Agent Framework（它們靠 MCP/A2A 互通）。[R13]
- 套 [12-Factor Agents]：自掌控制流（#8）、無狀態 reducer（#12）、小而專注 agent（#10）、prompt 版本化（#2）。[R14]
- **indexer↔api 縫**：契約型別 HTTP client 現做；**MCP-ready 留鉤子**——MCP 是 2026 連 AI 與服務的事實標準（Linux Foundation，OpenAI/Google/MS/AWS 採用），但價值來自「多 client 共用」。單一內部 agent ↔ 單一內部服務時，型別 client 更簡單；第二個消費者出現再把 indexer 包成 MCP server（MCP 是包在既有 API 外的協定層，屆時是加法）。[R15]
- 可觀測：對齊 OTel GenAI 語意慣例 + Langfuse（接既有 OTel）。[R16]

### 1.6 多租戶：Pool + Postgres RLS 起步

- **Pool**（共用 DB + `tenant_id` + Postgres RLS）起步，最便宜可擴展；保留升級 **silo**（DB-per-tenant）給未來高價值/合規客戶（動態多租戶）。[R17]
- **紀律：`tenant_id` 從第一天就埋進 schema**，即使登入晚做。
- **Organizations 模型**：顧問可跨多 org；每請求 scope 到一個 tenant。
- 認證：OAuth2/OIDC/JWT；B2B 需 Organizations 一等支援的 IdP（WorkOS/Clerk），別用 Auth0 硬湊。登入 = `apps/api` 的 `auth/` 模組 + `apps/web` 當 OAuth client；知識服務不碰。[R18]

### 1.7 資料主權（Database-per-Service）

每個資料庫歸它的服務私有：**Postgres 屬 api、Qdrant 屬 indexer**；別的服務只透過該服務的 API 取資料，**不直接碰它的倉庫**。資料庫不是服務、不是專案，是基礎設施。避免 Shared Database 反模式。[R19]

---

## 二、具體結構

### 2.1 Monorepo 根

```
caliburn/
├── package.json              # pnpm workspaces + turbo
├── pnpm-workspace.yaml
├── turbo.json                # tasks: dev / build / test / lint / codegen（affected-only）
├── pyproject.toml            # [tool.uv.workspace] members = apps/*, packages/ocs-contract/python
├── uv.lock                   # 一份共用 Python lockfile
├── apps/
│   ├── pdf-to-json/          # Python·uv — Pipes-and-Filters ETL
│   ├── ocs-indexer/          # Python·uv — RAG 知識服務
│   ├── api/                  # Python·uv — FastAPI + LangGraph
│   └── web/                  # Next.js 16
├── packages/
│   └── ocs-contract/         # schema/ + python/ + typescript/
└── docs/{specs,plans}
```
每個 Python app 放一個薄 `package.json`（name + scripts→`uv run`），Turborepo 靠它編排任務。

### 2.2 apps/api（jobintel-ai）— 右尺寸混血 hexagonal

```
apps/api/src/caliburn_api/
├── core/            # 內核（inward）：domain entities + ports(Protocol) + 純邏輯
│   ├── ports.py     #   LlmPort / PersistPort / KnowledgePort（從 graph_v3 移出）
│   ├── models.py    #   領域型別
│   └── ocs_doc.py   #   純文件規則
├── agent/           # LangGraph 子系統（原 graph_v3）：graph/nodes/state/deep/curate/prompts
├── documents/       # domain 模組：router · service(ocs_doc) · repo(DocRepo) · schemas
├── profiles/        # domain 模組：router · service · repo(ProfileRepo) · models
├── ai/              # AI 能力（純函式 draft_op/recommend_ks…）→ 依賴 core.ports
├── knowledge/       # KnowledgePort 的 adapter（indexer client）
├── infra/           # adapters：DbPersist · HttpIndexerClient · OpenRouterLlm；db session；RLS
├── auth/            # （未來）驗 JWT + 解 TenantContext
└── api/             # 薄路由 + deps.py（DI 把 infra adapter 接到 core ports；auth/tenant 相依）
+ alembic/  evals/
```
**依賴規則**：`api → (documents/profiles/agent/ai) → core`；`infra` 實作 `core` 的 ports；`core` 不 import 任何外層。解開現況 `graph_v3 ↔ services` 雙向纏繞。

### 2.3 apps/ocs-indexer（維持，微調）

```
src/jd_ocs_indexer/
├── models/        # 領域 entities（chunk, ocs）
├── ingestion/     # reader → normalizer → builder → payloads（離線管線）
├── embeddings/    # base.py(port) + bge_m3.py(adapter)  ← 加 embedding 模型版本標記
├── store/         # Qdrant adapter（writer, client, schema, ids）
├── api/           # 線上查詢（app, routes, service, schemas）薄
├── validation/    # eval（search, smoke, stats）
├── config.py
└── cli.py         # 瘦身：委派給 ingestion 模組
```

### 2.4 apps/pdf-to-json（維持管線，拆 god-file）

```
src/jd_pdf_to_json/
├── core/          # models + config
├── parsers/       # base(port) + pdf_parser(adapter)
├── transformers/  # base(port) + 區段 mapper 鏈（取代 1492 行 god-file）
│   ├── header_mapper.py  profile_mapper.py  units_tasks_mapper.py
│   ├── ks_mapper.py  attitude_mapper.py  notes_mapper.py
│   └── ocs_transformer.py   # 薄：編排上述 filter 鏈
├── validators/    # schema + business_rules
├── writers/       # base(port) + json_writer(adapter)
├── utils/  cli.py
```
依 Pipes-and-Filters：每個 mapper 單一職責、可單測、可單獨修。[R20]

### 2.5 packages/ocs-contract

```
packages/ocs-contract/
├── schema/*.schema.json     # 權威來源（JSON-Schema）
├── python/                  # 生成 Pydantic v2 + pyproject（uv workspace member）
├── typescript/              # 生成 TS + package.json
└── codegen（turbo task；build 前置；PR schema-diff）
```

---

## 三、House-style 共同慣例（統一外框、各自內容）

三專案**架構原則一致、目錄外框一致、領域內容各自 idiomatic**：

- **core（inward）**：domain models + ports + 純邏輯；不 import 外層。
- **adapters/infra（outward）**：實作 ports；所有外部 I/O（DB/HTTP/檔案/模型）。
- **入口薄**：`api/`（服務）或 `cli.py`（批次）只管 I/O。
- **跨切 port** 放 `core`；**單一能力 port** 跟其 adapter 共置（沿用 indexer `embeddings/base.py` 慣例）。
- **領域中間層**各自 idiomatic：管線（stage）/ app（domain 模組）/ 知識服務（ingestion+store）。
- **打包**：`src/` + `uv` + `pyproject.toml` 三專案統一。
- **依賴方向**：一律往內，enforce（domain 不 import adapters、application 不 import api）。[R2]

→ 現況：pdf-to-json 與 indexer 已大致同此慣例；**jobintel-ai 是唯一異類**（layer-based、port 散在 graph_v3、路由借兄弟路由），套上此慣例即對齊。

---

## 四、各專案內部優化（審查結論）

| 專案 | 健康 | 主刀 |
|---|---|---|
| **jobintel-ai** | 🟡 骨架好（已有 ports/adapters/repo/DI/乾淨 graph）但依賴方向纏繞 | 抽 `core/` 放 ports、解 `graph_v3↔services` 纏繞、layer→domain、`requirements→uv` |
| **ocs-indexer** | 🟢 對齊 RAG ingestion 管線（教科書） | 加 embedding 版本標記、瘦 CLI（小） |
| **pdf-to-json** | 🟡 管線骨架好但 `ocs_transformer.py` 1492 行 god-file | 拆成區段 mapper filter 鏈 |
| **跨專案** | — | 抽 `ocs-contract` → transformer+normalizer 同時縮小對齊 |

三專案皆**不需重寫**，各只有一個主刀 + 一個共同契約抽出。

---

## 五、分階段執行（每階段結束＝測試全綠、可驗收可暫停）

- **Phase 0 — House-style 慣例**：本文件第三節即規則書，指導後續重構。
- **Phase 1 — Monorepo 併合〔純機械、不改邏輯〕**：`git subtree` 併三 repo（保留歷史）+ Turborepo + uv workspace；三專案「原樣」`turbo test` 全綠。**機械搬移與改邏輯絕不混在同一步。**
- **Phase 2 — 抽 packages/ocs-contract**：JSON-Schema → codegen（Pydantic+TS）→ 接入 transformer/normalizer/api → PR schema-diff CI。
- **Phase 3 — 各專案內部優化（monorepo 內、照 house-style，三者獨立可任意序）**：
  - 3a jobintel-ai：抽 core/ports + 解纏繞 + layer→domain + uv。
  - 3b pdf-to-json：拆 1492 行 transformer 成 mapper 鏈。
  - 3c ocs-indexer：embedding 版本標記 + 瘦 CLI。

順序理由：規則書先行 → 都進同一個家（機械安全）→ 修共用接縫（契約，在 monorepo 抽最自然、不白工）→ 修各房間內裝（吃契約型別一次到位）。

---

## References（權威出處）

> 原則：只引**原始出處 / 公認權威 / 官方文件 / 大公司工程**，不引無名部落格。

- [R1] **Hexagonal/Clean/Onion 為同一概念**——Alistair Cockburn, *Hexagonal Architecture (Ports & Adapters)*（原作者）；Robert C. Martin, *The Clean Architecture*（cleancoder, 原作者）；Jeffrey Palermo, *The Onion Architecture*（原作者）。
- [R2] **Dependency Rule**——Robert C. Martin, *Clean Architecture*（Prentice Hall 書 + cleancoder blog）。
- [R3] **先單體 / Modular Monolith**——Martin Fowler, *MonolithFirst*（martinfowler.com）；Sam Newman, *Monolith to Microservices*（O'Reilly）。
- [R4] **選擇性套用 hexagonal（只在複雜接縫）**——Alistair Cockburn, *Hexagonal Architecture*。
- [R5] **monorepo（熱門專案/官方）**——LangChain 官方文件（monorepo structure）；Vercel, *Turborepo* 官方文件。
- [R6] **uv workspaces**——Astral 官方文件（docs.astral.sh）；**Turborepo+Python**——Vercel Turborepo 官方文件。
- [R7] **微服務的前提與代價**——Martin Fowler, *MicroservicePremium* / *Microservice Prerequisites*（martinfowler.com）；Sam Newman, *Building Microservices*（O'Reilly, 2nd ed）。
- [R8] **monorepo at scale**——R. Potvin & J. Levenberg, *Why Google Stores Billions of Lines of Code in a Single Repository*, Communications of the ACM (2016)。
- [R9] **Bounded Context**——Eric Evans, *Domain-Driven Design*（Addison-Wesley, 2003）；Martin Fowler, *BoundedContext*（martinfowler.com/bliki）。
- [R10] **服務分解判準**——Sam Newman, *Building Microservices*（O'Reilly）。
- [R11] **schema→程式碼 codegen**——Pydantic 官方文件（datamodel-code-generator）；JSON Schema（json-schema.org, 官方標準）。
- [R12] **契約優先 / API-first**——OpenAPI Specification（openapis.org, OpenAPI Initiative / Linux Foundation）。
- [R13] **Agent 框架**——LangChain/LangGraph 官方文件；Google, *Agent Development Kit (ADK)* 官方；Microsoft, *Agent Framework*（Microsoft Learn 官方）。
- [R14] **12-Factor Agents**——HumanLayer（廣被引用的 manifesto）；源頭 *The Twelve-Factor App*——Adam Wiggins / Heroku（12factor.net）。
- [R15] **Model Context Protocol**——Anthropic 官方公告 + 規範；Linux Foundation / Agentic AI Foundation（治理）。
- [R16] **GenAI 可觀測**——OpenTelemetry GenAI Semantic Conventions（OpenTelemetry / CNCF 官方）；Langfuse 官方文件。
- [R17] **多租戶隔離 silo/pool/bridge**——AWS Well-Architected *SaaS Lens*（AWS 官方）；Microsoft Azure Architecture Center, *Multitenancy*（官方）。
- [R18] **B2B 認證標準**——OAuth 2.0（IETF RFC 6749）+ OpenID Connect（OpenID Foundation, 官方規範）。
- [R19] **Database-per-Service / Shared DB 反模式**——Chris Richardson, microservices.io + *Microservices Patterns*（Manning）。
- [R20] **Pipes-and-Filters**——Gregor Hohpe & Bobby Woolf, *Enterprise Integration Patterns*（Addison-Wesley）；Microsoft Azure Architecture Center（官方）。
