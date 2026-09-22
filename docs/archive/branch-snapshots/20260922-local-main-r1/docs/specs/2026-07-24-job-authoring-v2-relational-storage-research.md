# Job Authoring v2：本機單一現況 JD 關聯式儲存設計

- 日期：2026-07-24
- 狀態：**已被 2026-07-29 `job_analysis` greenfield persistence 研究取代，勿據本文施工**
- 目標：先交付可儲存、訪談、編輯與匯出的高品質本機 JD 成品
- 不包含：版本歷史、還原、revision diff、SaaS、多租戶、帳號權限、公司共用職能庫、Graph DB
- 上游研究：
  - [專業職務分析與共編研究](2026-07-20-interview-vnext-professional-job-analysis-and-short-answer-architecture-research.md)
  - [本機多文件工作區研究](2026-07-23-local-multi-document-jd-workspace-and-public-form-ui-research.md)
  - [ADR 0039](../adr/0039-local-multi-document-canonical-public-form-workspace.md)

> **2026-07-29 supersession**
>
> 本文保留供追溯，但其 `app.job_authoring` bounded module、UUID-only Task identity、完整預建 O/P/K/S/A tables、
> `core/supporting` 與欄位集合已不是現行施工 authority。新引擎不搬遷、整合或 dual-write 舊資料；現行決策見
> [本機 JD 分層編輯與 `job_analysis` PostgreSQL 持久化研究](2026-07-29-local-jd-authoring-and-postgresql-persistence-research.md)。

## 1. 2026-07-24 Owner 裁決

第一個成品不做完整版本系統。

> 資料庫只保存每份 JD 的「目前內容」。員工儲存或接受 AI 提案時，直接在同一個 transaction 更新目前資料。
> 不為每次修改複製所有 Duty／Task／Output／Indicator／K／S rows。

因此目前資料設計：

- 不使用 `revision_id`；
- 不使用 `entity_version`；
- 不使用 `link_version`；
- 不建立 `job_authoring_revision_*` 內容表；
- 不提供歷史版本、還原或版本 diff；
- 不把這些功能偷偷換成 event sourcing、temporal tables 或其他複雜機制。

這不影響 AI 必須先提出 proposal。員工仍能：

- 直接編輯目前文件；
- 接受 AI 提案；
- 修改 AI 提案後採用；
- 拒絕 AI 提案。

差別只是「採用」會更新目前文件，而不是產生完整的新 revision。

另一項同等重要的裁決：

> 內部 Job Model 的目標是支援專業工作分析，不是逐欄複製政府公版。政府公版只是 export profile；內部可以保留
> 頻率、任務目的、責任程度、重要性與典型／例外等顧問分析資訊，再由不同匯出器決定是否顯示。

## 2. 核心關係

```text
job_authoring_documents
  ├─ job_authoring_duties
  │    └─ job_authoring_tasks
  │          ├─ job_authoring_outputs
  │          └─ job_authoring_indicators
  ├─ job_authoring_knowledge
  ├─ job_authoring_skills
  ├─ job_authoring_attitudes
  ├─ job_authoring_entry_requirements
  ├─ job_authoring_task_knowledge ── task + knowledge
  ├─ job_authoring_task_skills    ── task + skill
  └─ job_authoring_proposals
```

這是一般 PostgreSQL 關聯式模型，不是 Graph DB。UI 可以把資料投影成：

```text
主要職責
  └─ 工作任務
       ├─ 工作產出
       ├─ 行為指標
       ├─ K
       └─ S
```

但 K/S 在資料庫仍是文件層 entity，再透過 link table 連到一個或多個 Task，避免同一個 K/S 因畫面巢狀而被重複保存。

### 2.1 哪些訪談限定條件應進正式 Job Model

既有 R5 Evidence 已分開記錄 `frequency`、`ownership`、`importance`、`typicality`、`time_scope` 與 `polarity`。
它們不能全部原封不動搬進 JD：

