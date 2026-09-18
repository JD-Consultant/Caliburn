# Interview AI vNext V2-B Durable Persistence 實作計畫

- 日期：2026-07-16
- 狀態：**已完成(2026-07-17);七個 commits 全綠**——commit SHA 與實跑數字見 §11 實作結果
- 適用讀者：接手 V2-B 的工程師或 coding agent
- 精確 schema/transaction/recovery reference：[`../specs/2026-07-16-interview-vnext-v2b-durable-persistence-research.md`](../specs/2026-07-16-interview-vnext-v2b-durable-persistence-research.md)
- 上層工作包：[`2026-07-16-interview-ai-vnext-implementation-plan.md`](2026-07-16-interview-ai-vnext-implementation-plan.md)

本文是執行順序，不重複發明架構。遇到不明確處，先以 V2-B reference 為準；reference 沒寫的破壞性決定先更新文檔，不要在 code 裡自行選一個。

---

## 1. 完成定義

V2-B 完成時必須能以 PostgreSQL 16 integration tests證明：

```text
committed domain state
  + immutable command/result artifacts
  + durable operation checkpoint/attempt
  + hash-chained execution event
  + transactional outbox message
all-or-nothing

process crash
  -> fresh process/session reads checkpoint
  -> deterministic recovery decision
  -> no duplicate provider call after provider_completed
  -> no duplicate reducer mutation after committed
```

本工作包不接 production route、不打 live LLM、不做正式 ContextBuilder。若 PR 同時開始做 prompt/model品質，視為 scope failure。

## 2. Commit/PR 切片

一人團隊仍要拆小，建議依下列順序做 7 個 commits；每個 commit可 review、可 revert：

| Commit | 內容 | 可否碰 DB data | Gate |
|---|---|---:|---|
| V2-B-0 | dependency freshness與 test fixture foundation | 否 | lock + full regression |
| V2-B-1 | async application ports、serialization、errors | 否 | pure unit/dependency tests |
| V2-B-2 | ORM rows + migration 0010 | 只建新空表 | migration/introspection tests |
| V2-B-3 | repositories + UoW + atomic command commit | 是，測試 DB | CAS/rollback/idempotency tests |
| V2-B-4 | durable capture + outbox lease | 是，測試 DB | concurrency/expiry/order tests |
| V2-B-5 | checkpoint attempts + crash recovery | 是，測試 DB | recovery matrix/process restart tests |
| V2-B-6 | docs/results/final regression | 否 | focused + full suite、clean diff |

不得把 0010 migration、所有 repository、outbox與 recovery塞成一個不可 review的大 commit。

## 3. V2-B-0——Dependency freshness 與 PostgreSQL test foundation

### 3.1 修改檔案

- `apps/api/pyproject.toml`
- `apps/api/uv.lock`
- `apps/api/tests/conftest.py`
- `.github/workflows/` 下新增或擴充 vNext API test workflow；不要把只有 promptfoo的 workflow當 persistence CI

### 3.2 Dependency 動作

截至本文日期，先嘗試：

```toml
sqlalchemy[asyncio]==2.0.51
alembic==1.18.5
asyncpg==0.31.0
```

步驟：

1. 只改這三個 pins並 `uv lock`/`uv sync`；不順便升 FastAPI、Pydantic、LangGraph。
2. 跑完整 API suite。
3. 若相依衝突，記錄 package/resolver/test error；可以拆成 prerequisite blocker，但不可未說明就繼續用舊 pin。
4. 不使用 SQLAlchemy 2.1 prerelease API。

### 3.3 Test fixture

保留現有 outer-transaction `db_session` 供舊 tests；另外新增：

- `postgres_session_factory`：由 `TEST_DATABASE_URL` 建 engine + `async_sessionmaker(expire_on_commit=False)`；
- `vnext_ids`：每 case唯一 tenant/profile/session/run IDs；
- `vnext_profile`：建立最小 User/JobProfile fixture，tenant ID獨立產生；不得把 user ID當 tenant ID；
- `cleanup_vnext_rows`：只處理本 case IDs；先清 run manifest/session initial-state pointers，再依 attempts → checkpoints → outbox → events → commands → artifacts → runs → sessions → profile/user反向刪除；
- `require_postgres` marker/fixture：CI未設定 URL直接 fail；local可 skip並顯示原因。

Fixture 不可在同一 outer transaction包住所有 sessions，因 outbox/crash tests需要 transaction A commit後讓 transaction B看見。

