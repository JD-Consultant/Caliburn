---
title: Task Analysis 引擎 — 端到端設計(durable PostgreSQL + consultant Web)
audience: agent-primary(也給人)
scope: apps/api job_analysis + job_analysis_postgres + job_analysis routes + apps/web workspace
updated: 2026-08-09
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
> [ADR 0045](../adr/0045-job-analysis-local-web-contract-and-shared-authority-commit.md)；
> 最小顧問回合與固定開場見
> [ADR 0046](../adr/0046-professional-consultant-minimal-durable-loop.md)。OPKS 必須一起讀
> [ADR 0048](../adr/0048-opks-evidence-axes-and-document-level-competencies.md)～
> [ADR 0051](../adr/0051-opks-proposal-status-machine-and-stable-entity-id.md)。

## 1. 一句話

員工回一句話 → **assembler** 把現況投影成一份只用 ordinal 說話的 packet → **一次 HTTP** 打
OpenRouter 拿 `task_analysis_result_v3`(送出去的精簡形狀)→ **mapper** 還原成內部的
`TaskAnalysisResult` → **verifier**(純函式、零 LLM)擋掉所有確定性違規 →
**transition** 依 identity gate 決定「直接改 Work Model」還是「建立提案交給員工」→ 產出下一題。
**模型只提候選,application 是唯一寫入者,Proposal 只 gate Current JD。**

## 2. 組件(住哪 / 權力)

| 組件 | 是什麼 | 碼 | 權力 |
|---|---|---|---|
| domain | Task／SourceRef／SupportLink／open_issues／excluded_signals／Task Proposal，以及 OPKS 的 `OpksItem`／`CurrentJdOpks`／獨立 `OpksProposal` 凍結形狀 | `app/job_analysis/domain/`（OPKS：`opks.py`、`opks_proposal.py`） | 純 Pydantic,frozen;**非法狀態無法被表示**;只 import stdlib＋pydantic。OPKS 已進完整 authority state、人工編輯、Proposal 決策 API 與 Web editor |
| JD header | `JdHeader`：iCAP 版型表頭語意欄位（職能基準名稱／所屬類別／工作描述／nullable 基準級別 1–6／說明補充） | `app/job_analysis/domain/jd_header.py` | 純 Pydantic,frozen;全欄位 nullable,空字串拒收(要 `null` 不要 `""`);**沒有 `職能基準代碼`／`職類別代碼` 欄位**(iCAP 配發,不生成)。Task 1–4 已落地：`put_jd_header()` 經 authority seam、typed before/after Journal receipt 與 `PUT /{document_id}/jd-header` 接通；Task Analysis packet 只投影職能基準名稱與工作描述為「員工填寫的整體描述」背景、納入 read-set，且只有該背景存在時才在相鄰處顯示資料本地的追問指示；它沒有 ordinal／`SourceRef`／Evidence，不能單靠它建立 Task，且絕不進 OPKS packet；Web UI 尚未接通 |
| readiness | `assess_readiness(header)` → 只有 issue 清單的 `DocumentReadiness` | `app/job_analysis/application/readiness.py` | 純函式,零 IO,**不 import transport contract**;第一版只查表頭三項(名稱／工作描述／基準級別),零 issue 時安靜;**沒有 `is_complete`／百分比**;說明補充與所屬類別刻意不發聲。`DocumentView` 只承載此純函式的結果，Web 不重算 |
| llm 契約 | Task：內部 `TaskAnalysisResult`＋`task_analysis_result_v3` wire（v3 相對 v2 只多了與 `work_signals` 平行的 `issue_resolutions[]`；**不覆寫 v2**，同一個版本號不得指向兩種契約）；OPKS：獨立 `OpksResult`＋`opks_result_v1` wire；各自一份 Static Instructions | `app/job_analysis/llm/` | 只描述形狀與判準文字;**不做跨欄位驗證**。OPKS wire 只有 5 個 property、零 union，不擴充既有 Task schema |
| wire mapper | 中性值 → `None` 的純還原 | `llm/wire.py` 的 `wire_to_task_analysis_result()` | **不做語意判斷**;沒有 domain 落點的夾帶內容一律拒絕,不靜默丟棄 |
| assembler | Task 現況 → `TaskAnalysisPacket`；單一選定 Task → `OpksContextPacket`；兩者都有決定性 rendering | `application/context.py`、`application/opks_context.py` | 純函式;ordinal 的唯一產地。OPKS 只投影選定 Task、有效員工依據、該 Task O/P、全文件 K/S 與相關提案，不送完整 transcript／A／內部 ID |
| verifier | Task §9.5／§12.3 規則；OPKS decision／ordinal／refs 映射 | `application/verifier.py`、`application/opks_verifier.py` | 純函式；OPKS 會產出 application-side verified changes，但**不判必要性、可觀察性或文字品質** |
| operation | 組 packet → 呼叫 → parse → verifier | `application/operation.py`、`application/opks_operation.py` | Task 與 OPKS 各自一條顯式流程;**不是 agent runner**,無 retry |
| provider | 最小 OpenRouter Chat adapter | `providers/openrouter.py` | 一次 HTTP;固定 `reasoning=high` 且不回傳 reasoning;成功內容必須由 response `model` 證明來自 exact configured model;typed 失敗;**只收 render 過的文字** |
| transition | 結果 → Work Model 變更 ＋ Proposal | `application/transition.py` | **唯一寫入者**;全有或全無 |
| persistence ports | Current State repositories／UoW／版本化 Journal payload | `application/persistence.py` | 純 Protocol 與 frozen contracts；不認 ORM／JSON row |
| PostgreSQL adapter | 0012 四表＋0013 Journal kind＋0014 兩張 OPKS 表＋0015 Document Header、serialization、repositories、UoW | `app/adapters/job_analysis_postgres/` | `job_analysis_documents` 的 Header schema／JSON 都是 non-null；OPKS 五種 item 共用一張 typed JSONB 表、獨立 Proposal 共用另一張；不建五表或 refs join table。JSONB 讀取必須 hydrate；schema/shape 壞掉 fail-closed；repository 不 commit |
| authority commit seam | 完整 Current State → 同一 UoW 原子寫入 | `application/authority_commit.py` | **所有 authority writer（含 durable turn）**先重驗完整 `JobAnalysisState`（含 Header 與 OPKS refs），再 replace Header／JD／Task Proposal／OPKS／OPKS Proposal、寫入 0..N 筆 Journal、generation CAS、單次 commit；edited OPKS 決策用同一 seam 原子寫 proposal-decision 與 direct-edit 兩筆 Journal |
| authoring use cases | 文件庫、JD header、JD Task 與 OPKS add/edit/delete/reorder | `application/authoring.py`、`application/opks_authoring.py` | document row lock → entry replay check → Current State/Journal/generation 同交易；`put_jd_header()` 只替換 header、寫 `JdHeaderDirectEditPayload(before, after)`，不建 `SourceRef`／SupportLink、不碰 Task／Proposal／OPKS、不呼叫 LLM；未改內容拒絕，避免空 receipt／generation bump。Task 離開 Current JD 時，`prune_opks_for_current_jd()` 同交易移除其 O/P、清理 K/S refs，且不猜接 merge/split 新 Task |
| consultation use case | provider 前 replay → authority snapshot → 交易外模型呼叫 → verified commit | `application/consultation.py`、`application/durable_turn.py` | 已提交的同 key／同回答零 provider call；commit 時重鎖並比對 generation/read-set；Work Model、Proposal、下一題與 completed-turn Journal 同交易 |
| Proposal use cases | Task 與 OPKS 各自送審、決策與 stale | `application/proposal_decisions.py`、`application/opks_proposals.py` | 兩種 Proposal 不抽通用 framework；決策由 document lock 序列化。OPKS accepted 套用候選但不偽造 Evidence；edited 只可改文字並另鑄 direct-edit Evidence；歷史 accepted 不會誤殺日後建立的新 revise |
| Local Web API | 本機文件、JD header、Current JD、OPKS 與 Consultation routes | `app/api/routes/job_analysis.py` | 只做 generated wire DTO mapping；`PUT …/jd-header` 要求 `Idempotency-Key`，回 `JdHeaderView`，未改內容回 typed `422 invalid-request`；不暴露 Work Model、Journal、generation、內部 OPKS Source ID 或 provider detail。Consultation 會投影 Task 與 OPKS 兩種 Proposal，兩種 decision route 各自呼叫對應的 greenfield use case |
| Local Web UI | 文件庫、顧問訪談、Proposal 審查與單一開啟文件的 Task／OPKS editor | `apps/web/src/app/workspace/`、`components/workspace/` | generated TS DTO + TanStack Query；conversation／Proposal／Current JD 同頁，一份本地編輯草稿、明確儲存，不用 Server Action／autosave／第二份 document store。O/P/K/S 按 Task 投影，同一 K/S 保留同一 entity identity；未連結 K/S 與 A 留在文件層 |

