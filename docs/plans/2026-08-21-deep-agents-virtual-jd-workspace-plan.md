# Deep Agents 虛擬 JD 工作區 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 以 Deep Agents 受限 VFS 取代 model-facing candidate mega-form 與三個自寫來源 Tool，讓模型在隔離候選 JD 上讀／增／改／刪、取得 deterministic diagnostics 後發布待審 semantic diff，同時修正 rejection memory 與 edit-accept Evidence 兩個已確認缺口。

**Architecture:** 一個 `CompositeBackend` 將 `/skills`、`/sources`、`/approved`、`/pending` 掛成只讀 application projections，並以受限 `StateBackend` 承接唯一可寫的 `/candidate/<run_id>`。Deep Agents `FilesystemMiddleware` 提供六個通用 editor verbs；Caliburn 的空 payload `check_candidate_document` 只解析 framework 真實 after-state、解析 Evidence、建立 semantic changeset receipt。模型 final 只引用最後成功 receipt；員工 authority command 仍是唯一能改核准 JD 的邊界。

**Tech Stack:** Python 3.13、Pydantic 2、LangChain 1.3.15、LangGraph 1.2.11、Deep Agents 0.7.5、PostgreSQL、FastAPI、Next.js／React、pytest、Vitest／Testing Library。

**Spec:** `docs/adr/0064-deep-agents-virtual-jd-workspace-and-deterministic-evidence-anchor.md`；研究證據見 `docs/specs/2026-08-21-provider-neutral-virtual-jd-editor-and-evidence-anchor-research.md`。

## Global Constraints

- 核准 JD 只能由員工 `accept`／`edit-and-accept`／direct edit command 改變；VFS、Tool、模型 final 都沒有 approved write edge。
- 本輪不做 RAG／Reference、能力級別、A、auto-accept、多人協作或正式品質 eval。
- 使用 pinned Deep Agents framework primitives；不得自寫通用 filesystem、patch DSL、shell、host filesystem 或 operation-per-tool compatibility layer。
- 只暴露 `ls`、`read_file`、`grep`、`write_file`、`edit_file`、`delete`、`check_candidate_document`；不得暴露 `glob`、`execute`、舊來源 Tool、舊 candidate Tool 或專用 split／merge Tool。
- `/skills`、`/sources`、`/approved`、`/pending` 是只讀；只有當前 `/candidate/<run_id>` 可寫。backend policy 是 hard boundary，framework private permissions 不是唯一防線。
- `write_file` 只建立新 resource；`edit_file` 禁止 `replace_all=true`；`delete` 只刪單一合法 entity resource。
- 同 wave 的重疊 mutation 及 check＋mutation 必須整波拒絕；平行 read 與不同 entity mutation可以保留。
- 模型只提供 source handle、exact quote、必要時 1-based occurrence；application 對 raw immutable source 決定 offsets，不做 trim、Unicode normalization 或猜測。
- 初始 hard ceiling 為八次 model calls；總 Tool、token、cost、elapsed、recursion 與兩波 lookup 上限仍保留。
- `tool_token_limit_before_evict=None`、`human_message_token_limit_before_evict=None`；不得形成 `/large_tool_results` 或 `/conversation_history`。
- 每一 task 先取得正確 RED，再寫最小 production code，focused gate 綠後才 commit；不得把現有 false-dirty ADR 0060 metadata 納入 commit。

---

### Task 1: 修正 rejection fingerprint 與 edit-accept OPKS provenance

**Files:**
- Modify: `apps/api/app/consultant/document_review.py`
- Modify: `apps/api/app/consultant/document_authority.py`
- Test: `apps/api/tests/test_consultant_document_review.py`
- Test: `apps/api/tests/test_consultant_durable_authority_postgres.py`

**Interfaces:**
- Consumes: `ReviewableDocumentChange`、`DocumentPatchAction`、`SourceReference`、既有 employee-text delta extractor。
- Produces: evidence-independent rejection key；只對實際員工文字 delta 附加 direct-edit source 的 accepted action、changeset 與 OPKS document evidence。

- [ ] **Step 1: 寫 rejection bypass 的 failing unit tests**

