# Hybrid Candidate Document Edit Loop 完成報告

- 完成日期：2026-08-21
- 分支：`refactor/langgraph-consultant-runtime`
- Worktree：`S:\caliburn\.worktrees\langgraph-consultant-runtime`
- 本地 tag：`consultant-hybrid-candidate-edit-v1`
- 狀態：實作、真模型 smoke、完整 gates與獨立審核均完成；未 push、未 merge、worktree保留
- 決策：ADR 0063（Accepted）

> 不在本文件硬寫會隨修正輪次失效的 HEAD SHA或 commit總數。請以 `git rev-parse consultant-hybrid-candidate-edit-v1^{}` 與 `git log --oneline caca54f..consultant-hybrid-candidate-edit-v1` 取得最後事實。

## 1. 交付結果

現行顧問已從「模型在 final Structured Output 一次重送完整 Duty／Task／OPKS 草稿」切換為：

```text
員工原話／核准 JD／決策記憶
          ↓ 最小充分 Context＋按需 Skills
LangChain 單一顧問 agent
          ↓
job_document_candidate_edit（隔離候選、真實套用與驗證）
          ↓ Tool result：applied／rejected＋actionable issues
模型必要時修正完整 batch
          ↓
provider-native final Structured Output
只發布 latest revision／digest／完整 action handles
          ↓
LangGraph semantic commit → review queue（仍非核准）
          ↓
員工 accept／edit-accept／reject／defer 或 direct edit
          ↓
唯一核准 JD authority
```

模型沒有任何 approved-document write edge；候選成功、final publication成功都不等於員工接受。只有員工 command 能改核准 JD。

## 2. 成熟框架承接了什麼

| 目的 | 成熟元件 | Caliburn保留的薄政策 |
|---|---|---|
| model→Tool→result→model loop | LangChain `create_agent`／ToolNode | 候選 Tool 的 JD scope與語意 |
| runtime注入與call identity | LangChain `ToolRuntime[Any, Any]` | application注入 document／run／baseline；模型不可自填 |
| final typed publication | LangChain `ProviderStrategy`＋Pydantic | revision／digest／完整 ordered action set的產品規則 |
| durable candidate／fault recovery | LangGraph typed state＋PostgreSQL Saver | candidate run scope、stale baseline與完整 replacement batch |
| 員工原話與跨turn記憶 | LangGraph Store＋checkpoint | exact text、更正lineage、document scope、quote support |
| 最小充分Context | LangChain middleware＋deterministic projection | approved／pending／decision／source slice選擇與token budget |
| 按需Task／Duty／OPKS方法 | Deep Agents `SkillsMiddleware`＋唯讀`read_file` | 本專案研究驗證過的分析方法內容 |
| retry／calls／token／cost／time | LangChain built-in middleware＋callbacks＋OpenTelemetry | profile數值、no-silent-fallback與fail-closed receipt |
| 必要澄清與resume | LangGraph `interrupt()`／`Command(resume=...)` | 哪些衝突必須先問員工 |

沒有再建立第二套 agent loop、memory store、checkpoint engine、candidate table、JSON Patch engine、專用 split／merge Tool或 auto-accept workflow。

## 3. Model-facing surface

正式 surface 恰好五個 Tool：

1. `read_file`：按需讀取允許的專業 Skill；
2. `employee_source_get`：以stable ID取得同文件員工原話；
3. `employee_source_lineage`：取得更正 lineage；
4. `employee_source_search`：同文件範圍找回相關舊原話；
5. `job_document_candidate_edit`：提交一個strict typed完整 replacement batch。

候選 operation只有：

- `ADD`
- `REVISE`
- `WITHDRAW`
- `REASSIGN`
- `REORDER`

Task／Duty的拆分與合併由一般 operation＋dependency＋atomic subgroup組合；例如過大 Task 是新增替代 Tasks、撤回舊 Task、重接 Duty／OPKS，而不是新增專用 `split_task`／`merge_duty`權限。

## 4. 重要實作結果

- final schema不再攜帶完整文件草稿，只引用最新候選 receipt；未知revision、digest mismatch、subset／reorder／duplicate handles、另一run candidate與stale baseline皆fail closed。
- candidate Tool可引用同一batch local refs；正式UUID、排序、document ID與baseline由application配置。
- 同一tool-call ID＋同payload可安全 replay；換payload、source更正、stale candidate與非法linkage會被拒絕且不改state。
- pending／deferred overlay與rejected／stale／edit-accepted history明示 `approved=false`，不會混入approved slice。
- 員工接受九項、拒絕一個O後，下一輪能看見九項核准結果與拒絕記憶；被拒絕O不會復活。
- candidate staging不增加deterministic progress；publication只增加待審decision，accept／edit-accept後才影響核准coverage。
- `active_candidate`只在raw product checkpoint與matching same-run context使用，不出現在一般snapshot／API／export。
- API mapper明確投影review DTO，不把internal supersession／external dependency metadata直接塞進generated transport contract。

