# Caliburn 架構

> 現行產品是 `apps/api`、`apps/web` 與 `packages/job-analysis-contract`。repo 另保留 ADR 0057 的 RAG bounded context，但尚未接入 current API／Web；兩者必須保持 runtime、contract 與啟動邊界隔離。

## 鳥瞰

Caliburn 是給員工使用的本機 Web AI 職務分析與職務說明書顧問。單一本機操作者可保存多份彼此隔離的文件，不提供登入、多租戶、權限、計費、雲端或多人協作。

```text
Next.js workspace ──HTTP／SSE──▶ FastAPI consultant API
                                      │
                                      ├── consultant_documents 最小 catalog
                                      ├── LangGraph PostgreSQL Saver
                                      │     └── approved JD／訪談語意／interrupt／receipts
                                      ├── LangGraph PostgreSQL Store
                                      │     ├── employee sources／correction lineage
                                      │     ├── StoreBackend /workspace
                                      │     └── manifest／decision memory／rebase plan
                                      ├── derived semantic /review
                                      ├── bounded single consultant ──▶ OpenRouter
                                      └── approved-only projection ──▶ XLSX
```

PostgreSQL 是唯一預設基礎服務。API／Web 在 host 執行；OpenRouter model call 在資料庫 transaction 外執行。Qdrant、embedder 與 indexer 不在 current 啟動路徑。

每份 JD 只有一個持久、非權威的 active workspace。模型透過六個低階 VFS Tools 修改 Store 中的 canonical resources；application 自動驗證實際 after-state，並從 approved ↔ workspace 即時產生語意審核。只有員工 authority command 可修改 Saver 中的 approved JD，export 也只讀 approved。

## Monorepo 成員

| 路徑 | 職責 | 埠位 |
|---|---|---|
| [`apps/api/`](apps/api/README.md) | FastAPI、LangChain／LangGraph 顧問、OpenRouter、PostgreSQL、XLSX | `8001` |
| [`apps/web/`](apps/web/README.md) | Next.js 員工顧問工作區 | `3000` |
| [`packages/job-analysis-contract/`](packages/job-analysis-contract/) | durable consultant JSON Schema 生成的 Python／TypeScript 契約 | — |

## API 邊界

ADR 0060、0066 與 0067 的 production 依賴方向如下：

- `app/consultant/`：職務分析政策、Task／Duty／O／P／K／S Skills、typed model result、adaptive interview、required clarification、canonical workspace codec、`StoreBackend` path policy、automatic validation、semantic differ、employee authority 與 purpose-first projection。它不 import FastAPI、OpenRouter adapter、XLSX 或 RAG。
- `app/adapters/langgraph/`：以 `AsyncPostgresSaver` 與 `AsyncPostgresStore` 組成 application-scoped runtime，承接 catalog、source-first admission、checkpoint command、Store workspace 注入與 crash reconciliation。
- `app/adapters/openrouter/`：把 versioned model profile／run policy 綁到 LangChain `ChatOpenRouter`；不擁有產品狀態、workspace 或職務分析方法。
- `app/export/`：只把核准職務說明書組成 deterministic export model；未接受的 workspace 差異不可進入。
- `app/adapters/xlsx/`：唯一使用 OpenPyXL 的 renderer；官方 iCAP code cells 固定留白。
- `app/api/`：唯一 HTTP composition root、purpose-first mapper、RFC 9457 problem response 與 `/api/v1/job-analysis/consultant-documents` routes。
- `app/database.py`：只供 app lifespan／health check 使用的 SQLAlchemy connection；不是 document 或 workspace store。

已刪除的舊 production modules、routes、DTO 與 writers 不得重新接回 composition root。`apps/api/tests/test_consultant_hard_cut.py` 與 `test_consultant_foundation_boundaries.py` 保留 hard-cut 及 framework／RAG 依賴邊界。

## Durable authority 與 persistent workspace