新增兩個測試，固定同一 ADD OPKS payload、axis、Task linkage 與 source；第二次只改 `skill_ids` 或同一 quote 的 anchor 表示，均應拋出 `RejectedChangeRequiresNewEvidence`。另以真正不同的 committed employee source 證明可以再次提出。

```python
def test_rejected_opks_add_cannot_reappear_by_changing_method_or_anchor() -> None:
    rejected = _rejected_opks_add(skill_ids=("output",), anchored=False)
    for replay in (
        _same_opks_add(skill_ids=("output", "story-interview"), anchored=False),
        _same_opks_add(skill_ids=("output",), anchored=True),
    ):
        with pytest.raises(RejectedChangeRequiresNewEvidence):
            _create_again(rejected, replay)

def test_rejected_opks_add_may_reappear_with_new_employee_source() -> None:
    assert _create_again(rejected, _same_opks_add(source_id=new_source)).actions
```

- [ ] **Step 2: 跑 RED 並確認錯在 target key 混入 Evidence／Skill**

Run: `cd apps/api && uv run pytest tests/test_consultant_document_review.py -k "rejected_opks_add" -q`

Expected: 只改 Skill／anchor 的案例未拋例外；新 source 案例維持可建立。

- [ ] **Step 3: 將 semantic fingerprint 與 Evidence 分離**

讓 `_target_key()` 只包含 operation、path、canonical proposed content、OPKS axis 與 logical linkage；source IDs、quote anchors、Skill IDs 留在 action evidence。`_ensure_not_rejected_without_new_evidence()` 先比相同 semantic key／read-set，再以 source set 是否真的增加作准入。

```python
def _target_key(change: ReviewableDocumentChange) -> str:
    canonical = _canonical_semantic_after(change.after)
    linkage = _logical_linkage_key(change)
    axis = change.opks_kind.value if change.opks_kind is not None else "none"
    return f"{change.operation.value}:{change.path}:{axis}:{linkage}:{sha256(canonical).hexdigest()}"
```

- [ ] **Step 4: 寫 edit-accept OPKS provenance 的 failing tests**

測試 AI 提出 OPKS text、員工改字後接受：核准 OPKS、terminal action 與 changeset 均包含 direct-edit source；其 `SourcePositionAnchor` 指向實際採用文字。另測只改 display order／task linkage 時不鑄造也不附加文字 Evidence。

```python
async def test_opks_edit_accept_attaches_direct_edit_source_to_adopted_text(runtime) -> None:
    snapshot = await _edit_accept_opks_text(runtime, "每週五完成採購異常報表")
    source = await runtime.get_source(snapshot.document_id, direct_edit_source_id)
    assert snapshot.approved_document.opks[0].evidence_source_ids[-1] == source.source_id
    assert source.positions[0].start == 0
    assert source.text[source.positions[0].start:source.positions[0].end] == "每週五完成採購異常報表"

async def test_structural_edit_accept_does_not_attach_text_evidence(runtime) -> None:
    assert (await _edit_accept_opks_order(runtime)).new_source_id is None
```

- [ ] **Step 5: 跑 RED，最小修正 authority apply 與 durable decision**

在 `apply_review_command()` 先計算哪些 action 有 employee textual delta；只為那些 action 建立含 direct-edit source 的 authority copy。`apply_document_actions()` 以該 action 的 `source_ids` 附加 OPKS evidence；terminal action 更新 `source_ids`，並重建 `DocumentChangeSet.source_ids` 使 validator 重新驗證。純結構 action 保持原 evidence。

```python
employee_evidence_action_ids = {
    item.action_id
    for item in applicable
    if edited_action_source_payload((item,), {item.action_id: edited[item.action_id]})
}
authority_actions = tuple(
    _with_employee_source(item, source_reference.source_id)
    if item.action_id in employee_evidence_action_ids else item
    for item in applicable
)
document = apply_document_actions(document, authority_actions, edited_after_by_action_id=edited)
```

- [ ] **Step 6: 跑 focused GREEN 與 commit**

Run: `cd apps/api && uv run pytest tests/test_consultant_document_review.py tests/test_consultant_durable_authority_postgres.py -q`

Expected: 全綠，且 PostgreSQL fixture 無 skip。

Commit: `fix: preserve employee review and evidence authority`

---

### Task 2: 建立 canonical resource codec、stable handles 與 deterministic quote resolver

