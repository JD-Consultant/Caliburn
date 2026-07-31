---
title: Task Analysis 引擎 — 端到端設計(durable PostgreSQL + consultant Web)
audience: agent-primary(也給人)
scope: apps/api job_analysis + job_analysis_postgres + job_analysis routes + apps/web workspace
updated: 2026-07-30
---

# Task Analysis 引擎 — 端到端設計

> **主讀者 = coding agent。** 目的:不看 code 也能改對這條線——不亂發明欄位、不把語意判斷
> 塞進 verifier、不把已退場的舊 AI 路徑接回來。**living:動到這條線的碼,同 commit 更新本檔。**
>
> 決策:[ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md)
> (決定 3 greenfield、決定 23–28 structured output)、
> [ADR 0042](../adr/0042-r1-screening-stop-and-a6-first-version-default.md)(A6 為第一版預設;
> 新增欄位須指出它避免的具體使用者失敗)、[ADR 0035](../adr/0035-interview-vnext-openrouter-first-provider-boundary.md)(OpenRouter-first)。
> 凍結形狀與判準:[`2026-07-28-task-boundary-merge-split-and-identity-research.md`](../specs/2026-07-28-task-boundary-merge-split-and-identity-research.md)
> **§4／§5(判準)、§9(Task)、§10(Proposal)、§11(Context)、§12(Result)**。
> 計畫:[`2026-07-28-task-analysis-core-implementation-plan.md`](../plans/2026-07-28-task-analysis-core-implementation-plan.md)、
> [`2026-07-29-job-analysis-postgresql-persistence-plan.md`](../plans/2026-07-29-job-analysis-postgresql-persistence-plan.md)。
> Current State authority 與 greenfield 儲存邊界見
> [ADR 0043](../adr/0043-job-analysis-local-current-state-persistence-and-authoring-authority.md)；
> 員工不完整 Task 的 identity 對齊見
> [ADR 0044](../adr/0044-partial-jd-task-reconciliation-and-human-confirmation.md)。
> Local Web transport 邊界見
> [ADR 0045](../adr/0045-job-analysis-local-web-contract-and-current-jd-editing.md)；
> 最小顧問回合與固定開場見
> [ADR 0046](../adr/0046-professional-consultant-minimal-durable-loop.md)。

## 1. 一句話

員工回一句話 → **assembler** 把現況投影成一份只用 ordinal 說話的 packet → **一次 HTTP** 打
OpenRouter 拿 `TaskAnalysisResult.v1` → **verifier**(純函式、零 LLM)擋掉所有確定性違規 →
**transition** 依 identity gate 決定「直接改 Work Model」還是「建立提案交給員工」→ 產出下一題。
**模型只提候選,application 是唯一寫入者,Proposal 只 gate Current JD。**

## 2. 組件(住哪 / 權力)

