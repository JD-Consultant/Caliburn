# O/P/K/S/A 員工可控排序（匯出前置切片 A）實作計畫

- 日期：2026-08-06
- 狀態：T1–T6 COMPLETE
- 決策：[ADR 0058](../adr/0058-jd-deterministic-export-shape-and-format.md) 決定 5
- 研究：[`2026-08-06-jd-deterministic-export-research.md`](../specs/2026-08-06-jd-deterministic-export-research.md) §4
- 掛載形狀依據：[ADR 0048](../adr/0048-opks-evidence-axes-and-document-level-competencies.md) 決定 5–7
  （O/P 掛 Task、K/S/A 掛文件，依官方編號）
- 後續切片：[JD deterministic export](2026-08-06-jd-deterministic-export-plan.md)（切片 B，**依賴本切片**）
- 先例：[Duty 與 Task 職能級別](2026-08-05-job-analysis-duty-and-task-competency-level-plan.md)（T1–T6 完成）

## 1. 為什麼這是匯出的前置條件

匯出的 `O1.1.1`／`P1.1.1`／`K01`／`S01`／`A01` 位置碼**由排序推出**。目前 `OpksItem`
**沒有 `display_order`**，`SqlAlchemyOpksRepository.list()` 讀出順序是
`(created_at, entity_id)`——決定性、跨次讀取穩定，但**員工無法調整**。

`Duty` 與 `JdTask` 都有 `display_order` 與 Web 上下移按鈕；O/P/K/S/A 沒有。這個不對稱沒有理由，
而且**先出匯出再改排序，會讓已經交付給主管／HR 的文件編號改變**。因此排序必須先做完。

本輪前 baseline：完整 API `2147 passed / 0 failed / 0 skipped`、web `117 passed`＋tsc＋lint＋
`next build` 全綠。

## 2. 形狀

`OpksItem` 增一個欄位：

```
display_order: int >= 0    # 在 (document_id, entity_kind) 範圍內唯一
```

**唯一性範圍是 `(document_id, entity_kind)`，不是 `(document_id, task_id, entity_kind)`。**
理由是沿用 Duty／Task 的既有先例：`JdTask.display_order` 是**文件層**唯一，而 `T{i}.{j}` 的 `{j}`
在 Duty 內重新從 1 編號。同理，OUTPUT 的 `display_order` 在整份文件的 OUTPUT 之間唯一，
而 `O{i}.{j}.{k}` 的 `{k}` 在該 Task 的 OUTPUT 之間重新從 1 編號。這讓 DB 約束簡單
（一條 unique constraint），也不必在 Task 之間搬動時重編號。

K/S/A 本來就是文件層，範圍一致，無額外處理。

## 3. Task 切片（一個 task 一個 commit，綠了才 commit）

### T1 — domain

1. `domain/opks.py`：`OpksItem` 增 `display_order: int = Field(ge=0)`。
2. `CurrentJdOpks` 增驗證：同一 `entity_kind` 內 `display_order` 唯一、且 tuple 本身依
   `(entity_kind, display_order)` canonical 排序（比照 `JobAnalysisState._validate_duties()`）。
3. 測試：唯一性、canonical 排序、跨 kind 可重複（OUTPUT 的 0 與 KNOWLEDGE 的 0 並存合法）。

完成條件：非法狀態無法被建構；`test_job_analysis_dependencies.py` AST guard 仍綠。

### T2 — migration 0017

1. `alembic/versions/0017_*.py`：`job_analysis_opks_items` 增 `display_order`（BigInteger）。
2. **回填以現行讀取順序為準**：依 `(document_id, entity_kind)` 分組，按 `(created_at, entity_id)`
   由 0 起編號——**回填後的呈現順序與現況逐項相同**，既有文件不會因為這次 migration 改變外觀。
3. 回填後設 NOT NULL，加 `UNIQUE (document_id, entity_kind, display_order)` 與
   `CHECK (display_order >= 0)`。
