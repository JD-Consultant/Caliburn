# Interview AI vNext——最小 Authoring Core 垂直切片實作交接規格

- 日期：2026-07-23
- 狀態：**Completed（A1–A3 code green；A4 docs closed）**
- 前置狀態：R5-A、R5-BC、R5-D completed；目前 Alembic head=`0011`
- 產品目標：先打通「Evidence → task/output 提案 → 員工接受／修改／拒絕 → canonical revision」
- 本切片代號：**A1 Minimal Authoring Core**
- 下一切片：A2 Context Engine + `question.select`；其後才是 `episode.code` 真模型 task/output proposal
- 產品運行範圍：**單機／單使用者成品優先；SaaS 除非 owner 明確要求，否則不排入 roadmap**

> 本文件是 ADR 0038 之後第一份 Authoring Core 可施工規格。實作者不得再以舊 editor `_pending`、
> `DocumentVersion.content` 或 `InterviewState.candidates` 自行推導另一套文件真相。

---

## 1. 白話：這一步到底要做出什麼

這一步先做一個小但真的能工作的「AI 與員工共編文件核心」。

完成後，系統可以：

1. 為一個 vNext 訪談 session 建立一份空的職務文件草稿；
2. 員工直接新增或修改一個工作任務及其工作產出，立即成為文件真相；
3. 系統用已存在的員工 Evidence 建立一筆 scripted AI 建議；
4. AI 建議只會出現在待審區，不會偷偷寫進文件；
5. 員工可以選擇「符合我的工作」、「修改後採用」或「不符合」；
6. 接受或修改後採用會建立新的 immutable revision；拒絕不改文件；
7. 若員工先改了文件，舊 AI 建議會變 stale，不能被背景自動套用；
8. 每次讀取都能從最新 canonical revision 確定性產生 `JobStateDigest`，供後續顧問選題使用。

這不是完整 JD。它先證明產品最核心的權限與同步迴路成立：

```text
員工事實 Evidence
  -> AI task/output proposal（待審，不改文件）
  -> 員工接受／修改／拒絕
  -> canonical JobDocument revision
  -> deterministic JobStateDigest
  -> 下一輪顧問看見最新已接受內容
```

本切片先不用真模型。scripted proposal 會走與未來 `episode.code` 相同的 Authoring application seam；因此下一步換成
OpenRouter model output 時，不必重寫 revision、decision、stale 或 digest。

---

## 2. Authority 與衝突裁決

### 2.1 依據順序

實作衝突時依下列順序判定：

1. [ADR 0038](../adr/0038-interview-vnext-context-engine-and-professional-consultant-workflow.md)：產品 workflow、
   Context Engine、Authoring authority、AI proposal 與交付順序；
2. [2026-07-20 專業職務分析研究](../specs/2026-07-20-interview-vnext-professional-job-analysis-and-short-answer-architecture-research.md)：
   Canonical Job Model、command/proposal/conflict、task/output/K/S 分層；
3. [R5-D completed handoff](2026-07-22-interview-vnext-v3-5a-r5-d-bounded-correctness-closure-plan.md)：
   Evidence/Capture 完成基線與 post-R5 交付入口；
4. 本文件：A1 的 exact scope、欄位、交易、migration 與測試。

### 2.2 本文件對既有文字的兩個明確收斂

1. R5-D §18 的「必要 output/indicator 欄位」在本切片收斂為 **task 必填、output 可為 0..N、indicator 不做**。
   這符合 ADR 0038 §10「第一版先讓 task + output 可用，再加入 indicator、duty、K/S」。
2. `apps/api/app/interview_vnext/AGENTS.md` 舊文寫 migration `0011` 一律 blocked；該句是 R5 runtime 期間的禁令。
   R5-D 已完成，ADR 0038 已核准 post-R5 Authoring product slice，因此本文件**只授權**
   `0011_job_authoring_core.py` 的三張 Authoring 表。它不授權 provider、Web、SaaS 或其他 schema 擴張。

### 2.3 既有程式的實際盤點結論

| 現行物件 | 保留用途 | 為何不能直接當新 Authoring truth |
|---|---|---|
| `InterviewState.evidence` | 員工事實與來源權威 | 它是訪談 aggregate，不是可編文件 revision |
| `InterviewState.candidates/reviews` | 既有分析候選與歷史測試相容 | candidate status 不等於 canonical document proposal/revision |
| `DocumentVersion.content` | 現行手動 editor／OCS exchange | 深 JSON + row CAS，沒有 entity-level proposal/decision/provenance |
| OCS `_pending` | 舊 UI 的 inline 待審標記 | proposal 與 publication shape 混在一起，不能成為 audit authority |
| `packages/ocs-contract` | 匯入／匯出 exchange contract | T/P/O/K/S 是 publication position code，不是永久 entity ID |
| vNext Capture | LLM execution 證據 | 本切片沒有 provider call，不為 application command 再造 workflow run |

因此 A1 建立獨立的 `app/job_authoring/` modular-monolith module。舊 editor 未來只能作 thin adapter；本切片不把新 core
塞回 `_pending`。

---

## 3. Scope：必須做與明確不做

### 3.1 必須交付

- 一個 session 只能有一份 active `JobDocument`；
- canonical `JobDocumentDraft.v1`，第一版只有 job title、tasks、nested outputs；
- stable application-owned `document_id/task_id/output_id/revision_id/proposal_id`；
- immutable revision history與 mutable document head CAS；
- employee direct add／replace task bundle；
- scripted AI **add-task** proposal，task 必填、outputs 0..N；
- proposal evidence closure與可顯示 reason／limitations；
- employee accept／edit-then-accept／reject；
- proposal stale與 typed conflict；
- deterministic bounded `JobStateDigest.v1`；
- PostgreSQL migration `0011`、repositories、UoW與 real-PG tests；
- generated JSON Schemas與 drift tests；
- 一個 scripted real-PG end-to-end golden，證明三種 decision、direct edit與 stale；
- README／AGENTS／docs index 同步更新。

### 3.2 明確不做

- 不做 behavior indicator、duty、K/S、ability、attitude、職能級別；
- 不做職能基準 code/name/category/version 或公版 mapping；
- 不做 `reference.retrieve`、Qdrant、reranker、embedding；
- 不做 `question.select`、Agenda/Sufficiency、episode close；
- 不做 `episode.code` LLM operation、OpenRouter call、paid live；
- 不接 production FastAPI route、Web、舊 editor；
- 不做 publish/export/OCS projection；
- 不做公司 catalog、SaaS、多 tenant 行為、多人共同編輯、comment/presence/CRDT；
- 不做 delete task、reorder、merge、split、link/unlink；
- 不做全域 accept-all、background auto-apply 或 auto-rebase；
- 不新增 agent framework、workflow graph、event-sourcing framework、generic patch DSL；
- 不修改 R5 Evidence/State/command/event/reducer/provider/Capture contracts；
- 不修改既有 12-case suite identity、gold、fixture 或模型品質 verdict。

`tenant_id` 仍保留為既有資料隔離 scope，這不代表本切片新增 SaaS／公司功能。

### 3.4 2026-07-23 產品優先級裁決

目前目標不是建立可販售的多租戶平台，而是儘快讓一名員工能與 AI 顧問完成一份高品質、客製化職務說明書。因此：

- `tenant_id` 只作既有 vNext session／FK 的內部相容欄位；不因此建立 organization、member、ACL、quota、billing、tenant admin、跨租戶測試矩陣或 SaaS UI；
- 員工使用的是本機 Web app；啟動流程可自動開啟 localhost UI，但不會收到遠端產品網址、帳號或密碼，也不需自行設定 host／port；
- 不為「未來可能需要」增加 generic repository、command bus、workflow framework、額外 hash 層或全面測試排列；
- 不刪除 immutable revision、AI-only-proposal、employee decision、Evidence provenance、transaction/CAS 等會直接影響文件正確性的核心架構；
- 測試採風險導向：純契約／transition 代表邊界、資料庫關鍵不變量、以及一條真 PostgreSQL 產品 golden；後續功能不要求全面排列組合覆蓋；
- A1 完成後，工程時間優先投入 LLM／工作分析流程與能操作的最小介面，不投入 SaaS 化。除非 owner 之後明確改變範圍，本裁決持續有效。

### 3.3 成功畫面不是這一輪的 DoD

A1 的 end-user UI 尚未接線。此切片交付的是可被 API/Web adapter 呼叫的 production application core，加上一條 scripted
end-to-end golden。不能把「還沒有雙欄畫面」說成 A1 失敗，也不能把 A1 測試全綠說成完整產品完成。

---

## 4. Target architecture

```text
Interview vNext                         Job Authoring Core
┌──────────────────────────┐           ┌────────────────────────────┐
│ InterviewState.v3        │           │ JobDocument head           │
│ Evidence.v3              │--refs---->│ immutable revisions        │
│ session state/hash       │           │ proposals + decisions      │
└──────────────────────────┘           └──────────────┬─────────────┘
                                                     │ pure projection
                                                     v
                                            JobStateDigest.v1

future episode.code output
  -> application maps ordinals to Evidence refs
  -> CreateTaskProposalCommand
  -> same Authoring service used by scripted A1
```

分層固定為：