- Alembic fresh root `0018_consultant_runtime_root` 只建立 `consultant_documents` 與 `alembic_version`。`npm run consultant-storage:setup` 再由 LangGraph 官方 `.setup()` 建立 Saver／Store tables；Caliburn 不鏡像 framework state，也不建立 application-owned workspace table。
- Saver checkpoint 是核准職務說明書、可修訂理解、訪談工作、Gap、必要澄清、run／command receipt 與 source reference 的 owner。Store 是員工逐字來源／更正 lineage、workspace files、薄 manifest、decision memory 與可恢復 rebase plan 的 owner。Saver 不保存 workspace files；Store 不保存第二份 approved JD。
- Deep Agents `CompositeBackend` 對模型呈現五個 namespace：唯讀 `/skills`、`/sources`、`/approved`、`/review`，以及唯一可寫的 `/workspace`。其中 `/workspace` 由 document-scoped `StoreBackend` 持久化；`/review` 是 derived semantic projection，不是另一份 JD 或 durable review copy。
- 模型 surface 精確只有 `ls`、`read_file`、`grep`、`write_file`、`edit_file` 與 `delete`。沒有 Duty／Task／OPKS business Tool；複合變更由一般 resource create／edit／delete 形成。
- 每波 workspace mutation 後，validation middleware 在下一個 model boundary 讀取真實 Store bytes，檢查 canonical schema、identity、JD invariant、linkage、current employee Evidence 與 exact quote。digest mismatch 先標 `unvalidated`；invalid workspace 可持久續修，但其內容不產生可接受 review、不改 approved、不被 export。
- semantic review 由 application 比較 approved 與已驗證 workspace，按 dependency 及真正不可分割的 atomic subgroup 分組。員工看到職務語意 before／after，不看到 raw file diff、Tool JSON、VFS path、checkpoint 或 digest。
- review command 綁 exact approved revision、workspace generation／digest、changeset／group digest 與 action IDs；重疊內容改動後 fail stale，不重疊差異則從新基線重新投影。
- `accept` 與 `edit-and-accept` 是 AI 差異進入 approved 的唯一 write edge；員工 direct edit 可直接寫 approved。`reject` 保存理由與 decision memory 並撤回所選 workspace 差異；`defer` 保留 workspace 差異。
- accept／edit-and-accept 先持久化 decision／rebase plan，再把 approved JD 與 command receipt 提交 Saver checkpoint，最後 rebase 並驗證 Store workspace。reopen 或 exact replay 可在 checkpoint 成功、rebase 未完成的 crash window 補完；這是 approved-first recovery，不宣稱 Saver 與 Store 跨 transaction ACID。
- 員工來源保留 exact text、UTF-8 hash 與 stable identity。模型只提供 source handle、逐字 quote、occurrence 與已載 Skill IDs；application 確定性解析同文件 current source 的 Unicode offsets。source correction 保留 lineage、使舊 source 失效，並只阻擋直接依賴舊 Evidence 的 review group；approved 與無關 group 不變。
- 同一 API process 以 document-scoped admission state 及 `asyncio.Lock` 避免 active model run 與 employee review／direct edit 交錯；不同 document 可獨立進行。這是 process-local 保護，不是 distributed lock，沒有 multi-process／multi-instance guarantee。

## Contract 與 Web

`packages/job-analysis-contract/schema/job-analysis-workspace.schema.json` 是唯一 transport source。它發布 consultant catalog、durable snapshot、workspace review status／diagnostics、semantic review／clarification／direct-edit commands、approved document、export readiness 與 problem models；不發布 Store manifest、raw LangGraph state 或 model attempt internals。

Web 只有 `/workspace` 與 `/workspace/[document_id]`，以 TanStack Query 管 server cache、原生 `EventSource` 接 refetch notification、本機草稿保護 dirty editor。畫面分開呈現訪談、AI 目前理解／焦點／Gap／語意進度、AI 待審文件變更與員工核准文件；UI 不解析 raw checkpoint、framework interrupt、VFS path、Tool payload、digest、Context receipt 或 model attempt，也不保存第二份 server authority。

## 現行產品邊界

- 一位主要顧問按需組合 Skills；Skills 不是多個 Agent。沒有 multi-agent、planner／writer／critic 或 subagent 產品拓撲。
- 沒有 auto-accept／Auto mode；所有 AI 文件內容都須員工接受或修改後接受。
- 每份 JD 只有一個 active workspace；沒有 branch、fork、Git／PR、workspace 版本歷史 UI 或多人 review。
- current API／Web 沒有 RAG、Reference、semantic retrieval 或外部知識 Tool；同文件 `/sources` exact lookup 是來源記憶，不是 RAG。
- 能力級別與 A 不由 LLM 產生；官方 iCAP 配發代碼不由模型、員工或 export 補造。
- 本機第一版不提供 multi-process guarantee；擴張為多 process 或多人寫入前必須另開 ADR 加入真正 CAS／lease 與衝突政策。

## RAG 供應鏈（保留、隔離）

`apps/pdf-to-json`、`apps/ocs-indexer`、`apps/embedder`、`packages/ocs-contract` 與 `packages/indexer-contract` 是可獨立安裝／測試／執行的 RAG bounded context。它們不是 current runtime dependency；`npm run up`／`npm run dev` 不啟動，只有 `npm run rag:up`／`rag:dev` 明確 opt-in。current API 不得 import、呼叫或發布它們的 contract／route／tool。詳見 [`docs/design/rag-pipeline.md`](docs/design/rag-pipeline.md)。

## 指路

現行跨 app 真相見 [`docs/design/consultant-runtime.md`](docs/design/consultant-runtime.md)；核心決策見 [ADR 0060](docs/adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md)、[ADR 0066](docs/adr/0066-persistent-ai-jd-working-draft-and-semantic-review.md) 與 [ADR 0067](docs/adr/0067-deep-agents-store-backed-jd-working-draft.md)；本機操作見 [`docs/runbook.md`](docs/runbook.md)。