4. 測試：`test_job_analysis_migration.py` 補新欄位／約束期望；另一條測試驗證**回填順序等於
   migration 前的讀取順序**（這是本 task 唯一有資料遺失風險的地方）。

完成條件：真 PostgreSQL migration 綠；既有文件的 OPKS 呈現順序不變。

### T3 — persistence

1. `adapters/job_analysis_postgres/`：ORM 欄位、`load_opks_item`、`replace` 寫入 `display_order`；
   `list()` 的 `order_by` 從 `(created_at, entity_id)` 改成 `(entity_kind, display_order)`。
2. **檢查每一個建構 `CurrentJdOpks`／`OpksItem` 的地方**都帶了 `display_order`——
   比照 Duty 切片 T3 的教訓（模式比對會漏掉呼叫點，**寫腳本走訪每一個建構點逐一核對**，
   那次就是這樣抓到 `put_jd_header()`）。
3. 新增 OPKS item 時 `display_order` 取該 kind 現有最大值 +1（比照 `add_jd_task`）。
4. 測試：往返、既有文件載入、**AI 回合與 proposal 決策不改變既有項目的 `display_order`**
   （比照 header／Duty 的 mutation check）。

完成條件：真 PostgreSQL 測試綠。

### T4 — reorder use case 與 route

1. `application/opks_authoring.py`（或同層新檔）：`reorder_opks_items(*, document_id, entry_id,
   entity_kind, ordered_entity_ids)`，走 document lock → entry replay → `commit_authority_change()`。
   驗證 `ordered_entity_ids` 互異且**恰好涵蓋該 kind 的全部項目**（比照 `reorder_jd_tasks`）。
2. 錯誤：`InvalidOpksOrder`（422），需同時進 problem 映射與 contract 的 `ProblemDetail.type` enum
   ——**兩邊都要**，只加一邊就是 500 或序列化炸掉（Duty T5 的教訓）。
3. contract：`OpksItemView` 增 `display_order`；新增 `OpksOrderWrite`
   （`entity_kind` ＋ `ordered_entity_ids`）。codegen 照 `CLAUDE.local.md` 用 Python 3.13，
   **產物跑完要轉回 LF**（`check-codegen` 會再跑一次 codegen 並重新寫出 CRLF）。
4. route：`PUT /{document_id}/opks-order`，要求 `Idempotency-Key`。
5. 測試：儲存、replay 同 key、換內容 conflict、部分順序 422、generation 遞增。

完成條件：真 PostgreSQL route 測試綠。

### T5 — Web 上下移

1. `OpksEditor.tsx`：每個 O/P/K/S/A 項目加上下移按鈕，沿用 `TaskEditor`／`DutyEditor` 的
   失敗重試沿用同一把 key 的慣例。
2. **移動範圍是同一個 `entity_kind` 內**（O 只跟 O 換位置，不會跟 P 混）。
3. 排序邏輯若有可抽出的純函式，放 `src/lib/`——本 repo 的 vitest 只跑 `src/lib`，
   寫在 component 裡就沒有測試覆蓋（Duty T6 的教訓）。
4. web 三件套＋`npm run build`。

### T6 — 文檔同步（併在各 commit）

`docs/design/task-analysis-engine.md` 的 OPKS 與 persistence 段落；本檔執行證據。

## 4. 開放問題（不擋 T1–T6）

- 匯出時 K/S 要不要依「第一個引用它的 Task」再分組呈現？ADR 0048 決定 7 說「匯出時不必複製 K/S
  ——公版表格本來就是文件層編號」，所以第一版按文件層平坦列出即可；分組屬 UI 投影，不是匯出需求。

## 5. 執行證據（2026-08-06）

- baseline：完整 API `2147 passed`、web `117 passed`。

### 計畫的 task 切分有一處不可行，已合併

