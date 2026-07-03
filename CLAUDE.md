# Caliburn — agent orientation

Caliburn 是給顧問用的**多租戶 B2B SaaS**(職能基準 OCS → 職務說明書),公司間資料隔離。
Monorepo。維護者用**繁體中文**,請用繁中回應。

> 記憶是 per-project 的,不會跨資料夾搬。**這個 repo 的 `CLAUDE.md` + `docs/` 才是權威**;
> 不確定就讀下面指的文件,別憑空猜。

## 最重要:工作紀律(每個變更都照這個)

1. **先研究再動手** —— 重大變更前找**權威/主流/大廠/資深人物**的資料(官方文件、原作者、規範),
   寫一份**研究紀錄**到 `docs/specs/<date>-*.md`(含來源、診斷、選項、比對)。
2. **決策寫 ADR** `docs/adr/00NN-*.md`(Nygard 式;Accepted 後不改內容,要翻案開新號),
   並更新索引 `docs/adr/README.md`。
3. **plan** 寫到 `docs/plans/`(bite-size、可獨立驗證),再實作。
4. **安全網優先** —— 盡量 **move-only** 重構;既有測試/golden 當 characterization net,
   **green-before == green-after**;**一個 task 一個 commit**,綠了才 commit;收尾打 git tag。
5. **新 seam(API/共用格式)選契約機制** —— 照 `docs/contract-strategy.md` 的判準(已預答 #3)。
6. **不要 push、不做對外動作**,除非使用者明確要求。先研究、不懂就問。
7. **改子系統就更文檔** —— 跨 app/seam 的端到端說明住 `docs/design/`(單一 app 的住該 app 底下);
   **動到那條線的碼 → 同 commit 更新該文檔**(fossilization 是頭號壞味道)。寫法照
   `docs/design/README.md` 的 dual-audience 清單(動作→請求、真名、不變量、退役禁令)。

## 架構(權威:`ARCHITECTURE.md` + `docs/adr/README.md`)

- **monorepo**:Turborepo + **per-app uv**(各自 `uv.lock`)+ 契約用 **path-dep 套件**(`packages/`)。
- **3 個 bounded context**:`apps/pdf-to-json`(PDF→OCS JSON 解析)/ `apps/ocs-indexer`(檢索,Qdrant)/
  `apps/api` + `apps/web`(著作)。語言在這三處切換(對齊 DDD)。
- **api = 六邊形**:`app/core`(ports + domain,純)、`app/adapters`(DB/LLM/knowledge 等邊緣)、
  `app/services`(use-case)、`app/authoring`(LangGraph 編排,原 graph_v3;深問是**刻意單層 loop**,別重構)。ADR 0008。
- **契約**:#1 `packages/ocs-contract`(OCS 文件,JSON-schema→Pydantic+TS)、
  #2 `packages/indexer-contract`(indexer⇄api,共用 pydantic)、#3 web 吃 ocs-contract 生成的 TS。
  ADR 0004 / 0010 / 0011。
- **嵌入**:BGE-M3(dense+sparse)跑在 **GPU 容器 `apps/embedder`**(FastAPI+FlagEmbedding);
  indexer/api 走 HTTP 呼叫。**絕對不要把 torch 放回 app 進程**——Windows 上會 segfault/`_dynamo` 崩,
  已根治(ADR 0012;細節 `docs/specs/2026-06-29-embedder-service-bge-m3-research.md`)。

## 本地開發(`CONTRIBUTING.md` / `docs/runbook.md`)

- **一鍵**:`npm run up` = `docker compose up -d`(db:5432 + qdrant:6333 + **embedder:8082(GPU)**)
  `&& turbo dev`(api:8001 + web:3000 + indexer:8000)。`npm run down` 停 infra;Ctrl-C 停 dev server。
- 首次/改 schema:`npm run db:migrate`。Qdrant 空要建一次索引:
  `cd apps/ocs-indexer && uv run jd-ocs-indexer index ./data/jd-json`(走 embedder,**不需本機 torch**)。
- **測試**:`npx turbo test`。各 app:api `uv run pytest`、ocs-indexer `uv run --all-extras pytest`、
  pdf-to-json `uv run --extra dev pytest`;web `npx tsc --noEmit` + `npm run lint`。

## Windows 踩雷(重要)

- **PowerShell/Bash 工具的預設 cwd 可能是封存的舊 repo `s:\jobintel-ai`**。對 caliburn 下 docker compose 要
  `docker compose -p caliburn -f S:\caliburn\docker-compose.yml …`,或先 `cd /s/caliburn`;Bash 工具每次會 reset cwd。
- **在 git worktree 開發時,子代理/Bash 的 cwd 也可能落回主 checkout `s:\caliburn`(main)**——結果似是而非
  (grep 找不到明明存在的欄位之類)。動 worktree 前先 `pwd` + `git branch --show-current` 驗證。
- GPU-in-Docker 已驗證可用(RTX 4060,Docker Desktop + WSL2,`nvidia` runtime);embedder 容器用 `gpus: all`。
- `run_live.py` 的 reload 已關(改後端碼要手動重啟);git autocrlf(比對 codegen 用 `git diff` 不要用原始 diff);
  uv venv 沒有 pip,用 `uv pip`;CJK 用 `PYTHONUTF8=1`。
- **舊三 repo 已封存**(`s:\jobintel-ai` / `s:\jd-ocs-indexer` / `s:\jd-pdf-to-json`),別在那開發。

## 指路
`ARCHITECTURE.md` · `docs/adr/README.md`(0001–0021)· `docs/contract-strategy.md` ·
`CONTRIBUTING.md` · `docs/runbook.md` · `docs/specs/`(研究紀錄)· `docs/plans/` ·
**`docs/design/`(子系統端到端設計,給 agent;首份 `editor-knowledge-pack.md`)**。