### 3.4 Gate

- PostgreSQL service固定 16；
- `alembic upgrade head` 成功；
- 兩個真正獨立 AsyncSessions能互相看見 commit；
- 完整 API regression與變更前一致；
- git diff只含 dependency/test infrastructure。

## 4. V2-B-1——Application ports、serialization 與 stable errors

### 4.1 新增檔案

```text
apps/api/app/interview_vnext/application/persistence.py
apps/api/app/interview_vnext/persistence/errors.py
apps/api/app/interview_vnext/persistence/serialization.py
apps/api/app/interview_vnext/domain/reducers.py
apps/api/app/interview_vnext/domain/schema_exports.py
apps/api/app/interview_vnext/domain/write_schemas.py
apps/api/app/interview_vnext/domain/schemas/reduction-result.v1.schema.json
apps/api/tests/test_interview_vnext_persistence_serialization.py
apps/api/tests/test_interview_vnext_schemas.py
```

### 4.2 `application/persistence.py`

只定義 async Protocol/DTO，不 import SQLAlchemy。至少定義：

- `SessionRepository`：`create`, `get`, `save_cas`；
- `ArtifactRepository`：`put`, `get`, `get_many`；
- `CommandRepository`：`get_by_command_id`, `get_by_request_key`, `add`；
- `RunRepository`：`create`, `get`, `finalize`；
- `CheckpointRepository`：`create`, `get_by_operation`, `get_by_idempotency`, `save_cas`；
- `AttemptRepository`：`start`, `get`, `record_result`；
- `CaptureWriter`：`append_event`, `build_and_store_manifest`；
- `VNextUnitOfWork`：repository attributes + async context + explicit commit/rollback。

Port method必須傳 `tenant_id`；禁止只憑 `session_id` 查資料。

不要要求 async SQL class實作現有同步 `ArtifactStore/Outbox/CaptureRecorder` Protocol；in-memory fake可保留，application用新 async ports。

### 4.3 `serialization.py`

提供單一來源函式，不讓每個 repository自行 dump JSON：

```python
def dump_model(model: DomainModel) -> str: ...
def load_state(text: str, expected_hash: str) -> InterviewState: ...
def load_artifact(row) -> ArtifactRecord: ...
def load_event(text: str, expected_hash: str) -> ExecutionEvent: ...
def load_checkpoint(text: str) -> OperationCheckpoint: ...
```

必要行為：

- dump一定走既有 `canonical_json()`；
- read重跑 Pydantic strict validation；
- canonical text、hash、normalized identity任一不符 → `PersistedDataCorruption`；
- 不在 load時容忍未知欄位、補預設或修正時間；
- JSON decode/Pydantic errors包成 stable error，保留 exception chaining供 log。

`ReductionResult` 會作為 immutable command result artifact，因此本切片先替 model新增 `schema_version: Literal["reduction_result.v1"] = "reduction_result.v1"`，再加入 committed schema exports，固定 `$id = https://caliburn.local/schemas/reduction-result.v1.schema.json`。不可用無 schema ID 的任意 dict假裝 command replay payload。

### 4.4 Stable errors

完整清單依 reference §10。每個 exception至少有 stable `code`與必要 IDs；禁止 application依 constraint英文訊息判斷。

### 4.5 Tests

- state/event/checkpoint canonical round-trip；
- Unicode/emoji與 canonical byte hash；
- tampered text/hash/normalized ID皆 corruption；
- application AST dependency test仍禁止 SQLAlchemy；
- provider/v3 dependency guard仍通過。

## 5. V2-B-2——ORM rows 與 Alembic 0010

### 5.1 新增/修改檔案

```text
apps/api/app/interview_vnext/persistence/models.py
apps/api/alembic/versions/0010_interview_vnext_persistence.py
apps/api/alembic/env.py
apps/api/tests/test_interview_vnext_migration.py
```

### 5.2 ORM rules

- 繼承既有 `Base`，使用 SQLAlchemy 2.0 typed `Mapped`/`mapped_column`；不要再新增 legacy `Column` style。
- table/column/constraint/index完全依 reference §5。
- UUID用 `postgresql.UUID(as_uuid=True)`；時間用 timezone-aware timestamp；canonical payload用 `Text`。
- status用 `Text + named CheckConstraint`，不使用 native ENUM。
- 不設 ORM cascade delete、不建跨 package business relationship；repository可用 Core/ORM statements明確查寫。
- mapper不使用 `version_id_col`；session/checkpoint CAS由 explicit SQL完成。

