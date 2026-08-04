# 本機 JD 分層編輯與 `job_analysis` PostgreSQL 持久化研究

- 日期：2026-07-29
- 產品：本機 Web、單一操作者、可保存多份 JD；不做登入、SaaS、多租戶或多人協作
- 目標：讓已完成 T1–T7 的 `app/job_analysis` 可以保存、關閉、重開，並為員工直接編輯 Current JD
  建立最小而可靠的 PostgreSQL seam
- 不包含：Web route、完整 O/P/K/S/A、正式公版匯出、版本歷史、舊資料搬遷、Event Sourcing、hash chain

## 1. 結論

採用兩個彼此配合、但不混成一層的設計：

1. **克制版分層編輯器**：iCAP／Current JD 正式內容常駐；Task 的高價值工作分析欄位可展開編輯；
   來源按需唯讀；系統控制欄位隱藏。
2. **四表 hybrid persistence**：Current JD Task 使用關聯列；可變但有版本契約的 Work Model 與 Proposal payload
   使用小型 JSONB；完整回合、直接編輯與員工決策寫 append-only Journal。reload 直接讀 current state，
   不 replay Journal。

新設計是 greenfield：

- 不 import、wrap、dual-write 或回填 `app.job_authoring`／`app.interview_vnext`；
- 不搬 0011 的 revision、snapshot、hash 或 tenant 語意；
- 新資料從空的 `job_analysis_*` tables 開始；
- 舊表暫留但不接線，等新 vertical 驗證後另案刪除；不做舊資料 migration。

## 2. 現行權威與衝突

### 2.1 已定案的產品真相

- 員工可建立、保存、關閉並重開多份本機 JD，一次只操作一份。
- Current JD 是員工文件權威；AI 只能提出 Proposal，或在 Work Model 內更新自己的分析。
- 員工直接編輯 Current JD 立即保存；AI 不在每次 keypress／save 時介入。
- 員工下次與 AI 互動前才做 reconciliation；UI 不必顯示「待 AI 對齊」。
- 完成的 JD 編輯、完整 employee+AI turn 與 Proposal 決策可恢復；未完成 AI response 可丟棄。
- 公版是 export profile，不是內部 Job Model 的上限。

權威來源：

- [專業顧問流程 final red-team](2026-07-25-professional-job-analysis-consultant-process-final-red-team.md)
- [LLM architecture red-team](2026-07-25-professional-job-analysis-consultant-llm-architecture-red-team.md)
- [Task／Proposal／Context v1 研究](2026-07-28-task-boundary-merge-split-and-identity-research.md)
- [Task Analysis Engine](../design/task-analysis-engine.md)
- [ADR 0040](../adr/0040-professional-consultant-engine-and-r1-validation-contract.md)
- [ADR 0042](../adr/0042-r1-screening-stop-and-a6-first-version-default.md)

### 2.2 必須修正的舊文件

[2026-07-24 storage research](2026-07-24-job-authoring-v2-relational-storage-research.md) 正確保留了
「current rows、無 revision、員工決策後才改 JD」；但它的 bounded module、Task identity 與部分欄位已過時：

- authority 已由 `app.job_authoring` 改為 greenfield `app.job_analysis`；
- Current Work Model、Proposal v1、SourceRef／SupportLink 與 authority snapshot 已在 7 月 28 日重新定義；
- Task ID 現行契約是 application 配發的 stable non-empty text，不綁 UUID；
- `core/supporting` 是把 O*NET 群體尺度誤套到單一員工；
- 第一版不需要 `importance`、`typicality`、`time_share_percent`；
- 尚未存在 production contract 的 O/P/K/S/A 不應先建空表。

因此本文件取代該研究作為 `job_analysis` persistence authority；舊文保留供追溯，不據以施工。

## 3. 最新官方資料查證

### 3.1 iCAP：正式文件欄位與內部分析不能混為一談

iCAP 目前官方頁面把職務基本資料、工作描述、級別、主要職責／工作任務、工作產出、行為指標、K/S/A
列為職能基準內容。操作型 Task 可以沒有獨立工作產出，成果可由行為指標表達。

對本產品的含意：

- UI 與未來匯出必須完整容納上述欄位；
- 不得為填滿 Output 格子虛構產出；
- purpose、context、frequency、責任角色與 enabler 是本產品的工作分析資訊，不冒充 iCAP 官方欄位；
- 內部編輯器可以比公版更清楚，只有 export 才要求公版格式。

