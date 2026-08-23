# 持久 Store-backed AI JD 工作草稿完成報告

- **完成日期**：2026-08-23
- **施工計畫**：[`2026-08-22-persistent-store-backed-jd-working-draft-plan.md`](../plans/2026-08-22-persistent-store-backed-jd-working-draft-plan.md)
- **現行決策**：[ADR 0066](../adr/0066-persistent-ai-jd-working-draft-and-semantic-review.md)、[ADR 0067](../adr/0067-deep-agents-store-backed-jd-working-draft.md)、[ADR 0068](../adr/0068-framework-run-budgets-replace-lookup-wave-cap.md)
- **目前狀態**：保留於隔離 branch／worktree，尚未 merge、push 或開 PR。請用 `git branch --show-current`、`git rev-parse HEAD` 與 `git log --oneline` 取得當下位置，不在報告硬寫會因修正輪次失效的 final SHA／commit 數。

## 1. 結果

現行產品已從「每次 run 產生一份 candidate、模型顯式 check／publish、另一份 review queue 等員工裁決」切換成一份可跨回合續編的 JD 工作草稿：

1. AI 透過 Deep Agents 六個低階 filesystem Tools 編輯 `/workspace`；未接受內容在下一則訊息、關閉頁面、provider failure 與 process restart 後仍保留。
2. application 在每波修改後自動解析與驗證 Duty、Task、O／P／K／S、關聯與 Evidence；invalid 草稿可留待下一輪修，但不能進入可接受審核或 export。
3. 員工看到的是 approved JD 與工作草稿間的職務語意變更，不是檔案 path、JSON patch、Tool call 或 graph state。
4. 員工可接受、修改後接受、拒絕或延後；只有接受／修改後接受與員工直接編輯能經 authority seam 改變 approved JD。
5. AI 下一輪可讀取仍待決或延後的草稿並繼續整理；拒絕記憶會抑制同一語意變更，但不阻止真正不同的新建議。
6. Current 產品仍是一位職務分析顧問：有當前訪談焦點、背景線索吸收、Gap、可信進度、必要澄清與按需 Skills；本輪沒有加入 RAG、A、能力級別、auto-accept、多 Agent 或 eval 平台。

## 2. Framework mapping 與 Caliburn 最薄責任

| 目的 | 現行成熟 primitive | Caliburn 仍保留的必要規則 |
|---|---|---|
| Agent loop、Structured Output、middleware | LangChain 1.x | 職務顧問回答契約與產品 stopping rule |
| 六個 editor Tools、VFS route、workspace file CRUD | Deep Agents `CompositeBackend`／`StoreBackend` | document scope、唯讀／可寫 root policy |
| 對話、interrupt、run／command receipt、核准 authority state | LangGraph `AsyncPostgresSaver` | 員工核准才寫 approved 的 domain command |
| 跨回合 workspace、manifest、來源與 decision memory | LangGraph `AsyncPostgresStore` | namespace、薄 manifest 與 recovery policy；不另建 workspace table |
| Model／Tool 呼叫上限 | LangChain `ModelCallLimitMiddleware`／`ToolCallLimitMiddleware` | token、cost、elapsed、retry 與 VFS permission 的產品配置 |
| Schema／typed parsing | Pydantic 2 | Duty／Task／OPKS canonical resource 與 JD invariant |
| Human review lifecycle | Deep Agents workspace＋LangGraph persistence／command 提供機制 | semantic differ、dependency／atomic grouping、accept／edit-accept／reject／defer 語意 |
| Evidence | framework Tool／Store 承接讀取與保存 | 原話歸屬、來源更正、exact quote occurrence 與 deterministic anchor verifier |

沒有成熟通用框架能知道「一筆職務內容是否是合法 Task、某個 O／P／K／S 應依賴哪個 Task、哪些改動必須整組核准」，所以這些職務分析與員工 authority 規則仍是產品 domain；其餘 persistence、VFS、agent loop、middleware、typed parsing 與 run budgets 已交給成熟 primitive。

## 3. 產品 acceptance contract 對照