### 2.1 Current State partition（Task 1–2）

`JobAnalysisState` 是 application 內一名員工、一份職務說明書的 Current State 真相；各欄位的權力邊界不可互換：

| partition | 欄位 | 意義與規則 |
|---|---|---|
| JD header authority | `jd_header: JdHeader` | 公版表頭語意欄位；**必填、沒有 state default**。`DocumentRecord` 以 `job-analysis-jd-header/1` 持久化它；所有 authority writer 與 Current JD 共用同一條 authority seam。 |
| work-model authority | `work_model` | 由訪談證據形成的 Task／open issue／excluded signal；模型只能經 verifier＋transition 提出候選。 |
| current-JD authority | `current_jd` | 員工可見的正式 JD Task 投影；Proposal 決策才可改，`apply_task_analysis_result()` 永遠不直接改它。 |
| proposal memory | `proposals` | 待員工決策的 Task 假說與其 snapshot；不是 Current JD，也不能當成已成立工作。 |
| OPKS authority | `current_opks` | O/P/K/S/A 文件內容與 Evidence linkage；OPKS packet 不讀 `jd_header`。 |
| OPKS proposal memory | `opks_proposals` | 待員工決策的 OPKS 假說；與 Task Proposal 分開，不抽通用 Proposal contract。 |

`DocumentRecord.jd_header` 是 frozen dataclass 的必填欄位。只有 `create_document()` 新建文件明確寫入 `JdHeader()`；0015 對既有文件以 `job-analysis-jd-header/1`／`{}` 回填。此後所有 state reconstruction 都從 `record.jd_header` 取得，transition 只轉送既有 `state.jd_header`，而 `commit_authority_change()` 以已驗證 state 在同一 authority transaction 保存它；不得以 default 或 `DocumentMetadataWrite.title` 掩蓋這條 seam。

readiness 的輸入只有 `JdHeader`，輸出只有按固定表頭順序排列的 issue 清單：職能基準名稱、工作描述、基準級別。所屬類別、職業／行業分類、說明與補充事項空白不列 issue；不產生百分比、`ready` 或 `is_complete`，也不阻止保存、訪談或未來匯出。

## 3. 一輪的資料流(每步標函式)

