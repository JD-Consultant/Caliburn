# 行為指標判準修正與缺漏檢查涵蓋 O/P/K/S 實作計畫

- 日期：2026-08-07
- 狀態：**未開工**
- 決策：[ADR 0060](../adr/0060-enterprise-jd-indicator-depth-and-icap-reference.md)
  決定 1–6（判準修正）、決定 19–23（缺漏檢查與進度）
- 研究：[`2026-08-07-behavioral-indicator-depth-and-icap-reference-flow-research.md`](../specs/2026-08-07-behavioral-indicator-depth-and-icap-reference-flow-research.md)
  §2（iCAP 全量統計）、§3（三個缺陷診斷）
- 先例：[JD header 與 readiness 切片](2026-08-04-job-analysis-jd-header-and-readiness-slice-plan.md)、
  [Duty 與 Task 職能級別](2026-08-05-job-analysis-duty-and-task-competency-level-plan.md)
- 後續切片（**不在本計畫**）：iCAP 配對、`evidence_origin: reference`、逐項任務子對話

## 1. 為什麼這兩塊先做

兩者都**不依賴任何新基礎設施**：沒有 migration、沒有新 route、不接 indexer、不動 domain 型別
（readiness 只加規則，`ReadinessIssueCode` 是 enum 擴充不是形狀改變）。

而它們合起來就能讓 owner 在瀏覽器上看到這輪最在意的兩件事：
**任務名稱變短、行為指標變具體**，以及**指標缺漏會被看見**。

ADR 0060 決定 23 的訪談進度也由切片 B 順帶完成——進度是既有資料的投影，
`assess_readiness()` 涵蓋 O/P/K/S 之後就有資料可投影，不需要另建狀態機。

## 2. Baseline

2026-08-07 實測：`tests/test_job_analysis_prompt.py`、`test_job_analysis_opks_prompt.py`、
`test_job_analysis_readiness.py` 合計 **49 passed**。

動工前另需確認完整 `uv run pytest`、web `npm run test` ＋ `npx tsc --noEmit` ＋ `npm run lint` 綠，
並記錄數字——**green-before == green-after** 以那組數字為準。

## 3. 這兩支 prompt 的既有安全網（動手前必讀）

`test_job_analysis_prompt.py` 不是普通測試，它是 characterization net：

```python
INSTRUCTIONS_BYTES_BUDGET = 5300          # 目前實測 5,215
JUDGEMENT_SECTIONS = {                     # 逐段位元組數，一字不差
    "顧問訪談方式": 963,
    "Task 成立條件(四項同時滿足)": 658,
    "Enabler 硬規則": 370,
    "Split 與 Merge(任一條成立就檢查,不是自動執行)": 834,
    "不成立的訊號怎麼放": 833,
}
```

該檔案註解明寫：「**這些數字改變就是判準被動到了。**只有在確實要改判準文字時才更新，
而且要在同一個 commit 說明改了什麼、為什麼。」

**本計畫正是「確實要改判準」的情況**，所以更新這些數字是預期行為——但每一次更新都要在
commit message 說明動了哪一段、為什麼。**不得為了讓測試變綠而順手調數字**：
只有 T2 允許動 `Task 成立條件`，其餘四段的數字若變動，代表改錯地方了。

## 4. 切片 A：三個 prompt 判準修正

### T1 — `opks_prompt.py`：行為指標定義與技能寫法

現況（兩處錯誤，見研究 §3.1／§3.3）：

```
- 行為指標：能從工作行為或結果判斷是否做好；不得自行補數字…
- 技能：完成工作必要的可操作技術，以具體工作行為表達；不要寫成『具備……之能力』
```

改動：

1. **行為指標改為行為描述語意**（ADR 0060 決定 1–2）：是「這項任務具體要做哪些事」，
   可帶質性條件（依據什麼、為了確保什麼），**不是判斷做得好不好的判準**。
   企業內部版要求時機、來源、方法、產出形式；**「How much」不納入**——
   數量／頻率／達成率屬績效考核層。既有的「不得自行補數字」「不得自行補『依公司規定』」
   兩句**保留**（ADR 0048 決定 20 仍然有效，測試也在斷言它們）。
2. **技能改為名詞化能力／技巧**（決定 4）：官方寫法是 `資料分析能力`、`訪談技巧`；
   移除「以具體工作行為表達」（會產出 `操作資料分析工具`）。
   禁止的是冗贅句式 `具備……之能力`，不是「能力」一詞——這兩者不可混為一談。