| 要求 | 結果與主要證據 |
|---|---|
| 一份 JD 一個跨回合 active workspace | `StoreBackend` 使用 document-scoped LangGraph Store；PostgreSQL restart／failure recovery tests 與兩輪 live smoke 通過 |
| 六個低階 editor Tools | 精確為 `ls`、`read_file`、`grep`、`write_file`、`edit_file`、`delete`；沒有 business Tool 或專用 split／merge |
| 一般 create／edit／delete 組成複合變更 | semantic differ 依 dependency／atomic subgroup 產生員工可理解的整組或獨立決策 |
| invalid 可續修但不可審／不可 export | manifest＋automatic validator fail closed；UI 只顯示修復狀態 |
| 員工是唯一 approved authority | exact review command、approved-first commit、command receipt 與 deterministic rebase |
| stale 與不重疊變更正確分流 | 重疊 action fail stale／conflicted；不重疊 group 可重新投影；defer／reject 以所選 action 的語意 fingerprint 延續 |
| 原話、更正、Evidence 不退化 | source lineage、speaker ownership、exact quote／occurrence verifier 與 source-correction tests 保留 |
| 焦點、背景、Gap、進度與按需 Skill 保留 | API projection 與 Web 顯示已把候選工作標為「待員工決定」，不冒充已核准進度 |
| 第一版範圍沒有膨脹 | hard-cut guard 對淘汰 app／RAG production import 為零；沒有 RAG／A／auto／multi-agent／Git UI |

## 4. Browser 與兩回合 Luna 實測