1. `build_context_packet(transcript=…, current_turn_id=…, work_model=…, current_jd=…, active_question=…, proposals=…, employee_written_overview=…)`
   → `TaskAnalysisPacket`。順序完全跟隨輸入,所以同輸入同輸出；`durable_turn` 只由 Header 的職能基準名稱與工作描述決定性組成 overview。overview 是協助 coverage／矛盾與下一題判斷的背景 authority read-set，不配 ordinal 或 `SourceRef`，也不進 verifier context 或 OPKS packet；其「背景不是做過的事」追問規則與資料相鄰渲染，`TASK_ANALYSIS_INSTRUCTIONS` 保持不變。
2. `run_task_analysis_operation(packet=…, adapter=…)`:
   - `render_context_packet(packet)` → 純文字,當成 user message;
   - `TASK_ANALYSIS_INSTRUCTIONS` 當成 system message;
   - `task_analysis_wire_provider_schema()` 當成 `response_format.json_schema.schema`;
   - `adapter.complete(...)` → **一次** `POST https://openrouter.ai/api/v1/chat/completions`;
   - `TaskAnalysisWire.model_validate_json(text)` → `wire_to_task_analysis_result(...)`
     → `verify_task_analysis_result(...)`。
3. `apply_task_analysis_result(state=…, packet=…, result=…, operation_id=…)` → `TransitionResult`。

OPKS 是另一個已接通 durable generation 的單 Task operation，不擴充上面那份 Task schema：

1. `build_opks_context_packet(selected_task=…, current_opks=…, proposals=…)` 只投影該 Task 的完整語意、
   有效 `employee_turn`／`direct_edit` Evidence、該 Task 的 O/P、全文件 K/S ordinal，及與該 Task 有關的
   pending／deferred／rejected OPKS Proposal。沒有有效員工 Evidence 時直接回
   `OpksGroundingUnavailable`，不呼叫 provider。
2. `render_opks_context_packet()` 只呈現 ordinal 與員工可讀文字；K/S 另標是否已連到選定 Task，
   但不洩漏 Task／entity／source／proposal ID。待決內容明標「尚未成立」。
3. 模型用 `OPKS_INSTRUCTIONS`＋`opks_result_v1` 回傳
   `add_new／reuse_existing／revise_existing／remove_existing／uncertain`。wire 的 `0`／空字串只在 mapper
   邊界存在，還原後交 `verify_opks_result()`；任一機械違規即整批不產生 change。
4. `verify_opks_result()` 只解 ordinal 與 refs：O/P 綁選定 Task；K/S reuse 追加該 Task；K/S remove
   只解除該 Task及其 Indicator refs，映射成 revise，即使變成 unlinked 也不刪文件層 entity。
   「是否真的必要／可觀察／數值是否合理」留給 rubric 與員工 Proposal 決策。
5. `generate_opks_proposals()` 先查 `opks_generation` receipt，再以 `prepare_opks_generation()` 保存
   immutable authority snapshot；`run_opks_operation()` 在交易外做一次 provider 呼叫；
   `commit_opks_generation()` 重鎖文件並比對 generation 與 packet read-set，最後才把 verified changes
   轉成 pending `OpksProposal`，和 generation receipt 一起經 `commit_authority_change()` 原子提交。
   同一 `Idempotency-Key` 重送不再呼叫 provider；零 change 也保存
   `no_change` receipt。Provider failure、refusal、invalid 或 verifier rejected 都不改 Current JD。

### 3.1 誰觸發 OPKS：主回合凍結的唯一 child（ADR 0054）

**沒有「產生／重新分析 OPKS」按鈕，也沒有 background worker。** 員工不需要理解 OPKS 階段
存在；哪個 Task 現在值得分析由 application 純函式決定，不交給模型 routing。

- `eligible_opks_candidates(state, question_task_ids=…)`（`opks_scheduler.py`）是**純函式**：
  Task 在 Current JD、Work Model Task 為 `ACTIVE`、有 ≥1 筆有效員工依據、沒有指向它的 **active**
  issue（`OpenIssue.is_active`）、沒有它的 pending／deferred OPKS Proposal、本輪 `next_question`
  沒問到它。依 Current JD `display_order` 排序回傳，每筆帶 `analysis_input_digest`。
- **`purpose_result` 不是硬條件，也不得用引文數／字數／涵蓋度加強。** 前者因為工作產出可合法
  缺省（ADR 0052 決定 15），後者是 0052 決定 6 禁止的完成百分比換皮。證據太薄時由 specialist
  回全 `uncertain`，終端 receipt 讓浪費上限停在「每個輸入狀態一次呼叫」。
- 「這個輸入分析過了嗎」由 `select_scheduled_opks()` 對每個候選問 `journal.get()` 回答——child
  operation ID 是 `opks:auto:{task_id}:{digest}`，由 `scheduled_opks_operation_id()` 推導、**不另存**。
  因此不需要新的 query port。
- `commit_verified_turn()` 在同一交易內用 **post-transition** state 排定，寫進
  `CompletedTurnPayload.scheduled_opks`（最多一筆）。**綁定在 receipt 寫入時凍結**：replay 一律
  回傳既存 payload 那一筆，`_require_same_replay()` **刻意不比對** `scheduled_opks`。少了這一條，
  replay 會重跑 scheduler 依當下 state 改選下一個 Task，同一個員工回合因此付兩次錢。
- **執行點是 `submit_employee_turn()`，不是背景工作。** 主回合提交後，若 payload 帶
  `scheduled_opks` 就同步跑那一個 child；一次 `/turns` 最多主顧問 ＋ 一個 specialist，
  員工只看到一個「分析中」。child 的失敗**不得**改變 `/turns` 的結果：四種終端失敗由
  `generate_opks_proposals()` 自己寫 `failed` receipt，`StaleAuthoritySnapshot` 是
  abandon（不寫 receipt、不擋下次），兩者都在 `_run_scheduled_opks()` 內被吞掉。