**Files:**
- Create: `apps/api/app/consultant/workspace_resources.py`
- Create: `apps/api/app/consultant/evidence_anchor.py`
- Modify: `apps/api/app/consultant/provider_wire.py`
- Test: `apps/api/tests/test_consultant_workspace_resources.py`
- Test: `apps/api/tests/test_consultant_evidence_anchor.py`

**Interfaces:**
- Consumes: `ApprovedJobDocument`、pending `DocumentChangeSet`、`EmployeeSource`、`SkillId`。
- Produces: `WorkspaceCatalog`、canonical JSON files、`CandidateDocumentDraft`、`OutputEvidenceReference` 與 `resolve_evidence_reference()`。

- [ ] **Step 1: 寫 resource round-trip 與 model wire RED**

以含 Duty、孤立 Task、O/P/K/S 與既有 A 的文件建立 catalog。斷言 deterministic handles、固定 JSON key order、round-trip 保留所有可編輯欄位；A 與 competency 不出現在 model-editable resources且 parser 會從 baseline保留。`OutputEvidenceReference.model_json_schema()` 不得包含 `start`／`end`。

```python
def test_workspace_resources_round_trip_editable_jd_without_exposing_a_or_level() -> None:
    catalog = WorkspaceCatalog.from_snapshot(document, pending=())
    files = project_candidate_files(catalog, run_id=run_id)
    assert list(json.loads(files[f"/candidate/{run_id}/tasks/task-001.json"])) == EXPECTED_TASK_KEYS
    assert "competency_level" not in files[f"/candidate/{run_id}/tasks/task-001.json"]
    assert parse_candidate_files(catalog, files).approved_document.opks[-1].kind.value == "attitude"

def test_model_evidence_reference_has_quote_occurrence_but_no_offsets() -> None:
    schema = OutputEvidenceReference.model_json_schema()
    assert set(schema["properties"]) == {"source_handle", "quote", "occurrence", "skill_ids"}
```

- [ ] **Step 2: 跑 RED**

Run: `cd apps/api && uv run pytest tests/test_consultant_workspace_resources.py tests/test_consultant_evidence_anchor.py -q`

Expected: import error，因兩個新 module 尚不存在。

- [ ] **Step 3: 實作 typed resources 與 catalog**

建立 frozen／extra-forbid Pydantic models：`CandidateHeaderResource`、`CandidateDutyResource`、`CandidateTaskResource`、`CandidateOpksResource`、`CandidateReviewGroupsResource`、`WorkspaceEvidenceReference`。`WorkspaceCatalog` 以 deterministic sorted entity/source order配置 `duty-001`、`task-001`、`o-001`、`source-001`，並保存雙向 stable-ID mapping。canonical serializer 固定 `indent=2`、`ensure_ascii=False`、尾端換行。

```python
class WorkspaceEvidenceReference(WorkspaceModel):
    source_handle: Handle
    quote: NonEmptyText
    occurrence: int = Field(default=1, ge=1)
    skill_ids: tuple[SkillId, ...] = Field(min_length=1)

def canonical_resource_json(value: BaseModel) -> str:
    return json.dumps(value.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n"
```

- [ ] **Step 4: 寫 quote resolver 的中文／重複／gutter／更正 RED**

以 literal expected offsets 測唯一中文 quote、跨行 quote、同文重複 occurrence、out-of-range、quote 不存在、含 `1→` gutter、superseded source。不得由測試 helper 重算 expected offsets。

```python
def test_resolver_finds_second_chinese_occurrence_in_raw_source() -> None:
    anchor = resolve_exact_quote(raw="核對訂單，再核對訂單。", quote="核對訂單", occurrence=2)
    assert (anchor.start, anchor.end) == (7, 11)

def test_resolver_rejects_read_file_gutter() -> None:
    with pytest.raises(EvidenceAnchorError, match="quote does not occur"):
        resolve_exact_quote(raw="核對訂單", quote="1→核對訂單", occurrence=1)
```

- [ ] **Step 5: 實作 resolver 並跑 GREEN**

`resolve_exact_quote()` 只用 Python code-point exact substring 搜尋；唯一命中允許省略 occurrence，多命中必須明確 occurrence。`resolve_evidence_reference()` 透過 catalog 將 handle 映成當前 immutable source，拒絕跨文件／superseded source，輸出既有 durable `QuoteAnchor`。