| 訪談維度 | 正式 JD 處理 |
|---|---|
| `frequency` | 保存；協助判斷任務實際節奏與訪談深度 |
| `ownership` | 保存 `owner/shared/assists`；避免把他人的工作寫給員工 |
| `importance` | 保存 `core/supporting`；低頻任務也可能是高重要性 |
| `typicality` | 保存 `typical/occasional/exception`；頻率與典型性不可互相代替 |
| `time_scope` | 不建 JD 欄位；只有 current／現職內容才可 materialize 成 Task |
| `polarity` | 不建 JD 欄位；否定內容用來阻止錯誤 Task，不是正式 Task 屬性 |

`frequency` 不能單獨決定核心工作。例如年度法遵申報頻率低，但重要性可能很高；臨時代收文件頻率可能高，卻只是
支援工作。Context Engine 與顧問 loop 必須分開看頻率、重要性、責任程度與典型性。

## 3. Identity 與顯示碼

所有 JD entity 使用 application 產生的 UUID：

- `document_id`
- `duty_id`
- `task_id`
- `output_id`
- `indicator_id`
- `knowledge_id`
- `skill_id`
- `attitude_id`
- `entry_requirement_id`

`T1`、`O01`、`P01`、`K01`、`S01`、`A01` 都不是 ID。它們是 UI／匯出時依 `display_order`
產生的顯示碼。重新排序可以改變顯示碼，但不能改變 entity UUID 或 Task–K/S 關係。

公版項目也先建立本 JD 自己的 UUID。若來自公版，只額外保存現有 Indexer ID：

```text
ref_urn TEXT NULL
```

- `NULL`：客製內容；
- 非空：可回查公版來源；
- `ref_urn` 不是本 JD 的 PK／FK；
- 第一版不另建來源、作者、編輯者、複製方式或 provenance tables。

## 4. 目前資料表

### 4.1 `job_authoring_documents`

一列代表一份可從本機工作區開啟與儲存的 JD；公版表頭直接放在這張表，不另建 revision header。

| 欄位 | 型別 | 用途 |
|---|---|---|
| `document_id` | UUID | PK |
| `interview_session_id` | UUID NULL | 連接這份 JD 的訪談 session |
| `job_title` | TEXT | 本 JD 顯示名稱 |
| `benchmark_code` | TEXT NULL | 職能基準代碼 |
| `benchmark_name_type` | TEXT NULL | `job_family` 或 `occupation` |
| `benchmark_name` | TEXT NULL | 職能基準名稱 |
| `job_category_name` | TEXT NULL | 職類別名稱 |
| `job_category_code` | TEXT NULL | 職類別代碼 |
| `occupation_category_name` | TEXT NULL | 職業別名稱 |
| `occupation_category_code` | TEXT NULL | 職業別代碼 |
| `industry_category_name` | TEXT NULL | 行業別名稱 |
| `industry_category_code` | TEXT NULL | 行業別代碼 |
| `job_description` | TEXT NULL | 整體工作描述 |
| `benchmark_level` | SMALLINT NULL | 基準級別 |
| `additional_notes` | TEXT NULL | 其他補充說明 |
| `ref_urn` | TEXT NULL | 選用公版時的最小來源 ID |
| `created_at` | TIMESTAMPTZ | 建立時間 |
| `updated_at` | TIMESTAMPTZ | 最近儲存時間 |

`job_title` 是本地工作區的職務名稱；`benchmark_name` 是公版欄位。兩者可相同，也可不同。

### 4.2 `job_authoring_duties`

| 欄位 | 型別 | 用途 |
|---|---|---|
| `duty_id` | UUID | PK |
| `document_id` | UUID | FK → documents |
| `description` | TEXT | 主要職責 |
| `display_order` | INTEGER | 顯示順序 |
| `ref_urn` | TEXT NULL | 公版來源 ID |

### 4.3 `job_authoring_tasks`