- **`generate_opks_proposals()` 的 `expected_digest` 是必填的，`prepare_opks_generation()`
  一開工就比對。** 傳進去的一定是主回合凍結的那個 `ScheduledOpks.analysis_input_digest`——
  `operation_id` 由 `(task_id, digest)` 推導，三個值必須同源。**不比對就是靜默的雙重付費**：
  主回合 commit 之後、child 開始之前（crash 後重開、replay 之間）員工仍可能直接編輯那個
  Task，child 於是用新輸入分析、卻把 receipt 寫在舊 digest 推導出的 ID 上；下一輪 scheduler
  算出新 digest、`journal.get()` 找不到，同一份輸入再付一次。對不上就 abandon（決定 10），
  而且發生在 provider 呼叫**之前**——漂移這時已經看得出來，沒有理由先付錢再丟掉。
  grounding 檢查排在比對之前：「這個 Task 沒有員工依據」是它自己的狀態，不是漂移。
- **沒有 background worker，因此單純 reload／GET 不會補跑漏掉的 child。** 恢復只發生在
  兩個地方：同一個 `/turns` 以相同 `Idempotency-Key` replay（replay 分支會讀回既凍結的
  `scheduled_opks`），或後續回合的 scheduler 再次選到同一個 child ID。程式註解、UI 文案
  與文檔都不得暗示「開著就會自己補上」；`test_reloading_the_document_does_not_run_the_missing_child`
  就是擋住日後有人在讀取路徑加隱性 worker 的那道牆。
- `analysis_input_digest`（`opks_digest.py`）只吃 Task：六個語意欄位 ＋
  `Task.effective_employee_support_links`。**排除** `CurrentJdOpks`／`OpksProposal` 狀態（否則
  接受 Proposal 就會 ping-pong）與 `rejection_reason`（REJECTED 強制帶 reason，進 digest 就是
  付費 reject loop）。投影規則與 `build_opks_context_packet()` 共用同一個 domain property，
  兩邊各寫一份遲早失步。canonical JSON + SHA-256，**不得改用內建 `hash()`**（PYTHONHASHSEED
  隨機化會讓重開後同一輸入付兩次錢）。

### 3.2 缺口只有一條解決通道（ADR 0054 決定 22–23）

缺口走 `task_analysis_result_v3` 的第三個頂層陣列 `issue_resolutions[]`（`{ordinal,
resolution}`，扁平、每 issue 一筆），**不走 `WorkSignal`**。三個值：`answered` 沿用現行語意
（移出 `open_issues`）；`employee_unknown`／`not_applicable` 不移除，改寫入 `terminal_resolution`
轉成「已問過、勿重問」的 context memory。`source_ref` 由 application 蓋，不進 wire。

- **`answered` 的機械前提**：同一輪必須有一筆針對該 gap `subject_task_id` 的 `support_only`
  或 `revise`（`_leaves_employee_evidence_on()`）。少了它 digest 不變、OPKS 不會再分析，
  缺口被**假關閉**——員工以為答過了，系統卻永遠不會用那個答案。
- **`resolves_open_issue_ordinal` 不得用來關缺口**（`RESOLUTION_OPKS_GAP_NEEDS_ISSUE_RESOLUTION`）。
  ADR 0047 把那個欄位開放給「模型自己提出的」open issue，理由是只有主顧問知道自己上一輪問過
  什麼；OPKS 缺口由 specialist 提出，且上面那條前提是機械可判的，所以不在 0047 的範圍內。
  缺口在資料上長得跟一般 issue 一樣（沒有 `reconciliation_task_id`），**不擋就是一扇後門**：
  模型送一筆帶當輪 anchor 的訊號即可整筆刪除缺口、什麼依據都不留。帶依據的訊號也一樣擋——
  放行等於把前提複製到第二處。判別用 `subject_task_id`（domain 保證 `opks_axis` 非空必有它，
  且全 repo 只有 `_gap_issues()` 會寫它）。**0047 對沒有 subject Task 的 issue 原樣有效。**
- 主顧問 prompt 因此明寫「缺口一律用 `issue_resolutions` 關，不填
  `resolves_open_issue_ordinal`」：任何 violation 都會退掉整輪，模型走錯門就白付一次錢。

`TaskFields` 舊的兩個 OPKS hint 已退役；正式 O/P 的唯一資料來源是 `CurrentJdOpks`，不留第二份真相。

員工直接編輯走另一條短路徑：`put_jd_header`／`add_jd_task`／`edit_jd_task`／`delete_jd_task`／
`reorder_jd_tasks` 先鎖 document，以 Journal `entry_id` 做 replay/conflict 判定，同交易保存
Current JD、相關 Proposal stale、Work Model reconcile trigger、Journal 與 generation。**按儲存不呼叫 LLM**；
它、Proposal use cases、OPKS use cases 與 durable AI turn 都在各自完成入口規則與狀態推導後，共用
`commit_authority_change()` 做完整狀態驗證與最終寫入。`commit_verified_turn()` 仍保有
provider-outside-transaction 與 snapshot revalidation 語意；重鎖成功後把 post-transition state 與
下一題送入同一 seam，故 Header、Current JD、Proposal、Journal 與 generation 一起 CAS 提交。

