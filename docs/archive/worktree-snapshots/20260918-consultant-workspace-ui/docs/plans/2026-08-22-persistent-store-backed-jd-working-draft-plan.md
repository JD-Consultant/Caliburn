# 持久 Store-backed AI JD 工作草稿 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把單次 run 的 `/candidate/<run-id>`、model-facing check／publication handshake 與 durable `review_queue`，升級為每份 JD 一個由 Deep Agents `StoreBackend` 持久化的 `/workspace`；AI 可跨回合續編，application 自動驗證並即時投影語意差異，員工接受、修改後接受、拒絕或延後後，只有核准內容進入正式 JD。

**Architecture:** Deep Agents `StoreBackend` 直接使用既有 LangGraph `AsyncPostgresStore` 保存 canonical workspace files；`CompositeBackend` 只路由 `/skills`、`/sources`、`/approved`、`/workspace`、`/review`。LangGraph Saver 繼續保存對話、interrupt、run／command receipt 與 authority state。application 只新增薄 manifest、JD semantic differ、Evidence verifier 與可恢復 authority command；不建立第二張 workspace 表、不自寫 filesystem、不把完整 workspace 放進 prompt。

**Tech Stack:** Python 3.13、Pydantic 2、LangChain 1.3.15、LangGraph 1.2.11、Deep Agents 0.7.5、`langgraph-checkpoint-postgres` 3.1.2、PostgreSQL、FastAPI、Next.js／React、pytest、Vitest／Testing Library。