Run: `cd apps/api && uv run pytest tests/test_consultant_workspace_resources.py tests/test_consultant_evidence_anchor.py -q`

Commit: `feat: add canonical JD resources and evidence resolver`

---

### Task 3: 以 Deep Agents CompositeBackend 建立五個 namespace

**Files:**
- Create: `apps/api/app/consultant/workspace_backend.py`
- Modify: `apps/api/app/consultant/skill_backend.py`
- Modify: `apps/api/app/consultant/context.py`
- Test: `apps/api/tests/test_consultant_workspace_backend.py`
- Test: `apps/api/tests/test_consultant_agent_and_skills.py`

**Interfaces:**
- Consumes: Task 2 `WorkspaceCatalog`／canonical files、`PostgresConsultantRuntime` source read methods、Deep Agents `BackendProtocol`／`StateBackend`／`CompositeBackend`。
- Produces: `ConsultantWorkspaceBackendBinding`，內含共用 composite backend、package Skill backend、candidate state backend與 current run catalog。

- [ ] **Step 1: 寫 framework characterization 與 permission RED**

使用真 `FilesystemMiddleware` Tool coroutine 驗證 root 只列五個 namespace；candidate create/edit/delete成功，覆寫、`replace_all`、刪目錄、寫 `/approved`／`/sources`／`/skills`／`/pending`、讀其他 run 均回 structured error。確認 middleware eviction thresholds 為 `None`，state 不產生隱藏 routes。

```python
async def test_only_current_candidate_namespace_is_mutable(real_filesystem_tools) -> None:
    assert (await invoke("write_file", current_new_path, VALID_TASK_JSON)).status == "success"
    for path in (approved_path, source_path, skill_path, pending_path, other_run_path):
        assert (await invoke("write_file", path, "{}" )).status == "error"

async def test_framework_offload_namespaces_are_disabled(agent_state) -> None:
    assert not any(path.startswith(("/large_tool_results", "/conversation_history")) for path in agent_state["files"])
```

- [ ] **Step 2: 跑 RED**

Run: `cd apps/api && uv run pytest tests/test_consultant_workspace_backend.py -q`

Expected: import error，因 backend binding 尚不存在。

- [ ] **Step 3: 實作 mount-relative read-only backends**

調整 `PackageSkillBackend` 只作 `/skills/` route 的 mount-relative backend，仍保留 selected Skill、full-read-once與 loaded receipt。新增 `ApprovedProjectionBackend`、`PendingProjectionBackend`、`EmployeeSourceProjectionBackend`：前三者 write/edit/delete 一律拒絕；source 的 `als/aread/agrep` 直接 await runtime，current grep 排除 historical revisions並保留 max_count／truncated。

```python
composite = CompositeBackend(
    default=CandidatePolicyBackend(StateBackend(), run_id=run_id, initial_paths=candidate_paths),
    routes={
        "/skills/": skill_backend,
        "/sources/": source_backend,
        "/approved/": approved_backend,
        "/pending/": pending_backend,
    },
)
```

- [ ] **Step 4: 實作 candidate policy wrapper**

wrapper 重驗 POSIX absolute path、exact `/candidate/<run_id>/` prefix與 resource grammar。`write` 先讀並拒絕 existing path；`edit` 拒絕 `replace_all`；`delete` 只接受 header 以外的單一 duty/task/opks entity file，不接受 prefix／directory。同步與 async 方法共享純 policy，不把 async DB 包進 worker thread。

- [ ] **Step 5: 跑 source parity／Skill／permission GREEN**

Run: `cd apps/api && uv run pytest tests/test_consultant_workspace_backend.py tests/test_consultant_agent_and_skills.py -q`

Expected: stable-ID read、oldest-to-newest lineage、current-only lexical grep與 full Skill receipt 均全綠。

Commit: `feat: mount scoped consultant virtual workspace`

---

### Task 4: 建立 wave safety 與空 payload check Tool

**Files:**
- Create: `apps/api/app/consultant/workspace_tools.py`
- Modify: `apps/api/app/consultant/agent.py`
- Test: `apps/api/tests/test_consultant_workspace_tools.py`
- Test: `apps/api/tests/test_consultant_agent_and_skills.py`

