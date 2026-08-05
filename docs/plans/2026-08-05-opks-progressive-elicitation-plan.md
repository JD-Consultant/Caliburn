# OPKS 漸進式蒐集實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to execute this plan task-by-task. Keep one task per commit and stop at every stated gate.

**Goal:** 讓 OPKS 從「員工按按鈕的一次性生成器」變成「主顧問訪談循環的一部分」：Task 資料明顯可分析時由 application 純函式自動排定一次 OPKS specialist 呼叫，有依據的軸出 Proposal、缺依據的軸留下可持久的 gap，主顧問在同一聊天室一次追問一題，員工回答形成新 digest 後自動再分析，全程可重開、可恢復、同一輸入不重複付費。

**Architecture:** 兩個各自獨立的 durable operation：主回合（`durable_turn`）與 OPKS child（`opks_generation`）。主回合在同一交易內以純函式算出**最多一筆** `scheduled_opks`（`task_id` + `analysis_input_digest`）寫進 receipt；child ID 由這兩者推導為 `opks:auto:{task_id}:{digest}`，不重複持久化。`journal.get()` 就是「這個輸入分析過了嗎」的唯一查詢，不加新 query port。缺口重用 `uncertain` item 形狀（`opks_result_v1` 零 schema 變更），落地成帶 `subject_task_id`／`opks_axis` 的 `OpenIssue`；解決走與 `work_signals` 平行的新 `issue_resolutions[]`，不綁在 `WorkSignal.disposition` 的副作用上。不引入 queue、background worker、workflow engine、retry framework、agent router 或 tool loop。

**Tech Stack:** Python 3.12、Pydantic v2、FastAPI 0.115.0、SQLAlchemy 2.0.51 async、PostgreSQL 16（`work_model_json` / journal payload 皆為 JSONB + `*_schema_id`）、Alembic、pytest、JSON Schema 2020-12、Next.js 16.2.6、React 19、TanStack Query v5、TypeScript、Vitest、ESLint。

**Authority:** [ADR 0054](../adr/0054-opks-progressive-elicitation-and-scheduled-child-operation.md)（本計畫的唯一裁決來源，決定編號 1–37 直接被各 Task 引用）、[研究紀錄](../specs/2026-08-04-opks-progressive-elicitation-research.md)、[ADR 0048](../adr/0048-opks-evidence-axes-and-document-level-competencies.md) 決定 5／6／14／24–25、[ADR 0049](../adr/0049-opks-derived-axes-evidence-whitelist-and-document-authority.md) 決定 13–14、[ADR 0052](../adr/0052-jd-readiness-assessment-and-official-code-boundaries.md) 決定 1／6／7／15、[ADR 0047](../adr/0047-model-owned-open-issue-closure.md)、[Task Analysis Engine](../design/task-analysis-engine.md)。研究稿與 ADR 衝突時以 ADR 為準。

## Global Constraints

- **不做**：完成百分比、涵蓋度、進度 dashboard、側邊聊天、gap 問題卡、背景 worker、queue、retry／backoff／circuit breaker、通用 agent router／tool loop／handoff／tracing framework、K/S 變成 P 的子項、text-similarity 比對。
- **不恢復**「產生／重新分析 OPKS」按鈕；員工手動新增／編輯／刪除 O/P/K/S 一律保留，那不是 AI 入口（決定 1）。
- **不得**把 `purpose_result != null`、引文數、字數或涵蓋度放進 pre-gate（決定 4–5）。機械條件的誠實極限是「≥1 筆有效員工 SupportLink」。
- **不得**宣稱 at-most-once／exactly-once。provider 已回應、Journal commit 前崩潰仍可能重打（決定 33）。程式註解、docstring 與文檔都適用。
- **不得**由 application 推導跨軸依賴（決定 17）；一個缺口影響多軸時由 specialist 逐軸輸出 `uncertain`。
- 部分發布的效力單位是 **item**，不是軸、不是 Task（決定 18）。
- 每個已提交的員工回合最多一筆自動 OPKS call；相同 `analysis_input_digest` 不自動重跑；**零隱藏 retry**（決定 31）。
- OPKS child 失敗**不**回滾已提交的 Task Analysis，`/turns` 不得因此改回 5xx（決定 32）。
- 不 import／搬移／雙寫 `app.interview`、`app.interview_vnext`、`app.job_authoring`、`evals`；既有 AST guard 保持綠。
- 每個 Task 先紅測試再最小實作；一個 Task 一個 commit，綠了才 commit，**不 push**。
- 動到可觀察行為的 commit 同時更新 `docs/design/task-analysis-engine.md`，不得留到最後補。