```text
app/job_authoring/contracts.py        immutable domain values
app/job_authoring/commands.py         trusted application commands
app/job_authoring/transitions.py      pure document transitions
app/job_authoring/digest.py           deterministic bounded projection
app/job_authoring/ports.py            persistence/Evidence protocols
app/job_authoring/service.py          transaction orchestration
app/job_authoring/postgres_models.py  SQLAlchemy adapter rows
app/job_authoring/postgres.py         repositories/UoW/Evidence bridge
```

`contracts.py`、`commands.py`、`transitions.py`、`digest.py`只能 import標準庫、Pydantic與同一 `job_authoring` package。
它們不得 import SQLAlchemy、FastAPI、provider SDK、`app.interview` v3、OCS contract或Web DTO。

---

## 5. Canonical domain contracts

本節欄位是實作契約，不是示意。除明列 optional 外不得自行加 nullable 欄位。

### 5.1 共用 scalar 與文字規則

- 所有 models 採 `extra="forbid"`、`frozen=True`；collection 使用 tuple；
- 所有 timestamp 必須 aware UTC；
- 文字只拒絕 blank，不自動 `strip`、NFKC、改標點或重寫；
- `JobTitleText`：1..256 Unicode code points；
- `TaskStatementText`：1..512 code points；
- `OutputStatementText`：1..512 code points；
- `PlainReasonText`：1..512 code points；
- 一份 draft 最多 64 tasks；一個 task 最多 16 outputs；
- outputs中不得有重複 `output_id`；同一 draft不得有重複 task/output ID；
- 第一版不以模糊相似度拒絕重複文字；duplicate detection留給後續 episode/job eval。

### 5.2 Provenance／Evidence refs

```python
class EvidenceBasisRef:
    evidence_id: UUID
    evidence_hash: Sha256

class JobFieldProvenance:
    source_kind: Literal[
        "employee_document_edit",
        "accepted_ai_proposal",
        "employee_proposal_edit",
    ]
    source_id: UUID       # command_id 或 proposal_id
    evidence_basis: tuple[EvidenceBasisRef, ...] = ()

class ProposalStaleReason(StrEnum):
    DOCUMENT_REVISION_ADVANCED = "document_revision_advanced"
    BASE_REVISION_CHANGED = "base_revision_changed"
    EVIDENCE_BASIS_CHANGED = "evidence_basis_changed"
```

規則：

- direct edit 的 `source_kind=employee_document_edit` 且 `evidence_basis=()`；
- exact accept 的 source為 `accepted_ai_proposal`，保留 proposal已驗證的 evidence basis；
- edit-then-accept 的 source為 `employee_proposal_edit`：task保留原proposal task basis；沿用proposal output ID的output保留該
  output basis；員工新增的null-ID output在派生ID後使用empty basis。這些只代表形成背景，不得宣稱employee改寫後文字是
  Evidence原句；
- `evidence_hash` 是 `canonical_hash(Evidence.v3)`，不是 transcript hash、state hash或 artifact hash；
- accepted revision之後若 Evidence被更正，文件不會被背景刪除；後續 completion/provenance audit會提示重審。

### 5.3 Task/output 與 draft

```python
class JobOutput:
    output_id: UUID
    statement: OutputStatementText
    provenance: JobFieldProvenance

class JobTask:
    task_id: UUID
    entity_version: int                  # >= 1；整個 task bundle 的 CAS/fingerprint版本
    statement: TaskStatementText
    outputs: tuple[JobOutput, ...] = ()
    provenance: JobFieldProvenance

class JobDocumentDraft:
    schema_version: Literal["job_document_draft.v1"]
    document_id: UUID
    session_id: UUID
    job_title: JobTitleText
    tasks: tuple[JobTask, ...] = ()
```

規則：

- output nested於 task；task-output linkage因此不可缺；
- tuple順序是authoring order；direct add與proposal add一律 append；replace保留原task位置；
- `entity_version`在該task statement或outputs語意改變時加1；其他task不變；
- output有stable ID但A1不設獨立version，整個task bundle以`entity_version`作衝突單位；
- T01/O01不是欄位，也不持久化；未來publication projector依revision順序確定性產生；
- `job_title`由建立文件時的 profile title複製；A1不提供title編輯命令。

### 5.4 Revision view

```python
class JobDocumentRevision:
    schema_version: Literal["job_document_revision.v1"]
    revision_id: UUID
    document_id: UUID
    revision_number: int                 # initial = 0；之後連續 +1
    parent_revision_id: UUID | None
    snapshot: JobDocumentDraft
    snapshot_hash: Sha256
    source_kind: Literal[
        "initial",
        "employee_direct_edit",
        "ai_proposal_accept",
        "employee_proposal_edit",
    ]
    command_id: UUID
    occurred_at: UtcDatetime
```

`snapshot_hash == canonical_hash(snapshot)`。revision metadata不混入snapshot hash；同內容可以有同snapshot hash，但revision identity仍不同。

初始文件命令：

```python
class CreateJobDocumentCommand:
    schema_version: Literal["create_job_document_command.v1"]
    command_id: UUID
    tenant_id: UUID
    session_id: UUID
    job_title: JobTitleText
    occurred_at: UtcDatetime
```

`document_id`與revision0 ID由application依§6.1派生，不由caller或模型指定。

### 5.5 Direct edit command

```python
class EditableOutputValue:
    output_id: UUID | None
    statement: OutputStatementText

class TaskBundleEditValue:
    statement: TaskStatementText
    outputs: tuple[EditableOutputValue, ...] = ()

class EmployeeTaskBundleCommand:
    schema_version: Literal["employee_task_bundle_command.v1"]
    command_id: UUID
    tenant_id: UUID
    document_id: UUID
    expected_revision_id: UUID
    expected_revision_hash: Sha256
    action: Literal["add", "replace"]
    target_task_id: UUID | None
    expected_target_version: int | None
    value: TaskBundleEditValue
    occurred_at: UtcDatetime
```

shape規則：

| action | target_task_id | expected_target_version | output_id |
|---|---:|---:|---|
| `add` | 必須 null | 必須 null | 全部必須 null |
| `replace` | 必填 | 必填且 >=1 | 可為該task既有output ID或null；不得引用其他task output |

`replace`以傳入outputs tuple作完整新child list：保留的output帶原ID；刪除的output不傳；新增output用null。A1不提供整個task delete。

### 5.6 Trusted proposal draft與 persisted proposal

未來模型不會直接產下列 persisted identity；`episode.code`先輸出operation-local ordinals，application映射成 Evidence refs後，
才建立 trusted draft。

```python
class ProposedOutputDraft:
    statement: OutputStatementText
    evidence_basis: tuple[EvidenceBasisRef, ...]   # min_length=1

class TaskBundleProposalDraft:
    statement: TaskStatementText
    evidence_basis: tuple[EvidenceBasisRef, ...]   # min_length=1
    outputs: tuple[ProposedOutputDraft, ...] = ()
    plain_language_reason: PlainReasonText
    limitations: tuple[ShortText, ...] = ()

class CreateTaskProposalCommand:
    schema_version: Literal["create_task_proposal_command.v1"]
    proposal_id: UUID                  # application-owned；模型不得提供
    tenant_id: UUID
    session_id: UUID
    document_id: UUID
    base_revision_id: UUID
    base_revision_hash: Sha256
    evidence_state_version: int
    evidence_state_hash: Sha256
    source_kind: Literal["scripted", "llm_operation"]
    source_id: UUID                    # scripted case/run ID或operation_id
    draft: TaskBundleProposalDraft
    created_at: UtcDatetime
```

application將draft的Evidence refs驗完並派生ID後，建立immutable persisted proposal payload：

```python
class ProposedJobOutput:
    output_id: UUID
    statement: OutputStatementText
    evidence_basis: tuple[EvidenceBasisRef, ...]   # min_length=1

class ProposedJobTask:
    task_id: UUID
    statement: TaskStatementText
    outputs: tuple[ProposedJobOutput, ...]
    evidence_basis: tuple[EvidenceBasisRef, ...]   # min_length=1

class AiTaskBundleProposal:
    schema_version: Literal["ai_task_bundle_proposal.v1"]
    proposal_id: UUID
    session_id: UUID
    document_id: UUID
    base_revision_id: UUID
    base_revision_hash: Sha256
    evidence_state_version: int
    evidence_state_hash: Sha256
    operation: Literal["add_task"]
    proposed_task: ProposedJobTask     # IDs由application派生；尚非accepted JobTask
    plain_language_reason: PlainReasonText
    limitations: tuple[ShortText, ...]
    source_kind: Literal["scripted", "llm_operation"]
    source_id: UUID
    created_at: UtcDatetime
```

proposal payload immutable且不含lifecycle status。repository以row的`status`、optional decision與payload組成query view；因此
pending→accepted等狀態轉移不會改寫`proposal_json/proposal_hash`。

```python
class TaskProposalView:
    schema_version: Literal["task_proposal_view.v1"]
    proposal: AiTaskBundleProposal
    status: Literal["pending", "accepted", "edited", "rejected", "stale"]
    decision: EmployeeProposalDecision | None
    result_revision_id: UUID | None
    stale_reason: ProposalStaleReason | None
    resolved_at: UtcDatetime | None
```

