# 主要職責（Duty）與 Task 職能級別結構切片實作計畫

- 日期：2026-08-05
- 狀態：T1–T5 COMPLETE；T6–T7 尚未開工
- 決策：[ADR 0052](../adr/0052-jd-readiness-assessment-and-official-code-boundaries.md) 決定 10／13、
  [ADR 0053](../adr/0053-jd-header-authority-boundary-and-readiness-scope.md) 決定 7；
  authority seam 沿用 [ADR 0045](../adr/0045-job-analysis-local-web-contract-and-shared-authority-commit.md)
- 版型權威：[iCAP 2026 手冊逐字核對](../specs/2026-08-02-icap-2026-quality-manual-form-authority.md)、
  [2022 指引欄位標準](../specs/2026-07-13-ai-redesign-raw-icap-field-standards.md) §2／§6
- 前一個切片：[JD header 與 readiness](2026-08-04-job-analysis-jd-header-and-readiness-slice-plan.md)（T1–T6 完成）
- 現行設計：[`task-analysis-engine.md`](../design/task-analysis-engine.md)

## 1. 目標與現況

ADR 0052 決定 13 把「主要職責（Duty）＋每個 Task 的職能級別」列為**獨立結構切片**，並明定
**export-ready v1 必須完成**。目前 `Duty` 在 `app/job_analysis` 的 domain、contract、route、Web
**完全不存在**；`JdTask` 只有 `task_id` 與文件層唯一的 `display_order`，沒有職能級別。

沒有這一層就無法匯出：官方產出完整性清單（2022 指引 p38）把「主要職責及工作任務」與
「職能級別」列為必備內涵，而 `T1`／`T1.1` 位置碼要由 Duty→Task 的排序才推得出來。

本輪前 baseline：完整 API `2085 passed / 0 failed / 0 skipped`、web `108 passed`。

## 2. 官方語意（本切片的形狀來源）

| 概念 | 官方原文重點 | 對實作的意義 |
|---|---|---|
| 主要職責 | 「分層展開主要職責、工作任務、工作活動（**建議以主要職責、工作任務 2 層為主**）」 | 只做兩層：Duty → Task。**不做工作活動第三層** |
| 職責切分 | 「跨公司共通為原則，每項職責／任務的**大小要盡量一致**」 | 這是**語意判斷**，不進 verifier；留給員工與日後 rubric |
| 職能級別 | 「指要完成此項職責/工作任務所須之能力層次」；「個別工作任務之職能級別，**可能涵蓋不只一個級別**」 | 級別掛在 **Task**，各 Task 可不同，不是文件層單一值 |
| 與基準級別關係 | 「以**最主要或最多數**的工作任務所對應之職能級別，訂定為基準級別」 | 見 §7 待決 1：**本切片不自動推導**，因 ADR 0052 決定 12 已定 header 基準級別為員工手選 |
| 位置碼 | `T1`／`T1.1` 由排序決定，「匯出時決定性產生，不持久化」 | 本切片**不做匯出**，但排序必須足以決定性推出位置碼 |

## 3. 範圍

做：`Duty` 值物件與持久化、`JdTask` 的 `duty_id`（nullable）與 `competency_level`（nullable 1–6）、
Duty 的 add/edit/delete/reorder authoring use case、contract 與 route、Web 編輯、
readiness 補上這一層的缺漏規則。

不做：**匯出**（下一個切片）、工作活動第三層、AI 產生 Duty（見 §4）、
重做 OPKS identity（ADR 0052 決定 13 明定 OPKS 繼續引用 `task_id`）、
自動推導 header 基準級別（§7 待決 1）。

## 4. 為什麼第一版 AI 不參與 Duty

ADR 0052 決定 13 只要求「另開獨立結構切片」，沒有要求 AI 產生 Duty。第一版採**員工手動編輯**，
理由有三，若日後要翻案需先有真實使用摩擦的證據：

1. **ADR 0042 決定 7**：「每個新增欄位都讓形狀離 A6 的已驗證配置更遠，而第一版已無實驗預算校正。
   因此只增加**可機械檢查，或能直接診斷核心錯誤**的欄位。」把 Duty 塞進
   `task_analysis_result_v2` 是一大塊新的模型輸出面，且無預算驗證。
