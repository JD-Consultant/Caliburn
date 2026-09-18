# 顧問工作區、目前 JD 與明確審核語意實作計畫

> **狀態：owner 已於 2026-08-27 複核並授權執行。** 依本計畫在隔離 worktree 逐 Task 實作、驗證與複核；ADR 0070 仍須等完整 gate 通過後才升為 Accepted。

> **執行者必讀：** REQUIRED SUB-SKILL：以 `superpowers:executing-plans` 逐 task 執行；每個行為改動先依 `superpowers:test-driven-development` 寫紅燈測試；完成宣告前依 `superpowers:verification-before-completion` 重跑證據。

> **唯一執行計畫：** 本計畫取代 `docs/plans/2026-08-26-shared-current-jd-and-semantic-review-implementation.md`。不得執行舊計畫的 source-supersession Task 5，也不得從舊 code 反推產品需求。

**Goal：** 把 Current 產品收斂成一個以「目前 JD」為中央工作面的三欄 Web 顧問工作區。員工與 AI 持續編輯同一份 Store-backed working copy；AI 變更保持待審，員工可先修改再另行接受／拒絕；員工直接修改沒有 AI 差異的內容則立即成為核准文件。Duty／Task／工作細節／OPKS、未歸屬內容、K／S 多對多、生命週期與必要澄清均由後端權威規則投影，Web 不重算 domain invariant。員工補充或更正前文只是一般聊天；active analysis run 期間整個工作區只讀，完成、失敗或 timeout 後解鎖。

**Architecture：** 延續 ADR 0060 的 LangGraph Saver／Store durable authority 與 Deep Agents Store-backed workspace，不建立第二份文件、patch truth 或新資料表。`approved_document` 是只讀匯出基線，Store validation 的文件是 `current_document`，semantic review 永遠由兩者即時衍生。普通對話 context 由本輪訊息、token-bounded 近期雙向對話、可修訂理解與可讀目前 JD 組成，不新增 correction classifier。送出訊息前等待 autosave；durable `SOURCE_SAVED`／active run 與 process-local admission 共同阻擋同 document 所有員工寫入。通用互動交給 Base UI、TanStack Form／Query 與 react-resizable-panels；Caliburn 只保留框架不理解的職務分析結構、semantic diff、Evidence、dependency closure、employee authority transaction 與 crash recovery。

**Tech Stack：** Python 3.13、FastAPI、Pydantic v2、LangChain／LangGraph、Deep Agents StoreBackend、PostgreSQL；現行 Next.js 16.2.6／React 19.2.4／TypeScript／Tailwind 4／shadcn，並經 compatibility gate 採 Base UI 1.7.0、TanStack Query v5 最新相容 patch（查核時 5.102.2）、TanStack Form v1 最新相容 patch（查核時 1.33.5）、react-resizable-panels v4 最新相容 patch（查核時 4.12.3）、Vitest／Testing Library。實作日重查 stable tag；不得跳過 canary 只為追版本號。

**Spec：** [`docs/specs/2026-08-27-consultant-workspace-ui-and-pending-edit-semantics-design.md`](../../specs/2026-08-27-consultant-workspace-ui-and-pending-edit-semantics-design.md)；[`docs/adr/0070-consultant-workspace-ui-and-explicit-pending-edit-approval.md`](../../adr/0070-consultant-workspace-ui-and-explicit-pending-edit-approval.md)。

## Global Constraints

1. 先確認 `pwd` 與 `git branch --show-current`；只在隔離 worktree 的 `codex/consultant-workspace-ui` 分支寫入。
2. 不接 RAG／Reference；不新增 A 或能力級別的 AI 分析；不做 auto-accept、多 agent、正式 eval、來源歷史 UI、拖放或全域快捷鍵。
3. 不復活 `app.interview`、`app.interview_vnext`、`app.job_authoring`、`app.core` 等硬切舊系統，也不把舊名稱當新架構要求。
4. AI 沒有 approved write edge。員工編輯 AI pending after-state 不等於接受；接受／拒絕是獨立、明確、具 stale guard 的 employee command。
5. Web 不送「我碰了哪些 semantic path」作權威宣告；server 必須以最新 approved/current 狀態自行導出 delta、重疊 group、blast radius 與操作結果。
6. O／P 成為 JD item 時恰好屬於一個 Task；K／S 是 canonical 多對多，可暫時零連結但只顯示在「待重新連結 K／S」；A 是文件層，不掛 Task。
7. 每個 task 綠燈後做一次北極星檢查並獨立 commit。若檢查失敗，先停下與 owner 討論，不以舊 code 為保留理由。
8. 不碰主 worktree 既有 untracked 檔與 cache；不 push、不開 PR，除非 owner 另行明確要求。
9. 「我剛才說錯了」是一般 immutable chat turn。不得新增或保留 primary source-correction mode、舊訊息 target picker、LLM `superseded_source_handle`、`supersede／qualify／rebut` classifier，或把普通訊息轉成來源 lineage mutation。
10. 一個 document 同時只跑一輪分析。從送出至 run terminal，composer、JD 編輯、結構操作、Undo、Accept／Reject 都不可寫；閱讀、捲動、展開／收合、panel 調整與查看 diff／Evidence 仍可用。第一版不做 queue、steer、interrupt、rollback 或 parallel branch。
11. 送出訊息前先 flush 同 document autosave。autosave 失敗時保留聊天草稿、不建立員工 source、不啟動模型；UI disabled 不能取代 server-side durable run／stale guard。

## 權威資料與轉移界線（2026-08-27 複核）

