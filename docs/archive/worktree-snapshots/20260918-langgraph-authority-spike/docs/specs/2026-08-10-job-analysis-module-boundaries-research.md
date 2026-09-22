# Job Analysis 完成後的模組邊界研究

- 日期：2026-08-10
- 狀態：Research complete；實作前仍需 owner 核准設計
- 範圍：現行 `apps/api`／`apps/web` 的 move-only 架構整理

## 1. 問題

`app/job_analysis` 原本是為了隔離舊 `interview`／`interview_vnext` 而建立的 greenfield 工作面。現在 current-only hard cut 已完成，它已是唯一 production 系統；繼續把所有程式包在 `job_analysis` 名稱下，會把「開發隔離」與「正式模組邊界」混在一起。

本研究要回答：完成隔離後，應按技術層、功能能力，或 bounded context 重新分割；以及如何在不改 API、資料庫與行為的前提下落地。

## 2. 既有 repo 裁決

- [ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md) 把新顧問引擎定為 greenfield，禁止把舊 runtime 當作前提；它沒有要求 `job_analysis` 永久成為隔離沙盒。
- [ADR 0057](../adr/0057-current-only-runtime-and-data-boundary.md) 已把 `job_analysis` 提升為唯一現行 runtime；舊 runtime、contract、migration 與 app 已移除。
- [ADR 0008](../adr/0008-api-hexagonal-layering.md) 已確立依賴向內：pure core／ports → application → adapters／delivery，並以 composition root 接線。
- [`docs/contract-strategy.md`](../contract-strategy.md) 規定跨語言 contract 才放 `packages/`；domain／application 不直接依賴 transport DTO。
- [`docs/design/task-analysis-engine.md`](../design/task-analysis-engine.md) 確立 `JobAnalysisState`、Current State、Journal、generation/read-set 與 authority commit 是共同真相；Task 與 OPKS 不能各自建立第二份 document store 或 generic proposal framework。

## 3. 權威資料的收斂

### 3.1 Clean／Hexagonal 的規則

Robert C. Martin 的 Clean Architecture 將核心政策放在內層，要求 source dependency 只向內；跨邊界傳遞簡單的內部資料，不把 database row 或 framework DTO 帶進核心。

來源：[The Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)

這回答「依賴怎麼走」，但沒有回答整個 application 要按哪些業務模組切；因此只用它決定每個模組內的依賴方向。

### 3.2 Modular monolith 應按功能模組切

Spring Modulith 將 application module 定義為一個功能單位，包含：對外 API、不可被其他模組直接存取的內部實作，以及明確的 required interface。它預設用 application root 下的 direct sub-package 表示模組，並支援巢狀模組與 named interface。