## 持久化形狀變更的統一處理

`work_model` 與 journal payload 都是 JSONB + schema id（`WORK_MODEL_SCHEMA_ID` 等，見 `application/persistence.py:38-49`）。本計畫的所有欄位新增都是 **additive optional**，舊列反序列化時取 `None`／預設值，因此**不需要 Alembic migration**。動到形狀的 Task 必須：

1. 判斷是否 bump 對應的 `*_schema_id`（新增 optional 欄位可不 bump；改變既有欄位語意必須 bump）。
2. 加一筆「舊 JSON 讀得回新模型」的 round-trip 測試。
3. 在 commit message 說明選擇。

## Phase 1 — domain 與 persistence 形狀

### Task 1 — `OpenIssue` 的三個新欄位與 active 定義

**檔案：** `app/job_analysis/domain/work_model.py`、`domain/__init__.py`

- 新增 `OpksGapAxis(StrEnum)`，**只含 OUTPUT／INDICATOR／KNOWLEDGE／SKILL，不含 Attitude**（決定 19）。不要重用 `OpksEntityKind`，它含 ATTITUDE。
- 新增 `OpenIssueTerminalResolution { kind: employee_unknown | not_applicable, source_ref: SourceRef }` —— **合併為單一物件**，避免兩欄位失步（決定 19）。
- `OpenIssue` 新增三個 optional 欄位：`subject_task_id: TaskId | None`、`opks_axis: OpksGapAxis | None`、`terminal_resolution: OpenIssueTerminalResolution | None`。
- **`subject_task_id` 不得挪用 `reconciliation_task_id`**（決定 19）。加一個 validator 或註解點名兩者用途不同。
- validator：`opks_axis` 非空時 `subject_task_id` 必須非空（gap issue 一定綁一個 Task）。
- `OpenIssue.is_active` property = `terminal_resolution is None`（決定 20）。**全 repo 判斷 active 一律走這個 property**，不要在呼叫端寫 `is None`。

**紅測試：** gap issue 建構、`opks_axis` 不接受 attitude、`is_active` 三種情形、舊 JSON（無三欄位）round-trip。

**Gate：** `cd apps/api && uv run pytest tests/.../job_analysis/domain -q` 綠。

### Task 2 — `OpksGenerationPayload` 擴充為四種 outcome

**檔案：** `app/job_analysis/application/persistence.py:232-252`

- `OpksGenerationOutcome` 從 2 值擴為 `proposed | needs_clarification | no_change | failed`（決定 28）。舊值 `no_grounded_candidates` 改名為 `no_change`：**先查本機 journal 是否已有該值**（`SELECT DISTINCT payload->>'outcome' FROM ... WHERE kind='opks_generation'`）；有就加一個 deserialize alias，沒有就直接改。決定寫進 commit message。
- 新增 `analysis_input_digest: NonEmptyText`、`gap_issue_ids: tuple[Identifier, ...] = ()`。
- validator 寫死一致性（決定 28）：`proposed` 必須有 `proposal_ids` 且無 gap；`needs_clarification` 必須有 `gap_issue_ids`，**`proposal_ids` 仍可非空**；`no_change` 兩者皆空；`failed` 兩者皆空。`gap_issue_ids` 唯一。

**紅測試：** 四種 outcome 的合法與非法組合；`needs_clarification` + 非空 `proposal_ids` 必須**通過**（這是決定 28 的重點，不要寫反）。

**Gate：** application 單元測試綠。

### Task 3 — `analysis_input_digest` 與 child ID 推導

**檔案：** 新增 `app/job_analysis/application/opks_digest.py`

