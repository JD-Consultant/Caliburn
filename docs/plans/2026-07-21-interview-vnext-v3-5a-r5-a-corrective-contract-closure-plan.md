# Interview AI vNext V3-5A R5-A Corrective——Support 依賴方向與 QuestionFrame 生命週期閉合

- 日期：2026-07-21
- 狀態：**Approved / planned；R5-B 在本 corrective 完成前 blocked**
- Review baseline：`bf35137`（`feat(interview): define grounded answer domain contracts`）
- 上位決策：[`../adr/0037-interview-vnext-question-frame-contextual-evidence-and-employee-authority.md`](../adr/0037-interview-vnext-question-frame-contextual-evidence-and-employee-authority.md)
- R5 主規格：[`2026-07-20-interview-vnext-v3-5a-r5-grounded-short-answer-amendment-plan.md`](2026-07-20-interview-vnext-v3-5a-r5-grounded-short-answer-amendment-plan.md)
- Scope：**只修 R5-A review finding；不提前切 Evidence.v3／State.v3／commands／events／reducers／LLM runtime**

本文件是 R5-A code review corrective 的唯一施工 authority。它只補充並局部覆寫 R5 主規格的 `domain/support.py`
依賴方向與 `QuestionFrame` intra-model 時間 invariant；R5 其他資料契約、版本、流程與 gate 仍以 ADR 0037 和 R5
主規格為準。

若實作者發現必須改 Evidence／State schema version、provider wire、DB migration、operation registry 或 production route 才能完成
本 corrective，必須停下回報；那代表實作已跑出本文件授權範圍。

---

## 1. 白話：為什麼 R5-A 已綠，還不能直接做 R5-B

R5-A 已完成 QuestionFrame、contextual support、interpretation receipt 等 inactive domain contracts，而且現行 runtime 沒有被切換。
測試也全綠。但 code review 發現兩個契約閉合問題：

1. `support.py` 現在向 `evidence.py` 取得 `QuoteSpan`／`QuoteMatch`；R5-B 又要讓 `Evidence.v3` 使用
   `EvidenceSupport`。若照一般 top-level import 寫法，依賴會成為 `evidence -> support -> evidence`。
2. `QuestionFrame` 會驗狀態欄位是否齊全，卻仍接受 `closed_at < opened_at` 的不可能時間線。

第一項不是目前執行時錯誤，因為 Evidence 仍是 v2、尚未匯入 `EvidenceSupport`；它是下一個 hard cut 一定會撞到的結構問題。
現在修只需移動純 value objects；等 R5-B 才處理，會和 Evidence／State／Reducer 大切片混在一起，增加失敗歸因與 schema drift
風險。

第二項也不一定由正常 reducer 產生，但 persisted state、fixture 或 future command 若帶入倒序時間，Pydantic 目前會把它視為合法
QuestionFrame。這違反 R5-A「pure model 負責 intra-model coherence」的責任。

本 corrective 的目標不是增加功能，而是讓 R5-B 能建立在乾淨、單向、可驗證的 domain contract 上。

---

## 2. 已確認的 baseline 與 review 證據

Review 對象：

```text
bf35137 feat(interview): define grounded answer domain contracts
```

該 commit 的有效成果保留，不重寫：

- `QuestionFrameDefinition` mode/target matrix；
- proposition／slot／choice builders 與 sealed hash；
- raw UTF-8 question hash（不 trim、不 NFKC、不換行正規化）；
- literal/contextual support coherence；
- `TurnInterpretationRecord` frame pairing、Evidence ID uniqueness、insufficiency order；
- additive `question-frame.v1`／`turn-interpretation-record.v1` schema fixtures；
- active State／registry／provider wire 尚未切換。

2026-07-21 reviewer 重新執行：

```text
focused R5-A + schema/dependency: 58 passed
full no-network:                1002 passed / 197 skipped / 0 failed
git diff --check:               clean
worktree at review completion:  clean
```

本 corrective 不否定上述結果，只處理 full-green 測試沒有暴露的下一階段 dependency topology 與時間 invariant。

---

## 3. Finding A：現行 import 方向會讓 Evidence.v3 形成 cycle