| 欄位 | 型別 | 用途 |
|---|---|---|
| `task_id` | UUID | PK |
| `document_id` | UUID | FK → documents |
| `duty_id` | UUID NULL | 同一份文件的主要職責；尚未分組可空 |
| `description` | TEXT | 可觀察 action + object；Task 的主要顯示文字 |
| `purpose_text` | TEXT NULL | 執行此工作要達成的結果／目的 |
| `context_text` | TEXT NULL | 觸發條件、適用情境或主要輸入 |
| `frequency_value` | NUMERIC NULL | 每個 frequency unit 約執行幾次 |
| `frequency_unit` | TEXT NULL | `per_day/per_week/per_month/per_quarter/per_year/irregular` |
| `frequency_text` | TEXT NULL | 員工確認的自然語言，例如「旺季每日、平時視需求」 |
| `ownership` | TEXT NULL | `owner/shared/assists` |
| `importance` | TEXT NULL | `core/supporting` |
| `typicality` | TEXT NULL | `typical/occasional/exception` |
| `time_share_percent` | NUMERIC(5,2) NULL | 員工願意估算時才填的工時比重 |
| `display_order` | INTEGER | 文件內 Task 顯示順序 |
| `ref_urn` | TEXT NULL | 公版來源 ID |

欄位規則：

- `description` 保持短而清楚，不把所有限定條件塞進同一句；
- `frequency_text` 是員工看到的核准文字；`frequency_value/unit` 只在能可靠正規化時填，彼此不一致就拒絕寫入；
- `ownership/importance/typicality` 不知道時使用 `NULL`，不得由職稱或模型常識猜值；
- `time_share_percent` 完全選填，也不要求整份 JD 加總必須是 100%；舊 ADR 0027 的硬性 100% 是歷史假設，不是目前要求；
- 這些欄位由自然訪談抽取或高價值追問取得，不逐 Task 逐格盤問。

### 4.4 `job_authoring_outputs`

| 欄位 | 型別 | 用途 |
|---|---|---|
| `output_id` | UUID | PK |
| `document_id` | UUID | FK → documents |
| `task_id` | UUID | FK → 同一份文件的 Task |
| `name` | TEXT | 產出短名稱；使用名詞性、可交付／可查核的文字 |
| `description` | TEXT NULL | 產出的內容、範圍或必要組成 |
| `output_kind` | TEXT NULL | `document/data/system/decision/service_result/physical/other` |
| `recipient_text` | TEXT NULL | 主要交付、使用或服務對象 |
| `display_order` | INTEGER | Task 內順序 |
| `ref_urn` | TEXT NULL | 公版來源 ID |

第一版一個 Output 直接屬於一個 Task；有真實共用 Output 案例後再討論 many-to-many。
`output_kind` 是內部分析／篩選欄位，不要求政府公版匯出顯示。操作型 Task 可以沒有 Output，不為填滿欄位
虛構「報告」或其他產出。

### 4.5 `job_authoring_indicators`

行為指標內部保留「條件—行為—標準」結構，但不重複保存另一份完整句子。

| 欄位 | 型別 | 用途 |
|---|---|---|
| `indicator_id` | UUID | PK |
| `document_id` | UUID | FK → documents |
| `task_id` | UUID | FK → 同一份文件的 Task |
| `condition_text` | TEXT NULL | 在什麼情況、工具或輸入條件下 |
| `behavior_text` | TEXT | 可觀察的工作行為 |
| `standard_text` | TEXT NULL | 品質、時間、正確率或完成標準 |
| `measurement_method_text` | TEXT NULL | 如何檢查，例如主管覆核、抽樣或系統紀錄 |
| `display_order` | INTEGER | Task 內順序 |
| `ref_urn` | TEXT NULL | 公版來源 ID |

UI／匯出器再把三段組成自然句。公版資料若無法可靠拆段，可把完整內容先放在 `behavior_text`，其餘留空。
第一版不建立 `threshold JSONB`；「正確率 95%」直接保留在 `standard_text`。
Indicator 第一版只連 `task_id`，不加入 `output_id`；Output 與 Indicator 仍可在同一 Task 區塊一起檢視。

### 4.6 `job_authoring_knowledge`

| 欄位 | 型別 | 用途 |
|---|---|---|
| `knowledge_id` | UUID | PK |
| `document_id` | UUID | FK → documents |
| `name` | TEXT | K 短名稱 |
| `description` | TEXT NULL | 這份工作需要理解什麼 |
| `display_order` | INTEGER | 產生 K01／K02 的文件順序 |
| `ref_urn` | TEXT NULL | 公版來源 ID |