## 5. 產品北極星回歸

| 大方向 | 結果 |
|---|---|
| 一位專業職務說明書顧問 | 保持；Task／Duty／OPKS是Skills，不是多個agent人格 |
| 先大致理解，再以明確焦點深入 | 保持；前景focus與背景signal吸收可同時存在 |
| Task／Duty／OPKS隨訪談動態調整 | 保持；通用typed batch可跨實體重組 |
| LLM不能偷偷改文件 | 通過；candidate／publication都不是approved write |
| 員工接受／修改接受／拒絕／延後 | 通過；employee command是唯一authority |
| 記得員工以前說過的話 | 通過；Store保留exact source與correction lineage，Context按需找回 |
| 必要衝突先問員工 | 保持；typed clarification走LangGraph durable interrupt |
| Gap與進度可見且可信 | 保持；由durable state確定性投影，不信任模型自評百分比 |
| 員工可關閉、日後自然續談 | 保持；沒有新增「本輪可停」或wizard終止狀態 |
| 單一匯出且可強制 | 未改動；不被候選workspace影響 |

結果：**未發現偏離**。

## 6. 真實 GPT-5.6 Luna smoke

完整證據見 [`2026-08-15-hybrid-candidate-loop-live-smoke.md`](2026-08-15-hybrid-candidate-loop-live-smoke.md)。最終 `medium／8192` run：

- 第一輪三個Skill read＋一次candidate edit；Tool第一次即`applied`；
- revision 1、digest與三個action handles和review queue完全一致；
- 員工接受Task＋Indicator、拒絕Output；核准JD只出現接受項；
- 第二輪同時檢出approved context與rejected memory，未呼叫candidate Tool，核准JD不變；
- requested／actual model皆為`openai/gpt-5.6-luna`，actual provider皆為OpenAI；
- 5 attempts、43,023 tokens、41.483秒、USD 0.01162862；
- disposable資料精確清理，五張相關表前後都是0。

`max／16384`會在目前五步上限內失敗，因此沒有升高budget硬讓它通過；互動基線保留medium，正式模型品質比較延後到產品核心完成後。

## 7. 驗證結果

| Gate | Fresh結果 |
|---|---|
| 候選／agent focused，warnings as errors | `56 passed` |
| API完整pytest＋PostgreSQL | `265 passed` |
| Web Vitest | `27 passed` |
| Web TypeScript | clean |
| Web ESLint | clean |
| Contract codegen | clean；只有datamodel-code-generator已知FutureWarning |
| Turbo monorepo | `5 successful / 5 total` |
| `git diff --check` | clean |
| 相關DB tables | `0 / 0 / 0 / 0 / 0` |

第一次Turbo沒有注入`TEST_DATABASE_URL`，四個DB canary依設計主動fail；明確注入本機測試DB後原命令全綠。沒有把缺環境變數寫成產品修復，也沒有弱化canary。

## 8. 獨立審核

最後只讀 reviewer 依ADR 0063、完整branch diff、四個product canary、authority邊界、五Tool surface與no-RAG／no-A範圍執行：

- Critical：0；
- Important：0；
- Assessment：Ready to merge = **Yes**；
- reviewer確認candidate staging／publication／employee decision邊界、真LangChain ToolNode＋LangGraph／PostgreSQL canary，以及API explicit projection均成立。

唯一Minor是「完成報告不存在」。主審核對後確認該檔已在同一路徑建立，只是它在reviewer啟動後才成為未追蹤工作檔，因此review snapshot沒有看到；不建立第二份報告，也不把這項誤判當production finding。

## 9. 明確延後

- RAG／Reference consumer與檢索品質；
- 能力級別與A的研究、Skill與模型生成；
- auto-accept；
- product multi-agent；
- 正式eval平台與Luna／Terra／Sol／其他provider代表性比較；
- 非產品核心的額外observability／dashboard。

這些都沒有偷偷進production composition root。

## 10. 本機重跑

```powershell
cd S:\caliburn\.worktrees\langgraph-consultant-runtime\apps\api
$env:DEBUG='false'
$env:TEST_DATABASE_URL='postgresql+asyncpg://postgres:password@localhost:5432/caliburn'
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-reviewed'
uv run pytest -q

cd ..\web
npm run test
npx tsc --noEmit
npm run lint

cd ..\..
npm run check-codegen -w @caliburn/job-analysis-contract
npx turbo test --env-mode=loose --output-logs=errors-only --force
git diff --check
git status --short
```

真API runner位於ignored的`.superpowers/sdd/`，需要owner本機key且只應對disposable文件執行；API key不得寫進Git或完成報告。

## 11. 交付邊界

- 不push；
- 不開PR；
- 不merge；
- 不刪worktree或feature branch；
- `docs/adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md`保留進場前的line-ending-only working-tree stat，不納入任何commit。
