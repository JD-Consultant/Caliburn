---
title: 專業顧問引擎與 current-row JD — production 切換邊界
audience: agent-primary（也給人）
status: R1 T2 implemented；R1 gate 未通過；新 production route 尚未實作
updated: 2026-08-03
---

# 專業顧問引擎與 current-row JD — production 切換邊界

> **目前沒有新專業顧問 route／Web seam。** `apps/api/app/api/router.py` 未掛 `interview_vnext`、
> `job_authoring`、`professional_consultant` 或 `job_workspace`。R1 T1/T2 已建立離線合約、八案、rubric、verifier、
> prompts/schema 與 scripted runners；六臂 harness、live provider 與 gate 仍未完成，不得把 partial implementation 當成端點或 R1 通過。切換決策見
> [ADR 0041](../adr/0041-document-boundary-single-writer-cutover.md)，職務發現語意見
> [ADR 0042](../adr/0042-hybrid-job-discovery-and-ttop-formation.md)，第一版發布門檻見
> [ADR 0043](../adr/0043-real-employee-pilot-release-gate.md)，deployment boundary 見
> [ADR 0044](../adr/0044-server-deployed-browser-product.md)。

## 1. 目前可達的正式路徑（ACTIVE／TRANSITIONAL）

```text
Web /documents/[id]/interview
  -> POST /api/v1/job-profiles/{profile_id}/interview:turn
  -> app/interview
  -> op -> verify -> DocumentVersion.content._pending
  -> Web accept/reject helper
  -> PATCH /api/v1/job-profiles/{profile_id}/document
```

這條線仍承接現在的使用者流量，但只允許 maintenance。完整現行行為見
[訪談引擎 v3 設計](interview-engine.md)；它不是新顧問引擎的 domain 或 persistence authority。

## 2. 程式區域狀態

| 區域 | 狀態 | 可以做什麼 | 禁止 |
|---|---|---|---|
| `app/interview` | ACTIVE／TRANSITIONAL | 修阻斷、資料損毀、安全缺陷 | 新增新顧問 operation、擴充 `_pending` |
| `DocumentVersion.content` | ACTIVE／TRANSITIONAL | 保存既有 OCS editor 文件 | 成為新文件 authority、與 current rows dual-write |
| `app/interview_vnext` | ISOLATED PROTOTYPE／DONOR | 依 ADR 0040 逐項評估 provider、Capture、checkpoint 等基礎 | 直接掛 router；重用舊 gold/schema/operation/state |
| `app/job_authoring` v1 | ISOLATED PROTOTYPE | 保留既有測試與三表，不擴張 | 新增 revision-scoped entity；讓 `snapshot_json` 成為 v2 truth |
| current-row Authoring v2 | PLANNED／NOT IMPLEMENTED | 後續依核准 storage research 實作 | R0 建表、假裝 route 已存在 |
| 新 professional consultant | R1 T2 IMPLEMENTED／R1 IN PROGRESS | T1 authority bundle + T2 prompts、portable schema、scripted once/two-stage runner；下一步 T3 harness/Capture | import/wrap v3；直接 promotion 現有 vNext loop；未有 live 證據宣稱 gate 通過 |
| `job_workspace` seam | PLANNED／NOT IMPLEMENTED | R1–R5 過 gate 後組合第一條 production vertical | 在 R0 發明 request／response 或 route |

## 3. 第一條 production vertical（PV1，PLANNED）

PV1 的 outcome 已固定，介面尚未建立：

```text
建立新 JD
  -> 開始／恢復訪談
  -> 員工送出一段工作故事
  -> 保存 Source／Work Current State
  -> 回覆下一題
  -> 支持度足夠時建立 Task proposal
  -> 員工 accept／edit-accept／reject
  -> Current JD + proposal decision + Consultation Journal 同 transaction
  -> 關閉／重啟／重開仍一致
```

PV1 不含公版 reference challenger、完整 O/P/K/S/A 品質宣稱、完成判斷或正式匯出；這些分別由 R6／R7 gate 承擔。
PV1 只有在 R1–R5 gate 通過、實際 route 與 generated contract 落地後才可改標 ACTIVE。

### 3.1 混合式職務發現（PLANNED）

新顧問的分析順序固定為：暫定職務框架 → 開放工作敘事 → 週期／交接／例外／低頻高影響與 reference 定向補漏 →
跨敘事形成 Task → 歸納 Duty → 共同定義 Output／Indicator → 逐項連結 KSA 候選 → 人員確認。暫定 Duty 與 reference
只提供假說／覆蓋檢查，不是員工 Evidence；故事是材料，不直接成為 Task；Output 不得自動產生正式 Indicator。