### 3.1 現況

目前：

```text
domain/support.py
  -> from .evidence import QuoteMatch, QuoteSpan

domain/evidence.py
  -> owns QuoteMatch, QuoteSpan
  -> Evidence.v2 尚未引用 EvidenceSupport
```

R5-B 主規格要求：

```text
Evidence.v3.support:
  LiteralEmployeeSpanSupport | ContextualAnswerSupport
```

若在 `evidence.py` 直接加入 `from .support import EvidenceSupport`，會得到：

```text
evidence.py ───────────────> support.py
    ^                           |
    └──── QuoteSpan/Match <─────┘
```

Python 可用「先定義部分 class 再 late import」讓某些 import order 暫時成功，但這是隱含的 partial-module initialization 契約：

- cold-process import 順序可能影響結果；
- Pydantic `model_rebuild()`／JSON Schema traversal 更難推理；
- 未來只要有人把 import 移回檔案頂部，就會重新觸發 cycle；
- R5-B 的大型 hard cut 會被迫同時處理模組載入與 domain migration。

因此禁止以 late import、字串 forward reference、`TYPE_CHECKING` 或 runtime import hack 當正式修法。

### 3.2 核准的最終 ownership

`domain/support.py` 成為以下 primitive／support types 的唯一 owner：

```text
QuoteSpan
QuoteMatch
ContextualBindingKind
ContextualResolution
LiteralEmployeeSpanSupport
ContextualAnswerSupport
EvidenceSupport
```

`QuoteSpan`、`QuoteMatch` 從 `domain/evidence.py` 搬到 `domain/support.py`，class 名稱、欄位、enum value、validator 與
serialization shape 必須完全不變。

R5-A corrective 完成後：

```text
identifiers.py/base.py
          ^
          |
      support.py
          ^
          |
      evidence.py
          ^
          |
 question_frame.py / state.py / application / llm
```

更精確地說：

- `support.py` **不得** import `evidence.py`、`question_frame.py`、`state.py` 或 application/llm/evals；
- `evidence.py` 可 import `QuoteSpan`、`QuoteMatch`；R5-B 再由同一模組 import `EvidenceSupport`；
- `ContextualAnswerSupport` 只用 frame UUID/hash/ordinal，不 import `QuestionFrame` class；
- `question_frame.py` 可繼續 import `EvidenceKind`／`EvidenceQualifiers`／`EvidenceSubject`；不形成反向 cycle；
- application、llm、eval、tests 若只是需要 quote primitive，直接從 `domain.support` import；
- `domain.__init__` 對外仍可 export `QuoteSpan`，但 export source 改為 `domain.support`；不得新增雙份 class 或 alias subclass。

### 3.3 不能採用的替代方案

以下皆不接受：

- 在 `evidence.py` class 中間或函式內 late import `EvidenceSupport`；
- 用 `if TYPE_CHECKING` + 未驗證的 forward string 掩蓋 runtime cycle；
- 在 `support.py` 複製第二份 `QuoteSpan`／`QuoteMatch`；
- 保留兩個實際 class，再用 converter 互轉；
- 新增 Evidence v2/v3 dual-active shim；
- 為了 import 問題先把 support union 放進 provider output；
- 把 `EvidenceSupport` 改成無型別 `dict[str, Any]`。

這些做法不是抽象化，而是把同一份 authority 拆成兩份或把錯誤延後到 runtime。

---

## 4. Finding B：QuestionFrame 關閉時間可以早於開啟時間

### 4.1 現況

`QuestionFrame.lifecycle_is_coherent()` 已正確驗證：

- active 不得有 closure fields；
- consumed 必須有 answer、operation、closed_at；
- superseded 必須有 superseded_by、closed_at，且不得有 answer；
- stale 必須有 stale_reason、closed_at。

但目前只判斷 `closed_at is not None`，沒有比較時間，所以以下資料會通過：

```text
opened_at = 2026-07-21T10:00:00Z
closed_at = 2026-07-21T09:59:59Z
status    = consumed
```

### 4.2 核准 invariant

在 `QuestionFrame` model validator 增加單一明確規則：

