# JD 表頭（`JdHeader`）與 readiness 切片實作計畫

- 日期：2026-08-04
- 狀態：T1 COMPLETE；T2–T7 尚未開工
- 決策：[ADR 0052](../adr/0052-jd-readiness-assessment-and-official-code-boundaries.md)、
  [ADR 0053](../adr/0053-jd-header-authority-boundary-and-readiness-scope.md)；
  authority seam 邊界沿用 [ADR 0045](../adr/0045-job-analysis-local-web-contract-and-shared-authority-commit.md)
- 版型權威：[iCAP 2026 品質認證作業手冊逐字核對](../specs/2026-08-02-icap-2026-quality-manual-form-authority.md)
- 現行設計：[`task-analysis-engine.md`](../design/task-analysis-engine.md)

## 1. 目標與現況

ADR 0052／0053 已於 2026-08-02 Accepted，但 `JdHeader`、`DocumentReadinessView` 與 readiness issue
codes 在 domain、contract、route 與 Web **完全沒有實作**，也沒有 plan。本切片補上 ADR 0052 決定 11
列的範圍，**不做** Duty／Task 職能級別結構切片，**不做**匯出。

本輪前 baseline：完整 API `1750 passed / 277 skipped / 0 failed`（merge `f18c129` 後量測）。

不需要新研究或新 ADR：版型欄位已由 iCAP 手冊逐字核對，決策已由 0052／0053 固定。

## 2. 範圍

做：公版 header 欄位、nullable 基準級別（1–6，員工手選）、說明與補充事項、readiness 純函式、
API、UI 編輯與缺漏提示，以及把高訊號 header 送進 Task Analysis packet。

不做：Duty／每 Task 職能級別、匯出、`職能基準代碼`／`職類別代碼` 輸入欄、OPKS packet 變更、
通用 metadata framework、舊 OCS autofill。

## 3. 欄位形狀（依 iCAP 手冊附錄二與 ADR 0052 決定 8–9）

| 欄位 | 型別 | 備註 |
|---|---|---|
| `competency_name` 職能基準名稱 | `str \| None` | 職類／職業擇一，第一版單一自由文字 |
| `occupation_category_name` 職類別名稱 | `str \| None` | 依手冊領域分類；**代碼不開欄位**（iCAP 配發） |
| `occupation_name` 職業別名稱 | `str \| None` | 中華民國職業標準分類 |
| `occupation_code` 職業別代碼 | `str \| None` | 分類資料，員工可填（0052 決定 9） |
| `industry_name` 行業別名稱 | `str \| None` | 中華民國行業統計分類 |
| `industry_code` 行業別代碼 | `str \| None` | 分類資料，員工可填（0052 決定 9） |
| `work_description` 工作描述 | `str \| None` | 高訊號，進 Task Analysis packet |
| `competency_level` 基準級別 | `int \| None`，1–6 | 員工手選；**LLM 不得推論**（0052 決定 12） |
| `notes` 說明與補充事項 | `str \| None` | 條件式欄位，空白**不列缺漏**（0053 決定 8） |

**沒有** `職能基準代碼`／`職類別代碼` 欄位——不開輸入框、不列缺漏、不生成（0052 決定 8）。

空字串一律 trim 成 `None`（沿用現行 HTTP DTO mapper 慣例），domain 不收半成品。

## 4. readiness 第一版 issue codes

只涵蓋 header；Duty／Task 職能級別規則等該切片完成時加進**同一個純函式**，不加 scope／version 欄位
（0053 決定 7）。

| issue code | 何時發聲 |
|---|---|
| `competency_name_missing` | `competency_name` 為空 |
| `work_description_missing` | `work_description` 為空 |
| `competency_level_missing` | `competency_level` 為空 |

`DocumentReadinessView` **只有 `issues: tuple[...]`，沒有 `is_complete`／`ready`／百分比**；零 issue
時 UI 保持安靜（0053 決定 6）。措辭「iCAP 版型欄位尚有 X 項未填」，**不得**用「不完整／不合格／未通過」
（0052 決定 7）。

**所屬類別三組（職類別／職業別／行業別）第一版不發聲**：手冊未明確規定三者皆為必填，依 0052 決定 6
「無法確定的一律不提示」。這是刻意的保守選擇，不是遺漏；要改需先有官方依據。

## 5. Task 切片（一個 task 一個 commit，綠了才 commit）

### T1 — domain `JdHeader` 與 readiness 純函式

1. `app/job_analysis/domain/jd_header.py`：frozen `JdHeader`，全欄位 nullable，`competency_level`
   以 `Field(ge=1, le=6)` 約束，空白字串在 validator 拒絕（要 `None` 不要 `""`）。
