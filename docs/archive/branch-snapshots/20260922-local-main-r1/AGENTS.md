# Caliburn — agent orientation

Caliburn 現行目標是給員工使用的**伺服器部署、瀏覽器存取的 AI 職務分析與職務說明書 Web 應用程式**。Web UI／API／資料
由企業在內網／私有環境操作，或由我們代管；員工裝置只需瀏覽器，不在個人電腦執行完整 stack。第一個 production scope
是一個 deployment 服務一個企業，可保存並重新開啟多份彼此隔離的職務說明書。這不等於立即建立共享多租戶 B2B SaaS：
未另案前不得新增 tenant control plane、organization/member、ACL、計費、quota 或 tenant administration。多人角色、登入與
企業 SSO 必須在 R8 對非受控網路或多名使用者開放前另案決定，不能再用「只跑 localhost」迴避。
完整產品範圍鎖定見 `docs/product-notes.md`。Monorepo。維護者用**繁體中文**,請用繁中回應。

> 記憶是 per-project 的,不會跨資料夾搬。**這個 repo 的 `AGENTS.md` + `docs/` 才是權威**;
> 不確定就讀下面指的文件,別憑空猜。
> 本檔是唯一來源:`CLAUDE.md` 只做 `@AGENTS.md` import,**要改 orientation 就改這裡**,別在 `CLAUDE.md` 抄一份。

## 最重要:工作紀律(每個變更都照這個)

1. **先研究再動手** —— 重大變更前找**權威/主流/大廠/資深人物**的資料(官方文件、原作者、規範),
   寫一份**研究紀錄**到 `docs/specs/<date>-*.md`(含來源、診斷、選項、比對)。
2. **決策寫 ADR** `docs/adr/00NN-*.md`(Nygard 式;Accepted 後不改內容,要翻案開新號),
   並更新索引 `docs/adr/README.md`。**狀態預設 `Proposed`**——審查中的修正一律直接改那份
   Proposed ADR;**owner 核准後另開一個 commit** 把 ADR 與索引一起轉 `Accepted`。
   只有 owner 事先明確核准具體內容才可一開始就寫 `Accepted`。先例:ADR 0045
   (`820695a` Proposed → `f45b268` Accepted)。
3. **plan** 寫到 `docs/plans/`(bite-size、可獨立驗證),再實作。
4. **安全網優先** —— 盡量 **move-only** 重構;既有測試/golden 當 characterization net,
   **green-before == green-after**;**一個 task 一個 commit**,綠了才 commit;收尾打 git tag。