```text
closed_at is not null  =>  closed_at >= opened_at
```

邊界語意：

- `closed_at == opened_at` 合法，因同一 transaction／測試 clock 可能使用同一 timestamp；
- active frame 仍由既有規則要求 `closed_at is null`；
- 不 trim、不改寫、不自動校正 timestamp；倒序直接 validation failure；
- timestamps 仍必須是既有 `UtcDatetime`，本 corrective 不改 timezone 規則；
- 不在這裡檢查 consultant/employee turn chronology，那是 R5-B state cross-link／R5-C context verifier 責任。

建議固定 error message：

```text
question frame closed_at cannot precede opened_at
```

### 4.3 明確留給 R5-B 的 cross-state 規則

本 corrective 不提前實作：

- `superseded_by_frame_id != question_frame_id`；
- supersession target 必須存在；
- supersession cycle detection；
- 同一 state 最多一個 active frame；
- `active_question_frame_id` 與 frame collection closure；
- answer turn role／position／next-employee-turn scope；
- operation/frame/session IDs 的 aggregate closure。

這些需要完整 state，不屬於單一 QuestionFrame value object。實作者不得因看到相關缺口而把 R5-B 混入 corrective。

---

## 5. Schema 與持久化相容性決策

### 5.1 Quote primitive 搬檔不等於 schema migration

`QuoteSpan`／`QuoteMatch` 的 Python owner module 會改，但 portable JSON shape 不得改：

```text
QuoteSpan:
  unit = unicode_code_point
  start >= 0
  end > 0
  end > start

QuoteMatch:
  exact | normalized
```

Pydantic `$defs` 名稱仍必須是 `QuoteSpan`、`QuoteMatch`。不得把它們改名為 `SupportQuoteSpan` 或新增 schema version。

### 5.2 既有 committed schemas 必須 byte-identical

本 corrective 後，執行 domain schema writer 不應產生任何 JSON diff。至少包括：

- `evidence.v2.schema.json`；
- `apply-evidence-command.v2.schema.json`；
- `interview-state.v2.schema.json`；
- `reduction-result.v1.schema.json`；
- 其他透過 Evidence／QuoteSpan 間接引用的 active domain schemas。

LLM schema 也不得因 import ownership 改變而漂移。

如果 schema writer 產生任何 semantic 或 byte diff，先停止並找原因；不得用「只是搬檔」為理由重寫 fixtures。

### 5.3 版本與 DB

本 corrective：

- Evidence 仍是 `evidence.v2`；
- InterviewState 仍是 `interview_state.v2`；
- QuestionFrame 仍是 `question_frame.v1`；
- TurnInterpretationRecord 仍是 `turn_interpretation_record.v1`；
- Alembic 必須仍是 `0010 (head)`；
- 不新增 migration、table、column、registry entry、operation version 或 taxonomy event。

Evidence.v3／State.v3 的 hard cut 仍由 R5-B 一次完成。

---

## 6. 逐檔施工責任

### 6.1 必改 production-neutral domain

#### `app/interview_vnext/domain/support.py`

- 移除 `from .evidence import QuoteMatch, QuoteSpan`；
- 把 `QuoteSpan`／`QuoteMatch` 定義原樣搬入本檔；
- 建議排列順序：quote primitives → contextual enums → support models → discriminated union；
- 不 import Evidence／QuestionFrame／InterviewState；
- 保留現有 literal/contextual validators，不趁機改 support 語意。

#### `app/interview_vnext/domain/evidence.py`

- 刪除本檔內 `QuoteSpan`／`QuoteMatch` class definitions；
- 從 `.support` import 這兩個 primitive；
- Evidence.v2 欄位與 validators 完全不變；
- **本 corrective 不加入 `support: EvidenceSupport`**，那是 R5-B；
- 不改 Evidence schema version。

#### `app/interview_vnext/domain/__init__.py`

- `QuoteSpan` export source 改為 `.support`；
- 既有公開名稱不消失；
- 不提前 export EvidenceSupport／QuestionFrame 全套 API，除非 R5 主規格另有既定要求。

#### `app/interview_vnext/domain/invariants.py`