`TaskProposalView`依§10.4 lifecycle shape驗證；它是application query contract，不是DB mutable entity。

每個proposed task/output都必須有非空 Evidence basis；沒有output證據就不要產output。公版reference、模型常識或consultant問句
不能補成employee evidence。

### 5.7 Proposal decision command／decision

```python
class EmployeeProposalDecisionCommand:
    schema_version: Literal["employee_proposal_decision_command.v1"]
    command_id: UUID
    tenant_id: UUID
    document_id: UUID
    proposal_id: UUID
    expected_revision_id: UUID
    expected_revision_hash: Sha256
    action: Literal["accept", "edit", "reject"]
    edited_value: TaskBundleEditValue | None
    occurred_at: UtcDatetime

class EmployeeProposalDecision:
    schema_version: Literal["employee_proposal_decision.v1"]
    command_id: UUID
    proposal_id: UUID
    action: Literal["accept", "edit", "reject"]
    base_revision_id: UUID
    base_revision_hash: Sha256
    final_task: JobTask | None
    result_revision_id: UUID | None
    decided_at: UtcDatetime
```

shape規則：

- `accept`：`edited_value=None`；final task的ID／statement／outputs／Evidence basis逐欄等於persisted proposed task，另加
  `accepted_ai_proposal` canonical provenance；
- `edit`：`edited_value`必填；不得與persisted proposed bundle完全相同；
- `reject`：`edited_value=None`、`final_task=None`、`result_revision_id=None`；
- edited output ID只能是本proposal proposed output ID或null；
- decision只能從pending進入一個terminal status；terminal proposal不可第二次改decision；
- exact同command replay回既有結果；同command ID不同內容回idempotency conflict。

### 5.8 JobStateDigest

```python
class JobStateDigestTask:
    ordinal: str                        # T01, T02...只在digest內顯示
    task_id: UUID
    entity_version: int
    statement_excerpt: str
    output_excerpts: tuple[str, ...]
    omitted_output_count: int

class JobStateDigest:
    schema_version: Literal["job_state_digest.v1"]
    projection_version: Literal["1.0.0"]
    document_id: UUID
    session_id: UUID
    revision_id: UUID
    revision_number: int
    revision_hash: Sha256
    job_title: JobTitleText
    tasks: tuple[JobStateDigestTask, ...]
    omitted_task_count: int
    pending_proposal_ids: tuple[UUID, ...]
    pending_proposal_count: int
    stale_proposal_count: int
    digest_hash: Sha256
```

投影規則固定：

- 依canonical task order最多取前32個tasks；
- 每task最多取前4個outputs；
- task/output excerpt最多240 Unicode code points；超過時取前239個再加`…`；
- pending proposal IDs依`created_at, proposal_id`排序，最多16個；count保留全部數量；
- `digest_hash=canonical_hash(model_dump(exclude={"digest_hash"}))`；
- 不建立digest table、不由LLM摘要、不把pending proposal當accepted truth；
- active episode、gaps、contradictions由下一切片Context Engine與Interview state合成，不塞進Authoring-owned digest。

---

## 6. Identity、hash 與 canonical bytes

### 6.1 Identity ownership

模型輸出不得含任何UUID。application依下列literal名稱使用UUIDv5：

| Identity | Derivation |
|---|---|
| document | `uuid5(session_id, "job-authoring/document")` |
| revision | `uuid5(command_id, "job-authoring/revision")` |
| direct-add task | `uuid5(command_id, "job-authoring/task")` |
| direct new output | `uuid5(command_id, f"job-authoring/output/{index:04d}")` |
| proposed task | `uuid5(proposal_id, "job-authoring/task")` |
| proposed output | `uuid5(proposal_id, f"job-authoring/output/{index:04d}")` |
| edited new output | `uuid5(decision_command_id, f"job-authoring/output/{index:04d}")` |

index使用該輸入tuple的1-based順序；drop不重編persisted proposal IDs。literal字串建立constants並以test鎖定，不得散落複製。

### 6.2 Canonical serialization

新增`app/job_authoring/canonical.py`，逐行採vNext現行`ensure_ascii=False`、`sort_keys=True`、
`separators=(",", ":")`、`allow_nan=False`規則。A1**不移動或修改**R5的hash helper，也不讓Authoring反向importInterview
domain；以parity test對代表Pydantic/dict/tuple/CJK/emoji值證明兩者byte/hash相同。未來若確有第三個consumer，再另案抽成
無業務語意shared utility；本切片不為15行函式擴大R5 blast radius。

### 6.3 Persisted read rule

從DB讀任何snapshot/command/proposal/decision時固定：

1. parse JSON；
2. Pydantic strict model validate；
3. 重新canonical serialize；
4. canonical bytes必須逐byte等於row TEXT；
5. hash必須等於row hash；
6. row query columns的tenant/document/revision/proposal scope必須等於payload；proposal lifecycle欄與decision shape必須一致；
7. 不符時拋`PersistedAuthoringCorruption`，不得自行修補或略過。

---

## 7. Pure transition rules

### 7.1 建立初始文件

輸入：session/profile已存在、job title非空、`CreateJobDocumentCommand.v1`。

輸出：

- deterministic document ID；
- revision 0，empty tasks；
- source=`initial`；
- head指向revision 0；
- digest包含0 task／0 proposal。

一個session的第二次exact create回同一document/revision；若同session已存在但command/job title內容不同，回
`authoring_document_already_exists`，不得建立第二份active draft。

### 7.2 Employee direct add

1. 驗 expected revision ID/hash；
2. 驗 action shape與capacity；
3. application派生task/output IDs；
4. provenance=`employee_document_edit(command_id)`；
5. append task，產revision N+1；
6. head更新；
7. 同document其餘pending proposals全部轉stale；
8. 回revision + fresh digest。

### 7.3 Employee direct replace

1. target task必須存在且version exact；
2. output ID只可屬於target task或null；duplicate／foreign ID fail；
3. statement與output tuple若完全相同，回`no_semantic_change`，不建revision、不stale proposal；
4. 否則保留task ID與位置，task version+1；
5. 保留的output沿用ID；null output派生新ID；
6. 新內容provenance全部改成`employee_document_edit(command_id)`；舊來源仍可由parent revision查到；
7. 建revision、CAS head、stale其他pending proposals。

### 7.4 Proposal create

1. 以`FOR SHARE`讀取並鎖定vNext session row；
2. exact驗`evidence_state_version/hash`；
3. 每個Evidence ID必須存在於同session、status=active、hash exact；
4. 讀document head並驗base revision ID/hash；
5. 若proposal ID已存在，payload hash exact則idempotent return；不同則conflict；
6. application派生proposed task/output IDs；
7. 建pending proposal；**不建document revision、不改head**；
8. 回proposal + revision未變的digest。

### 7.5 Accept

1. 鎖session `FOR SHARE`，再鎖document，最後鎖proposal；
2. proposal必須pending且document/base revision exact；
3. 所有Evidence basis仍須active且hash exact；否則proposal轉stale後commit，回typed stale；
4. 由exact proposed task materialize canonical `JobTask(entity_version=1)`，加上`accepted_ai_proposal` provenance後append至draft；
5. 建revision N+1，source=`ai_proposal_accept`；
6. proposal轉accepted並保存decision/result revision；
7. document head CAS更新；其他pending proposal轉stale；
8. 同一transaction commit後回revision + digest。

### 7.6 Edit then accept

流程同accept，但先驗edited IDs與內容：

- task ID沿用proposed task ID；
- 保留output只可使用proposal outputs；new output使用null並由decision command派生；
- provenance=`employee_proposal_edit(proposal_id)`；
- final bundle若逐byte等於proposal，要求caller改送accept；
- 建revision，proposal status=`edited`。

### 7.7 Reject

- 鎖document/proposal並驗base仍exact；
- proposal轉`rejected`、保存decision；
- 不建revision、不改head、不stale其他proposal；
- fresh digest只改pending count；
- proposal row就是後續「不要無新support立即重提」的最小suppression fact；A1不做semantic dedup policy。

### 7.8 Stale rule

A1採**保守的document-head stale**：任何成功建立新revision的command，都把同document、不同proposal ID的pending proposal
以`document_revision_advanced`標成stale。若decision path發現未被標記但base/head已不同，使用`base_revision_changed`；若
Evidence status/hash已變，使用`evidence_basis_changed`。A1只有`add_task` proposal，尚無可靠target overlap analyzer；不做
靜默rebase比錯誤套用安全。

後續支援replace/remove時，才以target entity version/fingerprint放行non-overlap edits。實作者不得在A1偷偷加入generic merge engine。

---

## 8. Typed result／error contract

application不得把SQLAlchemy/Pydantic例外直接漏給caller。至少提供：

