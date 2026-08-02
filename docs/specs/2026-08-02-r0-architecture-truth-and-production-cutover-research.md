# R0：架構真相與第一條 production vertical 切換／退役研究

- 日期：2026-08-02
- 狀態：Accepted research；決策見 [ADR 0041](../adr/0041-document-boundary-single-writer-cutover.md)
- 範圍：現行 production、兩個隔離 prototype、新專業顧問引擎、current-row Authoring 與本機 Web 的切換邊界
- 不包含：R1 operation/schema 實作、資料庫 migration、API route、Web UI、既有資料刪除

## 1. 問題

repo 同時存在三套不同世代的寫入語意：

| 世代 | 現況 | 可寫真相 | 使用者是否可操作 |
|---|---|---|---|
| 現行 v3 | `app/interview` + `DocumentVersion.content` | 完整 OCS JSON 與文件內 `_pending` | 是；正式 router 與 Web 目前都走這條線 |
| vNext prototype | `app/interview_vnext` + migration `0010` | durable session/run/artifact/command/event/checkpoint 狀態 | 否；composition root 未掛 route |
| Authoring v1 prototype | `app/job_authoring` + migration `0011` | immutable `snapshot_json` revisions + proposals | 否；composition root 未掛 route |

產品權威則已改為：本機單一操作者、current-row relational JD、AI 只提 proposal、Current State 是唯一真相，
同交易寫 append-only Consultation Journal；專業顧問引擎依 ADR 0040 greenfield 重作。若直接把 vNext 接到舊 Web，
會同時延續被取代的 operation/state、舊 OCS JSON 寫入與 `_pending`，形成三套可寫 authority。

## 2. 程式碼診斷

### 2.1 目前真正的 production 路徑

`apps/api/app/api/router.py` 只掛：`users`、`job_profiles`、`documents`、`occupations`、`ai`、`interview`。
沒有 `interview_vnext`、`job_authoring` 或 `local_workspace` router。現行端到端為：

```text
/documents/[id]/interview
  -> POST /api/v1/job-profiles/{profile_id}/interview:turn
  -> app/interview consultant + scribe
  -> op -> verify -> DocumentVersion.content._pending
  -> Web 接受／拒絕
  -> PATCH /api/v1/job-profiles/{profile_id}/document
```

因此「vNext 已有 production OpenRouter backend」不等於「vNext 已是 production 使用者路徑」。production 在本研究中只指
composition root 可達且有使用者流量的路徑。

### 2.2 不能直接延伸的 prototype

- ADR 0040 已全面取代 ADR 0038；舊 `turn.interpret`、`question.select`、Context Builder、Evidence shape 與 gold
  不可作為新顧問引擎前提。
- `interview_vnext` 的 provider adapter、Capture、checkpoint、outbox、conformance 等可作候選 donor，
  但每項必須由新 operation 的需求重新證明，不得整包 import。
- `job_authoring` v1 的 revision/snapshot 設計不是 current-row v2 目標，不得加 revision-scoped Duty／Task／O/P/K/S/A。
- `apps/web` 現行 OCS editor 與追蹤修訂 UI 是過渡 production；只修阻斷性錯誤，不再承接新產品能力。

### 2.3 不需要重寫的穩定邊界

- `pdf-to-json`、`ocs-contract`、`ocs-indexer`、`indexer-contract`、`embedder` 的資料主權與服務邊界維持。
- PostgreSQL 仍由 API 擁有；Qdrant 仍由 indexer 擁有；API 不直接讀 Qdrant。
- OpenRouter-first 與 provider binding/conformance 原則維持，但 shipping operation、prompt、schema 必須依 R1 重新驗證。
- 現有 Web 視覺資產可以重用；不能重用它的 OCS JSON authority 與 `_pending` 寫入語意。

## 3. 外部權威研究