R1 只驗證上述路徑中的 Task Discovery 與下一問，不得提早建立完整 Duty／O／P／KSA 或把規劃中的順序寫成已存在 route。

### 3.2 R1 離線 authority bundle（IMPLEMENTED／PARTIAL）

目前可執行的 R1 邊界是：

```text
TaskDiscoveryInput
  -> once: task.discover
  -> 或 two-stage: turn.understand -> work.reconcile_decide
  -> strict JSON -> Pydantic operation output -> deterministic verifier
  -> TaskDiscoveryOutput
  -> 排序穩定的 VerificationReport
```

- `apps/api/app/professional_consultant/` 擁有新 `SourceClaim`、`UnmappedSignal`、`Story`、`WorkUnit`、
  `TaskCandidate`、`NextQuestion` 與 `turn.understand`／`work.reconcile + decide`／一次呼叫契約；合法的零 Task 結果是
  first-class outcome。
- deterministic verifier 檢查本回合新輸出的 span、entity/reference、correction supersession、Task support eligibility、重複關聯與
  exact-normalized 重問；它只拒絕可確定的結構／來源錯誤，不替代品質 grader。
- `apps/api/evals/professional_consultant/r1/` 擁有 8 個依 ADR 0040 重新裁決的 constructed-edge cases 與單一
  Job Analysis Quality Rubric。runtime loader 只回傳 transcript/input；expectations 與 adjudication 只能由 evaluation loader 讀取，
  防止答案滲入 generator。
- production `app/` 不 import eval assets；新 pure core 不 import `app.interview`、`app.interview_vnext`、
  `app.job_authoring`、FastAPI、ORM、provider SDK 或 agent/Graph framework。

T2 新增的可執行邊界：

- `PromptArtifact` 固定 `task.discover` minimal/full 與兩階段各自的 full prompt；minimal 只給 Task rubric，full 才加入
  Source Claim／Unmapped／Work Unit／linkage 與禁令。Prompt 不要求 chain-of-thought。
- `provider_schema_for(operation, profile)` 從同一 domain output model 投影 light/heavy schema。兩者 value shape 完全相同；
  light 只有 portable structural vocabulary，heavy 只增加 property descriptions。`$ref/$defs`、local constraints、title/default
  不穿越 seam，完整 Pydantic validation 與 verifier 永遠保留。
- `StructuredOutputProvider.generate(StructuredOperationRequest)` 是唯一 async port。request 只含 operation/version、prompt artifact、
  canonical input JSON 與 output-schema artifact；不含 OpenRouter `messages/response_format`、model、endpoint、routing、HTTP 或 SDK object。
- `run_task_discovery_once` 與 `run_task_discovery_two_stage` 都在每個 provider result 後 parse/verify。stage 1 invalid 時不呼叫
  stage 2；錯誤分為 `provider_failed`、`output_json_invalid`、`output_schema_invalid`、`verification_failed`，只有最後一類附
  `VerificationReport`。runner 不捕捉 async cancellation。
- eval-only `ScriptedProvider` 只依序回 neutral response 或 typed provider failure，production `app/` 不 import 它。

此 bundle **尚不包含** A1–A6 harness、Trial Manifest/Capture、blind grader、CLI、OpenRouter adapter/preflight 或 live eval。
因此 R1 仍是 `IN PROGRESS`，不是 `OFFLINE-READY`、`GATE-PASSED` 或 production。

## 4. 文件 ownership 與寫入不變量

1. 切換單位是整份 `document_id`；同一文件同一時間只有一個 writer generation。
2. legacy 文件只寫 `DocumentVersion.content`；新文件只寫 current-row Authoring。
3. AI output 只能建立 proposal；模型不能產生 application UUID，也不能直接更新 Current JD。
4. accept／edit-accept 才能修改 Current JD；reject 不修改；target 已變更時 proposal 必須 stale。
5. Current State、proposal decision 與 Consultation Journal 在同一 PostgreSQL transaction 寫入。
6. Journal 是歷史／診斷紀錄，不負責 replay 重建 Current State。
7. OCS JSON 是 import/export projection；不得回到 live workspace persistence。
8. Indexer 是 reference knowledge；不得把 reference candidate 當 employee Evidence 或直接寫正式 JD。
9. 第一版 Current JD 是 employee-confirmed draft truth，不是企業正式核准；現行 route 不建立主管／HR approval authority。
10. 完整 Web 與 technical cutover 只形成 release candidate；R9 必須由實際在職員工以本人工作完成端到端 pilot，才能稱為
    第一個員工可用成品。模擬 persona、高擬真 transcript、內部自測或非操作者專家審閱不能取代。

## 5. 切換流程