- `compute_analysis_input_digest(task: Task) -> str`：納入 Task 語意欄位（`statement`／`action`／`object`／`purpose_result`／`context`／`enablers`）與**當前有效且實際投影的** employee evidence（決定 12）。
- **投影規則必須與 `build_opks_context_packet` 同源**（`opks_context.py:135-144` 的 `effective_support_links` ∩ `{EMPLOYEE_TURN, DIRECT_EDIT}`）。把該篩選抽成一個共用 helper 兩邊呼叫；兩份各寫一次遲早失步，gate 就會與實際輸入不同步。
- **排除** `CurrentJdOpks` items、`OpksProposal` 狀態（ping-pong，決定 13）與 `rejection_reason`（付費 reject loop，決定 14）。加一筆測試把這三者變動後 digest 不變釘住。
- 決定性且跨 process 穩定：排序後的 canonical JSON + `hashlib.sha256`，**不得用 Python 內建 `hash()`**（PYTHONHASHSEED 隨機化）。
- `ScheduledOpks { task_id, analysis_input_digest }`（放 `application/opks_digest.py` 或 `persistence.py`，與 Task 4 一致即可）。
- `scheduled_opks_operation_id(scheduled) -> f"opks:auto:{task_id}:{digest}"`（決定 7）。

**紅測試：** 同輸入同 digest、語意欄位任一變動 digest 變、新增有效員工 evidence digest 變、OPKS/Proposal/rejection_reason 變動 digest **不**變、跨 process 穩定（子行程算一次比對）。

**Gate：** application 單元測試綠。

### Task 4 — `CompletedTurnPayload.scheduled_opks?`

**檔案：** `application/persistence.py:90-102`

- 新增 `scheduled_opks: ScheduledOpks | None = None`（決定 7）。
- **不**額外持久化 child operation ID —— 它由 `task_id` + digest 推導。
- 舊 entry（無此欄位）讀得回，`None` 表示該回合沒排定 child。

**紅測試：** 舊 payload JSON round-trip；帶 `scheduled_opks` 的 round-trip。

**Gate：** application 單元測試綠。

## Phase 2 — pre-gate 與排定

### Task 5 — pre-gate 純函式

**檔案：** 新增 `app/job_analysis/application/opks_scheduler.py`

`eligible_opks_candidates(state: JobAnalysisState) -> tuple[ScheduledOpks, ...]` —— **純函式，無 IO**，回傳已依 Current JD `display_order` 由小到大排序的候選（決定 6）。每個候選帶 `task_id` 與已算好的 digest。

條件（決定 3，缺一不可）：

- Task 在 Current JD；
- Work Model Task 為 `ACTIVE`（`TaskState`，`domain/task.py:71`）；
- 有 ≥1 筆仍有效的員工依據；
- 無指向該 Task 的 **active** 邊界／矛盾／證據不足 issue；
- 無指向該 Task 的 **active** OPKS gap（`is_active`，決定 20）；
- 無該 Task 的 pending／deferred OPKS Proposal；
- 本輪 `next_question` 未指向該 Task。

**「無相同 digest 的終端 receipt」這一條不在純函式裡** —— 它需要讀 journal。分兩層：純函式算出排序好的候選，application 端 `select_scheduled_opks()`（Task 6）依序對每個候選 `journal.get(document_id, scheduled_opks_operation_id(c))`，取第一個沒有 receipt 的。這保住「pre-gate 是純函式」的紀律（決定 2，沿用 0052 決定 1），也不需要新 query port。

**禁止：** `purpose_result` 硬條件（決定 4）；任何數量／長度／涵蓋度門檻（決定 5）。加兩筆測試把這兩條釘死——`purpose_result=None` 的 Task 必須 eligible；只有一筆短引文的 Task 必須 eligible。

**紅測試：** 七個條件各自單獨阻擋一次；多個 eligible 時取 `display_order` 最小；空集合回 `()`。

**Gate：** application 單元測試綠。

### Task 6 — 主回合在同一交易凍結唯一 child

**檔案：** `application/durable_turn.py:171-267`