OPKS 人工編輯沿用同一條權威邊界：`add_opks_item`／`edit_opks_item`／`delete_opks_item`
接受 `Idempotency-Key` 作為 Journal `entry_id`，由 application 配發 add ID；client 不得傳 Evidence 或
內部 ID。`DocumentView`／`ConsultationView` 只投影可編輯欄位與可讀的 evidence quotes。
Task delete 或 accepted／edited withdraw、merge、split 會在同一 authority transaction 呼叫
`prune_opks_for_current_jd()`：O/P 隨擁有它的 Task 移除，K/S 只移除失效 refs 且可保留 unlinked，
A 保留；系統不會把舊 refs 猜接到 replacement Task。員工直接刪除 Indicator 時，
`delete_opks_item()` 也會在同一交易移除 K/S 對該 Indicator 的 refs，避免留下懸空連結。
OPKS Proposal 決策走 `decide_opks_proposal()`，不呼叫模型：`accepted` 套用原候選且不因員工按接受
新增 Evidence；`edited` 只允許改文字，並在同交易寫 proposal-decision 與 direct-edit Journal、
把 direct-edit Evidence 掛到 Current JD；remove Proposal 沒有 replacement text，因此 `edited` 會回
typed 422 invalid request，不進交易深處；`rejected`／`deferred` 不改 Current JD。target／Task refs
或同一 entity 的並行提案失效時只把 active 提案標成員工可見的 `stale`，terminal 不回寫；重送已
stale 的決策不會再次 bump generation。Task 或 OPKS 人工編輯、Task Proposal 拓撲套用也會在同一
authority transaction 重算相關 OPKS Proposal，而不靠背景修補。

本機 Web 文件入口走 `GET /api/v1/job-analysis/documents`、
`PUT /api/v1/job-analysis/documents/{document_id}` 與
`GET /api/v1/job-analysis/documents/{document_id}`；後者的 `DocumentView` 一律含完整
`jd_header` 與由 `assess_readiness()` 產生的 code-only `readiness`。`PUT /api/v1/job-analysis/documents/{document_id}/jd-header`
以 `Idempotency-Key` 替換完整 Header；mapper 是唯一 trim／空字串→`null` 的位置，route／Web 不重算 readiness。
標題只是 metadata：同 ID 的 PUT 可建立或改名，
但不走 authority seam、不寫 Journal、也不 bump `authority_generation`。新路徑的錯誤使用
RFC 9457 `application/problem+json`；path-scoped handler 會把舊 routes 的既有錯誤 body 原樣保留。
Current JD Task 的 POST／PUT／DELETE 與排序 PUT 都要求 `Idempotency-Key`，原樣映射成
Journal `entry_id`；沒有 middleware、隱藏 retry 或第二套寫入邏輯。員工清空 optional text 時，
HTTP DTO mapper（與 LLM 的 `wire.py` 無關）先 trim 並轉成 `null`；必填 statement 變空則回 `invalid-request`，不讓半成品進 domain。
**`POST …/tasks/{task_id}/opks-proposals` 已退役，不得復活**（ADR 0054 決定 1）。OPKS 的唯一 AI 入口是
`POST …/turns` 排定的 child：員工不需要理解 OPKS 階段的存在，也不該由他判斷哪個 Task 已經談夠、
何時該按。連帶退役的還有 `OpksGenerationView` 契約型別與 Web 的「產生建議」按鈕。
**員工手動新增／編輯／刪除 O/P/K/S 的端點保留**——那不是 AI 入口。AI 仍然只建立待員工決定的
Proposal，不直接寫 Current JD OPKS。

`DocumentView` 與 `ConsultationView` 帶 `opks_task_status[]`，每筆 `{ task_id, status }`。
規則是 `opks_task_status()` 純函式（ADR 0052 決定 1），contract 只承載結果（決定 2），
**Web 直接呈現、不自行重算**（決定 3）。狀態只有三個值，對應 ADR 0054 決定 36 允許的**全部**
措辭——`not_ready_for_analysis`／`awaiting_employee_answer`／`proposals_ready`，中文字串住
`jobAnalysisOpks.ts`，受 0052 決定 7 約束（不得用「不完整」「不合格」「未通過」）。
**缺口優先於待審提案**：兩者同時存在是常態（決定 18 的 item-level 部分發布），只說
「已可提出建議」會讓員工以為已經談完。**判不出來的 Task 不出現在陣列裡**，因此沒有第四個
標籤也沒有完成百分比——0052 決定 6：「無法確定的一律不提示。」
Web 的 `/workspace` 用 `DocumentLibrary` 列出／建立／改名；`/workspace/[document_id]` 用
`ConsultationWorkspace` 同頁組合 `ConsultationPanel`、Task／OPKS Proposal cards、`TaskEditor` 與
`OpksEditor`，一次只開一份文件。OPKS 人工變更也採明確儲存，成功後只 invalidate document、
consultation 與文件庫 query；不手動維護第二份 cache。K/S 可投影到多個 Task 但 entity ID 不複製，
Task 移除後保留的 unlinked K/S 仍在文件層可見；A 只在文件層手動編輯，不提供 AI 生成按鈕。
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
會改變 Task 邊界的矛盾／責任問題，再處理一般 open issue、**OPKS 缺口**與遺漏掃描
（ADR 0054 決定 21 的 agenda 順序，實作住 `context.py` 的 `_agenda_rank()`）。pending／deferred Proposal
只是待決假說，不會凍結訪談；第一版沒有完成 gate，模型不得宣稱訪談或 JD 已完成。這些是
scripted smoke 保護的顧問行為基線，不代表模型品質已通過。
既有 Task 在下一次 AI 互動時看到 JD/Work Model 差異；JD-only Task 先落一筆
`insufficient_evidence` open issue，明確保存該 JD `task_id`，不補造空殼 Work Model Task。
下一輪 packet 只把它投影成可追問的 partial Task：