### 4.7 `job_authoring_skills`

| 欄位 | 型別 | 用途 |
|---|---|---|
| `skill_id` | UUID | PK |
| `document_id` | UUID | FK → documents |
| `name` | TEXT | S 短名稱 |
| `description` | TEXT NULL | 能運用什麼方法完成工作 |
| `display_order` | INTEGER | 產生 S01／S02 的文件順序 |
| `ref_urn` | TEXT NULL | 公版來源 ID |

### 4.8 `job_authoring_attitudes`

| 欄位 | 型別 | 用途 |
|---|---|---|
| `attitude_id` | UUID | PK |
| `document_id` | UUID | FK → documents |
| `name` | TEXT | 態度名稱 |
| `description` | TEXT | 可觀察的態度說明 |
| `display_order` | INTEGER | 產生 A01／A02 的順序 |
| `ref_urn` | TEXT NULL | 公版來源 ID |

Attitude 不從員工聊天語氣自動推斷；必須有工作內容、公版候選或員工確認。

### 4.9 `job_authoring_entry_requirements`

| 欄位 | 型別 | 用途 |
|---|---|---|
| `entry_requirement_id` | UUID | PK |
| `document_id` | UUID | FK → documents |
| `requirement_kind` | TEXT | `education`、`experience` 或 `prerequisite_ability` |
| `description` | TEXT | 任職條件 |
| `display_order` | INTEGER | 同類別內順序 |
| `ref_urn` | TEXT NULL | 公版來源 ID |

這是「建議擔任此職務的條件」，不與 K/S 混表。

### 4.10 `job_authoring_task_knowledge`

| 欄位 | 型別 | 用途 |
|---|---|---|
| `document_id` | UUID | 文件邊界 |
| `task_id` | UUID | FK → 同文件 Task |
| `knowledge_id` | UUID | FK → 同文件 Knowledge |
| `relevance_reason` | TEXT NULL | 為什麼完成此 Task 需要這項 Knowledge |

PK `(task_id, knowledge_id)`。不存 `display_order`，Task 下顯示 K 時使用 Knowledge 自己的文件順序。
`relevance_reason` 是工作需求的關聯理由，不是來源／作者／provenance 紀錄。

### 4.11 `job_authoring_task_skills`

| 欄位 | 型別 | 用途 |
|---|---|---|
| `document_id` | UUID | 文件邊界 |
| `task_id` | UUID | FK → 同文件 Task |
| `skill_id` | UUID | FK → 同文件 Skill |
| `relevance_reason` | TEXT NULL | 為什麼完成此 Task 需要這項 Skill |

PK `(task_id, skill_id)`。不存 `display_order`，Task 下顯示 S 時使用 Skill 自己的文件順序。
`relevance_reason` 是工作需求的關聯理由，不是來源／作者／provenance 紀錄。

### 4.12 `job_authoring_proposals`

這張表只保存尚待員工決定或已決定的 AI 文件修改建議，不保存完整版本歷史。

| 欄位 | 型別 | 用途 |
|---|---|---|
| `proposal_id` | UUID | PK |
| `document_id` | UUID | FK → documents |
| `proposal_kind` | TEXT | `add`、`edit` 或 `delete` |
| `target_type` | TEXT | duty/task/output/indicator/knowledge/skill/attitude/entry requirement/header |
| `target_id` | UUID NULL | add 可空；edit/delete 指向目標 |
| `base_payload` | JSONB NULL | 提案時員工看到的原內容，用於 diff 與避免覆蓋後續人工修改 |
| `proposed_payload` | JSONB | AI 建議內容 |
| `reason_text` | TEXT NULL | 給員工看的白話建議理由，不保存 hidden chain-of-thought |
| `decision_payload` | JSONB NULL | 員工修改後採用的最後內容 |
| `status` | TEXT | `pending`、`accepted`、`edited`、`rejected` 或 `stale` |
| `created_at` | TIMESTAMPTZ | 建立時間 |
| `resolved_at` | TIMESTAMPTZ NULL | 員工完成決定時間 |