- `commit_verified_turn` 在寫 journal **之前**，用 **post-transition** 的 `transition.state` 算 `select_scheduled_opks()`（新加的 Task 才排得到），寫進 `CompletedTurnPayload.scheduled_opks`。
- **一個已提交的員工回合最多綁定一個 child，綁定在 receipt 寫入時凍結**（決定 8）。沒有這一條，replay 會重跑 scheduler 改選下一個 Task，使同一個員工回合付兩次錢——這是本計畫最重要的單一不變量。
- `_require_same_replay`（:146）**不得**比對 `scheduled_opks`：replay 時不重算，一律以既存 payload 為準。
- `commit_verified_turn` 的回傳要能帶出 `scheduled_opks`（`TransitionResult` 外再回一個值，或包成一個小 dataclass）。replay 分支同樣要回既存 payload 的 `scheduled_opks`（決定 9 的前提）。

**紅測試：** 提交後 payload 帶正確 `scheduled_opks`；沒有 eligible 時為 `None`；**同一 operation_id replay 兩次回同一個 `scheduled_opks`，即使中間 state 已讓 scheduler 會選另一個 Task**（這筆測試就是決定 8 的守門員）。

**Gate：** `uv run pytest -k "durable_turn or scheduler"` 綠。

## Phase 3 — gap 的表示、產生與 receipt

### Task 7 — `uncertain` 從被丟棄變成 gap

**檔案：** `llm/opks_result.py`、`llm/opks_wire.py`、`llm/opks_prompt.py:24`、`application/opks_verifier.py:237`

- `uncertain` 的 `text` 從**強制空字串**改為**強制非空的缺口摘要**，`target_ordinal` 維持 0（決定 15）。prompt 同步改寫。
- **gap 不帶問句**（決定 16）—— 問句在提問當下由主顧問生成，讓 0048 決定 14（不得把 K/S 問成認領題）只住主顧問 prompt 一處。prompt 要明說「只寫缺什麼，不要寫成問句」。
- `opks_verifier.py:237` 的 `if item.decision is OpksDecision.UNCERTAIN: continue` 改成收集：`OpksVerificationReport` 新增 `gaps: tuple[OpksGap, ...]`，`OpksGap { entity_kind, summary }`。
- **`opks_result_v1` 的 JSON Schema 必須零變更**（決定 15）。跑 codegen 後用 `git diff` 確認（AGENTS：autocrlf，不要看原始 diff）。若 schema 真的變了，代表非空約束被寫進了 schema 而不是 validator —— 改回 validator 層。

**紅測試：** `uncertain` 帶空 text 被拒；帶非空 text 進 `report.gaps`；`gaps` 與 `changes` 可同時非空（決定 18 的 item-level 部分發布）；schema 位元組數與 property 數不變。

**Gate：** `uv run pytest -k opks` 綠 + schema `git diff` 為空。

### Task 8 — gap 落地成 `OpenIssue`，receipt 帶 digest 與 gap ids

**檔案：** `application/opks_generation.py:169-253`

- `report.gaps` → `OpenIssue(kind=INSUFFICIENT_EVIDENCE, subject_task_id=…, opks_axis=…, summary=gap.summary, source_anchors=…)`。
- issue id **決定性**：`f"{operation_id}-gap{index}"`，沿用既有 proposal_id 慣例（`:210`），**不得用 `uuid4()`**。
- `source_anchors` 至少一筆（`work_model.py:41-51` 的 validator 要求）：用該 Task 的有效員工 support 的 `SourceRef`。
- outcome：有 gap → `needs_clarification`（**`proposal_ids` 仍可非空**）；無 gap 有 proposal → `proposed`；兩者皆無 → `no_change`（決定 28）。
- payload 帶 `analysis_input_digest`（從 snapshot 帶進來，不重算）與 `gap_issue_ids`。
- Proposal、OpenIssue 與 receipt **在同一個 `commit_authority_change()` 交易寫入**（決定 30）—— open_issues 在 `state.work_model` 裡，順著現有 `next_state` 更新即可。

**紅測試：** gap → issue 的欄位對映；同一交易三者齊寫；operation 重跑產生相同 issue id；`needs_clarification` + 非空 proposals 的完整路徑。