| Code | 語意 | 是否改DB |
|---|---|---:|
| `authoring_document_not_found` | document不在scope | 否 |
| `authoring_document_already_exists` | session已有不同create內容 | 否 |
| `authoring_revision_conflict` | expected head ID/hash不符 | 否 |
| `authoring_task_not_found` | replace target不存在 | 否 |
| `authoring_task_version_conflict` | target entity version不符 | 否 |
| `authoring_output_scope_invalid` | output ID不屬target/proposal | 否 |
| `authoring_capacity_exceeded` | task/output上限超過 | 否 |
| `authoring_no_semantic_change` | direct replace沒有語意改變 | 否 |
| `authoring_proposal_not_found` | proposal不在scope | 否 |
| `authoring_proposal_already_decided` | terminal proposal收到不同decision | 否 |
| `authoring_proposal_stale` | base/head或Evidence basis已變 | proposal可轉stale |
| `authoring_evidence_invalid` | create時Evidence缺失／非active／hash不符 | 否 |
| `authoring_idempotency_conflict` | 同command/proposal ID不同canonical內容 | 否 |
| `persisted_authoring_corruption` | DB bytes/hash/scope不一致 | 否；fail closed |

write service回傳下列discriminated Pydantic union；不要用`dict`或HTTP status作domain contract：

```python
class AuthoringRevisionCommitted:
    outcome: Literal["revision_committed"]
    revision: JobDocumentRevision
    digest: JobStateDigest
    proposal: TaskProposalView | None

class AuthoringProposalCreated:
    outcome: Literal["proposal_created"]
    proposal: TaskProposalView
    digest: JobStateDigest

class AuthoringProposalRejected:
    outcome: Literal["proposal_rejected"]
    proposal: TaskProposalView
    digest: JobStateDigest

class AuthoringProposalStaled:
    outcome: Literal["proposal_staled"]
    proposal: TaskProposalView
    digest: JobStateDigest
    reason_code: ProposalStaleReason

class AuthoringNoSemanticChange:
    outcome: Literal["no_semantic_change"]
    revision: JobDocumentRevision
    digest: JobStateDigest
```

`AuthoringProposalStaled`是成功commit的business outcome：service必須先保存stale transition並commit，再return，不能以exception離開
UoW造成rollback。其他表中「是否改DB=否」的validation/conflict使用typed `AuthoringError(code, details)` exception；FastAPI mapping留給
未來thin adapter。

---

## 9. Application ports 與 service API

### 9.1 Ports

`ports.py`只定義A1需要的方法：

```python
class AuthoringDocumentRepository(Protocol):
    async def get(..., for_update: bool = False) -> AuthoringDocumentRecord | None: ...
    async def get_by_session(...): ...
    async def add(...): ...
    async def compare_and_set_head(...): ...

class AuthoringRevisionRepository(Protocol):
    async def get(...): ...
    async def get_by_command_id(...): ...
    async def add(...): ...

class AuthoringProposalRepository(Protocol):
    async def get(..., for_update: bool = False): ...
    async def add(...): ...
    async def decide(...): ...
    async def mark_other_pending_stale(...): ...
    async def list_for_digest(...): ...

class AuthoringEvidenceReader(Protocol):
    async def lock_session_state(...): ...

class AuthoringUnitOfWork(Protocol):
    documents: AuthoringDocumentRepository
    revisions: AuthoringRevisionRepository
    proposals: AuthoringProposalRepository
    evidence: AuthoringEvidenceReader
    async def commit(...): ...
```

不建立repository registry、generic aggregate repository或base service class。

### 9.2 Public application functions

`service.py`只暴露：

```python
create_job_document(uow_factory, command)
get_job_document(uow_factory, tenant_id, document_id)
apply_employee_task_bundle(uow_factory, command)
create_task_proposal(uow_factory, command)
decide_task_proposal(uow_factory, command)
list_task_proposals(uow_factory, tenant_id, document_id, statuses=...)
get_job_state_digest(uow_factory, tenant_id, document_id)
```

query function在read transaction先以`FOR SHARE`讀document head，再讀exact revision與proposal summaries；釋放transaction後才對
已取得的immutable values作pure digest projection。所有write function在commit前完成hydrate/revalidation；provider/network call
不得在UoW內。

### 9.3 Lock ordering

全切片固定順序：

```text
需要Evidence的命令：interview_vnext_sessions -> job_authoring_documents -> job_authoring_proposals
不需要Evidence的命令：job_authoring_documents -> job_authoring_proposals（若有）
```

任何新path不得先鎖proposal再鎖document，也不得持有transaction時呼叫LLM。

---

## 10. PostgreSQL migration `0011`

### 10.1 為何需要新表，不沿用 `document_versions`

`document_versions`把整份OCS JSON當content，proposal只存在`_pending`，無法獨立驗base revision、Evidence closure或decision audit。
把A1塞回該表會在接K/S與task linkage時再次重構。三張小表是必要產品domain，不是提前SaaS化。

### 10.2 Table 1：`job_authoring_documents`

| Column | Type | Null | 規則 |
|---|---|---:|---|
| `document_id` | UUID | no | PK |
| `tenant_id` | UUID | no | storage scope |
| `session_id` | UUID | no | 一session一document |
| `head_revision_id` | UUID | no | application-enforced pointer |
| `head_revision_number` | BIGINT | no | >=0 |
| `head_revision_hash` | TEXT | no | sha256 regex |
| `created_at` | TIMESTAMPTZ | no | UTC |
| `updated_at` | TIMESTAMPTZ | no | >=created_at |

constraints/indexes：

- PK `document_id`；
- unique `uq_ja_docs_tenant_document(tenant_id, document_id)`；
- unique `uq_ja_docs_tenant_session(tenant_id, session_id)`；
- FK `(tenant_id, session_id)` → `interview_vnext_sessions(tenant_id, session_id)`，`ON DELETE RESTRICT`；
- index `ix_ja_docs_tenant_updated(tenant_id, updated_at DESC, document_id)`；
- explicit CAS SQL同時比對`head_revision_id + head_revision_number + head_revision_hash`。

`head_revision_id`刻意不建跨向revision的circular FK；每次hydrate必須讀exact revision並驗tenant/document/number/hash。這沿用vNext
pointer由application hydrate fail-closed保證的做法，避免為三表prototype引入nullable head或deferred circular cleanup。

### 10.3 Table 2：`job_authoring_revisions`

| Column | Type | Null | 規則 |
|---|---|---:|---|
| `revision_id` | UUID | no | PK |
| `tenant_id` | UUID | no | scope |
| `document_id` | UUID | no | parent aggregate |
| `revision_number` | BIGINT | no | >=0 |
| `parent_revision_id` | UUID | yes | revision0=null，其他必填 |
| `source_kind` | TEXT | no | exact allowlist |
| `command_schema_id` | TEXT | no | stable schema ID |
| `command_id` | UUID | no | idempotency |
| `command_json` | TEXT | no | canonical object |
| `command_hash` | TEXT | no | sha256 |
| `snapshot_schema_id` | TEXT | no | `job_document_draft.v1` |
| `snapshot_json` | TEXT | no | canonical object |
| `snapshot_hash` | TEXT | no | sha256 |
| `occurred_at` | TIMESTAMPTZ | no | command clock |
| `created_at` | TIMESTAMPTZ | no | DB/application persisted clock |

constraints/indexes：

- unique `(tenant_id, revision_id)`；
- unique `(tenant_id, document_id, revision_number)`；
- unique `(tenant_id, command_id)`；
- FK `(tenant_id, document_id)` → documents，RESTRICT；
- self FK `(tenant_id, parent_revision_id)` → revisions，RESTRICT；nullable；
- CHECK initial shape：revision0只有`source_kind=initial`且parent null；revision>0不得initial且parent非null；
- CHECK JSON object、sha256、time與source allowlist；
- UPDATE rejection trigger：revision immutable；A1無production delete API，tenant-scoped test cleanup與migration downgrade仍可按FK
  反向順序DELETE/drop。

hydrate另驗parent屬同document且number恰為current-1；DB self FK只保證identity存在，不以跨列CHECK假裝能表達連續性。

### 10.4 Table 3：`job_authoring_proposals`

| Column | Type | Null | 規則 |
|---|---|---:|---|
| `proposal_id` | UUID | no | PK |
| `tenant_id` | UUID | no | scope |
| `document_id` | UUID | no | aggregate |
| `base_revision_id` | UUID | no | immutable |
| `base_revision_hash` | TEXT | no | immutable sha256 |
| `evidence_state_version` | BIGINT | no | >=0 |
| `evidence_state_hash` | TEXT | no | sha256 |
| `source_kind` | TEXT | no | scripted/llm_operation |
| `source_id` | UUID | no | run/case或operation |
| `proposal_schema_id` | TEXT | no | active v1 |
| `proposal_json` | TEXT | no | canonical immutable payload |
| `proposal_hash` | TEXT | no | sha256 |
| `status` | TEXT | no | pending/accepted/edited/rejected/stale |
| `decision_command_id` | UUID | yes | employee terminal才有 |
| `decision_schema_id` | TEXT | yes | employee terminal才有 |
| `decision_json` | TEXT | yes | canonical |
| `decision_hash` | TEXT | yes | sha256 |
| `result_revision_id` | UUID | yes | accept/edit必填 |
| `stale_reason` | TEXT | yes | stale必填；`ProposalStaleReason` allowlist |
| `created_at` | TIMESTAMPTZ | no | |
| `resolved_at` | TIMESTAMPTZ | yes | terminal必填 |
| `updated_at` | TIMESTAMPTZ | no | |

constraints/indexes：