### 5.3 Migration rules

依 reference §11 create/drop order。特別檢查：

- migration head只有一個，0010下接0009；
-八張表，不多不少；
- artifact/event/command immutable UPDATE triggers；
- outbox immutable payload guard；
- run manifest circular FK在 artifacts後建立、downgrade前移除；
- run lifecycle CHECK只硬保證 open無 completion/manifest，以及 terminal有 `completed_at`、至少一個 event、時間不倒退；**不得**加入 terminal必須有 manifest的 CHECK。terminal manifest由 `WorkflowRun` validator + atomic finalize + hydrate corruption check保證，讓 test cleanup可先清 pointer；
- session initial-state artifact FK也在 artifacts後建立；第一個 command前必須已有 version-0 snapshot；
-所有 vNext FK `ON DELETE RESTRICT`；
- partial index predicate與 lease query status完全相同；
- identifier < 63 bytes；
-不修改 v3 table。

### 5.4 Migration tests

在 disposable test database/schema：

1. upgrade到0009，插入最小 v3 fixture；
2. 記錄 v3 tables columns、row counts與 canonical content hash；
3. upgrade0010；
4. introspect八張表、columns、nullability、PK/FK/unique/CHECK/index/trigger；
5. 確認 v3 snapshot不變；
6. downgrade0009；
7. 確認只移除 vNext objects且 v3 snapshot不變。

run lifecycle要另外做一組精確測試：DB接受 terminal + completed_at + null manifest，供受控 cleanup；但相同 row經 `RunRepository.get()` hydrate時必須是 `PersistedDataCorruption`。這不是放寬 runtime invariant，而是把跨列 artifact完整性放在能原子驗證它的 application/UoW邊界。

Alembic autogenerate diff只能當輔助；官方已明列 CHECK等偵測限制，因此 introspection test是 gate。

## 6. V2-B-3——Repositories、UoW 與 atomic command commit

### 6.1 新增檔案

```text
apps/api/app/interview_vnext/persistence/repositories.py
apps/api/app/interview_vnext/persistence/unit_of_work.py
apps/api/app/interview_vnext/application/durable_commands.py
apps/api/tests/test_interview_vnext_persistence.py
```

### 6.2 Unit of Work

`SqlAlchemyVNextUnitOfWork` constructor只收 `async_sessionmaker`。進入時建立一個 AsyncSession/transaction/repositories；退出時：

- exception或未 explicit commit → rollback；
- explicit commit成功 → close；
- commit失敗 → rollback再 re-raise stable/translatable error；
- instance不可重入、不可跨 task共用。

Repository不得自行 commit或開 nested transaction。provider/exporter callback不得傳入 UoW block。

### 6.3 Artifact repository

`put(record)`：

1. 完整 validate；external在本階段拒絕；
2. `INSERT ... ON CONFLICT DO NOTHING RETURNING`；
3. conflict時讀既有 row並比較完整 `ArtifactRecord`；
4. 完全相同回既有；不同 `ArtifactConflict`。

禁止 `ON CONFLICT DO UPDATE`。`get_many` 要保留 caller refs順序並對每個 ref比 kind/media/schema/hash/size。

### 6.4 Session repository

`get(tenant_id, session_id)`讀 state並驗：

- row identity == nested state session identity；
- row status/workflow/reference/state_version/timestamps == nested session；
- canonical/hash一致。
- `state_version > 0`時 initial-state artifact ref存在且指向同 tenant/session的 `state.snapshot.initial`；

`save_cas(old_version, new_state)`使用單一 UPDATE/RETURNING：

```sql
UPDATE interview_vnext_sessions
SET status = :status,
    state_version = :new_version,
    state_schema_version = :schema_version,
    state_json = :state_json,
    state_hash = :state_hash,
    updated_at = :updated_at
WHERE tenant_id = :tenant_id
  AND session_id = :session_id
  AND state_version = :old_version
RETURNING session_id;
```

0 rows先不自行 commit/retry；交由 use case rollback後分辨 duplicate或 stale conflict。

### 6.5 `apply_durable_command`

依 reference §7.3實作固定順序。Input至少有：tenant/session/run、typed command、request idempotency key、command/reduction artifact IDs、event draft/clock。

