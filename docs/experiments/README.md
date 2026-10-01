# Caliburn 模型實驗紀錄

本目錄保存會影響顧問 LLM 架構的**小型實證**：實際測試方法、案例、模型可見的完整輸入、模型最終輸出、
評分與限制。它不是通用 eval 平台，也不取代 [research/](../research/README.md) 的研究或 `docs/adr/` 的決策。新目標的逐任務實測沿[計畫證據](../plans/2026-09-29-target-rebuild/evidence/README.md)保存，不為分類再搬一份。

## 1. 與其他文檔的邊界

| 位置 | 回答的問題 |
|---|---|
| `docs/research/` | 外部資料告訴我們什麼？有哪些設計選項與限制？ |
| `docs/specs/`／`docs/architecture/` | 本產品的責任、流程與契約是什麼？有效性由決策入口判定 |
| `docs/experiments/` | 我們實際怎麼測？輸入、輸出與結果是什麼？ |
| `docs/adr/` | owner 最後採納哪個架構決策？ |
| `docs/plans/` | 核准後如何實作？ |

實驗報告可以否定既有假說，但**不會自行改寫架構 authority**。若結果需要更改已 Accepted 的 ADR，
應另開新 ADR。

## 2. 一個實驗目錄至少包含

```text
<date>-<experiment-name>/
├─ README.md       # 問題、假說、arms、方法、停止與採納條件
├─ rubric.md       # 實驗前固定的裁決標準
├─ cases/          # 輸入案例與人工裁決重點
├─ trials/         # 每次受測模型實際看見的 prompt/input 與最終 output
├─ results.csv     # 執行後的逐 trial 摘要
└─ report.md       # 執行後的分析、限制與下一步
```

實驗設計階段可以先只有 `README.md`、`rubric.md` 與 `cases/`／`trials/` 的格式說明；
不得用虛構結果填充 `results.csv` 或 `report.md`。

## 3. 保存規則

- 保存**我們實際送出的可見 prompt/input**與受測模型最終回覆，不聲稱能取得平台隱藏 system
  instructions、私有 reasoning 或完整內部執行軌跡。
- 不要求、不保存 chain-of-thought；需要理由時只保存短而可檢查的 decision rationale。
- 每個 trial 記錄 requested/resolved model、provider/endpoint、reasoning effort、case、arm、執行環境與時間。
- 同一比較中的模型、rubric、輸出格式與非受測條件必須相同。
- 案例與 rubric 在開始跑 trial 前固定；中途修正就升實驗 revision，不能默默改完繼續混算。
- 小型 constructed 實驗可將完整 trial 提交 Git；大量或敏感資料另訂保存規則，不能把秘密或 API key
  放進本目錄。
- 實驗失敗、平手與限制都要保留，不能只提交看起來成功的輸出。

## 4. 實驗清單

- [較早實驗與驗收原件](legacy-evidence/README.md)：原 `specs/evidence/` 歸位；涵蓋當時 JD、UI、Memory、工具與保存的反例和驗證。
- [歷史工作樹的獨有實驗](historical/README.md)：CT 系列、JD 整合初審與修正、R1 方法資產、Agent 任務報告；重複副本不另存。
- [新目標證據](../plans/2026-09-29-target-rebuild/evidence/README.md)：T01–T18 各自的判準、結果與限制，仍由該任務維護。
- [跨校可用的問題分析案例](../reports/research-casebook.md)：給教授與報告讀者的解讀入口，不取代原始結果。

- [`2026-07-26-r1-p0-context-representation/`](2026-07-26-r1-p0-context-representation/) —
  **Closed／不執行**（[ADR 0041](../adr/0041-r1-p0-closure-first-version-context-and-holdout.md)，2026-07-27）。
  原欲比較 Raw-only、Raw+Spans、Hybrid 與 Structured-only 四種 Context 對 Task 邊界分析的影響；
  六份 constructed cases、rubric 與 assembler 已凍結為 revision 1，**零個 trial 曾被執行**。
  原 Codex-subagent 執行法先被停止（平台不允許把 subagent 當外部 API 受測模型），
  其後 owner 裁定不另付真 provider 成本，改以
  [外部權威證據審查](../specs/2026-07-26-professional-consultant-context-representation-external-evidence-review.md)
  收斂為「不建 literal-claim layer」。**該結論的依據是 YAGNI 與外部證據，不是本實驗的結果。**
  frozen 案例、rubric 與 assembler 保留為可重用資產，再使用須另升 revision。

- [`2026-07-27-r1-task-discovery/`](2026-07-27-r1-task-discovery/) —
  ADR 0040 正式 R1 六 arm 快篩的實驗資產。**Segment 1–4 完成**（八案凍結、rubric、契約、
  deterministic verifier、mocked transport、六 arm assembler／runner／blind grader，
  加上一個不使用正式案例的 live plumbing preflight）；
  scripted 48-observation／80-call 骨架已跑通但不具品質結論資格。experiment revision 1，suite hash
  `6c8863863a233830a9216a3ebae46389c91082f097b337c25404400bc93694f7`；
  上述為早期準備狀態；後續 [R1a 結果](2026-07-27-r1-task-discovery/r1a-results.md)已完成八案 × A1／A6／A2 的 24 observations，含兩次中止嘗試與 grader 漏判。A3／A4／A5 未執行；不是六 arm 全跑，也不是 SME 驗證。
  設計 authority 在
  [`2026-07-27-professional-consultant-r1-task-discovery-experiment-design.md`](../specs/2026-07-27-professional-consultant-r1-task-discovery-experiment-design.md)，
  分段見 [實作計畫](../plans/2026-07-27-r1-task-discovery-implementation-plan.md)。
