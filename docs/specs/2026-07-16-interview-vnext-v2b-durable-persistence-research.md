# Interview AI vNext V2-B——Durable Persistence、Outbox 與 Crash Recovery 規格

- 日期：2026-07-16（Asia/Taipei）
- 狀態：**實作交接規格已核准；程式與 migration 尚未開始**
- 主架構：[`2026-07-16-interview-ai-vnext-greenfield-architecture.md`](2026-07-16-interview-ai-vnext-greenfield-architecture.md)
- 上游 contract：[`2026-07-16-interview-vnext-v2-provider-capture-research.md`](2026-07-16-interview-vnext-v2-provider-capture-research.md)
- 執行清單：[`../plans/2026-07-16-interview-vnext-v2b-durable-persistence-plan.md`](../plans/2026-07-16-interview-vnext-v2b-durable-persistence-plan.md)
- 決策依據：ADR 0034；本文細化 persistence seam，沒有改變 ADR 的 greenfield 邊界

---

## 1. 交接結論

V2-B 要做的不是「把幾個 Pydantic model 存進資料庫」，而是建立一條可證明以下性質的 durable boundary：

1. employee turn 先持久化，provider call 才能開始；
2. domain state、command/result artifact、checkpoint、execution event 與 outbox 在需要原子一致時，由**同一個 PostgreSQL transaction**提交；
3. provider call 與外部 exporter 永遠在 transaction 外，不長時間持有 DB connection/row lock；
4. state mutation 使用 explicit compare-and-swap（CAS）版本；run event sequence 與 outbox queue 才使用短命 row lock；
5. process 在任何 checkpoint 中斷後，可由 committed record 決定「繼續、等待、reconcile、retry 或直接回既有結果」，不靠記憶體中的 agent state；
6. outbox 提供 at-least-once delivery，不聲稱 exactly-once；consumer/exporter 必須以 `event_id` 冪等；
7. vNext 使用全新 tables，不共用、不雙寫、不刪改 v3 interview rows。

第一版採 **一列 canonical aggregate state + immutable command/result artifacts**，不先建立 `evidence/inference/episode/candidate` 的第二套正規化權威表。V5 有真實查詢需求時，再加可重建 read projection。這可避免一人團隊在還沒有 runtime query 前，就維護兩份會漂移的 domain graph。

## 2. 現況與相容基線

### 2.1 已存在、不得重做的 contract

`apps/api/app/interview_vnext/` 已有：

- immutable `InterviewState`、typed commands、pure reducers、stable state hash；
- provider-neutral `OperationSpec`、`ModelCallRequest`、`ModelCallResult`；
- `ArtifactRecord`、`ExecutionEvent`、`RunManifest`；
- `OutboxRecord` state machine；
- multi-attempt `OperationCheckpoint` state machine；
- in-memory fake 與 committed JSON Schemas/taxonomy。

V2-B 必須把這些 contract 持久化，不得另創一套語意相近但欄位不同的 DB DTO。ORM row 只存在 adapter；讀回後必須重新經 Pydantic model validation。

### 2.2 目前基礎設施