不要讓 caller先自行產生 result state再要求 repository信任；use case必須 load current state並呼叫 registered pure reducer。Reducer dispatch用 explicit command type mapping，未知 schema/type hard fail，不用反射 class name猜。

### 6.6 Tests

- reference §12 cases 1–7；
-每個 repository flush點都有 failpoint rollback case；
-兩 concurrent tasks各自用新 UoW/session；
- duplicate race的 loser rollback後用新 UoW讀 existing result；
- transaction完成後 fresh session重建完整 state/reduction；
- repository回 domain models，不回 ORM rows。

## 7. V2-B-4——Durable Capture 與 outbox

### 7.1 新增檔案

```text
apps/api/app/interview_vnext/persistence/capture.py
apps/api/app/interview_vnext/persistence/outbox.py
apps/api/tests/test_interview_vnext_outbox_postgres.py
```

### 7.2 Durable event append

`append_event()`固定流程：

1. taxonomy validate event_type/stage；
2. 查相同 event ID；存在時比較 logical supplied fields，完全相同回 existing並確保 outbox存在，不新增 sequence；
3. 批次驗所有 artifact refs；
4. `SELECT run ... FOR UPDATE`；
5. 檢查 run open、architecture/workflow/taxonomy/session identity；
6. 以 `event_count+1`、`last_event_hash`建 `ExecutionEvent`；
7. insert immutable event；
8. insert pending outbox，message ID=event ID，copy canonical event text/hash/sequence；
9. update run count/first/last hash；
10. flush，commit由外層 UoW控制。

`create_run()` 在第一個 session run中還要先保存 immutable version-0 state snapshot並設定 `initial_state_artifact_id`，之後才 append `workflow.run.started`。若 session version已大於0但 pointer不存在，hard fail為 corruption，不可拿當前 state偽裝 initial state。

同一 transaction任何一步失敗，run counter不可前進。

### 7.3 Run finalize

1. append terminal run event；
2. 用 transaction內完整 chain建/validate `RunManifest`；
3. put manifest artifact；
4. update run status/completed_at/manifest ref；
5. commit。

步驟1–4必須同一 transaction。terminal run拒絕後續 event；相同 finalize inputs可回 existing manifest，不同 completion/hash conflict。DB CHECK只要求 terminal completion/event count，不硬要求 manifest；`WorkflowRun` validator與 repository hydrate仍必須把 terminal + null manifest視為 corruption。測試要證明 finalize任一步 rollback後不會留下半套 terminal fields，也要證明 §3.3 cleanup可先清 manifest pointer而不偽造 run status。

### 7.4 Outbox adapter

完整 lease SQL使用 reference §8，不另寫簡化版 `SELECT LIMIT`。要求：

- DB current timestamp；
- `FOR UPDATE SKIP LOCKED`只在 queue；
-同 run阻擋後續 non-terminal message；
- limit 1–500、lease 5–900 seconds；
- lease transaction commit後才 call exporter；
- mark delivered/failed用 owner/status/expiry compare條件與 `RETURNING`；
- 0 rows轉 `OutboxLeaseConflict`；
- duplicate delivery由 event ID處理，不承諾 exactly once。

### 7.5 Tests

執行 reference §12 cases 8–14，並額外測：

- 100個不同 run可分批 lease；
-同 run ordering與不同 run concurrency；
- retry_at必須晚於 failure DB time；
- dead_letter保留 payload/hash並讓後續 sequence可見；
- delivered/dead_letter不被一般 lease重新取出；
- EXPLAIN顯示在測試資料量足夠時可使用 queue partial indexes；不把特定 cost數字寫死。

## 8. V2-B-5——Checkpoint attempts 與 crash recovery

### 8.1 新增檔案

```text
apps/api/app/interview_vnext/application/durable_operations.py
apps/api/app/interview_vnext/application/recovery.py
apps/api/tests/test_interview_vnext_recovery_postgres.py
```

### 8.2 Durable operation use cases

分成獨立函式/類別，不建立一個會跨 network持有 UoW的 mega-function：

- `prepare_operation(...)`
- `start_attempt(...)`
- `record_attempt_result(...)`
- `record_verification(...)`
- `commit_verified_operation(...)`
- `fail_operation(...)`

每個函式只做一個短 transaction；provider call在 `start_attempt` commit後、`record_attempt_result` 前。

Checkpoint write順序永遠是：hydrate → pure transition function → canonical serialize → revision CAS。不要直接 patch JSON columns繞過 `OperationCheckpoint` validator。