- `no_match + add` 才能以同一 `task_id` materialize Work Model Task；
- `exclude` 只建立員工可見的 JD-only withdraw Proposal，不靜默移除文件；
- `duplicate`／`overlap`／`uncertain` 保留 issue 並追問，不以文字相似度猜 identity；
- next question 指向該 issue 時，同一 transition 保存 `last_asked_turn_id`，reload 後可續問。

`last_asked_turn_id` **兩條 target 都記**：指向既有 open issue（`existing_open_issue`），
或指向**本輪剛提出該 issue 的訊號**（`new_signal`，issue id 為 `{operation_id}-i{index}`）。
同一輪提出 issue 又追問它是最常見的顧問形狀；只記前者的話新 issue 永遠停在
`None`，下一輪 packet 顯示「(尚未問過)」，模型就把剛問過的缺口當成沒問過再問一次。
`new_signal` 指向的訊號不一定產生 issue（例如剛新增的 Task），沒有就沒得記，不是錯誤。

持久 AI 回合由 `submit_employee_turn()` 先以 `operation_id` 查 Journal：已提交且回答相同就直接
返回，回答不同則 `IdempotencyConflict`；只有尚未提交才依序呼叫 `prepare_turn()` →
`run_task_analysis_operation()` → `commit_verified_turn()` → `commit_authority_change()`。第一步讀完即關閉交易，LLM I/O
期間不持有 PostgreSQL lock；最後一步才重鎖 document。generation、packet read-set 或
conversation authority 任一不一致就回 `StaleAuthoritySnapshot`，舊結果不得套用。
相同 `operation_id` 的已提交回合不會再打 provider，也不會新增 Task／Proposal／Journal。
兩個同時飛行中的相同 request 尚未合併；這是單機第一版的明示限制，不得稱為 exactly-once。
模型輸出 `task_change.add` 表示該訊號已通過 Task 成立判準：transition 先建立 Work Model 候選，
並在同一結果中建立 pending `add` Proposal。候選仍不是 Current JD；只有員工 accept／edit 後才進文件。
若只建立不可見候選而沒有 Proposal，Consultation View 又不暴露 Work Model，員工就永遠無法審查 AI 找到的工作。

Proposal 決策由 `decide_proposal()` 完成，沒有 LLM。`accepted` 套用 `jd_after`；
**新進 JD 的 Task 在套用時才拿到 `display_order`，不照抄提案帶的值**：提案建立時
`transition._next_jd_order()` 讀的是當下的 Current JD，訪談期間 JD 是空的，所以每一筆 `add`
都算出 0；照抄會讓第二筆被接受時撞上「display order 必須唯一」，而一次訪談產出多筆 `add`
提案是常態。位置是 JD 清單的性質不是提案內容——員工審的是文字，`edited_jd_after` 也明文
不准改 `display_order`。已在 JD 的 Task 保留原位置，移除先套用讓新進者填補空號。
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
| `invalid_output` | 不是合法的 `task_analysis_result_v3` JSON,或還原不成 domain 契約(夾帶) | 重組 context 再來,不是 retry 同一份 |
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
| domain 型別 | 形狀不變量,**非法狀態無法被建構** | `active` Task 至少一條有效 SupportLink;`withdrawn` 必有 reason;lineage 不成環;staged delta 的 ID 不重複且欄位必須符合 action;Current JD／Proposal ID 不重複且 JD 投影順序 canonical;§10.5 的 `edited_jd_after` 四條硬規則；OPKS Evidence 非空且只收 employee turn/direct edit，O/P 恰連一個 Task、K/S 多對多、A 不帶 refs，OPKS Proposal 的 action/snapshot/status payload 不可矛盾 |
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
- **精確重複才由程式拒絕。** 逐欄完全相同的 `work_signals[]`，以及 OPKS packet 現況或同批輸出中
  `entity_kind` 相同且 trim 後文字逐字相同的 `add_new`，都是確定性錯誤；近似文字、同義改寫與
  Task／OPKS identity 仍是語意問題，不做相似度服務或工具字典。
- **新分析不能讓舊提案無聲留下。** 同一 Task 已被本輪實質重新分析、但沒有 replacement 時，
  仍將重疊的 pending／deferred Proposal 標成 stale，並保存員工看得到的理由。
- **greenfield 邊界。** `app/job_analysis` **不得 import** `app.interview`、`app.interview_vnext`、
  `app.job_authoring`、`evals`,也不得 import DB／web 框架。由
  `tests/test_job_analysis_dependencies.py` 以 AST 強制。
- **smoke 綠燈不代表模型品質通過。** `tests/test_job_analysis_smoke.py` 用 scripted provider；
  `tests/test_job_analysis_durable_smoke.py` 用 fake verified result 與真 PostgreSQL，只證明交易／reload vertical。
  `tests/test_job_analysis_opks_vertical_postgres.py`／`scripts/job_analysis_opks_smoke.py` 也只以 scripted
  provider 證明 OPKS 的生成、決策、人工編輯、reuse、Task delete 與無 Evidence 停線可經真 PostgreSQL
  走完；它不打網路，也不證明 OPKS 文字品質。
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
| **真模型跑通** | **三回合已在三個模型上跑完**(Opus 5／Sonnet 5／Luna-Pro,皆 `committed`×3)。2026-07-31 的八次付費 run 累計 US$0.613,找出**七個**契約層缺陷,全部已修：grammar 過大、`target_ordinal` 的 1-based／0-based 不一致、6 條 verifier 規則模型無從得知、一般 open issue 無關閉路徑（ADR 0047）、新 issue 拿不到 `last_asked_turn_id`、schema 名稱帶點、`$ref` 帶兄弟 keyword（後兩者是可攜性,契約原本鎖死 Anthropic）| **merge／split、supersession 一次都沒被觀測到**；過早關閉 open issue 的風險也未被測到（turn 3 時已無 issue 可關）。`withdraw` 只在 Luna-Pro 的錯誤補救裡出現過,不算正常路徑觀測。**Proposal 決策已首次走通**：run 5 的四筆 `add` 全部 accepted，產出第一份 4 條的 Current JD（`authority_generation: 7`）——並在該路徑上找出 `display_order` 照抄提案值的缺陷，已修 |
| prompt 品質結論 | **仍然沒有 rubric。** 已觀測到跨回合記憶、更正處理與 enabler 硬規則守住,也用三模型 A/B 定位出一個判準落點缺陷(§8.2),但那些都是單次 synthetic trial 的事實記錄,不是品質 gate | 有可比對的判準與重複抽樣之後 |