來源：[Spring Modulith Fundamentals](https://docs.spring.io/spring-modulith/reference/fundamentals.html)

Spring Modulith 的驗證規則要求模組依賴無 cycle、跨模組只能走 API package，並可宣告 allowed dependencies。

來源：[Spring Modulith Verification](https://docs.spring.io/spring-modulith/reference/verification.html)

這支持「功能模組作外框、每個模組內再守 Clean／Hexagonal」，而不是全 application 只切成一層 `domain`、一層 `application`、一層 `adapters`。

### 3.3 大型 monolith 的實務：先依真實內聚切，再以工具封邊

Shopify 將大型 Rails monolith 按業務能力整理成 components，並用 Packwerk 檢查 declared dependency 與 private implementation；其重點不是把程式分散部署，而是在同一 codebase 建立 public entrypoint、低耦合與可執行邊界。Shopify 的後續回顧也提醒：若只依理想化 domain 名稱先畫邊界，卻不符合程式實際如何一起變更與呼叫，會產生大量不自然的例外與待辦。

來源：[Shopify — Enforcing Modularity with Packwerk](https://shopify.engineering/enforcing-modularity-rails-apps-packwerk)、[A Packwerk Retrospective](https://shopify.engineering/a-packwerk-retrospective)

因此本案不把目錄名稱直接宣稱為可獨立部署的 bounded context，而是依現有 use case、共同 Current State／transaction 與實際依賴切功能模組，再用 public API 與 AST checks 把邊界變成事實。

GitLab 2026 的 modular monolith 設計同樣採「廣泛模組化、ROI 明確才抽服務」，要求 transport 成為 adapter、domain 只透過 public API 存取，並以 one-way dependency／hexagonal architecture 隔離內層；它也明確指出資料表、外鍵與 ORM 關聯才是實際 extraction 的主要耦合。

來源：[GitLab — Rails Monolith Decomposition](https://handbook.gitlab.com/handbook/engineering/architecture/design-documents/modular_monolith/)

這支持 Caliburn 保留一個 authority kernel 與單一 transaction，不為目錄對稱假造 Task／OPKS 的獨立資料所有權。

### 3.4 FastAPI 的 delivery layer 應薄且按功能拆 route

FastAPI 官方的 Bigger Applications 範例把 users、items、admin 分成 router modules，再由 `main.py` 組裝；router 仍屬同一個 application，不代表要拆成多個服務。

來源：[FastAPI — Bigger Applications](https://fastapi.tiangolo.com/tutorial/bigger-applications/)

因此本 repo 應拆 API route／mapper 的功能責任，但保留單一 FastAPI process 與既有 public prefix。

### 3.5 Next.js 允許按 feature／route 組織，但不替產品決定邊界

Next.js 官方列出的合法組織策略包含：將 routing 留在 `app`、把程式放在 `src` 的 top-level folders，或按 feature／route colocate；route groups 與 private folders 可在不改 URL 的情況下表達組織邊界。官方同時明說框架不替團隊規定唯一目錄法。

來源：[Next.js — Project Structure and Organization](https://nextjs.org/docs/app/getting-started/project-structure)

因此 Web 採 feature-first，但不機械複製 backend package：只有具備實際 UI responsibility 的能力才建 feature，`app` 保持 composition，真正跨 feature 的 transport／UI primitive 才進 `shared`。

### 3.6 邊界要能被機械驗證

Import Linter 提供的架構契約類型正好對應本次需求：`layers`、`forbidden`、`independence`、`acyclic siblings`。它也說明 layers 可套在同一 package 的子模組或多個 root package 上。

來源：[Import Linter](https://import-linter.readthedocs.io/en/latest/index.html)、[Contract types](https://import-linter.readthedocs.io/en/v2.3/contract_types.html)

本 repo 已有 AST dependency tests；第一階段可用既有測試實作相同規則，不為簡單 move-only 重構先引入新的架構框架。

## 4. 現況診斷

現行 `app/job_analysis` 不是只有一個問題：

- `application/__init__.py` 聚合幾乎所有 use case、domain state、persistence ports、Task／OPKS operation 與 verifier，形成過大的 public facade。
- `transition.py` 約 1000 行、`verifier.py` 約 940 行、`authoring.py`／`proposal_decisions.py`／`context.py` 各約 670–690 行；技術層名稱掩蓋了功能責任。
- `app/api/routes/job_analysis.py` 約 650 行，`job_analysis_mapper.py` 約 410 行；HTTP delivery、文件、顧問、OPKS 與 export 還在同一 route seam。
- PostgreSQL adapter 與 API mapper 直接 import `app.job_analysis.application` 的大 facade；小幅變更容易觸發整個 application import surface。
- `application/operation.py`、`opks_operation.py`、`consultation.py` 與 `opks_generation.py` 直接依賴具體 `OpenRouterAdapter`；provider outcome／port 被放在外層 adapter package，形成 application → provider 的反向邊。
- `application/export_xlsx.py` 直接 import OpenPyXL；純 export assembly 與 framework renderer 沒有保持內外層分離。
- Web 的 workspace component／helper 仍按技術形狀平鋪，且原研究目標樹只畫 API，與本文件宣告的 API／Web scope 不一致。
- Task、OPKS、文件編輯雖可按功能分，但都必須經同一份 Current State 與 authority commit；它們不是三個可獨立持有資料真相的 bounded context。

## 5. 方案比較

### A. 保留全域技術分層，只拆大型檔案

```text
app/core/
app/application/
app/llm/
app/adapters/
app/api/
```

優點是最接近 ADR 0008、搬動風險最低；缺點是 `application` 仍會把 documents、consultation、Task、OPKS、export 混在一起，功能模組的 public／internal 邊界仍不明。

### B. 每個功能做完全獨立 vertical slice

```text
app/documents/{domain,application,ports}
app/consultation/{domain,application,llm}
app/opks/{domain,application,llm}
app/export/{application}
```

優點是功能內聚與可替換性最好；缺點是若把 Current State、Journal、authority transaction 也複製進各 slice，會製造第二份真相、雙寫或 cycle。以目前資料模型不能直接採用純隔離版本。

### C. 功能模組 + shared kernel + 外層 adapters（建議）

功能能力是 package 外框；共用的 Current State、authority seam、識別碼、持久化 ports 與不可避免的跨功能 domain types 放在小而明確的 shared kernel。每個功能模組只暴露 application API，內部 prompt、verifier、mapper 不給其他模組直接 import。

這保留 modular monolith 的單一 process／單一 transaction，又消除 `job_analysis` 作為歷史隔離容器的角色，且可由 AST／Import Linter 類型規則驗證。

## 6. 建議目標邊界

第一階段只定義邊界，不立即決定每個檔案的最終命名：

```text
apps/api/app/
  core/                    # shared kernel：state、ids、authority 與真正共用的 domain
  documents/               # 文件生命週期、header、readiness、員工直接編輯
  task_analysis/            # context、wire、operation、verifier、transition、Task proposal
  opks/                    # OPKS child operation、scheduler、authoring、proposal
  consultation/            # employee turn orchestration；只走上述模組的 public API
  export/                  # deterministic assembly
  adapters/
    postgres/              # SQLAlchemy／serialization／repositories
    openrouter/            # provider transport 與 execution evidence
    xlsx/                  # OpenPyXL renderer
  api/
    routes/                # 按 documents／consultation／opks／export 拆薄 route
    mappers/               # transport ↔ internal DTO

apps/web/src/
  features/
    documents/
    consultation/
    opks/
    export/
  shared/                  # HTTP transport、query client、通用 UI；不放 domain policy
  app/                     # Next.js pages，只負責 composition
```

`core` 不是新的業務大雜燴。型別或 port 只有同時符合下列條件才可進 core：至少兩個功能模組真的消費、代表穩定的共同業務語言或 authority seam、且不依賴 IO／framework／transport。其餘一律由使用它的功能模組擁有；不能因為它是 Pydantic model、Protocol 或「可能共用」就搬進 core。

新增第一層功能模組也不是純命名決定；它必須有可一句話說明的主要責任、可列舉的 public use cases、能隱藏的 internal implementation，且放入依賴圖後不造成 cycle。若仍共享同一 aggregate／transaction，目錄分開不等於另建資料所有權或 bounded context。

`JobAnalysisState`／authority transaction 是共同 aggregate seam，因此留在 core；Task Analysis／OPKS 的 model-call port 由各功能模組的 application 端定義，OpenRouter adapter 只實作 port，不能讓 application 型別依賴 `OpenRouterAdapter`。純 `ExportDocument` assembly 留在 export，OpenPyXL renderer 移到外層 xlsx adapter。

依賴規則：

```text
api composition → feature public APIs → core
consultation → task_analysis public API + opks public API + core
documents／task_analysis／opks／export → own internals + core only
adapters → owning feature ports + core boundary types
feature A -/> feature B internals
core -/> api／adapters／FastAPI／SQLAlchemy／provider
```

功能模組之間若未來真的需要協作，只能新增明確的 public application API／typed internal contract；不以共用 `__init__.py` 或 wildcard export 偷開後門。

Python 的 `__init__.py` 只提供可讀的 public facade，本身不構成 access control。外部模組不得 import `internal`／底層實作檔，並由 AST architecture tests 強制 no-cycle、API-only access 與 allowed dependency graph。

## 7. 不變量與非目標

- 不改 `/api/v1/job-analysis`、`job-analysis-contract`、`job_analysis_*` table name、Current State 語意或 authority transaction。
- 不拆成微服務、不新增 package、不恢復 legacy／vNext／OCS。
- 不把 Task 與 OPKS 偽造為互不相干的 bounded context；它們仍在同一本地文件與同一 authority kernel 內。
- 不為了追求對稱，把簡單 CRUD 套上不必要的 port／adapter；只在外部 IO、交易、模型 provider 與跨模組 seam 保留 port。
- 每次搬移先跑既有測試，再跑 import boundary checks；每個 task 一個 commit，維持 green-before == green-after。

## 8. 研究結論

`app/job_analysis` 應從「greenfield 隔離容器」提升為「現行 API 內的功能模組集合」。最適切的分法不是把所有程式直接攤平成單一 `core/application`，也不是把 Task／OPKS 拆成互不共享資料的服務，而是：

1. 以 documents、task_analysis、opks、consultation、export 作功能模組外框。
2. 以小型 shared kernel 保留 Current State／authority／ports。
3. 每個模組內仍遵守 Clean／Hexagonal 依賴向內。
4. 用明確 public API、禁止跨模組 internal import、無 cycle 與既有 AST tests 固化規範。

這是研究結論，不是尚未經 owner 核准的施工 plan。