2. **職責切分是純語意判斷**（大小一致、跨公司共通），verifier 攔不住，錯了只能靠員工看出來——
   那正是先讓員工直接編輯的情境。
3. 歸納 Duty 的前提是「跨敘事已形成穩定 Task」（ADR 0055）。目前訪談產出的 Task 數量與穩定度
   都還沒有真實員工資料佐證，先做 AI 歸納會是在猜。

因此本切片**不動 `task_analysis_result_v2` wire schema，不動 Static Instructions**，
也就不需要再一次生產模型複驗。

## 5. 形狀

### 5.1 `Duty`

```
duty_id: DutyId          # application 配發，比照 direct-{entry_id}
statement: NonEmptyText  # 主要職責敘述
display_order: int >= 0  # 文件內唯一
```

刻意**沒有**：職能級別（掛 Task 不掛 Duty）、`T1` 位置碼（匯出時才算）、purpose/outcome
（官方沒有這個欄位，加了就是發明版型）。

### 5.2 `JdTask` 增兩個 nullable 欄位

| 欄位 | 型別 | 理由 |
|---|---|---|
| `duty_id` | `DutyId \| None` | **nullable 是硬需求**：既有文件的 Task 都還沒有 Duty，而 ADR 0052 決定 13 明令**不得自動合成假的 T1**。未指派是合法狀態，由 readiness 提示 |
| `competency_level` | `int \| None`，1–6 | 員工手選；官方允許各 Task 不同級別 |

> **T1 施工時的形狀調整**：兩個欄位都放進 `JdTaskFields`（而非只有 `JdTask`）。
> 原計畫要另開 `assign_task_duty` use case 與 route，但兩者都是員工權威的 Task 內容，
> 走既有的 `edit_jd_task` 就夠——少一條 use case、少一條 route、少一套冪等語意。
> T4／T5 因此不再需要獨立的指派入口。

`display_order` **維持文件層唯一**，不改成 Duty-scoped：位置碼 `T{i}.{j}` 由
「Duty 的 display_order」與「該 Duty 底下 Task 依 display_order 的相對次序」決定性推出，
既有 reorder route 與其冪等語意完全不用動。

### 5.3 readiness 新增 issue codes

加進**同一個 `assess_readiness()` 純函式**，不新增 scope／version 欄位（ADR 0053 決定 7）。
它的簽章會從 `(header)` 變成 `(header, duties, tasks)`。

| issue code | 何時發聲 |
|---|---|
| `task_duty_missing` | 有 Task 未指派 Duty |
| `task_competency_level_missing` | 有 Task 未填職能級別 |
| `duty_without_task` | 有 Duty 底下沒有任何 Task |

前兩者是官方產出完整性清單的必備內涵，可機械判定；第三者是版型上推不出
`T{i}.{j}` 的空職責。**維持只提示不阻止**（ADR 0052 決定 5），措辭沿用
「iCAP 版型欄位尚有 X 項未填」，不得用「不完整／不合格／未通過」。

## 6. Task 切片（一個 task 一個 commit，綠了才 commit）

### T1 — domain `Duty` 與 `JdTask` 兩個新欄位

1. `domain/duty.py`：frozen `Duty`；`DutyId` 沿用 `Identifier`。
2. `domain/proposal.py`：`JdTaskFields` 增 `competency_level`（`ge=1, le=6`），
   `JdTask` 增 `duty_id`。
3. `application/transition.py`：`JobAnalysisState` 增 `current_duties: tuple[Duty, ...]`；
   驗證 duty ID 唯一、`display_order` 唯一且 canonical 排序、**Task 的 `duty_id` 必須指向存在的 Duty**
   （指向不存在的 Duty 是不可表示的狀態）。
4. `tests/test_job_analysis_duty_domain.py`：形狀、級別邊界、canonical 排序、
   dangling `duty_id` 被拒、未指派（`None`）是合法狀態。

完成條件：非法狀態無法被建構；`test_job_analysis_dependencies.py` AST guard 仍綠。

### T2 — readiness 擴充