**Interfaces:**
- Consumes: Task 3 backend binding、Task 2 parser、LangChain `ToolRuntime`／`AgentMiddleware`。
- Produces: `CandidateCheckPort`、`CandidateCheckToolBinding`、`build_check_candidate_document_tool()`、`WorkspaceToolWaveMiddleware`。

- [ ] **Step 1: 寫 Tool surface、schema 與 wave RED**

characterization 只允許 `{ls, read_file, grep, write_file, edit_file, delete, check_candidate_document}`。check 的 model-facing schema 必須是 empty object；禁止 document payload。建立同一 AI message 的工具波：平行 reads成功、不同 entity edits成功；同 path／ancestor overlap及 mutation＋check均整波 error且後端零 mutation。

```python
def test_workspace_tool_surface_has_no_business_or_host_tools(agent) -> None:
    assert {tool.name for tool in agent.tools} == EXPECTED_WORKSPACE_TOOLS
    assert check_tool.tool_call_schema.model_json_schema()["properties"] == {}

async def test_check_and_mutation_in_one_wave_are_both_rejected(scripted_agent) -> None:
    result = await scripted_agent.ainvoke(_wave(edit_call, check_call))
    assert _tool_statuses(result) == ["error", "error"]
    assert _candidate_text(result) == ORIGINAL_TEXT
```

- [ ] **Step 2: 跑 RED**

Run: `cd apps/api && uv run pytest tests/test_consultant_workspace_tools.py -q`

- [ ] **Step 3: 實作 wave middleware**

`WorkspaceToolWaveMiddleware.awrap_tool_call()` 從最後一個 AI message 的完整 `tool_calls` 建立 deterministic wave plan。若包含 check＋mutation或 mutation paths相同／ancestor-descendant，依 tool_call_id 全部回相同 actionable `ToolMessage(status="error")`；不依 completion order上鎖後放行部分呼叫。

```python
conflict = analyze_workspace_wave(last_ai_message.tool_calls)
if conflict is not None:
    return ToolMessage(name=name, tool_call_id=tool_call_id, status="error", content=conflict)
return await handler(request)
```

- [ ] **Step 4: 實作 empty-input check Tool**

Tool 透過 binding 讀目前 backend真實 files，呼叫 `CandidateCheckPort.check_candidate_document()`；成功回 revision／digest／ordered action handles與 semantic actions，失敗回可修 issues。像現有 ToolRuntime hidden slot一樣覆寫 `tool_call_schema`，model schema不出現 runtime或文件 payload。

- [ ] **Step 5: 跑 GREEN 與 framework schema metric**

Run: `cd apps/api && uv run pytest tests/test_consultant_workspace_tools.py tests/test_consultant_agent_and_skills.py -q`

另以 `convert_to_openai_tool` 記錄 schemas、properties、optional、union、open objects、depth與 bytes；actual tool names不得出現 host／legacy business tools。

Commit: `feat: add safe virtual JD edit and check tools`

---

### Task 5: 將 resource after-state 轉成 verified semantic publication

**Files:**
- Create: `apps/api/app/consultant/candidate_publication.py`
- Modify: `apps/api/app/adapters/langgraph/postgres.py`
- Modify: `apps/api/app/consultant/graph.py`
- Modify: `apps/api/app/consultant/state.py`
- Delete: `apps/api/app/consultant/candidate_workspace.py`
- Test: `apps/api/tests/test_consultant_candidate_publication.py`
- Test: `apps/api/tests/test_consultant_candidate_loop.py`
- Test: `apps/api/tests/test_consultant_durable_authority_postgres.py`

**Interfaces:**
- Consumes: parsed `CandidateDocumentDraft`、baseline document/revision、pending actions、resolved Evidence、loaded Skills。
- Produces: `CandidateCheckRequest`、durable `CheckedCandidateReceipt` 與 existing `DocumentChangeSet` review bundle。

- [ ] **Step 1: 寫 semantic diff／receipt／lifecycle RED**

覆蓋 header、Duty、Task、O/P/K/S create/edit/delete，application配置正式 UUID/order；Task拆分以 create兩 Task＋重連 OPKS＋delete舊 Task形成 atomic group。invalid linkage、Evidence、unknown handle只回 issues且 review queue為零。成功 check後再 edit造成 digest mismatch；old run receipt不能發布；成功 publication與 active receipt清除同 transition。