| 組件 | 是什麼 | 碼 | 權力 |
|---|---|---|---|
| domain | Task／SourceRef／SupportLink／open_issues／excluded_signals／Proposal 的凍結形狀 | `app/job_analysis/domain/` | 純 Pydantic,frozen;**非法狀態無法被表示**;只 import stdlib＋pydantic |
| llm 契約 | `TaskAnalysisResult.v1` ＋ portable provider schema ＋ Static Instructions | `app/job_analysis/llm/` | 只描述形狀與判準文字;**不做跨欄位驗證** |
| assembler | 現況 → `TaskAnalysisPacket` ＋ 決定性 rendering | `application/context.py` | 純函式;ordinal 的唯一產地 |
| verifier | §9.5／§12.3 的全部確定性規則 | `application/verifier.py` | 純函式;**只回報違規,不改任何東西** |
| operation | 組 packet → 呼叫 → parse → verifier | `application/operation.py` | 單一顯式流程;**不是 agent runner**,無 retry |
| provider | 最小 OpenRouter Chat adapter | `providers/openrouter.py` | 一次 HTTP;固定 `reasoning=high` 且不回傳 reasoning;成功內容必須由 response `model` 證明來自 exact configured model;typed 失敗;**只收 render 過的文字** |
| transition | 結果 → Work Model 變更 ＋ Proposal | `application/transition.py` | **唯一寫入者**;全有或全無 |
| persistence ports | Current State repositories／UoW／版本化 Journal payload | `application/persistence.py` | 純 Protocol 與 frozen contracts；不認 ORM／JSON row |
| PostgreSQL adapter | 0012 四表＋0013 Journal kind、serialization、repositories、UoW | `app/adapters/job_analysis_postgres/` | JSONB 讀取必須 hydrate；schema/shape 壞掉 fail-closed；repository 不 commit |
| authority commit seam | 完整 Current State → 同一 UoW 原子寫入 | `application/authority_commit.py` | 先重驗完整 `JobAnalysisState`，再 replace JD／Proposal、選擇性寫 Journal、generation CAS、單次 commit |
| authoring use cases | 文件庫與 JD Task add/edit/delete/reorder | `application/authoring.py` | document row lock → entry replay check → Current State/Journal/generation 同交易；不呼叫 LLM |
| consultation use case | provider 前 replay → authority snapshot → 交易外模型呼叫 → verified commit | `application/consultation.py`、`application/durable_turn.py` | 已提交的同 key／同回答零 provider call；commit 時重鎖並比對 generation/read-set；Work Model、Proposal、下一題與 completed-turn Journal 同交易 |
| Proposal use cases | 候選送審 + accept/edit/reject/defer/revision request | `application/proposal_decisions.py` | `propose_task_for_jd()` 不自動接受；決策由 document lock 序列化；接受類才改 JD；決策寫 Journal |
| Local Web API | 本機文件、Current JD 與 Consultation routes | `app/api/routes/job_analysis.py` | 只做 generated wire DTO mapping；不暴露 Work Model、Journal、generation 或 provider detail；turn／Proposal decision 直接呼叫 greenfield application use cases |
| Local Web UI | 文件庫、顧問訪談、Proposal 審查與單一開啟文件的 Task editor | `apps/web/src/app/workspace/`、`components/workspace/` | generated TS DTO + TanStack Query；conversation／Proposal／Current JD 同頁，一份本地編輯草稿、明確儲存，不用 Server Action／autosave／第二份 document store |

## 3. 一輪的資料流(每步標函式)

1. `build_context_packet(transcript=…, current_turn_id=…, work_model=…, current_jd=…, active_question=…, proposals=…)`
   → `TaskAnalysisPacket`。順序完全跟隨輸入,所以同輸入同輸出。
2. `run_task_analysis_operation(packet=…, adapter=…)`:
   - `render_context_packet(packet)` → 純文字,當成 user message;
   - `TASK_ANALYSIS_INSTRUCTIONS` 當成 system message;
   - `task_analysis_result_provider_schema()` 當成 `response_format.json_schema.schema`;
   - `adapter.complete(...)` → **一次** `POST https://openrouter.ai/api/v1/chat/completions`;
   - `TaskAnalysisResult.model_validate_json(text)` → `verify_task_analysis_result(...)`。
3. `apply_task_analysis_result(state=…, packet=…, result=…, operation_id=…)` → `TransitionResult`。

員工直接編輯走另一條短路徑：`add_jd_task`／`edit_jd_task`／`delete_jd_task`／
`reorder_jd_tasks` 先鎖 document，以 Journal `entry_id` 做 replay/conflict 判定，同交易保存
Current JD、相關 Proposal stale、Work Model reconcile trigger、Journal 與 generation。**按儲存不呼叫 LLM**；
它與 Proposal use cases 各自完成入口規則與狀態推導後，共用
`commit_authority_change()` 做完整狀態驗證與最終寫入。Durable AI turn 不走這個 seam：
`apply_task_analysis_result()` 已驗證新狀態，且 durable turn 另有 provider-outside-transaction 與
snapshot revalidation 語意。