- unique `(tenant_id, proposal_id)`；
- partial unique `(tenant_id, decision_command_id) WHERE decision_command_id IS NOT NULL`；
- FK document、base revision、result revision，全部scope在同tenant且RESTRICT；hydrate再驗revision屬同document；
- index `(tenant_id, document_id, status, created_at, proposal_id)`；
- lifecycle CHECK：
  - pending：無decision/result/stale/resolved；
  - accepted/edited：decision四欄+result+resolved非空，stale_reason空；
  - rejected：decision四欄+resolved非空，result/stale空；
  - stale：decision/result空，stale_reason+resolved非空；
- guarded update trigger只允許pending一次轉terminal及`updated_at`改變；immutable payload/base/source欄不得改；
- test cleanup依proposal→revision→document順序刪，測試專用cleanup可在明確tenant scope下使用`DELETE`；production不提供
  delete API，且所有cross-row FK均RESTRICT。

### 10.5 Exact database object names

PostgreSQL identifier一律使用以下名稱；不要讓Alembic/SQLAlchemy自動命名核心constraint：

```text
job_authoring_documents
  PK  job_authoring_documents_pkey
  UQ  uq_ja_docs_tenant_document
  UQ  uq_ja_docs_tenant_session
  FK  fk_ja_docs_session
  CK  ck_ja_docs_head_number
  CK  ck_ja_docs_head_hash
  CK  ck_ja_docs_time_order
  IX  ix_ja_docs_tenant_updated

job_authoring_revisions
  PK  job_authoring_revisions_pkey
  UQ  uq_ja_revs_tenant_revision
  UQ  uq_ja_revs_document_number
  UQ  uq_ja_revs_tenant_command
  FK  fk_ja_revs_document
  FK  fk_ja_revs_parent
  CK  ck_ja_revs_number_parent
  CK  ck_ja_revs_source
  CK  ck_ja_revs_command_hash
  CK  ck_ja_revs_snapshot_hash
  CK  ck_ja_revs_command_json
  CK  ck_ja_revs_snapshot_json
  TR  ja_revs_reject_update
  FN  ja_revs_reject_update_fn

job_authoring_proposals
  PK  job_authoring_proposals_pkey
  UQ  uq_ja_props_tenant_proposal
  FK  fk_ja_props_document
  FK  fk_ja_props_base_revision
  FK  fk_ja_props_result_revision
  CK  ck_ja_props_source
  CK  ck_ja_props_state_version
  CK  ck_ja_props_base_hash
  CK  ck_ja_props_state_hash
  CK  ck_ja_props_payload_hash
  CK  ck_ja_props_payload_json
  CK  ck_ja_props_decision_json
  CK  ck_ja_props_stale_reason
  CK  ck_ja_props_lifecycle
  CK  ck_ja_props_time_order
  IX  uq_ja_props_decision_command       # partial UNIQUE
  IX  ix_ja_props_document_status
  TR  ja_props_guard_update
  FN  ja_props_guard_update_fn
```

`ck_ja_props_decision_json`允許NULL；非NULL時`jsonb_typeof(decision_json::jsonb)='object'`。proposal update trigger只允許
`status/decision_*/result_revision_id/stale_reason/resolved_at/updated_at`依合法pending→terminal transition改變；若immutable欄位的
`IS DISTINCT FROM`為true就raise。

employee terminal hydrate另驗：accepted↔`action=accept`、edited↔`action=edit`、rejected↔`action=reject`；row
`decision_command_id/result_revision_id/resolved_at`必須逐欄等於decision payload。stale沒有decision，reason只能是上述三個值。

### 10.6 Migration cycle

新增 `apps/api/alembic/versions/0011_job_authoring_core.py`：

```text
upgrade: documents -> revisions -> proposals -> indexes/triggers
downgrade: proposal trigger/table -> revision trigger/table -> documents
```

`0010 -> 0011 -> 0010` 必須在可拋棄 migration DB完整實跑，且0010八表與v3既有表的schema/row snapshot逐byte不變。

---

## 11. Persistence adapter exact behavior

### 11.1 SQLAlchemy rows

新增`postgres_models.py`並由`alembic/env.py`明確import註冊metadata。rows不跨出adapter；application只看Pydantic record。
不用ORM relationship、cascade或`version_id_col`；CAS使用explicit SQL。

### 11.2 UoW

`SqlAlchemyAuthoringUnitOfWork`一instance一AsyncSession一transaction，未explicit commit一律rollback。它不得繼承
`SqlAlchemyVNextUnitOfWork`；兩者可共用session factory與少量serialization helper，但不共享mutable repository instance。

### 11.3 Evidence bridge

`SqlAlchemyAuthoringEvidenceReader.lock_session_state()`：

1. `SELECT interview_vnext_sessions ... FOR SHARE`；
2. 沿用vNext serialization hydrate `InterviewState.v3`與state hash檢查；
3. 回`EvidenceSourceSnapshot(session_id, state_version, state_hash, active Evidence map)`；
4. 不把ORM row或完整InterviewState存進proposal；只持久化已選Evidence basis refs與source state authority。

不得由Authoring domain import `InterviewState`。具體adapter可以import並轉成Authoring port DTO。

### 11.4 Idempotency order

每個write service先查existing command/proposal identity，再檢stale precondition：

1. existing + canonical hash exact →回原結果；
2. existing + hash不同 →idempotency conflict；
3. 不存在 →才驗head/proposal/Evidence並執行。

這避免client timeout後重送成功命令，卻因head已前進而錯報stale。

---

## 12. Scripted end-to-end golden

A1不呼叫模型。golden使用現行R5 fixture builder或production command/reducer建立一個真`InterviewState.v3`，至少含一筆
active Evidence，其內容能支持：

```text
task：彙整各門市缺貨明細並提出補貨建議
output：補貨建議表
```

不得直接SQL偽造Evidence row或跳過R5 state validator。

real-PG golden至少建立四個獨立document分支：

1. **accept**：pending不改draft；accept後task/output出現在revision1；
2. **edit**：員工將task或output改寫後採用；revision內容是employee final value，provenance正確；
3. **reject**：proposal terminal rejected，head仍revision0；
4. **stale**：proposal建立後employee direct add/replace；舊proposal stale，decision不能套用；
5. **direct edit**：新增後再replace，task ID/position保留、version+1、new output ID deterministic；
6. 每個分支都驗digest、DB reopen hydrate、exact idempotent replay與tenant/session scope。

golden是application產品loop自測，不是模型品質eval，不產promotion verdict或paid cost。

---

## 13. Exact file plan

### 13.1 新增 production files

```text
apps/api/app/job_authoring/
  __init__.py
  AGENTS.md
  contracts.py
  commands.py
  canonical.py
  transitions.py
  digest.py
  errors.py
  ports.py
  service.py
  postgres_models.py
  postgres.py
  schema_exports.py
  write_schemas.py
  schemas/
    job-document-draft.v1.schema.json
    job-document-revision.v1.schema.json
    create-job-document-command.v1.schema.json
    employee-task-bundle-command.v1.schema.json
    create-task-proposal-command.v1.schema.json
    ai-task-bundle-proposal.v1.schema.json
    task-proposal-view.v1.schema.json
    employee-proposal-decision-command.v1.schema.json
    employee-proposal-decision.v1.schema.json
    job-state-digest.v1.schema.json

apps/api/alembic/versions/
  0011_job_authoring_core.py
```

只有上述10個top-level seam需要committed schema；nested task/output/provenance由其parent schema引用，不另產十幾份碎schema。
`job_authoring/AGENTS.md`必須指向ADR 0038與本計畫，並重申domain dependency、AI-only-proposal、employee decision、
no legacy editor/OCS source-of-truth與三表上限；不得複製整份計畫形成第二份規格。

### 13.2 新增 tests

```text
apps/api/tests/test_job_authoring_contracts.py
apps/api/tests/test_job_authoring_transitions.py
apps/api/tests/test_job_authoring_digest.py
apps/api/tests/test_job_authoring_dependencies.py
apps/api/tests/test_job_authoring_migration.py
apps/api/tests/test_job_authoring_postgres.py
apps/api/tests/test_job_authoring_vertical_postgres.py
```

### 13.3 可修改的既有檔案

| File | 允許改動 |
|---|---|
| `apps/api/alembic/env.py` | import Authoring ORM metadata |
| `apps/api/tests/conftest.py` | 增加Authoring tenant-scoped cleanup，且先於vNext session刪除 |
| `apps/api/tests/test_interview_vnext_migration.py` | single head預期從0010改0011；0010自身cycle語意不改 |
| `apps/api/app/interview_vnext/AGENTS.md` | R5 complete、Authoring 0011例外、active plan link |
| `apps/api/app/interview_vnext/README.md` | A1 active scope/status與link |
| `docs/README.md` | plan index |
| R5-D plan §18 | link A1並把indicator收斂為deferred |

### 13.4 禁止順手修改

除非本文件停線條件成立並由owner另行核准，不得修改：

- `app/interview_vnext/domain/*`；
- `app/interview_vnext/application/operation_executor.py`、`context_builder.py`；
- `app/interview_vnext/llm/*`；
- `evals/interview_vnext/providers/*`；
- 12 case fixtures/gold/suite hash；
- `app/interview/*`、`app/core/domain/ocs_doc.py`；
- `packages/ocs-contract`、`apps/web`、indexer/embedder；
- dependency/lock files。