```python
async def test_checked_candidate_only_publishes_exact_latest_resource_digest(runtime) -> None:
    receipt = await check_candidate(runtime, files=VALID_FILES)
    mutated = {**VALID_FILES, task_path: CHANGED_TASK_JSON}
    with pytest.raises(CandidatePublicationStale):
        await publish(runtime, receipt=receipt, current_files=mutated)
    assert (await runtime.snapshot(document_id)).review_queue == ()

async def test_task_split_is_general_atomic_resource_diff(runtime) -> None:
    receipt = await check_candidate(runtime, files=SPLIT_FILES)
    assert {a.operation.value for a in receipt.actions} == {"add", "revise", "withdraw"}
    assert len({a.atomic_subgroup_id for a in receipt.actions}) == 1
```

- [ ] **Step 2: 跑 RED**

Run: `cd apps/api && uv run pytest tests/test_consultant_candidate_publication.py tests/test_consultant_candidate_loop.py -q`

- [ ] **Step 3: 實作 parser→diff→changeset pipeline**

以 baseline stable ID mapping與 canonical resource paths產生 granular `ReviewableDocumentChange`；新增 identity只由 application `uuid5(document_id, run_id/resource-handle)`配置。Evidence refs先經 Task 2 resolver。`review-groups.json` 只能引用已知 changed handles；application再依 linkage補齊不可分割 closure，不信任 model漏列依賴。

- [ ] **Step 4: 取代 durable scratch model**

將舊 `CandidateWorkspace`／tool receipts改為 `CheckedCandidateReceipt`：只保存 run、baseline revision、resource digest、candidate revision、changeset、used Skills與check call ID。DB lock內重讀 Current JD／sources、驗 read-set並寫 outer graph `checked_candidate` channel；不保留 `active_candidate` compatibility alias。check不改 review queue；final publication才把 exact changeset移入 review queue並清 checked receipt。

```python
class CheckedCandidateReceipt(DurableModel):
    run_id: UUID
    baseline_revision: int
    candidate_revision: int
    resource_digest: Digest
    check_call_id: NonEmptyText
    used_skill_ids: tuple[SkillId, ...]
    changeset: DocumentChangeSet
```

- [ ] **Step 5: 跑 PostgreSQL GREEN 與零殘留檢查**

Run: `cd apps/api && uv run pytest tests/test_consultant_candidate_publication.py tests/test_consultant_candidate_loop.py tests/test_consultant_durable_authority_postgres.py -q`

Expected: 無 skip；測後 consultant documents／checkpoint／Store fixtures依既有 cleanup歸零。

Commit: `refactor: publish verified virtual JD candidates`

---

### Task 6: Hard-cut model wire、來源 Tool 與五步 profile

**Files:**
- Modify: `apps/api/app/consultant/agent.py`
- Modify: `apps/api/app/consultant/model_output.py`
- Modify: `apps/api/app/consultant/provider_wire.py`
- Modify: `apps/api/app/consultant/results.py`
- Modify: `apps/api/app/consultant/run_service.py`
- Modify: `apps/api/app/consultant/model_runtime.py`
- Modify: `apps/api/app/config.py`
- Delete: `apps/api/app/consultant/candidate_tool.py`
- Delete: `apps/api/app/consultant/candidate_wire.py`
- Modify: `apps/api/app/consultant/context.py`
- Test: `apps/api/tests/test_consultant_model_output.py`
- Test: `apps/api/tests/test_consultant_model_runtime.py`
- Test: `apps/api/tests/test_consultant_run_service.py`
- Test: `apps/api/tests/test_consultant_hard_cut.py`

**Interfaces:**
- Consumes: Task 3 workspace binding、Task 4 tools、Task 5 checked receipt、Task 2 resolved `AnalysisBasis`。
- Produces: provider-neutral seven-tool agent、八步 bounded profile、compact final publication reference。

- [ ] **Step 1: 寫 hard-cut 與八步 RED**

AST/import tests禁止 `candidate_wire`、`candidate_tool`、`employee_source_get/lineage/search`、`OutputQuoteAnchor.start/end`。scripted agent走八次 model calls成功，第九次由 framework `ModelCallLimitMiddleware` 拒絕；兩波 lookup限制只計 `ls/read_file/grep`，mutation/check不冒充 lookup。