本機 Web 文件入口走 `GET /api/v1/job-analysis/documents`、
`PUT /api/v1/job-analysis/documents/{document_id}` 與
`GET /api/v1/job-analysis/documents/{document_id}`。標題只是 metadata：同 ID 的 PUT 可建立或改名，
但不走 authority seam、不寫 Journal、也不 bump `authority_generation`。新路徑的錯誤使用
RFC 9457 `application/problem+json`；path-scoped handler 會把舊 routes 的既有錯誤 body 原樣保留。
Current JD Task 的 POST／PUT／DELETE 與排序 PUT 都要求 `Idempotency-Key`，原樣映射成
Journal `entry_id`；沒有 middleware、隱藏 retry 或第二套寫入邏輯。員工清空 optional text 時，
wire mapper 先 trim 並轉成 `null`；必填 statement 變空則回 `invalid-request`，不讓半成品進 domain。
Web 的 `/workspace` 用 `DocumentLibrary` 列出／建立／改名；`/workspace/[document_id]` 用
`ConsultationWorkspace` 同頁組合 `ConsultationPanel`、Proposal cards 與 `TaskEditor`，一次只開一份文件。
顧問讀寫只走 `GET …/consultation`、`POST …/turns` 與 `POST …/proposals/{id}/decisions`；成功回應同步更新
Consultation／Document query，人工 Task 編輯仍走同一組 Current JD routes，不另建 AI document store。
Task form 的 draft 只在編輯期間存在；成功後 invalidate 文件、Consultation 與文件庫 query 並回讀 PostgreSQL 現況。相同失敗操作、相同 payload 的人工重送沿用原
`Idempotency-Key`；未改內容禁止儲存，避免製造空 Journal 與無關 generation bump。
新 document 建立時，`put_document_metadata()` 在同一個 UoW 建立固定 consultant opening
Journal entry 並設為 `active_question`；不呼叫模型、不另建 chat table。rename 與 metadata replay
不重複開場。`JournalRepository.list_conversation_turns()` 依 `journal_sequence` 將 opening 展開成
一個 consultant turn，並將每個 completed-turn payload 展開成 employee＋consultant；這份 lossless
transcript 同時供下一輪 packet 與之後的 Consultation View 使用。
one-stage prompt 不把訪談寫成固定問卷：先理解職位的服務對象與目的，每段完整回答可辨識
0..N 個工作訊號；故事仍有資訊時可深挖，故事結束後回到例行、週期與例外責任。下一題優先處理
會改變 Task 邊界的矛盾／責任問題，再處理 open issue 與遺漏掃描。pending／deferred Proposal
只是待決假說，不會凍結訪談；第一版沒有完成 gate，模型不得宣稱訪談或 JD 已完成。這些是
scripted smoke 保護的顧問行為基線，不代表模型品質已通過。
既有 Task 在下一次 AI 互動時看到 JD/Work Model 差異；JD-only Task 先落一筆
`insufficient_evidence` open issue，明確保存該 JD `task_id`，不補造空殼 Work Model Task。
下一輪 packet 只把它投影成可追問的 partial Task：

- `no_match + add` 才能以同一 `task_id` materialize Work Model Task；
- `exclude` 只建立員工可見的 JD-only withdraw Proposal，不靜默移除文件；
- `duplicate`／`overlap`／`uncertain` 保留 issue 並追問，不以文字相似度猜 identity；
- next question 指向該 issue 時，同一 transition 保存 `last_asked_turn_id`，reload 後可續問。

持久 AI 回合由 `submit_employee_turn()` 先以 `operation_id` 查 Journal：已提交且回答相同就直接
返回，回答不同則 `IdempotencyConflict`；只有尚未提交才依序呼叫 `prepare_turn()` →
`run_task_analysis_operation()` → `commit_verified_turn()`。第一步讀完即關閉交易，LLM I/O
期間不持有 PostgreSQL lock；最後一步才重鎖 document。generation、packet read-set 或
conversation authority 任一不一致就回 `StaleAuthoritySnapshot`，舊結果不得套用。
相同 `operation_id` 的已提交回合不會再打 provider，也不會新增 Task／Proposal／Journal。
兩個同時飛行中的相同 request 尚未合併；這是單機第一版的明示限制，不得稱為 exactly-once。
模型輸出 `task_change.add` 表示該訊號已通過 Task 成立判準：transition 先建立 Work Model 候選，
並在同一結果中建立 pending `add` Proposal。候選仍不是 Current JD；只有員工 accept／edit 後才進文件。
若只建立不可見候選而沒有 Proposal，Consultation View 又不暴露 Work Model，員工就永遠無法審查 AI 找到的工作。