1. `application/readiness.py`：簽章改 `(header, duties, tasks)`，新增三個 issue code，
   輸出順序維持決定性（先 header 三項，再結構三項）。
2. `tests/test_job_analysis_readiness.py`：各 issue 單獨觸發、全填時零 issue、
   `DocumentReadiness.model_fields` 仍精確等於 `{"issues"}`、
   **所屬類別仍不發聲**（owner 2026-08-05 已裁定非必填）。

完成條件：仍不回 `is_complete`／百分比；仍不阻止任何操作。

### T3 — persistence 與 migration 0016

1. `alembic/versions/0016_job_analysis_jd_duties.py`：
   - 新表 `job_analysis_jd_duties`（`document_id`、`duty_id`、`statement`、`display_order`、
     時間欄；PK `(document_id, duty_id)`、`display_order` 文件內唯一）；
   - `job_analysis_jd_tasks` 增 `duty_id`（nullable，FK 到上表，`ON DELETE SET NULL`）
     與 `competency_level`（nullable，CHECK 1–6）。
   - 既有列不回填任何 Duty——**不得自動合成假的 T1**。
2. `application/persistence.py`：`DutyRepository` Protocol；`commit_authority_change()`
   一併 replace duties。
3. `adapters/job_analysis_postgres/{models,serialization,repositories}.py`：讀寫與 hydrate，
   shape 壞掉 fail-closed。
4. 八個 `JobAnalysisState(...)` 建構點全部帶 `current_duties`
   （**與 T2 header 同一類風險：漏一個就會讓一次 AI 回合把 Duty 洗掉**）。
5. 測試：往返、CAS、既有文件（無 Duty）照常載入、
   **AI 回合與 proposal 決策不動 Duty**（比照 header 的 mutation check）。

完成條件：真 PostgreSQL 測試綠；`ON DELETE SET NULL` 讓刪 Duty 不會孤兒化 Task。

### T4 — authoring use cases

1. `application/duty_authoring.py`：`add_duty`／`edit_duty`／`delete_duty`／`reorder_duties`，
   全部走 document lock → entry replay → `commit_authority_change()`，不呼叫 LLM。
   **Task 的 `duty_id`／`competency_level` 不另開入口**：它們在 `JdTaskFields` 裡，
   既有的 `edit_jd_task` 已經涵蓋（T1 形狀調整）。
2. 刪除 Duty 時，其底下 Task 的 `duty_id` 在**同一交易**設回 `None`，並保留 Task 本身
   （Task 是員工權威內容，不因為職責重整而消失）。
3. 測試：儲存、replay 同 key、conflict、未改內容拒絕、generation 遞增、
   刪 Duty 後 Task 仍在且變成未指派、OPKS 的 O/P 不受影響（仍綁同一 `task_id`）。

### T5 — contract 與 route

1. schema 新增 `DutyView`／`DutyWrite`；
   `JdTaskView`／`JdTaskWrite` 增 `duty_id`／`competency_level`；
   `DocumentView` 增 `duties`。（`ReadinessIssueView` 的 `code` enum 已於 T2 補齊——
   不補當下 API 就會炸，見 T2 執行證據。）
2. codegen 用 Python 3.13（見 `CLAUDE.local.md` 的環境雷），產物轉回 LF。
3. route：`POST/PUT/DELETE …/duties` 與 `PUT …/duty-order`，全部要求 `Idempotency-Key`，
   錯誤走既有 problem+json。Task 的兩個新欄位走既有 `PUT …/tasks/{id}`，不另開 route。
4. 測試：route 行為、缺 key、無效級別、readiness 隨結構變動。

### T6 — Web 編輯

1. `DutyEditor.tsx`：Duty 的新增／改名／排序／刪除；`TaskEditor` 增「所屬職責」下拉
   （可清空）與「職能級別」1–6 下拉（可清空）。
2. Current JD 依 Duty 分組呈現；**未指派 Task 集中在「尚未歸入主要職責」區**，
   讓缺漏看得見而不是被藏起來（ADR 0052 決定 5：缺漏必須在成品上看得見）。