`base_payload` 不是版本系統。接受 edit/delete 前，service 只比較目前目標是否仍等於 base；若員工已經直接修改該項，
proposal 變成 stale，不得覆蓋新內容。

## 5. 儲存與 AI 提案流程

### 5.1 員工直接編輯

```text
員工修改
  -> 前端短暫 debounce
  -> 後端驗證欄位與關係
  -> transaction 更新目前 rows
  -> documents.updated_at 更新
```

不在每次 keypress 建立資料庫寫入，也不建立 revision。

### 5.2 AI 修改

```text
AI 分析 Evidence + Current Job Canvas
  -> 建 proposal
  -> UI 顯示新增／修改／刪除差異
  -> 員工接受、修改後採用或拒絕
```

- 接受：同一 transaction 更新目前 rows，proposal → accepted；
- 修改後採用：使用 `decision_payload` 更新目前 rows，proposal → edited；
- 拒絕：不改 JD rows，proposal → rejected；
- 目標已被人工修改：不覆蓋，proposal → stale。

AI provider、prompt 或模型永遠不能直接寫 `job_authoring_*` 內容表。

## 6. 專業職務說明書的品質規則

內部欄位增加的目的不是讓表格變長，而是讓 AI 顧問能做下列專業判斷。

### 6.1 Duty／Task

- Duty 是一組具有共同 purpose、workflow stage、stakeholder 或 domain 的 Tasks，不是單句改寫；
- Task 使用具體動詞，描述「action + object」，必要時另存 purpose/context；
- 一條 Task 是具有有意義結果的最小活動單位，避免把多個先後步驟硬塞成一條；
- 只收 current、affirmed，且 ownership 為 owner/shared/assists 的實際工作；
- 任務粒度應大致一致，檢查缺漏、重複與過度切碎；
- frequency、importance、typicality 與 optional time share 共同協助判斷核心程度，不使用單一欄位硬排序。

### 6.2 Output

- 優先寫文件、報告、資料集、設定、系統、決策結果或其他可查核成果；
- 使用名詞性描述，不把每個 Task 動詞機械名詞化；
- 純操作／服務型 Task 可以合法沒有 Output，成果改由 Indicator 說清楚；
- Output 必須連回真實 Task，不為了填滿公版格子憑空補產出。
- Output 可另存 kind、內容範圍與 recipient，讓內部分析不受公版單一文字格限制。

### 6.3 Indicator

- 內部採 `condition + observable behavior + standard`；
- 必須能區分合格與不合格表現；
- 禁止「了解、熟悉、積極負責、溝通良好」等無法直接觀察的口號；
- 數字 KPI／門檻只能來自員工回答、員工直接輸入或明確採用的規範；模型不可自己發明；
- 沒有可靠門檻時可以只有清楚的質性 standard，不用為量化而量化。
- `measurement_method_text` 只描述如何查核，不得用模糊覆核文字取代可觀察 standard。

### 6.4 Knowledge／Skill

- K 描述完成 Task 所需的事實、原則、規則或模型，不寫成「熟悉／精通」；
- S 描述能學習、能展示的做法，不把工具名稱本身當技能；
- 每個 K/S 都必須連到至少一個 Task，且確實有助於完成該 Task；
- Task–K/S link 可保存白話 `relevance_reason`，協助員工理解 AI 為什麼建議；
- 公版查無結果時建立 document-local custom K/S，不強迫選最近的官方項目；
- 員工審核的是「這份工作是否需要」，不是替系統審 taxonomy 學術名稱。

### 6.5 訪談負擔

高品質不等於每個欄位都逐題詢問：

1. 先用工作故事／open narrative 找出 Task 與 workflow；
2. 自動抽取已說出的 frequency、ownership、purpose、output 與 standard；
3. 每個 episode 只追問 1–2 個最能提升 JD 的缺口；
4. K/S 主要由已確認 Task + optional 公版候選起草，再讓員工用白話審核；
5. `NULL`、unknown 與 not applicable 都是合法結果；
6. 不為補齊公版欄位拖長訪談。

## 7. 既有 0011 的處理