Proposal 決策由 `decide_proposal()` 完成，沒有 LLM。`accepted` 套用 `jd_after`；
`edited` 套用員工文字並標記後續 reconcile；`rejected`、`deferred`、
`revision_requested` 不改 Current JD。merge／split／JD 內 withdraw 的
`staged_work_model_delta` 只在 accepted／edited 時與 JD 同交易套用。`jd_before`
已不等於 Current JD 時，提案轉為員工可見的 `stale`，舊內容不得硬套。
JD-only withdraw 可以沒有 staged delta；決策端在 document lock 內以目前 Work Model 重驗：
target 後來出現未退休 Task 或已被較新 retirement 取代時，一律轉 `stale`。接受移除 JD Task
時，同交易清除指向該 Task 的 reconciliation issue，避免 reload 後繼續追問已不存在的內容。
Task Analysis 的 `add` 建立 Work Model 候選，並在同一 transition 建立 pending `add` Proposal；
它不替員工接受或直接寫入 JD。`propose_task_for_jd()` 仍是非顧問流程把既有候選送審的顯式 bridge，
Consultation turn 不再重複呼叫它。

`OperationOutcome` 五種結局,呼叫端照名字處置:

| 結局 | 意思 | 該怎麼辦 |
|---|---|---|
| `verified` | 通過 verifier | 交給 transition |
| `rejected` | parse 得出來但違反確定性規則 | 不得套用;`report.violations` 有逐條理由 |
| `invalid_output` | 不是合法的 `TaskAnalysisResult.v1` JSON | 重組 context 再來,不是 retry 同一份 |
| `refused` | 模型拒答 | **不是錯誤,也不可重試** |
| `failed` | timeout／連線／非 200／provider error／截斷／response model 不符 | 依 `detail` 的 kind 決定；`truncated` 要調 `max_tokens`，`model_mismatch` 不得拿來判斷產品品質 |

## 4. ordinal 與 ID:誰認得誰

- **模型永遠不產生 ID**,只用 packet 給的 ordinal 與本次輸出內的位置索引。
- ordinal **每輪重新編號**,mapping 只住 `application/context.py`,**不進 domain**——domain 的 Task 只認 `task_id`。
- active task ordinal `1..N`;**retired task ordinal `N+1..N+M`**,兩組不相交。
  不相交是為了讓「retired 不得被指涉」可判定:共用整數的話,`target_task_ordinals: [2]` 永遠先命中
  active #2,規則等於不存在。
- support link ordinal 是 **task-local** 的 `1..k`,模型靠它指認「哪一句依據被更正」。
- rendering **只用 ordinal 說話**:`task_id`／`turn_id`／`issue_id` 都不會出現在送給 provider 的文字裡。

## 5. 不變量住在哪一層(改規則前先確認要改哪一層)

| 層 | 規則 | 例子 |
|---|---|---|
| domain 型別 | 形狀不變量,**非法狀態無法被建構** | `active` Task 至少一條有效 SupportLink;`withdrawn` 必有 reason;lineage 不成環;staged delta 的 ID 不重複且欄位必須符合 action;Current JD／Proposal ID 不重複且 JD 投影順序 canonical;§10.5 的 `edited_jd_after` 四條硬規則 |
| verifier | 需要 packet 才判斷得出的規則 | quote 必須是該員工回合的逐字子字串;ordinal 在範圍內;`no_match` 不得帶 target;merge ≥2;split child 只能沿用母 Task 的有效 support ordinal;withdraw 不得帶 `task_fields` 但必須帶 `withdraw_reason`;同一 target 被兩筆 `task_change` 指涉或兩筆 signal 逐欄完全相同 → **明確拒絕**;supersession 必須指向仍有效且被同一筆 signal 指涉的 support link |
| transition | 需要 state 才判斷得出的規則 | identity gate;§9.5 三出口;Task／Proposal 的決定性 ID 採 insert-only,撞到不同內容即拒絕;retirement 來源只能取自該 signal 實際引用的 anchor;§10.8 stale disposition |
| **不在任何一層** | 語意判斷 | purpose 是否相同、該不該 merge／split、outcome 是否可理解、enabler 分類是否正確——**歸 rubric 與員工審核**(§9.5 末段) |