3. 沿用明確儲存、無 autosave、dirty guard 併入 `ConsultationWorkspace`。
4. **不顯示 `T1`／`T1.1`**：那是匯出版面位置碼，不是畫面上的 identity（ADR 0052 決定 10）。
5. web 三件套＋`npm run build`。

### T7 — 文檔同步（併在 T1–T6 各自 commit）

`docs/design/task-analysis-engine.md` §2／§5／§8；`docs/README.md` 索引。

## 7. 待決（開工前需 owner 一句話）

1. **header 的「基準級別」要不要提示與 Task 級別不一致？**
   官方（2022 指引 p49）說基準級別可由「最主要或最多數的工作任務」得出，但 ADR 0052 決定 12
   已定它是**員工手選、LLM 不得推論**。本計畫**預設不自動推導、也不發不一致提示**（保守側）。
   若 owner 要，最多做成 readiness 的一條提示，仍不自動填。
2. **Duty 要不要有數量上限或建議數？** 官方只說「大小盡量一致」，沒有數字。
   本計畫**不設限制**；若 owner 有實務偏好再加。

兩題都不阻擋 T1–T4 施工。

## 8. 驗證

每個 task：targeted → 受影響 → AST guard → 完整 API 相較 baseline 只增加 pass → `git diff --check`。
T5／T6 另跑 contract codegen 與 web 三件套。

**不需要 live／付費呼叫**：本切片不動 wire schema、不動 Static Instructions、不動 packet
（見 §4），因此沒有「會影響判斷的改動」。

## 9. 停線條件

- 自動合成 `T1` 或任何預設 Duty，讓既有文件憑空長出職責（ADR 0052 決定 13）；
- 用 `ResponsibilityRole` 冒充主要職責（同上）；
- 把 `T1`／`T1.1` 位置碼落庫或當成 identity（決定 10）；
- 讓 LLM 產生 Duty 或推導職能級別／基準級別；
- 為了 Duty 重做 OPKS identity 或讓 O/P 改綁 Duty（決定 13）；
- readiness 出現 `is_complete`／百分比，或開始阻止保存／訪談／匯出；
- 做到第三層「工作活動」，或提前實作匯出。

## 10. T1 執行證據（2026-08-05）

- baseline：完整 API `2085 passed / 0 failed / 0 skipped`。
- `Duty` 只有 `duty_id`／`statement`／`display_order`。測試逐一鎖定**沒有**級別欄位
  （級別掛 Task）與**沒有**任何 `*code*` 欄位（`T1` 是匯出版面位置碼，不落庫）。
- `duty_id` 與 `competency_level` 進 `JdTaskFields`（見上方形狀調整）。`duty_id` 本身只保證是
  個 ID；**指向的 Duty 是否存在由 `JobAnalysisState` 驗**，因為只有那一層同時看得到兩者。
- 未指派（`duty_id is None`）是**合法狀態**並有測試；指向不存在的 Duty 則不可表示。
- **施工中被自己的新驗證抓到一個真 bug**：`apply_task_analysis_result()` 重建
  `JobAnalysisState` 時沒有帶 `current_duties`，於是任何帶 `duty_id` 的 Current JD Task
  都會變成 dangling reference，**整筆 transition 被擋掉**（`outcome=rejected`）。已修。
  這正是本計畫 T3 第 4 點警告的那一類遺漏，只是因為 T1 先加了驗證而提早爆出來。
- `_jd_task_from_fields()` 另補上兩個欄位的 carry-through：AI 的 `TaskFields` 沒有這兩欄，
  模型填不了，但 revise 會**重建整個 `JdTask`**，不帶就等於一次回合把員工設的職責歸屬與級別
  靜默清空。以 mutation check 驗證該測試有效：拿掉 carry-through 後測試確實變紅。
- `validate_edited_jd_after()` 把 `duty_id`／`competency_level` 與既有的 `display_order` 並列
  釘住：`edited` 是文字修改不是結構修改（§10.5），職責歸屬與級別各有自己的入口，
  不得從「改提案文字」夾帶進來。
- **其餘九個 `JobAnalysisState(...)` 建構點尚未帶 `current_duties`**：它們都從 persistence 水合，
  而 duties repository 要 T3 才存在。目前無害（沒有任何路徑能設 `duty_id`），
  但 T3 必須一次補齊，否則 duties 會在 reload 後靜默消失。
