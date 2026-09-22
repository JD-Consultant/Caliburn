# 可修訂工作理解與共用 JD 工作區 Implementation Plan

> **施工仍暫停（2026-08-28）**：Owner 已確認每個工作回合都先更新／校正 Work Understanding，並暫定採「局部理解足夠即可產生局部待審 JD，不等待整體完成」；此裁決可由真實 transcript 的 churn／review fatigue／stale 證據推翻。Runtime 已裁決為「一個 product run 的有界 Tool-feedback consultant loop」：不建立 `should_edit_jd`，不固定單 call 或兩 stage；若 JD 依賴本輪新／修訂理解，必須先取得 application 驗證並提交後的 canonical Tool result。`validated` 只代表 schema／source／quote／reference／revision／domain invariant 合法，不代表員工已確認；deterministic error 由 system／同一顧問修復，只有真正 blocking 的工作語意才問員工。Owner 已核准 Work Understanding 採 source-linked、可修訂的 Case／Pattern／Unresolved typed collection，不建立獨立可寫 `WorkScope`；未定位線索不得強迫綁 Duty／Task／OPKS。最新機制稽核已把 owner 收斂為 LangGraph thread checkpoint，Store 只保存 immutable sources 與 current JD workspace；LangMem／Trustcall 不作預設 canary，只有真實 reconcile 失敗證據才可由 successor 重開。**JD 領域欄位與 provider schema preflight 尚未完成，以下舊 `kind + text + free-text scope` interface 已撤回，不得施工。**後續欄位稽核及本計畫全面重寫／複審完成前仍不得開始施工。

> **欄位契約覆寫（2026-08-28）**：Owner 已接受 [`LLM 應填欄位與 Tool Contract 審查`](../../specs/2026-08-28-llm-authored-field-contract-audit.md)。固定 `ConsultantModelOutput`、flat all-required wire、empty sentinel、model-authored occurrence／Skill receipt／application metadata 均已撤回。**本計畫 Task 2–7 仍含舊 code snippets，整份計畫目前只供追溯，不是可執行施工單。**必須先完成 JD 領域欄位稽核，再依新 atomic tagged Tool contract 全面重寫、複審；不得只局部改名後交給實作者。

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Before each behavior change use `superpowers:test-driven-development`; after each task use `superpowers:requesting-code-review`; before any completion claim use `superpowers:verification-before-completion`.

**Title：** 可修訂工作理解、同一份目前 JD 與最小審核語意 Big-bang 升級

**Goal：** 依 2026-08-28 owner 最新逐項確認，把 Caliburn 收斂成一位可跨輪記住員工實際工作的專業顧問：一般聊天先更新 source-linked 工作理解，再依該理解維護員工與 AI 共用的目前 JD；AI 變更留在同一工作面等待明確 Accept／Reject，員工可先編輯但不會因此偷渡接受；重大歧義才以 durable「需要你的確認」停在安全邊界。移除舊 Gap／calibration／source-correction／model-authored Skill evidence／`defer`／`edit-and-accept` 機制，不接 RAG、A／能力級別、auto-accept、多 Agent 或正式 eval。

**Architecture：** LangGraph Postgres Saver 是工作理解、Focus bookmark、required-input wait、run／command receipts 與 approved baseline 的唯一 durable semantic owner；LangGraph Store／Deep Agents `StoreBackend` 是 immutable employee turns 與唯一 current JD working copy 的 owner。一個員工訊息對應一個顧問 product run，不採多 Agent 與固定 Stage 1／Stage 2：同一顧問先吸收本輪訊息、必要近期對話、相關理解與員工 JD delta，按需呼叫 understanding Tool；application 解析 source／quote、指派 stable ID、deterministic 驗證並原子提交 current Work Understanding，無實質改變允許 no-op。任何依賴本輪新／修訂理解的 JD 操作，都必須等 canonical ID／revision 以 Tool result 回到同一 run 後，模型才可按需讀 JD／Skill 並呼叫 VFS edit Tool；只依賴既有 canonical understanding 的文件工作不強迫額外 round-trip。沒有 `should_edit_jd`：讀取／比較不是 authority action，實際 JD Tool call 才是操作決定。文件 Tool 成功並通過 understanding basis、blocking ambiguity、dependency closure、schema、read-set 與 document invariant 後，才原子發布待審 semantic group；失敗保留理解且 JD 不留半套變更。transient failure 由 LangGraph bounded retry；可修復的 schema／source／quote／reference／revision error 以最多五筆 typed diagnostic 回同一顧問，每個 authority stage 最多一次 validation-driven continuation；semantic ambiguity 才可能 interrupt，unexpected error rollback 並解鎖。Web 只呈現 server projection，不重算 authority。Claude／Codex 只作共同工作面、真實 diff、Tool feedback、Context 與 recovery 的產品方法參考；framework 必須另依官方 primitive 的適配性選擇，不從 coding agent 類比推導技術棧或 domain schema。

> **UI 範圍更正（2026-08-28）：** Work Understanding 首先是給 LLM 跨輪記憶、修訂理解並推導 JD 的內部狀態。第一版不以「AI 目前理解」UI 為交付 gate；核心完成後若能從同一 checkpoint 低成本產生，才加預設收合、唯讀的進階檢視，不得反過來塑造內部 schema。

**Tech Stack：** Python 3.13、FastAPI、Pydantic v2、LangChain 1.x、LangGraph 1.x＋PostgreSQL checkpointer／Store、Deep Agents `StoreBackend`、OpenRouter adapter；Next.js 16、React 19、TypeScript、Tailwind 4、Base UI、TanStack Query／Form、react-resizable-panels、Vitest／Testing Library。

**Spec：** [ADR 0071](../../adr/0071-revisable-work-understanding-context-and-review-provenance.md)、[ADR 0070](../../adr/0070-consultant-workspace-ui-and-explicit-pending-edit-approval.md)、[產品流程研究](../../specs/2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md)、[對話／工作理解研究](../../specs/2026-08-27-consultant-conversation-continuity-and-understanding-context-research.md)、[LLM 欄位契約稽核](../../specs/2026-08-28-llm-authored-field-contract-audit.md)、[UI 與 pending edit 設計](../../specs/2026-08-27-consultant-workspace-ui-and-pending-edit-semantics-design.md)。若舊研究、舊 plan 或現行 code 與上述最新裁決衝突，以 ADR 0071、欄位契約稽核與 owner 最新確認為準；不得從舊欄位反推需求。

## Global Constraints

1. 施工前依 `superpowers:using-git-worktrees` 從 `refactor/current-only-architecture` 建立隔離 worktree，分支預設 `codex/consultant-work-understanding-workspace`；每次寫入前確認 `pwd` 與 `git branch --show-current`。
2. 這是 fresh-root hard cut：不搬舊 checkpoint、Gap、calibration、source supersession 或 review lifecycle，不雙寫、不建立 compatibility wrapper。測試 DB 依 runbook 重建。
3. 不復活 `app.interview`、`app.interview_vnext`、`app.job_authoring`、`app.core`、`app.documents`、`app.task_analysis`、`app.opks`、`app.consultation` 或舊 `adapters.postgres`。
4. 不接 RAG／Reference；第一版核心 JD、Web 編輯與匯出均不包含 A／能力級別；不做 auto-accept、多 Agent、正式 eval、來源版本歷史 UI、拖放或完整鍵盤操作矩陣。
5. 一個 document 同時只允許一輪 AI run。active run 期間 composer、JD autosave、結構操作、Undo、Accept／Reject 均由 server admission 拒絕；閱讀、捲動、展開／收合與看 diff 不受影響。error／timeout 必須解鎖並恢復可輸入，不得只剩「重試」。
6. required input 等待期間只允許回答該 request；其他聊天、JD 編輯、Undo、Accept／Reject 回 typed 409。回答後立刻成為普通 employee turn，啟動下一輪分析；該輪 terminal 後解鎖。
7. 員工與 AI 編輯同一份 current JD。approved baseline 只是只讀 authority／export 基線，不是第二個主編輯器；AI 永遠沒有 approved write edge。
8. 員工直接編輯沒有 pending AI overlap 的內容時，同一 authority command 更新 current＋approved；若編輯 AI after-state，只更新 current 並維持 pending。client 不可自稱 touched paths，server 以 revision、workspace generation／digest 與前後內容自行導出 semantic delta。
9. Work Understanding 是唯一可寫語意 collection，以 stable、可修訂且不綁 JD 的工作範圍整理；未定位理解可暫無範圍。一般待釐清由其狀態投影，Focus 只是 LangGraph runtime bookmark，Progress 是 derived projection。精確 schema 定案前不得把舊 free-text `kind／scope` 實作成 production。禁止重建 `WorkModel`／`GapStore`／`Proposal`／`CurrentJd`／`Focus` writer。
9A. 原始 Work Understanding collection 是 LLM 內部狀態，第一版 Web contract／UI 不必完整暴露；可選「AI 目前理解」檢視不得成為新 writer、新 authority 或核心 acceptance gate。
10. 每個 task 先紅燈、再最小綠燈、再 north-star audit，完成後獨立 commit。任何會改變產品行為而未被 ADR 0071 明確裁決的問題都先停下問 owner；純框架接線依官方 contract 實作。
11. 不 push、不開 PR。全部 tasks、review fixes 與完整 gates 通過後建立本地 annotated tag `consultant-work-understanding-workspace-v1`，再由 owner 決定 merge／push。
12. deterministic validation 不宣告員工工作真相：technical／schema／source／quote／ID／revision 錯誤不得建立 required input；只有 employee-only 的 blocking semantic ambiguity 才能 interrupt。每個 authority stage 最多一次 validator-driven model repair，第二次失敗必須 terminal、rollback 當次 transaction 並解鎖。