### 8.1 Attributed live smoke(`scripts/job_analysis_live_smoke.py`)

一支**一次性診斷 CLI**,不是 eval framework、不是常駐設施,也**沒有任何 runtime 或 route 依賴它**。
它跑真 `create_document()` → `submit_employee_turn()` → `load_document()`、真 PostgreSQL 與真 OpenRouter,
固定三回合 synthetic 場景(多工作＋工具 / 更正責任 / 途中新增工作),每回合只送一次。

邊界:

- 硬上限 **3 次 generation call、US$0.75、零 retry**;reserve 用 live catalog 單價在 HTTP **之前**算,
  超過就停。完成後改用 `usage.cost` 累計,cost 缺失即停止剩餘回合。
- 只有這支 CLI 的 `RecordingTransport` 加 `X-OpenRouter-Metadata: enabled` 與 `X-OpenRouter-Cache: false`;
  **`OpenRouterAdapter` 與 FastAPI dependency 的 headers 未改**,產品回合不要求 metadata。
- raw capture 寫 gitignored `output/job-analysis-live-smoke/<run-id>/`;request headers 永不落地,
  因此 API key 沒有進檔案的路徑。Git 只收 `docs/experiments/` 的精簡報告。
- `--max-generation-calls 0` 只做 catalog preflight,不建文件、不花錢。working tree dirty 時 CLI 在付費前停止。
- 它**不是**瀏覽器 E2E:不驗 UI 點擊、CORS 或前端錯誤顯示。單次 trial 也不能宣稱穩定品質或比較模型。

**這支的場景永遠不會排定 OPKS child。** 訪談只產生 Proposal,沒有員工決策步驟,所以沒有
Task 進得了 Current JD,pre-gate 一次都不會通過。要觀察 0054 那條線得用下面那一支。

### 8.1.1 OPKS 漸進式蒐集的 live smoke(`scripts/job_analysis_opks_elicitation_live_smoke.py`)

同樣是一次性診斷 CLI,差別只有場景:它把**單一** Task 直接種進 Current JD(走
`commit_authority_change()`),訪談才走得到主回合 → 排定 child → 缺口 → 追問 → 回答 →
再分析。只種一個 Task 是成本護欄——pre-gate 逐 Task,多一個就多一條 child。

回答的是 scripted 測試回答不了的四件事(ADR 0054 計畫 T18):specialist 在證據薄時是否
真的回 `uncertain`;gap 摘要是否被寫成問句(決定 16);主顧問是否把 K/S 問成認領題
(ADR 0048 決定 14);`issue_resolutions[]` 是否被當成偷懶關閉的出口(0054 後果段已承認
verifier 擋不住)。加一點:模型會不會仍想用 `resolves_open_issue_ordinal` 關缺口。

- 硬上限 **5 次 generation call、US$1.80、零 retry**;3 回合主顧問 ＋ 最多 2 次 child
  (缺口 active 期間 pre-gate 擋住同一個 Task,所以中間那回合不會再排)。CLI 只能往下調。
- **逐 call 記錄與結算,不是逐回合。** 一個 `/turns` 可能有兩次呼叫,只取最後一次會漏掉
  specialist 那次的成本與內容。capture 用送出的 schema 名字分辨主顧問與 specialist。
- `observations.json` 只做**機械抽取**:缺口摘要、結尾是不是問號、主顧問問句原文、
  送出的 `issue_resolutions`。K/S 有沒有問成認領題是語意判斷,只列原文給人讀,不自動判。
- 已知不忠實:種下的依據不在 transcript 裡;員工回合預先凍結,接不上主顧問當下真正問的
  那一題。這兩點寫在 manifest 的 `limitations`,不得在報告裡略過。

### 8.2 開發用便宜模型,生產用貴模型——以及哪些問題不准用便宜模型回答

2026-07-31 owner 決定:**本機開發與測試跑 `openai/gpt-5.6-luna-pro`(實測約 Opus 的 10%),
正式上線再切 Opus。** 落地方式刻意不對稱:

- `config.py` 的 committed 預設**維持 `anthropic/claude-opus-5`** —— 生產 correct-by-default,
  上線不需要記得切回去;要記得的是把本機 `.env` 的覆寫拿掉。
- 便宜模型只以本機 `.env`(gitignored)的 `JOB_ANALYSIS_MODEL`／`JOB_ANALYSIS_PROVIDER` 覆寫。
  smoke CLI 與 dev server 讀同一份 settings,所以兩邊自動一致。

**分界線比切換方式重要。** Luna-Pro 在同一個凍結場景下會從「我會**協助**正式環境部署」
生出一條 Task(run 6 與 run 8 兩次都是),而 Opus 5(2/2)與 Sonnet 5 都判成
`責任邊界不明` open issue 並追問。把判準搬到 `disposition` 的 description 之後仍然如此
——**能力問題,不是指令問題**(`docs/experiments/…-attributed-live-smoke/README.md` §0f／§0g)。