- job_analysis targeted：`656 passed`（+17）。完整 API：**`2102 passed / 0 failed / 0 skipped`**（+17）。
- 下一個可獨立 task 是 T2（readiness 擴充）。

## 11. T2 執行證據（2026-08-05）

- baseline：完整 API `2102 passed`、web `108 passed`。
- `assess_readiness()` 簽章改成**三個必填 keyword**（`header`／`duties`／`tasks`），
  刻意不給預設值：漏傳 `tasks` 會是 `TypeError`，不會安靜地變成「這份文件沒有結構缺漏」
  這種錯答案。有測試專門守這件事。
- **結構缺漏一個 code 一則，不是一個 Task 一則。** 兩個理由：readiness 是提示不是待辦清單
  （ADR 0053 決定 6），而且既有的 `ReadinessNotice` 用 `key={issue.code}` 渲染，
  一個 code 多則會產生重複 React key。
- **`field` 全部改成有前綴的路徑**（`jd_header.competency_level` vs `current_jd.competency_level`）：
  header 與 Task 各有一個 `competency_level`，不加前綴分不出是哪一個。有測試鎖定兩者不同。
- 輸出順序：header 三項在前，結構三項在後，決定性。
- **T5 的 contract enum 提前到 T2**：不補 `ReadinessIssueView.code` 的三個新值，
  `to_document_readiness_view()` 會在序列化時 `ValidationError`，三個既有 API 測試立刻紅。
  每個 task 必須自己是綠的，所以 enum 跟著 T2 走；T5 只剩 `DutyView`／`DutyWrite` 與
  `DocumentView.duties`。codegen 產物 diff 純新增，既有型別未動。
- web 端補上三個標籤，並測試 header 的「基準級別」與 Task 的「職能級別」標籤**不相同**。
- 施工中一個自我修正：`test_header_issues_come_before_structural_issues` 第一版預期錯了——
  把唯一的 Task 抽離職責，那個職責也就變成空的，`duty_without_task` 本來就該一起報。
  是測試的預期寫錯，不是實作錯。
- 仍**不回** `is_complete`／百分比，仍**不阻止**任何操作；所屬類別仍不發聲（owner 已裁定非必填）。
  另在 docstring 補記工作產出（O）缺席與態度（A）為空都不得機械判成缺漏（ADR 0052 決定 15／16）。
- job_analysis targeted：`665 passed`（+9）。完整 API：**`2111 passed / 0 failed / 0 skipped`**（+9）。
  contract 16 passed；web `109 passed`＋tsc＋lint 全綠。
- 下一個可獨立 task 是 T3（persistence 與 migration 0016），**必須一次補齊九個
  `JobAnalysisState(...)` 建構點的 `current_duties`**。

## 12. T3 執行證據（2026-08-05）

- baseline：完整 API `2111 passed / 0 failed / 0 skipped`。
- **偏離計畫：`jd_tasks.duty_id` 不建 FK，因此也沒有 `ON DELETE SET NULL`。**
  第 1 點原本要求 FK＋`ON DELETE SET NULL`，實作時發現這在本 repo 會反過來造成資料遺失：
  repository 用 delete-then-insert 的 `replace()` 寫整份 duties，加上 `ON DELETE SET NULL` 之後，
  **每一次改任何一條 Duty 都會把所有 Task 的 `duty_id` 清成 `NULL`**——正是本切片要防的那個 bug。
  改採既有 OPKS `task_refs` 的先例：child 關係的參照完整性由 `JobAnalysisState` 守。
  完成條件因此改寫為：
  1. domain 拒絕指向不存在 Duty 的 Task（T1 已有測試），髒資料**讀取時整份 fail-closed**
     ——`test_a_dangling_duty_reference_fails_closed_on_read` 直接用 SQL 寫進 `duty-gone` 驗證；
  2. T4 的 `delete_duty` 必須在**同一交易**把該 Duty 底下 Task 的 `duty_id` 設為 `None`。
     這條是 T4 的驗收項，不是 T3 能代為保證的。
  取捨與理由寫進 migration docstring，日後讀 schema 的人不會誤以為忘了加 FK。
