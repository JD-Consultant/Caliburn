# Current Application Modularization — 完成報告

**分支：** `refactor/current-application-modules`（分出自 `refactor/current-only-architecture` @ `af7d732`）
**Tag：** `current-application-modules-v1`（指向 `44bab11`）
**依據計畫：** [`docs/plans/2026-08-10-current-application-modularization-plan.md`](../plans/2026-08-10-current-application-modularization-plan.md)（8 個 task 全數勾選完成）
**權威 ADR：** [`docs/adr/0058-current-api-functional-modules-and-dependency-rules.md`](../adr/0058-current-api-functional-modules-and-dependency-rules.md)
**研究依據：** [`docs/specs/2026-08-10-job-analysis-module-boundaries-research.md`](2026-08-10-job-analysis-module-boundaries-research.md)

## 目標

在不改 HTTP／JSON Schema／PostgreSQL／產品行為的前提下，移除歷史隔離容器
`apps/api/app/job_analysis`，把現行 API 拆成 ADR 0058 規定的功能模組
（`core`／`documents`／`task_analysis`／`opks`／`consultation`／`export`／`adapters`／`api`），
並把 `apps/web` 整理成 feature-first 結構。純 source-level refactor，無資料庫、
契約、或前端行為變更。

## 執行方式

用 `superpowers:subagent-driven-development`：每個 task 由一個全新 implementer
subagent 實作、commit、自我審查；再由獨立 task-reviewer subagent 做 spec
compliance + code quality 兩項判定；有 Important/Critical 發現就開 fix
subagent 修正、再審一輪，直到 clean 才進下一個 task。8 個 task 全部跑完後，
再對整條分支跑一次 whole-branch review（Opus），把該輪發現的問題也修完、
再審一次通過。施工全程在獨立 git worktree（`.worktrees/current-application-modules`）
進行，未動到使用者原本工作樹的任何未追蹤／未提交內容。

## 變更範圍

- **後端**（`apps/api/app/`）：`app/job_analysis/` 完全刪除（無 shim、無 facade）。
  新增 `core/`（shared domain kernel + authority + persistence ports +
  journal/errors/model_outcome/opks_integrity）、`documents/`、`task_analysis/`
  （含 `TaskAnalysisModelPort`）、`opks/`（含 `OpksModelPort`）、`consultation/`
  （唯一同時依賴 task_analysis 與 opks 的模組）、`export/`、
  `adapters/{postgres,openrouter,xlsx}/`；`api/routes/` 與 mapper 依 feature
  拆成四組，共用原 `/job-analysis/documents` prefix。六個模組各自有 AST
  import-boundary guard test（`apps/api/tests/test_job_analysis_dependencies.py`），
  外加一個涵蓋 `app/api` 與所有 composition-root 檔案（`app_factory.py`／
  `main.py`／`database.py`／`config.py`／`observability.py`／`models/**`）的
  guard，全部用 `__all__` cross-check 防止「import 到 submodule 而非 curated
  export」的漏洞。
- **前端**（`apps/web/src/`）：`components/workspace/`、`lib/jobAnalysis*.ts`
  解散，改為 `features/{documents,consultation,opks,export}/`（各自有
  curated `index.ts`）＋ `shared/{api,query,providers,ui}/`；`ConsultationPanel`／
  `ConsultationWorkspace`（同時協調兩個 feature 的 proposal review UI）留在
  `app/workspace/[document_id]/_components/` 做 app-level composition。新增
  `src/architecture.test.ts`（TypeScript compiler API + Vitest）強制
  shared→feature 禁止、feature↔feature 禁止、app 只能經 feature `index.ts`
  進入、以及 feature/shared 不得反向 import app。
- **文件**：`AGENTS.md`、`ARCHITECTURE.md`、`docs/design/task-analysis-engine.md`、
  `docs/design/README.md`、`apps/api/README.md`、`apps/web/README.md`、
  `apps/web/docs/data-layer.md` 的 source map／依賴規則同步更新；
  `apps/api/app/job_analysis/AGENTS.md` 內容併入權威文件後刪除舊檔；
  ADR 0058 補一句話記錄 `core/opks_integrity.py` 作為 rule 7 的
  「已知但受觀察」例外（它放的是 OPKS staleness/pruning policy，不是純型別／port，
  但另一個選項——開一條 `documents → opks` 邊——更糟）。

共 15 個 commit，201 個檔案，+3773/-2970 行。完整 commit 列表：

```
8926248 refactor: extract current authority domain core
4f2754f refactor: extract authority and persistence seams
9c4f79b refactor: split journal payload contracts out of persistence ports
87aad76 refactor: extract documents module
c210a91 test: guard documents module import boundary
34c973b refactor: extract task analysis module
917240e refactor: extract opks module
237b4bb refactor: extract consultation orchestration
da83d9c test: close submodule-reach-in loophole in consultation import guard
61b35ec refactor: compose current functional modules
ef12ca1 fix: restore JdTaskView annotation and fix stale doc path
c7a13e7 refactor: organize workspace by feature
ef090a5 docs: sweep stale paths, tick plan checkboxes, note core watch item
095dc9c test: close remaining import-guard gaps found in whole-branch review
44bab11 docs: fix stale jobAnalysisQueries.ts path in web data-layer doc
```