3. **知識維持名詞**、**K/S 維持抽象層**（決定 5）：具體工具留在行為指標裡，
   K/S 寫抽象才能跨任務重用（官方 `S02 資料分析能力` 跨 4 項任務）。
4. 不新增章節、不擴充第一版範圍——`test_prompt_does_not_expand_the_first_slice_scope`
   的六個禁字（`attitude`／`taxonomy`／`proficiency`／`external code`／`匯出編碼`／`職能基準代碼`）
   必須維持不出現。

測試：

- `test_job_analysis_opks_prompt.py` 的 `test_prompt_is_behavior_first_grounded_and_allows_abstention`
  斷言片語清單，其中「行為指標」「不得自行補數字」等仍應存在；
  **新增斷言**：不得出現「判斷是否做好」這類判準語意，且技能段不得出現「以具體工作行為表達」。
- 三個既有測試維持綠。

完成條件：OPKS prompt 不再把行為指標定義成品質判準；技能寫法與公版一致。

### T2 — `prompt.py`：Task statement 寫法與成立判準分離

現況（研究 §3.2）：成立條件第一句「可寫成 `action + object (+ purpose/result)` 的單句」
同時被當成判準與 statement 寫法，模型照著寫出 20–30 字長句。

改動（**只動「Task 成立條件」這一段**）：

1. **成立判準不變**（四項同時滿足的語意一字不動）。
2. **加上 statement 寫法**：寫成名詞短語；具體行為留給行為指標、產出物留給工作產出。
   官方中位數 8 字、71% ≤10 字——**寫進 prompt 的是「名詞短語」這個形狀要求，
   不是字數上限**（硬性字數會讓模型截斷語意）。
3. **不得寫入「25 字」之類的 P 目標值**（ADR 0060 決定 3a）：企業內部版的行為指標
   本來就該比公版長，把公版數字當目標會讓深度落空。

測試：

- 更新 `JUDGEMENT_SECTIONS["Task 成立條件(四項同時滿足)"]` 為新的實測 byte 數，
  **其餘四段不得變動**。
- `INSTRUCTIONS_BYTES_BUDGET` 目前 5,300、實測 5,215，餘裕 85 bytes。
  本次新增文字若超出，**上調預算並在該常數的註解說明原因**（沿用 2026-08-05 T5 的既有慣例，
  該處已有一次上調的先例與寫法）。
- 新增斷言：成立條件段落同時含有判準與「名詞短語」的寫法要求。

完成條件：判準與寫法在 prompt 中是可分辨的兩件事。

### T3 — 生產模型複驗（**gate，需 owner 授權付費**）

ADR 0060 決定 6：T1／T2 屬 ADR 0042 分界的「判斷層」改動，
**在 Luna-Pro 上驗過只算「未在生產模型上驗過」**。

1. 用 `scripts/job_analysis_live_smoke.py` 的既有邊界（硬上限 3 次 generation call、
   US$0.75、零 retry）在 **Opus 5 或 Sonnet 5** 上跑一輪。
2. 觀察項（這次改動的具體目標，不是泛泛的「品質有沒有變好」）：
   - 產出的 Task `statement` 是否為名詞短語，而非 20–30 字長句；
   - 行為指標是否為行為描述，而非「達成率」「是否做好」這類判準；
   - 行為指標是否**未**出現員工沒說過的數值；
   - 技能是否寫成 `XX能力`／`XX技巧`，而非動作句。
3. 紀錄寫 `docs/experiments/`，比照
   [`2026-08-05-jd-header-packet-live-verification/`](../experiments/2026-08-05-jd-header-packet-live-verification/README.md)。

完成條件：有一份可追溯的 live 紀錄。**未跑完此 gate 不得宣稱切片 A 完成**，
但 T1／T2 可以先合併——它們本身是綠的。

## 5. 切片 B：缺漏檢查涵蓋 O/P/K/S

### 形狀改變：`assess_readiness()` 需要 OPKS

現行簽章只有 `header`／`duties`／`tasks`，**看不到 O/P/K/S**，所以無法判斷指標缺漏。

```python
def assess_readiness(*, header, duties, tasks, opks) -> DocumentReadiness
```

新參數**必填 keyword、無預設值**——沿用該函式 docstring 已寫明的理由：
漏傳會是 `TypeError`，不會變成「這份文件沒有缺漏」這種安靜的錯答案。

呼叫點共兩處 production ＋ 測試：