### 8.3 Attempt invariants

- attempt 1只能由 prepared建立；
- retry必須已保存前一 attempt result；
- attempt number連續、attempt ID不重用；
- calling row可一次轉 result_recorded；
- provider result artifact必須等於 checkpoint final attempt-result ref；
- provider execution ref成對有/無，opaque且只交給對應 adapter；
- request deadline/operation max attempts由 `OperationSpec`判斷，不 hardcode無限 retry。

### 8.4 Recovery implementation

`decide_recovery(checkpoint, attempt, now, policy, provider_capabilities)`先做 pure decision，enum至少：

- `START_ATTEMPT`
- `WAIT_FOR_DEADLINE`
- `RECONCILE_PROVIDER`
- `RECORD_LOST_AND_RETRY`
- `MARK_FAILED`
- `VERIFY_EXISTING_RESULT`
- `COMMIT_VERIFIED_RESULT`
- `RETURN_COMMITTED`
- `RETURN_FAILED`

Coordinator依 reference §9一次執行一個 decision/transaction。若 reconcile要 network，先讀 committed ref並關閉 transaction，network後另開 transaction記結果。

### 8.5 Process-crash tests

每個 phase都採：commit → 丟棄所有 Python objects/session → fresh session/repository啟動。至少：

- prepared crash；
- calling before deadline；
- calling with recoverable ref；
- calling after deadline retry；
- attempt exhausted；
- provider_completed；
- verified；
- committed；
- failed；
-兩 recovery workers concurrent CAS。

Scripted provider要計數；`provider_completed|verified|committed|failed` recovery的 generate call count必須 0。calling timeout retry只能增加一次新 attempt。

## 9. V2-B-6——Final verification 與文檔回寫

### 9.1 Focused commands

實際可執行 command(2026-07-17 實跑,PostgreSQL 16、SQLAlchemy 2.0.51、
alembic 1.18.5、asyncpg 0.31.0):

```powershell
cd apps/api
$env:TEST_DATABASE_URL='postgresql+asyncpg://postgres:password@localhost:5432/caliburn'
uv run alembic upgrade head
uv run pytest tests/test_interview_vnext_persistence_serialization.py `
  tests/test_interview_vnext_migration.py `
  tests/test_interview_vnext_persistence.py `
  tests/test_interview_vnext_outbox_postgres.py `
  tests/test_interview_vnext_recovery_postgres.py `
  tests/test_interview_vnext_pg_fixtures.py -q
