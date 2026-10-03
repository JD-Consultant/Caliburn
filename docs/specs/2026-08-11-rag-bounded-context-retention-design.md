# RAG bounded contexts 保留與 current-only 隔離設計

獨立 RAG 包含 PDF 轉換、文件契約、索引、嵌入與向量資料庫。這份 2026-08-11 的設計記錄說明如何保留這條資料管線，同時讓 JD App 不依賴它啟動。文中的目錄與命令保留當時條件；現行產品邊界見[ADR0079](../adr/0079-target-rebuild-production-cutover.md)，操作方式見[操作手冊](../runbook.md)。

## 1. 背景與診斷

`60db19a` 的 current-only hard cut 將 monorepo 從五個 app 與三個 package 收斂成 `apps/api`、`apps/web` 與 `packages/job-analysis-contract`。這同時刪除了尚未接回現行 API/Web、但未來 RAG 仍需要的供應鏈：

```text
PDF → OCS contract → OCS JSON → indexer → embedder → Qdrant
```

已確認的保留範圍是：RAG 尚未接上 current API/Web，但 `pdf-to-json`、`ocs-indexer`、`embedder` 與其 contracts 留在 monorepo，供後續建置使用。

刪除範圍的直接證據：

- `60db19a` 刪除 `apps/ocs-indexer`、`apps/pdf-to-json`、`apps/embedder`。
- 同一 hard cut 刪除 `packages/ocs-contract`、`packages/indexer-contract`。
- ADR 0057 是 `Proposed`；當時依這次範圍修正更新提案，不改寫 Accepted ADR。


## 2. 保留與隔離原則

採「選擇性恢復、隔離保留」：

1. 恢復三個 RAG bounded contexts 與兩個 contracts，使它們可各自安裝、測試、執行。
2. 恢復完整 908 份 OCS JSON corpus。
3. 恢復完整 908 份 PDF corpus；PDF 不只是測試 fixture，也是未來重新產生 OCS JSON 的來源材料。
4. 不恢復已淘汰的 `app.interview`、`app.interview_vnext`、`app.job_authoring`、舊 migration、舊 Web editor 或 SaaS runtime。
5. RAG pipeline 暫時不得被 current API/Web import 或呼叫；正式接線時另開 ADR 定義 API⇄indexer contract 與資料流。

## 3. 目標 monorepo 邊界

```text
apps/
├─ api/                 # current Job Analysis product
├─ web/                 # current local workspace
├─ pdf-to-json/         # PDF → OCS JSON；獨立 Python app
├─ ocs-indexer/         # OCS JSON → Qdrant；獨立 Python app
└─ embedder/            # BGE-M3 HTTP service；GPU container

packages/
├─ job-analysis-contract # current API/Web contract
├─ ocs-contract          # PDF/parser/indexer OCS document contract
└─ indexer-contract      # future indexer query/API wire contract
```

這仍是 monorepo；app 數量不代表所有 app 都必須在同一個 production composition root。RAG app 是 repo member 與可獨立驗證的 bounded context，但不是 current Web product 的 runtime dependency。

## 4. 啟動與依賴設計

### Current path

- `npm run up` 維持 PostgreSQL 加 current API/Web。
- current API/Web 不依賴 Qdrant、embedder、`ocs-contract` 或 `indexer-contract`。
- current production boundary guard 繼續禁止 API/Web 反向接入 RAG app。

### RAG path

- Compose 保留 `qdrant` 與 `embedder`，但標記為 `rag` profile。
- RAG 使用者明確啟用 profile 後，才啟動 Qdrant／GPU embedder；indexer 仍可在 host 以自己的 uv project 執行。
- root 提供獨立的 RAG 操作指令；current `dev`／`up` 不得因 workspace 恢復而自動啟動 indexer。
- `npm run down` 的 current 行為不應要求 RAG service 存在；另提供 RAG profile 的停止指令。