- 級別的 1–6 由 DB CHECK 擋在**寫入端**：原本想寫「存了 9 之後讀取要 fail-closed」的測試，
  結果 `UPDATE ... SET competency_level = 9` 直接被 `ja2_ck_jd_tasks_competency_level` 拒絕，
  根本造不出那個髒狀態。測試因此改成斷言 DB 自己就擋下來——比繞過約束再驗讀取更接近真相。
- 第 4 點的「八個建構點」實際是**九個**：改完之後寫了一支腳本走訪每一個 `JobAnalysisState(`
  呼叫點逐一核對，抓到 `put_jd_header()` 被前面的模式比對漏掉。這正是 header 切片同一類風險，
  靠人眼掃過去會漏。
- 寫入順序：`commit_authority_change()` **先 replace duties 再 replace tasks**，
  同一交易內不會出現「Task 指向已被刪掉的 Duty」的中間狀態；既有的寫入順序斷言一併更新。
- 測試：新增 `tests/test_job_analysis_duty_persistence.py`（7 條，全部跑真 PostgreSQL）——
  往返、canonical 排序在 replace 後仍成立、**既有無 Duty 文件照常載入且不合成假的 T1**、
  員工改表頭不會洗掉 Duty、員工改 Task 不會洗掉 Duty、DB 擋掉越界級別、髒 `duty_id` 讀取拒收。
  `test_job_analysis_migration.py` 補上新表與兩欄的 PK／unique／FK／check 期望。
- job_analysis targeted：`672 passed`（+7）。完整 API：**`2118 passed / 0 failed / 0 skipped`**（+7）。
- 同 commit 更新 `docs/design/task-analysis-engine.md`：T1／T2 只改了 plan 沒改 design doc，
  這次一次補齊 Duty 的 domain 形狀、readiness 的三條結構 issue、0016 與無 FK 的理由、
  authority commit 的寫入順序，以及 transition carry-through 現在也涵蓋 `current_duties`。
- 下一個可獨立 task 是 T4（authoring use cases），其中 `delete_duty` 必須承接上面第 2 點。

## 13. T4 執行證據（2026-08-05）

- baseline：完整 API `2118 passed / 0 failed / 0 skipped`。
- 四支 use case 住 `application/duty_authoring.py`，與 JD Task 那四支同形。
  新增 `DutyDirectEditPayload`／`job-analysis-duty-direct-edit/1`、`DutyNotFound`、
  `DutyNotChanged`、`InvalidDutyOrder`。
- **T3 欠下的保證在這裡補齊**：`delete_duty()` 在同一交易把底下 Task 的 `duty_id` 設回 `None`，
  Task 本身留著。以 mutation check 證明是承重的——把那段 `model_copy` 拿掉，5 條測試變紅。
- **施工中發現一個計畫沒寫、但非做不可的正確性問題**：刪掉職責必須同時把受影響 Task
  仍在等待的 Task Proposal 轉 stale。理由不是整潔——`_apply_jd_entries()` 接受提案時是把
  `jd_after` 的 `JdTask` **整份**寫回 Current JD，而那份快照還帶著剛被刪掉的 `duty_id`。
  不轉 stale 的話，那筆提案會**永遠接受不了**（`JobAnalysisState` 擋下 dangling `duty_id`），
  員工只剩「拒絕」一條路。同樣以 mutation check 鎖定。
- **兩件刻意不做**：Duty 的四支都不動 Work Model（`_reconciled_work_model()` 是標記
  「員工改了 Task 內容、AI 之後要對齊」，而 AI 對職責歸屬從頭到尾沒有權限，標了只是雜訊），
  也不 prune OPKS（O/P/K/S 綁 `task_id`，刪職責不刪 Task；有測試斷言刪前刪後 OPKS 相同）。
- **與 `edit_jd_task` 的一處刻意不一致**：`edit_duty()` 拒絕未改內容（`DutyNotChanged`），
  `edit_jd_task()` 不拒絕。採用 `put_jd_header()` 的理由——空編輯寫一筆 before==after 的
  Journal 又 bump generation，會平白讓別的 client 的 read-set 失效。這裡記下來，免得日後
  被當成漏掉的不一致而「修正」掉。