如果為了A1必須改上述檔案，先證明最小原因與blast radius，不得用「方便整合」當理由。

---

## 14. Test matrix

### 14.1 Contracts／schema

至少覆蓋：

- strict unknown-field rejection、frozen、tuple collections；
- blank與長度邊界（繁中、emoji、CRLF）；
- add／replace command shape matrix；
- accept／edit／reject decision shape matrix；
- evidence basis非空、unique與hash格式；
- draft task/output identity closure；
- duplicate ID、foreign output ID、capacity limit；
- generated schema與committed files byte-equal；
- schema writer連跑兩次、兩個temp dir byte-equal；
- historical vNext schema files零diff。

### 14.2 Identity／determinism

- 每個§6.1 literal的UUIDv5 golden；
- 相同command/proposal輸入得到相同IDs/hash/revision；
- output drop不改其他persisted ID；
- direct replace保留task ID與position；
- canonical JSON對dict key order不敏感、對tuple order敏感；
- 繁中/emoji serialization保留原字；
- 共用canonical helper後，R5既有代表state/artifact hash golden不變。

### 14.3 Pure transitions

| Vector | Expected |
|---|---|
| empty draft + direct add | revision1，task v1，outputs deterministic |
| replace exact target | same task ID/position，version+1 |
| replace stale target version | typed conflict，state不變 |
| replace foreign output ID | scope invalid，state不變 |
| replace no semantic change | no revision/no stale |
| accept exact proposal | materialize same proposed IDs/text/basis + accepted provenance後append |
| edit proposal | employee final value + employee provenance |
| edit equal proposed | reject shape，要求accept |
| reject | no document mutation |
| task/output capacity | fail closed |

### 14.4 Digest

- revision metadata與hash exact；
- canonical order → T01/T02；
- 32 task、4 output、240 code-point boundaries；
- CJK/emoji截斷不切壞Unicode code point；
- omitted counts exact；
- pending IDs order/cap與count；
- reject/stale後counts更新但revision不變；
- input不變時byte/hash完全相同；
- digest不含完整proposal reason、Evidence text、transcript、public reference或hidden reasoning。

### 14.5 Migration introspection

`test_job_authoring_migration.py`在獨立可拋棄DB執行：

1. upgrade到0010；
2. 插v3 + vNext fixture並snapshot既有tables；
3. upgrade0011；
4. exact introspect三表 columns/nullability/PK/unique/FK/CHECK/index/trigger；
5. 驗所有constraint identifiers <63 bytes；
6. 插一組合法document/revision/proposal lifecycle；
7. 逐一證明invalid lifecycle/hash/json/cross-scope被拒；
8. revision UPDATE被trigger拒；proposal lifecycle以外的payload mutation被拒；
9. downgrade0010；Authoring objects/functions全消失；
10. 0010八表與v3 snapshot完全不變。

現行`test_migration_0010_cycle_preserves_v3_and_builds_exact_schema`仍只跑到0010並驗八表，不能改成模糊「至少存在」測試。

### 14.6 Repository／corruption

- create/read/reopen full hydrate；
- head pointer missing/wrong revision/wrong number/wrong hash；
- noncanonical JSON bytes、valid JSON wrong hash、schema major unknown；
- revision parent不存在、跨document或number不連續；
- proposal base/result revision跨document；
- proposal status／decision／result lifecycle columns彼此不一致；
- exact idempotent replay與same-ID-different-hash conflict；
- explicit document head CAS只有一個concurrent writer成功；
- transaction failure時revision/proposal/head全部rollback，不留半套；
- tenant A不能讀/決定tenant B proposal。

### 14.7 Evidence closure

- active exact Evidence可建proposal；
- missing、superseded、withdrawn、wrong session、wrong hash全部拒絕；
- evidence state version/hash stale拒絕proposal create；
- proposal建立後Evidence被supersede，accept/edit會把proposal轉stale、不建revision；
- reject不需要重新聲稱proposal內容正確，但仍要求proposal/head scope exact；
- consultant turn、reference text與Inference ID不能冒充Evidence basis。

### 14.8 Decision／concurrency

- accept/edit revision + proposal decision + head + stale-other-proposals同transaction；
- reject只更新proposal；
- 兩個worker同時決定同proposal，只能一個terminal decision；
- 一個worker direct edit、一個accept：依lock/CAS次序只能有一個基於舊head成功；另一個typed stale；
- timeout後重送exact command回相同result，不新增revision；
- terminal proposal收到different command回already-decided/idempotency conflict，不改原audit。

### 14.9 Dependency guards

AST/import test至少禁止：

- Authoring domain/commands/transitions/digest import SQLAlchemy、FastAPI、provider SDK；
- `job_authoring` import `app.interview` v3、`ocs_contract`、indexer contract、Web DTO；
- `app/interview_vnext/domain`反向import`job_authoring`；
- production `app/` import`evals.*`；
- 新增LangChain/LangGraph/PydanticAI或agent framework dependency。

---

## 15. Implementation sequence／commit slicing

所有commit必須在其宣告gate全綠後才建立。不得commit已知整套會紅的中間狀態；test-first紅可留working tree，但code修綠後
與對應test同commit。

### A0——Baseline audit（不commit）

1. 確認HEAD至少含`2432e98`與`8ab5986`；
2. `git status --short`記錄既有owner變更，不碰不屬本切片的dirty files；
3. Alembic current/heads都為0010；
4. 跑現行full no-network與real-PG baseline；預期參考：
   - no-network `1071 passed / 211 skipped / 0 failed`；
   - full API + real PG `1282 passed / 0 skipped / 0 failed`；
5. 記錄`caliburn-db-1`原始Up/Down狀態；需要時依runbook啟動，交付恢復或據實回報。

若baseline不同但全綠，記錄實際數字後繼續；若有既有fail，先回報，不把它混進A1。

### A1——Domain contracts + pure transitions + digest

新增contracts/commands/transitions/digest/errors、schemas與四個no-network test files。此commit不import DB、不建migration。

建議commit：

```text
feat(authoring): define task revision and proposal contracts
```

commit前：focused contracts/transitions/digest/dependency綠、schema drift零diff、完整no-network 0 fail。

### A2——0011 + PostgreSQL adapter

新增migration、rows、ports、postgres repository/UoW/Evidence reader與migration/postgres tests；更新Alembic env、head assertion、cleanup。

建議commit：

```text
feat(authoring): persist canonical document revisions and proposals
```

commit前：A1 tests、migration full cycle、Authoring PG suite、全部vNext real-PG與完整no-network全綠；Alembic head唯一0011。

### A3——Application service + product-loop golden

實作service exact transactions與scripted vertical real-PG golden。不得加HTTP route或模型adapter。

建議commit：

```text
feat(authoring): apply employee decisions to task proposals
```

commit前：全部A1 tests、concurrency/idempotency/corruption、vertical golden、full API+real PG與no-network全綠。

### A4——Docs/status

回寫本文件實際證據、README、AGENTS與docs index；若實作過程有核准偏差，寫明原因與blast radius，不假裝原計畫就是如此。

建議commit：

```text
docs(authoring): close the minimal authoring core handoff
```

所有commit沿用repo目前owner identity；不得加Codex/AI co-author trailer；不得push。

---

## 16. Verification commands

以下命令以`apps/api`為working directory；實作者可依本機venv使用`uv run`，但必須`--locked`且不得臨時安裝dependency。

### 16.1 Pure/focused

```powershell
uv run --locked pytest `
  tests/test_job_authoring_contracts.py `
  tests/test_job_authoring_transitions.py `
  tests/test_job_authoring_digest.py `
  tests/test_job_authoring_dependencies.py -q
```

### 16.2 Migration／real PostgreSQL

```powershell
$env:TEST_DATABASE_URL='postgresql+asyncpg://postgres:password@localhost:5432/caliburn_test'
uv run --locked alembic upgrade head
uv run --locked pytest `
  tests/test_job_authoring_migration.py `
  tests/test_job_authoring_postgres.py `
  tests/test_job_authoring_vertical_postgres.py -q
```

### 16.3 vNext regression

```powershell
uv run --locked pytest tests/test_interview_vnext_*.py -q
```

PowerShell wildcard若被runner當literal，使用：

```powershell
$files = Get-ChildItem tests -Filter 'test_interview_vnext_*.py' | ForEach-Object FullName
uv run --locked pytest @files -q
```

real-PG gate必須0 skipped。no-network新增PG-only nodes可由既有`require_postgres` skip，但須證明既有passed node沒有轉skip，且PG
gate已實跑同一批nodes。

### 16.4 Full suites

```powershell
# no-network
Remove-Item Env:TEST_DATABASE_URL -ErrorAction SilentlyContinue
uv run --locked pytest -q