```python
def test_interactive_profile_allows_eight_model_steps_and_rejects_ninth() -> None:
    assert run_script(EIGHT_STEP_EDIT_CHECK_REPAIR_FINAL).status == "completed"
    with pytest.raises(ModelCallLimitExceededError):
        run_script(NINE_STEP_SCRIPT)
```

- [ ] **Step 2: 跑 RED**

Run: `cd apps/api && uv run pytest tests/test_consultant_model_runtime.py tests/test_consultant_run_service.py tests/test_consultant_hard_cut.py -q`

- [ ] **Step 3: 組裝共用 workspace middleware**

`build_professional_consultant_agent()` 建立一次 `ConsultantWorkspaceBackendBinding`，同一 composite backend供 `SkillsMiddleware`與`FilesystemMiddleware`。filesystem tools allowlist固定六個、eviction關閉；另加入 check Tool與wave middleware。刪除 source/candidate business tools及 compatibility aliases。`ConsultantContextMiddleware` 不再把完整 approved／pending／source 內容塞回 dynamic prompt，只保留目前焦點、Gap、可信 Progress、必要澄清、短 workspace index與當輪員工訊息；詳細內容由 VFS按需讀取。

- [ ] **Step 4: 改 final Evidence 與 publication wire**

`OutputAnalysisBasis` 使用 `OutputEvidenceReference`；run service在 map result前以 current catalog＋runtime async解析成 durable `AnalysisBasis`。`OutputCandidatePublication` 與 internal `CandidatePublication` 只保留 candidate revision、resource digest與ordered action IDs，不重送文件。final前以 response files重算 resource digest，防止 check後修改。既有 stable-prefix prompt cache block與usage receipt必須保持；只更新固定 Tool schema，不把任何動態 workspace內容移進 cache prefix。

- [ ] **Step 5: 設八步 defaults 並跑 GREEN**

將 `Settings.consultant_max_model_calls` 預設改為 8，agent guard改成 `> 8`；既有總 Tool／token／cost／elapsed／retry維持。lookup middleware改為 path-aware：只計 `/skills`、`/sources`、`/approved`、`/pending` 的 `ls/read_file/grep` wave，候選區內的 editor read不誤耗來源 lookup quota。更新 `.env.example`／runbook若存在相同設定，不碰本機 `.env` secrets。

Run: `cd apps/api && uv run pytest tests/test_consultant_model_output.py tests/test_consultant_model_runtime.py tests/test_consultant_run_service.py tests/test_consultant_hard_cut.py -q`

Commit: `refactor: hard-cut to virtual JD model interface`

---

### Task 7: 端到端 authority、partial review 與 crash/retry gate

**Files:**
- Modify: `apps/api/tests/test_consultant_candidate_loop.py`
- Modify: `apps/api/tests/test_consultant_durable_authority_postgres.py`
- Modify: `apps/api/tests/test_consultant_interview_flow.py`
- Modify: `apps/api/tests/test_consultant_context.py`
- Modify: `apps/api/tests/test_app_wiring.py`

**Interfaces:**
- Consumes: 完整 VFS agent、PostgreSQL runtime、員工 review commands。
- Produces: 可重現的完整產品流程安全網；production code只修這些測試揭露的 integration defects。

- [ ] **Step 1: 寫完整產品情境 RED**

以真 `create_agent`＋scripted model＋真 filesystem Tools＋PostgreSQL跑：讀 source/Skill→edit→check failure→repair→recheck→final→九項接受、一項 O 拒絕→下一輪 context只含九項核准與拒絕記憶。另測 unpublished scratch遇direct edit被丟棄、published pending遇同欄direct edit stale、defer不改 approved、atomic split不可部分接受。

- [ ] **Step 2: 跑 RED 並只修 integration root cause**

Run: `cd apps/api && uv run pytest tests/test_consultant_candidate_loop.py tests/test_consultant_durable_authority_postgres.py tests/test_consultant_interview_flow.py tests/test_consultant_context.py -q`

Expected: 新情境先因尚未接齊的 lifecycle／context seam失敗；不得用放寬 invariant讓測試通過。

- [ ] **Step 3: 完成 run lifecycle 與 context projection**