**Gate：** `uv run pytest -k opks_generation` 綠。

### Task 9 — terminal 失敗寫 `failed` receipt，digest 漂移不寫

**檔案：** `application/opks_generation.py:158-166, 193-206`

- 目前 `_require_verified` 對非 VERIFIED 直接 raise。改為：**terminal 失敗（provider error／invalid output／refused／verifier rejected）寫一筆 `outcome=failed` 的 receipt 並正常回傳**（決定 29）。四種 outcome 在阻擋效果上等價，差別只在呈現與診斷。
- **digest 漂移 → abandon，不寫任何 receipt**（決定 10）。現行 `StaleAuthoritySnapshot`（:196、:203）就是這條路徑：維持 raise，讓呼叫端吞掉。**abandon 與 failed 必須分開**——用一次偶發競態永久壓住一個 digest 是錯的。
- **第一版不做 backoff、attempt counter、circuit breaker**（決定 29）。
- 誠實記一行：偶發 provider 抖動會永久壓住那個確切 digest，直到新 Evidence 使 digest 改變（ADR 後果段已載明）。

**紅測試：** 四種 terminal 失敗各寫一筆 `failed` receipt；寫過 `failed` 後同 digest 的 candidate 不再被 `select_scheduled_opks()` 選中；digest 漂移**不**留 receipt，且下一輪同 digest 仍可被選中。

**Gate：** `uv run pytest -k opks_generation` 綠。

## Phase 4 — 追問與無副作用的解決通道

### Task 10 — packet 的 active／terminal 分區與 agenda 順序

**檔案：** `application/context.py:99-105, 244-251`

- **只有 active issue 進 `open_issues` 並取得 ordinal**（決定 20）。
- terminal issue 留在 `work_model.open_issues`，但在 packet **另開一區呈現、不配發 ordinal** —— 這是關鍵：ordinal 是模型唯一的指認手段，不配發就結構性地讓模型無法再次「解決」它，也不用靠 prompt 約束。該區的語意只有一個：「已問過、勿重問」的 context memory。
- agenda 順序（決定 21）：Task 邊界矛盾／責任問題 → 一般 open issue → **OPKS gap** → 遺漏掃描。
- gap 呈現要讓主顧問看得到它綁哪個 Task、缺哪一軸，**但不給問句**（決定 16）。

**紅測試：** terminal issue 不在 `open_issues`、不佔 ordinal、出現在 memory 區；active issue ordinal 連號；agenda 四段順序。

**Gate：** `uv run pytest -k context` 綠。

### Task 11 — 第三個頂層陣列 `issue_resolutions[]`

**檔案：** `llm/result.py:145-147`、`llm/wire.py`、`llm/schemas/task_analysis_result_v2.json`、`application/verifier.py`、`application/transition.py:261-268, 309-322`

- `IssueResolution { ordinal, resolution: answered | employee_unknown | not_applicable }`，扁平、每 issue 一筆（決定 22）。
- 加成 `TaskAnalysisResult` 的**第三個頂層陣列**，與 `work_signals` 平行。**不**把 gap resolution 綁在 `WorkSignal.disposition`（那會拖著該筆 signal 的副作用），**不**把 `resolves_open_issue_ordinal` 複數化。
- wire schema 維持 portable strict subset：改完重新量 property 數／anyOf 數／$defs 數／位元組數，記進 commit message（目前基準：2 props、0 anyOf、0 $defs、4,668 bytes）。
- **verifier 規則（決定 23）：`answered` 必須在同一輪有一筆與該 gap 的 `subject_task_id` 相關、且留下有效員工 Evidence 的 `WorkSignal`**，否則 digest 不變、OPKS 不會再分析，gap 會被假關閉。這是機械可判的跨欄位條件。
- verifier 另外檢查：ordinal 必須指向 **active** issue（terminal 沒有 ordinal，指過去就是無效 ordinal）。
- transition（決定 24）：`answered` 沿用現行語意（`_close_open_issue`，移出 `open_issues`）；`employee_unknown`／`not_applicable` **不移除**，寫入 `terminal_resolution` 後轉為 context memory。
- **resolution 的 `source_ref` 由 application 蓋，不進 wire**（決定 25）。
- 誠實記一行：`issue_resolutions[]` 給了模型一個新的偷懶出口，決定 23 只擋機械前提，其餘靠 rubric 與「specialist 下次仍會重提同一 gap」的自我修正，**verifier 擋不住**。