- `QuoteMatch` 改從 `.support` import；
- Evidence／EvidenceStatus 等仍從 `.evidence` import；
- invariant 行為不變。

#### `app/interview_vnext/domain/question_frame.py`

- 在既有 lifecycle validator 加 `closed_at >= opened_at`；
- 不改任何 hash builder、mode matrix 或 field shape；
- 不切 aggregate cross-state invariants。

### 6.2 必改 active application／LLM import sites

只做 import ownership 的機械遷移，不改函式行為：

- `app/interview_vnext/application/turn_interpret.py`；
- `app/interview_vnext/llm/turn_interpret.py`。

兩檔中的 `QuoteSpan`／`QuoteMatch` 改從 `domain.support` import；其他 Evidence types 保留原來源。

### 6.3 必改 eval import site

- `evals/interview_vnext/fixture_builder.py`。

只改 quote primitive import source；fixture bytes、Evidence.v2 shape、case suite hash不得變。

### 6.4 必改 tests／dependency guard

目前已知直接使用 quote primitives 的測試：

- `tests/test_interview_vnext_context_builder.py`；
- `tests/test_interview_vnext_domain.py`；
- `tests/test_interview_vnext_question_frame.py`；
- `tests/test_interview_vnext_turn_interpret.py`；
- `tests/test_interview_vnext_workflow_reducers.py`。

實作者仍必須用下列搜尋確認沒有漏網 Python consumer，不可只照清單猜：

```powershell
rg -n "QuoteSpan|QuoteMatch" app/interview_vnext evals/interview_vnext tests -g "*.py"
```

規則：除 `domain/evidence.py` 自己為定義 Evidence.v2 欄位而 import 外，其他 production/eval/test consumer 都應直接從
`domain.support` 或既有 `domain` public export 取得 quote primitive；不得繼續把 `evidence.py` 當它們的 owner。

在 `tests/test_interview_vnext_dependencies.py` 增加結構 guard：

- AST 檢查 `domain/support.py` 不得 relative/absolute import evidence module；
- guard 失敗時輸出檔案與 line number；
- 不要只用容易誤判註解／字串的文字 `rg` 當測試本體。

---

## 7. 實作順序

以下是一個 atomic corrective；在完整 gate 綠之前不得 commit 半成品。

### Step 1——先釘 regression tests

新增測試並確認至少下列向量在舊 baseline 會失敗：

1. structural import guard：`support.py` 不得 import `evidence.py`；
2. consumed frame 的 `closed_at < opened_at` 必須 ValidationError；
3. superseded frame 的 `closed_at < opened_at` 必須 ValidationError；
4. stale frame 的 `closed_at < opened_at` 必須 ValidationError。

測試可先在工作樹暫時紅，但不得 commit 紅狀態。

### Step 2——搬移 quote primitive ownership

按 §6.1 搬 class，保留 class body 與 enum values。禁止以複製後保留舊 class 的方式過渡。

### Step 3——機械遷移 imports

按 §6.2–§6.4 更新所有 direct consumer。這一步不得改 extraction、span calculation、normalization 或 serializer 行為。

### Step 4——補 lifecycle time invariant

只增加一條 `closed_at` 不早於 `opened_at` 的規則。equal timestamp 測試必須保持合法。

### Step 5——schema、cold import 與完整回歸

先跑 focused，再跑完整 no-network 與 real PostgreSQL focused。所有 gate 綠後才 commit。

---

## 8. 必須新增／保留的測試矩陣

### 8.1 Import topology

| Case | Expected |
|---|---|
| AST 掃描 `support.py` | 不 import evidence/question_frame/state |
| fresh process：先 import support，再 evidence | 成功 |
| fresh process：先 import evidence，再 support | 成功 |
| `Evidence.model_json_schema()` | 成功，無 unresolved forward ref |
| `TypeAdapter(EvidenceSupport).json_schema()` | 成功，discriminator=`support_kind` |
| production imports | 無 class identity mismatch |

Fresh-process 測試必須真的用新 Python process，不能只在已載入 pytest process 中交換 import statement。建議以
`subprocess.run([sys.executable, "-c", ...], check=True)` 實作，且不得碰 network／DB。