| 來源 | 與本案直接相關的結論 |
|---|---|
| Martin Fowler, [Strangler Fig](https://martinfowler.com/bliki/StranglerFigApplication.html), 2024 | 大型替換不應假設「照舊系統重寫」就安全；以小範圍新價值逐步替換，讓投資、回饋與退役逐步可見。 |
| AWS, [Strangler fig pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/modernization-decomposing-monoliths/strangler-fig.html) | 切換分 transform／coexist／eliminate；coexist 必須有明確 rollback，最後一定要 eliminate，不能讓過渡層永久化。 |
| AWS, [Anti-corruption layer pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/acl.html) | 舊、新 domain 語意不同時用窄 adapter/facade 翻譯；所有依賴移走後 ACL 本身也要退役。 |
| Danilo Sato／Martin Fowler, [Parallel Change](https://martinfowler.com/bliki/ParallelChange.html) | 不相容介面以 expand／migrate／contract 分段；若 contract 階段不執行，並存版本會比原狀更糟。 |
| PostgreSQL 16, [Constraints](https://www.postgresql.org/docs/16/ddl-constraints.html) | 跨列／跨表完整性優先用 primary key、unique、foreign key，而非依賴應用慣例或跨表 `CHECK`。 |
| PostgreSQL, [START TRANSACTION](https://www.postgresql.org/docs/current/sql-start-transaction.html) | Current State、proposal decision 與 Consultation Journal 的原子性必須由同一 transaction 明確保護。 |

本案不是把 monolith 拆成微服務；採用的是上述模式的**切換紀律**。seam 位於同一 FastAPI application 的 router／application
boundary，避免為本機單人產品增加 gateway、訊息匯流排或新服務。

## 4. 選項比較

| 選項 | 優點 | 主要問題 | 裁決 |
|---|---|---|---|
| A. 立即刪除 v3、一次大改 | 最快看到整齊碼面 | R1–R5 尚未過 gate；沒有可用替代路徑與資料回退 | 拒絕 |
| B. 舊 OCS JSON 與 current rows 長期 dual-write | 表面上可隨時切 UI | 兩套 authority 必然漂移；proposal、linkage、順序與 `_pending` 無可靠雙向映射 | 拒絕 |
| C. 舊 route 呼叫新核心並互相轉換 | 可少改 Web | 舊 envelope 與 OCS deep JSON 會污染新 Source／Work／Document 邊界；ACL 變永久產品層 | 拒絕 |
| D. 以 document 為切換單位、單寫者並存 | rollback 與資料責任清楚；不用同步同一文件 | 過渡期要維護舊、新兩個 UI 路徑 | 採用 |
| E. 等 R1–R9 全做完才一次切換 | 最少過渡程式 | 太晚取得真實 Web/transaction 回饋，退役風險集中 | 拒絕 |

## 5. 採用方案

### 5.1 第一條 production vertical（PV1）

PV1 是第一個可由本機員工操作、且完整走新 truth boundary 的最小成果：

```text
建立一份新 JD
  -> 開始／恢復訪談
  -> 員工送出一段工作故事
  -> 新顧問引擎保存 Source／Work Current State 並產生下一題
  -> 有足夠支持時建立 Task proposal
  -> 員工 accept／edit-accept／reject
  -> 同 transaction 更新 Current JD + proposal decision + Consultation Journal
  -> 關閉並重開後，conversation 與 Current JD 一致
```

PV1 必須等 R1–R5 各自 exit gate 通過後才能掛 production route。R6 公版 challenger、R7 完成判斷／匯出可以在
PV1 後與 Web 後段整合交錯；PV1 不得假裝代表完整產品品質。

### 5.2 切換單位與單一寫入者

- 切換單位是整份 `document_id`，不是 endpoint、欄位或單一 Task。
- 新 workspace 建立的文件只寫 current-row tables；舊 `job_profile` 文件只寫 `DocumentVersion.content`。
- 同一 `document_id` 在任一時點只能有一個 writer generation。
- 遷移一份舊文件時，先驗證／匯入新 current rows；成功後才把該文件標成新 writer 所有。失敗則舊文件原封不動。
- 不把新 current rows 回寫成舊 OCS draft；OCS 只由 deterministic export projector 產生。

### 5.3 seam 與契約

- 新 `local_workspace` application seam 組合新顧問核心、current-row Authoring、知識 port 與 transaction。
- FastAPI route 只依賴 `local_workspace` use cases，不直接組合 prototype repositories。
- Web／Python 是跨語言 seam，依 `docs/contract-strategy.md` 採獨立 JSON Schema SSOT + Pydantic／TypeScript codegen。
- `local-workspace-contract` 不 import 或重定義 `ocs-contract`；後者只留在 import/export boundary。
- R0 不建立 package 或 route；實際 request／response 名稱要在 PV1 contract task 中產生並由測試固定。

### 5.4 既有資料處理

切換前必須先跑 read-only inventory，不能先假設資料可丟：

| inventory 結果 | 處理 |
|---|---|
| 只有可重建測試／開發資料 | 備份必要 fixture 後一次切換，不做 production importer |
| 有要保留的本機 JD | 每份文件 transaction-safe 單向匯入，產 reconciliation report；原始 OCS JSON 暫時唯讀保留 |
| mapping 不完整 | 不切該 document writer；回報缺欄／linkage，禁止靜默截斷 |

長期 dual-write、雙向同步與自動 reverse migration 一律禁止。

### 5.5 rollback

- PV1 route 啟用前：rollback 只是移除新 composition，不影響現行 v3。
- coexist 期間：legacy document 仍由舊 writer 處理；新 document 不得倒灌舊 writer。
- 單份匯入失敗：rollback 該 transaction，舊文件仍可讀寫。
- 新 writer 發生 LLM 故障：保留新 workspace 的 direct edit／resume，不把新文件導向舊 `_pending`。
- schema migration 必須 additive；實體刪除 legacy tables 另開後續 task，不能與首次 route cutover 同 commit。

## 6. 切換與退役 gate

| Gate | 必須證明 | 未通過時 |
|---|---|---|
| G0 架構真相 | 本研究、ADR 0041、R0 plan、living design 與 orientation 一致 | 不開始 R1 |
| G1 顧問核心 | ADR 0040 的 R1 exit gate 通過 | 不做 DB／Web product seam |
| G2 共編核心 | R2–R5 的 multi-turn、resume、O/P/K/S/A、proposal／Current JD gate 通過 | 不掛 PV1 route |
| G3 PV1 安全網 | generated contract、real PostgreSQL vertical、Web typecheck/lint、重啟重開、idempotency、stale proposal 測試全綠 | 不讓新文件走新 writer |
| G4 資料切換 | inventory、備份／匯入、reconciliation report、`legacy_documents_remaining` 可判定 | 舊文件保持 legacy writer |
| G5 退役 | 新文件全走新路徑；需保留文件皆已匯入；owner 接受 clean-install 與 restart 操作結果 | 不刪舊 route/code/table |

G5 後按不同 commit 退役：先移除舊 Web 導航與寫 route，再移除 v3／prototype code，最後才以獨立 migration 刪表。
每一步都保留前一個 release tag 作 recoverable checkpoint。

## 7. 結論

Caliburn 不需要三套模型互相同步；需要的是一個明確的 document ownership boundary。現行 v3 保持可用但凍結，
新顧問引擎先完成 R1–R5 品質與共編 gate，PV1 才建立新的 local workspace seam。coexist 只允許不同文件分屬不同 writer，
不允許同一文件 dual-write。當所有需保留文件已切換，舊 UI／route／domain／table 依序 eliminate。