# real PostgreSQL
$env:TEST_DATABASE_URL='postgresql+asyncpg://postgres:password@localhost:5432/caliburn_test'
uv run --locked pytest -q
```

### 16.5 Schema／Alembic／hygiene

```powershell
uv run --locked python -m app.job_authoring.write_schemas
git diff --exit-code -- 'apps/api/app/job_authoring/schemas/*.schema.json'
uv run --locked alembic current
uv run --locked alembic heads
git diff --check
git status --short
```

另以`rg`確認：

- `app/job_authoring`無`app.interview`、`ocs_contract`、provider SDK；
- `app/`無`evals.*` production import；
- staged files無`.env`、API key、output bundle、database dump；
- migration只有0011，無0012；
- dependency/lockfile零diff。

---

## 17. Definition of Done

全部成立才可將A1標為Completed：

1. 一個session只建立一份canonical document與revision0；
2. direct add/replace在real PG建立immutable revisions，CAS/idempotency正確；
3. pending proposal建立時accepted draft byte/hash完全不變；
4. accept、edit、reject三條路徑都有real-PG golden；
5. AI未經employee decision改accepted truth的路徑數=0；
6. direct edit後舊proposal不會被自動套用；
7. stale Evidence basis不會被accept/edit；
8. task/output每個persisted claim都有正確provenance；
9. deterministic digest同輸入byte/hash一致且有明確bound；
10. DB重開後hydrate結果與write response一致；
11. corruption、cross-tenant、concurrency與transaction rollback tests全綠；
12. 0011 upgrade/downgrade不改0010/v3資料；
13. generated schema無drift；
14. full no-network 0 fail，full API+real PG 0 skipped/0 fail；
15. 沒有provider/network/Web/editor/indexer/dependency變更；
16. docs/status與實際程式一致；
17. working tree不含本切片未說明的變更；
18. 未push，commit author/committer只有repo owner。

完成A1只代表**共編authority與revision loop可用**，不代表模型品質、完整JD、production route或end-user UI完成。

---

## 18. Stop conditions：遇到就回報，不要猜

遇到下列任一項立即停線，提供證據、最小重現、2–3個選項、推薦與blast radius：

- 必須修改R5 Evidence/State/schema才能建立proposal；
- 必須讓Authoring domain import舊editor/OCS深JSON才能前進；
- 0011需要超過三張核心表或出現generic event/patch/ACL/framework表；
- 現行DB無法在同transaction驗Evidence state與Authoring write；
- application-enforced head pointer無法在hydrate/corruption tests中fail closed；
- accept/edit無法做到revision+decision+head原子commit；
- lock order造成可重現deadlock；
- exact idempotent replay必須新增全域command bus才可成立；
- digest必須靠LLM summary才可產生；
- scripted vertical要求接OpenRouter、Web或Qdrant才跑得動；
- 為了整合現有editor，必須放棄stable IDs、immutable revision、proposal audit或provenance；
- migration會破壞既有0010/v3資料；
- full suite出現無法歸因於本切片的既有failure。

不得用相容shim、`dict[str, Any]`、吞例外、關閉validator、增加skip或把資料塞進`_pending`來繞過停線。

---

## 19. 實作完成回報格式

交付回報至少包含：

1. A0實際baseline與起始HEAD；
2. A1–A4 commits、subject、author/committer、是否push；
3. 新增／修改檔案與偏離§13預算原因；
4. active contract/schema versions與schema directory hash；
5. migration head、三表exact名稱、upgrade/downgrade結果；
6. documents/revisions/proposals實際constraints/indexes/triggers；
7. direct add/replace與no-op結果；
8. accept/edit/reject/stale每條golden的document/proposal/revision結果；
9. Evidence active/wrong-hash/superseded closure結果；
10. idempotency與concurrency結果；
11. corruption與cross-tenant matrix結果；
12. digest truncation/determinism結果與代表hash；
13. focused pure、migration、Authoring PG、全部vNext PG、full no-network、full real-PG exact counts；
14. schema drift、Alembic heads、dependency/import guards、`git diff --check`；
15. secret/output scan與local Docker狀態；
16. 未完成項、限制與是否阻擋A2；
17. 明確確認未接provider、paid live、production route、Web/editor、reference/K/S；
18. working tree與tag狀態。

---

## 20. A1完成後立即做什麼

A1之後不再擴充Authoring generic能力，也不做 SaaS。為了最快看到可用成品，後續按下列產品順序前進：

1. **Context Engine + `question.select`**：把 Evidence、未解缺口與最新 `JobStateDigest` 組成 operation-specific context，選出最有資訊價值的一題；
2. **`episode.code/1.x` 工作分析**：用 OpenRouter 將一段已訪談內容分析成 id-less task/output proposal，再映射到本切片的 `CreateTaskProposalCommand`；
3. **最小本機 Web workspace**：聊天、文件預覽／直接編輯、AI 提案的接受／修改／拒絕共用同一 application service；不先做登入、組織或多人協作；
4. **真模型產品 loop eval**：評估提問效率、task/output 正確性、證據支持與使用者修訂量，而非再增加底層 framework；
5. 產品 loop 穩定後，再依序加入 behavior indicator、duty、K/S、公版 retrieval 與 publication/export。

Context Engine 的第一段資料流如下：

```text
InterviewState Evidence + Authoring JobStateDigest
  -> operation-specific Context Engine
  -> deterministic candidate gaps
  -> question.select/1.x
  -> consultant acknowledgement + one natural next question + persisted QuestionFrame
```

A2仍不需要`episode.code`寫文件。A2全綠後做A3：以active episode Evidence呼叫`episode.code/1.x`，將id-less task/output
candidates轉成A1已完成的`CreateTaskProposalCommand`。接上最小workspace後，才是第一個員工可真正對話、看見文件逐步形成、
直接編輯並審核AI建議的測試品。

indicator、duty、K/S、公版retrieval與publication依序後接；不得回頭把A1擴成一次完成整份JD的mega-slice。

---

## 21. 實作紀錄（完成時回寫）

狀態：**Completed（核心 application 可被後續 API／workspace／LLM operation 呼叫）**。

實作進度：
- A0 baseline（green-before）：no-network `1071 passed / 211 skipped / 0 failed`；full real-PG `1371 passed / 0 failed`（= 原 1282 + A1 89）。`caliburn-db-1` 起始即 Up(healthy)。
- A1：committed `d555667 feat(authoring): define task revision and proposal contracts`（author/committer 皆 owner，未 push）。89 focused / 1160 full no-network 全綠；10 個 schema drift 零 diff；dependency guard 經負向自證。
- A2：committed `b15ff516 feat(authoring): persist canonical document revisions and proposals`（author/committer 皆 owner，未 push）。三張表、repository/UoW、Evidence bridge、migration full cycle、leaf-first test cleanup 完成；A1/A2 focused + migration `94 passed`、adapter real-PG `4 passed`、全部 vNext real-PG `894 passed / 0 skipped`、full no-network `1160 passed / 216 skipped / 0 failed`；Alembic 唯一 head `0011`。
- A3：committed `5534011 feat(authoring): apply employee decisions to task proposals`（author/committer 皆 owner，未 push）。七個 application use cases與 discriminated result union完成；一條 real-PG golden以四份獨立document覆蓋 accept／edit／reject／direct edit + stale、DB reopen與exact replay。Authoring focused `95 passed`，A3 vertical `1 passed`，full no-network `1160 passed / 217 skipped / 0 failed`。
- A4：本 docs/status commit；同步 README／AGENTS／docs index，並鎖定單機產品與 LLM 工作分析優先級。

核准偏差與限制：

- 依 owner「加速看到成品、測試不求全面覆蓋」裁決，A3 沒再建立大規模 concurrency/cross-scope 組合矩陣，也未在 A3 後重跑整套 full real-PG；資料層風險由 A2 migration/repository gates與 A3 真 PostgreSQL golden覆蓋。架構不變量沒有刪除。
- 新增的 no-network skip 只有 `test_job_authoring_vertical_postgres.py` 這一個真 PostgreSQL node；它在 real-PG 已實跑通過，不是以 skip 規避驗收。
- 本切片未接 provider、network、paid live、production route、Web/editor、reference、indicator 或 K/S；所以它是可用 application core，不是員工已能操作的完整成品。
- `caliburn-db-1` 在本次開始前已運行，交付時保持運行；沒有 down、刪 volume 或 push。

---

## 22. A2 施工裁決與 adapter API 草案（2026-07-23，owner 核可）

本節記錄 A2 動 adapter 前，owner 對 plan 未寫死處的三點裁決與據此定的 adapter API。**不新增 ADR、不另起架構研究**；adapter 實作以本節為準。

### 22.1 三點裁決

1. **`edit` 後與提案逐 byte 相同 → 沿用 `authoring_no_semantic_change`（不新增錯誤碼）。**
   員工選「修改 AI 提案」但改後內容與原提案完全一致時：不建 revision、不改 proposal 狀態、回 typed
   `AuthoringError(code="authoring_no_semantic_change", details={"required_action":"accept"})`，讓 UI 提示改按「接受」；
   **不得自動替員工接受**。須區分：一般文件編輯無變化 → 回 `AuthoringNoSemanticChange` 正常 outcome；修改 AI 提案無變化 → 回 typed error 要求改用 accept。（已於 `transitions.materialize_edit` 實作並鎖測試。）
2. **revision self-FK 維持 production `ON DELETE RESTRICT`；測試 cleanup 用葉節點迴圈。**
   不為測試改 cascade / deferrable。tenant-scoped 測試 cleanup 順序：先刪 proposals → 每輪刪「目前無 child 的 revision」→ 重複到 revisions 清空 → 最後刪 document。**防呆:若仍有 revision 但某輪刪除數為 0,立即 fail**(不得無限迴圈或靜默留資料)。此為測試 helper,非 production 通用刪除。
3. **先定 adapter API(本節 22.2–22.4),核可後才寫 persistence adapter。** 另:migration 0011 docstring 已修正為「downgrade 會刪三張 authoring tables 與其資料,限 pre-production/dev/test,不影響 0010/vNext」。

### 22.2 Adapter-boundary record DTOs（`ports.py`）

皆 frozen；**raw ORM row、raw JSON、完整 `InterviewState` 一律不得穿過 adapter boundary**。

```python
class AuthoringDocumentRecord:      # mutable head pointer 列
    document_id: UUID; tenant_id: UUID; session_id: UUID
    head_revision_id: UUID; head_revision_number: int; head_revision_hash: Sha256
    created_at: UtcDatetime; updated_at: UtcDatetime