# → 50 passed, 0 skipped(migration test 自建/自毀獨立資料庫,不碰共享 dev DB)
```

再跑既有 vNext focused suite與完整 API suite。完整 suite在本 repo需 `$env:DEBUG='false'` 時照既有 runbook設定；不可因 DB tests較慢就從 merge gate移除。

### 9.2 回寫檔案

- 本 plan狀態與各 commit SHA；
- `2026-07-16-interview-ai-vnext-implementation-plan.md` 的 V2-B progress；
- `apps/api/app/interview_vnext/README.md` 的 durable claims、tables、測試 command與下一步 V3；
- `docs/README.md` 索引；
-若實際 contract與本文不同，先更新 research/reference並說明理由；若改 architecture decision才新增 ADR。

### 9.3 最後 gate

- focused Postgres tests全部實跑，0 skip；
-完整 API regression無新增 failure/skip；
- `git diff --check`；
- Alembic只有一個 head；
- migration downgrade不碰 v3；
- production app仍走 v3 route，vNext persistence沒有被 live composition root注入；
- commit author/committer沿用 repository owner identity，不加入額外 co-author trailer。

## 10. Code review checklist

### Transaction

- [ ] 是否有 provider/exporter network call在 DB transaction內？有即退回。
- [ ] repository是否偷偷 commit？有即退回。
- [ ] state/checkpoint是否 explicit CAS且檢查0 rows？
- [ ] event/outbox/run counter是否同 transaction？
- [ ] failed transaction後是否先 rollback/close，再用新 transaction查 duplicate？

### Integrity

- [ ] canonical payload是否保存 exact TEXT並重算 hash？
- [ ]每個 lookup/update是否帶 tenant ID？
- [ ] artifact/event/command是否 immutable、沒有 conflict update？
- [ ] normalized columns與 Pydantic nested identity是否雙向檢查？
- [ ] migration constraints/indexes/triggers是否由 introspection test證明？

### Concurrency/recovery

- [ ] concurrent task是否各自有 AsyncSession？
- [ ] `SKIP LOCKED`是否只用在 outbox queue？
- [ ] lease成功後是否先 commit才 call exporter？
- [ ] calling retry是否先保存舊 attempt result？
- [ ] provider_completed以後是否保證不重打 provider？
- [ ] committed recovery是否回既有 artifact而非重跑 reducer？

### Scope

- [ ] 是否誤加 LangGraph checkpoint/vector store/multi-agent？
- [ ] 是否誤建第二套 evidence/candidate權威表？
- [ ] 是否 import/wrap v3 interview internals？
- [ ] 是否接了 production route/live provider？

任一項答案不符合時，V2-B不得標完成。

## 11. 實作結果(2026-07-17 回寫)

### 11.1 Commits(一 task 一 commit,全部綠了才 commit)

| Commit | SHA | Gate 實跑 |
|---|---|---|
| V2-B-0 | `5bb72be` | 無 DB 337 passed/111 skipped(=基線);有 DB 450/0 skip;alembic 1.18.5 upgrade head OK |
| V2-B-1 | `d73ea79` | 463 passed/0 skip;serialization round-trip/corruption 全綠 |
| V2-B-2 | `5db1e43` | 465 passed;0009→0010→0009 循環 + introspection 全對,v3 byte 級不變 |
| V2-B-3 | `11c4ada` | 478 passed;§12 cases 1–7 + failpoints + 裁決 corruption cases |
| V2-B-4 | `73998a7` | 491 passed;cases 8–14 + finalize rollback + 100-run lease + EXPLAIN |
| V2-B-5 | `4d8edbd` | 499 passed;cases 15–19 + §8.5 crash matrix,scripted provider 計數 0 |
| V2-B-6 | (本回寫 commit) | focused 50 passed/0 skip;git diff --check 乾淨;單一 head=0010;production composition root 零 vNext import |

### 11.2 與原文的差異(均已回寫 reference 對應章節)

1. **§7.3 加 step 0:command commit 先鎖 run row(一致鎖序 run → session/artifacts)。**
   實測(§12 case 6 併發)抓到 deadlock:兩 writer 的 artifact/command INSERT 各持
   FK `KEY SHARE`,與對方的 session CAS/`run FOR UPDATE` 互等,PG 判 DeadlockDetected。
   run row 本來就是 chain 的序列鎖,提早取得即結構性消滅死鎖;transaction 短、無
   network I/O,可觀察契約不變。連帶:等鎖期間同 command 已被 commit 時,reducer 的
   idempotent 結果照 command record 走 replay(合法 race),record 缺席才是 corruption。
2. **`capture.py` 的 `append_event` 隨 V2-B-3 落地**(非 §2 表列的 V2-B-4):
   §7.3 step 7 與 §12 case 2 都要求 command commit 同 transaction append event+outbox,
   是計畫自身的依賴序;V2-B-4 補 create_run/finalize/manifest 與 lease adapter。
3. **outbox/event 的 `created_at` 用 DB 時鐘(`now()`)**:enqueue time=持久化時間;
   混用 domain `occurred_at` 會在 app/DB 時鐘差下撞 `updated_at >= created_at` CHECK。
4. **`record_attempt_result` 收呼叫端分類好的 outcome**(succeeded/retryable/
   non-retryable)+ canonical result artifact;typed `ModelCallResult` 正規化屬
   V3 workflow/V6 provider adapter。derived 不變量:attempt row 與 checkpoint 轉換
   同 transaction ⟹ durable「calling+result_recorded」組合必為 retryable。
5. **Port 增補**(§4.2 是「至少定義」):`SessionRepository.initial_state_artifact_id`
   /`set_initial_state_artifact`(§5.1/§7.2 pointer 協定)、`RunRepository.lock`(差異 1)。
6. **repositories 在 flush 期也翻譯 named-constraint violation**(併發 INSERT race
   在 flush 就爆,不會等到 commit);`alembic.ini` 補 `path_separator = os` 且必須
   維持 ASCII(configparser 用 locale 編碼讀,CJK 註解會炸)。

### 11.3 已知後續(不屬 V2-B)

- V3 fixed replay:正式 ContextBuilder + typed `ModelCallResult` 接 `record_attempt_result`。
- V5 前完成 authenticated principal → tenant → profile ownership(§2.3)。
- outbox dead_letter 的 metric/alert 與管理重播(§8.3)維持未做。