完整逐步紀錄在 [`2026-08-21-virtual-jd-workspace-live-smoke.md` §5](2026-08-21-virtual-jd-workspace-live-smoke.md#5-2026-08-23-持久工作草稿的兩輪-luna-browserapi-pass)。固定採購情境的結果：

- 第一回合：Luna／medium 共 4 model calls、10 Tool calls、47,273 total tokens、25,847 cache-read tokens、US$0.00850244；工作草稿形成 2 Duty、5 Task、14 OPKS，而 approved 仍未被 AI 自動改寫。
- 員工在真 Web UI 部分接受一組 Duty／Task、拒絕一個 OPKS、延後另一項；重新進頁面後決策與未決草稿仍存在。
- 第二回合：AI 記得既有採購工作與待決草稿，新增第六項工作並保留員工明確排除範圍；共 7 model calls、82,345 total tokens、35,267 cache-read tokens、US$0.01675639。結束時 approved 仍只有員工已接受的 1 Duty／1 Task／0 OPKS，工作草稿 0 diagnostics，23 pending＋1 deferred。
- UI 沒有暴露 raw JSON、VFS path、digest 或 Tool payload；重複控制項具有可區分 accessible name。

這只是窄機制 smoke，不是模型品質 eval，也不據此決定 production reasoning effort。成本顯示持久工作草稿本身沒有每輪自動 dump 全部文件，但 agent 修復與多 Tool step 仍需由既有 model／Tool／token／cost／elapsed ceilings 控制。

## 5. 施工中發現並修正的問題

1. 固定兩波 lookup 上限會在模型取得新 validation diagnostic 後誤擋合法修復。依 LangChain／Deep Agents 官方 production guidance 改由總 model／Tool budgets 控制，決策記於 ADR 0068；沒有把 2 換成另一個猜測數字。
2. 初版 browser projection 把候選工作顯示成「目前知道 0 項工作」。修正為從 Store-derived review 投影「待員工決定／員工延後」的真實 coverage 與 decision counts；approved authority 不變。
3. 初版 defer 綁整份 workspace digest，導致 AI 修改不相關內容時延後項目回到 pending。依 VS Code「被修改的檔案才清除已審狀態」與 Git non-overlapping merge 原則，改綁所選 action 的 canonical semantic fingerprint；重疊變更仍 fail stale。
4. 隔離 worktree 不會帶入 ignored `.env`；第一次 live 啟動在 provider call 前 fail closed，沒有 Opus call／費用。之後以啟動程序明確注入 Luna profile 與 secret，並以 durable attempt receipt 的 `actual_model`／`actual_provider` 驗證真實路由。
5. sandbox 阻擋外部 TCP 與 Vite 子程序曾造成 `transport_error`／`spawn EPERM`。兩者都以相同程式在允許網路／子程序的受控測試環境重跑；沒有把環境限制誤修成產品 workaround。
6. 最後獨立複審確認兩個真缺口：部分 reject 原先會隱藏整組而非只隱藏員工勾選的 action；direct edit 回應會帶 rebase 前的舊 workspace snapshot。兩者都先以 regression RED 重現，再分別改成 selected-action semantic fingerprint 投影與 rebase 後 fresh snapshot，scoped re-review 回報無新 Critical／Important。reviewer 另建議把 Duty／OPKS action 各自算成進度工作，複核後不採用：產品進度是 Task／工作範圍中心，相關 Duty／OPKS 已透過 Task depth 反映；另有 pending／deferred action count，若把 Header／Duty 當工作反而會灌水。
7. 關閉 live dev server 時，真 browser console 暴露多筆相同 employee-safe diagnostic 使用相同 React key。依 React 官方 sibling key 規則，先用真元件測試重現 warning，再以完整 `code／path／message` 加同內容 occurrence 形成 deterministic key；保留每筆診斷、不用 random、不新增 API identity。完整 Web `38 passed`，scoped Luna review 為 Critical／Important／Minor 全零。

上述做法主要依 [LangChain middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)、[Deep Agents production](https://docs.langchain.com/oss/python/deepagents/going-to-production)、[Deep Agents backends](https://docs.langchain.com/oss/python/deepagents/backends)、[LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)、[VS Code review agent edits](https://code.visualstudio.com/docs/agents/run/review-code-edits)、[Git merge](https://git-scm.com/docs/git-merge)、[OpenAI Apply Patch](https://developers.openai.com/api/docs/guides/tools-apply-patch)、[Anthropic checkpointing](https://code.claude.com/docs/en/checkpointing) 與 [React list keys](https://react.dev/learn/rendering-lists#keeping-list-items-in-order-with-key)；診斷與方案細節見研究稿及 ADR Sources。

## 6. Final Gate evidence

2026-08-23 在上述獨立複審修正後，於實際 worktree fresh run：

- 顧問 runtime／workspace／authority focused：`172 passed`。
- API 全套、真 PostgreSQL：`287 passed`。
- Web Vitest：`5 files／38 passed`；TypeScript `tsc --noEmit` 與 ESLint exit 0。
- contract codegen check exit 0。
- `npx turbo test`：5 tasks successful；API `258 passed／29 skipped`、Web `38 passed`、PDF `23 passed`、OCS indexer `53 passed`。
- `git diff --check` 無 whitespace error。
- hard-cut：淘汰 app 與隔離 RAG 對 current production import 為零；舊 lifecycle 唯一字串命中是 Web negative canary 明確斷言頁面不得出現 `/candidate/`，不是 production reference。

非功能 warning：Windows pytest cache path 無寫入權限；codegen 使用的 formatter 發出未來預設值變更警告。兩者都未改變測試或生成結果。

## 7. 已知界線

- 第一版只承諾本機單一操作者／單 process admission；若未來變成多 process 或多人，必須新增真正跨 process CAS／lease ADR。
- 只有一份 active workspace，不提供 branch、history、rewind 或 auto-accept。
- RAG／Reference、A、能力級別、正式 eval 平台留待產品核心完成後另行研究；RAG bounded context 仍與 current runtime 隔離。
- Luna live smoke 證明流程可用與成本可觀測，不代表已完成模型品質比較，也不把 `medium` 自動定為 production 最佳值。

## 8. 本機重跑

```text
cd apps/api
uv run pytest -q

cd ../..
npx turbo test
npm run check-codegen -w @caliburn/job-analysis-contract
npx tsc --noEmit -p apps/web/tsconfig.json
npm run lint -w @caliburn/web
git diff --check
```

需要 live model 時，依 [`docs/runbook.md`](../runbook.md) 從啟動程序注入 provider secret與明確 model profile；不得把 `.env` 複製進 worktree、commit 或輸出到 log。