2. `app/job_analysis/application/readiness.py`：`ReadinessIssueCode` StrEnum、frozen
   `DocumentReadiness`（只有 `issues`）、`assess_readiness(header) -> DocumentReadiness` 純函式，
   輸出順序決定性。**不 import transport contract、不碰 IO**（0052 決定 1）。
3. `tests/test_job_analysis_jd_header.py`：欄位形狀、級別邊界（0／7 拒絕，1／6 接受）、空字串拒絕。
4. `tests/test_job_analysis_readiness.py`：三個 issue 各自觸發、全填時零 issue、`notes` 空白不發聲、
   所屬類別空白不發聲、輸出順序穩定。

完成條件：純函式無 IO；`test_job_analysis_dependencies.py` 的 AST guard 仍綠。

### T2 — state、persistence 與 migration 0015

1. `JobAnalysisState` 增 `jd_header: JdHeader = JdHeader()`；`commit_authority_change` 驗證後一併寫入。
2. `application/persistence.py`：`DocumentRecord` 增 `jd_header`；`DocumentRepository.update_authority`
   簽章增 `jd_header`；新增 `JD_HEADER_SCHEMA_ID = "job-analysis-jd-header/1"` 與
   `JdHeaderDirectEditPayload`（`before`／`after` 快照）＋ `JD_HEADER_DIRECT_EDIT_SCHEMA_ID`。
3. `alembic/versions/0015_job_analysis_jd_header.py`：在 `job_analysis_documents` 增
   `jd_header_schema_id`／`jd_header_json` 兩欄（比照既有 `work_model_*`），既有列以空 header 回填。
   **不建新表**——header 與 `authority_generation` 同列，CAS 原子性直接成立。
4. `adapters/job_analysis_postgres/{models,serialization,repositories}.py`：新增兩欄的讀寫與 hydrate；
   shape 壞掉 fail-closed。
5. `tests/test_job_analysis_migration.py`、`test_job_analysis_persistence_contracts.py`、
   `test_job_analysis_authority_commit.py`、`test_job_analysis_postgres.py`：補 header 往返與 CAS。

完成條件：真 PostgreSQL 測試綠；既有文件（無 header）可正常載入。

### T3 — authoring use case（員工儲存 header）

1. `application/authoring.py` 增 `put_jd_header()`：document lock → `Idempotency-Key` 當 Journal
   `entry_id` 做 replay/conflict 判定 → 同交易寫 Current State、Journal（direct-edit payload）與
   generation bump，全部經 `commit_authority_change()`。**不呼叫 LLM。**
2. 未改內容禁止儲存（沿用 Task 編輯的既有規則），避免空 Journal 與無關 generation bump。
3. `tests/test_job_analysis_authoring_postgres.py`：儲存、replay 同 key、conflict、未改內容拒絕、
   generation 遞增、Journal payload 正確。

完成條件：header 走的是與 Task／OPKS 同一條 authority seam（0053 決定 3）。

### T4 — contract 與 API

1. `packages/job-analysis-contract/schema/job-analysis-workspace.schema.json`：新增 `JdHeaderView`、
   `JdHeaderWrite`、`DocumentReadinessView`、`ReadinessIssueView`；`DocumentView` 增
   `jd_header` 與 `readiness`。**契約只承載形狀與固定 issue code，不承載政策**（0052 決定 2）。
   **不擴充 `DocumentMetadataWrite`**（0053 決定 1–2）。
2. `npm run -w @caliburn/job-analysis-contract build` 重生 Pydantic／TS，`check-codegen` 綠。
3. `app/api/routes/job_analysis.py` 增 `PUT /{document_id}/jd-header`，要求 `Idempotency-Key`，
   回 `JdHeaderView`；錯誤走既有 RFC 9457 problem+json。`GET /{document_id}` 一併回 `jd_header`
   與 `readiness`。
4. `app/api/job_analysis_mapper.py`：DTO ↔ domain，空字串 trim 成 `null`。
5. `tests/test_job_analysis_api.py`、`test_job_analysis_api_postgres.py`：route 行為、缺
   `Idempotency-Key`、無效級別回 `invalid-request`、readiness 隨 header 變動。

完成條件：Web 不需自行重算 readiness（0052 決定 3）；exporter 日後呼叫同一純函式（0052 決定 4）。

### T5 — Task Analysis packet 的整體描述區

1. `application/context.py`：`TaskAnalysisPacket` 增 `employee_written_overview`，**只帶
   職能基準名稱與工作描述**，**沒有 ordinal、沒有 `SourceRef`**，與有 ordinal 的訪談依據明確分開
   （0053 決定 4）。`build_context_packet()` 增 `jd_header` 參數。
2. `render_context_packet()` 把該區獨立成段，明寫其用途只有理解用語／找 coverage 缺口／發現矛盾／
   選擇追問，並明寫**不得單獨據以產生任何 task change**。