### 8.2 Primitive identity／behavior

| Case | Expected |
|---|---|
| `QuoteSpan(start=0,end=1)` | valid |
| end == start | reject |
| end < start | reject |
| start < 0 | reject |
| exact + normalization_version | reject |
| normalized + null normalization_version | reject |
| existing Evidence.v2 exact quote | 行為不變 |
| existing normalized quote | 行為不變 |

### 8.3 Lifecycle chronology

| Status | closed/open relation | Expected |
|---|---|---|
| active | closed null | valid |
| consumed | closed > opened | valid |
| consumed | closed == opened | valid |
| consumed | closed < opened | reject |
| superseded | closed < opened | reject |
| stale | closed < opened | reject |

既有 required/forbidden field matrix 測試不得刪除或改弱。

### 8.4 Schema drift

- `tests/test_interview_vnext_schemas.py` 全綠；
- domain writer 在 temporary directory 產生兩次結果 byte-equal；
- committed schema directory與 `SCHEMA_EXPORTS` 完全一致；
- corrective commit 不應包含任何 `*.schema.json` diff；
- eval case suite hash不變；
- application/llm/capture active schema fixtures不變。

---

## 9. 驗收命令

從 `apps/api` 執行；使用 lock，不安裝新 dependency。

### 9.1 Static／focused

```powershell
uv run --locked pytest -q tests/test_interview_vnext_question_frame.py tests/test_interview_vnext_dependencies.py tests/test_interview_vnext_schemas.py
uv run --locked pytest -q tests/test_interview_vnext_domain.py tests/test_interview_vnext_turn_interpret.py tests/test_interview_vnext_workflow_reducers.py tests/test_interview_vnext_context_builder.py
```

### 9.2 Full no-network

```powershell
Remove-Item Env:TEST_DATABASE_URL -ErrorAction SilentlyContinue
uv run --locked pytest -q
```

基準是 `0 failed`。總 passed 可以因新增 regression tests 大於 1002；`197 skipped` 是 review baseline，不可把新增的非 DB／network
測試改成 skip 來湊數。

### 9.3 Real PostgreSQL focused

依 `docs/runbook.md` 設定既有 `TEST_DATABASE_URL`，不得建立新 migration：

```powershell
uv run --locked alembic current
uv run --locked pytest -q tests/test_interview_vnext_persistence.py tests/test_interview_vnext_outbox_postgres.py tests/test_interview_vnext_fixed_replay_postgres.py tests/test_interview_vnext_recovery_postgres.py
uv run --locked alembic heads
```

`current`／`heads` 都必須是 `0010`。若本機無 DB，這不是自行 skip 的授權；停止並在交付中明確回報 gate 未完成，R5-B 不解鎖。

### 9.4 Schema／dependency／hygiene

```powershell
uv run --locked python -m app.interview_vnext.domain.write_schemas
git diff --exit-code -- app/interview_vnext/domain/schemas
uv run --locked pytest -q tests/test_interview_vnext_dependencies.py tests/test_interview_vnext_schemas.py
git diff --check
rg -n "from \.evidence import QuoteMatch|from \.evidence import QuoteSpan" app/interview_vnext evals/interview_vnext tests
rg -n "evals\.interview_vnext" app
git status --short
```

注意：最後一個 quote import 搜尋對 multiline import 不完整，所以只能作人工輔助；正式防線是 AST dependency test 與完整測試。

---

## 10. Commit slicing 與綠度規則

### R5-A-C1——Code/test corrective

一個 atomic commit 完成：

- Quote primitive ownership 搬移；
- 全 consumer import 機械遷移；
- structural/fresh-process tests；
- QuestionFrame chronology invariant/tests。

建議 subject：

```text
fix(interview): close R5-A support and frame invariants
```

commit 前要求：§9 全部 required gate 綠。禁止提交「focused 綠、full suite 已知紅」的 commit。

### R5-A-C2——Status evidence

Code corrective 完成後，另以 docs-only commit 回寫：

- 本文件狀態與 exact SHA／test counts；
- R5 主規格 R5-A／R5-B 狀態；
- `docs/README.md`；
- `app/interview_vnext/README.md`；
- 若 eval README 的 next-step 指標已過期，再同步該處。