class AuthoringRevisionRecord:       # immutable revision + command 稽核欄(不帶 raw json)
    tenant_id: UUID                  # 保留 storage scope(domain payload 不含 tenant)
    revision: JobDocumentRevision    # 已 hydrate + §6.3 驗證
    command_schema_id: str; command_hash: Sha256; created_at: UtcDatetime

class AuthoringProposalRecord:       # repo 以 row status/decision/payload 組出的 query view
    tenant_id: UUID                  # 保留 storage scope
    view: TaskProposalView; proposal_hash: Sha256; created_at: UtcDatetime

class EvidenceSourceSnapshot:        # 最小形狀;不暴露 InterviewState/ORM
    tenant_id: UUID; session_id: UUID
    state_version: int; state_hash: Sha256
    active_evidence: tuple[EvidenceBasisRef, ...]  # 只含 active,依 evidence_id.bytes 排序
    # frozen model 的 dict 欄位不會真的凍結,故用既有 EvidenceBasisRef tuple;
    # service 需查找時自建暫時 dict,不另立 ActiveEvidenceDTO。

class DigestProposalSummary:         # 供 digest 投影(bounded IDs 與總數分離)
    pending: tuple[tuple[UtcDatetime, UUID], ...]   # (created_at, proposal_id),最多前 16 筆
    pending_count: int                              # 全部 pending 總數(可 > 16)
    stale_count: int                                # 全部 stale 總數
# digest.build_job_state_digest(revision, pending_proposals=summary.pending,
#   pending_proposal_count=summary.pending_count, stale_proposal_count=summary.stale_count)
# count 由 SQL COUNT 求,不得為算總數把所有 proposal 無上限載入記憶體。
```

### 22.3 Repository / UoW / Evidence 方法簽章與語意

```python
AuthoringDocumentLock = Literal["none", "share", "update"]   # 單一參數,不用互斥 bool
ProposalStatus = Literal["pending", "accepted", "edited", "rejected", "stale"]

class AuthoringDocumentRepository(Protocol):
    async def get(tenant_id, document_id, *, lock: AuthoringDocumentLock = "none")
        -> AuthoringDocumentRecord | None
        # lock: none / share(FOR SHARE,query projection 用) / update(FOR UPDATE,write 用);不存在回 None
    async def get_by_session(tenant_id, session_id, *, lock: AuthoringDocumentLock = "none")
        -> AuthoringDocumentRecord | None
    async def add(record: AuthoringDocumentRecord) -> None
        # INSERT head;撞 uq_ja_docs_tenant_session → raise AuthoringError(DOCUMENT_ALREADY_EXISTS)
    async def compare_and_set_head(tenant_id, document_id, *, expected_revision_id,
        expected_revision_number, expected_revision_hash, new_revision_id,
        new_revision_number, new_revision_hash, updated_at) -> bool
        # 條件式 UPDATE ... WHERE head_*=expected_*;回 True 表 1 列更新(原子 CAS),False → caller raise REVISION_CONFLICT

class AuthoringRevisionRepository(Protocol):
    async def get(tenant_id, revision_id) -> AuthoringRevisionRecord | None       # 不存在回 None
    async def get_by_command_id(tenant_id, command_id) -> AuthoringRevisionRecord | None  # 建 revision 的命令 idempotency
    async def add(revision: JobDocumentRevision, command: AuthoringCommand) -> None
        # 內部序列化 command → schema_id/json/hash;INSERT immutable 列

class AuthoringProposalRepository(Protocol):
    async def get(tenant_id, proposal_id, *, for_update=False) -> AuthoringProposalRecord | None
    async def get_by_decision_command_id(tenant_id, command_id)
        -> AuthoringProposalRecord | None
        # reject 不建 revision,decision 存 proposal 列;reject exact retry 在 stale/head 檢查前辨識;
        # 同 command_id 用於他 proposal → IDEMPOTENCY_CONFLICT。查到必為 terminal,不加鎖。
    async def add(proposal: AiTaskBundleProposal) -> None                          # INSERT status=pending
    async def decide(tenant_id, proposal_id, *, status, decision, result_revision_id,
        stale_reason, resolved_at, updated_at) -> bool
        # UPDATE ... WHERE tenant_id AND proposal_id AND status='pending'(受 trigger+CHECK)。
        # 1 列→True;0 列→False(service 重讀,分類 not_found / already_decided);>1 列→PersistedAuthoringCorruption。
        # partial-unique(decision_command)衝突翻成 IDEMPOTENCY_CONFLICT,不得漏 IntegrityError。
    async def mark_other_pending_stale(tenant_id, document_id, *, keep_proposal_id,
        reason, resolved_at, updated_at) -> tuple[UUID, ...]                        # 回被標 stale 的 proposal_ids,依 proposal_id 排序(不依賴 RETURNING 順序)
    async def list(tenant_id, document_id, *, statuses: tuple[ProposalStatus, ...])
        -> tuple[AuthoringProposalRecord, ...]                                      # 固定 created_at ASC, proposal_id ASC;無 pagination
    async def list_for_digest(tenant_id, document_id) -> DigestProposalSummary

class AuthoringEvidenceReader(Protocol):
    async def lock_session_state(tenant_id, session_id) -> EvidenceSourceSnapshot
        # SELECT interview_vnext_sessions ... FOR SHARE;adapter 內 hydrate InterviewState.v3 + 驗 state_hash;
        # 只回最小 snapshot(InterviewState/ORM 不外流);session 不存在 → raise AuthoringError(EVIDENCE_INVALID)

class AuthoringUnitOfWork(Protocol):        # async context manager
    documents; revisions; proposals; evidence
    async def commit() -> None
```

`AuthoringCommand = CreateJobDocumentCommand | EmployeeTaskBundleCommand | EmployeeProposalDecisionCommand`。

### 22.5 A2 commit 前必測(owner 指定,除既有 §14.5/§14.6 矩陣外)

`FOR SHARE` query 鎖成立;17 筆 pending → digest 回 16 IDs + `pending_count=17`;reject exact replay(不重複建 decision);decision command collision(同 command_id 用於他 proposal → `IDEMPOTENCY_CONFLICT`);`list` 排序(created_at, proposal_id);`decide()` 零列更新的 not_found / already_decided 分流。

### 22.4 鎖 / 回傳 / 錯誤區分 / 交易歸屬 / 邊界

- **回傳約定**:查無 → `None`(service 轉 `DOCUMENT_NOT_FOUND`/`PROPOSAL_NOT_FOUND`);CAS 失敗 → `compare_and_set_head` 回 `False`(service 轉 `REVISION_CONFLICT`);終態轉移/標 stale → 回 affected IDs;persisted 不一致 → repo hydrate 直接 raise `PersistedAuthoringCorruption`(§6.3 fail-closed,不自修不略過)。
- **idempotency**:write service 先 `get_by_command_id`/`get`;存在且 hash 相同 → 回原結果;存在且 hash 不同 → `IDEMPOTENCY_CONFLICT`;不存在才驗 head/evidence 後執行(§11.4)。
- **鎖順序(§9.3)**:需 Evidence 的命令 `interview_vnext_sessions(FOR SHARE) → job_authoring_documents(FOR UPDATE) → job_authoring_proposals(FOR UPDATE)`;不需 Evidence 的 `documents → proposals`。任何 path 不得先鎖 proposal 再鎖 document,持交易時不得呼叫 LLM/network。
- **交易歸屬**:`SqlAlchemyAuthoringUnitOfWork` = 一 `AsyncSession` 一 transaction 的 async context manager;`__aenter__` 開,未 explicit `commit()` 則 `__aexit__` rollback。**service 開 UoW、在 commit 前完成所有 hydrate/revalidation、再 commit**;provider/network 不得在 UoW 內。UoW 不繼承 `SqlAlchemyVNextUnitOfWork`,可共用 session factory 與少量 serialization helper。
- **邊界不變量**:repo 只回 22.2 的 frozen record;`command_json/snapshot_json/proposal_json/decision_json` 等 raw bytes 只在 adapter 內;`InterviewState.v3` 只在 Evidence reader 內 hydrate,對外僅 `EvidenceSourceSnapshot`。