| 位置 | 用途 |
|---|---|
| `app/api/job_analysis_mapper.py:294` | `GET /{document_id}` 的 `readiness` |
| `app/api/routes/job_analysis.py:196` | 匯出的第二張工作表 |
| `tests/test_job_analysis_export_xlsx.py:58` | 匯出測試 |
| `tests/test_job_analysis_readiness.py`（271 行） | 全部呼叫點要補 `opks=` |

### T4 — contract 先加 issue codes

**必須先於 T5**：`ReadinessIssueView.code` 是 enum，contract 沒有新值時，
mapper 一產生新 code 就是 validation error。先加 enum、還沒有人產生它，一切維持綠。

1. `packages/job-analysis-contract/schema/job-analysis-workspace.schema.json`
   的 `ReadinessIssueView.code.enum` 增兩個值（命名比照既有風格，例如
   `task_indicator_missing`／`task_competency_missing`）。
2. 跑 codegen 產生 `models.py` 與 TS，**確認產物換行為 LF**後再 commit
   （產物換行不一致會讓 `check-codegen.mjs` 的 `git diff --exit-code` 誤判為有 diff）。
3. `npm run check-codegen` 綠。

完成條件：contract 有新 enum 值，全測試維持綠（此時尚無人產生新 code）。

### T5 — `readiness.py` 兩條新規則

1. `ReadinessIssueCode` 增兩個成員，與 T4 的 enum 值一致。
2. 簽章增 `opks` 參數；兩處 production 呼叫點與測試同步。
3. 規則：
   - **任務沒有任何行為指標** → 一則 issue；
   - **任務沒有連到任何知識或技能** → 一則 issue。
   沿用既有慣例：**一個 code 一則，不是一個 Task 一則**（ADR 0053 決定 6，
   readiness 是提示不是待辦清單）。
4. **不得新增「任務沒有工作產出」規則**（ADR 0060 決定 20）：
   21.8% 的官方任務本來就沒有 O。`readiness.py` 的 docstring 已有一段列出刻意不發聲的欄位，
   工作產出就在其中——**該段不得刪改**，並補上這次的量化依據。
5. docstring 補記：K/S 規則比官方嚴格約 4%（3.9% 官方任務無 K、4.0% 無 S），
   這是刻意取捨，不得寫成「官方每項任務都有 K/S」。

測試：

- 新增：有指標／無指標、有 K 無 S、K/S 皆無、無任務時不發聲、
  **有任務但無工作產出時不得產生 issue**（這條是防止未來有人「順手補齊」的迴歸鎖）。
- 既有 271 行測試補 `opks=` 參數後維持綠。

完成條件：缺漏檢查看得見 P 與 K/S，看不見 O。

### T6 — Web 呈現

1. `apps/web/src/lib/jobAnalysisHeader.ts` 的 `READINESS_FIELD_LABELS` 補兩個中文標籤。
2. `ReadinessNotice` **不需要改**——它只呈現 API 回來的 issues、不自行重算
   （ADR 0052 決定 3）。措辭仍是「iCAP 版型欄位尚有 X 項未填」。
3. 確認零 issue 時仍然不渲染任何東西（沒有綠色「完成」，ADR 0053 決定 6）。

測試：web `npm run test` ＋ `npx tsc --noEmit` ＋ `npm run lint` 綠。

完成條件：員工在 `/workspace` 看得到指標與 K/S 的缺漏提示。

## 6. 不在本計畫

- iCAP 配對、待訪談清單、`evidence_origin: reference`、已退場職類過濾（ADR 0060 決定 7–18）。
- 逐項任務子對話與 Duty 歸納（ADR 0061 全部）。
- **「寫了一條但很粗略」的品質判定**——ADR 0060 決定 21 明示不設條數門檻，
  真正的防線是訪談追問（ADR 0061 決定 5），不是 `assess_readiness()`。
- 訪談進度的 UI 呈現：資料由 T5 產生，畫面留給子對話切片一併處理。

## 7. 收尾

一個 task 一個 commit，綠了才 commit。切片 A（T1–T2）與切片 B（T4–T6）彼此獨立，
可任一先行；T3 是切片 A 的 gate，需 owner 授權付費 run。

全部完成後打 git tag，並更新
[`docs/design/task-analysis-engine.md`](../design/task-analysis-engine.md)
——它是這條線的 living 文檔，prompt 判準與 readiness 範圍都在其涵蓋範圍內
（AGENTS.md：動到那條線的碼，同 commit 更新該文檔）。