5. **新 seam(API/共用格式)選契約機制** —— 照 `docs/contract-strategy.md` 的判準(已預答 #3)。
6. **不要 push、不做對外動作**,除非使用者明確要求。先研究、不懂就問。
7. **改子系統就更文檔** —— 文檔架構/擺放/寫作/維護的**權威總則見 `docs/README.md`**。跨 app/seam 的
   端到端說明住 `docs/design/`(單一 app 的住該 app 底下);**動到那條線的碼 → 同 commit 更新該文檔**
   (fossilization 是頭號壞味道);寫法照 dual-audience 清單(動作→請求、真名、不變量、退役禁令)。

### 現行產品優先級（高於歷史 SaaS 架構慣性）

- 先做員工可用瀏覽器操作的 server-deployed Web release candidate；員工不得負責設定 host／port、資料庫、GPU 或服務啟停，
  也不要引入未被要求的 Electron／Tauri／原生桌面殼。企業自管與我們代管共用同一套 deployable stack；開發者 localhost
  只是 development profile。第一版只有通過真實在職員工的端到端 pilot gate 後，才能稱為員工可用成品；合成 eval、
  高擬真 transcript 或內部自測不得替代（ADR 0056／0057）。
- 第一版 Current JD 是員工確認、可交主管／HR 審閱的草稿，不宣稱企業正式核准。server deployment 本身不授權 reviewer role、
  多人共編、共享多租戶 SaaS、organization／tenant 或 ACL；這些仍須另案。但不得再把企業自管／我們代管的 deployment
  誤稱為 SaaS 擴張而禁止。
- 時間、研究與設計優先投入訪談品質、Context Engine、LLM 工作分析、task/output/indicator/K/S 品質、Evidence linkage與JD成品品質。
- Server-side API 可呼叫 OpenRouter；API key 是 deployment secret，不得進瀏覽器或由員工日常輸入。
- 不為未被要求的 SaaS、generic framework、全面 hash／audit 或測試排列拖延成品；仍保留會直接保護文件真相、員工決策、
  provenance與交易正確性的核心安全網。

### 輸出風格

- **文檔長度照任務給** —— `docs/specs/`、ADR、`docs/plans/` 講清楚實質內容就停;不要補填充章節、
  重複摘要、樣板段落。ADR 就是 Nygard 那幾段(context / decision / consequences),不是論文。
- **回應精簡** —— 動手前一句話說要做什麼;過程中只在有發現或改方向時回報;收尾第一句先講結果,
  細節放後面。但書與免責從簡。
- **少開 subagent** —— 只有大型、真正獨立可平行的工作(例如跨多檔案的橫向調查)才委派。幾個 tool call
  能做完的不要委派;**不要開 subagent 複查自己的工作**;一個能做完就別開多個。
- 規則 4 的測試綠燈、一 task 一 commit 是工程紀律,留著。但**不要再加「做完自己再複查一遍」這類自我複查
  指令** —— 模型本來就會自查,重複下令只會多燒 token 而不提升品質。

## 架構(權威:`ARCHITECTURE.md` + `docs/adr/README.md`)

- **monorepo**:Turborepo + **per-app uv**(各自 `uv.lock`)+ 契約用 **path-dep 套件**(`packages/`)。
- **3 個 bounded context**:`apps/pdf-to-json`(PDF→OCS JSON 解析)/ `apps/ocs-indexer`(檢索,Qdrant)/
  `apps/api` + `apps/web`(著作)。語言在這三處切換(對齊 DDD)。
- **api = 六邊形**:`app/core`(ports + domain,純)、`app/adapters`(DB/LLM/knowledge 等邊緣)、
  `app/services`(use-case)、`app/interview`(**淘汰但暫留的舊 AI 路徑**:顧問+書記 op→verify→`_pending`
  追蹤修訂;判準教材在 `app/interview/skills/`,調教首選改 skill 不改碼)、`app/observability.py`
  (OTel 橫切)。ADR 0008 / **0030**(舊 LangGraph/CopilotKit 已退場,勿救回;端到端見
  `docs/design/interview-engine.md`)。
- **Task Analysis 引擎(現行新工作面)**：`app/job_analysis` 依 ADR **0040／0042** greenfield 實作
  (domain／llm／application／providers)。durable vertical 已接通：文件/direct edit → PostgreSQL
  Current State → packet → 一次 HTTP → verifier → identity gate → 候選/Proposal → 員工決策 → reload；
  新 `/api/v1/job-analysis` routes 與 `/workspace` Web 已接通，conversation／Proposal／Current JD 同頁。
  資料從新四表開始，不搬、不整合、不雙寫舊資料。禁止 import
  `app.interview`／`app.interview_vnext`／`app.job_authoring`／`evals`(AST 測試強制)。
  端到端見 `docs/design/task-analysis-engine.md`。
- **AI vNext 隔離中**：`app/interview_vnext` 依 ADR **0034** greenfield 實作；V1 domain 與 V2-A
  provider-neutral/Capture contracts 已完成，無 route/DB/live LLM，production 不 import。禁止 import/wrap v3 consultant/scribe/harvest/select；細節先讀
  `app/interview_vnext/README.md`、其 `AGENTS.md` 與 `docs/plans/2026-07-16-interview-ai-vnext-implementation-plan.md`。
- **離線 R1 harness 是封存資產,不是工作面**：`app/professional_consultant` 與
  `evals/professional_consultant/r1` 是另一條離線分支在**尚未看到 ADR 0042 之前**建的六臂快篩資產
  (contracts／verifier／prompts／runners／capture／blind grader)。ADR **0042** 已裁定 R1 架構快篩收束、
  A6 作第一版預設,**合併進 main 不等於恢復快篩**;沒有 owner 新裁決不得續建、不得跑 48/80、
  不得接 route/DB/Web。現行工作面一律是 `app/job_analysis`;與 `evals/professional_consultant_r1`
  的取捨與退役見 `docs/design/professional-consultant-engine.md`。
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
  並從 repo 根跑。**本機絕對路徑 / 封存舊 repo 位置 / GPU 型號見 `CLAUDE.local.md`**(gitignored;
  Codex 讀者另有 `Codex.local.md` 位置,兩者都在 `.gitignore`)。
- GPU-in-Docker 已驗證可用(Docker Desktop + WSL2、`nvidia` runtime);embedder 容器用 `gpus: all`。
- `run_live.py` 的 reload 已關(改後端碼要手動重啟);git autocrlf(比對 codegen 用 `git diff` 不要用
  原始 diff);uv venv 沒有 pip,用 `uv pip`;CJK 用 `PYTHONUTF8=1`。

## Agent skills

### Issue tracker

Issue、spec 與 ticket 使用 `.scratch/<feature>/` 下的 Local Markdown 管理。見
`docs/agents/issue-tracker.md`。

### Triage labels

使用 `needs-triage`、`needs-info`、`ready-for-agent`、`ready-for-human`、`wontfix` 五種標準狀態。見
`docs/agents/triage-labels.md`。

### Domain docs

採 multi-context domain docs；由根目錄 `CONTEXT-MAP.md` 指向各 bounded context 的 `CONTEXT.md`。見
`docs/agents/domain.md`。

## 指路
**`docs/README.md`(文檔系統:架構/規則/索引)** · `ARCHITECTURE.md` · `docs/adr/README.md`(0001–0057)·
`docs/contract-strategy.md` · `CONTRIBUTING.md` · `docs/runbook.md` · `docs/specs/`(研究紀錄)·
`docs/experiments/`(實證紀錄)·
`docs/plans/` · `docs/design/`(子系統端到端設計,給 agent)。