**紅測試：** 三種 resolution 的 transition 行為；`answered` 無對應 WorkSignal 被 verifier 拒；ordinal 指向 terminal issue 被拒；wire round-trip。

**Gate：** `uv run pytest -k "result or verifier or transition"` 綠。

### Task 12 — 主顧問 prompt 接上 gap 與 `issue_resolutions`

**檔案：** `llm/prompt.py`

- 說明 agenda 中的 OPKS gap 區與 memory 區怎麼讀。
- 一次問一題，沿用既有單一 active question，**不開第二套對話狀態機**（決定 34–35）。
- 明寫 0048 決定 14 的禁令：K/S 缺口一律問行為與實例，**不得**問成「你具備 X 能力嗎」的認領題。
- 說明 `issue_resolutions[]` 三值的用法與 `answered` 的前提（同輪必須有留下員工證據的 signal）。

**紅測試：** prompt 快照測試（若既有 prompt 有快照 net 就沿用；沒有就只做 lint／格式檢查，不新造測試框架）。

**Gate：** `uv run pytest -k prompt` 綠。

## Phase 5 — Task 離開 Current JD 時的清理

### Task 13 — 擴充 prune seam 終結 gap issue

**檔案：** `application/opks_authoring.py:72`、`application/authoring.py:526`、`application/proposal_decisions.py:632`

- **`prune_opks_for_current_jd()` 現行簽章只收／回 `CurrentJdOpks`，碰不到 `work_model.open_issues`**（決定 26）。加一個相鄰純函式 `prune_opks_gaps_for_current_jd(open_issues, current_jd) -> tuple[OpenIssue, ...]`，或擴充同一 seam——兩者擇一，不要兩套。
- 在**同一個 authority transaction、同一批既有呼叫點**接上：Task delete、accepted withdraw、merge、split。
- **merge／split 一律終結 gap，不遷移**（決定 27），沿用既有政策「不把舊 refs 猜接到 replacement Task」。

**紅測試：** 四個呼叫點各一筆；merge／split 後 gap 被終結而非搬到 replacement Task；非 OPKS 的 open issue 不受影響。

**Gate：** `uv run pytest -k "authoring or proposal_decisions"` 綠。

## Phase 6 — `/turns` 接上 child

### Task 14 — 主回合後執行 scheduled child

**檔案：** `app/api/routes/job_analysis.py`（`/turns` 路徑）或其 service 殼

- 主回合 commit 後，若 payload 帶 `scheduled_opks`：以 `scheduled_opks_operation_id()` 推導的 ID 呼叫 `generate_opks_proposals()`。
- **replay 若發現 scheduled child 尚無 receipt，恢復同一個 child**（同 `task_id` ＋ 同 digest，決定 9）—— 涵蓋「主回合 commit 後、child 執行前 crash」。既有的 `_committed_replay`（`opks_generation.py:120`）已能認出已完成的 child 並直接回傳。
- **digest 漂移則 abandon**（決定 10）：吞掉 `StaleAuthoritySnapshot`，不寫 receipt，不影響 `/turns` 回應。
- **`/turns` 最多執行主顧問 ＋ 一個 OPKS specialist**（決定 34），員工只看到一個「分析中」。
- **child 失敗不改 `/turns` 狀態碼**（決定 32）。回傳最新 ConsultationView。

**紅測試（fake adapter，不打 live）：** 排定 → child 跑完 → 同一回應看得到新 Proposal／gap；child 失敗 → `/turns` 仍 200 且主回合結果完好；同 Idempotency-Key replay 兩次只付一次；「主回合已 commit、child 未跑」的 crash 模擬在下一次 replay 恢復同一 child。

**Gate：** `uv run pytest -k "turns or job_analysis_routes"` 綠。

## Phase 7 — API 與 Web

### Task 15 — 退役手動生成端點與按鈕