| 官方資料 | 已驗證的成熟做法 | Caliburn 採用／不照抄 |
|---|---|---|
| [OpenAI apply patch](https://developers.openai.com/api/docs/guides/latest-model#the-apply-patch-tool)；[Codex IDE](https://openai.com/index/introducing-upgrades-to-codex/) | 模型提出受控操作，由 harness 實際套用、驗證、回報；人可預覽並編輯目前變更 | 採 working surface＋verifier＋derived diff；不採 Git／程式碼 patch UI |
| [Anthropic — How Claude Code works](https://code.claude.com/docs/en/how-claude-code-works) | 同一 session 保存歷史，使用者以普通 follow-up 修正方向 | 採一般對話修正＋持久歷史；官方資料不支持另造來源更正表單或 classifier |
| [VS Code — running request](https://code.visualstudio.com/docs/chat/chat-overview#_send-messages-while-a-request-is-running)；[LangGraph — double texting](https://docs.langchain.com/langsmith/double-texting) | queue／steer／stop／reject 都必須有明確 harness policy；LangGraph 的部署級 queue 不在 OSS runtime | 第一版明確採 reject；不為未核准需求引入 Agent Server 或 partial-run recovery |
| [TanStack Query mutation scopes](https://tanstack.com/query/latest/docs/framework/react/guides/mutations#mutation-scopes) | 同 scope mutation 序列執行 | 採同 document autosave scope，送出前等待清空 |
| [RFC 9110 `If-Match`](https://www.rfc-editor.org/rfc/rfc9110.html#name-if-match) | 條件式 request 防 lost update | 延續 revision／generation／digest；UI lock 不是 authority |
| [WHATWG `readonly`／`disabled`](https://html.spec.whatwg.org/multipage/input.html#the-readonly-attribute)；[WAI-ARIA `aria-busy`](https://www.w3.org/TR/wai-aria-1.2/#aria-busy) | 寫入控制與忙碌狀態有原生可及語意 | 只鎖 mutation controls，不用全頁 overlay，不鎖閱讀操作 |
| [Base UI releases](https://base-ui.com/react/overview/releases)；[TanStack Form docs](https://tanstack.com/form/latest/docs/framework/react/guides/arrays)／[npm stable](https://www.npmjs.com/package/@tanstack/react-form)；[TanStack Query npm stable](https://www.npmjs.com/package/@tanstack/react-query)；[`react-resizable-panels`](https://www.npmjs.com/package/react-resizable-panels) | 穩定 accessible primitives、nested form state、server state 與 resizable layout | compatibility gate 後使用；framework 不取得 JD authority |

轉移邊界：這些資料證明 agent loop、審核、併發策略與 Web primitives 是成熟機制；它們沒有驗證 Caliburn 的 Duty／Task／OPKS 分析品質。職務分析語意仍依本 repo 研究與員工 authority，不宣稱「大廠 UI」等於領域效果最佳。

## 完整檔案地圖

### 契約

- 修改 `packages/job-analysis-contract/schema/job-analysis-workspace.schema.json`
- 重新生成 `packages/job-analysis-contract/src/job_analysis_contract/models.py`
- 重新生成 `packages/job-analysis-contract/types/job-analysis-workspace.ts`
- 修改 `packages/job-analysis-contract/tests/test_consultant_contract.py`
- 修改 `packages/job-analysis-contract/tests/test_schema.py`

### API／顧問 runtime

- 修改 `apps/api/app/consultant/views.py`
- 修改 `apps/api/app/consultant/state.py`
- 修改 `apps/api/app/consultant/document_authority.py`
- 新增 `apps/api/app/consultant/current_document.py`
- 新增 `apps/api/app/consultant/document_commands.py`
- 修改 `apps/api/app/consultant/workspace_state.py`
- 修改 `apps/api/app/consultant/workspace_resources.py`
- 修改 `apps/api/app/consultant/workspace_review.py`
- 修改 `apps/api/app/consultant/workspace_authority.py`
- 修改 `apps/api/app/consultant/context.py`
- 修改 `apps/api/app/consultant/run_service.py`
- 修改 `apps/api/app/consultant/clarification.py`
- 修改 `apps/api/app/consultant/graph.py`
- 修改 `apps/api/app/adapters/langgraph/postgres.py`
- 修改 `apps/api/app/api/consultant_mapper.py`
- 修改 `apps/api/app/api/routes/consultant.py`
- 修改相關 API tests，並新增或擴充下列聚焦測試：
  - `apps/api/tests/test_consultant_current_document.py`
  - `apps/api/tests/test_consultant_document_commands.py`
  - `apps/api/tests/test_consultant_context.py`
  - `apps/api/tests/test_consultant_current_document_recovery_postgres.py`

### Web

- 修改 `apps/web/package.json` 與根 `package-lock.json`
- 新增 `apps/web/src/shared/ui/resizable.tsx`
- 新增 `apps/web/src/features/consultant/ConsultantWorkspaceShell.tsx`
- 新增 `apps/web/src/features/consultant/InterviewWorkMap.tsx`
- 新增 `apps/web/src/features/consultant/CurrentJobDocumentEditor.tsx`
- 新增 `apps/web/src/features/consultant/CurrentDocumentSection.tsx`
- 新增 `apps/web/src/features/consultant/SemanticReviewPopover.tsx`
- 新增 `apps/web/src/features/consultant/DocumentLifecycleMenu.tsx`
- 修改 `apps/web/src/features/consultant/ConsultantWorkspace.tsx`
- 修改 `apps/web/src/features/consultant/ConsultantConversation.tsx`
- 修改 `apps/web/src/features/consultant/ConsultantInsightPanel.tsx`，最後由 `InterviewWorkMap` 取代其工作地圖職責
- 修改 `apps/web/src/features/consultant/consultantWorkspaceModel.ts`
- 修改 `apps/web/src/features/consultant/consultantWorkspaceTestFixture.ts`
- 修改 `apps/web/src/shared/api/jobAnalysisApi.ts`
- 修改 `apps/web/src/shared/api/consultantApi.test.ts`
- 修改 `apps/web/src/shared/query/jobAnalysisQueries.ts`
- 修改 `apps/web/src/app/globals.css`
- 刪除被取代的 `ApprovedDocumentEditor.tsx`、`DocumentReviewPanel.tsx`、`DocumentChangeEditor.tsx`
- 重寫 `ConsultantWorkspace.integration.test.tsx` 與 `consultantWorkspaceModel.test.ts`

### 文件

- 修改 `docs/adr/0070-consultant-workspace-ui-and-explicit-pending-edit-approval.md` 為 `Accepted`
- 修改 `docs/adr/README.md`
- 修改 `docs/design/consultant-runtime.md`
- 修改 `AGENTS.md`
- 修改 `apps/api/README.md`
- 修改 `apps/web/README.md`
- 修改 `apps/web/docs/data-layer.md`
- 新增 `docs/specs/2026-08-27-consultant-workspace-live-verification.md`

---

## Task 1：Framework compatibility gate

**目的：** 先證明採用的成熟 Web primitives 可在現行 Next／React 上運作；本 task 不提早改跨層契約，確保 commit 本身維持全綠。

**Files：**

- Modify: `apps/web/package.json`
- Modify: `package-lock.json`
- Create: `apps/web/src/shared/ui/resizable.tsx`
- Modify: `apps/web/src/features/consultant/ConsultantWorkspace.integration.test.tsx`

### Step 1：先寫 framework canary 紅燈

在 Web integration test 加一個最小 harness，要求：

```tsx
render(<ResizablePanelGroup orientation="horizontal">...</ResizablePanelGroup>);
expect(screen.getByRole("separator")).toBeInTheDocument();
expect(screen.getByRole("button", { name: "收合訪談工作地圖" })).toBeEnabled();

const form = renderHook(() => useForm({ defaultValues: { duties: [] } }));
expect(form.result.current.state.values.duties).toEqual([]);
```

執行：

```powershell
npm run test -w @caliburn/web -- ConsultantWorkspace.integration.test.tsx
```

預期：缺少 resizable／TanStack Form 依賴，測試失敗。

### Step 2：重查 stable tag、安裝通過 canary 的版本並建立 shadcn-compatible wrapper

2026-08-27 查核基準如下；執行日先重查 official release／npm stable tag：

```json
"@base-ui/react": "^1.7.0",
"@tanstack/react-query": "^5.102.2",
"@tanstack/react-form": "^1.33.5",
"react-resizable-panels": "^4.12.3"
```

stable tag 不是跳過驗證的理由。以最小 canary 驗證 Next 16／React 19、SSR、focus、types 與既有測試後，才讓 lockfile 固定實際版本；若最新 patch 有已知 regression，可退回上一個通過版本，但必須記錄官方 issue／repro 與理由。不要順便升級本切片未使用的 Next、React 或 shadcn CLI。

`resizable.tsx` 只包裝 v4 `Group`／`Panel`／`Separator`，保留原生 ARIA 與 keyboard resize；不要自建拖曳邏輯。

```powershell
npm install
```

### Step 3：完整 compatibility gate 與 north-star checkpoint

```powershell
cd apps/web
npm run test
npx tsc --noEmit
npm run lint
```

檢查：只引入通用 UI／form mechanism；沒有第三份 document、沒有 RAG、沒有復活舊系統。

### Step 4：commit

```powershell
git add apps/web/package.json package-lock.json apps/web/src/shared/ui/resizable.tsx apps/web/src/features/consultant/ConsultantWorkspace.integration.test.tsx
git commit -m "build: add consultant workspace UI primitives"
```

---

## Task 2：由 Store 投影唯一目前 JD 與完整 stale guard

**目的：** Web 直接收到經後端驗證的 current working document，不再以 approved＋patch 自行拼裝。

**Files：**

- Modify: `apps/api/app/consultant/views.py`
- Modify: `apps/api/app/consultant/workspace_state.py`
- Modify: `apps/api/app/consultant/workspace_resources.py`
- Modify: `apps/api/app/api/consultant_mapper.py`
- Modify: `packages/job-analysis-contract/schema/job-analysis-workspace.schema.json`
- Modify: `packages/job-analysis-contract/tests/test_consultant_contract.py`
- Regenerate: `packages/job-analysis-contract/src/job_analysis_contract/models.py`
- Regenerate: `packages/job-analysis-contract/types/job-analysis-workspace.ts`
- Modify: `apps/web/src/features/consultant/consultantWorkspaceTestFixture.ts`
- Modify: `apps/api/tests/test_consultant_api_mapper.py`
- Modify: `apps/api/tests/test_consultant_workspace_state.py`
- Create: `apps/api/tests/test_consultant_current_document.py`

### Step 1：寫 projection 紅燈

建立三個案例：

1. approved 與 Store 相同時，`current_document == approved_document` 且 review clean。
2. AI 修改 Store 後，`current_document` 是 after-state、`approved_document` 仍是 baseline。
3. Store invalid／stale 時，API 不投影猜測的 current document，而回既有 typed authority conflict。

核心 assertion：

```python
snapshot = await runtime.reopen_document(document_id)
assert snapshot.current_document.tasks[0].statement == "AI 待審內容"
assert snapshot.approved_document.tasks[0].statement == "核准內容"
assert snapshot.document_review.workspace_digest == manifest.resource_digest
```

contract test 同時先要求：

```python
assert snapshot_view.current_document.document_id == DOCUMENT_ID
assert snapshot_view.document_review.workspace_digest
```

執行：

```powershell
cd apps/api
uv run pytest tests/test_consultant_current_document.py tests/test_consultant_api_mapper.py -q
```

預期：`ConsultantSnapshot` 尚無 current projection，失敗。

### Step 2：先改 schema、codegen 與 Web fixture

契約只先新增：

```text
ConsultantSnapshotView.current_document: ApprovedJobDocumentView
DocumentReviewView.workspace_digest: string
```

本 task 不提前移除 review／clarification 舊欄位；它們會在有對應 Web consumer 改動的 Task 5／6 同 commit 收斂。

```powershell
npm run codegen -w @caliburn/job-analysis-contract
npm run check-codegen -w @caliburn/job-analysis-contract
```

### Step 3：只從 fresh Store validation 建立 current document

把 `_snapshot()` 已取得的 `validation.document.approved_document` 傳入 projection：

```python
class ConsultantSnapshot(DurableModel):
    # checkpoint-only projection 尚未讀 Store 時必須是 None；public mapper 禁止 None。
    current_document: ApprovedJobDocument | None = None
    approved_document: ApprovedJobDocument

class DocumentReviewProjection(DurableModel):
    workspace_generation: int
    workspace_digest: str
    ...
```

`snapshot_from_state()` 仍只建立 checkpoint-owned 部分；只有 runtime 讀完 Store、驗完 revision／baseline／Evidence 後才用 `model_copy(update=...)` 加入 current document 與 review。不得把 current document 回寫 checkpoint 形成第二 authority。

### Step 4：處理 pending Task 的 employee-only L overlay

Store metadata namespace 只保存：

```python
class PendingTaskCompetencyLevels(DurableModel):
    by_task_handle: dict[str, int]
```

它不是另一份文件：

- AI workspace resource schema不新增 L／A writable 欄位；模型看不到也改不到。
- current projection 對 AI-new Task 套上員工設定的 L。
- Task 被 reject／delete 時 pruning；Task accept 時 materialize 到 approved Task 後刪 overlay。
- 文件層 A 與已核准 Task L 仍走普通 employee authority edit。

先在 `test_consultant_current_document.py` 加 overlay round-trip／prune 測試，再實作。

### Step 5：綠燈與 north-star checkpoint

```powershell
cd apps/api
uv run pytest tests/test_consultant_current_document.py tests/test_consultant_workspace_state.py tests/test_consultant_api_mapper.py -q
cd ..\..\packages\job-analysis-contract
uv run pytest tests/test_consultant_contract.py tests/test_schema.py -q
cd ..\..\apps\web
npm run test
npx tsc --noEmit
```

檢查：員工與 AI 看到同一 current document；approved 仍獨立只讀；Web 沒有 domain merge。

### Step 6：commit

```powershell
git add apps/api/app/consultant/views.py apps/api/app/consultant/workspace_state.py apps/api/app/consultant/workspace_resources.py apps/api/app/api/consultant_mapper.py apps/api/tests/test_consultant_api_mapper.py apps/api/tests/test_consultant_workspace_state.py apps/api/tests/test_consultant_current_document.py packages/job-analysis-contract apps/web/src/features/consultant/consultantWorkspaceTestFixture.ts
git commit -m "feat: project validated current job document"
```

---

## Task 3：目前 JD autosave 的 authority split 與 crash recovery

**目的：** 同一個 autosave endpoint 正確區分普通員工編輯與 AI pending after-state 編輯；client 不決定 authority。

**Files：**

- Create: `apps/api/app/consultant/current_document.py`
- Modify: `apps/api/app/consultant/document_authority.py`
- Modify: `apps/api/app/consultant/workspace_authority.py`
- Modify: `apps/api/app/consultant/graph.py`
- Modify: `apps/api/app/adapters/langgraph/postgres.py`
- Modify: `apps/api/app/api/routes/consultant.py`
- Modify: `packages/job-analysis-contract/schema/job-analysis-workspace.schema.json`
- Modify/generated: contract Python／TypeScript
- Create: `apps/api/tests/test_consultant_current_document_recovery_postgres.py`
- Modify: `apps/api/tests/test_consultant_workspace_authority.py`
- Modify: `apps/api/tests/test_consultant_api.py`

### Step 1：寫純 planner 紅燈

新增 `derive_current_document_edit()` 測試，輸入只有 server 讀到的 approved、current 與 employee submitted document：

```python
class CurrentDocumentEditPlan(DurableModel):
    approved_after: ApprovedJobDocument
    current_after: ApprovedJobDocument
    pending_paths: tuple[str, ...]
    approved_paths: tuple[str, ...]
    source_positions: tuple[SourcePositionAnchor, ...]
```

必測：

- ordinary approved scalar change → approved/current 都更新。
- pending AI scalar change → current 更新、approved 不變、group 仍 pending。
- 一次 request 同時碰 ordinary 與 pending → server 拆分，兩邊都不遺漏。
- stable ID 被全文件覆寫／偽造關係 → reject，不採信 client。
- AI-new Task L → metadata overlay，accept 前不進 approved。

執行：

```powershell
cd apps/api
uv run pytest tests/test_consultant_current_document.py -q
```

預期：planner 尚不存在，失敗。

### Step 2：實作 server-derived semantic overlap

重用現有 `derive_workspace_review()` 的 action path／group closure；不要讓 client 傳 touched path。演算法：

```text
latest approved/current → exact stable-ID diff(current, submitted)
每個 employee delta 與最新 pending semantic group 比對
overlap：只寫 current after-state
non-overlap：套用到 approved_after，並同步寫 current_after
最後以 ApprovedJobDocument 驗整份不變式
```

文字修改建立一個 `EmployeeSourceKind.DIRECT_EDIT`，用 Python 字串 index 產生 exact positions；受影響 O／P／K／S resource 的 Evidence 只附 employee 真正新增的文字，不偽造 AI quote。

### Step 3：新增 guarded current endpoint

契約：

```json
{
  "document": "ApprovedJobDocumentWrite",
  "workspace_generation": 12,
  "workspace_digest": "sha256..."
}
```

路由改為：

```text
PUT /consultant-documents/{document_id}/current-document
Headers: Idempotency-Key, X-Expected-Revision
```

移除 `/approved-document` 的 Web 使用；endpoint 可以在 Task 9 完成後刪除。mutation 仍走 `employee_mutation_admission(document_id)`。

### Step 4：以一份 persisted plan 跨 Saver／Store 提交

沿用現有 rebase recovery 模式，不新增 DB table：

1. Store metadata 寫 `current-edit:{command_id}` plan，含 expected/result workspace digest、approved before/after digest、完整 desired resource files、employee source id、L overlay。
2. graph `workspace_authority_commit` 原子提交 `approved_after`（可與 before 相同）與 source receipt。
3. `StoreBackedWorkspace.apply_rebase()` 以 exact digest 套用 current files、validation、manifest generation。
4. 完成後標記 source committed、刪 plan。
5. reopen recovery 只有在 graph 最新 document/source receipt 與 plan 完全吻合時補第二 seam；若第一 seam 未成功則刪 plan，不套到不相關文件。

### Step 5：寫 crash point 測試

Postgres 測試至少覆蓋：

- plan 後、graph 前 crash → reopen 不改 authority。
- graph 後、Store 前 crash → reopen exactly once 完成 Store。
- Store 已完成、回應前 crash → idempotent replay 相同結果。
- generation／digest／revision stale → 409，文件不變。

執行：

```powershell
cd apps/api
uv run pytest tests/test_consultant_current_document.py tests/test_consultant_workspace_authority.py tests/test_consultant_current_document_recovery_postgres.py tests/test_consultant_api.py -q
```

### Step 6：north-star checkpoint 與 commit

檢查：改綠色欄位後仍 pending；ordinary employee edit 立即核准；無第三份 truth、無 hidden merge。

```powershell
git add apps/api packages/job-analysis-contract
git commit -m "feat: autosave guarded current document edits"
```

---

## Task 4：Typed structural commands、ownership lifecycle、preview 與 bounded Undo

**目的：** 讓員工在目前 JD 新增／移動／解散／刪除／連結，而不是由 Web 手刻 relation pruning。

**Files：**

- Create: `apps/api/app/consultant/document_commands.py`
- Modify: `apps/api/app/consultant/current_document.py`
- Modify: `apps/api/app/consultant/workspace_authority.py`
- Modify: `apps/api/app/api/routes/consultant.py`
- Modify: contract schema/generated files
- Create: `apps/api/tests/test_consultant_document_commands.py`
- Modify: `apps/api/tests/test_consultant_api.py`

### Step 1：以行為矩陣寫紅燈

一個 public discriminated application command，不是 LLM Tool：

```python
type DocumentStructureCommand = (
    CreateDuty | CreateTask | CreateOpks | CreateAttitude |
    DissolveDuty | CascadeDeleteDuty | MoveTask | DeleteTask |
    ReorderEntity | LinkSharedOpks | UnlinkSharedOpks |
    DeleteOwnedOpks | DeleteSharedOpks | UndoDocumentCommand
)
```

具體 intent：

```text
create_duty(name)
create_task(duty_id|null, statement, competency_level|null)
create_opks(task_id, kind=output|performance_indicator|knowledge|skill, text)
create_attitude(text)
dissolve_duty(duty_id)
cascade_delete_duty(duty_id, preview_digest)
move_task(task_id, destination_duty_id|null)
reorder_entity(entity_kind, entity_id, parent_id|null, before_entity_id|null)
delete_task(task_id)
link_shared_opks(item_id, task_id)
unlink_shared_opks(item_id, task_id)
delete_owned_opks(item_id)
delete_shared_opks(item_id, preview_digest)
undo(undo_token)
```

測試矩陣：

| command | 必須結果 |
|---|---|
| dissolve Duty | Duty 刪除，Tasks 與其 details/O/P/K/S links 保留並未歸屬 |
| cascade Duty | Duty、owned Tasks、details、O/P 刪除；K/S 僅 unlink，最後 link 失去則保留 |
| move/unassign Task | 完整 subtree 保留 |
| reorder entity | 只正規化同一層 display_order；不改 stable ID 或 ownership |
| delete Task | Task、details、O/P 刪除；K/S 僅 unlink |
| unlink K/S | canonical item 保留；零 link 時進待重新連結 |
| delete owned O/P/A | 單一 item 刪除，可 Undo |
| delete shared K/S | canonical item 刪除並從所有 Task links 移除 |
| create O/P | 必須指定且只連一個 Task |
| create K/S | 第一筆至少指定一個 Task；日後可 unlink 至零 |
| create A | 文件層，沒有 Task link |

### Step 2：實作 pure command planner

`plan_document_structure_command(current, command)` 回傳完整 `current_after`、server-derived blast radius、inverse command 與 touched stable entities。所有 stable ID 由 application 產生；前端不生 UUID。

命令先改 current，再交 Task 3 同一 authority split：

- target／parent 是 AI pending → 保持 current pending。
- ordinary approved target → employee authority 立即更新 approved/current。
- 一個 command 不得把同一員工意圖拆成多個半完成 transaction。

### Step 3：高影響 preview 與短期 Undo

```text
POST /current-document/commands/preview
POST /current-document/commands
```

preview 回傳 server-derived `preview_digest`、counts/names 與 `confirmation_required`。刪除含多個 Task、會解除共享 K/S links 等高影響 cascade，以及永久刪除仍被 Task 使用的 canonical K/S 才要求確認；不得由 Web 自算數量或自行決定風險。普通單項刪除立即執行並提供 Undo。

每份 document 的 Store metadata 只保存最後一筆 bounded inverse：

```python
class DocumentUndoRecord(DurableModel):
    token: str
    resulting_revision: int
    resulting_workspace_digest: str
    inverse_command: dict[str, JsonValue]
```

新 authority mutation 使舊 token 失效；stale undo 明確回 409，不隱藏 merge。這不是版本歷史功能。

### Step 4：契約 codegen 與聚焦測試

```powershell
npm run codegen -w @caliburn/job-analysis-contract
npm run check-codegen -w @caliburn/job-analysis-contract
cd apps/api
uv run pytest tests/test_consultant_document_commands.py tests/test_consultant_current_document.py tests/test_consultant_api.py -q
```

### Step 5：north-star checkpoint 與 commit

檢查：分析順序仍可先有線索後成結構；未歸屬 Task 可帶 OPKS；K/S 多對多未被 UI 階層誤刪；A 未掛 Task。

```powershell
git add apps/api packages/job-analysis-contract
git commit -m "feat: add typed current document lifecycle commands"
```

---

## Task 5：把 review 收斂為 current diff 的 Accept／Reject

**目的：** 刪除舊 proposal form lifecycle；編輯由 current autosave 負責，review 只負責 promotion 或 revert。

**Files：**

- Modify: `apps/api/app/consultant/state.py`
- Modify: `apps/api/app/consultant/views.py`
- Modify: `apps/api/app/consultant/workspace_review.py`
- Modify: `apps/api/app/consultant/workspace_authority.py`
- Modify: `apps/api/app/api/routes/consultant.py`
- Modify: contract schema/generated files
- Modify: `apps/api/tests/test_consultant_workspace_review.py`
- Modify: `apps/api/tests/test_consultant_workspace_authority.py`
- Modify: `packages/job-analysis-contract/tests/test_consultant_contract.py`
- Modify: `apps/web/src/features/consultant/DocumentReviewPanel.tsx`
- Modify: `apps/web/src/features/consultant/consultantWorkspaceModel.ts`
- Modify: `apps/web/src/features/consultant/ConsultantWorkspace.integration.test.tsx`
- Modify: `apps/web/src/shared/api/jobAnalysisApi.ts`
- Modify: `apps/web/src/shared/api/consultantApi.test.ts`

### Step 1：寫 lifecycle 紅燈

必測：

- API／schema 只接受 `accept_changes`、`reject_changes`。
- `edit_and_accept_changes`、`defer_changes` 回 422。
- 員工先改兩個綠色欄位，兩次 autosave 後 group 仍 pending；最後 Accept 一次 promotion 整組。
- Reject 把選定 atomic group 的 current 值還原 approved baseline。
- untouched group 仍 pending；accepted／rejected group 不污染其他 group。
- move 在舊／新位置共用一個 group identity，不形成兩份 Task。

### Step 2：移除舊 decision state

刪除：

```text
WorkspaceDecisionKind.EDIT_ACCEPT
WorkspaceDecisionKind.DEFER
WorkspaceReviewDecisionKind.DEFER
edited_after_by_action_id
deferred 作為 reviewable status
```

保留 rejection decision memory，避免 AI 沒有新 Evidence 時立刻重提相同內容；接受後 workspace rebase／Evidence／dependency closure／stale guard 仍沿用現行成熟機制。

### Step 3：Accept materialize employee-only L overlay

若 group 接受 AI-new Task，將 Task handle 對應的 pending competency level 放入 `approved_after`；Reject／delete 則 prune。此規則只處理員工 L，不讓 AI 分析或寫 L。

### Step 4：同 commit 收斂過渡 Web consumer

在 inline semantic review 尚未於 Task 9 完成前，既有 `DocumentReviewPanel` 暫時只顯示 Accept／Reject；移除 edit-and-accept、defer 與 edited payload。這是維持每個 commit 可執行的過渡 consumer，不改變最終「中央 inline、無獨立 review panel」目標。

### Step 5：驗證

```powershell
npm run codegen -w @caliburn/job-analysis-contract
npm run check-codegen -w @caliburn/job-analysis-contract
cd apps/api
uv run pytest tests/test_consultant_workspace_review.py tests/test_consultant_workspace_authority.py tests/test_consultant_current_document.py tests/test_consultant_api.py -q
cd ..\..\packages\job-analysis-contract
uv run pytest tests/test_consultant_contract.py tests/test_schema.py -q
cd ..\..\apps\web
npm run test
npx tsc --noEmit
npm run lint
```

### Step 6：north-star checkpoint 與 commit

檢查：review 不是第三份文件；修改不等於接受；AI 仍無 approved write edge。

```powershell
git add apps/api packages/job-analysis-contract apps/web
git commit -m "refactor: separate current editing from review decisions"
```

---

## Task 6：一般對話延續、durable 單輪寫入鎖、失敗恢復與自由文字必要澄清

**目的：** 員工像正常訪談一樣補充或說「剛才說錯」，不進專用 correction protocol；同一 document 只跑一輪分析，失敗後可 retry 或直接送普通新訊息；必要澄清由同一聊天輸入回答。

**Files：**

- Modify: `apps/api/app/consultant/context.py`
- Modify: `apps/api/app/consultant/run_service.py`
- Modify: `apps/api/app/consultant/clarification.py`
- Modify: `apps/api/app/consultant/graph.py`
- Modify: `apps/api/app/adapters/langgraph/postgres.py`
- Modify: `apps/api/app/api/routes/consultant.py`
- Modify: contract schema/generated files
- Modify: `apps/api/tests/test_consultant_context.py`
- Modify: `apps/api/tests/test_consultant_run_service.py`
- Modify: `apps/api/tests/test_consultant_clarification.py`
- Modify: `apps/api/tests/test_consultant_api.py`
- Modify: `apps/api/tests/test_consultant_durable_authority_postgres.py`
- Modify: `apps/web/src/features/consultant/ConsultantConversation.tsx`
- Modify: `apps/web/src/features/consultant/ConsultantInsightPanel.tsx`
- Modify: `apps/web/src/shared/api/jobAnalysisApi.ts`
- Modify: `apps/web/src/shared/api/consultantApi.test.ts`
- Modify: `apps/web/src/features/consultant/ConsultantWorkspace.integration.test.tsx`

### Step 1：先以契約與 context 紅燈撤回專用來源更正

必測：

- 一般 answer request 只有普通 `text`，不含員工可填的 `supersedes_source_id`、source target 或 correction mode。
- provider output schema 不新增 `superseded_source_handle`，也沒有 `supersede／qualify／rebut` classifier。
- 對話依時間保存「每月整理」與後來的「我剛才說錯，是每週」兩則 immutable 訊息；第二則不改寫、retire 或標記第一則來源。
- model context 以時間順序包含本輪訊息、token-bounded 近期員工＋顧問對話、目前可修訂理解，以及目前 JD／workspace 的讀取入口；本輪 employee source 恰好一次。
- 長對話超過 budget 時先縮近期逐字對話，保留目前理解與按需 `/sources` lookup；不得每輪塞完整 transcript。

這些 deterministic tests 只驗證「模型看得到正確資料、沒有專用 correction protocol」，不假裝 unit test 能證明模型一定理解中文指涉。真正的「剛才說錯」效果留到 Task 10 Luna smoke。

### Step 2：移除 Current composition root 的 source-specific correction 流程

- 刪除主 answer API／Web 的 `supersedes_source_id`、逐則「更正這段原話」、`direct_correction` 表單與 retry-only 文案。
- 普通員工訊息不得呼叫 `apply_source_correction()` 或修改舊 source validity／lineage；顧問只透過既有 typed understanding／workspace operations 修訂目前理解與 JD。
- 先用 `rg` 盤點 source-lineage primitives。若只剩舊 Current correction flow 與其 tests，直接移除，不留 wrapper；若仍有 Evidence 完整性所需的內部讀取，保留最小資料型別但不得有 production writer 或 UI／provider consumer，並在 Task 10 文件說清楚。
- 語意真的不明確時，由顧問照一般對話輸出 required clarification；application 不先猜是哪個舊 source。

### Step 3：durable reject admission 與失敗後普通新訊息

`admit_employee_answer()` 與 `employee_mutation_admission()` 收斂成：

```text
SOURCE_SAVED／active → 第二個 answer 與所有 employee document mutation 回 typed 409
FAILED → 同 input 可 retry，也可建立全新普通訊息／run
COMPLETED／無 run → 正常下一輪
```

- guard 在 document lock 內同時檢查 process-local active set 與 durable `latest_run.status`；不能只靠單一 process set，避免背景 task 尚未取得 lock、頁面重整或另一分頁穿透。
- review、direct edit、pending edit、結構 command 與 Undo routes 全部走同一 admission；retry／run completion 使用既有專用 transition。
- 失敗 source 保留在歷史與 context；新訊息不必假裝取代失敗訊息。相同 idempotency key 仍 replay，不重複 source。
- 不引入 LangSmith Agent Server、queue、interrupt／steer、rollback 或 concurrent branching。

### Step 4：必要澄清改自由文字

`RequiredClarificationAnswerWrite` 只有 `text`。choices 可留在 projection 當可點選的填字建議，但 resolver 不要求答案恰好等於 choice。若 interrupt 存在，使用相同 LangGraph `thread_id` resume；保持官方規則：interrupt 前不放不可重入 side effect。

同一 commit 先讓 Web 移除 radio requirement：一般聊天 composer 在 clarification active 時改送 `{text}` 至 clarification endpoint。failed／timeout 顯示 retry 快捷鍵，但 textarea 可輸入任何新訊息。Task 7 再完成全工作區唯讀與三欄視覺。

### Step 5：驗證

```powershell
npm run codegen -w @caliburn/job-analysis-contract
npm run check-codegen -w @caliburn/job-analysis-contract
cd apps/api
uv run pytest tests/test_consultant_context.py tests/test_consultant_run_service.py tests/test_consultant_clarification.py tests/test_consultant_api.py tests/test_consultant_durable_authority_postgres.py -q
cd ..\web
npm run test
npx tsc --noEmit
npm run lint
```

另以 `rg` 證明 production contract／Web／composition root 沒有 source-specific correction consumer；若保留內部 lineage 型別，列出唯一必要 caller，不能用「以前就有」當理由。

### Step 6：north-star checkpoint 與 commit

檢查：一般更正仍是普通對話；沒有 app classifier；失敗不再 retry-only；durable active run 擋所有寫入；一般 gap 不阻塞，必要澄清才阻塞。

```powershell
git add apps/api packages/job-analysis-contract apps/web
git commit -m "refactor: simplify conversation and serialize consultant writes"
```

---

## Task 7：三欄 workspace shell、工作地圖與執行期全工作區唯讀

**目的：** 先完成穩定資訊架構，再接中央 editor；左右 panel 可收合／調寬／獨立滾動，composer 固定。active analysis run 只鎖所有 mutation，不鎖閱讀與導航。

**Files：**

- Create: `apps/web/src/features/consultant/ConsultantWorkspaceShell.tsx`
- Create: `apps/web/src/features/consultant/InterviewWorkMap.tsx`
- Modify: `apps/web/src/features/consultant/ConsultantWorkspace.tsx`
- Modify: `apps/web/src/features/consultant/ConsultantConversation.tsx`
- Modify: `apps/web/src/features/consultant/ConsultantInsightPanel.tsx`
- Modify: `apps/web/src/features/consultant/ApprovedDocumentEditor.tsx`（Task 9 前的過渡 consumer）
- Modify: `apps/web/src/features/consultant/DocumentReviewPanel.tsx`（Task 9 前的過渡 consumer）
- Modify: `apps/web/src/features/consultant/DocumentChangeEditor.tsx`（Task 9 前的過渡 consumer）
- Modify: `apps/web/src/features/consultant/consultantWorkspaceModel.ts`
- Modify: `apps/web/src/features/consultant/consultantWorkspaceTestFixture.ts`
- Modify: `apps/web/src/app/globals.css`
- Modify: `apps/web/src/shared/api/jobAnalysisApi.ts`
- Modify: `apps/web/src/features/consultant/ConsultantWorkspace.integration.test.tsx`

### Step 1：寫 layout／workspace admission 紅燈

Testing Library 驗證：

- 三個 landmarks 分別叫「訪談工作地圖」「目前 JD」「AI 職務分析顧問」。
- 左右 panel 可由明確按鈕收合／展開；中央一直存在。
- 每欄有自己的 scroll container；chat message list 滾動但 composer 固定存在。
- answer POST pending 或 snapshot `source_saved` 時，workspace region `aria-busy=true`，composer textarea／send disabled。
- 同一 busy 狀態也停用目前 editor 的文字寫入、新增／刪除／移動／重排、Undo 與 Accept／Reject；模擬 click／typing 不得呼叫 mutation API。
- busy 時 Duty／Task disclosure、左右 panel 收合／調寬、各欄捲動、開啟 diff／Evidence 仍可用；不得用攔住整頁的 overlay。
- completed、failed／timeout 後全部 mutation controls enabled；failed 畫面同時有「重試分析」與可送任何普通新訊息。
- pending review 單獨存在不會 disabled composer 或普通 JD 編輯。
- UI 完全找不到「更正這段原話」。
- required clarification 存在時，同一 composer 送到 clarification endpoint，不顯示 radio form。

### Step 2：實作 responsive shell 與單一 write-lock projection

寬螢幕用 `react-resizable-panels`；`useDefaultLayout` 保存 panel layout，只在使用者真的拖曳時寫 localStorage。中 viewport 一次顯示中央＋一側；窄 viewport 以 Base UI positioned Dialog／Drawer 顯示左右欄。不要建立 mobile app navigation。

`ConsultantWorkspace` 只導出一個 `workspaceMutationLocked`：送出 mutation 正在 admission，或 server snapshot run 為 `source_saved`／active。它是 UI projection，不是新 workflow state。文字欄位依 HTML 語意用 `readOnly`／`disabled`；會改 server state 的 buttons 明確 `disabled`；disclosure、popover、panel 與 scroll controls 不吃這個 prop。畫面顯示「AI 正在分析；完成後可繼續編輯」。

後端 Task 6 的既有 typed `409 …/consultant-run-active` 仍是 authority；若 UI 因 stale snapshot 誤送 mutation，統一 refetch 並顯示 busy status，不做 client merge。

視覺延續核准的乾淨模擬：中性背景、細分隔線、單一 blue accent；紅／綠只用於 semantic diff，不能把 O/P/K/S 各染一種高飽和色。

### Step 3：工作地圖只投影導航，不複製 JD

內容：

- 訪談概況：可見工作數、depth/coverage 文字摘要、待審數、未歸屬 Task 數、待重新連結 K/S 數。
- 白話 Focus：來源是 `current_interview`／interview work，不強迫綁 Task。
- 一般待釐清：顯示 gaps 與尚未定位線索，非 blocker。
- 必要澄清：醒目顯示並指示「請在右側聊天回答」。
- JD 大綱：Duty→Task 導覽，只定位中央內容，不在左欄編完整文件。

保留既有 understanding calibration 的產品語意，但放在合適的工作地圖區塊；不要把 calibration 的「之後再補」混回已移除的 review defer。

### Step 4：驗證與 north-star checkpoint

```powershell
cd apps/web
npm run test -- ConsultantWorkspace.integration.test.tsx consultantWorkspaceModel.test.ts
npx tsc --noEmit
npm run lint
```

檢查：Focus 不是 Task；工作地圖不是第二份 JD；一般待審不阻塞；active run 只鎖寫入且 terminal status 必解鎖。

### Step 5：commit

```powershell
git add apps/web
git commit -m "feat: build resizable consultant workspace shell"
```

---

## Task 8：TanStack Form 目前 JD、階層呈現與 autosave

**目的：** 中央以一份 nested form 呈現與編輯 current document，使用 server authority API，不再有手動 Save 或 client relation pruning。

**Files：**

- Create: `apps/web/src/features/consultant/CurrentJobDocumentEditor.tsx`
- Create: `apps/web/src/features/consultant/CurrentDocumentSection.tsx`
- Create: `apps/web/src/features/consultant/DocumentLifecycleMenu.tsx`
- Modify: `apps/web/src/features/consultant/ConsultantWorkspace.tsx`
- Modify: `apps/web/src/features/consultant/consultantWorkspaceModel.ts`
- Modify: `apps/web/src/shared/api/jobAnalysisApi.ts`
- Modify: `apps/web/src/shared/query/jobAnalysisQueries.ts`
- Modify: `apps/web/src/features/consultant/ConsultantWorkspace.integration.test.tsx`
- Modify: `apps/web/src/shared/api/consultantApi.test.ts`

### Step 1：寫 editor 紅燈

必測使用者情境：

- 表頭可編 title/category/occupation/code/industry/description/L/notes；A 是文件層獨立區。
- Duty→Task→工作細節＋O/P/K/S。
- 一個 Task 可各有多個 O/P/K/S；共享 K/S 在每個 Task 下投影，但 canonical item 只有一份。
- 未歸屬 Task 可有完整 details 與 OPKS。
- 零 link K/S 才顯示「待重新連結 K/S」。
- 顯示本地 ordinal（職責 1、任務 1…）與 type label，不暴露穩定 UUID 當員工編號。
- 編輯後沒有 Save 按鈕，狀態依序「儲存中」「已儲存」；失敗保留 field value 並顯示可重試。
- mutation payload 帶 latest revision/generation/digest。
- 同 document 快速連續 autosave 使用相同 Query mutation scope，序列化而非競速覆蓋。
- active run／answer admission 時所有 editor mutation controls 唯讀，但 disclosure、scroll 與文字選取仍可用。
- 使用者按送出聊天時，先等待該 document autosave scope 完成；保存失敗則不呼叫 answer API、保留聊天草稿與未保存欄位。

### Step 2：TanStack Form 管 local nested state

用 `useForm({ defaultValues: snapshot.current_document })` 與 field selectors。snapshot 更新時：

- 沒有 local dirty／pending request 的欄位同步 server。
- request in-flight 或失敗的欄位保留使用者值並顯示狀態。
- stale 409 先 refetch，再讓員工看到目前 server 值；不自動三方 merge。

autosave 使用一個局部 debounce（停止輸入或 blur）與：

```ts
scope: { id: `consultant-current-document:${documentId}` }
```

TanStack Query cache 只做 server-state cache，不持久化 document authority。

### Step 3：建立 autosave→answer admission barrier

在 workspace 層提供最小協調介面（例如 `flushCurrentDocument(): Promise<void>`），由 form controller 立即觸發尚未送出的 debounce，並 await 最新 `mutateAsync` Promise；TanStack Query 的同 `scope.id` queue 會先完成較早 autosave。`useIsMutating` 只顯示狀態，不用 polling 猜何時完成，也不另建 queue framework：

1. 員工按送出後立即避免重複操作，但先 flush dirty field 並等待同 document mutation scope 清空。
2. flush 成功才 POST employee answer；answer admission 開始後 `workspaceMutationLocked=true`。
3. flush 失敗就回到可編輯狀態，聊天草稿不清空、answer/source/run 都不得建立。
4. server 回 typed `…/consultant-run-active` 時 refetch snapshot 並顯示唯讀 busy state；其他 stale error 顯示目前 server 值，不自動三方 merge。

### Step 4：新增與 lifecycle 接 typed commands

- Duty header 的 `+` 新增 Duty。
- Duty 內 `+` 新增 Task；Task 內 `+` 選 O/P/K/S；A 區新增 A。
- 文件底部提供預設收合的「共用 K／S 管理」，顯示 canonical K／S、被哪些 Task 使用及永久刪除入口；Task 內只能解除連結。零 link 項目另在「待重新連結 K／S」醒目呈現，但仍是同一 canonical item。
- 文字選單清楚區分「解散職責（保留任務）」「刪除職責與內容」「移到未歸屬」「刪除任務」「解除 K/S 連結」「永久刪除 K/S」。
- 普通操作成功顯示 Undo toast；高影響先呼叫 preview，再用 Base UI Dialog 列 blast radius 確認。
- 不做 drag/drop；移動由 Menu／Combobox 選目的 Duty。重排 Duty／Task／同類 OPKS 用簡單上移／下移或位置 menu，呼叫 server `reorder_entity`。

所有 lifecycle controls 都接 `workspaceMutationLocked`；busy 時不可呼叫 preview 或 mutation，但仍可展開選單看目前結構，不顯示可執行的假動作。

### Step 5：刪除舊 client invariant

從 `consultantWorkspaceModel.ts` 刪除 client-side relation pruning、patch application 與 approved/localStorage merge。前端只做 view model：排序、label、展開狀態與 server-returned semantic metadata 對位。

### Step 6：驗證與 north-star checkpoint

```powershell
cd apps/web
npm run test -- ConsultantWorkspace.integration.test.tsx consultantWorkspaceModel.test.ts consultantApi.test.ts
npx tsc --noEmit
npm run lint
```

檢查：文件階層不規定分析先後；K/S canonical 多對多沒有被畫面複製成多份；A 未放 Task 下；無手動 Save；送出分析前一定取得最新已保存 JD；active run 無員工寫入縫隙。

### Step 7：commit

```powershell
git add apps/web
git commit -m "feat: edit current job document inline"
```

---

## Task 9：中央 inline semantic diff、Evidence 與獨立 Accept／Reject

**目的：** 讓員工在同一 JD 骨架直接看懂 AI 改了哪裡，修改綠色 after-state 後仍可整組審核。

**Files：**

- Create: `apps/web/src/features/consultant/SemanticReviewPopover.tsx`
- Modify: `apps/web/src/features/consultant/CurrentJobDocumentEditor.tsx`
- Modify: `apps/web/src/features/consultant/CurrentDocumentSection.tsx`
- Modify: `apps/web/src/features/consultant/ConsultantWorkspace.tsx`
- Modify: `apps/web/src/shared/api/jobAnalysisApi.ts`
- Rewrite: `apps/web/src/features/consultant/ConsultantWorkspace.integration.test.tsx`
- Delete: `apps/web/src/features/consultant/ApprovedDocumentEditor.tsx`
- Delete: `apps/web/src/features/consultant/DocumentReviewPanel.tsx`
- Delete: `apps/web/src/features/consultant/DocumentChangeEditor.tsx`

### Step 1：寫 semantic review 紅燈

測試：

- update：原值紅色刪除線唯讀；current 綠色可直接編輯。
- add：只有綠色 current entity。
- delete：只有紅色 baseline ghost。
- move：舊 Duty 下紅色 ghost、新 Duty 下綠色 current，共用同一 group label／popover。
- 點差異才開 contextual popover；點其他地方或 Escape 關閉。
- popover 顯示簡短變更原因、Evidence 摘要、`接受`／`拒絕`；沒有「稍後處理」「編輯後接受」。
- 修改綠色欄位只觸發 current autosave；pending count 不減。
- 接受 atomic group 才更新 approved；拒絕還原整組。
- group 有 dependencies 時，UI 顯示 server 回傳 closure，不自行判斷。
- active run 時仍可開啟與閱讀 semantic diff／Evidence，但綠色 after-state 唯讀，Accept／Reject disabled，且不呼叫 review mutation。

### Step 2：把 semantic metadata 對位到同一 document skeleton

`consultantWorkspaceModel.ts` 建立純 read-only index：

```ts
type ReviewDecoration = {
  groupId: string;
  groupDigest: string;
  operation: "add" | "update" | "withdraw" | "move";
  baseline: unknown;
  current: unknown;
  evidence: EvidenceSummary[];
  dependencyActionIds: string[];
};
```

這只是 server semantic review 的索引，不保存第三份文件、不套 patch、不決定 authority。

### Step 3：視覺與互動

- 紅色只呈現 baseline 被移除內容，唯讀。
- 綠色就是 current form field，可編輯。
- semantic label（新增／修改／移動／刪除）是提示，不取代底層 exact add/update/withdraw。
- popup 用 Base UI Popover 的 focus／dismiss primitives；Evidence 預設摘要，按需展開逐字 quote/source。
- 一個 atomic group 一組 Accept/Reject；即使跨多個 entity 也不拆成會產生中間態的局部核准。
- `workspaceMutationLocked` 只控制 after-state editor 與 review commands；Popover 的開關、內容閱讀、Evidence 展開與 dismiss 維持可用。

### Step 4：移除舊 UI

`ConsultantWorkspace` 不再 render separate review、approved editor 或「匯出版本」tab。approved baseline 第一版只供 inline 紅色 baseline、Accept／Reject 與 export 使用；員工主畫面永遠只有一份目前 JD。

### Step 5：驗證與 north-star checkpoint

```powershell
cd apps/web
npm run test
npx tsc --noEmit
npm run lint
rg -n "edit_and_accept|defer_changes|更正這段原話|ApprovedDocumentEditor|DocumentReviewPanel" src
```

預期：測試全綠；`rg` 除測試明確驗證不支援的字串外沒有 production consumer。

檢查：一個 current document；改綠色不接受；semantic diff 可看懂但不是第二 authority；active run 看得到差異但不能寫入或裁決。

### Step 6：commit

```powershell
git add apps/web
git commit -m "feat: review AI edits inline in current JD"
```

---

## Task 10：跨層整合、Accepted ADR、真瀏覽器／Luna Max smoke 與完整 gate

**目的：** 從員工視角驗證產品不是「元件各自綠」而是可完成多輪訪談、編輯、審核與匯出的完整流程。

**Files：**

- Modify: `AGENTS.md`
- Modify: `docs/adr/0070-consultant-workspace-ui-and-explicit-pending-edit-approval.md`
- Modify: `docs/adr/README.md`
- Modify: `docs/design/consultant-runtime.md`
- Modify: `apps/api/README.md`
- Modify: `apps/web/README.md`
- Modify: `apps/web/docs/data-layer.md`
- Create: `docs/specs/2026-08-27-consultant-workspace-live-verification.md`
- Modify: any tests needed to close defects found by real use; do not weaken assertions to obtain green.

### Step 1：先跑 contract／boundary／hard-cut gate

```powershell
npm run check-codegen -w @caliburn/job-analysis-contract
cd apps/api
uv run pytest tests/test_consultant_foundation_boundaries.py tests/test_consultant_hard_cut.py tests/test_consultant_task6_contract.py -q
```

預期：沒有舊 production import、Web 不成 authority、contract 生成乾淨。

### Step 2：啟動本機產品並做真瀏覽器驗收

依 runbook 啟動 PostgreSQL、migration、consultant Store tables、API/Web。用 in-app browser 實際驗證：

1. 寬／中／窄 viewport；左右收合、拖寬、各自滾動、composer 固定。
2. 長 JD 有多 Duty／Task／多個 O/P/K/S，階層仍可辨識。
3. ordinary edit autosave 後 export 更新。
4. AI pending 經 reload 仍存在；改綠色後仍 pending；Accept 才進 export；Reject 還原。
5. move 的舊／新位置 diff 正確且只是一個 Task。
6. dissolve/cascade/delete/unlink/last-link K/S/Undo 全符合 ownership。
7. 製造未完成 autosave 後按送出：先完成保存再啟動模型；保存失敗時 answer API 未被呼叫且聊天草稿仍在。
8. running 時 composer、目前 JD 編輯、add/delete/move/reorder、Undo、Accept／Reject 都不可用；scroll、disclosure、panel 與 diff／Evidence 可用。用第二分頁直接打 mutation API 仍得到 typed 409。
9. 刻意造成 provider failure／timeout 後所有 mutation controls 解鎖，可 retry 且可直接送任何普通新訊息。
10. required clarification 直接在聊天自由回答。
11. 不存在「更正這段原話」、舊訊息 target 或 correction mode。
12. 強制匯出維持既有政策，不在本次改 readiness 規則。

把 browser 步驟、預期、實際、截圖路徑或可重現缺陷記入 live verification 文件。

### Step 3：GPT-5.6 Luna Max 真模型 smoke

只從主 app `.env` 安全注入 key，不複製、不印出 secret。明確 override：

```text
CONSULTANT_MODEL=openai/gpt-5.6-luna
CONSULTANT_PROVIDER=OpenAI
CONSULTANT_REASONING_EFFORT=max
```

至少跑一段 5–8 輪的職務訪談：先發現工作、產生 Duty/Task/OPKS 待審、員工修改一個綠色欄位、拒絕一組，再以普通聊天說「我剛才說錯了，原本說每月，其實是每週」並繼續訪談。確認 context 沒有 source target／correction classifier，模型仍能用近期對話與目前理解修訂相關成果；若指涉故意寫得含糊，可正常追問，而不是 verifier 拒絕。以 durable attempt receipt 的 `actual_model`／`actual_provider` 證明實際路由，不只相信 env。

紀錄：

- 每輪 employee／consultant 可公開測試文字；
- model/tool step、token/cost metadata（不含 secret）；
- current/approved/pending 的關鍵狀態；
- verifier rejection 若有，保留錯誤與修正原因；
- 方向偏移檢查。

這是 smoke，不擴張成正式 eval harness。

### Step 4：完整 gate

```powershell
cd apps/api
uv run pytest -q
cd ..\web
npm run test
npx tsc --noEmit
npm run lint
cd ..\..
npx turbo test
npm run check-codegen -w @caliburn/job-analysis-contract
git diff --check
git status --short
```

預期：零 unexpected failure；若仍有既存 Postgres FK failure，必須以本次 fresh output 與歷史證據確認同一問題，不可口頭沿用。

### Step 5：最終北極星稽核

逐項在驗證報告回答並附證據：

1. 員工是不是只操作一份目前 JD？
2. AI 是否永遠只能造成待審 current diff？
3. 員工改 AI 內容是否仍需另按 Accept？
4. ordinary employee edit 是否立即成為核准 authority？
5. Focus／gap 是否允許尚未定位，而非硬綁 Task？
6. Duty/Task/O/P/K/S/A 與 ownership 是否符合研究結論？
7. 工作地圖是否只是導航、聊天是否能在失敗後恢復？
8. 是否只把通用機制交給成熟框架，保留必要產品語意？
9. 是否沒有 RAG、A AI 分析、auto-accept、多 agent 或其他未核准範圍？
10. 一般補充／更正是否只是普通對話，沒有 source-specific schema、classifier 或 UI？
11. active run 是否鎖住所有寫入但保留閱讀，且 success／failure／timeout 都能解鎖？
12. answer 是否一定在同 document autosave 成功後才 admission？

任一答案不是明確「是」，先修正或回 owner 討論，不接受「大致上」。

### Step 6：文件、ADR 與 commit/tag

驗證全綠後把 ADR 0070 `Proposed` 改為 `Accepted`，同步 ADR index、`AGENTS.md` 與設計／runbook 說明；`AGENTS.md` 不再把普通聊天更正描述成專用 correction-lineage product flow。

```powershell
git add AGENTS.md docs apps/api/README.md apps/web/README.md apps/web/docs/data-layer.md
git commit -m "docs: accept consultant workspace authority design"
git tag consultant-workspace-ui-v1
```

tag 只在本地；不要 push。

## 計畫完成定義

- 一個目前 JD 中央編輯面取代舊 approved editor＋review form。
- current/approved 雙 snapshot 與 derived semantic diff 經契約投影。
- pending autosave、ordinary direct edit、Accept／Reject、結構 command、Undo、durable run admission、失敗後普通新訊息與 context 組裝都有 deterministic＋Postgres recovery 測試；自然語句理解只以真模型 smoke 驗證，不造假 deterministic eval。
- Web 使用 compatibility gate 通過的 Base UI 1.7、TanStack Form v1、TanStack Query v5、react-resizable-panels v4 stable patch，而不是自行重寫通用互動。
- browser 與 Luna Max 真實 smoke 有可重現紀錄。
- 完整 API/Web/contract/monorepo gate 綠燈、工作樹只含本分支預期變更、本地 tag 建立、未 push。