## 審查結果

- **8 個 task 全數 task-scoped review 通過**（spec compliance + code quality
  雙判定）。5 個 task 在第一輪就 clean；3 個 task（Task 2／3／6）發現
  Important 問題後修正、再審通過——都是 guard/split 相關的紮實發現（例如
  Task 6 第一輪的 AST guard 有 module-string 漏洞，`from app.task_analysis
  import operation` 能繞過檢查，修正後改用 `__all__` cross-check）。
- Task 5 施工中發現一個計畫本身沒列到的邊界問題（`question_target_task_ids`
  按 ADR 0058 rule 2 在 `opks` 底下沒有合法歸屬，`StaleAuthoritySnapshot`
  同時被 opks 與 consultation 消費），implementer 自行搬移並在報告中詳列依據；
  reviewer 驗證技術結果正確，但把「未先跟 controller 確認就動了已審過的模組」
  記成一個流程提醒，供後續 task 參考。Task 8 也遇到類似情況
  （`UnsavedChangesGuard` 同時被 opks 與 documents 消費），這次在完成報告中
  主動先講清楚依據，reviewer 判定是正確且必要的偏離。
- **全分支 review**（Opus，對整條 12-commit diff）：驗證了 HTTP 路由集合
  逐一比對後與搬移前完全相同（21 個 endpoint，含 path／method／status_code／
  response_model）、mapper 22 個函式全數搬移無遺漏、provider-before-transaction
  順序未變、零 migration／schema 改動。結論「Ready to merge: With fixes」，
  抓到兩個 Important（`app/api` guard 有跟 Task 6 同款的漏洞、guard 涵蓋範圍
  漏了六個 composition-root 檔案）與若干 Minor（過期文件路徑、plan checkbox
  未勾、`architecture.test.ts` 有未涵蓋的 zone）。修正後再審一輪，全數
  Critical/Important 清零。

## 驗證證據（Final Gate，`docs/plans/...-plan.md` 最後一節）

- `rg` 掃描 `apps AGENTS.md ARCHITECTURE.md` 找不到任何現行 source 的舊路徑
  （`app.job_analysis`／`components/workspace`／`@/lib/jobAnalysis`）。
- 後端 AST 依賴契約：`test_job_analysis_dependencies.py` 10/10 通過
  （six 模組 guard + api/composition-root guard + openpyxl 隔離 + 舊路徑禁用）。
- `npm run check-codegen -w @caliburn/job-analysis-contract`：零真實差異
  （唯一一次 diff 是換行符號雜訊，已還原）。
- `npx turbo test --force --env-mode=loose`：api 715 passed/104 skipped
  （無 DB 模式）、web 9 files/59 tests passed。
- Web `npx tsc --noEmit` 與 `npm run lint`：乾淨。
- 對本機 PostgreSQL（migration head = 0017）跑完整 API suite：818 passed，
  1 個已知、與本次改動無關的既存失敗
  （`test_postgres_rejects_a_task_with_a_dangling_duty_reference`，經 Task 3／5／6／7
  四個獨立 reviewer 各自從 diff 內容確認與本分支任何 commit 無因果關係——
  沒有任何 commit 動過 migration／FK／schema）。
- `git diff --check`：整條分支（`af7d732..HEAD`）乾淨。
- 工作樹只剩使用者原有未追蹤檔，無殘留。

## 已知延後項目（非阻塞，供審核者知悉）

以下是全分支 review 明確判定「可以延後」、且已記錄在案的項目，不在本分支修：

- `apps/api/app/task_analysis/__init__.py` 的 `ProposalDecision` 是一個沒有
  外部消費者的 dead export（可留給下次順手清或補上型別消費）。
- `TaskAnalysisModelPort`／`OpksModelPort` 目前沒有 mypy/pyright 或
  `@runtime_checkable` 驗證簽章一致；有 smoke test 會在簽章漂移時透過
  `TypeError` 間接抓到，但不是專門的邊界測試。
- `_optional_text` helper 在三個 mapper 檔案中逐字重複（5 行 ×3）——已確認
  合併不會造成 import cycle，純粹是這次沒動它，先留著。
- `apps/api/app/adapters/openrouter/__init__.py` 的 facade 有 29 個 public
  names，超過 25 的 review 門檻，但是搬移前就存在的狀態（100% rename），
  非本次引入。
- 沒有一支專門的「route snapshot」測試會在未來的路由拆分中自動抓漏；
  這次是靠 reviewer 手動逐一比對 21 個 endpoint 確認一致，值得之後補一支。

## 如何在本機重跑驗證

```bash
cd apps/api && uv run pytest -q                      # 無 DB
TEST_DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/caliburn \
  uv run pytest -q                                    # 對本機 Postgres 全跑
cd apps/web && npx tsc --noEmit && npm run test && npm run lint
npx turbo test --force --env-mode=loose
npm run check-codegen -w @caliburn/job-analysis-contract
```

## 目前狀態

分支與 worktree（`S:\caliburn\.worktrees\current-application-modules`）保留，
尚未 merge、未 push。等候人工審核。
