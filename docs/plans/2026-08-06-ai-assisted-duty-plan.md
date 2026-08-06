# AI 輔助主要職責（暫定職務框架）實作計畫

- 日期：2026-08-06
- 狀態：T1–T5 尚未開工
- 決策：[ADR 0059](../adr/0059-ai-assisted-duty-suggestion.md)（本切片的權威依據）
- 研究：[`2026-08-06-ai-assisted-duty-research.md`](../specs/2026-08-06-ai-assisted-duty-research.md)
- 語意來源：[ADR 0055](../adr/0055-hybrid-job-discovery-and-ttop-formation.md) 決定 2、
  [`2026-08-03-ai-conversational-job-analysis-discovery-route-research.md`](../specs/2026-08-03-ai-conversational-job-analysis-discovery-route-research.md) 步驟 1
- 形狀先例：OPKS 的獨立 operation（[ADR 0049](../adr/0049-opks-derived-axes-evidence-whitelist-and-document-authority.md)）——
  `application/opks_operation.py`、`llm/opks_result.py`、`llm/opks_wire.py`
- 翻案：[Duty 切片](2026-08-05-job-analysis-duty-and-task-competency-level-plan.md) §4「第一版 AI 不參與 Duty」

## 1. 目標

員工在文件早期（甚至還沒開始訪談）可以按一個按鈕，讓 AI 依 `title` 與
`JdHeader.work_description` 提出一組**候選主要職責**；員工逐條勾選採用，勾選即建立真正的 Duty。

**這條路徑完全可略過** —— 空手建 Duty、先訪談後建 Duty 都必須照常可行（ADR 0059 決定 9）。

本輪前 baseline：完整 API `2147 passed / 0 failed / 0 skipped`、web `117 passed`。

## 2. 範圍

做：獨立的 duty-suggestion operation（wire schema、prompt、provider 呼叫、verifier）、
一條 route、Web 候選清單 UI。

不做（ADR 0059 已排除）：從穩定 Task 歸納 Duty、reference／indexer 接入、
第三種 Proposal、候選出處落庫、候選品質評估方法。

**明確不動**：`task_analysis_result_v2`、其 Static Instructions、`Duty` domain 型別、
`JobAnalysisState`、任何 migration。本切片**零 schema 變更、零 migration**。

## 3. 形狀

```
llm/duty_suggestion_result.py   DutySuggestionResult（內部）
llm/duty_suggestion_wire.py     duty_suggestion_v1（model-facing，維持輕量）
llm/duty_suggestion_prompt.py   Static Instructions
application/duty_suggestion_context.py   DutySuggestionPacket ＋ 決定性 render
application/duty_suggestion_operation.py run_duty_suggestion_operation()
```

wire schema 刻意**極小**（ADR 0048 決定 10：model-facing wire schema 維持輕量，
ExtractBench 顯示綁定變數是單次輸出總量）：

```
{ "duties": [ { "statement": str } ] }
```

**沒有** `duty_id`（application 配發）、**沒有** `display_order`（勾選時才決定）、
**沒有** confidence／rationale 欄位（ADR 0042 決定 7：只加可機械檢查或能診斷核心錯誤的欄位；
兩者皆非）。

## 4. Task 切片（一個 task 一個 commit，綠了才 commit）

### T1 — wire、內部型別與 prompt

1. `llm/duty_suggestion_result.py`：`DutySuggestionResult`（frozen，`duties: tuple[NonEmptyText, ...]`）。
2. `llm/duty_suggestion_wire.py`：`duty_suggestion_v1` wire 型別、portable schema 產生器、
   `duty_suggestion_wire_to_result()`——**中性值還原為拒絕而非靜默丟棄**（比照 `llm/wire.py` 的既有慣例）。
3. `llm/duty_suggestion_prompt.py`：Static Instructions。內容要點：
   - 產出**主要職責**（動詞＋受詞＋條件），不是工作任務、不是工作活動
   - 官方建議兩層為主，**不得往下展開任務**
   - 粒度盡量一致、跨公司共通（2022 指引 p46）
   - **只依據提供的職稱與工作描述**；不得虛構具體系統、部門或人名
   - **不得產生任何代碼**（`職能基準代碼`／`職類別代碼`／`T1`）
4. 測試：wire → 內部型別的還原、空清單合法、夾帶未知欄位被拒。

完成條件：`test_job_analysis_dependencies.py` AST guard 仍綠；**`task_analysis_result_v2` 檔案零改動**
（測試可直接斷言該模組的 `model_fields` 未變）。