來源：

- 勞動部勞動力發展署，[iCAP 職能相關概念](https://icap.wda.gov.tw/ap/knowledge_introduction.php)
- 勞動部勞動力發展署，
  [職能基準發展指引（2022 修訂，平台目前提供的正式指引）](https://icap.wda.gov.tw/ap/get_file.php?c=%E8%81%B7%E8%83%BD%E5%9F%BA%E6%BA%96%E7%99%BC%E5%B1%95%E6%8C%87%E5%BC%95.pdf&e=20221026143138.pdf&t=download)

### 3.2 O*NET：可以借概念，不能複製群體分數

O*NET 30.3 的 Task Ratings 是 occupation-level 群體統計，包含 relevance、importance、frequency、樣本數、
標準誤與信賴區間。`Core/Supplemental` 以 relevance ≥67% 與平均 importance ≥3.0 分類。

本產品是一份單一員工的客製 JD，沒有群體樣本，因此：

- 不儲存 O*NET relevance 百分比、樣本數、標準誤或信賴區間；
- 不使用 `core/supporting` 冒充 O*NET Core/Supplemental；
- frequency 可借用尺度概念，但員工確認的自然語言才是 canonical，例如「旺季每日、平時依事件」；
- 若未來需要重要性，應研究「未做好時的影響程度」，不使用 O*NET 可比較分數。

來源：

- O*NET 30.3，[Task Ratings](https://www.onetcenter.org/dictionary/30.3/mysql/task_ratings.html)
- O*NET 30.3，[Task Statements](https://www.onetcenter.org/dictionary/30.3/csv/task_statements.html)
- O*NET，2025-02，
  [Identification of Emerging Tasks: A Revised Approach](https://www.onetcenter.org/reports/EmergingTasks_RevisedApproach.html)

### 3.3 UI：需要分層，但不能把必要內容藏起來

GOV.UK Design System 的現行 guidance：

- 只有部分使用者／情境需要的詳細內容可用 progressive disclosure；
- 多數使用者都需要的內容不能藏在 details／accordion；
- 不使用巢狀 accordion 拆一整串問題；
- 可修改資料要讓使用者容易檢查與回到原處修改。

OpenAI 2026 的 reviewed-update guidance 也要求第一版先固定欄位範圍，讓人能看到來源並接受、修改或拒絕；
Anthropic 2026 的實際使用研究則指出，有效 oversight 是可信的可見性與簡單介入，不是核准每個內部步驟。

來源：

- GOV.UK，[Details](https://design-system.service.gov.uk/components/details/)
- GOV.UK，[Accordion](https://design-system.service.gov.uk/components/accordion/)
- GOV.UK，[Check answers](https://design-system.service.gov.uk/patterns/check-answers/)
- OpenAI Academy，2026-06，
  [Practice better CRM hygiene with Codex](https://academy.openai.com/public/clubs/champions-ecqup/resources/practice-better-crm-hygiene-with-codex-2026-06-18)
- Anthropic，2026-02，
  [Measuring AI agent autonomy in practice](https://www.anthropic.com/research/measuring-agent-autonomy)

### 3.4 PostgreSQL／SQLAlchemy：關聯與 JSONB 可共存，但 JSONB 必須是原子資料

PostgreSQL 18 current docs 明確說 relational 與 JSONB 可以互補；即使需求可變，JSON 文件仍應有可預測結構。
任何 JSONB 更新會鎖整列，因此一個 JSONB 應代表不可合理拆分、一起修改的 atomic datum。

這支持：

- Current JD Task 要獨立成列，因為員工會分別新增、修改、刪除與排序；
- Current Work Model 可是一個 document-scoped JSONB，因為 transition 以整體 immutable state 驗證後原子替換；
- Proposal payload 可是一列一個 JSONB，因為一份 Proposal 的 target、before/after 與 staged delta 必須一起成立；
- 不把完整 JD、Work Model、Proposal、對話全部塞進同一個 JSONB。

PostgreSQL row lock 只阻擋同列 writer／locker；`FOR UPDATE` 持有到 transaction 結束。官方也警告不要在等待使用者或
外部工作時長時間持鎖。SQLAlchemy 2.0.51 的 `Session.begin()`／`AsyncSession` context manager 提供
commit-on-success、rollback-on-error；每個 concurrent asyncio task 必須有自己的 `AsyncSession`。

來源：

- PostgreSQL 18，[JSON Types §8.14.2](https://www.postgresql.org/docs/current/datatype-json.html#JSON-DOC-DESIGN)
- PostgreSQL 18，[Explicit Locking](https://www.postgresql.org/docs/current/explicit-locking.html)
- PostgreSQL 18，[Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)
- SQLAlchemy 2.0.51，
  [Transactions and Connection Management](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html)
- SQLAlchemy 2.0.51，
  [AsyncSession with Concurrent Tasks](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html#using-asyncsession-with-concurrent-tasks)
- Alembic 1.18.5，[Cookbook](https://alembic.sqlalchemy.org/en/latest/cookbook.html)

repo 目前固定 PostgreSQL 16、SQLAlchemy 2.0.51、asyncpg 0.31.0、Alembic 1.18.5；本設計只使用 PostgreSQL 16
已有的 JSONB、FK、CHECK、UNIQUE、identity 與 row locks，不要求升級 DB image或新增 dependency。

## 4. 產品編輯層裁決

### 4.1 常駐、員工可直接編輯

- iCAP／Current JD 表頭、工作描述、級別、主要職責；
- Task statement；
- 正式 Output、Indicator、K、S、A 與補充說明。

這些都是 Current JD employee-authoritative content。第一個 persistence vertical 只做 Task；其餘等各自 production
contract 成立才加，不先建空表。

### 4.2 每個 Task 一層「工作分析詳情」，可展開編輯

第一版 Task authoring contract 只增加：

| UI 名稱 | 儲存欄位 | 規則 |
|---|---|---|
| 工作目的／要達成的結果 | `purpose_result` | nullable；可合理隱含 |
| 執行情況或條件 | `context` | nullable |
| 執行頻率 | `frequency_text` | nullable；員工自然語言是 canonical |
| 你在這項工作的角色 | `responsibility_role` | nullable；`primary/shared/assist` |
| 工具、系統與方法 | `enablers` | `{kind,name}[]`；Java/Python/HTML 的正確落點 |

Task 收合時只顯示少量摘要，例如「每週｜主要負責｜ERP｜產出：月報」。未知值留空，不逐欄追問。

### 4.3 第一版不做

- `importance/core/supporting`；
- 獨立 `typicality`（合法的事件觸發／不固定節奏先由 `frequency_text` 表達）；
- `time_share_percent`；
- O*NET 群體尺度；
- `ref_urn`／公版 retrieval；
- 通用 custom fields。

### 4.4 唯讀或隱藏

| 內容 | UI |
|---|---|
| 相關員工原話、公版來源、已被更正 | 按需展開、唯讀、使用白話 |
| Work Model `action/object` | 隱藏 |
| `deliverable_hint/success_criterion_hint` | 隱藏；正式 Output／Indicator 才是文件真相 |
| UUID／operation ID／ordinal／authority generation | 隱藏 |
| merge/split lineage | 平常隱藏；Proposal 卡只顯示 before/after |
| `pending_reconciliation` | 隱藏；過時 Proposal 只顯示「內容已修改，此建議不再適用」 |

## 5. 需要先修正的 Current JD 契約

現行 `JdEntry {task_id, content}` 只足夠跑 T1–T7 scripted vertical，不足以支援已核准的直接編輯。
在 DB migration 前先建立獨立的 `JdTask`／`JdTaskFields`：

```text
JdTask
├─ task_id
├─ statement
├─ purpose_result?
├─ context?
├─ frequency_text?
├─ responsibility_role?
├─ enablers[]
└─ display_order
```

- Current Work Model `Task` 與 Current JD `JdTask` 是不同 authority，不共用同一 Pydantic model。
- Work Model 保留 action/object、support、lineage、hint 與 reconciliation。
- Proposal `jd_before`／`jd_after` 必須比較完整 `JdTask`，不能只比較 statement。
- 員工新增 JD-only Task 時，application 先配發 stable Task ID 並保存 Current JD；不得偽造 Work Model
  action/object/support。`JD task_id 不存在於 Work Model` 本身就是待 reconciliation 的可推導事實。
- 員工修改或刪除既有 JD Task 時，同交易寫 direct-edit Journal 並使相關 Work Model／Proposal 失穩；
  不直接讓員工改 Work Model。

Task ID 沿用現行 domain 契約：document-local stable non-empty text，由 application 配發；`T01` 只是依
`display_order` 產生的畫面／匯出碼，不是 ID。資料庫使用 `(document_id, task_id)` composite identity，
不把現行契約偷偷改成 UUID。

## 6. 比較三種 persistence 方案

### A. 全關聯式

把 Work Model 的 SupportLink、lineage、open issue、excluded signal、Proposal staged delta 全拆表。

- 優點：可用 FK 查詢每個節點。
- 缺點：大量 tables／joins／hydrate code；模型契約尚在演進；會重新走向已否決的 Evidence Engine。
- 裁決：不採。

### B. 全部 JSONB

一份 document row 保存 Current JD、Work Model、Proposal 與對話。

- 優點：最快落地。
- 缺點：員工改一項 Task 仍鎖整份文件；排序、FK、list pending Proposal、直接編輯與未來 O/P/K/S/A 都變成
  application-only integrity；容易形成第二份 monolithic snapshot。
- 裁決：不採。

### C. Hybrid current state（採用）

```text
job_analysis_documents
├─ work_model_json
├─ active_question_json?
├─ authority_generation
│
├─ job_analysis_jd_tasks          Current JD Task rows
├─ job_analysis_proposals         one atomic Proposal per row
└─ job_analysis_journal           completed turns / direct edits / decisions
```

未來 O/P/K/S/A 在契約完成後各自新增 relational current tables；不改四表的 authority 原則。

## 7. 第一個 schema 的責任

### 7.1 `job_analysis_documents`

一列一份本機 JD：

- `document_id UUID` PK；
- `title TEXT`（文件庫名稱；第一版不等同完整公版 header）；
- `work_model_schema_id TEXT`；
- `work_model_json JSONB`；
- `active_question_json JSONB NULL`；
- `authority_generation BIGINT NOT NULL DEFAULT 0`；
- `created_at/updated_at TIMESTAMPTZ`。

hydrate 時用現行 Pydantic contract 驗證 JSONB；不一致 fail closed，不讓損壞資料進模型。

### 7.2 `job_analysis_jd_tasks`

- `(document_id UUID, task_id TEXT)` composite PK；
- `statement TEXT NOT NULL`；
- `purpose_result/context/frequency_text TEXT NULL`；
- `responsibility_role TEXT NULL`，named CHECK 限定 `primary/shared/assist`；
- `enablers_json JSONB NOT NULL DEFAULT '[]'`，hydrate 驗 `{kind,name}[]`；
- `display_order INTEGER NOT NULL`，非負；同一文件不得重複；
- `created_at/updated_at TIMESTAMPTZ`；
- FK `document_id → documents ON DELETE CASCADE`。

這張表只存員工可見、可編輯的 Current JD Task。Work Model 欄位不得鏡像進來形成雙重真相。

### 7.3 `job_analysis_proposals`

- `(document_id, proposal_id TEXT)` composite PK；
- `status TEXT`，named CHECK 使用現行 ProposalStatus；
- `base_authority_generation BIGINT`；
- `proposal_schema_id TEXT`；
- `proposal_payload JSONB`（target、完整 JD before/after、staged delta 與決策 payload）；
- `caused_by_decision_id TEXT NULL`，同一 document 內唯一；
- `created_at/resolved_at TIMESTAMPTZ`。

adapter 從 relational identity/status 與 payload 重建 `Proposal` 並完整驗證。Proposal 是 current review object，
不是 revision snapshot。

### 7.4 `job_analysis_journal`

- `journal_sequence BIGINT GENERATED ALWAYS AS IDENTITY` PK；
- `document_id UUID` FK；
- `entry_id TEXT`，同一 document 唯一，亦作 command／operation idempotency key；
- `kind TEXT`：`employee_turn/direct_edit/proposal_decision`；
- `payload_schema_id TEXT`；
- `payload JSONB`；
- `created_at TIMESTAMPTZ`。

Journal 只 insert，不提供 update/delete repository method。它保存 completed unit 與 SourceRef 目標，但：

- Current State 不靠 Journal replay 重建；
- 不要求 Journal 足以重建 Current State；
- 不建 event projection、snapshot、hash chain、outbox 或 CQRS；
- 模型比較重播仍由 runtime 外的 eval capture 負責。

## 8. Transaction 與 authority generation

### 8.1 員工直接編輯

```text
validate command
  → BEGIN
  → lock document row FOR UPDATE
  → entry_id 已存在：回既有結果，不重做
  → insert/update/delete/reorder JD Task
  → insert direct_edit Journal
  → 更新 Work Model reconciliation / stale Proposal
  → authority_generation + 1
  → COMMIT
```

前端可 debounce，但一次完整 save 是一個 transaction；不在每次 keypress 寫 DB。

### 8.2 AI turn

```text
短 transaction A：讀取 authority snapshot + context，結束
provider call：transaction 外
短 transaction B：
  lock document FOR UPDATE
  → generation / read-set 不符：丟棄舊結果，重新分析
  → apply verified transition
  → 寫 Work Model + Proposal + completed-turn Journal
  → generation + 1
  → COMMIT
```

絕不在等待 LLM 或使用者時持 DB lock。`AsyncSession` 一個 asyncio task 一個，不跨 task 共用。

### 8.3 Proposal 決策

同一 transaction：

- lock document，再以固定順序 lock Proposal／Task；
- 驗 Proposal 仍為 pending/deferred、generation 與完整 `jd_before`；
- accept/edited 才套用 Current JD；reject/defer 不改 JD；
- staged Work Model delta 與 JD 需要一起生效時原子套用；
- 寫 `proposal_decision` Journal、更新 Proposal、generation + 1。

所有 mutation 固定先 lock document，再依 task_id／proposal_id 排序，避免互鎖順序漂移。

### 8.4 reload

直接 hydrate：

1. document + Work Model；
2. ordered Current JD Tasks；
3. pending/deferred Proposals；
4. active question；
5. 最近完成回合。

不 replay Journal，不讀舊 `job_authoring` 或 vNext tables。

## 9. 過度設計紅隊

| 攻擊 | 處理 |
|---|---|
| 四表還是太多，能否一個 JSONB？ | Task、Proposal、Journal 的修改與查詢生命週期不同；合併後會回到 whole-document lock 與 monolithic snapshot。 |
| Work Model 為何不拆表？ | 第一版只需整體 hydrate／replace，且 domain 以 immutable aggregate 驗證；拆 SupportLink／lineage 表沒有產品收益。 |
| 為何需要 generation，明明單一使用者？ | 使用者可在 LLM 執行期間直接編輯；這是真實兩個 writer 時序，不是 SaaS concurrency。 |
| 為何需要 Journal？ | SourceRef、完整 turn resume、direct edit 與 decision 需要 durable target；但 Journal 不具重建責任。 |
| 為何不把舊資料搬過來？ | 尚未有使用者／production data，搬遷只會把失效 contract 與 revision/hash 語意帶進新引擎。 |
| 為何現在不建 O/P/K/S/A tables？ | 還沒有 production contracts；先建會讓 schema 反向決定尚未研究完成的語意。 |
| 是否需要 trigger／RLS／outbox？ | 不需要：單機無 tenant，無外部消息投遞；application transaction + named constraints 足夠。 |

## 10. 最小施工順序

1. 先把 Current JD 從 `JdEntry` 升為可編輯 `JdTask`，同步 Proposal before/after 與 context projection。
2. 建 persistence ports，不讓 `app/job_analysis` import SQLAlchemy。
3. 在 `app/adapters/` 新建 greenfield PostgreSQL adapter；Alembic 新增 `job_analysis_*` tables。
4. 實作 create/list/load document、Task direct edit/reorder/reload。
5. 實作 verified AI transition 的兩段式 authority snapshot commit。
6. 實作 Proposal accept/edit/reject/defer/stale 與 completed Journal。
7. 用少量 real-PostgreSQL integration tests 驗原子性、stale、idempotency 與 reload。
8. scripted vertical 通過後才設計 local Web route；其後依序增加 O/P/K/S/A。

## 11. 明確延後

- 公版 header 全欄位與 export；
- O/P/K/S/A／Requirement tables；
- 公版 retrieval 與 `ref_urn`；
- 版本歷史、undo、revision diff；
- DB 內 append-only trigger；
- Event Sourcing／CQRS／Graph DB；
- background worker／outbox；
- SaaS、tenant、account、ACL；
- 搬遷、轉換或相容舊 `job_authoring`／vNext 資料。