## 6. Identity gate:什麼時候可以直接改 Work Model

閘門是 `topology_affected_existing_ids ∩ current_jd_task_ids`,**不是動作類型**。

| 情境 | Work Model | Proposal |
|---|---|---|
| `add` 候選 | 立即建立候選 ID | 顧問回合在同一結果建立 pending add Proposal；員工接受／修改後接受才進 JD |
| 同 ID `revise` | 立即更新 | 只有 JD 文字也要改時才建立 |
| `withdraw`,target 不在 JD | 立即 retire | 不建立 |
| `withdraw`,target 在 JD | 暫不 retire,設 `pending_reconciliation` | 建立 |
| `merge`,成員全不在 JD | 立即 merge | 不建立 |
| `merge`,任一成員在 JD | 暫不套用 topology | 建立(帶 staged delta) |
| `split`,母 Task 不在 JD | 立即 split | 不建立 |
| `split`,母 Task 在 JD | 暫不套用 topology | 建立(帶 staged delta) |

Merge 的新 Task 保留所有 member 的有效 SupportLink並加入本輪來源；split child 只繼承模型
以 `inherited_support_ordinals` 明確選取的母 Task 來源，再加入本輪來源。跨 JD 的 staged
新 Task 保存同一組 application-built SupportLink，接受時不重新猜測 provenance。

同一輪可以同時包含立即套用與 Proposal。**`apply_task_analysis_result` 永遠不動 `current_jd`**:
JD 只在員工決定提案時才改。

## 7. 不變量與禁令(code 讀不出來的)

- **一次 operation ＝ 一次 HTTP。** 沒有 fallback、沒有隱藏 retry、沒有 provider registry。
  `provider_order` 恰好一個 slug:OpenRouter 的 `order` 會依序嘗試清單內的 provider,
  `allow_fallbacks: false` 只擋清單外的。
- **A6 treatment 不可靜默漂移。** request 固定送
  `reasoning: {effort: high, exclude: true}`；有成功 content 時，response `model` 缺失或不等於
  configured exact model 一律 `model_mismatch`，不 parse、不 retry。
- **provider 只收 `render_context_packet()` 的文字。** `adapter.complete()` 的簽章收不到 packet 模型
  ——不要為了方便加一個吃 model_dump 的多載,那等於把內部 ID 送出去。
- **不做全文 UUID 形狀掃描**(§12.3):輸出契約沒有可填 ID 的欄位,而員工原話可能合法含有
  request／correlation UUID,掃描只會誤殺。
- **全有或全無。** transition 中途用 `model_copy(update=…)` 疊改(不驗證),收尾逐筆
  `Task.model_validate(...)`;§9.5 的三出口在那裡執行,任何一條不變量不成立就整筆拒絕、state 原封不動。
- **精確重複才由程式拒絕。** 逐欄完全相同的 `work_signals[]` 是確定性錯誤；近似文字、
  同義改寫與 Task 邊界仍是語意問題，不做相似度服務或工具字典。
- **新分析不能讓舊提案無聲留下。** 同一 Task 已被本輪實質重新分析、但沒有 replacement 時，
  仍將重疊的 pending／deferred Proposal 標成 stale，並保存員工看得到的理由。
- **greenfield 邊界。** `app/job_analysis` **不得 import** `app.interview`、`app.interview_vnext`、
  `app.job_authoring`、`evals`,也不得 import DB／web 框架。由
  `tests/test_job_analysis_dependencies.py` 以 AST 強制。
- **smoke 綠燈不代表模型品質通過。** `tests/test_job_analysis_smoke.py` 用 scripted provider；
  `tests/test_job_analysis_durable_smoke.py` 用 fake verified result 與真 PostgreSQL，只證明交易／reload vertical。
  `tests/test_job_analysis_api_postgres.py` 再以真 PostgreSQL 和實際 FastAPI route 驗證本機 Web 的文件／Task
  mutation、排序、reload 與 metadata rename 邊界；它仍不代表瀏覽器 UX 或模型品質通過。
  依 ADR 0042 決定 3,R1 exit gate 判準未被否決、只是暫停阻擋效力;**任何文件都不得把它寫成
  Task Discovery 已通過**。