T1（domain）／T2（migration）／T3（persistence）**綠不起來**：對一個**已經持久化**的型別加
**必填**欄位，domain 一改 serialization 就少一個欄位可填，直到 migration 加上欄位為止。
Duty 切片沒遇到是因為 `Duty` 是全新型別、沒有既有列。三者合併成一個 commit——
「綠了才 commit」是硬規則，「bite-size」是準則。

### 施工中抓到兩個真的 bug

1. **`_apply_item()` 會讓第二筆被接受的提案撞號。** 它把候選原樣接進 Current JD，
   包含佔位的 `display_order`；而一次 operation 產出多筆 add 提案是常態。這與
   `_apply_jd_entries()` 早就記錄過的 JdTask 問題是**同一條理由**（該 docstring 寫著
   「提案帶的那個值不能照抄」）。改成接受當下才配位置、REVISE 保留原位。
2. **`add_opks_item()` 的重播比對會誤判。** 它在讀 state 之前就建好 `expected` 並整個比對；
   `display_order` 一旦來自 state，同一把 key 重播時清單可能已變，合法重播會被誤判成
   `IdempotencyConflict`。改成比對**不含位置**的內容指紋——即 `add_jd_task` 只比
   `JdTaskFields` 的既有作法。

### 一處刻意沒做：`CurrentJdOpks` 的 canonical tuple 排序

T1 第 2 點原本要求「同 kind 內唯一**且 tuple 本身依 `(entity_kind, display_order)` canonical 排序**」。
**只做了唯一性，沒做 canonical 排序**，理由：

- `current_duties[0]` 就是 `T1`，順序有單一意義，所以 Duty 值得要求 canonical；
  但 `current_opks.items` 混了五種 kind，`items[0]` **沒有任何意義**，要求排序買不到對應的保證。
- 位置碼的正確性由**匯出端明確排序**保證（切片 B 會有測試守），而不是靠 tuple 順序——
  依賴 tuple 順序反而更脆弱。
- 代價是要求所有測試的 tuple 必須按 kind 分組，churn 不小卻擋不到真的 bug。

唯一性是承重的（同 kind 撞號就算不出唯一的 `O1.1.1`），canonical 排序不是。

### 兩處結構調整

- `next_display_order` 本來想放 application，但 `opks_authoring` 已經 import
  `opks_proposals`，放哪一邊都循環。搬進 `CurrentJdOpks` 當 method——「這個 kind 的下一個位置」
  本來就是集合自己的問題。
- `OpksDirectEditPayload` 多了第四種 action。reorder 不帶 item 快照而帶
  `entity_kind`＋`ordered_entity_ids`，validator 改成**雙向拒絕**（reorder 不得帶快照、
  其餘三種不得帶 reorder 欄位），否則會出現「delete 帶著 ordered_entity_ids」這種無意義記錄。

### migration 0017 唯一的資料風險已鎖住

回填嚴格照 migration 前的 `(created_at, entity_id)` 讀取順序。
`test_job_analysis_opks_backfill.py` 塞入順序刻意與 `created_at` 順序不同，
斷言每個 kind 的相對順序不變、且各自從 0 連續編號。

### Web

分區顯示與文件層排序之間的落差由 `kindOrderAfterMove()` 這支純函式承接：畫面按 Task 分區，
但 `display_order` 是文件層 per-kind，所以**相鄰以看得見的子集合為準、交換發生在完整清單上**。
放 `src/lib/` 是因為本 repo 的 vitest 只跑 `src/lib`（Duty T6 的教訓）。有測試守
「不會弄丟或重複任何 id」與「不在可見區塊內的 id 回 null」。

### 數字

- domain＋migration＋persistence：完整 API **`2148 passed`**（+1）。
- T4 reorder use case＋route＋contract：完整 API **`2158 passed`**（+10）、contract 16、
  web 117＋tsc＋lint。
- T5 Web：web **`122 passed`**（+5）＋tsc＋lint＋`npm run build` 全綠。
- **本切片沒有真人瀏覽器驗證**（比照 Duty T6 的坦白）；要驗證需重啟本機 dev server，動手前先問。

下一個是切片 B（匯出）。

