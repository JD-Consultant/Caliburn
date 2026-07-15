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
7. **改子系統就更文檔** —— 文檔架構/擺放/寫作/維護的**權威總則見 `docs/README.md`**。跨 app/seam 的
   端到端說明住 `docs/design/`(單一 app 的住該 app 底下);**動到那條線的碼 → 同 commit 更新該文檔**
   (fossilization 是頭號壞味道);寫法照 dual-audience 清單(動作→請求、真名、不變量、退役禁令)。

## 架構(權威:`ARCHITECTURE.md` + `docs/adr/README.md`)

- **monorepo**:Turborepo + **per-app uv**(各自 `uv.lock`)+ 契約用 **path-dep 套件**(`packages/`)。
- **3 個 bounded context**:`apps/pdf-to-json`(PDF→OCS JSON 解析)/ `apps/ocs-indexer`(檢索,Qdrant)/
  `apps/api` + `apps/web`(著作)。語言在這三處切換(對齊 DDD)。
- **api = 六邊形**:`app/core`(ports + domain,純)、`app/adapters`(DB/LLM/knowledge 等邊緣)、
  `app/services`(use-case)、`app/interview`(**現行 production 唯一 AI 大腦**:顧問+書記 op→verify→`_pending`
  追蹤修訂;判準教材在 `app/interview/skills/`,調教首選改 skill 不改碼)、`app/observability.py`
  (OTel 橫切)。ADR 0008 / **0030**(舊 LangGraph/CopilotKit 已退場,勿救回;端到端見
  `docs/design/interview-engine.md`)。
- **AI vNext 隔離中**：`app/interview_vnext` 依 ADR **0034** greenfield 實作；V1 domain foundation 已完成，
  無 route/DB/LLM，production 不 import。禁止 import/wrap v3 consultant/scribe/harvest/select；細節先讀
  `app/interview_vnext/README.md`、其 `AGENTS.md` 與 `docs/plans/2026-07-16-interview-ai-vnext-implementation-plan.md`。
- **契約**:#1 `packages/ocs-contract`(OCS 文件,JSON-schema→Pydantic+TS)、
  #2 `packages/indexer-contract`(indexer⇄api,共用 pydantic)、#3 web 吃 ocs-contract 生成的 TS。
  ADR 0004 / 0010 / 0011。
- **嵌入**:BGE-M3(dense+sparse)跑在 **GPU 容器 `apps/embedder`**(FastAPI+FlagEmbedding);
  indexer/api 走 HTTP 呼叫。**絕對不要把 torch 放回 app 進程**——Windows 上會 segfault/`_dynamo` 崩,
  已根治(ADR 0012;細節 `docs/specs/2026-06-29-embedder-service-bge-m3-research.md`)。

## 本地開發(`CONTRIBUTING.md` / `docs/runbook.md`)

- **一鍵**:`npm run up` = `docker compose up -d`(db:5432 + qdrant:6333 + **embedder:8082(GPU)**)
  `&& turbo dev`(api:8001 + web:3000 + indexer:8000)。正常收 dev server 用 Ctrl-C;
  `npm run down` = `docker compose down` + `kill-port 3000/8000/8001`(停 infra **且**補收 dev server 孤兒進程
  ——視窗被硬關沒 Ctrl-C 時,uvicorn/next 會殘留占著 port,down 會清掉)。
- 首次/改 schema:`npm run db:migrate`。Qdrant 空要建一次索引:
  `cd apps/ocs-indexer && uv run jd-ocs-indexer index ./data/jd-json`(走 embedder,**不需本機 torch**)。
- **測試**:`npx turbo test`。各 app:api `uv run pytest`、ocs-indexer `uv run --all-extras pytest`、
  pdf-to-json `uv run --extra dev pytest`;web `npm run test`(vitest,src/lib)+ `npx tsc --noEmit` + `npm run lint`。

## Windows / 環境踩雷(重要)

- **Bash/PowerShell 工具的 cwd 未必是你以為的 repo**——Bash 工具每次 reset cwd,且可能落在別的
  checkout(封存的舊 repo,或 worktree 開發時落回主 checkout `main`);徵狀似是而非(grep 找不到明明
  存在的欄位)。**動手前 `pwd` + `git branch --show-current` 驗證**;docker compose 用 `-p caliburn`
  並從 repo 根跑。**本機絕對路徑 / 封存舊 repo 位置 / GPU 型號見 `CLAUDE.local.md`。**
- GPU-in-Docker 已驗證可用(Docker Desktop + WSL2、`nvidia` runtime);embedder 容器用 `gpus: all`。
- `run_live.py` 的 reload 已關(改後端碼要手動重啟);git autocrlf(比對 codegen 用 `git diff` 不要用
  原始 diff);uv venv 沒有 pip,用 `uv pip`;CJK 用 `PYTHONUTF8=1`。

## 指路
**`docs/README.md`(文檔系統:架構/規則/索引)** · `ARCHITECTURE.md` · `docs/adr/README.md`(0001–0034)·
`docs/contract-strategy.md` · `CONTRIBUTING.md` · `docs/runbook.md` · `docs/specs/`(研究紀錄)·
`docs/plans/` · `docs/design/`(子系統端到端設計,給 agent)。