**檔案：** `app/api/routes/job_analysis.py:202-230`、`apps/web/src/components/workspace/OpksEditor.tsx:260-276`、`apps/web/src/lib/jobAnalysisApi.ts:182`、`apps/web/src/lib/jobAnalysisApi.test.ts:221`

- 移除 `POST /{document_id}/tasks/{task_id}/opks-proposals` 與對應 web client、按鈕與測試（決定 1）。
- **保留**員工手動新增／編輯／刪除 O/P/K/S 的端點與 UI。
- 在 `docs/design/task-analysis-engine.md` 記一條退役禁令（AGENTS 規則 7 的 dual-audience 清單）：這個端點與按鈕**不得**復活；OPKS 的唯一 AI 入口是主回合排定的 child。

**Gate：** api 測試綠 + `npm run test` + `npx tsc --noEmit` + `npm run lint` 綠。

### Task 16 — Web 三態狀態呈現

**檔案：** `app/api/job_analysis_mapper.py`（ConsultationView）、`apps/web/src/components/workspace/OpksEditor.tsx`

- 狀態僅呈現三種措辭（決定 36）：**尚未適合分析／尚有待確認資訊／已可提出建議**，措辭受 0052 決定 7 約束。
- **不做**完成百分比、不宣稱「OPKS 已完整」、不做進度 dashboard。
- **不做** gap 側邊聊天、不做問題卡（決定 35）—— gap 只由主顧問在同一聊天室問，一次一題。
- 三態由已有的資料推導（是否有 active gap／是否有 pending Proposal／pre-gate 是否通過），**不新增第二份狀態真相**。

**Gate：** `npm run test` + `npx tsc --noEmit` + `npm run lint` 綠。

## Phase 8 — vertical 驗收

### Task 17 — PostgreSQL 端到端 vertical（fake adapter）

一條測試走完 ADR 的驗收流程，全部落 PostgreSQL、中途重載一次：

```text
員工訪談 → Task 穩定並進入 Current JD → 自動排定 OPKS
→ 有依據的部分產生 Proposal → 缺資料的部分形成 gap
→ 主顧問稍後追問 → 員工回答 → 自動重新分析
→ 員工接受／編輯／拒絕 OPKS → reload 後狀態一致
```

另外釘住三條付費邊界：同一回合只付一次；同一 digest 只付一次；拒絕 Proposal **不**觸發重分析（決定 14）。

**Gate：** `npx turbo test` 全綠（api + web + indexer + pdf-to-json）。此處打 git tag。

### Task 18 — live smoke（**需 owner 當次授權**）

**不得自行執行。** 依既有規矩：每次付費都要**當次授權且指名金額**，並先窮盡免費重放。本 Task 只負責準備 `run_live.py` 腳本與預期觀察點，執行前停下來問。

觀察點：specialist 是否真的在證據薄時回 `uncertain` 而非硬編；gap 摘要是否寫成問句（違反決定 16）；主顧問是否把 K/S 問成認領題（違反 0048 決定 14）；`issue_resolutions[]` 是否被當成偷懶關閉的出口（ADR 後果段已承認 verifier 擋不住，只能靠實測看）。

## 執行順序摘要

```text
Phase 1 (T1–T4)  domain／persistence 形狀，無行為改變
Phase 2 (T5–T6)  pre-gate 純函式 + 主回合凍結唯一 child   ← 決定 8 是最重要的不變量
Phase 3 (T7–T9)  gap 的表示、落地與四種終端 receipt
Phase 4 (T10–T12) agenda 分區 + issue_resolutions[] + prompt
Phase 5 (T13)    Task 離開 Current JD 的清理
Phase 6 (T14)    /turns 接上 child，replay 與 abandon
Phase 7 (T15–T16) 退役按鈕 + 三態呈現
Phase 8 (T17–T18) vertical 驗收 + live smoke（需授權）
```

Phase 1–2 之間、Phase 3 內部各 Task 有順序相依；Phase 5 與 Phase 3–4 無相依，可提前做。Phase 7 必須在 Phase 6 之後（不能先拆掉唯一入口再接新入口）。