新一般 run只初始化目前 run candidate files；舊 scratch不可列讀或發布。pending仍以 `approved=false` overlay進 context，不自動疊入 candidate；只有當輪員工原話明確要求繼續修某個 pending bundle時，模型才可在 `review-groups.json` 引用該 bundle的 action handles，application重驗 dependency／supersession。成功 publication與 checked receipt清除保持同 graph transition。

- [ ] **Step 4: 跑 GREEN、回看北極星並 commit**

逐項核對：單一顧問、動態 Task/Duty/OPKS、員工原話與更正、Focus/Gap/Progress、必要澄清、自然關頁續談、單一可強制匯出、no-RAG、no-A、no-auto-accept均未偏移。

Commit: `test: close virtual JD authority loop`

---

### Task 8: Web semantic review、browser、live model 與完成文件

**Files:**
- Modify only if the regression test exposes a visible gap: `apps/web/src/features/consultant/DocumentReviewPanel.tsx`
- Modify only if the regression test exposes a typed-edit gap: `apps/web/src/features/consultant/DocumentChangeEditor.tsx`
- Modify: `apps/web/src/features/consultant/ConsultantWorkspace.integration.test.tsx`
- Modify: `docs/design/consultant-runtime.md`
- Modify: `docs/specs/2026-08-14-consultant-runtime-north-star-audit-ledger.md`
- Create: `docs/specs/2026-08-21-virtual-jd-workspace-live-smoke.md`
- Create: `docs/specs/2026-08-21-virtual-jd-workspace-completion.md`

**Interfaces:**
- Consumes: unchanged public semantic review contract與production OpenRouter adapter。
- Produces: 員工可用 UI、真 provider證據、可重跑完成報告。

- [ ] **Step 1: 跑 Web regression 並補真 UI test（只在可見行為缺口時改 production）**

員工只能看到 semantic diff、接受、修改後接受、拒絕、延後；不得看到 VFS path、JSON、tool call或每一步 editor。以 role/name查找控制項，鍵盤完成每個決策；Accessible Name由可見 label或`aria-label`提供。

Run: `cd apps/web && npm run test && npx tsc --noEmit && npm run lint`

- [ ] **Step 2: 跑 API／contract／monorepo完整 gates**

Run:

```text
cd apps/api && uv run pytest -q
npm run check-codegen -w @caliburn/job-analysis-contract
npx turbo test --force --env-mode=loose
git diff --check
```

Expected: 零 unexpected failure；任何既存環境問題要用證據區分，不得冒充 pass。

- [ ] **Step 3: 跑 GPT-5.6 Luna 窄 live smoke**

只使用本專案 `apps/api/.env` 的 key/base URL，不輸出 secret。情境必須實際產生至少一次 edit error或domain diagnostic，再由模型修正、check成功與final publication；記錄每 model step、Tool名稱/status、cache write/read tokens、cost、latency、requested/actual provider。額外用 owner指定的第二 profile做一次窄 probe；若不可用，記實際 provider錯誤而不換模型冒充。

- [ ] **Step 4: 以 in-app browser 驗證真頁面**

啟動 current API/Web，建立 disposable文件並完成一輪：員工回答→AI candidate→semantic review→修改一項後接受→拒絕另一項→刷新頁面。確認核准 JD只含接受值、拒絕記憶仍在、VFS細節不可見、accessible name與鍵盤操作正常。清除測試文件與本地服務。

- [ ] **Step 5: 更新設計／證據／完成報告並接受 Final Gate**

完成報告只引用 `git rev-parse`／`git log` 重跑指令，不硬編易失效的 tag SHA或 commit count。記錄兩個 review缺口、root cause、RED/GREEN、schema metric、真模型與browser結果、已知延後項目（RAG、A、能力級別、正式 eval）。確認 ADR 0060–0063只由0064 successor關係取代，Accepted歷史未事後改寫。

Commit: `docs: close virtual JD workspace upgrade`

- [ ] **Step 6: 建立本地 tag並交付獨立審核**

Tag: `consultant-virtual-jd-workspace-v1`

獨立 reviewer必須對照 ADR 0064、產品大方向與 base diff，只回報可重現 Critical/Important findings；修正後重跑相應 focused gate與Final Gate，通過才進 finishing-a-development-branch 流程。