## 成熟框架與不可轉移邊界

| 官方 primitive | 本計畫使用方式 | Caliburn 仍須自定義 |
|---|---|---|
| [LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | typed checkpoint、thread resume、fault recovery | 哪些內容是工作理解、Focus 與 approved authority |
| [LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) | safe-boundary `interrupt()`／`Command(resume=...)` | 何時真的需要員工確認、回答後如何修訂理解 |
| [LangGraph Memory](https://docs.langchain.com/oss/python/concepts/memory) | collection memory 與 hot-path update | 工作理解狀態與來源資格 |
| [LangMem](https://langchain-ai.github.io/langmem/reference/memory/)／[Trustcall](https://github.com/hinthornw/trustcall) | 本輪正式不採用；只有真實 transcript 暴露可重現 reconcile 缺口時，才由 successor 用該失敗案例重開比較 | 不為 framework 覆蓋率執行 canary；production 不加入 dependency、wrapper 或第二 memory owner |
| [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api#command) | Tool／`Command` 更新 state 後按最新 state 動態 route 或結束 | 哪些理解變更可成為 JD basis、文件 pass／repair 上限 |
| [LangGraph error handling](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph#handle-errors-appropriately) | transient 用 `RetryPolicy`、LLM-recoverable 回模型、user-fixable 才 interrupt、unexpected bubble | 哪些錯誤屬職務語意、每 stage 一次 repair 上限與 UI copy |
| [Deep Agents Backends](https://docs.langchain.com/oss/python/deepagents/backends) | current JD 的 VFS read／write／edit／delete、按需讀 understanding／sources／skills | Duty／Task／OPKS 結構、semantic diff、atomic group |
| [LangChain Structured Output](https://docs.langchain.com/oss/python/langchain/structured-output) | 顧問 effect／Tool arguments 的 strict schema | 內容真實性、source／quote、stable ref 與 domain verifier |
| [LangChain HITL](https://docs.langchain.com/oss/python/langchain/human-in-the-loop) | approve／reject 的人類決策原則；不直接套 middleware 的 tool-call queue | 可跨輪文件 semantic review、部分獨立 group 與拒絕 fingerprint |
| [Anthropic Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | 最小高訊號 context、structured notes、just-in-time retrieval | 哪些職務理解與 pending provenance 對本輪相關 |
| [OpenAI Function Calling](https://developers.openai.com/api/docs/guides/function-calling)、[Model guidance](https://developers.openai.com/api/docs/guides/latest-model) | 中間驗證會改變下一決定時，把 Tool result 回給模型；call 數不作產品 invariant | 工作理解／JD 的因果 gate、停止與核准政策 |
| [OpenAI Conversation State](https://developers.openai.com/api/docs/guides/conversation-state) | 對話 continuity 與 transport optimization | 不把 provider conversation 當產品記憶或 authority |
| [Codex Memories](https://learn.chatgpt.com/docs/customization/memories)、[Claude Code Memory](https://code.claude.com/docs/en/memory) | 參考「強制規則／模型記憶分層、精簡索引常駐、細節按需載入」 | coding memory 不是 Work Understanding framework；不照搬 markdown store／背景更新時機 |
| [Codex Code Review](https://learn.chatgpt.com/docs/code-review)、[Claude Checkpointing](https://code.claude.com/docs/en/checkpointing) | 參考同一工作區的真實 diff、可復原 edit receipt 與長期 authority 分離 | JD 不採 Git staged／commit 或只追蹤 AI file edits的限制 |
| [Anthropic Writing effective tools](https://www.anthropic.com/engineering/writing-tools-for-agents) | 精簡、可操作的 Tool result／error；嚴格模型與 poka-yoke | Caliburn error codes、source／quote 規則與 transaction boundary |
| [VS Code Review Edits](https://code.visualstudio.com/docs/agents/run/review-code-edits) | 同一工作面看 before／after、先修改 after 再明確決定 | JD 權威、職務語意與 atomic group；不照搬 Git UI |
| [RFC 9110 `If-Match`](https://www.rfc-editor.org/rfc/rfc9110.html#name-if-match) | revision／digest 條件式 mutation | 哪些 semantic group 可一起提交 |
| [Base UI](https://base-ui.com/react/overview/releases)、[TanStack Form](https://tanstack.com/form/latest/docs/framework/react/guides/arrays)、[TanStack Query](https://tanstack.com/query/latest/docs/framework/react/guides/mutations)、[react-resizable-panels](https://www.npmjs.com/package/react-resizable-panels) | accessible primitives、nested JD form、server state、autosave scope、可收合三欄 | Apple-like 視覺、JD hierarchy、review copy |

## Target Interfaces（最新邊界摘要；下方 Task code snippets 尚未重寫）

### 1. Work Understanding 與 Focus

Work Understanding 是 LangGraph checkpoint 內一份 source-linked、可修訂的 typed collection：application-owned envelope 保存 identity／revision／lifecycle；Case／Pattern／Unresolved variants 保存完整職務語意。沒有另一個可寫 `WorkScope`；Orientation、coverage、一般待釐清與 Progress 都由 current collection 投影。Focus 只是可恢復 runtime bookmark，可指 current understanding／unresolved／臨時查詢，不綁 Duty／Task／OPKS，也沒有 source。

模型只在確實有 semantic mutation 時呼叫 atomic tagged Tool。current employee source identity、stable IDs、revision、lifecycle、receipt 與 projection metadata 均由 application／framework 擁有。exact quote 由模型選取，application 做逐字唯一匹配；若不唯一就要求擴大 quote，不使用 model-authored occurrence 或 fuzzy match。

### 2. Model text、Tool calls 與同輪 canonical result

普通可見回覆是 assistant text，不存在每輪必填的 `ConsultantModelOutput`。模型可在同一 provider response 呼叫小型 Work Understanding、Focus、required-input 或 JD VFS Tools；只有 operation／role 合法的 variant 才出現在當輪 schema，沒有資料時就不呼叫，不填 dummy 空值。

Tool 成功後回 canonical IDs／revision／receipt；若同輪後續 JD edit 依賴新理解，模型才 continuation。沒有 downstream dependency 時可直接發布已緩衝的 assistant text，不固定多一次 model call。同輪暫時 local reference 是否仍需要，必須在新 Tool schema 與 LangGraph Tool-result flow 完成後再定，不能沿用舊 `u1／source_basis_ordinal` 設計。

### 2A. Understanding Tool result 與 error ownership

這是 agent-internal Tool contract，不進 public Web contract：

```python
class UnderstandingToolDiagnostic(BaseModel):
    code: NonEmptyText
    path: NonEmptyText
    message: NonEmptyText
    expected_rule: NonEmptyText

class UnderstandingToolResult(BaseModel):
    status: Literal["committed", "no_change", "repairable_error"]
    current_revision: int
    resolved_understanding_refs: dict[str, UUID]
    diagnostics: tuple[UnderstandingToolDiagnostic, ...]  # 0–5
```

- `committed`：整批 understanding effects 已在一個 transaction 通過並提交，回 canonical ref／revision；
- `no_change`：本輪已重新理解，但沒有 meaning／status／relations／source basis 的實質改變；
- `repairable_error`：當次 transaction 零寫入，回精簡 code／path／expected rule；同一 authority stage 在整個 product run 最多觸發一次 model continuation；
- 第二次仍失敗、provider terminal failure 或 unexpected exception 不偽裝成 Tool success，交 graph failure path，UI 解鎖；
- required input 不出現在本 result。它是顧問看到 canonical understanding／conversation 後提出的 semantic effect；deterministic error 永不轉成員工問題。

model-authored contract 不得包含 stable source UUID、understanding／version UUID、revision、digest、quote start／end、occurrence、Skill receipt 或 workspace identity。current source 由 runtime 注入；模型只選 exact quote、必要 semantic relations 與 semantic effects。application 指派／解析技術欄位。quote 不 trim、不 normalize、不 fuzzy match；重複時要求模型擴大 quote。

### 3. Required input

```python
class RequiredInputOption(DurableModel):
    label: NonEmptyText
    description: NonEmptyText

class RequiredInput(DurableModel):
    request_id: UUID
    question: NonEmptyText
    reason: NonEmptyText
    understanding_ids: tuple[UUID, ...] = Field(min_length=1)
    options: tuple[RequiredInputOption, ...] = ()  # 只允許 0 或 2–4

class RequiredInputAnswerWrite(BaseModel):
    text: NonEmptyText
```

選項點擊只把人類可讀答案填入 `text`；自由輸入也走同一欄。request 不帶 Task、Duty、branch、quote、Skill ID 或獨立 choice authority。

### 4. Current JD、review basis 與 decisions

- `ApprovedJobDocument`／public JD contract 移除 `evidence_source_ids`；來源只留在 Work Understanding。
- `ConsultantSnapshotView` 同時回 `current_document`（中央編輯面）與 `approved_document`（只讀基線／export authority）。
- `DocumentPatchAction` 只承載 semantic operation／path／before／after／read-set／dependency／status；不再承載 source、quote、Skill、employee-after 或 rejection reason。
- `DocumentChangeSet` 承載 `understanding_ids`（1～N）、一段短 `reason`、actions 與 stale metadata。
- public review command 只有：

```json
{ "command": "accept_changes", "action_ids": ["..."] }
{ "command": "reject_changes", "action_ids": ["..."] }
```

employee 修改綠色 after-state 走 current-document autosave，不是 review command。Accept 提升該 atomic group 的 current values；Reject 以 approved baseline 還原整組。兩者均不收理由。

### 5. 最小 receipts／delta

```python
class EmployeeDocumentDelta(DurableModel):
    command_id: UUID
    revision: int
    semantic_paths: tuple[str, ...]
    before_digest: Sha256Digest
    after_digest: Sha256Digest

class RejectedChangeFingerprint(DurableModel):
    semantic_digest: Sha256Digest
    understanding_version_digest: Sha256Digest
    boundary_digest: Sha256Digest

class ReviewDecisionReceipt(DurableModel):
    command_id: UUID
    group_digest: Sha256Digest
    decision: Literal["accepted", "rejected"]
    revision: int
    status: Literal["planned", "authority_committed", "completed"]
```

`EmployeeDocumentDelta` 只保存自上次成功顧問 run 後需要回饋模型的 compact semantic paths／digests，不是 employee source，也不是第二份 JD。Reject fingerprint 不推測理由；只有三個 digest 均未實質改變才抑制原樣重提。

三個拒絕指紋採固定 canonical JSON（UTF-8、object key 排序、array 依 stable semantic path／UUID 排序、無空白）後 SHA-256：

- `semantic_digest`：atomic group 內每個 action 的 canonical `operation／semantic_path／before／after`；
- `understanding_version_digest`：該 group 引用的 `(understanding_id, version_id)` 排序集合；
- `boundary_digest`：group target keys、dependency／read-set semantic paths 與 approved-baseline digest。

任何 digest input 變動都視為新分析邊界，可再次提出；三者完全相同才抑制原樣重提。指紋不保存拒絕理由、不做 embedding 相似判斷，也不永久禁止相似文字。

## Complete File Map

### Contract

- Modify: `packages/job-analysis-contract/schema/job-analysis-workspace.schema.json`
- Regenerate: `packages/job-analysis-contract/src/job_analysis_contract/models.py`
- Regenerate: `packages/job-analysis-contract/types/job-analysis-workspace.ts`
- Modify: `packages/job-analysis-contract/tests/test_consultant_contract.py`
- Modify: `packages/job-analysis-contract/tests/test_schema.py`

### API／runtime

- Modify: `apps/api/app/consultant/state.py`
- Modify: `apps/api/app/consultant/results.py`
- Modify: `apps/api/app/consultant/provider_wire.py`
- Modify: `apps/api/app/consultant/model_output.py`
- Modify: `apps/api/app/consultant/interview.py`
- Replace internals: `apps/api/app/consultant/understanding.py`
- Modify: `apps/api/app/consultant/context.py`
- Modify: `apps/api/app/consultant/agent.py`
- Modify: `apps/api/app/consultant/verification.py`
- Modify: `apps/api/app/consultant/run_service.py`
- Modify: `apps/api/app/consultant/graph.py`
- Replace semantics: `apps/api/app/consultant/clarification.py`
- Modify: `apps/api/app/consultant/views.py`
- Modify: `apps/api/app/consultant/workspace_resources.py`
- Modify: `apps/api/app/consultant/workspace_state.py`
- Modify: `apps/api/app/consultant/workspace_validation.py`
- Modify: `apps/api/app/consultant/workspace_backend.py`
- Modify: `apps/api/app/consultant/workspace_review.py`
- Modify: `apps/api/app/consultant/workspace_authority.py`
- Modify: `apps/api/app/consultant/workspace_tools.py`
- Modify: `apps/api/app/api/consultant_mapper.py`
- Modify: `apps/api/app/api/routes/consultant.py`
- Modify: `apps/api/app/adapters/langgraph/postgres.py`
- Modify: relevant `apps/api/tests/test_consultant_*.py`
- Add: `apps/api/tests/test_consultant_work_understanding.py`
- Add: `apps/api/tests/test_consultant_current_document.py`
- Add: `apps/api/tests/test_consultant_required_input.py`
- Add: `apps/api/tests/test_consultant_review_provenance.py`

### Web

- Modify: `apps/web/package.json`
- Modify: `package-lock.json`
- Add: `apps/web/src/shared/ui/resizable.tsx`
- Add: `apps/web/src/features/consultant/ConsultantWorkspaceShell.tsx`
- Add: `apps/web/src/features/consultant/InterviewWorkMap.tsx`
- Add: `apps/web/src/features/consultant/CurrentJobDocumentEditor.tsx`
- Add: `apps/web/src/features/consultant/CurrentDocumentSection.tsx`
- Add: `apps/web/src/features/consultant/SemanticReviewPopover.tsx`
- Add: `apps/web/src/features/consultant/RequiredInputCard.tsx`
- Modify: `apps/web/src/features/consultant/ConsultantWorkspace.tsx`
- Modify: `apps/web/src/features/consultant/ConsultantConversation.tsx`
- Replace responsibilities: `apps/web/src/features/consultant/ConsultantInsightPanel.tsx`
- Modify: `apps/web/src/features/consultant/consultantWorkspaceModel.ts`
- Modify: `apps/web/src/features/consultant/consultantWorkspaceTestFixture.ts`
- Rewrite: `apps/web/src/features/consultant/ConsultantWorkspace.integration.test.tsx`
- Rewrite: `apps/web/src/features/consultant/consultantWorkspaceModel.test.ts`
- Modify: `apps/web/src/shared/api/jobAnalysisApi.ts`
- Modify: `apps/web/src/shared/api/consultantApi.test.ts`
- Modify: `apps/web/src/shared/query/jobAnalysisQueries.ts`
- Modify: `apps/web/src/app/globals.css`
- Delete after replacement: `apps/web/src/features/consultant/ApprovedDocumentEditor.tsx`
- Delete after replacement: `apps/web/src/features/consultant/DocumentReviewPanel.tsx`
- Delete after replacement: `apps/web/src/features/consultant/DocumentChangeEditor.tsx`

### Documentation

- Accept after gates: `docs/adr/0071-revisable-work-understanding-context-and-review-provenance.md`
- Accept after gates: `docs/adr/0070-consultant-workspace-ui-and-explicit-pending-edit-approval.md`
- Modify: `docs/adr/README.md`
- Modify: `docs/design/consultant-runtime.md`
- Modify: `AGENTS.md`
- Modify: `apps/api/README.md`
- Modify: `apps/web/README.md`
- Modify: `apps/web/docs/data-layer.md`
- Add: `docs/specs/2026-08-28-consultant-work-understanding-live-verification.md`

---

## Task 1：Framework decision lock 與 Web compatibility gates

**Purpose：** 先把已核准的 framework 邊界鎖成可檢查依賴規則：本切片沿用 LangGraph checkpoint／Store、Deep Agents VFS 與 Pydantic typed effects，不加入 LangMem／Trustcall 或第二 owner；再升級／加入這個產品切片實際會用到的成熟 Web primitives。Web gate 不藉機升級 Next、React 或加入新的 state owner。

**Files：**

- Modify: `apps/web/package.json`
- Modify: `package-lock.json`
- Add: `apps/web/src/shared/ui/resizable.tsx`
- Modify: `apps/web/src/features/consultant/ConsultantWorkspace.integration.test.tsx`
- Modify: `apps/api/tests/test_consultant_foundation_boundaries.py`（或現有最接近的 dependency guard）

### Step 0：先寫 framework owner／dependency guard

加入最小靜態 guard，證明 production runtime 沒有 `langmem`／`trustcall` dependency 或 import，且 Work Understanding writer 只能經 LangGraph checkpoint transition。這不是宣稱套件永遠不可用，而是防止在沒有 successor ADR 與可重現產品缺口時偷接第二 owner。

```powershell
cd apps/api
uv run pytest tests/test_consultant_foundation_boundaries.py -q
```

Expected：guard 先因新規則尚未實作而紅燈；最小修正只補依賴／writer 邊界，不安裝或模擬 generic memory manager。若施工中的真實 transcript 暴露穩定失敗模式，停止本計畫並另寫 successor research／ADR；不得在 task 內臨時加套件。

### Step 1：寫 Web primitive compatibility 紅燈

先加最小測試，要求：

```tsx
render(
  <ResizablePanelGroup orientation="horizontal">
    <ResizablePanel defaultSize={25}>左</ResizablePanel>
    <ResizableHandle />
    <ResizablePanel defaultSize={75}>右</ResizablePanel>
  </ResizablePanelGroup>,
);
expect(screen.getByRole("separator")).toBeInTheDocument();

const form = renderHook(() =>
  useForm({ defaultValues: { duties: [] as Array<{ statement: string }> } }),
);
expect(form.result.current.state.values.duties).toEqual([]);
```

Run：

```powershell
npm run test -w @caliburn/web -- ConsultantWorkspace.integration.test.tsx
```

Expected：`@tanstack/react-form`、`react-resizable-panels` 或 wrapper 尚不存在，測試失敗。

### Step 2：安裝已查核 stable 版本並包最薄 wrapper

```powershell
npm install -w @caliburn/web @base-ui/react@1.7.0 @tanstack/react-query@5.102.2 @tanstack/react-form@1.33.5 react-resizable-panels@4.12.3
```

`resizable.tsx` 只重匯出／樣式化 library `Group／Panel／Separator`，保留 library 的 pointer 與 ARIA 行為；不自建 drag state。若執行日 stable tag 已更新，先在此 compatibility test 驗證再只升相容 patch，並把版本與官方 release link 記入 live-verification 文件。

### Step 3：綠燈與 north-star audit

```powershell
cd apps/web
npm run test
npx tsc --noEmit
npm run lint
```

North-star：只新增 layout／form mechanism；沒有文件 authority、RAG、第二套 workflow 或多 Agent。

### Step 4：commit

```powershell
git add apps/web/package.json package-lock.json apps/web/src/shared/ui/resizable.tsx apps/web/src/features/consultant/ConsultantWorkspace.integration.test.tsx
git commit -m "build: add consultant workspace UI primitives"
```

---

## Task 2：以單一 Work Understanding collection 取代 Gap／calibration／source correction（舊施工稿，必須重寫）

> **不得執行本 Task 現有 snippets。** 它們仍引用舊狀態 enum、`ConsultantModelOutput`、local ordinal、flat all-required wire 與 occurrence。重寫時以 ADR 0071、研究 §15.20 與欄位契約稽核為準；本段只保留預估檔案範圍與歷史測試意圖。

**Purpose：** 完成 source → revisable understanding 的垂直 hard cut與 understanding Tool-feedback gate；以已定稿的 stable WorkScope＋atomic collection 取代舊 free-text `kind／scope`、Gap／calibration／source correction。普通員工更正仍是一則新聊天，不再修改舊 source；未知、矛盾、已修訂與未定位線索只存在一個 collection。schema／source／quote／reference／revision error 由 system／同一顧問依 typed result 修復，絕不偽裝成員工問題。此 task 同步 contract／API／現有 Web projection，commit 結束時完整 compile 與測試維持綠燈。

> **Blocked：** 本 Task 後續 code snippets 仍有舊 `kind + text` 草稿引用。必須等下一輪精確 schema、scope relation／lineage 與 coverage 全部回填，再逐段重寫並由 owner 審核；不得把本 Task 當成目前可執行指令。

**Files：**

- Modify: `apps/api/app/consultant/state.py`
- Modify: `apps/api/app/consultant/results.py`
- Modify: `apps/api/app/consultant/provider_wire.py`
- Modify: `apps/api/app/consultant/model_output.py`
- Modify: `apps/api/app/consultant/agent.py`
- Modify: `apps/api/app/consultant/model_runtime.py`
- Modify: `apps/api/app/consultant/interview.py`
- Replace internals: `apps/api/app/consultant/understanding.py`
- Modify: `apps/api/app/consultant/verification.py`
- Modify: `apps/api/app/consultant/run_service.py`
- Modify: `apps/api/app/consultant/graph.py`
- Modify: `apps/api/app/consultant/views.py`
- Modify: `apps/api/app/api/consultant_mapper.py`
- Modify: `apps/api/app/api/routes/consultant.py`
- Modify: `packages/job-analysis-contract/schema/job-analysis-workspace.schema.json`
- Regenerate: generated Python／TypeScript contract files
- Modify: contract、runtime、mapper、route、Web model／fixture tests
- Add: `apps/api/tests/test_consultant_work_understanding.py`

### Step 1：寫 domain 與 contract 紅燈

加入以下案例：

```python
def test_current_understanding_requires_employee_source() -> None:
    with pytest.raises(ValidationError, match="current understanding requires"):
        WorkUnderstandingItem(
            understanding_id=uuid4(),
            version_id=uuid4(),
            kind="work_fact",
            text="每週彙整法規異動",
            status=WorkUnderstandingStatus.CURRENT,
            source_ids=(),
            created_revision=1,
        )

def test_pure_unresolved_understanding_may_have_no_source() -> None:
    item = WorkUnderstandingItem(
        understanding_id=uuid4(),
        version_id=uuid4(),
        kind="unknown",
        text="重大修法由誰核准仍不清楚",
        status=WorkUnderstandingStatus.UNRESOLVED,
        source_ids=(),
        created_revision=1,
    )
    assert item.source_ids == ()

def test_normal_employee_answer_has_no_source_supersession_field() -> None:
    schema = EmployeeAnswerWrite.model_json_schema()
    assert "supersedes_source_id" not in schema["properties"]

def test_quote_offsets_are_not_model_authored() -> None:
    serialized = json.dumps(ConsultantModelOutput.model_json_schema())
    assert "start_offset" not in serialized
    assert "end_offset" not in serialized

@pytest.mark.asyncio
async def test_deterministic_error_repairs_once_without_interrupt(runtime) -> None:
    result = await runtime.run_with_outputs(
        invalid_quote_output(),
        repaired_quote_output(),
    )
    assert result.model_repair_count == 1
    assert result.required_input is None
    assert result.work_understanding

@pytest.mark.asyncio
async def test_second_deterministic_failure_rolls_back_and_unlocks(runtime) -> None:
    before = await runtime.snapshot()
    result = await runtime.run_with_outputs(
        invalid_quote_output(),
        invalid_quote_output(),
    )
    after = await runtime.snapshot()
    assert result.status == "failed"
    assert after.work_understanding == before.work_understanding
    assert after.active_run is None
    assert after.required_input is None
```

Contract tests additionally assert these names are absent everywhere in generated public models:

```text
UnderstandingCalibration
VisibleGapView
UnderstandingCalibrationDecisionWrite
supersedes_source_id
superseded_by_source_id
employee_confirmed
challenged
```

Run：

```powershell
cd apps/api
uv run pytest tests/test_consultant_work_understanding.py tests/test_consultant_model_output.py tests/test_consultant_api_mapper.py -q
cd ../..
npm run test -w @caliburn/job-analysis-contract
```

Expected：新型別不存在、舊 contract 仍暴露上述欄位，測試失敗。

### Step 2：替換 durable state 與 transition

在 `state.py`：

- 以 Target Interfaces 的 `WorkUnderstandingItem／Status` 取代 `UnderstandingItem／Status`、`GapItem／GapStatus`、全部 calibration 型別；
- 以單一 `work_understanding: dict[str, dict]` 與 `focus: dict | None` 取代 `understanding／gaps／understanding_calibrations／latest_calibration_id／interview_work／current_work_id`；
- 移除 `source_supersessions` 與 direct source-correction action；employee source 僅 append；
- 保留 immutable source Store identity、messages、approved baseline、run／command receipts。

在 `interview.py／understanding.py`：

- ADD 由 `uuid5(document_id, f"consultant:{run_id}:understanding:{local_ref}")` 指派 stable `understanding_id／version_id`；
- REVISE 建新 `version_id`，舊版本標 `SUPERSEDED` 並互填 lineage；
- RETIRE 只改目前版本狀態；
- 同一 result 先解析 local refs，再解析 Focus、required input 與 document edit bases；未知 ref fail closed；
- 不以訊息時間自動覆蓋舊理解；互斥且無法判斷時必須形成 `CONTRADICTED`。

### Step 3：重建 model Tool contract（現有內容已撤回）

`provider_wire.py／model_output.py／results.py` 改成 Target Interfaces：

- `OutputSourceBasis` 不含 Skill；
- `source_basis_ordinal=0` 只允許純 `UNRESOLVED`；
- `ordinary_follow_up` 只包含顯示文字與相關 understanding refs，不保存自由文字 `answer_target` authority；
- `focus_change` 是一個 optional-by-neutral-shape object，不新增 Agenda／work-unit writer；
- 刪除 `OutputGap`、`SufficiencyRecommendation`、`AttentionChange` 與對應 reducer。

撤回「所有欄位 required、空陣列／空字串表示 none」。新版本必須使用小型 atomic tagged variants，讓非法 role／operation 組合不可表示；application 已知欄位由 ToolRuntime／server 注入，普通 assistant text 不進 structured root。若單一 union 在實際 endpoint preflight 不相容，改為當輪動態曝光 2～4 個 role-specific Tools，不得退回 dummy wire。

### Step 4：接上 framework-native failure routing 與一次 repair gate

- provider／strict wire failure 轉成 typed adapter failure，不把 raw traceback 或完整 schema 塞回 Context；
- LangGraph model／provider node 對 timeout、rate limit 與明確暫時錯誤使用小上限 `RetryPolicy`；transport retry 不重置 semantic repair budget；
- understanding Tool 原子驗證 runtime-injected source、exact quote 唯一匹配、semantic refs、revision、lineage、狀態轉換與 source eligibility；成功回 `committed／no_change`；quote 不唯一時回擴大引用的 typed diagnostic；
- 可修復錯誤回最多五筆 `UnderstandingToolDiagnostic`，由 graph 回同一 agent；每 stage 只允許一次 validation-driven continuation；
- 第二次 validation failure 或 unexpected error rollback 當次 Tool transaction、terminal run 並清除 active lock；不得建立 required input；
- semantic ambiguity 由模型輸出 `UNRESOLVED／CONTRADICTED`，只有符合 Task 6 blocking policy 才建立 required input。

追加 graph tests：transient error 走 policy 且不 interrupt；repairable error 只回模型一次；unexpected error 保留先前已提交 state、JD 不留下半套、composer 可再次送訊息。

### Step 5：contract、mapper 與暫時 UI projection 一次 hard cut

完整 `work_understanding.items` 不直接暴露給 Web；早先草稿中的專用 public shape 已撤回，不得照舊 schema 施工。

保留 `opening_navigation` 只作新文件開場說明，不把它當進度 authority。移除 `current_interview／visible_work／understanding／semantic_progress／sufficiency`、calibration buttons 與「稍後確認」。public contract 第一版只暴露員工有用的 server projection：目前訪談重點、可回答的待釐清／矛盾、訪談概況計數、待審數量與 required input；不為 UI 改變內部 Work Understanding schema。若核心完成後確認可低成本投影「AI 目前的理解」，再另以最小 read-only contract 加入；它不是 Task 2／Task 7 綠燈條件。

Generate and inspect：

```powershell
npm run codegen -w @caliburn/job-analysis-contract
npm run check-codegen -w @caliburn/job-analysis-contract
```

### Step 6：綠燈、舊名 hard-cut 與 north-star audit

```powershell
cd apps/api
uv run pytest -k "consultant and (understanding or output or mapper or route or graph)" -q
cd ../web
npm run test
npx tsc --noEmit
npm run lint
cd ../..
rg -n "UnderstandingCalibration|GapItem|GapStatus|decide_understanding_calibration|apply_source_correction|supersedes_source_id" apps/api/app/consultant apps/api/app/api apps/web/src/features/consultant packages/job-analysis-contract/schema
```

Expected：tests 全綠；最後 `rg` 零 production hit。另斷言 `repair_count <= 1`、deterministic failure 從不產生 required input、model wire 無 stable UUID／revision／digest／quote offset、terminal failure 後 active run lock 已清除。North-star：員工只能以一般聊天修正理解；沒有 Gap／calibration 第二 owner，Focus 不綁 JD entity；員工不替系統修技術錯誤。

### Step 7：commit

```powershell
git add apps/api/app/consultant apps/api/app/api packages/job-analysis-contract apps/web/src/features/consultant apps/web/src/shared/api
git commit -m "refactor: make work understanding the semantic memory owner"
```

---

## Task 3：以 Work Understanding provenance 與真實 Skill receipts 取代 JD Evidence

**Purpose：** 移除 JD／VFS 內嵌 source／quote／Skill 欄位；來源與 quote 只落在工作理解，AI 已實際編輯的 workspace path 由 final compact basis 綁 1～N 筆理解與短理由。framework receipts 而非模型自報證明 Skill 真的載入。

**Files：**

- Modify: `apps/api/app/consultant/workspace_resources.py`
- Modify: `apps/api/app/consultant/workspace_state.py`
- Modify: `apps/api/app/consultant/workspace_backend.py`
- Modify: `apps/api/app/consultant/workspace_tools.py`
- Modify: `apps/api/app/consultant/workspace_validation.py`
- Modify: `apps/api/app/consultant/workspace_review.py`
- Modify: `apps/api/app/consultant/document_authority.py`
- Modify: `apps/api/app/consultant/context.py`
- Modify: `apps/api/app/consultant/verification.py`
- Modify: `apps/api/app/consultant/run_service.py`
- Modify: `apps/api/app/consultant/agent.py`
- Modify: contract schema／generated files／tests
- Add: `apps/api/tests/test_consultant_review_provenance.py`

### Step 1：寫 provenance 與 Skill receipt 紅燈

核心 cases：

```python
def test_approved_opks_has_no_source_field() -> None:
    assert "evidence_source_ids" not in ApprovedOpksItem.model_fields

def test_changed_resource_requires_understanding_basis() -> None:
    result = validate_workspace(..., document_edit_bases=())
    assert [d.code for d in result.diagnostics] == ["review-basis-missing"]

def test_model_cannot_claim_skill_usage() -> None:
    schema = ConsultantModelOutput.model_json_schema()
    assert "skill_ids" not in json.dumps(schema)

def test_required_method_is_proved_by_loaded_skill_receipt() -> None:
    verify_document_edit_methods(
        edit_kinds={"knowledge"},
        loaded_skill_ids=("knowledge",),
    )
```

再加一個失敗 case：模型改 K item，但 execution receipt 未載入 `knowledge` Skill，deterministic verifier 回 `required_skill_not_loaded`。

Run：

```powershell
cd apps/api
uv run pytest tests/test_consultant_review_provenance.py tests/test_consultant_workspace_resources.py tests/test_consultant_workspace_validation.py tests/test_consultant_workspace_tools.py -q
```

Expected：JD 仍有 evidence 欄位、model schema 仍含 Skill，自然紅燈。

### Step 2：把 understanding 投影成 Deep Agents 唯讀資源

在既有 `CompositeBackend` 新增唯讀路由：

```text
/understanding/index.json
/understanding/u-<stable-short-handle>.json
```

內容只含 stable handle、status、kind、text、related handles 與 source availability；完整原話仍由既有 `/sources` 按需讀。`write_file／edit_file／delete_file` 對 `/understanding` 必須由 backend permission 拒絕。不要另建 memory table 或複製一份 Work Understanding 到 Store。

### Step 3：移除 workspace Evidence metadata

- `WorkspaceHeaderResource／Duty／Task／Opks` 刪除 `evidence`；
- `WorkspaceDocumentDraft` 刪除 `evidence_references／resource_evidence`；
- `WorkspaceManifest.evidence_basis_digest` 改為 `understanding_basis_digest`，只 digest 本輪 review basis 引用的 understanding version，不 digest 全部來源；
- `ApprovedOpksItem`、editable document、contract view／write 全數移除 `evidence_source_ids`；
- 刪除 `_attach_opks_evidence` 與 approved document evidence validator；
- 保留 `QuoteAnchor／resolve_evidence_reference`，但唯一 consumer 改為 Work Understanding source basis verifier。

### Step 4：驗證 final document-edit basis 與實際 VFS diff

`run_service.py` 在 agent 完成後：

1. 取得本輪開始與結束 workspace manifest；
2. 由 application 列出 changed canonical resource paths；
3. 將 `OutputDocumentEditBasis.resource_paths` normalize 成 canonical absolute workspace paths；
4. 要求每個 changed path 恰被一筆 basis 覆蓋，basis 不可指未改 path；
5. 解析 existing UUID／同輪 local understanding ref，要求至少一筆；
6. 建立 path → `ReviewBasis(understanding_ids, reason)` mapping；
7. 依操作種類對 `agent.skill_backend.loaded_skill_ids` 做 deterministic method prerequisite check；
8. 將 mapping 與 workspace generation 原子保存為 manifest review metadata，供 derived review 使用；不把它寫回 JD JSON。

如果 application dependency closure 把多個 basis 合併為一個 atomic group，`DocumentChangeSet.understanding_ids` 取 stable union；`reason` 以原順序把不同短理由組成同一個員工可讀條列字串。這只是呈現合併，不能拆開 application 判定必須原子的 actions。

### Step 5：Context hard cut

`ConsultantContextMiddleware` 每輪固定組成：

```text
versioned consultant policy + current objective
current employee turn
shortest required recent bidirectional dialogue
relevant current/unresolved/contradicted/unlocated understanding
Focus bookmark
current workspace orientation + validation status
compact pending review provenance + unchanged rejection fingerprints
unconsumed employee JD deltas
short Skill catalog
```

完整 source、Work Understanding、current JD resource、review detail、Skill 正文由 VFS 按需讀。新增 receipts 記錄每個 context item 的 authority label、ref、reason 與 token estimate；不得保存完整 prompt 或 chain-of-thought。

### Step 6：綠燈與 hard-cut scan

```powershell
cd apps/api
uv run pytest -k "consultant and (context or evidence or workspace or skill or output or run_service)" -q
cd ../..
npm run test -w @caliburn/job-analysis-contract
npm run check-codegen -w @caliburn/job-analysis-contract
rg -n "evidence_source_ids|WorkspaceEvidenceReference|skill_ids.*Output|model-authored.*skill" apps/api/app/consultant packages/job-analysis-contract/schema
```

Expected：tests 全綠；production schema／JD resources 零舊 evidence 欄位。`SkillId` 可繼續存在於 allowlist／receipt／Skill backend，不可存在 model-authored result。

### Step 7：commit

```powershell
git add apps/api/app/consultant packages/job-analysis-contract
git commit -m "refactor: ground JD review in work understanding"
```

---

## Task 4：投影唯一 current JD，並把員工編輯變成可消耗 delta

**Purpose：** Web 永遠編輯 Store 中唯一 current document；server 自行分辨 pending overlap 與普通員工編輯。普通編輯立即更新 approved，但不鑄 employee source；下一輪模型只看自上次成功分析後的 compact delta。

**Files：**

- Modify: `apps/api/app/consultant/views.py`
- Modify: `apps/api/app/consultant/state.py`
- Modify: `apps/api/app/consultant/workspace_resources.py`
- Modify: `apps/api/app/consultant/workspace_authority.py`
- Modify: `apps/api/app/consultant/workspace_backend.py`
- Modify: `apps/api/app/consultant/run_service.py`
- Modify: `apps/api/app/api/consultant_mapper.py`
- Modify: `apps/api/app/api/routes/consultant.py`
- Modify: contract schema／generated files／tests
- Modify: `apps/web/src/shared/api/jobAnalysisApi.ts`
- Modify: `apps/web/src/features/consultant/consultantWorkspaceModel.ts`
- Modify: fixtures／API tests
- Add: `apps/api/tests/test_consultant_current_document.py`

### Step 1：寫 current／approved projection 紅燈

```python
async def test_snapshot_projects_store_current_document() -> None:
    snapshot = await runtime.reopen_document(DOCUMENT_ID)
    assert snapshot.current_document.tasks[0].statement == "AI 待審內容"
    assert snapshot.approved_document.tasks[0].statement == "已核准內容"

async def test_employee_edit_of_clean_group_updates_both_without_source() -> None:
    before_sources = (await runtime.reopen_document(DOCUMENT_ID)).source_count
    result = await runtime.edit_current_document(...)
    assert result.current_document.job_title == "員工修訂"
    assert result.approved_document.job_title == "員工修訂"
    assert result.source_count == before_sources

async def test_employee_edit_of_pending_after_remains_pending() -> None:
    result = await runtime.edit_current_document(...)
    assert result.current_document.tasks[0].statement == "員工調整 AI 文字"
    assert result.approved_document.tasks[0].statement == "原核准文字"
    assert result.document_review.unresolved_action_count == 1
```

另測整份 client payload 同時含 clean 與 pending edits 時，server 按 semantic group 分流；client 偽造 path list 或舊 workspace digest 回 typed 409。

### Step 2：加入 server-owned `current_document` projection

`StoreBackedWorkspace.read_snapshot()` 通過 validation 後解析 `WorkspaceEditableDocument`；`ConsultantSnapshot`／contract 新增 required `current_document`。如果 workspace invalid／conflicted，不用 approved 猜 current，沿用 typed diagnostic 並把 document mutation disabled；snapshot 仍可回最後一個 validated current projection，且標示 `workspace_status`。

### Step 3：建立 current-document authority command

把現行 `PUT .../approved-document` 改成：

```text
PUT /api/v1/job-analysis/consultant-documents/{document_id}/current-document
Headers: Idempotency-Key, If-Match revision, X-Workspace-Generation, X-Workspace-Digest
Body: CurrentJobDocumentWrite
```

server 流程：

1. 讀最新 approved＋current＋derived review；
2. 比較 server 前一 current 與新 payload，導出 changed semantic groups；
3. closure 與 pending action overlap 的 group 只寫 current；
4. 無 pending overlap 的 group同時寫 current＋approved；
5. 以現有 workspace authority transaction／recovery seam 原子 commit；
6. 在 checkpoint 累積 `EmployeeDocumentDelta`，不建立 Store employee source；
7. run 成功後以 `consumed_through_revision` 標記已消耗 delta，失敗／retry 不提前清除。

### Step 4：移除 direct-edit source 路徑

刪除 `_approved_document_from_edit(... source_id=...)` 對 OPKS source 的附加、`direct-edit-source` command ID、`EmployeeSourceKind.DIRECT_EDIT` 與 `_require_known_evidence_sources`。保留 idempotent command receipt、revision／digest／recovery。

### Step 5：綠燈與 north-star audit

```powershell
cd apps/api
uv run pytest tests/test_consultant_current_document.py tests/test_consultant_workspace_authority.py tests/test_consultant_workspace_recovery_postgres.py tests/test_consultant_api_mapper.py -q
cd ../web
npm run test
npx tsc --noEmit
cd ../..
rg -n "approved-document|direct-edit-source|EmployeeSourceKind\.DIRECT_EDIT" apps/api/app apps/web/src packages/job-analysis-contract/schema
```

Expected：tests 全綠；舊 route／source kind 零 production hit。North-star：員工與 AI 是同一 working copy，只有 approved baseline 決定 export；JD 編輯不冒充訪談原話。

### Step 6：commit

```powershell
git add apps/api/app apps/api/tests packages/job-analysis-contract apps/web/src
git commit -m "feat: expose the shared current JD authority surface"
```

---

## Task 5：把 review lifecycle 收斂成 pending／Accept／Reject／stale

**Purpose：** 員工在 current JD 直接修改 AI after-state 後仍是 pending；Accept 才提升整個最小 atomic group，Reject 整組回退且不填理由。保留最小 receipts 與防原樣重提 fingerprint，移除 `defer／edit-and-accept／employee_after／rejection_reason`。

**Files：**

- Modify: `apps/api/app/consultant/state.py`
- Modify: `apps/api/app/consultant/workspace_review.py`
- Modify: `apps/api/app/consultant/workspace_authority.py`
- Modify: `apps/api/app/consultant/workspace_state.py`
- Modify: `apps/api/app/consultant/workspace_validation.py`
- Modify: `apps/api/app/consultant/context.py`
- Modify: `apps/api/app/api/routes/consultant.py`
- Modify: `apps/api/app/api/consultant_mapper.py`
- Modify: contract schema／generated files／tests
- Modify: `apps/web/src/shared/api/jobAnalysisApi.ts`
- Modify: `apps/web/src/features/consultant/consultantWorkspaceModel.ts`
- Modify: fixtures／tests
- Add: `apps/api/tests/test_consultant_review_provenance.py`

### Step 1：寫 review lifecycle 紅燈

```python
def test_review_command_has_only_accept_or_reject() -> None:
    assert set(WorkspaceDecisionKind) == {
        WorkspaceDecisionKind.ACCEPT,
        WorkspaceDecisionKind.REJECT,
    }

async def test_editing_pending_after_does_not_accept_group() -> None:
    edited = await edit_current_document(...)
    group = edited.document_review.groups[0]
    assert group.status == "pending"
    assert edited.approved_document != edited.current_document

async def test_reject_restores_whole_atomic_group_without_reason() -> None:
    result = await decide_review(command="reject_changes", action_ids=(ACTION_ID,))
    assert result.current_document == result.approved_document
    assert result.document_review.groups == ()

def test_same_rejected_change_is_suppressed_only_while_basis_is_unchanged() -> None:
    assert suppress(rejected, same_semantic, same_understanding, same_boundary)
    assert not suppress(rejected, same_semantic, changed_understanding, same_boundary)
```

Contract tests assert `DocumentReviewDecisionWrite` has only `command／action_ids`; generated schema contains none of `defer_changes、edit_and_accept_changes、edited_after_by_action_id、rejection_reason、deferred、edit_accepted`.

### Step 2：縮減 review domain

- `DocumentChangeStatus` 只保留 `PENDING／STALE` 作 active derived review；accepted／rejected 存於 `ReviewDecisionReceipt`，不留在目前差異清單；
- `DocumentPatchAction` 移除 `source_ids／quote_anchors／employee_after／rejection_reason`，保留 path read-set、dependency、atomic subgroup、before／after 與 stale reason；
- `DocumentChangeSet` 新增 `understanding_ids`（min 1）與短 `reason`，刪除 changeset source IDs；
- `WorkspaceReviewCommand` 只允許 accept／reject，payload 只有 command ID、changeset ID、action IDs、expected revision、workspace generation／digest；
- `select_workspace_actions()` 仍由 server 擴成最小 dependency／atomic closure，UI 不可拆散。

### Step 3：Accept／Reject authority

Accept：

1. 以最新 current values 重建 selected group；
2. 重驗 read-set、understanding version digest、workspace generation／digest；
3. 原子更新 approved baseline；
4. 清除已接受 paths 的 review-basis metadata；
5. 保留最小 `ReviewDecisionReceipt`，不保留 AI reason 於 JD。

Reject：

1. 計算 selected closure；
2. 用 approved baseline 還原 current 的整組 paths；
3. 清除該組 review-basis metadata；
4. 保存 `RejectedChangeFingerprint(semantic, understanding-version, boundary)`；
5. 不要求／推測 reason，不新增 Work Understanding。

`workspace_validation` 若看見與未失效 fingerprint 完全相同的模型變更，回可修復 diagnostic `unchanged-rejected-change`，讓 agent 回退該 VFS edit；相關 understanding version 或 boundary digest 改變後不阻擋。

### Step 4：綠燈與 hard-cut scan

```powershell
cd apps/api
uv run pytest tests/test_consultant_workspace_review.py tests/test_consultant_workspace_authority.py tests/test_consultant_review_provenance.py tests/test_consultant_workspace_recovery_postgres.py -q
cd ../web
npm run test
npx tsc --noEmit
cd ../..
npm run test -w @caliburn/job-analysis-contract
rg -n "defer_changes|edit_and_accept_changes|EDIT_ACCEPTED|DEFERRED|rejection_reason|employee_after" apps/api/app apps/web/src packages/job-analysis-contract/schema
```

Expected：全綠且最後 `rg` 零 production hit。North-star：不處理就是 pending；編輯不等於接受；Reject 不偽造員工理由。

### Step 5：commit

```powershell
git add apps/api/app apps/api/tests apps/web/src packages/job-analysis-contract
git commit -m "refactor: reduce JD review to explicit accept or reject"
```

---

## Task 6：以 safe-boundary LangGraph interrupt 實作「需要你的確認」

**Purpose：** 只有不回答就必須猜、且猜錯會實質改壞工作理解／JD 的歧義才阻塞。先 durable commit 同輪安全結果，再由無前置副作用 wait node interrupt；回答是普通 employee turn，resume 後必須跑下一次完整分析。

**Files：**

- Modify: `apps/api/app/consultant/state.py`
- Replace semantics: `apps/api/app/consultant/clarification.py`
- Modify: `apps/api/app/consultant/interview.py`
- Modify: `apps/api/app/consultant/graph.py`
- Modify: `apps/api/app/consultant/run_service.py`
- Modify: `apps/api/app/consultant/workspace_backend.py`
- Modify: `apps/api/app/adapters/langgraph/postgres.py`
- Modify: `apps/api/app/api/routes/consultant.py`
- Modify: `apps/api/app/api/consultant_mapper.py`
- Modify: contract schema／generated files／tests
- Modify: `apps/web/src/shared/api/jobAnalysisApi.ts`
- Minimal adapt: `apps/web/src/features/consultant/ConsultantConversation.tsx`
- Minimal adapt: `apps/web/src/features/consultant/ConsultantInsightPanel.tsx`
- Add: `apps/api/tests/test_consultant_required_input.py`

### Step 1：寫 required-input 與 lock 紅燈

```python
def test_required_input_references_understanding_not_work_or_source() -> None:
    fields = RequiredInput.model_fields
    assert "understanding_ids" in fields
    assert not {"affected_work_ids", "affected_branch", "source_ids"} & fields.keys()

@pytest.mark.asyncio
async def test_interrupt_survives_process_restart_and_resumes_once(postgres_runtime):
    waiting = await create_blocking_case(postgres_runtime)
    reopened = await reopen_runtime()
    assert reopened.snapshot.required_input.request_id == waiting.request_id
    answered = await reopened.answer_required_input(waiting.request_id, text="由我核准")
    assert answered.run.status == "source_saved"
    assert await count_employee_sources(answered.document_id, text="由我核准") == 1

@pytest.mark.asyncio
async def test_waiting_document_rejects_every_write_except_matching_answer():
    assert (await edit_current_document(...)).problem.status == 409
    assert (await accept_review(...)).problem.status == 409
    assert (await submit_normal_message(...)).problem.status == 409
    assert (await answer_matching_request(...)).status == 202
```

另測 options 數量只允許 0 或 2–4、一次只存在一題、wrong／stale request ID 回 typed 409、failure／timeout 後可送新訊息。

### Step 2：建立同輪 local-ref resolution

模型若在本輪首次發現衝突：

1. `understanding_changes` 建／修 `UNRESOLVED` 或 `CONTRADICTED` item，給 local ref；
2. `required_input.understanding_refs` 引用該 local ref；
3. application 在 `VerifiedConsultantCommit` 內先分配 stable IDs，再建立 `RequiredInput`；
4. 0 reference 永遠非法，不以 current turn 作例外。

### Step 3：重構 graph safe boundary

Graph 形狀固定為：

```text
apply_authority_command
  → if required_input is None: END
  → wait_for_required_input (interrupt only; no write before interrupt)
  → register_answer_source (idempotent)
  → END
```

顧問 run 的 semantic commit 已在進入 wait node 前完成；`wait_for_required_input` resume 時重跑也不重複任何 side effect。API answer route 以 `Command(resume={text, source_reference, command_receipt})` 恢復，完成 source registration 後由既有 run admission 啟動下一次 `_execute_admitted_consultant_turn()`；不能只清 request 就回 idle。

### Step 4：public contract 與最小既有 UI 適配

- `required_clarification` 改名 `required_input`；
- `RequiredInputView` 只含 request ID、question、reason、1～N understanding IDs、0 或 2–4 `{label, description}`；
- answer write 只含 `text`；
- 等待時舊 insight panel 暫時顯示一張「需要你的確認」卡並取代 composer，選項按下填入 text、自由輸入可覆寫；完整樣式在 Task 7。

### Step 5：綠燈與 restart gate

```powershell
cd apps/api
uv run pytest tests/test_consultant_required_input.py tests/test_consultant_durable_authority_postgres.py tests/test_consultant_workspace_recovery_postgres.py tests/test_consultant_run_service.py -q
cd ../web
npm run test
npx tsc --noEmit
cd ../..
rg -n "RequiredClarification|affected_branch|affected_work_ids.*clarification|current_understanding.*clarification" apps/api/app apps/web/src packages/job-analysis-contract/schema
```

Expected：全綠且舊 required-clarification production shape 清除。North-star：一般未知不 interrupt；只有 blocking ambiguity 使用 durable pause；回答後必定回到工作理解分析。

### Step 6：commit

```powershell
git add apps/api/app apps/api/tests apps/web/src packages/job-analysis-contract
git commit -m "feat: add durable required-input boundary"
```

---

## Task 7：建立可收合三欄工作區與正確執行期互動

**Purpose：** 套用已確認的 Apple-like 乾淨 UI 骨架：左工作地圖、中央目前 JD、右對話；三區獨立捲動，左右可收合，中央自動擴張。Focus／待釐清／訪談概況／required input 只作新語意投影，不復活舊 agenda；完整工作理解 UI 不在本 Task 的必做範圍。

**Files：**

- Add: `apps/web/src/features/consultant/ConsultantWorkspaceShell.tsx`
- Add: `apps/web/src/features/consultant/InterviewWorkMap.tsx`
- Add: `apps/web/src/features/consultant/RequiredInputCard.tsx`
- Modify: `apps/web/src/features/consultant/ConsultantWorkspace.tsx`
- Modify: `apps/web/src/features/consultant/ConsultantConversation.tsx`
- Replace responsibilities: `apps/web/src/features/consultant/ConsultantInsightPanel.tsx`
- Modify: `apps/web/src/features/consultant/consultantWorkspaceModel.ts`
- Modify: `apps/web/src/features/consultant/consultantWorkspaceTestFixture.ts`
- Modify: `apps/web/src/features/consultant/ConsultantWorkspace.integration.test.tsx`
- Modify: `apps/web/src/app/globals.css`

### Step 1：寫 layout／conversation 紅燈

Testing Library cases：

1. 左右 panel 各有獨立 scroll container；中央不是 side-panel scroll 的 child。
2. 「收合工作地圖」「收合訪談」可各自隱藏 panel，中央佔用釋放空間；重開後仍顯示相同內容。
3. composer 固定在右欄底部，不需捲到訊息最下方才可輸入。
4. active run 時 mutation controls disabled、`aria-busy=true`，閱讀與 panel controls 仍可用。
5. failed run 顯示錯誤與「重試」，同時一般 composer 已解鎖，可直接送新訊息。
6. required input 卡取代 composer，只有其送出可用。

Run：

```powershell
npm run test -w @caliburn/web -- ConsultantWorkspace.integration.test.tsx
```

### Step 2：實作三欄 shell

- desktop 使用 `react-resizable-panels`；左／右各有明確 collapse trigger 與合理 min size，中央永遠保留主要寬度；
- 每欄 `min-height: 0`＋自己的 `overflow-y: auto`；conversation 外框固定、message list 捲動、composer sticky bottom；
- 小螢幕以 Base UI Drawer／Tabs 呈現 side panels，不嘗試同時塞三欄；
- neutral gray／white 為主，blue 只作主動操作，red／green 只出現在 semantic diff；不用彩色卡片區分 O／P／K／S。

### Step 3：工作地圖只顯示可理解的投影

左欄順序：

```text
目前訪談重點（可空；不顯示 Task ID）
訪談概況（已理解範圍／待釐清／矛盾／未定位／待審數量，無百分比）
待釐清（UNRESOLVED／CONTRADICTED 的員工可回答文字）
```

單純缺 O／P／K／S 不出現在「待釐清」。第一版不常駐顯示完整 Work Understanding、source／quote 或來源歷史。若最後有餘力，可加「AI 目前的理解」預設收合唯讀檢視；它必須從同一 server state 推導、不可編輯、不影響本 Task 驗收。

### Step 4：required input 與 active-run admission UX

- options 有值時顯示 2–4 個可選 card button，再保留「自行輸入」；沒有 options 就只顯示必填文字框；
- 選項只是填入答案，不另送 choice ID；
- 送出前先等待 current-document autosave queue 清空；autosave 失敗保留聊天草稿且不啟動 run；
- 409 後重新抓 snapshot，保留尚未成功送出的文字；不以 disabled UI 取代 server authority。

### Step 5：Web gate、north-star audit、commit

```powershell
cd apps/web
npm run test
npx tsc --noEmit
npm run lint
```

North-star：員工看得到焦點與待釐清但不被 wizard 綁住；聊天可正常休息／關頁／續談；錯誤後不會鎖死。

```powershell
git add apps/web
git commit -m "feat: build the consultant three-panel workspace"
```

---

## Task 8：把 current JD 編輯與 semantic review 合成同一中央工作面

**Purpose：** 用已確認的 Duty → Task → 工作細節＋OPKS hierarchy 呈現 current JD；AI 差異原位紅／綠顯示，點擊差異才開就近 review popover。員工直接編輯綠色 after-state，autosave 後仍 pending；沒有獨立「修改」決定或額外「儲存」按鈕。

**Files：**

- Add: `apps/web/src/features/consultant/CurrentJobDocumentEditor.tsx`
- Add: `apps/web/src/features/consultant/CurrentDocumentSection.tsx`
- Add: `apps/web/src/features/consultant/SemanticReviewPopover.tsx`
- Modify: `apps/web/src/features/consultant/ConsultantWorkspace.tsx`
- Modify: `apps/web/src/features/consultant/consultantWorkspaceModel.ts`
- Modify: `apps/web/src/shared/api/jobAnalysisApi.ts`
- Modify: `apps/web/src/shared/query/jobAnalysisQueries.ts`
- Rewrite relevant integration／model／API tests
- Delete after replacement: `ApprovedDocumentEditor.tsx`
- Delete after replacement: `DocumentReviewPanel.tsx`
- Delete after replacement: `DocumentChangeEditor.tsx`

### Step 1：寫 central editor／review 紅燈

Required scenarios：

1. 同一 Task 顯示多個 O／P／K／S；K／S 被多 Task 引用時標示「共用於 N 個任務」，不複製 entity。
2. 不顯示容易因移動失真的 D1／T1／O1；使用 entity type、名稱與局部數量。
3. 修改顯示 baseline 紅色刪除線＋current 綠色可編輯；新增只有綠色；刪除只有紅色；move 在舊／新位置共用一個 change identity。
4. 點 AI 差異開 popover；點其他地方／Escape 關閉。popover 顯示 group reason、相關工作理解摘要、Accept、Reject；沒有 Edit／Defer／拒絕理由。
5. 改綠色後 autosave request 完成，但 Accept request 尚未送出且 diff 仍在。
6. Accept／Reject 送整個 dependency closure；UI 不能只送 group 中一個相依 action。
7. active run／required input 時中央只讀，但仍可展開與看 diff。

### Step 2：建立階層 view model

server contract 維持 flat stable entities，Web 只做 presentation grouping：

```text
document header（第一版不含 A／能力級別）
Duty
  Task
    Task L／工作細節（action、object、purpose、context、frequency、role、enablers）
    O（0..N）
    P（0..N）
    K（0..N links）
    S（0..N links）
尚未歸屬
  Task without duty（可帶完整工作細節與合法 OPKS）
  待重新連結 K／S（只在已核准 canonical item 失去最後 link 時出現）
```

O／P 成為 JD item 時仍恰好一個 Task；先被分析到但尚未定位的 O／P／K／S 留在 Work Understanding，不建立寬鬆 JD entity。

### Step 3：TanStack Form autosave

- form default 永遠來自 `snapshot.current_document`；
- 同 document mutation scope 序列化 autosave，300–500 ms debounce；blur／送出聊天前立即 flush；
- 畫面只顯示「儲存中／已儲存／儲存失敗」，沒有 Save button；
- server response 以 `chooseNewestConsultantSnapshot` 防 delayed response 覆蓋 SSE 新 snapshot；
- 409 清掉 stale local selection、refetch 最新 current／review，再保留可安全重套的文字輸入；不自動覆蓋 server。

### Step 4：結構新增、移動、解除與刪除

就近 `＋` 支援新增 Duty、Duty 下 Task、Task 下 O／P／K／S；K／S 可「新增」或用 Base UI Combobox「連結既有」。`×` 只用於可逆的單項移除入口，實際選單文案依 ownership：

| Command | Deterministic result |
|---|---|
| 解散 Duty、保留工作 | Duty 消失；Tasks 整棵移到尚未歸屬，工作細節與 OPKS 保留 |
| 刪除 Duty 及其工作 | Duty、Tasks、工作細節、O／P 刪除；K／S 只解除 links |
| 移動／取消 Task 歸屬 | Task 整棵移到另一 Duty 或尚未歸屬 |
| 刪除 Task | Task、工作細節、O／P 刪除；K／S 只解除該 Task link |
| Task 內移除 K／S | 只解除 link |
| 永久刪除 canonical K／S | 從待重新連結／管理位置執行，先列受影響 Tasks |

可完整逆轉的單項操作立即 autosave 並提供短期 Undo；多 Task cascade 先由 server 回 blast radius（Task／O／P 數與 K／S unlink 數），再用 Base UI Alert Dialog 確認。第一版只要求原生 Tab、Enter／Space、Escape；不自建 global shortcut、keyboard drag 或 ARIA tree。

### Step 5：semantic review popover

- popover anchor 是被改的 entity／field，不是頁尾 queue；
- baseline 唯讀，current after-state 使用與普通 current JD 相同 editor；
- group move 不顯示模糊「原本／建議」表單，而在舊位置標「移出」、新位置標「移入」；
- group 只有 Accept／Reject；按鈕 sticky 在 popover footer；
- 顏色之外固定加「AI 新增／AI 修改／AI 移出／AI 刪除」文字或圖示；
- unrelated clean fields 可正常編輯；pending group 的 after-state 編輯仍待審。

### Step 6：刪除舊主編輯／review components 並跑 gate

只有新 integration tests 全綠後才刪三個舊 components；禁止留 hidden alternate editor。

```powershell
cd apps/web
npm run test
npx tsc --noEmit
npm run lint
cd ../..
rg -n "ApprovedDocumentEditor|DocumentReviewPanel|DocumentChangeEditor|edit_and_accept|defer_changes" apps/web/src
```

Expected：全綠且最後 `rg` 零 production hit。North-star：一份可見 current JD、一個就地 diff；人與 AI 改同一 after-state，AI 內容仍需明確 Accept。

### Step 7：commit

```powershell
git add apps/web
git commit -m "feat: unify current JD editing and semantic review"
```

---

## Task 9：完整 gates、真瀏覽器與一次 Luna Max 窄 smoke

**Purpose：** 證明 hard cut 後的 deterministic authority、重啟恢復、UI 與真模型最小垂直流程可用；不把一次 smoke 冒充正式 eval，不因失敗連續付費重試。

**Files：**

- Add: `apps/api/scripts/consultant_work_understanding_live_smoke.py`
- Add: `docs/specs/2026-08-28-consultant-work-understanding-live-verification.md`
- Modify: `docs/adr/0070-consultant-workspace-ui-and-explicit-pending-edit-approval.md` status only after gate
- Modify: `docs/adr/0071-revisable-work-understanding-context-and-review-provenance.md` status only after gate
- Modify: `docs/adr/README.md`
- Modify: `docs/design/consultant-runtime.md`
- Modify: `AGENTS.md`
- Modify: API／Web READMEs and data-layer doc

### Step 1：full deterministic gates

先確認 disposable PostgreSQL target，不把 skipped DB tests 當成功：

```powershell
npm run infra
npm run db:migrate
npm run consultant-storage:setup
cd apps/api
uv sync
uv run pytest -q
cd ../web
npm run test
npx tsc --noEmit
npm run lint
cd ../..
npm run check-codegen -w @caliburn/job-analysis-contract
npx turbo test
git diff --check
```

若 PostgreSQL suite 需要 explicit `TEST_DATABASE_URL`，使用 runbook 的 disposable dev DB；先驗 fixtures rollback／cleanup，再執行，不把 production DB 當測試目標。

### Step 2：真瀏覽器 acceptance

啟動 current API／Web，使用 in-app browser 完成以下單一路徑並保存截圖／console 結果到 live-verification 文件：

1. 建新文件，送出員工工作敘述；分析時 composer 與 JD mutation disabled，但可閱讀／收合 panel。
2. 完成後看到 Work Understanding、Focus／待釐清 projection 與 current JD AI diff。
3. 編輯一個綠色 after-state，確認 autosave 後仍 pending；再 Accept 整組，approved/export 才改。
4. Reject 第二個 atomic group，確認 current rollback 且不要求理由。
5. 觸發 required input，關頁重開仍存在；只能回答該卡，回答後下一輪修訂 Work Understanding。
6. 模擬 provider failure，確認聊天框解鎖，可重試也可送新訊息。
7. 收合左右欄，中央擴張；三欄各自捲動，composer 不需捲到底才可輸入。

Browser console 不得有 hydration、duplicate key、unhandled promise 或 accessibility primitive warnings。

### Step 3：一次 GPT-5.6 Luna Max 窄 smoke

runner 必須：

- 從 `apps/api/.env` 讀 key，但不複製到 worktree、不輸出 secret；
- 強制 exact `openai/gpt-5.6-luna`、provider `OpenAI`、fallback disabled、`reasoning=max`；
- 使用足以容納 reasoning＋strict final 的 `max_tokens=32768`，同時保留既有 model／tool／elapsed／total-token／cost fail-closed guards；
- 只跑一個兩回合小情境：第一回合建立工作理解＋一組待審 Task／OPKS；第二回合用「我剛才說錯了」修訂理解與 pending JD；
- 斷言模型 route、實際 loaded Skills、context receipts、source／quote resolution、current≠approved before Accept、Accept 後一致、無 RAG／A；
- 記錄 calls、input／output／reasoning／cache tokens、latency、provider cost 與 terminal status。

Run：

```powershell
cd apps/api
uv run python scripts/consultant_work_understanding_live_smoke.py --model openai/gpt-5.6-luna --provider OpenAI --reasoning-effort max --max-output-tokens 32768 --max-cost-usd 0.20
```

若 provider/network/model failure：保留 receipt 與分類，先以 deterministic reproduction 修 code；未取得 owner 新授權前不得反覆付費 retry。一次 smoke 只證明 plumbing／代表性可用性，不宣稱模型品質已評估完成。

### Step 4：hard-cut audit

```powershell
rg -n "GapItem|UnderstandingCalibration|supersedes_source_id|evidence_source_ids|edit_and_accept|defer_changes|rejection_reason|app\.(interview|interview_vnext|job_authoring|core|documents|task_analysis|opks|consultation)" apps packages/job-analysis-contract/schema
rg -n "RAG|Reference|competency.*AI|auto.accept|multi.agent" apps/api/app/consultant apps/web/src/features/consultant
git status --short
git diff --check
```

允許 docs 的歷史文字與 tests 的 explicit negative canary；production imports／contracts／UI actions 必須零 hit。

### Step 5：更新 current design、接受 ADR、review 與 tag

只有 Step 1–4 都有新鮮證據後：

1. 更新 `docs/design/consultant-runtime.md`、AGENTS、API/Web README 與 Web data-layer；
2. 把 ADR 0070／0071 status 改 `Accepted`，同步 ADR index；Accepted 前不提前改狀態；
3. live-verification 文件寫執行日期、exact commands、成功／已知失敗、browser scenario、Luna receipts、cleanup 與不宣稱事項，不硬編容易過時的 commit count；
4. 用 `superpowers:requesting-code-review` 做一次 spec／security／authority review，修完再重跑受影響 gates；
5. 用 `superpowers:verification-before-completion` 重跑 final evidence；
6. commit docs，建立 annotated local tag。

```powershell
git add AGENTS.md apps/api/README.md apps/web/README.md apps/web/docs/data-layer.md docs
git commit -m "docs: record consultant understanding workspace completion"
git tag -a consultant-work-understanding-workspace-v1 -m "Consultant work understanding workspace v1"
```

不 merge、不 push，交回 owner 審核。

## Plan Self-Review Gate

實作者開始 Task 1 前，以及 Task 9 結束前，各跑一次：

```powershell
rg -n "TO[D]O|T[B]D|placehol[d]er|稍後決[定]|視情況實[作]" docs/superpowers/plans/2026-08-28-consultant-work-understanding-and-workspace-implementation.md
rg -n "GapItem|UnderstandingCalibration|edit_and_accept|defer_changes|rejection_reason|model-authored.*skill_ids" docs/superpowers/plans/2026-08-28-consultant-work-understanding-and-workspace-implementation.md
```

第一個指令必須零 hit。第二個指令只可命中「移除／禁止／hard-cut scan」敘述，不能把任何舊形狀列為 target。最後逐項對照 ADR 0071 acceptance gate 1–9、ADR 0070 decisions 1–16 與本計畫 Tasks 2–9；每個產品規則必須至少有一個明確 test 或 browser scenario。