| Luna-Pro 答得準(契約層,與模型無關) | Luna-Pro 答不準(判斷層,與模型高度相關) |
|---|---|
| schema 能不能編譯、跨 provider 可攜 | Task 邊界判斷 |
| 機械耦合規則(relation↔change、ordinal、anchor) | 證據紀律(`open_issue` vs `task_change`) |
| verifier／transition／persistence 整條鏈 | statement／`purpose_result` 品質 |
| 新欄位有沒有被填、pipeline regression | 追問品質、跨回合取捨 |

因此:**契約類改動在 Luna-Pro 上驗過即可;會影響判斷的改動(prompt 判準、schema description、
context 取捨)在 Luna-Pro 上驗過只算「未在生產模型上驗過」,上線前要補一次 Opus／Sonnet run。**
現有的一筆未清:commit `4b75190` 給 `disposition` 補的判準只在 Luna-Pro 上觀測過。
| prompt 品質調校 | `llm/prompt.py` 已有 Task 判準與彈性顧問行為基線，但尚未用真實員工資料調校 | 有真實使用摩擦後以 rubric／eval 調整，不先加 planner 或第二次呼叫 |
| duplicate／overlap identity 自動收斂 | 第一版刻意不做；模型保留 issue 並追問員工 | 有真實重複摩擦證據後再研究，不用相似度猜測 |
| OPKS 真模型品質結論 | **第一切片已接通**：`OpksItem`／`CurrentJdOpks`／獨立六態 `OpksProposal`、0014 兩表、人工編輯、API、Web、單 Task Context、零 union `opks_result_v1`、deterministic verifier、一次 provider operation 與 durable generation receipt 均已落地。七情境 scripted vertical 以真 PostgreSQL 驗證同 key replay 零 call、四種員工決策、A 人工編輯、同一 K 跨 Task reuse、Task delete 清理與無 Evidence 在 provider 前停線；舊 OPKS hint 已退役。裁決見 [ADR 0048](../adr/0048-opks-evidence-axes-and-document-level-competencies.md)～[0051](../adr/0051-opks-proposal-status-machine-and-stable-entity-id.md)，**四份一起讀** | scripted provider 不回答真模型的 O/P/K/S 品質；需要品質結論時另做有預算上限的 live smoke，不重開本切片或加 eval framework |
| 完整 header、匯出 | **Task 1–3 已落地**：`JdHeader`／readiness 純函式、0015 persistence、typed Header direct-edit receipt、`PUT /jd-header` 與 `DocumentView` 的 `jd_header`／server-provided `readiness` 都已接通。**尚未進 Task packet 或 Web UI**；`DocumentMetadataWrite` 仍只有 `title` | **已由 ADR [0052](../adr/0052-jd-readiness-assessment-and-official-code-boundaries.md) 裁決順序**：先 header／nullable 基準級別／說明補充＋readiness 純函式（**`app/job_analysis` 持有規則**，contract 只承載 view 與 issue codes；只提示不阻止保存／訪談／匯出），再 **Duty＋Task 職能級別的獨立結構切片（export-ready v1 必須完成）**，最後才 deterministic 匯出（不讓 LLM 參與）。**header 走 `JdHeader` 的 authority seam，不是擴充 `DocumentMetadataWrite`；readiness 第一版不回 `is_complete`**（ADR [0053](../adr/0053-jd-header-authority-boundary-and-readiness-scope.md)）。`職能基準代碼`／`職類別代碼` 由 iCAP 配發，不開欄位、不列缺漏、不得生成（0040 決定 33–34、0052 決定 8）；`T1`／`O1.1.1` 是匯出版面位置碼，非 identity（0052 決定 10） |
| revision-request replacement | revision request 可保存／reload，但不會自動重建 replacement | 後續模型流程 |
| 一般瀏覽器完整跨埠 smoke | **HTTP 層已逐段驗過**（2026-07-31，api:8001 ＋ web:3000 同時在跑）：文件庫 `GET` 正確回報 `task_count`、consultation view 帶齊 conversation／proposals／tasks、**三筆 `add` 提案連續 `POST …/decisions` 全 200**（正是 `display_order` 缺陷會炸的路徑）、同 `Idempotency-Key` 重送 200 且不重複、reload 後 JD 排序正確；CORS preflight 200 且 `access-control-allow-headers` 含 `idempotency-key`。`/workspace` 與 `/workspace/{id}` 皆 HTTP 200。Web 90 tests／tsc／lint 通過 **已由維護者在一般瀏覽器完成**（2026-07-31）：文件 `b47d6717` 的三筆 `add` 提案**在 UI 上連續按 accept 全部成立**，Current JD 由 0 條變 3 條、`display_order` 0/1/2；同文件被 withdraw 的那筆提案維持 `stale` 且無法接受，因此 Luna-Pro 在 turn 1 誤建的「協助正式環境部署」**沒有進入 JD**——Proposal gate 當安全網首次被真流量驗證 | 本列已無待辦。持續維持:不為測試環境加入 proxy、fake production mode 或 E2E framework |

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
- OPKS first slice:
  [`ADR 0048`](../adr/0048-opks-evidence-axes-and-document-level-competencies.md)～
  [`ADR 0051`](../adr/0051-opks-proposal-status-machine-and-stable-entity-id.md)、
  [`implementation plan`](../plans/2026-08-01-job-analysis-opks-first-slice-plan.md)
- 舊路徑(**已退場,勿救回**):[`interview-engine.md`](interview-engine.md)、
  [ADR 0030](../adr/0030-ai-coedit-tracked-changes-one-brain.md)