- `DutyDirectEditPayload.unassigned_task_ids` 只在 delete 出現，且不參與 replay 比對
  （replay 比的是 `duty_id`）。它是 provenance：刪職責是唯一會改到別的列的操作，
  日後回頭讀 Journal 必須能直接答出「那次刪除把哪幾條 Task 變成未指派」。
- 測試：`tests/test_job_analysis_duty_authoring_postgres.py` 19 條，全部跑真 PostgreSQL——
  四支的儲存、同 key replay 不重複生效且不 bump generation、同 key 換內容 conflict、
  **同一個 `entry_id` 不得被 Duty 與 JD Task 兩種 direct edit 各認一次**、未改內容拒絕、
  generation 遞增、刪職責後 Task 仍在且 `duty_id` 為 `None` 但級別留著、
  不相干的 Task 維持指派、提案轉 stale、OPKS 不受影響、reorder 從 0 重編號且不斷開 Task 連結。
- 完整 API：**`2137 passed / 0 failed / 0 skipped`**（+19）。
- 下一個可獨立 task 是 T5（contract 與 route）。註記：`DutyNotChanged` 與 `InvalidDutyOrder`
  需要各自的 problem+json 映射，比照 `JdHeaderNotChanged → 422 invalid-request`。

## 14. T5 執行證據（2026-08-05）

- baseline：完整 API `2137 passed`、contract `16 passed`、web `109 passed`。
- **計畫外但必須做的一項：`ConsultationView` 也要有 `duties`。** 計畫只寫 `DocumentView.duties`，
  但 `ConsultationPanel` 的 Current JD 讀的是 consultation 回應（送出回合、決策提案都回這個形狀），
  不是 document。只加在 `DocumentView` 的話，T6 的職責分組會在每個回合之後對不起來。
- **`toTaskWrite()` 現在就要帶兩個新欄位，不能等 T6。** 這是同一個資料遺失類別：
  `JdTaskWrite` 兩個欄位是必填，少送就等於送 `null`，員工在既有編輯器改一次文字
  就會把職責歸屬與級別洗掉。因此 `TaskFormValue` 先加 `dutyId`／`competencyLevel` 純往返，
  T6 才加下拉；round-trip 測試把這件事鎖起來。
- **兩個新 problem type 必須同時進 contract enum 與 problem 映射。** 只加映射的話
  `ProblemDetail` 會在序列化時 `ValidationError`（實測：兩條測試變紅）；
  `application_error_response()` 對沒映射的錯誤是 `raise TypeError`，所以只加 enum 會變 500。
  兩邊都有測試守（`test_an_unknown_duty_is_404_not_500`）。
- 新增一條機械不變量：`set(JdTaskWrite.model_fields) == set(JdTaskFields.model_fields)`。
  `to_jd_task_fields()` 是逐欄手寫的，漏一欄就是員工存了卻沒生效；兩邊欄位集合相同是這個
  切片才成立的性質（Duty 與級別刻意放進 `JdTaskFields` 而不另開 use case），把它鎖起來。
- codegen 照 `CLAUDE.local.md` 用 Python 3.13；產物是純新增，既有型別未動。
  **`npm run check-codegen` 會再跑一次 codegen，而它在這台機器上會重新寫出 CRLF**——
  跑完要再轉一次 LF，否則 commit 進去的是 CRLF。
- 測試：`test_job_analysis_api_postgres.py` 新增 9 條（建立／排序／投影、缺 `Idempotency-Key`、
  空編輯 422 problem+json、未知 Duty 404、部分順序 422、Task 帶職責與級別且 readiness 跟著變、
  越界級別被契約擋、刪職責後 Task 仍在且未指派、consultation 也投影 duties），
  mapper 新增 1 條。
- 完整 API：**`2147 passed / 0 failed / 0 skipped`**（+10）。contract `16 passed`；
  web `109 passed`＋`tsc --noEmit`＋`lint` 全綠。
- 下一個是 T6（Web 編輯）：`DutyEditor`、Task 的兩個下拉、Current JD 依 Duty 分組且
  未指派 Task 要看得見。

