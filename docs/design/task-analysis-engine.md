---
title: Task Analysis 引擎 — 端到端設計(第一條 vertical＋PostgreSQL adapter,無 route)
audience: agent-primary(也給人)
scope: apps/api app/job_analysis/*(domain / llm / application / providers)
updated: 2026-07-29
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
> [ADR 0043](../adr/0043-job-analysis-local-current-state-persistence-and-authoring-authority.md)。

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
| PostgreSQL adapter | 0012 四表、serialization、repositories、UoW | `app/adapters/job_analysis_postgres/` | JSONB 讀取必須 hydrate；schema/shape 壞掉 fail-closed；repository 不 commit |
| authoring use cases | 文件庫與 JD Task add/edit/delete/reorder | `application/authoring.py` | document row lock → entry replay check → Current State/Journal/generation 同交易；不呼叫 LLM |
| durable turn | authority snapshot → 交易外模型呼叫 → verified commit | `application/durable_turn.py` | commit 時重鎖並比對 generation/read-set；Work Model、Proposal、下一題與 completed-turn Journal 同交易 |
| Proposal use cases | 候選送審 + accept/edit/reject/defer/revision request | `application/proposal_decisions.py` | `propose_task_for_jd()` 不自動接受；決策由 document lock 序列化；接受類才改 JD；決策寫 Journal |

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
既有 Task 在下一次 AI 互動時看到 JD/Work Model 差異，JD-only Task 先落一筆可追問的 open issue。

持久 AI 回合由 composition 依序呼叫 `prepare_turn()` →
`run_task_analysis_operation()` → `commit_verified_turn()`。第一步讀完即關閉交易，LLM I/O
期間不持有 PostgreSQL lock；最後一步才重鎖 document。generation、packet read-set 或
conversation authority 任一不一致就回 `StaleAuthoritySnapshot`，舊結果不得套用。
相同 `operation_id` 的已提交回合只回傳目前狀態，不會再新增 Task／Proposal／Journal。

Proposal 決策由 `decide_proposal()` 完成，沒有 LLM。`accepted` 套用 `jd_after`；
`edited` 套用員工文字並標記後續 reconcile；`rejected`、`deferred`、
`revision_requested` 不改 Current JD。merge／split／JD 內 withdraw 的
`staged_work_model_delta` 只在 accepted／edited 時與 JD 同交易套用。`jd_before`
已不等於 Current JD 時，提案轉為員工可見的 `stale`，舊內容不得硬套。
Task Analysis 的 `add` 只建立 Work Model 候選；`propose_task_for_jd()` 是把一個已穩定候選
送給員工審核的顯式 bridge。它不每輪自動製造提案，也不替員工接受。

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
| `add` 候選 | 立即建立候選 ID | 不建立(要進 JD 是後續的事) |
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
- **smoke 綠燈不代表模型品質通過。** `tests/test_job_analysis_smoke.py` 用 scripted provider。
  依 ADR 0042 決定 3,R1 exit gate 判準未被否決、只是暫停阻擋效力;**任何文件都不得把它寫成
  Task Discovery 已通過**。

## 8. 現在還沒有的(別假設它存在)

| 沒有的東西 | 現況 | 什麼時候做 |
|---|---|---|
| route／Web UI | 完全沒有 | persistence 之後的最小 local Web |
| endpoint variant preflight | `provider_order` 只鎖 base slug,同 provider 可能有多個 endpoint variant | 真正付費呼叫前的 catalog／live preflight |
| prompt 品質調校 | `llm/prompt.py` 只寫到「不與 §4 判準相反」的結構最小集 | rubric／eval 的獨立工作 |
| 員工決定提案的流程 | Proposal 建得出來、可持久化，但尚無套用決定的 use case | persistence plan Task 7 |

## 9. 指路

- 判準與凍結形狀:[研究稿 §4／§5／§9–§12](../specs/2026-07-28-task-boundary-merge-split-and-identity-research.md)
- 決策:[ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md)、
  [ADR 0042](../adr/0042-r1-screening-stop-and-a6-first-version-default.md)
- 實作步驟:[T1–T7 計畫](../plans/2026-07-28-task-analysis-core-implementation-plan.md)
- durable vertical:
  [`PostgreSQL persistence plan`](../plans/2026-07-29-job-analysis-postgresql-persistence-plan.md)
- 舊路徑(**已退場,勿救回**):[`interview-engine.md`](interview-engine.md)、
  [ADR 0030](../adr/0030-ai-coedit-tracked-changes-one-brain.md)