3. `llm/prompt.py` 的 Static Instructions 同步加入該禁令。
4. **OPKS packet 不變**（0053 決定 4 末段）——header 不得進 `opks_context.py`，否則工作描述會
   繞過 0048／0049 的 Evidence 白名單支撐 K/S。
5. `tests/test_job_analysis_context.py`、`test_job_analysis_prompt.py`、`test_job_analysis_opks_context.py`：
   rendering 決定性、該區無 ordinal／無 ID、OPKS packet 位元組不受 header 影響。

完成條件：`test_job_analysis_opks_context.py` 證明 header 沒有洩漏進 OPKS。

### T6 — Web 編輯與缺漏提示

1. `apps/web/src/components/workspace/JdHeaderForm.tsx` 與 `ReadinessNotice.tsx`；
   `ConsultationWorkspace.tsx` 接入。
2. 採**明確儲存**（沿用 Task／OPKS 慣例），無 autosave、無 Server Action、無第二份 store；
   成功後 invalidate document／consultation／文件庫 query。
3. `ReadinessNotice` 直接呈現 API 的 issues；**零 issue 時不渲染任何東西**，不顯示綠色「完成」。
   文案「iCAP 版型欄位尚有 X 項未填」。
4. `基準級別` 是 1–6 下拉，可清空；**沒有 AI 生成按鈕**。
5. web 測試：`npm run test`＋`npx tsc --noEmit`＋`npm run lint`。

完成條件：UI 不重算 readiness；措辭不含「不完整／不合格／未通過」。

### T7 — 文檔同步（與 T1–T6 各自同 commit，不另開收尾 commit）

`docs/design/task-analysis-engine.md`：§2 組件表、§3 資料流、§5 不變量層級、§8「完整 header、匯出」
列改為已完成的部分與剩下的 Duty／匯出；`apps/api/README.md` codemap；`docs/README.md` 索引加本 plan。

## 6. 驗證

每個 task：targeted tests → 受影響 tests → `test_job_analysis_dependencies.py` AST guard →
完整 API `uv run pytest` 相較 baseline 只增加 pass → `git diff --check`。
T4／T6 另跑 contract codegen 與 web 三件套。

**不需要 live／付費呼叫**：本切片沒有新的模型行為主張。T5 改了 packet 與 instructions，屬
「會影響判斷的改動」，依 `task-analysis-engine.md` §8.2 **上線前**要補一次 Opus／Sonnet run；
該 run 需 owner 另行授權，不屬本切片完成條件。

## 7. 停線條件

- 為了 header 去擴充 `DocumentMetadataWrite`，或讓 header 繞過 `commit_authority_change`；
- 開出 `職能基準代碼`／`職類別代碼` 輸入框，或讓 application／LLM 生成它們；
- readiness 出現 `is_complete`／`ready`／完成百分比，或用「不完整／不合格」措辭；
- readiness 阻止保存、訪談或匯出；
- header 進了 OPKS packet；
- 模型被允許只憑 header 產生 task change，或推論基準級別；
- 為了本切片新增通用 metadata framework、接回舊 OCS autofill，或提前做 Duty／匯出。

## 8. 待決（開工前需 owner 一句話）

「所屬類別」三組是否要列入 readiness 缺漏。第 4 節目前**不發聲**（依 0052 決定 6 的保守側）。
若 owner 認為官方版型要求必填，再補 issue code；這不影響其餘 task 的施工順序。

## 9. T1 執行證據（2026-08-04）

- RED：`tests/test_job_analysis_{jd_header,readiness}.py` 先因 `JdHeader` 與
  `application.readiness` 缺失形成可重現 collection error；GREEN 後兩檔 `29 passed`。
- `app/job_analysis/domain/jd_header.py`：九個欄位全 nullable，`competency_level` 以
  `ge=1, le=6` 約束，文字欄位沿用 `NonEmptyText` 因此空字串與純空白一律拒收。測試另鎖定
  **模型不存在任何 iCAP 配發代碼欄位**，`_code` 結尾的欄位只有職業別與行業別兩個分類代碼。
- `app/job_analysis/application/readiness.py`：`assess_readiness()` 依官方表頭順序回三個
  determinable issue，順序決定性；`DocumentReadiness.model_fields` 精確等於 `{"issues"}`，
  測試逐一擋掉 `is_complete`／`ready`／`percent` 等欄位名。說明補充與所屬類別經測試證明不發聲。
- AST 測試證明 `readiness.py` 不 import `job_analysis_contract`、FastAPI、SQLAlchemy 或 httpx。
- job_analysis targeted：`551 passed / 59 skipped`。完整 API：`1779 passed / 277 skipped / 0 failed`，
  相較本輪 baseline `1750 passed / 277 skipped / 0 failed` 恰好增加 29 個新測試，無 regression。
- 尚未接 `JobAnalysisState`、persistence、migration、API、packet 或 UI；未跑 live／付費呼叫。
  下一個可獨立 task 是 T2。