Docker 官方的 Compose profiles 允許未標 profile 的核心服務預設啟動，並以 `--profile` 或 `COMPOSE_PROFILES` 選擇性啟動其他服務，符合 current path 與 RAG path 的隔離需求：

- <https://docs.docker.com/compose/how-tos/profiles/>
- <https://qdrant.tech/documentation/installation/>

### Python project path

`pdf-to-json`、`ocs-indexer`、contracts 保持各自的 `pyproject.toml`／`uv.lock`。`ocs-contract` 與 `indexer-contract` 以相對 path dependency 提供給需要它們的 app；current API 不宣告這些依賴。uv 官方支援 editable path source，且明確指出多 package repo 可使用 workspace／path dependency 管理：

- <https://docs.astral.sh/uv/concepts/projects/dependencies/>

## 5. 資料流與責任

```text
PDF corpus
  │
  ▼
pdf-to-json ──uses──> ocs-contract ──writes──> OCS JSON corpus
                                               │
                                               ▼
                                         ocs-indexer
                                               │
                         HTTP embedding       │ Qdrant
                         ┌───────────────┐    ▼
                         │ apps/embedder │ → vector index
                         └───────────────┘
```

- `pdf-to-json` 只負責解析與轉換，不寫 current PostgreSQL。
- `ocs-indexer` 只負責 ingest、embedding wiring、Qdrant index/query，不 import current API domain。
- `embedder` 只提供 BGE-M3 HTTP embedding service，不進 API process。
- `indexer-contract` 保留作未來 query seam；在 current API 尚未接 RAG 前，不新增 consumer。

## 6. 隔離設計的驗證方法

隔離設計可從依賴、啟動及測試三方面檢查：

1. root workspace graph 看得到三個 RAG app 與兩個 contracts；current API/Web 仍可正常 install。
2. `pdf-to-json` 的 parser／transformer tests 與 `ocs-contract` codegen check 通過。
3. `ocs-indexer` 的 unit／contract tests 通過；不把 live Qdrant 或 GPU 服務列為預設單元測試前提。
4. `docker compose config` 的預設服務只有 PostgreSQL；啟用 `rag` profile 才包含 Qdrant／embedder。
5. Turbo 的預設 `dev` 只啟動 current API/Web；RAG 以明確 filter／指令啟動。
6. Workspace lockfile 與各專案依賴一致，現行 API／Web 的測試不因 RAG 目錄存在而改變。
7. 新增或更新 boundary tests，證明 current API/Web 沒有 import `apps/ocs-indexer`、`apps/pdf-to-json`、`embedder` 或舊 runtime。

## 7. 後果與未來接線

好處是 RAG 所需程式碼與來源資料不會再被 current-only cleanup 誤刪，同時 current Web 成品不會被 Qdrant、GPU 或 PDF pipeline 拖入啟動與部署邊界。代價是 monorepo 會重新包含兩個 Python data app、GPU container 與約 311.6 MiB PDF corpus；這是為未來 RAG 保留可重建來源所接受的成本。

讓 JD App 使用檢索結果，還需要定義查詢格式、索引更新時效、嵌入模型身分、失敗時的替代行為，以及結果與 JD 依據的關係。這份設計只處理獨立 RAG 的保留與隔離，不代表已接入 JD App。

## 8. 研究來源

- 本 repo：`docs/adr/0057-current-only-runtime-and-data-boundary.md`（Proposed，需依本裁決修正）。
- 本 repo：`docs/specs/2026-08-10-current-only-hard-cut-design.md`、`docs/plans/2026-08-10-current-only-hard-cut-plan.md`。
- Git history：`60db19a` 及其 parent，作為恢復檔案與刪除範圍的 provenance。
- Docker Compose Profiles 官方文件：<https://docs.docker.com/compose/how-tos/profiles/>。
- uv path dependencies 官方文件：<https://docs.astral.sh/uv/concepts/projects/dependencies/>。
- Qdrant 官方安裝／Docker 文件：<https://qdrant.tech/documentation/installation/>。