- local/CI PostgreSQL image 是 `postgres:16`；因此 migration 必須以 PostgreSQL 16 為最低相容版本，不使用 17/18-only SQL。
- 專案目前 pin `SQLAlchemy 2.0.35`、`Alembic 1.13.3`、`asyncpg 0.30.0`。
- 截至 2026-07-16，官方 current stable 分別是 SQLAlchemy 2.0.51、Alembic 1.18.5、asyncpg 0.31.0。SQLAlchemy 2.0.48 之後也修過 engine concurrency 相關 critical issue；因此 V2-B-0 要先在**獨立 commit**更新這三個 patch/minor pin、重鎖 `uv.lock`、跑完整 regression，再開始 migration。若相依套件不相容，保留 SQLAlchemy 2.0 API，但把版本阻擋證據寫入 plan，不可靜默跳過。[SQLAlchemy 2.0 changelog](https://docs.sqlalchemy.org/en/20/changelog/changelog_20.html)、[Alembic changelog](https://alembic.sqlalchemy.org/en/latest/changelog.html)、[asyncpg releases](https://github.com/MagicStack/asyncpg/releases)
- 不升 SQLAlchemy 2.1 prerelease，不因「最新」改用未穩定 major。

### 2.3 尚未存在的 tenant/auth seam

現行 `JobProfile` 只有 `user_id`，route 仍以 query param 暫代正式身份；vNext domain 已要求 `tenant_id`。V2-B 的責任是：

- 保存 application 傳入的 authoritative `tenant_id`；
- 所有 vNext lookup/update 都帶 `tenant_id`；
- 用 composite foreign key 阻止 vNext tables 彼此跨 tenant 串接；
- `profile_id` 仍 FK 到既有 `job_profiles.id`，`ON DELETE RESTRICT`。

V2-B **不得自行假設 `tenant_id == user_id`**。V5/V7 接 route 前，必須另完成「已認證 principal → tenant → profile ownership」驗證，並更新 profile deletion use case；否則 production gate 不得通過。

## 3. 已閱讀的一手資料與直接設計影響

| 一手資料 | 官方事實 | 本規格的落地方式 |
|---|---|---|
| [PostgreSQL 18 `SELECT` locking clause](https://www.postgresql.org/docs/current/sql-select.html) 與 [PostgreSQL 16 同頁](https://www.postgresql.org/docs/16/sql-select.html) | `SKIP LOCKED` 會產生不一致視圖，不適合一般查詢，但適合多 consumer 的 queue-like table | 只用在 outbox lease；不拿它讀 session state、checkpoint 或 domain aggregate |
| [PostgreSQL transaction isolation](https://www.postgresql.org/docs/current/transaction-iso.html) | `READ COMMITTED` 是預設；每個 statement 看自己的 committed snapshot；Serializable 需要普遍處理 `40001` retry | V2-B 先用 `READ COMMITTED` + explicit CAS/短 row lock；不把整個 app 切 Serializable |
| [PostgreSQL explicit locking](https://www.postgresql.org/docs/current/explicit-locking.html) | row lock 不阻擋一般 reader，只阻擋同列 writer/locker；lock 到 transaction 結束才釋放 | run sequence/outbox lease transaction 必須短；provider/exporter network call 不得在 lock 內 |
| [PostgreSQL partial indexes](https://www.postgresql.org/docs/16/indexes-partial.html) | partial index 只收符合 predicate 的 rows，適合固定狀態子集 | pending/retry/expired lease 各建 partial index，不替 delivered 歷史建立無用 queue index |
| [SQLAlchemy async session](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html) | `AsyncSession` 是 mutable stateful transaction；concurrent tasks 必須一 task 一 session | UoW/session 只屬單一 coroutine；outbox concurrency test 使用兩個獨立 sessions |
| [SQLAlchemy session basics](https://docs.sqlalchemy.org/en/20/orm/session_basics.html) | Session/AsyncSession 不是可跨 task 共用的全域 cache | composition root 注入 `async_sessionmaker`，不是長命 `AsyncSession` |
| [SQLAlchemy version counter](https://docs.sqlalchemy.org/en/20/orm/versioning.html) | ORM `version_id_col` 只在 flush individual ORM rows 生效，不保護 bulk UPDATE | session/checkpoint 使用明確 `UPDATE ... WHERE revision = :expected RETURNING`，不依賴 mapper 魔法 |
| [SQLAlchemy `with_for_update`](https://docs.sqlalchemy.org/en/20/core/selectable.html#sqlalchemy.sql.expression.GenerativeSelect.with_for_update) | PostgreSQL dialect可產生 `FOR UPDATE SKIP LOCKED` | 一般 repository 用 SQLAlchemy 2.0 statements；outbox complex CTE 可用 `text()` 並有 SQL integration test |
| [AWS transactional outbox](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html) | business update 與 outbox 同 transaction；rollback 不可留下 event；可能重送，consumer 要冪等；順序需要保存 | event row + outbox row同 transaction；event ID是 message ID；同 run 同時最多一個未完成 delivery |
| [Alembic autogenerate](https://alembic.sqlalchemy.org/en/latest/autogenerate.html) | autogenerate 必須人工 review；CHECK/部分 constraint 不能可靠偵測 | 0010 migration手工撰寫/審查；schema introspection test明查 constraint/index，不接受「autogenerate 沒 diff」當驗收 |

上述資料支援的是 concurrency/persistence primitives；以下 table layout 與 transaction protocol 是依 Caliburn contract 做出的工程推論，不是假稱 PostgreSQL/AWS 官方提供了本專案完整 schema。

## 4. 資料權威與儲存格式

### 4.1 四種資料角色不得混用

| 角色 | 權威資料 | 可否更新 | 用途 |
|---|---|---:|---|
| materialized working state | `interview_vnext_sessions.state_json` | CAS 更新 | 快速載入當前 aggregate |
| replay/audit artifacts | command、reduction、request、response、verification等 artifact | 不可 UPDATE | 重播、比對、追查品質 |
| execution history | hash-chained execution event + run manifest | 不可 UPDATE | workflow trajectory、eval、observability |
| delivery state | outbox status/lease/error | 可依 state machine 更新 | 把 committed event 至少一次送到外部 consumer |

execution event 不是完整 event-sourcing payload；完整 command/result/state 留在 artifact。只靠 event table 不得宣稱能重建 domain state。

### 4.2 為什麼 canonical JSON 使用 `TEXT`，不是直接把 hash 原文放 JSONB

`canonical_json()` 對 UTF-8 bytes 做 hash。JSONB 會解析並以資料庫內部形式保存，不能保證取回原始 byte representation。因此：

- `state_json`、`event_json`、`checkpoint_json`、outbox 的 immutable `event_json`、artifact `inline_content` 都用 `TEXT` 保存 exact canonical string；
- query 需要的欄位另外正規化成 UUID/text/timestamp columns；
- DB 用 `jsonb_typeof(column::jsonb) = 'object'` 擋掉非 JSON object，但 canonical ordering/hash 仍由 Python validator 驗證；
- repository write 前先 Pydantic validate → `canonical_json()` → hash；read 後 `json.loads()` → Pydantic validate → 重算 canonical string/hash，不相等即 `PersistedDataCorruption`，不可「修一修繼續」。

### 4.3 第一版不做 domain child normalization

V2-B 不建立 `interview_vnext_evidence/inferences/episodes/gaps/candidates/reviews/turns` 權威表，理由是：

- `InterviewState` 有大量雙向 closure/lineage invariant，拆表後需要一套第二寫入模型；
- V2-B/V3 尚無線上跨 session 查詢需求；
- command/reduction artifacts 已保留 immutable 歷史；
- aggregate 大小可先由 metrics 驗證，不憑想像提前導入 projection drift。

V5 若 Web/reporting 需要查單一 candidate/evidence，新增 `interview_vnext_*_projection` tables；projection 必須帶 `source_state_hash`，可刪除重建，不成為 reducer 的 input authority。

## 5. PostgreSQL schema：固定八張表

所有欄位名稱、nullability 與唯一性如下。實作者若要增刪欄位，先更新本文與 migration plan，不得現場自行猜。

### 5.1 `interview_vnext_sessions`

| 欄位 | 型別 | Null | 語意 |
|---|---|---:|---|
| `session_id` | UUID PK | 否 | domain session ID |
| `tenant_id` | UUID | 否 | 所有查詢的第一 scope |
| `profile_id` | UUID FK | 否 | `job_profiles.id`, delete restrict |
| `architecture_id` | TEXT | 否 | 必須等於 `interview-vnext-evidence-workflow` |
| `workflow_version` | TEXT | 否 | SemVer |
| `reference_snapshot_id` | TEXT | 否 | immutable reference identity |
| `status` | TEXT | 否 | planned/active/paused/finishing/completed/failed |
| `state_version` | BIGINT | 否 | `>= 0`，CAS token |
| `state_schema_version` | TEXT | 否 | 初始為 `interview_state.v2` |
| `state_json` | TEXT | 否 | canonical full `InterviewState` |
| `state_hash` | TEXT | 否 | `sha256:<64 lowercase hex>` |
| `initial_state_artifact_id` | UUID FK | 是 | 第一個 run建立後必填；immutable version-0 state snapshot |
| `created_at` | TIMESTAMPTZ | 否 | domain UTC time |
| `updated_at` | TIMESTAMPTZ | 否 | 不早於 created_at |

Constraints/indexes：

- `uq_ivn_sessions_tenant_session (tenant_id, session_id)`，供 composite FK；
- `ix_ivn_sessions_tenant_profile (tenant_id, profile_id, updated_at DESC)`；
- status、hash、`state_version >= 0`、JSON object、時間順序 CHECK；
- initial-state FK在 artifacts table建立後加入；任何 command前，application必須確認此欄非 null；若 `state_version > 0`仍為 null，視為 persisted corruption；
- 不建立「同 profile 一個 active」partial unique，因產品是否允許平行訪談要由 V4/V5 明確決定，不能沿用 v3 假設。

### 5.2 `interview_vnext_runs`

| 欄位 | 型別 | Null | 語意 |
|---|---|---:|---|
| `run_id` | UUID PK | 否 | 一次 durable workflow run |
| `tenant_id` | UUID | 否 | tenant scope |
| `session_id` | UUID | 否 | composite FK 到 session |
| `architecture_id` | TEXT | 否 | 與 session/event 一致 |
| `workflow_version` | TEXT | 否 | 本 run 固定版本 |
| `taxonomy_id` | TEXT | 否 | execution taxonomy identity |
| `taxonomy_version` | TEXT | 否 | taxonomy SemVer |
| `taxonomy_hash` | TEXT | 否 | taxonomy canonical hash |
| `status` | TEXT | 否 | open/completed/failed |
| `event_count` | BIGINT | 否 | 初始 0，由 append event transaction遞增 |
| `first_event_hash` | TEXT | 是 | event_count=0 時必須 null |
| `last_event_hash` | TEXT | 是 | event_count=0 時必須 null |
| `manifest_artifact_id` | UUID FK | 是 | application-level terminal invariant；FK 在 artifacts 建好後加入，DB lifecycle CHECK 不要求 terminal 非 null |
| `started_at` | TIMESTAMPTZ | 否 | run start |
| `completed_at` | TIMESTAMPTZ | 是 | terminal run 必填 |

Constraints/indexes：

- `uq_ivn_runs_tenant_run (tenant_id, run_id)`；
- composite FK `(tenant_id, session_id)`；
- `ix_ivn_runs_tenant_session_started (tenant_id, session_id, started_at, run_id)`；
- event_count/hash coherence CHECK；open 必須同時沒有 completion/manifest；terminal 在 DB CHECK 只要求 `completed_at` 非 null、`event_count >= 1`、completion不早於 start；
- finalize 必須先 append `workflow.run.completed|failed`，再以包含該 event 的 chain 建 manifest。

`terminal → manifest_artifact_id IS NOT NULL` **刻意不放進 DB CHECK**。原因是 manifest pointer需要在測試清理、資料維護或未來受控刪除前暫時清空；若 row-local CHECK硬綁 terminal manifest，§12.1 的合法 FK cleanup就無法執行。完整性改由四層共同保證：

1. `WorkflowRun` DTO validator拒絕 terminal + null manifest；
2. `RunRepository.finalize()` 在同一 transaction一次設置 terminal status、`completed_at`與 manifest pointer；
3. repository hydrate任何 terminal row時重跑 DTO validator，null manifest回 `PersistedDataCorruption`；
4. finalize rollback/read-corruption integration tests。

因此 DB 允許的是「管理/cleanup可暫時解除 pointer」，application runtime不允許把該狀態當合法 `WorkflowRun` 使用。不要改用 DEFERRABLE FK，也不要為 cleanup把 terminal run偽造回 open。

### 5.3 `interview_vnext_artifacts`

| 欄位 | 型別 | Null | 語意 |
|---|---|---:|---|
| `artifact_id` | UUID PK | 否 | `ArtifactRef.artifact_id` |
| `tenant_id` | UUID | 否 | persistence-only tenant scope |
| `record_schema_version` | TEXT | 否 | `execution_artifact.v1` |
| `run_id` | UUID | 否 | composite FK 到 run |
| `session_id` | UUID | 是 | 有值時 composite FK 到 session |
| `turn_id` | UUID | 是 | artifact metadata，不另建 FK |
| `operation_id` | UUID | 是 | artifact metadata |
| `attempt_id` | UUID | 是 | artifact metadata |
| `kind` | TEXT | 否 | StableName |
| `media_type` | TEXT | 否 | exact media type |
| `schema_id` | TEXT | 是 | payload contract ID |
| `content_hash` | TEXT | 否 | exact UTF-8 content hash |
| `byte_size` | BIGINT | 否 | UTF-8 bytes，`>= 0` |
| `storage` | TEXT | 否 | inline/external |
| `inline_content` | TEXT | 是 | inline 時唯一 location |
| `external_uri` | TEXT | 是 | external 時唯一 location |
| `retention_class` | TEXT | 否 | StableName |
| `redaction_status` | TEXT | 否 | not_required/applied/unknown |
| `contains_test_data` | BOOLEAN | 否 | default false |
| `created_at` | TIMESTAMPTZ | 否 | immutable creation time |

Constraints/indexes：

- `uq_ivn_artifacts_tenant_artifact (tenant_id, artifact_id)`；
- composite FK 到 run；nullable composite FK 到 session；
- storage/location exclusive CHECK；hash/byte size/stable-name CHECK；
- `ix_ivn_artifacts_tenant_session_created`、`ix_ivn_artifacts_operation_attempt`；
- trigger `ivn_artifacts_reject_update` 拒絕所有 UPDATE；repository 不提供 delete；所有 FK 使用 RESTRICT；
- V2-B repository **只接受 inline writes**。Table 先保留 external shape，但在有能驗 hash/size 的 object-store adapter 前，external write 回 stable `external_artifact_store_unavailable`。

### 5.4 `interview_vnext_commands`

每個成功套用的新 command 一列；duplicate invocation 讀既有列，不新增第二列。

| 欄位 | 型別 | Null | 語意 |
|---|---|---:|---|
| `command_id` | UUID PK | 否 | reducer idempotency identity |
| `tenant_id` | UUID | 否 | scope |
| `session_id` | UUID | 否 | target session |
| `run_id` | UUID | 否 | 產生此 command 的 run |
| `request_idempotency_key` | TEXT | 是 | 未來 transport/client key；不可取代 command ID |
| `command_schema_id` | TEXT | 否 | committed schema ID |
| `command_artifact_id` | UUID FK | 否 | canonical typed command |
| `command_hash` | TEXT | 否 | duplicate payload comparison |
| `reduction_artifact_id` | UUID FK | 否 | canonical `ReductionResult`，含 full state/events |
| `reduction_hash` | TEXT | 否 | result artifact hash |
| `expected_state_version` | BIGINT | 否 | command input version |
| `result_state_version` | BIGINT | 否 | 必須等於 expected + 1 |
| `result_state_hash` | TEXT | 否 | committed state hash |
| `result_reason_code` | TEXT | 否 | 新列應為 `applied` |
| `occurred_at` | TIMESTAMPTZ | 否 | domain command time |
| `committed_at` | TIMESTAMPTZ | 否 | DB use case commit time |

Constraints/indexes：

- `uq_ivn_commands_tenant_session_command`；
- partial unique `uq_ivn_commands_request_key` on `(tenant_id, session_id, request_idempotency_key)` where key is not null；
- composite FK 到 session/run/artifacts；hash/version/time CHECK；
- trigger 拒絕 UPDATE；repository 不提供 delete。

duplicate 規則：相同 `command_id` 或 request key + 相同 `command_hash` 回既有 reduction；相同 key + 不同 hash 回 `IdempotencyConflict`。絕不 `ON CONFLICT DO UPDATE`。

`ReductionResult` 是 command replay的完整 immutable payload，V2-B 必須新增固定 discriminator `schema_version = "reduction_result.v1"`，並發布 `reduction-result.v1.schema.json`；artifact `schema_id` 使用該 schema的完整 `$id`。不得把無 schema identity 的任意 dict當 reduction artifact。

### 5.5 `interview_vnext_execution_events`

| 欄位 | 型別 | Null | 語意 |
|---|---|---:|---|
| `event_id` | UUID PK | 否 | execution event ID |
| `tenant_id` | UUID | 否 | scope |
| `run_id` | UUID | 否 | chain owner |
| `session_id` | UUID | 否 | vNext interview run必須屬於一個 session；DB adapter刻意收窄 envelope 的 optional shape |
| `turn_id` | UUID | 是 | query key |
| `operation_id` | UUID | 是 | query key |
| `parent_operation_id` | UUID | 是 | nested operation query key |
| `attempt_id` | UUID | 是 | query key |
| `attempt` | INTEGER | 是 | `>=1`，與 attempt_id 同時有/無 |
| `event_schema_version` | TEXT | 否 | `execution_event.v1` |
| `event_type` | TEXT | 否 | open StableName，由 taxonomy validation |
| `stage` | TEXT | 否 | open StableName，由 taxonomy validation |
| `status` | TEXT | 否 | ok/partial/failed/skipped |
| `sequence` | BIGINT | 否 | run 內從 1 連續 |
| `previous_event_hash` | TEXT | 是 | sequence=1 時 null |
| `event_hash` | TEXT | 否 | canonical event body hash |
| `event_json` | TEXT | 否 | exact canonical full `ExecutionEvent` |
| `occurred_at` | TIMESTAMPTZ | 否 | event time |
| `created_at` | TIMESTAMPTZ | 否 | persistence time |

Constraints/indexes：

- unique `(tenant_id, run_id, sequence)`；composite FK 到 run/session；
- sequence/hash/attempt/JSON object CHECK；
- `ix_ivn_events_tenant_session_occurred`、`ix_ivn_events_operation_attempt`；
- trigger 拒絕 UPDATE；
- artifact refs留在 canonical event JSON；append 前 repository 以同一 transaction批次讀取並比對所有 referenced artifacts 的完整 `ArtifactRef`。

event sequence 不由 caller 猜。`append_event()` 先 lock run row，使用 `event_count + 1` 與 `last_event_hash` 建 event，insert event/outbox，再更新 run counters。

### 5.6 `interview_vnext_outbox`

| 欄位 | 型別 | Null | 語意 |
|---|---|---:|---|
| `message_id` | UUID PK/FK | 否 | 必須等於 event ID |
| `tenant_id` | UUID | 否 | scope |
| `run_id` | UUID | 否 | delivery ordering group |
| `event_sequence` | BIGINT | 否 | run sequence |
| `event_hash` | TEXT | 否 | immutable payload integrity |
| `event_json` | TEXT | 否 | self-contained canonical event payload |
| `status` | TEXT | 否 | pending/leased/retry_wait/delivered/dead_letter |
| `delivery_attempts` | INTEGER | 否 | 每次 lease +1，初始 0 |
| `lease_owner` | TEXT | 是 | leased only |
| `lease_expires_at` | TIMESTAMPTZ | 是 | leased only |
| `next_attempt_at` | TIMESTAMPTZ | 是 | retry_wait only |
| `delivered_at` | TIMESTAMPTZ | 是 | delivered only |
| `last_error_code` | TEXT | 是 | retry_wait/dead_letter 必填 |
| `created_at` | TIMESTAMPTZ | 否 | event enqueue time=**持久化時間,用 DB 時鐘 `now()`**(2026-07-17 註記:lease/mark 的 `updated_at` 用 `CURRENT_TIMESTAMP`,若 enqueue 用 domain `occurred_at`,app/DB 時鐘差會違反 `updated_at >= created_at` CHECK) |
| `updated_at` | TIMESTAMPTZ | 否 | state transition time |

Constraints/indexes：

- FK message→event、composite FK tenant/run；unique `(tenant_id, run_id, event_sequence)`；
-完整 OutboxRecord status-shape CHECK；
- partial indexes：pending `(created_at,message_id)`、retry `(next_attempt_at,created_at,message_id)`、expired lease `(lease_expires_at,message_id)`；
- index `(tenant_id,run_id,event_sequence,status)` 支援同 run ordering；
- trigger 只允許 state/lease/error/time欄位依合法 transition 更新，拒絕改 identity/event payload。Python 仍先建完整 `OutboxRecord` 驗證；trigger 是第二道防線。

合法 DB transition固定為：

| Old | New | 額外條件 |
|---|---|---|
| pending | leased | attempts +1，新 owner非空，新 expiry在未來 |
| retry_wait | leased | `next_attempt_at <= CURRENT_TIMESTAMP`；attempts +1 |
| leased | leased | 舊 lease已到期；attempts +1；允許另一 owner接手 |
| leased | delivered | SQL WHERE驗證舊 owner與 lease未過期；清 lease/error，設 delivered_at |
| leased | retry_wait | SQL WHERE驗證 owner/expiry；清 lease，retry time在未來，保留 error code |
| leased | dead_letter | SQL WHERE驗證 owner/expiry；清 lease，保留 error code |

delivered/dead_letter 在 V2-B 都是 terminal；idempotent delivered由 repository先讀 existing直接返回，不送出 UPDATE。

### 5.7 `interview_vnext_operation_checkpoints`

| 欄位 | 型別 | Null | 語意 |
|---|---|---:|---|
| `checkpoint_id` | UUID PK | 否 | checkpoint ID |
| `tenant_id` | UUID | 否 | scope |
| `run_id` | UUID | 否 | owner run |
| `session_id` | UUID | 否 | target session |
| `turn_id` | UUID | 是 | target turn |
| `operation_id` | UUID | 否 | globally unique operation instance |
| `operation_name` | TEXT | 否 | stable operation |
| `operation_definition_hash` | TEXT | 否 | immutable operation identity |
| `idempotency_key` | TEXT | 否 | workflow identity |
| `status` | TEXT | 否 | prepared/calling/provider_completed/verified/committed/failed |
| `revision` | BIGINT | 否 | checkpoint CAS token，初始 0 |
| `checkpoint_schema_version` | TEXT | 否 | `operation_checkpoint.v1` |
| `checkpoint_json` | TEXT | 否 | exact canonical current checkpoint |
| `request_artifact_id` | UUID FK | 否 | prepared request |
| `active_attempt_id` | UUID | 是 | non-prepared 必填 |
| `active_attempt` | INTEGER | 是 | non-prepared 必填 |
| `provider_result_artifact_id` | UUID FK | 是 | provider_completed+ |
| `verification_artifact_id` | UUID FK | 是 | verified+ |
| `domain_result_artifact_id` | UUID FK | 是 | committed only |
| `response_artifact_id` | UUID FK | 是 | committed only |
| `failure_artifact_id` | UUID FK | 是 | failed only |
| `failure_reason_code` | TEXT | 是 | failed only |
| `state_before_hash` | TEXT | 否 | operation input state |
| `state_after_hash` | TEXT | 是 | committed only |
| `created_at` | TIMESTAMPTZ | 否 | prepared time |
| `updated_at` | TIMESTAMPTZ | 否 | latest transition time |

Constraints/indexes：

- unique `(tenant_id, operation_id)`；
- unique `(tenant_id, session_id, operation_name, idempotency_key)`；
- composite FK 到 run/session/artifacts；
- status-shape、hash、revision、JSON object、time CHECK；
- `save()` 必須 `WHERE checkpoint_id AND tenant_id AND revision=:expected RETURNING`；0 rows → rollback/reload，比對是否為相同 idempotent transition，否則 `CheckpointConflict`。

`attempt_result_artifacts` 的 ordered refs保存在 canonical checkpoint JSON；DB 中每次 attempt 的可查狀態由下一張表保存，hydration 時兩者必須一致。

### 5.8 `interview_vnext_operation_attempts`

| 欄位 | 型別 | Null | 語意 |
|---|---|---:|---|
| `attempt_id` | UUID PK | 否 | model attempt ID |
| `tenant_id` | UUID | 否 | scope |
| `run_id` | UUID | 否 | owner run |
| `session_id` | UUID | 否 | target session |
| `operation_id` | UUID | 否 | composite FK 到 checkpoint |
| `attempt` | INTEGER | 否 | operation 內從 1 連續 |
| `status` | TEXT | 否 | calling/result_recorded |
| `request_artifact_id` | UUID FK | 否 | exact `ModelCallRequest` artifact |
| `result_artifact_id` | UUID FK | 是 | result_recorded 必填 |
| `provider` | TEXT | 否 | resolved adapter stable name |
| `requested_model` | TEXT | 否 | request model identity |
| `provider_execution_ref_kind` | TEXT | 是 | optional opaque resume/reconcile ref kind |
| `provider_execution_ref` | TEXT | 是 | optional opaque ref；不是 evidence/domain state |
| `deadline_at` | TIMESTAMPTZ | 否 | retry/recovery deadline |
| `started_at` | TIMESTAMPTZ | 否 | calling start |
| `updated_at` | TIMESTAMPTZ | 否 | latest state |
| `completed_at` | TIMESTAMPTZ | 是 | result_recorded 必填 |

Constraints/indexes：

- unique `(tenant_id, operation_id, attempt)`；unique `(tenant_id, attempt_id)`；
- composite FK 到 checkpoint/run/session/artifacts；
- status/result/ref-pair/time CHECK；
-只有 `calling → result_recorded` 一次性 UPDATE；已記錄結果不可換 artifact；retry 必須 INSERT 新 attempt row。

目前 `LlmPort.generate_structured()` 是單次同步語意，沒有 start/poll API。V2-B 可以保存 opaque execution ref，但不得假裝所有 provider 都能 reconcile。V6 若 adapter 支援 background job，再以 optional `RecoverableLlmPort` 使用此欄；不支援時依 §9 的 deadline/retry policy。

## 6. ORM、port 與檔案邊界

新增檔案固定如下：

```text
apps/api/app/interview_vnext/application/
├─ persistence.py          # async Protocols；不 import SQLAlchemy
├─ durable_commands.py     # load → reducer → atomic commit use case
├─ durable_operations.py   # prepare/start/result/verify/commit/fail use cases
└─ recovery.py             # pure recovery decision + coordinator

apps/api/app/interview_vnext/persistence/
├─ models.py               # SQLAlchemy rows only
├─ serialization.py        # canonical text ↔ Pydantic + corruption errors
├─ repositories.py         # session/artifact/command/run/checkpoint/attempt repos
├─ capture.py              # durable append event + outbox atomic writer
├─ outbox.py               # lease/delivered/failed SQL queue adapter
├─ unit_of_work.py         # AsyncSession lifecycle；唯一 commit owner
└─ errors.py               # stable adapter exceptions

apps/api/tests/
├─ test_interview_vnext_persistence.py
├─ test_interview_vnext_outbox_postgres.py
├─ test_interview_vnext_recovery_postgres.py
└─ test_interview_vnext_migration.py
```

`observability.InMemoryOutbox`/`CaptureRecorder` 是同步 contract fake；async SQL adapter 不得用 `run_until_complete` 假裝實作它。新增 application async ports：

```python
class VNextUnitOfWork(Protocol):
    sessions: SessionRepository
    artifacts: ArtifactRepository
    commands: CommandRepository
    runs: RunRepository
    checkpoints: CheckpointRepository
    attempts: AttemptRepository
    capture: CaptureWriter

    async def __aenter__(self) -> "VNextUnitOfWork": ...
    async def __aexit__(self, exc_type, exc, tb) -> None: ...
    async def commit(self) -> None: ...
    async def rollback(self) -> None: ...
```

硬規則：

- repository 只 `flush/execute`，不得 `commit()`；
- UoW 一個 instance/AsyncSession只由一個 task 使用；
- composition root 注入 `async_sessionmaker[AsyncSession]`；
- use case 用 `async with uow:`，成功明確 `commit()`，未 commit/exception 自動 rollback；
- ORM row 不流入 domain/application；provider SDK object 不流入 persistence；
- 不把 vNext models加入現行 route dependency。Alembic `env.py` 可明確 import `interview_vnext.persistence.models` 以註冊 `Base.metadata`，production route仍不接線。

## 7. Atomic transaction protocols

### 7.1 建立 session

同一 transaction：

1. validate initial `InterviewState`；state/session identity、version 0、hash一致；
2. 確認 `profile_id` 存在；不要推導 tenant；
3. insert `interview_vnext_sessions`；
4. commit。

session bootstrap 尚未呼叫 provider。第一個 workflow run另由 `create_run()` 建立。

### 7.2 建立 workflow run

同一 transaction：

1. 以 `(tenant_id, run_id)` 查 duplicate；identity完全相同可回既有，不同則 `RunConflict`；
2. insert open run，event count初始0；
3. 若 session尚無 `initial_state_artifact_id`，只允許在 `state_version=0`時保存 `state.snapshot.initial` artifact（schema為 committed InterviewState schema），再更新 session pointer；
4. 立即 append `workflow.run.started` event + outbox，將 run chain推進到 sequence 1；
5. commit。

因此任何 committed run至少有 started event，且 session在第一個 command前已有 immutable version-0 snapshot。Run fail/complete也必須先 append terminal event，再建立 manifest；不會出現 event count 0卻 terminal的合法 committed狀態。

### 7.3 收到 employee turn／套用任何 domain command

provider call 前必須完成以下 transaction：

0. **先鎖 run row(`SELECT … FOR UPDATE`)——一致鎖序 run → session/artifacts**
   (2026-07-17 實作註記):不先鎖時,兩個併發 command 的 artifact/command INSERT
   會各自對 run/session row 持 FK `KEY SHARE` 鎖,與對方 step 6 的 session CAS 與
   step 7 的 `run FOR UPDATE` 形成互等,PostgreSQL 以 DeadlockDetected 收場(整合
   測試實測)。run row 本來就是 event chain 的序列鎖;提早取得讓同 run 寫入者
   序列化、死鎖結構性消失。transaction 仍短(pure reducer、無 network I/O)。
   連帶規則:等鎖期間同 command 已被別的 transaction commit → reducer 回
   idempotent,此時**查 command record 走 replay**(合法 race);record 缺席才是
   `PersistedDataCorruption`。
1. 以 `(tenant_id, session_id)` 查 duplicate command/request key；存在則比 `command_hash`，相同回既有 reduction，不寫新 event；不同則 conflict。
2. 讀 session row並 hydrate/重算 state hash。
3. 在 transaction 內執行 pure reducer；它不做 I/O，transaction 不會因此變長。
4. 建 command artifact與 reduction artifact，`put()` 只允許 immutable insert/idempotent same-record。
5. insert command row。
6. CAS update session：`WHERE state_version = command.expected_state_version`，同步更新 state JSON/hash/status/version。
7. append `state.transition.accepted` execution event；在 append內 lock run、insert event + outbox、更新 run chain。
8. commit。

若 CAS 0 rows，整筆 rollback，包括 artifacts/command/event/outbox。若是 concurrent duplicate造成 unique violation，rollback後開**新 transaction**讀既有 command再比 hash；不可在 failed `AsyncSession` 繼續查。

### 7.4 Prepare operation

同一 transaction：

1. load committed state；
2. 保存 prompt/schema/context/selection manifest與 `ModelCallRequest` artifacts；
3. 以 `(tenant,session,operation_name,idempotency_key)` 查 existing checkpoint；相同 request/definition/state hash回既有；不同 conflict；
4. insert `prepared` checkpoint；
5. append `workflow.step.started` event/outbox；
6. commit。

到此為止才允許啟動 attempt。

### 7.5 Start attempt

短 transaction：

1. load checkpoint + expected revision；
2. 用既有 pure transition `mark_calling()` 或 `start_next_attempt()` 產生 next checkpoint；
3. insert新 `operation_attempts` calling row；retry時前一 attempt 必須已 result_recorded；
4. checkpoint CAS update；
5. append `model.call.started` event/outbox；
6. commit。

commit 後才執行 `await llm.generate_structured(request)`。任何 provider network call都不在 UoW 裡。

### 7.6 Record provider result

provider 返回後開新 transaction。(2026-07-17 實作註記:V2-B 的
`record_attempt_result` 收呼叫端已分類的 outcome——succeeded/retryable/
non-retryable——與 canonical result artifact;typed `ModelCallResult` 的正規化
屬 V3 workflow 與 V6 provider adapter。因 attempt row 與 checkpoint 轉換同一
transaction,crash 後 durable 的「calling + result_recorded」組合**只可能**來自
retryable 結果,§9 的 recovery decision 因此不需重新解析 result。)

1. 保存 visible response/error與 canonical `ModelCallResult` artifacts；
2. `operation_attempts calling → result_recorded`，result artifact不可換；
3. 若 succeeded，checkpoint `calling → provider_completed`；
4. 若 retryable failure/incomplete且 policy還允許 retry，checkpoint保留 calling，但 result已在 attempt row與 checkpoint prior result list；下一 transaction再 start新 attempt；
5. 若 refusal/non-retryable/attempt exhausted，checkpoint `→ failed`；
6. append `model.call.completed|failed` event/outbox；
7. commit。

重送相同 result artifact為 idempotent；相同 attempt ID不同 result hash為 conflict。

### 7.7 Verification

同一 transaction保存 verification artifact、checkpoint `provider_completed → verified`、`verification.completed` event/outbox。Schema valid 不等於 semantic valid；verification rejected時建立 failure artifact並進 failed，不執行 reducer。

### 7.8 Commit verified proposal

同一 transaction：

1. hydrate current session state；
2. 若 checkpoint `state_before_hash`/command expected version已 stale，依 operation policy重新 prepare，不把舊 proposal硬套新 state；
3. 執行 reducer，保存 domain command/reduction/response artifacts；
4. insert command + CAS session；
5. checkpoint `verified → committed` CAS；
6. append state/workflow event與 outbox；
7. commit。

這裡 session、command、checkpoint、event、outbox 必須同生共死。checkpoint committed後讀 `domain_result_artifact/response_artifact`即可回覆，不重打 provider。

## 8. Outbox lease SQL 與 delivery protocol

### 8.1 Lease query

lease使用 DB `CURRENT_TIMESTAMP` 作跨 process權威時間，`lease_seconds`/`limit` 是有上限的 bind parameters。每個 run同時只允許最早的 non-terminal message進行 delivery：

```sql
WITH picked AS (
    SELECT o.message_id
    FROM interview_vnext_outbox AS o
    WHERE (
        o.status = 'pending'
        OR (o.status = 'retry_wait' AND o.next_attempt_at <= CURRENT_TIMESTAMP)
        OR (o.status = 'leased' AND o.lease_expires_at <= CURRENT_TIMESTAMP)
    )
      AND NOT EXISTS (
          SELECT 1
          FROM interview_vnext_outbox AS prior
          WHERE prior.tenant_id = o.tenant_id
            AND prior.run_id = o.run_id
            AND prior.event_sequence < o.event_sequence
            AND prior.status NOT IN ('delivered', 'dead_letter')
      )
    ORDER BY o.created_at, o.message_id
    FOR UPDATE OF o SKIP LOCKED
    LIMIT :limit
)
UPDATE interview_vnext_outbox AS o
SET status = 'leased',
    delivery_attempts = o.delivery_attempts + 1,
    lease_owner = :worker_id,
    lease_expires_at = CURRENT_TIMESTAMP + make_interval(secs => :lease_seconds),
    next_attempt_at = NULL,
    updated_at = CURRENT_TIMESTAMP
FROM picked
WHERE o.message_id = picked.message_id
RETURNING o.*;
```

`limit` 初始 default 100、hard max 500；`lease_seconds` 初始 default 60、允許 5–900。這些是 operational config，不寫進 domain contract。修改預設值不改 event schema，但要有 load test/metric依據。

### 8.2 Export transaction boundary

1. transaction A lease rows並 commit；
2. transaction外逐筆/批次呼叫 exporter；payload帶 `event_id/run_id/sequence/event_hash`；
3. 成功後 transaction B `mark_delivered`：WHERE status leased、owner一致、lease尚未過期；
4. 失敗後 transaction B `mark_failed`：有 retry time → retry_wait，否則 dead_letter；
5. exporter成功但 B commit前 process死掉，lease到期後會重送；consumer以 event ID去重。

不得在 network成功後 delete outbox row；delivered/dead_letter保留供稽核與重播。未來 retention另做明確 policy/migration。

### 8.3 Ordering 與 dead letter

- 同一 run只有最早 non-terminal message可 lease，因此正常路徑保持 sequence；不同 runs可平行。
- dead_letter視為 terminal，後續 sequence可繼續，但 hash chain會讓 downstream看見缺口；必須發 metric/alert。
- V2-B 將 dead_letter視為 terminal，不提供 replay method。未來若需要管理重播，要先版本化 outbox transition contract，保留原 event/message ID並新增 operator reason artifact；不可現在偷留未測後門。

## 9. Crash recovery decision table

recovery掃描的是 committed checkpoint；不得從「最後一則聊天文字」猜進度。

| Checkpoint | Durable facts | Recovery action | 可否呼叫 provider |
|---|---|---|---:|
| prepared | request/state-before已存；無 attempt | 建 attempt 1、commit calling，再呼叫 | 是，commit後 |
| calling，active attempt已有 retryable result | attempt row已 result_recorded；checkpoint尚未 append該 prior result | 依 policy執行 `start_next_attempt`，或額度耗盡時 failed | 新 attempt commit後才可 |
| calling，active attempt已有 non-retryable result | attempt row已 result_recorded | 以同 result/failure artifact把 checkpoint轉 failed | 否 |
| calling，deadline未到，無 recoverable ref | request可能已送出但結果未知 | 等到 deadline；不立即製造 duplicate | 否 |
| calling，有 recoverable ref且 adapter支援 | provider execution identity已存 | 呼叫 adapter `reconcile(ref)`；結果另開 transaction記錄 | 只可 reconcile，不可新 generate |
| calling，deadline已到，attempt仍有額度 | active attempt結果未知/失敗 | 先建立 explicit lost/timeout `ModelCallResult` artifact並完成舊 attempt，再 start下一 attempt | 是，新 attempt commit後 |
| calling，attempt額度耗盡 | 所有 attempt皆有結果或最後一個已 timeout | failure artifact + checkpoint failed | 否 |
| provider_completed | canonical provider result已存 | 執行 semantic verification | 否 |
| verified | accepted verification已存 |執行 idempotent reducer/CAS commit | 否 |
| committed | domain result/response/state-after已存 | 直接回既有 response/result | 否 |
| failed | terminal failure artifact/reason已存 | 回 stable failure；人工/新 operation才能重啟 | 否 |

Recovery coordinator每次只做一個 transition並 commit，之後重讀；不在一個超長 transaction跑完整 workflow。若兩個 recovery workers搶同 checkpoint，以 `revision` CAS決勝，loser rollback/reload；不得兩邊都 start新 attempt。

## 10. Stable persistence errors

adapter exceptions不直接暴露 SQLSTATE/constraint string：

| Exception | 條件 |
|---|---|
| `SessionNotFound` | tenant-scoped session不存在 |
| `StateVersionConflict` | session CAS 0 rows且不是 duplicate command |
| `IdempotencyConflict` | command/request key相同但 canonical hash不同 |
| `ArtifactConflict` | artifact ID相同但完整 record不同 |
| `ArtifactNotFound` | required ref不存在或 ref metadata不符 |
| `RunConflict` | run identity/terminal chain不符 |
| `ExecutionEventConflict` | event ID重用但 logical payload不同 |
| `CheckpointConflict` | checkpoint idempotency/revision/transition衝突 |
| `OutboxLeaseConflict` | owner/status/expiry不符 |
| `PersistedDataCorruption` | canonical JSON、Pydantic、hash或 normalized columns不一致 |
| `ExternalArtifactStoreUnavailable` | V2-B嘗試 external artifact write |

repository可依 named constraint/SQLSTATE轉換，但 application test只斷言上述 stable type/code，不斷言 PostgreSQL英文錯誤字串。

## 11. Migration 0010 規則

### 11.1 Upgrade

1. 新檔固定為 `apps/api/alembic/versions/0010_interview_vnext_persistence.py`，`down_revision = "0009"`。
2. 只建立本文八張表、named constraints/indexes與 vNext trigger/functions。
3. create order：sessions → runs → artifacts → session initial-state FK + runs manifest FK → commands → execution events → outbox → checkpoints → attempts → triggers/indexes。
4. 所有 constraint/index/trigger/function顯式命名且小於 PostgreSQL 63-byte identifier limit。
5. Text+CHECK取代 native PostgreSQL ENUM，避免未來新增狀態需危險 enum DDL；open taxonomy names不做封閉 CHECK。
6. 不改 `interview_sessions/interview_turns/interview_llm_calls/interview_eval_*` 或 document tables。
7. migration手工 review；autogenerate只作 diff輔助，不能擁有 CHECK/trigger真相。

### 11.2 Downgrade

只在無 production vNext data 的開發/測試使用：

1. 先 drop triggers/functions、session→initial-state artifact FK與 run→manifest artifact circular FK；
2. 依 attempts → checkpoints → outbox → events → commands → artifacts → runs → sessions反向 drop；
3. 回到 revision 0009；
4. 不改任何 v3 rows/schema。

一旦 V7 pilot寫入 production，rollback是停用 vNext route並保留 tables，不執行 destructive downgrade。這是資料 rollback與程式 rollback的區別。

### 11.3 ORM metadata

- vNext rows可繼承既有 `app.models.base.Base`；
- Alembic `env.py` 顯式 import vNext persistence models；
- migration與 ORM model的 table/constraint/index contract必須有 introspection test；
- 不把 ORM relationship cascade設成 `all, delete`；audit/history FK一律 RESTRICT。

## 12. 必要整合測試

### 12.1 Test environment

既有 `db_session` fixture以 outer transaction rollback隔離，無法測「commit後另一 process/session看見」；V2-B crash/outbox測試不得沿用它。

新增 Postgres fixture使用 `TEST_DATABASE_URL` 與多個獨立 `async_sessionmaker`：

- CI提供 PostgreSQL 16 service並先 `alembic upgrade head`；
- 每個 case產生唯一 tenant/session/run UUID；
- test可真正 commit並由 fresh session讀取；
- finally依該 tenant/session ID清理：先把 mutable run `manifest_artifact_id`與 session `initial_state_artifact_id`設 null，再依 attempts → checkpoints → outbox → events → commands → artifacts → runs → sessions → profile/user刪除；不可 truncate共享 DB；
- local未設 DB可標記 skip，但 V2-B merge/promotion workflow必須設 DB，不能以 skipped當通過。

### 12.2 Minimum cases

1. initial state write/read canonical round-trip與 hash一致；
2. state + command/reduction artifacts + command + event + outbox同 transaction commit；
3. 在每個 flush point注入 exception後 rollback，fresh session查不到半套資料；
4. 相同 command ID/hash回既有 result，不增 state version/event/outbox；
5. 相同 idempotency key不同 hash穩定 conflict；
6. 兩個 sessions同 expected state version併發，恰一個成功，另一個 conflict；
7. artifact同 ID同 record idempotent、不同 record conflict、UPDATE trigger拒絕；
8. 兩 workers用獨立 AsyncSession併發 lease，同 message不重複 lease；
9. lease expiry後另一 worker接手，delivery_attempts +1；
10. 非 owner、expired owner不可 mark delivered/failed；
11. exporter成功、mark-delivered前 crash，expiry後重送同 event ID；
12. 同 run event 2在 event 1 non-terminal時不可 lease；不同 run可平行；
13. event append併發仍得到連續 sequence/hash chain；
14. event/artifact/outbox/finalize任一步失敗，run event_count/hash或 terminal fields不得半套前進；terminal row被直接清成 null manifest時，DB cleanup可執行，但 repository hydrate必須回 corruption；
15. prepared recovery只建立一次 attempt 1；
16. calling未到 deadline不重打；deadline後先保存 lost result再 attempt 2；
17. 兩 recovery workers中只有一個checkpoint CAS成功；
18. provider_completed/verified/committed recovery的 scripted provider call count保持 0；
19. committed recovery回完全相同 response artifact/hash；
20. migration 0009→0010→0009只增刪 vNext objects，v3 row counts/content hash不變；
21. schema introspection確認所有 named CHECK/FK/unique/partial index/trigger存在；
22. dependency guard確認 application/domain仍不 import SQLAlchemy，vNext仍不 import v3 internals。

「process crash」測法是：phase transaction commit後直接丟棄 UoW/session與 in-memory objects，以全新 session/repository重啟 recovery。只在同一 Python object上呼叫第二次不算 crash recovery test。

## 13. Observability 與 operational defaults

V2-B 本身不接外部 dashboard，但至少提供可查 metrics/log fields：

- outbox pending/retry/leased-expired/dead-letter count與 oldest age；
- delivery attempts/error code；
- checkpoint各 status count與 oldest age；
- state CAS conflict/idempotent replay count；
- transaction latency、artifact bytes、state JSON bytes；
- corruption/constraint conflict必須 error log，帶 tenant/session/run/operation IDs，不帶完整 transcript；
- DB pool wait/checked-out count。

初始 alert候選（V7 才接 production）：dead_letter > 0、expired lease持續增加、calling超過 deadline、provider_completed/verified長時間未前進、corruption > 0。

## 14. 明確不在 V2-B

- live OpenAI/Anthropic adapter與 provider選型；
-正式 Prompt/ContextBuilder；
- Web/production route、auth/tenant mapping；
- external artifact object store；
- vector database或 LangGraph checkpoint；
- normalized evidence/candidate read projections；
-跨 service message broker、CDC、Kafka/SQS；
- RLS policy與資料 retention/delete product policy；
- exactly-once delivery；
- v3 migration、雙寫或刪除。

`langgraph-checkpoint-postgres` 已在依賴中不代表 vNext要使用它。ADR 0034 的 workflow state、artifact、checkpoint semantics是本專案 contract；除非後續 eval證明需要 graph runtime，V2-B 不引入其 tables/checkpointer。

## 15. V2-B 完成的唯一宣告方式

只有同時達成以下條件，README/plan才可把 V2-B改成完成：

- 0010 migration upgrade/downgrade與 schema introspection全綠；
- 本文八張表、async UoW/repositories/outbox/recovery皆實作；
- §12 的 minimum cases全綠且 Postgres tests不是 skip；
-完整 API regression全綠；
- production route仍沒有 import/use vNext；
- 實際 commit SHA、測試數與 PostgreSQL版本寫回 plan/README。

完成 V2-B只代表 durable foundation成立；不代表 LLM分析品質好。品質要在 V3 fixed replay、V4 adaptive conversation與 V6 provider/model bake-off用 Capture證明。
