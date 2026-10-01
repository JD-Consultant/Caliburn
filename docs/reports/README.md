# 報告與研究材料入口

本頁整理供教授評閱、推甄與專題報告使用的材料，包括產品介紹、架構解說、開發沿革與實驗證據。產品規格由原設計文件維護，任務狀態見[任務表](../plans/2026-09-29-target-rebuild/tasks.md)；歷史實驗須依當時的版本與範圍解讀。

外部官方資料與論文比較見[研究分類](../research/README.md)，工作分析方法見[指南入口](../guides/README.md)。報告說明問題、取捨與成果；研究支援設計，實驗才提供實測證據，三者不互相替代。

若要查找開發素材，可從[開發演進的 11 個面向](development-history/README.md#按問題找素材)開始。索引由 3 月的前身專案追起，分成產品、檢索、Memory、JD、工程五份沿革，涵蓋資料解析、工作分析、Prompt／Tool、UI／PDF、安全恢復、評測與交付。摘要連回原件，保留失敗、未採用及後來更改的方案，不另存一份實驗結果。

| 查找目的 | 入口 |
|---|---|
| 依時間和問題看整個演進 | [分類索引](development-history/README.md) |
| 從研究能力挑材料 | [公開能力判準](admissions/research-readiness.md) → [按能力查證據](development-history/evidence-by-capability.md) |
| 文件沒展開，想看實際程式如何改 | [前後程式與測試](development-history/code-evolution.md) |
| 需要較完整的案例寫法 | [四個案例摘要](research-casebook.md)，不是全部發展史 |
| 準備實際送件 | [備審準備](admissions/README.md)，另外確認本人、他人與AI的貢獻分界 |

## 介紹產品與程式設計

| 要說明什麼 | 閱讀入口 |
|---|---|
| 問題、使用者與產品價值 | [產品專題介紹](../product-introduction.md) |
| 程式分工、Context、Memory、引用與恢復 | [教授版架構報告](system-architecture/README.md)，先看其程式基準與限制 |
| 上台展示流程與架構 | [圖稿目錄](system-architecture/diagrams/README.md)，保留 PNG、SVG 與 Mermaid 原始檔 |

## 說明如何發現問題並驗證改善

| 主題 | 經過與解讀 | 可核對的原始材料 |
|---|---|---|
| 實驗發現了什麼問題（缺口、已修正、環境事故；不含解法） | [實驗發現的問題彙整](experiment-findings.md) | 各項直接連到原證據頁與資料包 |
| 訪談分析品質、Prompt 比較與來源漏選 | [T14 品質紀錄](../plans/2026-09-29-target-rebuild/evidence/t14-job-analysis-quality.md) | [訪談指引比較資料包](../plans/2026-09-29-target-rebuild/evidence/data/instruction-experiments-2026-10-01/README.md) |
| 長訪談、程序事故、恢復與 PDF | [T17 旅程紀錄](../plans/2026-09-29-target-rebuild/evidence/t17-course-administrator-journey.md) | 同一[長旅程資料包](../plans/2026-09-29-target-rebuild/evidence/data/instruction-experiments-2026-10-01/README.md)的逐字稿、事件與成品 |
| 原生接續、容量與來源工具探測 | [T16 接續紀錄](../plans/2026-09-29-target-rebuild/evidence/t16-compaction-continuity.md)及[證據分類](../plans/2026-09-29-target-rebuild/evidence/README.md) | [執行與品質探測原件](../plans/2026-09-29-target-rebuild/evidence/data/runtime-probes-2026-10-01/README.md) |
| 早期 JD 分析、人工欄位與來源資格、匯出取捨 | [早期研究收錄](../archive/branch-snapshots/20261002-legacy-jd-research/README.md) | 原文、來源提交及 manifest；不是新目標實測 |
| 候選文件編輯、虛擬工作區與持久工作稿的實作過程 | [早期實作報告](../experiments/historical/agent-task-reports/README.md) | 8 份既有報告原文，保留測試、限制與當時程式基準 |
| 舊 JD 編輯整合的失敗、修正及重驗 | [整體審查](../experiments/historical/20260918-analysis-only-agent/evidence/jd-editor-core-review/README.md)、[Task6](../experiments/historical/20260918-analysis-only-agent/evidence/jd-editor-task6/README.md) | 相同目錄保留 review、輸入、輸出、日誌與當時 source；精確 Git 原件見[歷史索引](../archive/worktree-history-index.md) |

引用實驗時，同時交代問題、場景、方法、版本、結果與限制。不要只挑最後成功紀錄，也不要把單次合成案例推論成普遍品質；歷史報告中的模型、費用限制與後續工作只代表當時狀態。

## 保存與後續維護

- 實驗紀錄繼續寫在原任務的 `evidence/`，原始輸出留在其 `data/`；報告引用它們，不另存一份可各自修改的結果。
- 已完成的分支與 worktree 由[歷史索引](../archive/worktree-history-index.md)查來源及恢復方式。封存 tag 保存完整提交，目錄快照提供閱讀；兩者用途不同。
- 2026-10-02 的材料整理僅保存在本機，未推送；被 Git 忽略的暫存也不代表已有遠端備份。保存範圍與未處理材料見[整理紀錄](../archive/repository-organization-2026-10-02.md)。