**Specs and evidence:** [ADR 0066](../adr/0066-persistent-ai-jd-working-draft-and-semantic-review.md)、[ADR 0067](../adr/0067-deep-agents-store-backed-jd-working-draft.md)、[研究稿](../specs/2026-08-22-persistent-ai-jd-working-draft-and-semantic-review-research.md)、[產品大方向 §9.19](../specs/2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md#919-持久-ai-working-draft-與語意審核校正2026-08-22owner-已核准)。框架行為依 [Deep Agents Backends](https://docs.langchain.com/oss/python/deepagents/backends)、[LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)、[LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) 與 pinned-version characterization tests。

## Product acceptance contract

完成後必須同時成立：

1. 員工未接受的 AI 編輯在下一次訊息、頁面關閉、provider failure 與 process restart 後仍是同一份 active workspace；不從 approved 重建覆蓋。
2. 模型只看到六個低階 editor Tools：`ls`、`read_file`、`grep`、`write_file`、`edit_file`、`delete`。沒有 Duty／Task／OPKS business Tool、專用 split／merge Tool、`check_candidate_document` 或 publication Tool。
3. Task 拆分等複合變更由一般 create／edit／delete 形成；application 只依「能否獨立套用仍合法」分 semantic review group。員工不會看到 raw file diff、Tool JSON 或 graph state。
4. AI 可把 workspace 暫時改成 invalid，但 invalid／unvalidated workspace 不產生可接受 review、不改 approved、不被 export；下一輪能讀到短 diagnostics 並續修。
5. `accept`／`edit-and-accept`／員工 direct edit 是唯一 approved write edge。`reject` 撤回 active workspace 差異並留下 decision memory；`defer` 保留差異。
6. review command 綁 exact approved revision、workspace generation／digest 與 group digest。重疊內容改動後 fail stale；不重疊 group 仍可重新投影並繼續審。
7. 員工原話、來源更正、exact quote anchor 與 Evidence 仍由 Caliburn deterministic verifier 管理；模型不填 offset。
8. 目前焦點、背景線索、gap、可信進度、Skill 按需載入與必要澄清不因 workspace 升級而退回 wizard、一次生成或每個 edit 都問人。
9. 第一版仍不做 RAG／Reference、能力級別、A、auto-accept、多 workspace／branch、Git／PR、多人、多 process、多 Agent或正式 eval 平台。

## Global implementation constraints

- 所有工作在既有隔離 worktree／branch 完成；動手前每次確認 `pwd` 與 `git branch --show-current`。
- 0066／0067 是 Accepted ADR，不事後改寫；若實作證明產品決策必須翻案，停下來與 owner 討論並新增 successor ADR。
- `StoreBackend` 是唯一 workspace file owner；不得同步複製到 `StateBackend.files`、checkpoint channel、application-owned table、host filesystem 或 Git。
- thin manifest 只保存 identity／generation／digest／validation／recovery metadata，不保存第二份 JD JSON。
- framework 暫時不能取代的責任只限 canonical resource codec、JD invariant、semantic differ／dependency grouping、Evidence、employee authority 與 recovery policy。
- Task 1–5 可在分支內短暫與舊 production path 並存以維持每個 commit 可測；Task 6 必須一次 hard cut 並刪除 compatibility path。中間 commit 不 merge／push／tag。
- 既有current文件若尚無workspace namespace，第一次開啟時只從當下approved JD seed；舊run-scoped candidate／review queue是未核准AI產物，不做dual-read或資料搬移。若施工時發現已有必須保存的真實使用者未決資料，Task 6前停下與owner討論，不自行擴張migration。
- 每個 task 都先取得正確 RED，再寫最小 production code，跑 focused gate，做一次「產品北極星」反查，才 commit。
- 每次commit前以`git status --short`確認scope，只stage該Task列出的檔案；不得用`git add -A`把worktree中既有或其他Task的修改混入。
- 不為本輪增加模型 pass、critic、多 Agent或完整 eval；最終只做一個兩回合窄 live smoke 與成本觀測。

---

### Task 1: 建立 persistent workspace resource identity 與薄 manifest

**Files:**
- Modify: `apps/api/app/consultant/workspace_resources.py`
- Create: `apps/api/app/consultant/workspace_state.py`
- Modify: `apps/api/tests/test_consultant_workspace_resources.py`
- Create: `apps/api/tests/test_consultant_workspace_state.py`

**Interfaces:**
- `project_workspace_files(document, *, handle_registry) -> WorkspaceProjection`
- `parse_workspace_files(document_id, files, *, handle_registry) -> WorkspaceDocumentDraft`
- `workspace_resource_digest(files) -> Sha256Digest`
- `WorkspaceManifest`、`WorkspaceDiagnostic`、`WorkspaceProjection`、`WorkspaceDocumentDraft`

- [ ] **Step 1: 寫 `/workspace` 與 stable identity 的 failing tests**

加入以下案例：

- projection 根目錄固定為 `/workspace`，沒有 run ID；
- 不再產生 model-authored `review-groups.json`；
- restart 後相同 handle 對應相同 stable entity ID；
- 新增 `task-new-001` 後接受，再重投影不會改成另一個 handle／UUID；
- Duty／Task／O／P／K／S round-trip 保留目前可編輯欄位，A 與能力級別仍不進 model-editable schema；
- canonical JSON 維持 UTF-8、固定 key order、兩格縮排與結尾 newline。

```python
def test_workspace_projection_has_one_run_independent_root() -> None:
    projection = project_workspace_files(document, handle_registry={})
    assert "/workspace/header.json" in projection.files
    assert not any("/candidate/" in path for path in projection.files)
    assert not any("review-groups" in path for path in projection.files)


def test_new_workspace_handle_keeps_the_same_stable_id_after_restart() -> None:
    first = parse_workspace_files(
        document_id,
        files_with_new_task("task-new-001"),
        handle_registry={},
    )
    second = parse_workspace_files(
        document_id,
        files_with_new_task("task-new-001"),
        handle_registry=first.handle_registry,
    )
    assert first.document.tasks[-1].task_id == second.document.tasks[-1].task_id
```

- [ ] **Step 2: 寫 manifest validator 的 failing tests**

`WorkspaceManifest` 至少包含：`schema_version`、`generation`、`resource_digest`、`approved_baseline_revision`、`approved_baseline_digest`、`evidence_basis_digest`、`validation_status`、`diagnostics`、`entity_ids_by_handle`。測試拒絕負 generation、錯誤 digest、重複 stable ID、valid 狀態仍帶 error diagnostic，以及 manifest digest 與實際 files 不符卻被當成 valid。

```python
class WorkspaceValidationStatus(StrEnum):
    UNVALIDATED = "unvalidated"
    VALID = "valid"
    INVALID = "invalid"
    CONFLICTED = "conflicted"


class WorkspaceManifest(DurableModel):
    schema_version: Literal[1] = 1
    generation: int = Field(ge=0)
    resource_digest: Sha256Digest
    approved_baseline_revision: int = Field(ge=0)
    approved_baseline_digest: Sha256Digest
    evidence_basis_digest: Sha256Digest
    validation_status: WorkspaceValidationStatus
    diagnostics: tuple[WorkspaceDiagnostic, ...] = ()
    entity_ids_by_handle: dict[str, UUID] = Field(default_factory=dict)
```

- [ ] **Step 3: 跑 RED**

Run from `apps/api`:

```text
uv run pytest tests/test_consultant_workspace_resources.py tests/test_consultant_workspace_state.py -q
```

Expected: 新型別／函式尚不存在或舊 projection 仍產生 run-scoped path。

- [ ] **Step 4: 實作最小 resource codec 與 manifest**

沿用已驗證的 Pydantic resource schema與 quote-reference 形狀；`CandidateHeader／Duty／Task／OpksResource`改名為`Workspace*Resource`，並移除 run namespace 與 model-authored review file。既有實體使用 registry 保存 handle→UUID；新 handle 使用 `uuid5(document_id, f"workspace:{kind}:{handle}")`，驗證成功後寫回 registry。registry 是 identity metadata，不複製文件內容。

- [ ] **Step 5: 跑 GREEN、型別／格式檢查與北極星反查**

Run from `apps/api`:

```text
uv run pytest tests/test_consultant_workspace_resources.py tests/test_consultant_workspace_state.py tests/test_consultant_evidence_anchor.py -q
```

確認本 task 沒有新增 business-specific Tool、RAG、A／能力級別或第二份文件資料庫。

- [ ] **Step 6: Commit**

```text
git add apps/api/app/consultant/workspace_resources.py apps/api/app/consultant/workspace_state.py apps/api/tests/test_consultant_workspace_resources.py apps/api/tests/test_consultant_workspace_state.py
git commit -m "refactor: define the persistent JD workspace state"
```

---

### Task 2: 以 Deep Agents StoreBackend 持久化唯一 active workspace

**Files:**
- Modify: `apps/api/app/consultant/workspace_state.py`
- Modify: `apps/api/app/consultant/workspace_backend.py`
- Modify: `apps/api/app/consultant/workspace_tools.py`
- Modify: `apps/api/app/consultant/candidate_publication.py`
- Modify: `apps/api/app/consultant/run_service.py`
- Modify: `apps/api/app/adapters/langgraph/postgres.py`
- Modify: `apps/api/tests/test_consultant_workspace_backend.py`
- Modify: `apps/api/tests/test_consultant_workspace_tools.py`
- Modify: `apps/api/tests/test_consultant_run_service.py`
- Modify: `apps/api/tests/test_consultant_durable_authority_postgres.py`

**Interfaces:**
- `StoreBackedWorkspace(store, document_id)`：只組合官方 `StoreBackend` 與 lifecycle metadata，不重寫 CRUD。
- `PostgresConsultantRuntime.workspace_namespace(document_id)`
- `PostgresConsultantRuntime.workspace_metadata_namespace(document_id)`
- `PostgresConsultantRuntime.workspace_decision_namespace(document_id)`
- `WorkspacePolicyBackend(StoreBackend)`
- `ConsultantWorkspaceBackendBinding.workspace_backend`

- [ ] **Step 1: 寫 pinned framework characterization RED**

使用真正 `AsyncPostgresStore` 證明：

1. `StoreBackend(namespace=lambda _: fixed_namespace, store=runtime.store)` 可在 agent graph 外 `awrite／aread／aedit／adelete`；
2. 重建 backend instance 仍讀到同內容；
3. 另一 document namespace 完全隔離；
4. workspace files 不出現在 authority checkpoint `files` channel；
5. 同一文件刪除後 workspace、metadata、decision 三個 namespaces 均清空。

```python
async def test_deep_agents_store_backend_is_application_accessible_and_restart_safe(
    runtime,
) -> None:
    first = StoreBackend(
        namespace=lambda _runtime: runtime.workspace_namespace(document_id),
        store=runtime.store,
    )
    assert (await first.awrite("/workspace/header.json", "{}\n")).error is None
    reopened = StoreBackend(
        namespace=lambda _runtime: runtime.workspace_namespace(document_id),
        store=runtime.store,
    )
    assert (await reopened.aread("/workspace/header.json")).content == ["{}"]
```

- [ ] **Step 2: 跑 RED 並記錄 pinned API 行為**

Run from `apps/api`:

```text
uv run pytest tests/test_consultant_workspace_backend.py tests/test_consultant_durable_authority_postgres.py -k "store_backend or workspace_namespace" -q
```

Expected: production 尚未提供 namespace／Store-backed binding；若框架輸出形狀與假設不同，先修正 characterization，不以 private API 硬接。

- [ ] **Step 3: 實作薄 Store-backed lifecycle**

```python
class StoreBackedWorkspace:
    def __init__(self, *, store: BaseStore, document_id: UUID) -> None:
        self.backend = StoreBackend(
            namespace=lambda _runtime: workspace_namespace(document_id),
            store=store,
        )

    async def ensure_initialized(
        self,
        *,
        approved_document: ApprovedJobDocument,
        approved_revision: int,
    ) -> WorkspaceManifest: ...

    async def read_snapshot(self) -> WorkspaceSnapshot: ...
```

`ensure_initialized()` 只在 namespace 從未建立時 seed；只要 manifest 或任一 canonical file 存在，就不得因新 turn／run 覆蓋。file write／edit／delete 全部委派 `StoreBackend`；manifest 以同一 LangGraph Store 的 metadata namespace保存。

- [ ] **Step 4: 將 production binding 從 StateBackend 切到 StoreBackend**

- `CandidatePolicyBackend` 改名 `WorkspacePolicyBackend`，根固定 `/workspace/`，保留 create-only write、no `replace_all`、header不可刪與 canonical path policy；
- `ConsultantWorkspaceBackendBinding` 移除 `candidate_state_backend`、`run_id`、`initial_files`；
- `build_consultant_workspace_backend()` 接收已初始化 `StoreBackedWorkspace`；
- 目前仍存在的 check Tool 改成從 Store backend 讀真實 files，不再讀 LangGraph `state["files"]`；
- `run_service` 不再把 `files` 塞入 agent input；
- `delete_document()` 清除三個固定 namespaces。

- [ ] **Step 5: 寫跨回合／重啟／不重 seed GREEN**

至少覆蓋：第一輪新增未核准 Task、第二輪 source 進來後仍存在；provider exception後仍存在；重新建立 runtime connection後 byte-identical；另一文件看不到；approved 未被改動。

Run from `apps/api`:

```text
uv run pytest tests/test_consultant_workspace_backend.py tests/test_consultant_workspace_tools.py tests/test_consultant_run_service.py tests/test_consultant_durable_authority_postgres.py -q
```

- [ ] **Step 6: 北極星反查與 Commit**

確認目前只是換 persistence primitive：仍是一位顧問、一份 active workspace、員工 authority、no RAG；尚未把 Store 全文注入 context。

```text
git commit -m "refactor: persist the AI JD workspace with StoreBackend"
```

---

### Task 3: 每波 mutation 後自動驗證並保存短 diagnostics

**Files:**
- Create: `apps/api/app/consultant/workspace_validation.py`
- Modify: `apps/api/app/consultant/workspace_state.py`
- Modify: `apps/api/app/consultant/workspace_tools.py`
- Modify: `apps/api/app/consultant/agent.py`
- Modify: `apps/api/app/consultant/context.py`
- Modify: `apps/api/app/consultant/candidate_publication.py`
- Create: `apps/api/tests/test_consultant_workspace_validation.py`
- Modify: `apps/api/tests/test_consultant_agent_and_skills.py`
- Modify: `apps/api/tests/test_consultant_context.py`
- Modify: `apps/api/tests/test_consultant_candidate_loop.py`

**Interfaces:**
- `WorkspaceValidationService.validate_current(...) -> WorkspaceValidationResult`
- `WorkspaceValidationMiddleware(AgentMiddleware)`
- `WorkspaceValidationResult.document` 只在 valid 時存在；diagnostics永遠是短 code／path／message，不帶整份文件。

- [ ] **Step 1: 寫 verifier RED**

涵蓋：JSON syntax、Pydantic schema、stable identity、Duty／Task／OPKS linkage、JD invariant、Evidence source currentness、exact quote／occurrence、read-set／approved basis。另測：

- manifest digest與實際 files不符時不信 manifest並重驗；
- source correction改變 Evidence basis，即使 files未變也重驗；
- invalid files持久保留但 result沒有 reviewable document；
- 修復後 generation增加且狀態回到 valid。

```python
async def test_digest_mismatch_forces_validation_instead_of_trusting_manifest(
    workspace,
) -> None:
    await workspace.backend.aedit(task_path, old, invalid, replace_all=False)
    result = await validator.validate_current(...)
    assert result.manifest.validation_status is WorkspaceValidationStatus.INVALID
    assert result.document is None
```

- [ ] **Step 2: 從 candidate publication 抽出純 validation seam**

`candidate_publication.py` 暫時可呼叫新 service 以維持分支內現行功能，但 parsing、Evidence、JD invariant只能有一份實作。validation不得建立 review queue、receipt或改 approved。

- [ ] **Step 3: 寫 middleware RED**

Fake model／tool loop證明：

1. 無 mutation時同 digest不重驗；
2. 一個 model response 內不同 path 的平行 mutation完成後只驗一次完整 after-state；
3. invalid時下一個 model call收到 compact diagnostics；
4. 模型企圖直接 final時，middleware最多要求一次修復再受既有 model-call hard guard限制；
5. valid happy path不增加額外 model call。

- [ ] **Step 4: 實作 framework-native hook**

`WorkspaceToolWaveMiddleware` 仍在執行前拒絕重疊 mutation；`WorkspaceValidationMiddleware.abefore_model()` 在上一波 tools已完成後比對實際 digest並驗證。`ConsultantContextMiddleware` 每次 model call只加入：workspace generation／status、至多數條 diagnostics、`/workspace`與`/review`導覽 path；不得加入完整 files。

```python
class WorkspaceValidationMiddleware(AgentMiddleware):
    async def abefore_model(self, state, runtime):
        result = await self._validator.validate_current(
            loaded_skill_ids=self._skill_backend.loaded_skill_ids,
        )
        runtime.context.workspace_validation = result.summary
        return None
```

- [ ] **Step 5: 跑 focused GREEN**

Run from `apps/api`:

```text
uv run pytest tests/test_consultant_workspace_validation.py tests/test_consultant_agent_and_skills.py tests/test_consultant_context.py tests/test_consultant_candidate_loop.py -q
```

- [ ] **Step 6: 北極星反查與 Commit**

確認 validation是 deterministic application step，不是 critic Agent；正常回合不增加 model pass，invalid才讓同一顧問修復。

```text
git commit -m "feat: validate JD workspace mutations automatically"
```

---

### Task 4: 從 approved ↔ workspace 即時產生 semantic review

**Files:**
- Create: `apps/api/app/consultant/workspace_review.py`
- Modify: `apps/api/app/consultant/document_review.py`
- Modify: `apps/api/app/consultant/workspace_backend.py`
- Modify: `apps/api/app/consultant/workspace_resources.py`
- Create: `apps/api/tests/test_consultant_workspace_review.py`
- Modify: `apps/api/tests/test_consultant_document_review.py`
- Modify: `apps/api/tests/test_consultant_workspace_backend.py`

**Interfaces:**
- `derive_workspace_review(approved, valid_workspace, manifest, decisions) -> WorkspaceReviewProjection`
- `WorkspaceReviewProjectionBackend`：唯讀 `/review/**` projection。
- 現有 `DocumentChangeSet`／`DocumentPatchAction` 暫作 employee-facing semantic diff 型別；它們是 Caliburn domain責任，不是持久 proposal store。

- [ ] **Step 1: 寫語意差異與 stable identity RED**

測試：

- 相同 approved revision＋workspace digest產生相同 changeset／action IDs；任一相關內容改變後 ID改變；
- 低階 JSON 格式／key order變動不形成 semantic change；
- 新增、修改、刪除、重新歸類與調序正確投影 before／after；
- invalid／unvalidated workspace沒有可接受 bundle，只顯示 diagnostics；
- accept後 approved與workspace相同的內容自然從 projection消失。

- [ ] **Step 2: 寫 dependency grouping RED**

固定兩種代表情境：

1. 十個互不相依 Task與其 OPKS，可個別審；拒絕其中一個 O不影響另外九個完整 Task；
2. 一個 Task以兩個新 Task取代，相關 OPKS linkage也更新：兩個 create、一個 delete與必要 OPKS updates必須在同一 atomic subgroup。沒有專用 `split` Tool或model operation。

```python
def test_task_replacement_is_grouped_from_general_resource_changes() -> None:
    review = derive_workspace_review(approved, split_workspace, manifest, ())
    group = review.group_containing_path("/tasks/task-old")
    assert {change.operation for change in group.actions} == {
        DocumentPatchOperation.ADD,
        DocumentPatchOperation.WITHDRAW,
        DocumentPatchOperation.REVISE,
    }
    assert len({item.atomic_subgroup_id for item in group.actions}) == 1
```

- [ ] **Step 3: 將現有已驗證 differ搬到新 module，不複製演算法**

從 `candidate_publication.py` 移動 `_semantic_changes()`、read-set、Evidence basis與dependency grouping；輸入改為 valid workspace snapshot，輸出不寫 graph state。changeset ID以 document ID、approved revision、workspace generation／digest與group digest確定性產生。`/review` backend每次讀取都先確認 manifest digest仍匹配實際 files。

- [ ] **Step 4: 以 decision metadata投影 deferred／rejection memory**

`defer`只在 decision record的 workspace／group digest仍相同時顯示 deferred；workspace改動後自然回 pending。已拒絕且沒有新 Evidence／員工要求／相關工作邊界改變的相同 semantic fingerprint應成為validation diagnostic，不重新出現在可接受 review。

- [ ] **Step 5: 跑 GREEN、檢查 `/review` 唯讀**

Run from `apps/api`:

```text
uv run pytest tests/test_consultant_workspace_review.py tests/test_consultant_document_review.py tests/test_consultant_workspace_backend.py -q
```

- [ ] **Step 6: 北極星反查與 Commit**

確認 review是application從真實 after-state推導，不是模型填 proposal form，也不是第二份 JD；一般訪談仍可在有未決 review時繼續。

```text
git commit -m "feat: derive semantic review from the JD workspace"
```

---

### Task 5: 建立 employee authority command、partial decision 與可恢復 rebase

**Files:**
- Create: `apps/api/app/consultant/workspace_authority.py`
- Modify: `apps/api/app/consultant/document_authority.py`
- Modify: `apps/api/app/consultant/document_review.py`
- Modify: `apps/api/app/consultant/workspace_state.py`
- Modify: `apps/api/app/consultant/graph.py`
- Modify: `apps/api/app/adapters/langgraph/postgres.py`
- Create: `apps/api/tests/test_consultant_workspace_authority.py`
- Modify: `apps/api/tests/test_consultant_durable_authority_postgres.py`
- Modify: `apps/api/tests/test_consultant_document_review.py`

**Interfaces:**
- `WorkspaceReviewCommand`：exact command ID、approved revision、workspace generation／digest、changeset ID、selected action IDs、edited after values、reason。
- `WorkspaceDecisionRecord`：idempotency／rejection／defer metadata；存在 Store decision namespace，不複製 review payload。
- `WorkspaceRebasePlan`：authority commit前確定性計算，command receipt可在crash後完成同一 rebase。
- `WorkspaceAuthorityService.decide(...) -> ConsultantSnapshot`

- [ ] **Step 1: 寫 normal decision RED**

覆蓋：

- accept一個獨立 group只改 approved相應內容，其他 workspace差異仍在；
- edit-and-accept只為員工實際文字 delta建立 direct-edit source與 quote anchor，純結構修改不鑄造文字 Evidence；
- reject撤回該 group workspace差異、保存理由與 semantic fingerprint；
- defer不改 workspace／approved；
- atomic subgroup少選一項必須整組拒絕；
- exact replay回傳相同結果，same command ID＋不同 payload衝突。

- [ ] **Step 2: 寫 stale／non-overlap RED**

舊 changeset ID在以下情況 fail closed：approved revision變更、workspace digest變更、group digest變更、Evidence source被更正。另一個不重疊 group在重新投影後仍存在並可決策。

- [ ] **Step 3: 寫 approved-first crash-window RED**

在 runtime加入測試 hook，只供測試於兩個 seam注入 failure：

1. authority checkpoint完成、workspace baseline尚未更新；
2. reject decision record完成、workspace revert尚未完成。

reopen／exact replay必須由 command receipt、manifest baseline mismatch與實際 digest確定性完成；approved成功後不可回滾或被workspace覆蓋。

```python
async def test_accept_recovers_after_authority_checkpoint_before_workspace_rebase(
    runtime,
) -> None:
    runtime._after_workspace_authority_checkpoint = raise_once
    with pytest.raises(InjectedFailure):
        await runtime.decide_workspace_changes(command)
    reopened = await runtime.reopen_document(document_id)
    assert accepted_task in reopened.approved_document.tasks
    assert reopened.document_review.unresolved_action_count == 0
```

- [ ] **Step 4: 實作 command service與graph authority seam**

在 document lock內重新載入 approved、actual workspace、manifest與derived review；驗 exact identity後先計算結果。edit-accept若含員工文字delta，先依現有source-first seam把direct-edit source寫成pending，graph authority checkpoint成功後再標committed；失敗由既有reconciliation收斂。accept／edit-accept先提交graph authority與`CommandReceipt`，再更新workspace baseline／files；reject／defer以idempotent decision record保存。任何 application file write仍走StoreBackend；graph command只接收已驗證的新approved文件與receipt，不接收模型輸出。

- [ ] **Step 5: 實作 direct-edit three-way rebase**

authority commit前以 `old approved`、`current workspace`、`new approved`計算：

- workspace未改的path採員工新approved值；
- 只有workspace改的path保留AI差異；
- 雙方改成同值直接收斂；
- 雙方改成不同值保留AI working value但標 `conflicted` diagnostic，只阻擋 affected group。

不得用整份workspace重 seed，也不得讓AI值覆蓋員工direct edit。

- [ ] **Step 6: 跑 focused GREEN**

Run from `apps/api`:

```text
uv run pytest tests/test_consultant_workspace_authority.py tests/test_consultant_document_review.py tests/test_consultant_durable_authority_postgres.py -q
```

- [ ] **Step 7: 北極星反查與 Commit**

確認四種決策語意、員工原話與authority seam仍符合產品大方向；框架沒有取得accept權限。

```text
git commit -m "feat: apply employee decisions to the persistent JD workspace"
```

---

### Task 6: Production hard cut，移除 candidate handshake 與 durable review queue

**Files:**
- Modify: `apps/api/app/consultant/state.py`
- Modify: `apps/api/app/consultant/graph.py`
- Modify: `apps/api/app/consultant/agent.py`
- Modify: `apps/api/app/consultant/model_output.py`
- Modify: `apps/api/app/consultant/results.py`
- Modify: `apps/api/app/consultant/run_service.py`
- Modify: `apps/api/app/consultant/context.py`
- Modify: `apps/api/app/consultant/views.py`
- Modify: `apps/api/app/consultant/workspace_backend.py`
- Modify: `apps/api/app/consultant/workspace_tools.py`
- Modify: `apps/api/app/adapters/langgraph/postgres.py`
- Modify: `apps/api/app/api/consultant_mapper.py`
- Modify: `apps/api/app/api/routes/consultant.py`
- Delete: `apps/api/app/consultant/candidate_publication.py`
- Delete or replace: `apps/api/tests/test_consultant_candidate_publication.py`
- Delete or replace: `apps/api/tests/test_consultant_candidate_loop.py`
- Modify: `apps/api/tests/test_consultant_agent_and_skills.py`
- Modify: `apps/api/tests/test_consultant_model_output.py`
- Modify: `apps/api/tests/test_consultant_run_service.py`
- Modify: `apps/api/tests/test_consultant_api_mapper.py`
- Modify: `apps/api/tests/test_consultant_api.py`
- Modify: `apps/api/tests/test_consultant_hard_cut.py`
- Modify: `apps/api/tests/test_consultant_clarification.py`
- Modify: `apps/api/tests/test_consultant_interview_flow.py`
- Modify: `apps/api/tests/test_consultant_export_mapper.py`
- Modify: `apps/api/tests/test_consultant_understanding_and_sufficiency.py`

- [ ] **Step 1: 寫 hard-cut contract RED**

斷言：

- model Tool names恰為六個 filesystem verbs；
- `ConsultantModelOutput`／`ConsultantResult`沒有 `candidate_publication`；
- graph state沒有`checked_candidate`與durable `review_queue`；
- command context沒有`check_candidate_document`／`publish_checked_candidate`；
- model成功完成後，valid workspace review可由snapshot取得，不需final echo；
- model沒有編輯 workspace時正常回覆仍可成功且沒有空changeset。
- required clarification仍以LangGraph interrupt／resume保存，且只阻擋affected branch；一般gap與未決document review不會錯誤中止安全訪談。
- export在valid、invalid與未決workspace三種情況都只讀approved；semantic progress仍依職務內容覆蓋／Evidence／gap計算，不把workspace file數或review數假裝成完成度。

- [ ] **Step 2: 簡化 model final與system prompt**

final只保留顧問可見回答、可修訂理解／attention／gap effects、下一個問題或必要澄清與sufficiency；移除 revision、digest、action handles、publication與model回送Skill receipt。Skill使用證據由middleware／workspace validation receipt掌握。

system prompt改成：

```text
/skills、/sources、/approved、/review 唯讀；/workspace 是唯一可編輯且跨回合保存的工作草稿。
需要改文件時用六個 editor verbs；application會在mutation wave後自動驗證。
不要填offset、stable UUID、workspace revision、digest或action handle。
只有員工能把 /review 中的內容整合進 approved。
```

- [ ] **Step 3: 將 snapshot與route切到derived review／new authority service**

`snapshot_from_state()`只投影 checkpoint facts；`PostgresConsultantRuntime`在回傳前以actual workspace enrich `ConsultantSnapshot.document_review`。production state與view都不再使用`review_queue`名稱。`decide_document_changes()`改委派`WorkspaceAuthorityService`；現有HTTP route與idempotency header維持，避免不必要API churn。

- [ ] **Step 4: 刪除舊 lifecycle與轉接碼**

移除：

- `CheckedCandidateReceipt`、`CandidateCheckRequest/Result`、`CandidatePublication`；
- `check_candidate_document` Tool與graph action；
- `publish_checked_candidate` runtime／graph branch；
- `/candidate/<run-id>`、`/pending` projection與run seed；
- final publication echo與對應mapping；
- `DocumentChangeOperation.MERGE／SPLIT`、`DocumentPatchOperation.MERGE／SPLIT`與`target_ids`專用拓撲；複合變更只保留一般ADD／REVISE／WITHDRAW及dependency／atomic subgroup；
- production state、view與context中的`review_queue`名稱；
-舊candidate publication tests，不保留wrapper／alias／dual write。

`CompositeBackend` 最終只有五個routes，workspace Tool surface恰為六個。

- [ ] **Step 5: 跑 production slice GREEN**

Run from `apps/api`:

```text
uv run pytest tests/test_consultant_agent_and_skills.py tests/test_consultant_model_output.py tests/test_consultant_run_service.py tests/test_consultant_api.py tests/test_consultant_hard_cut.py tests/test_consultant_clarification.py tests/test_consultant_interview_flow.py tests/test_consultant_export_mapper.py tests/test_consultant_understanding_and_sufficiency.py tests/test_consultant_workspace_validation.py tests/test_consultant_workspace_review.py tests/test_consultant_workspace_authority.py -q
```

- [ ] **Step 6: 靜態 hard-cut guard**

```text
rg -n "check_candidate_document|publish_checked_candidate|CheckedCandidateReceipt|CandidatePublication|CandidatePolicyBackend|CandidateDocumentDraft|/candidate/|candidate_state_backend|review_queue|Document(Change|Patch)Operation\.(MERGE|SPLIT)" apps/api/app apps/api/tests
```

Expected: 零 production reference；研究／歷史文件不在此guard範圍。

- [ ] **Step 7: 北極星反查與 Commit**

以 Product acceptance contract九條逐項勾選。若任一項只能靠舊queue／handshake成立，不得commit。

```text
git commit -m "refactor: cut over to the persistent JD working draft"
```

---

### Task 7: 更新 contract、API projection 與員工 semantic review UI

**Files:**
- Modify: `packages/job-analysis-contract/src/job_analysis_contract/models.py`
- Modify: `packages/job-analysis-contract/src/job_analysis_contract/__init__.py`
- Modify: `packages/job-analysis-contract/tests/test_consultant_contract.py`
- Regenerate: `packages/job-analysis-contract/schema/job-analysis-workspace.schema.json`
- Regenerate: `packages/job-analysis-contract/types/job-analysis-workspace.ts`
- Modify: `apps/api/app/api/consultant_mapper.py`
- Modify: `apps/api/tests/test_consultant_api_mapper.py`
- Modify: `apps/api/tests/test_consultant_api.py`
- Modify: `apps/web/src/features/consultant/consultantWorkspaceModel.ts`
- Modify: `apps/web/src/features/consultant/DocumentReviewPanel.tsx`
- Modify: `apps/web/src/features/consultant/DocumentChangeEditor.tsx`
- Modify: `apps/web/src/features/consultant/ConsultantWorkspace.integration.test.tsx`
- Modify: `apps/web/src/features/consultant/consultantWorkspaceModel.test.ts`
- Modify: `apps/web/src/shared/api/consultantApi.test.ts`

**Contract additions:**

```python
class WorkspaceReviewStatus(StrEnum):
    CLEAN = "clean"
    PENDING = "pending"
    INVALID = "invalid"
    CONFLICTED = "conflicted"


class WorkspaceDiagnosticView(BaseModel):
    code: str
    path: str | None
    message: str


class DocumentReviewView(BaseModel):
    workspace_generation: int
    workspace_status: WorkspaceReviewStatus
    diagnostics: list[WorkspaceDiagnosticView]
    bundles: list[DocumentChangeSetView]
    unresolved_action_count: int
    blocked_branches: list[BlockedInterviewBranchView]
    safe_interview_work_available: bool
    decision_required_before_more_interview: bool
    explanation: str | None
```

不要把 virtual paths、tool calls、raw JSON diff、Store namespace或framework state暴露成員工必須理解的UI。

- [ ] **Step 1: 寫 contract／mapper RED**

測 clean、pending、invalid、conflicted四種snapshot；invalid沒有可按接受的bundle，pending保留既有 action／atomic subgroup資訊。review write仍只傳員工決策、selected action IDs、edited values與reason；exact workspace identity由changeset/action IDs與expected revision驗證，不要求UI重送file digest。

- [ ] **Step 2: 寫 Web RED**

Testing Library涵蓋：

- pending顯示「AI 建議的文件變更」與接受／修改後接受／拒絕／稍後；
- invalid只顯示「AI 正在修正工作草稿」與簡短問題，不提供接受按鈕；
- conflicted說明正式文件與工作草稿同處被改，請員工選擇，不用technical jargon；
- stale 409後自動refetch，不把舊選擇套到新內容；
- 十筆變更可選九筆接受、一個 O拒絕；atomic subgroup選取維持整組。

- [ ] **Step 3: 更新 contract並codegen**

Run from repo root:

```text
npm run codegen -w @caliburn/job-analysis-contract
npm run check-codegen -w @caliburn/job-analysis-contract
```

- [ ] **Step 4: 更新 UI 與 accessible names**

每個icon-only control與group checkbox必須有可辨識 accessible name；狀態訊息使用`role="status"`，blocking conflict使用`role="alert"`。保留現有typed field editor，不新增檔案編輯器、Git diff或branch UI。

- [ ] **Step 5: 跑 API／contract／Web GREEN**

Run from `apps/api`:

```text
uv run pytest tests/test_consultant_api_mapper.py tests/test_consultant_api.py -q
```

Run from repo root:

```text
npm run test -w @caliburn/web -- ConsultantWorkspace.integration.test.tsx consultantWorkspaceModel.test.ts consultantApi.test.ts
npx tsc --noEmit -p apps/web/tsconfig.json
npm run lint -w @caliburn/web
```

- [ ] **Step 6: 北極星反查與 Commit**

確認員工看到的是職務內容與決策，不是 framework／舊Proposal生命週期；未決內容可繼續訪談，必要澄清才阻擋相關分支。

```text
git commit -m "feat: review persistent AI document changes in the workspace"
```

---

### Task 8: 補齊 failure recovery、source correction 與同文件 admission guard

**Files:**
- Modify: `apps/api/app/adapters/langgraph/postgres.py`
- Modify: `apps/api/app/consultant/run_service.py`
- Modify: `apps/api/app/consultant/workspace_state.py`
- Modify: `apps/api/app/consultant/workspace_validation.py`
- Modify: `apps/api/app/consultant/workspace_authority.py`
- Modify: `apps/api/tests/test_consultant_durable_authority_postgres.py`
- Modify: `apps/api/tests/test_consultant_run_service.py`
- Create: `apps/api/tests/test_consultant_workspace_recovery_postgres.py`

- [ ] **Step 1: 寫 provider／process failure RED**

覆蓋：model已成功寫一個file後provider timeout、validation前process interruption、validation invalid後自然關閉、runtime重建。四者都不得改approved；reopen後actual workspace與diagnostics可續修。

- [ ] **Step 2: 寫 source correction RED**

更正被workspace Evidence引用的source後：舊quote basis失效、affected review不再可接受、其他不相關group仍可審；AI下一輪看到短diagnostic與最新source lineage，不把舊原話當current。

- [ ] **Step 3: 寫同document admission RED**

同一document模型正在mutation時，employee review／direct edit回明確409 busy而不是交錯寫入；不同document仍可平行。模型run結束／失敗後guard必定釋放。不得用database transaction包住provider call。

```python
@asynccontextmanager
async def active_consultant_run(self, document_id: UUID):
    async with self._lock_for(document_id):
        if document_id in self._active_model_runs:
            raise ConsultantRunAlreadyActive(document_id)
        self._active_model_runs.add(document_id)
    try:
        yield
    finally:
        async with self._lock_for(document_id):
            self._active_model_runs.discard(document_id)
```

employee command在取得document lock後檢查active set；第一版只宣稱單process／本機保護，不假裝成multi-process CAS。

- [ ] **Step 4: 量測 Store成長與checkpoint邊界**

測試建立50輪小幅workspace edit，只量測workspace／manifest／decision namespaces與checkpoint table成長；斷言authority state沒有files副本。記錄數據供completion report，不設定未研究的硬容量門檻。

- [ ] **Step 5: 跑 recovery GREEN**

Run from `apps/api` with the project test PostgreSQL:

```text
uv run pytest tests/test_consultant_workspace_recovery_postgres.py tests/test_consultant_durable_authority_postgres.py tests/test_consultant_run_service.py -q
```

- [ ] **Step 6: 北極星反查與 Commit**

確認failure recovery沒有導入第二份workspace、長transaction、multi-worker假設或額外模型call。

```text
git commit -m "test: harden persistent JD workspace recovery"
```

---

### Task 9: 設計文件、瀏覽器 smoke、窄 live model smoke 與 Final Gate

**Files:**
- Modify: `docs/design/consultant-runtime.md`
- Modify: `ARCHITECTURE.md`
- Create: `docs/specs/2026-08-22-persistent-store-backed-jd-working-draft-completion.md`
- Modify only if implementation contradicts a non-decision detail: `docs/specs/2026-08-22-persistent-ai-jd-working-draft-and-semantic-review-research.md`

- [ ] **Step 1: 更新現行設計文件**

文件必須畫清楚：

```text
employee source -> Store
                     |
                     v
LangChain/Deep Agents agent -> StoreBackend /workspace
                     |               |
                     |               v
                     |      automatic JD/Evidence validation
                     |               |
                     v               v
              concise reply    derived /review
                                      |
employee accept/edit/reject/defer ----+
                                      v
                         LangGraph authority checkpoint
                                      |
                                      v
                                approved JD -> export
```

明示Saver／Store分工、五個namespace、六個Tools、approved-first recovery、single-process admission與no-RAG界線。

- [ ] **Step 2: 跑完整 automated gates**

Run from `apps/api`:

```text
uv run pytest -q
```

Run from repo root:

```text
npx turbo test
npm run check-codegen -w @caliburn/job-analysis-contract
npx tsc --noEmit -p apps/web/tsconfig.json
npm run lint -w @caliburn/web
git diff --check
```

不得把既存PostgreSQL FK failure說成新功能通過；若仍存在，completion report要列出精確test、錯誤與與本branch無關的證據。

- [ ] **Step 3: 用真瀏覽器做員工情境 smoke**

啟動current產品後，使用in-app browser完成：

1. 新增文件並送第一段員工回答；
2. 看見AI建議的Task／Duty／OPKS語意變更；
3. 接受部分、拒絕一個O、延後另一項；
4. 關閉並重新進頁面；
5. 未決workspace仍存在，approved只含接受內容；
6. 再送一段回答，AI在同一workspace續編；
7. UI沒有raw JSON／path／Tool／digest，鍵盤與accessible name可操作。

保存browser步驟與結果到completion report；若UI行為失敗，先用`superpowers:systematic-debugging`定位，不以手改資料繞過。

- [ ] **Step 4: 做一個兩回合窄 live model smoke**

使用本專案 `apps/api` env已配置的provider，優先目前核准的GPT 5.6／Luna Max可用路由；不擴成eval。固定一個採購情境，驗證：

- 第一回合寫workspace並得到valid semantic review；
- 不接受，第二回合仍從同workspace續編；
- final不回送revision／digest／action handles；
- 正常路徑Tools只有六個；
- 記錄model calls、input/output/reasoning tokens、prompt cache hit、latency與估算cost；
- 與2026-08-21既有live smoke只比較mechanism failure與成本，不宣稱模型品質優勝。

- [ ] **Step 5: 最終 hard-cut與大方向審核**

Run:

```text
rg -n "check_candidate_document|publish_checked_candidate|CheckedCandidateReceipt|CandidatePublication|CandidatePolicyBackend|CandidateDocumentDraft|/candidate/|candidate_state_backend|review_queue|Document(Change|Patch)Operation\.(MERGE|SPLIT)" apps/api/app apps/web/src packages/job-analysis-contract/src
rg -n "app\.interview|app\.interview_vnext|app\.job_authoring" apps/api/app apps/web/src
git diff --check
git status --short
```

第一個搜尋必須零結果；第二個搜尋必須零production import。再逐條核對本計畫 Product acceptance contract與研究稿§1.2／§5／§8，completion report逐項列證據。

- [ ] **Step 6: Request review, fix findings, rerun Final Gate**

使用`superpowers:requesting-code-review`審查：產品方向、framework mapping、authority繞過、Store雙重truth、recovery、Evidence、成本與UI。所有屬實發現先補RED再修；最後使用`superpowers:verification-before-completion`重跑受影響focused gates與完整Final Gate。

- [ ] **Step 7: Commit documentation and create local tag**

```text
git commit -m "docs: complete the persistent JD workspace upgrade"
git tag persistent-store-backed-jd-working-draft-v1
```

保留branch／worktree；不push、不開PR、不merge，等待owner另行明確要求。

## Final traceability checklist

| Product／ADR requirement | Primary implementation task | Required evidence |
|---|---:|---|
| 一份JD一個跨回合active workspace | 1–2 | restart／cross-turn Postgres tests |
| StoreBackend而非StateBackend／自建表 | 2 | pinned characterization＋no files checkpoint assertion |
| 五個namespace、六個低階Tools | 2、6 | backend／agent hard-cut tests |
| 自動驗證、invalid可續修但不可審 | 3 | middleware wave／digest mismatch tests |
| semantic review非raw file diff | 4、7 | grouping unit tests＋Web integration |
| accept／edit／reject／defer | 5、7 | authority＋UI tests |
| exact stale、partial decision、atomic group | 4–5 | ten-items／Task replacement tests |
| approved-first與crash recovery | 5、8 | injected failure PostgreSQL tests |
| direct edit不被AI覆蓋 | 5 | three-way rebase tests |
| employee source／correction／Evidence | 3、5、8 | quote＋source correction tests |
| 按需context、無完整workspace dump | 3、6 | context receipt／token tests |
| no RAG／A／能力級別／auto／multi-agent | all | north-star checks＋hard-cut grep |
| 員工可關閉、回來繼續 | 2、8、9 | restart test＋browser smoke |
| 成本不因架構無限放大 | 3、9 | no-extra-call test＋narrow live metrics |