### T2 — context packet 與 operation

1. `application/duty_suggestion_context.py`：`DutySuggestionPacket`（`title`、`work_description`、
   **既有 Duty 敘述清單**）＋決定性 render。
   帶入既有 Duty 是為了讓模型**避免重複建議已經有的職責**——同 `build_opks_context_packet()`
   帶入既有 K/S 的理由（ADR 0048 決定 9）。
2. `application/duty_suggestion_operation.py`：`run_duty_suggestion_operation()`，
   一次 HTTP、無 retry、沿用 `OperationOutcome`（比照 `run_opks_operation()`）。
3. verifier（可併在 operation 內，規模不值得另開檔）：
   - 敘述非空、去除前後空白後仍非空
   - **與既有 Duty 逐字重複者剔除**（機械可檢查）
   - **含 `T\d` 形狀位置碼者剔除**（ADR 0052 決定 10：位置碼不是 identity，模型不該產）
   - 上限一個合理條數（避免單次輸出量爆掉，ADR 0048 決定 10）
4. 測試：用 scripted transport（比照既有 API 測試的 `_ConsultantTransport`），
   驗證重複剔除、位置碼剔除、空結果的 outcome。

完成條件：不呼叫真 provider；scripted 測試綠。

### T3 — route

1. `POST /{document_id}/duty-suggestions`，回一組候選敘述（純讀取語意，但因為會呼叫付費 provider，
   **仍要求 `Idempotency-Key`**，比照既有 OPKS generation route 的作法）。
2. **不寫任何 authority 狀態、不寫 Journal、不 bump generation** —— 候選在被接受前不是文件的一部分
   （ADR 0059 決定 4）。
3. contract：新增 `DutySuggestionView`（`duties: string[]`）。codegen 照 `CLAUDE.local.md` 用
   Python 3.13，**產物跑完轉回 LF**（`check-codegen` 會再跑一次並重新寫出 CRLF）。
4. provider 失敗沿用既有 `consultant_unavailable_response()` → 503。
5. 測試：200 正常路徑、未知文件 404、缺 `Idempotency-Key` 422、provider 失敗 503、
   **呼叫後 `authority_generation` 不變**（決定 4 的迴歸測試）。

### T4 — Web 候選清單

1. `DutyEditor.tsx` 加一顆「AI 建議職責」按鈕與候選清單區。
2. 候選以 checkbox 呈現，**明確標示為 AI 建議**（ADR 0059 決定 11），
   措辭需讓員工看得出「這不是你說過的話」。
3. 勾選後按「加入」→ 逐條呼叫既有 `addDuty()`（每條各自的 `Idempotency-Key`）。
4. **候選區可整批關閉／忽略**，不擋任何既有操作（決定 9）。
5. 可抽出的純邏輯（候選過濾、已存在判斷）放 `src/lib/` 才有 vitest 覆蓋。
6. web 三件套＋`npm run build`。

完成條件：**本切片沒有真人瀏覽器驗證**（比照 Duty T6、匯出切片的坦白）；
要驗證需重啟本機 dev server，動手前先問。

### T5 — 文檔同步（併在各 commit）

`docs/design/task-analysis-engine.md` §2 補新 operation 一列，並在 Duty 那一列補上
「AI 只提候選、員工勾選才成立」；本檔執行證據。

## 5. 一次付費 live 驗證（T1–T4 綠之後，需 owner 事前授權）

scripted transport 不回答「真模型建議的職責品質如何」。收尾建議做一次**有預算上限**的
live smoke，比照 header 切片的 `docs/experiments/2026-08-05-jd-header-packet-live-verification/`：

- 固定 2–3 個職稱＋工作描述
- 檢查：是否為主要職責層級（不是任務）、粒度是否一致、有無虛構具體系統／部門、有無產生代碼
- **不得**用來宣稱「AI 建議 Duty 對員工有幫助」——那要 R9 真人 pilot 才答得出來（ADR 0056）

## 6. 開放問題（不擋 T1–T5）

- 候選出處（來自哪個官方基準）要不要保留給員工看？第一版不接 reference 所以不存在，
  接了之後 `Duty` 型別沒有欄位放它，會需要 migration（ADR 0059 後果已標註）。
- 被忽略的候選要不要留下紀錄以評估建議品質？選項 A 目前不留（ADR 0059 後果已標註）。
- 什麼時候該做 (ii) 從穩定 Task 歸納 Duty？依 ADR 0059 決定 1，等 R9 pilot 的實際資料。
