# Caliburn 模型實驗紀錄

本目錄保存會影響顧問 LLM 架構的**小型實證**：實際測試方法、案例、模型可見的完整輸入、模型最終輸出、
評分與限制。它不是通用 eval 平台，也不取代 `docs/specs/` 的研究或 `docs/adr/` 的決策。

## 1. 與其他文檔的邊界

| 位置 | 回答的問題 |
|---|---|
| `docs/specs/` | 權威資料與理論告訴我們什麼？有哪些設計選項？ |
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

- 保存**我們實際送出的可見 prompt/input**與 subagent 最終回覆，不聲稱能取得平台隱藏 system
  instructions、私有 reasoning 或完整內部執行軌跡。
- 不要求、不保存 chain-of-thought；需要理由時只保存短而可檢查的 decision rationale。
- 每個 trial 記錄 requested model、reasoning effort、`fork_context`、case、arm 與時間。
- 同一比較中的模型、rubric、輸出格式與非受測條件必須相同。
- 案例與 rubric 在開始跑 trial 前固定；中途修正就升實驗 revision，不能默默改完繼續混算。
- 小型 constructed 實驗可將完整 trial 提交 Git；大量或敏感資料另訂保存規則，不能把秘密或 API key
  放進本目錄。
- 實驗失敗、平手與限制都要保留，不能只提交看起來成功的輸出。

## 4. 現行實驗

- [`2026-07-26-r1-p0-context-representation/`](2026-07-26-r1-p0-context-representation/) —
  在不使用外部 API key 的情況下，以隔離 Codex subagent 快篩 Raw-only、Structured-only 與 Hybrid
  Context 對 Task 邊界分析的影響。