建議 subject：

```text
docs(interview): close R5-A corrective handoff
```

不得改寫 `bf35137`；保留原始 R5-A commit 與 corrective 歷史。

---

## 11. 明確非目標

本 corrective 不做：

- Evidence.v3 active schema；
- InterviewState.v3；
- commands/events/reducers hard cut；
- active frame pointer、CAS、stale reducer；
- ContextPacket／TurnInterpretInput/Output v2；
- prompt／policy／operation registry 2.0.0；
- OpenRouter/OpenAI adapter schema migration；
- Capture artifact/event/manifest root 改動；
- JD synthesis、editor、Web、production route；
- paid live probe／batch；
- cache、provider routing、conformance 改動；
- migration `0011`；
- 新框架或 dependency。

也不要趁機重新命名 QuestionFrame enums、改 hash canonicalization、重排 insufficiency order，或進行全專案 formatter rewrite。

---

## 12. Definition of Done

- [ ] `support.py` 不 import `evidence.py`／QuestionFrame／State；
- [ ] `QuoteSpan`／`QuoteMatch` 只有一份 class authority；
- [ ] Evidence.v2 使用來自 `support.py` 的相同 primitive；
- [ ] production／eval／tests quote imports 已機械遷移且 AST guard 鎖住方向；
- [ ] fresh process 兩種 import order與兩種 schema generation皆成功；
- [ ] QuestionFrame 所有 terminal status 拒絕 `closed_at < opened_at`；
- [ ] equal timestamp 合法；既有 lifecycle matrix全綠；
- [ ] committed domain/application/llm/capture schema bytes無改變；
- [ ] suite/case hashes無改變；
- [ ] full no-network 0 failed；
- [ ] real PostgreSQL focused 0 skipped／0 failed；
- [ ] dependency/schema guards、`git diff --check` 全綠；
- [ ] Alembic仍0010，無0011；
- [ ] 無 provider/runtime/editor/Capture scope creep；
- [ ] author/committer 只使用 repository owner identity；無額外 co-author；
- [ ] 未 push、未跑 paid live、未提交 key/output bundle。

全部成立後，才能把 R5-B 從 blocked 改為 ready。

---

## 13. 必須停下回報的情況

1. 搬移 QuoteSpan／QuoteMatch 導致任何 committed schema byte drift；
2. 無法在不使用 late import／forward-ref hack 的情況下消除 cycle；
3. Evidence.v2 runtime behavior、serialized JSON 或 existing fixture hash改變；
4. 必須提前加入 EvidenceSupport 欄位才能讓測試綠；
5. 必須修改 DB schema或新增0011；
6. 必須改 provider adapter／route／cache／conformance；
7. full suite出現與單純 import ownership無法解釋的 regression；
8. real PostgreSQL資料不是可清理的測試資料；
9. 實作者認為 self-supersession／active pointer／answer turn closure也應塞入本 corrective；
10. 只能透過保留雙份 primitive或 compatibility shim 才能過測試。

遇到上述任一項，不得擴大修補；保留工作樹證據並回報具體檔案、錯誤與已嘗試的安全方案。

---

## 14. 實作者交付回報格式

交付時逐項提供：

1. R5-A-C1／C2 commit SHA、subject、author、committer；
2. `QuoteSpan`／`QuoteMatch` 最終 owner 與 import graph；
3. 所有機械遷移 consumer 清單；
4. AST dependency guard 與 fresh-process import/schema 測試數；
5. lifecycle chronology vectors與結果；
6. schema writer後 `git diff --exit-code` 結果；
7. focused 測試逐檔 exact counts；
8. full no-network exact passed/skipped/failed；
9. real PostgreSQL focused exact passed/skipped/failed；
10. Alembic current/heads；
11. `git diff --check`、dependency guard、secret scan；
12. 是否有未完成 gate；
13. 明確確認未做 Evidence.v3／State.v3／provider／Capture／editor／Web／live；
14. 明確結論：R5-B 是否已解鎖。

「測試大致通過」或只回報 focused suite 不算交付完成。