現行 migration 0011 已有：

- `job_authoring_documents`
- `job_authoring_revisions`
- `job_authoring_proposals`

它是先前最小 Authoring Core 的實驗性 revision 版本，不再代表目前 MVP 儲存目標。實作本設計前必須另寫 migration
與切換計畫，但現在不急著刪表或改 production code。

實作時遵守：

1. 不新增 revision-scoped entity tables；
2. 不讓舊 `snapshot_json` 與新 current tables 同時成為可寫 authority；
3. 測試資料可重建時，優先一次切換，不做長期 dual-write；
4. 舊 revisions tables 可暫留未使用，待新 current flow 驗證後再清理；
5. 不為相容 test data 增加長期 adapter、回填或 SaaS infrastructure。

## 8. 為什麼現在這樣較適合

保留的核心品質：

- T/O/P/K/S/A 分離；
- 真正 UUID 與 FK；
- Task–K/S 明確 linkage；
- AI proposal 必須由員工決定；
- 公版只作候選與最小 `ref_urn` 參考；
- 內部保留頻率、目的、責任、重要性與典型性，不受公版欄位限制；
- 一份 JD 可完整儲存、關閉、重開、切換與匯出。

延後的功能：

- 歷史版本列表；
- 還原舊版；
- revision diff；
- 撤銷跨多次儲存；
- 多人同時編輯與衝突合併。

這些功能不直接提升第一個成品的訪談與職務分析品質，因此等成品可用後再評估。

穩定 UUID 已足以讓未來版本功能識別同一個 Task/K/S；目前不需要預先加入 `entity_version` 或複製整份 JD。

## 9. 最小實作順序

1. 定稿 current `JobDocumentDraft.v2` contract；
2. 建立 current relational tables 與 repository；
3. 完成新增、開啟、儲存、切換多份 JD；
4. 接 employee direct edit；
5. 接 AI proposal accept/edit/reject/stale；
6. 接訪談 Context Engine 與 Current Job Canvas；
7. 接公版 retrieval 候選與 `ref_urn`；
8. 接政府公版格式與一般 JD 格式匯出。

最低測試只保留：

- 不可把其他文件的 Task 與本文件 K/S 連在一起；
- 顯示順序變更不改 entity UUID；
- 接受／修改後採用才改文件，拒絕不得改文件；
- stale proposal 不得覆蓋員工新內容；
- 儲存後關閉重開，JD 內容與 linkage 一致。

## 10. 來源

- PostgreSQL, [Constraints](https://www.postgresql.org/docs/current/ddl-constraints.html) — FK、composite FK 與
  many-to-many association table。
- SQLAlchemy 2.0, [Basic Relationship Patterns](https://docs.sqlalchemy.org/en/20/orm/basic_relationships.html) —
  one-to-many 與 many-to-many。
- 勞動部勞動力發展署 iCAP,
  [職能相關概念](https://icap.wda.gov.tw/ap/knowledge_introduction.php) — 主要職責／工作任務、工作產出、行為指標、
  Knowledge、Skill 定義。
- U.S. Department of Labor O*NET,
  [O*NET Database](https://www.onetcenter.org/database.html) — Tasks、Knowledge、Skills 分離。
- NIST,
  [NICE Framework Current Versions](https://www.nist.gov/itl/applied-cybersecurity/nice/nice-framework-resource-center/nice-framework-current-versions) —
  Task、Knowledge、Skill components。
- European Commission ESCO,
  [Structure of ESCO Downloadable Datasets](https://esco.ec.europa.eu/en/structure-esco-downloadable-datasets) —
  occupations、skills concepts 與 relationship files／stable URIs。
- National Center for O*NET Development,
  [Task Writing Guidelines](https://www.onetcenter.org/dl_files/GreenTask_AppB.pdf) — Task 的 action/object/purpose
  結構、單一活動與文字品質規則。
- UK Standards & Frameworks Panel,
  [Quality Criteria for National Occupational Standards](https://ukstandards.org.uk/media/nfmcz5ir/nos-quality-criteria-11-09-23.pdf) —
  performance criteria 必須能區分合格與不合格表現。