- **第一版不是固定問卷或完成判定器。** 固定的只有開場與權力邊界；模型每輪可辨識 0..N 個訊號並只選
  一個最高價值問題。現在沒有 completion gate、Role/Coverage entity、planner、第二模型呼叫、Graph runtime
  或 background workflow；不得因 UI 已閉環就宣稱完整職務分析已完成。

## 8. 現在還沒有的(別假設它存在)

| 沒有的東西 | 現況 | 什麼時候做 |
|---|---|---|
| endpoint variant preflight | `provider_order` 只鎖 base slug,同 provider 可能有多個 endpoint variant。`providers/openrouter_evidence.py` 的 `select_catalog_endpoint()` 已能從 model detail 選出唯一 active endpoint,但**沒有任何 runtime 路徑呼叫它** | 由待建的 live smoke wrapper 在付費前呼叫;不進 request 路徑 |
| route 歸因 | `inspect_openrouter_execution()` 可解析 router metadata、pipeline 與 `usage.cost`,並判定該次能否用於品質歸因。**一般產品回合不要求也不送 metadata**;`OpenRouterAdapter` 的 headers 未改,結果不寫 PostgreSQL／Journal | metadata／no-cache opt-in 只留給待建的 smoke wrapper |
| 真模型跑通的證據 | 上述兩個 parser 都只在離線 fixture 下驗過。**尚未對 Opus 5／Anthropic route 送過任何真實請求**,因此沒有 endpoint catalog 實測值,也沒有任何 prompt 品質結論 | 由 attributed live smoke 產生後,才把結論寫進 `docs/experiments/` 與本表 |
| prompt 品質調校 | `llm/prompt.py` 已有 Task 判準與彈性顧問行為基線，但尚未用真實員工資料調校 | 有真實使用摩擦後以 rubric／eval 調整，不先加 planner 或第二次呼叫 |
| duplicate／overlap identity 自動收斂 | 第一版刻意不做；模型保留 issue 並追問員工 | 有真實重複摩擦證據後再研究，不用相似度猜測 |
| O/P/K/S/A、完整 header、匯出 | 目前只做 Task 與較豐富的內部 JD Task 欄位 | 各自研究／契約完成後逐項加；匯出才對齊公版 |
| revision-request replacement | revision request 可保存／reload，但不會自動重建 replacement | 後續模型流程 |
| 一般瀏覽器完整跨埠 smoke | Next UI shell 已實際載入；本次 Codex in-app browser 的 client policy 封鎖 `localhost:8001`，故無法在該瀏覽器完成 API round-trip。Web 90 tests／tsc／lint／build 與真 PostgreSQL API vertical 已通過 | 用一般本機瀏覽器確認即可；不為測試環境加入 proxy、fake production mode 或 E2E framework |

## 9. 指路

- 判準與凍結形狀:[研究稿 §4／§5／§9–§12](../specs/2026-07-28-task-boundary-merge-split-and-identity-research.md)
- 決策:[ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md)、
  [ADR 0042](../adr/0042-r1-screening-stop-and-a6-first-version-default.md)
- 實作步驟:[T1–T7 計畫](../plans/2026-07-28-task-analysis-core-implementation-plan.md)
- durable vertical:
  [`PostgreSQL persistence plan`](../plans/2026-07-29-job-analysis-postgresql-persistence-plan.md)
- partial Task reconciliation:
  [`ADR 0044`](../adr/0044-partial-jd-task-reconciliation-and-human-confirmation.md)、
  [`implementation plan`](../plans/2026-07-30-job-analysis-partial-task-reconciliation-plan.md)
- Local Web first slice:
  [`ADR 0045`](../adr/0045-job-analysis-local-web-contract-and-shared-authority-commit.md)、
  [`implementation plan`](../plans/2026-07-30-job-analysis-local-web-first-slice-plan.md)
- 舊路徑(**已退場,勿救回**):[`interview-engine.md`](interview-engine.md)、
  [ADR 0030](../adr/0030-ai-coedit-tracked-changes-one-brain.md)