```text
R0 architecture lock
  -> R1 Task Discovery gate
  -> R2 multi-turn gate
  -> R3 resume/context-state gate
  -> R4 Duty + O/P/K/S/A gate
  -> R5 proposal/current-JD gate
  -> PV1 contract + API + Web + real-PG vertical
  -> 新文件切新 writer
  -> legacy inventory／必要時逐文件單向匯入
  -> legacy_documents_remaining = 0
  -> 移除舊 Web 寫入與 route
  -> 移除舊 domain/prototype code
  -> 獨立 migration 刪 legacy tables
```

不得跳過中間 gate，亦不得把 route cutover、code deletion、table deletion 合成一次 big-bang 變更。
上述是 writer／route 的技術切換順序，不等於產品 release。整體 roadmap 完成 R6–R8 後只得到 server-deployed Web release candidate；
R9 真實員工 pilot gate 通過後，才到達第一個員工驗證成品。

## 6. 資料遷移與 rollback

- inventory 是 read-only；先判斷有沒有需保存的本機 JD。
- 可重建資料直接重建；需保存資料逐 document transaction 匯入並產 reconciliation report。
- mapping 不完整時不切 ownership，舊資料保持可讀寫；禁止靜默丟欄位。
- coexist 期間 legacy document 可繼續走舊 route；新 document 永不倒灌 `_pending`。
- LLM 失效時，新 workspace 以 direct edit／resume 降級；不以舊引擎接管新 document。
- legacy table 只在新 route 穩定、需保留資料完成切換且 owner 核准後，由獨立 migration 刪除。

## 7. 契約邊界

PLANNED `job_workspace` 是 Python／TypeScript seam，因此依 `docs/contract-strategy.md` 使用獨立 JSON Schema SSOT，
生成 Pydantic 與 TypeScript。它與 `ocs-contract` 平行：

```text
job-workspace-contract   = 對話、Current Work／JD view、proposal decision 的 live contract
ocs-contract             = PDF ingest／OCS import/export contract
indexer-contract         = API 與 indexer 的 Python query contract
```

任何實作 commit 必須把本節替換成真實 package、schema ID、route、request、response、錯誤碼與 transaction；
在那之前不得建立手寫 TS DTO 假裝契約已定。

## 8. 退役禁令

- 不把 `turn.interpret`／`question.select`／舊 Evidence shape 改名後當新 R1。
- 不 import/wrap `app.interview.consultant`、`scribe`、`harvest`、`select`。
- 不擴充 `_pending`、`DocumentVersion.content`、`snapshot_json` 或 revision entity。
- 不做同文件 dual-write、雙向同步或自動 reverse migration。
- 不在 consultant／Authoring domain 偷塞登入、共享 tenant control plane、organization、ACL、message bus 或 Graph framework；
  R8 的 ingress／identity policy 由 deployment edge 的獨立決策承擔。
- 不在沒有 inventory、備份與 owner 核准時刪 legacy data/table。

## 9. 指路

- 產品範圍：[`../product-notes.md`](../product-notes.md)
- 顧問核心決策：[`../adr/0040-professional-consultant-engine-and-r1-validation-contract.md`](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md)
- 切換決策：[`../adr/0041-document-boundary-single-writer-cutover.md`](../adr/0041-document-boundary-single-writer-cutover.md)
- 職務發現決策：[`../adr/0042-hybrid-job-discovery-and-ttop-formation.md`](../adr/0042-hybrid-job-discovery-and-ttop-formation.md)
- Deployment 決策：[`../adr/0044-server-deployed-browser-product.md`](../adr/0044-server-deployed-browser-product.md)
- current-row storage：[`../specs/2026-07-24-job-authoring-v2-relational-storage-research.md`](../specs/2026-07-24-job-authoring-v2-relational-storage-research.md)
- R0 研究：[`../specs/2026-08-02-r0-architecture-truth-and-production-cutover-research.md`](../specs/2026-08-02-r0-architecture-truth-and-production-cutover-research.md)
- R0／PV1 plan：[`../plans/2026-08-02-professional-consultant-production-cutover-plan.md`](../plans/2026-08-02-professional-consultant-production-cutover-plan.md)
- R1 離線研究：[`../specs/2026-08-03-r1-offline-contract-verifier-implementation-research.md`](../specs/2026-08-03-r1-offline-contract-verifier-implementation-research.md)
- R1 T2 研究：[`../specs/2026-08-03-r1-t2-prompt-schema-scripted-runner-research.md`](../specs/2026-08-03-r1-t2-prompt-schema-scripted-runner-research.md)
- R1 實作 plan：[`../plans/2026-08-03-r1-task-discovery-offline-implementation-plan.md`](../plans/2026-08-03-r1-task-discovery-offline-implementation-plan.md)
