# 報告與研究材料入口

給教授、推甄與專題報告的材料由此查找。這裡只分類原有成果，不新增產品規格或把歷史實驗當成目前驗收；任務狀態仍見[任務表](../plans/2026-09-29-target-rebuild/tasks.md)。

## 介紹產品與程式設計

| 要說明什麼 | 閱讀入口 |
|---|---|
| 問題、使用者與產品價值 | [產品專題介紹](../product-introduction.md) |
| 程式分工、Context、Memory、引用與恢復 | [教授版架構報告](system-architecture/README.md)，先看其程式基準與限制 |
| 上台展示流程與架構 | [圖稿目錄](system-architecture/diagrams/README.md)，保留 PNG、SVG 與 Mermaid 原始檔 |

## 說明如何發現問題並驗證改善

| 主題 | 經過與解讀 | 可核對的原始材料 |
|---|---|---|
| 訪談分析品質、Prompt 比較與來源漏選 | [T14 品質紀錄](../plans/2026-09-29-target-rebuild/evidence/t14-job-analysis-quality.md) | [訪談指引比較資料包](../plans/2026-09-29-target-rebuild/evidence/data/instruction-experiments-2026-10-01/README.md) |
| 長訪談、程序事故、恢復與 PDF | [T17 旅程紀錄](../plans/2026-09-29-target-rebuild/evidence/t17-course-administrator-journey.md) | 同一[長旅程資料包](../plans/2026-09-29-target-rebuild/evidence/data/instruction-experiments-2026-10-01/README.md)的逐字稿、事件與成品 |
| 原生接續、容量與來源工具探測 | [T16 接續紀錄](../plans/2026-09-29-target-rebuild/evidence/t16-compaction-continuity.md)及[證據分類](../plans/2026-09-29-target-rebuild/evidence/README.md) | [執行與品質探測原件](../plans/2026-09-29-target-rebuild/evidence/data/runtime-probes-2026-10-01/README.md) |
| 早期 JD 分析、人工欄位與來源資格、匯出取捨 | [早期研究收錄](../archive/branch-snapshots/20261002-legacy-jd-research/README.md) | 原文、來源提交及 manifest；不是新目標實測 |
| 舊 JD 編輯整合的失敗、修正及重驗 | [整體審查](../archive/worktree-snapshots/20260918-analysis-only-agent/docs/specs/evidence/jd-editor-core-review/README.md)、[Task6](../archive/worktree-snapshots/20260918-analysis-only-agent/docs/specs/evidence/jd-editor-task6/README.md) | 相同目錄保留 review、輸入、輸出、日誌與當時 source；精確 Git 原件見[歷史索引](../archive/worktree-history-index.md) |

引用實驗時，同時交代問題、場景、方法、版本、結果與限制。不要只挑最後成功紀錄，也不要把單次合成案例推論成普遍品質；歷史報告中的模型、費用限制與後續工作只代表當時狀態。

## 保存與後續維護

- 實驗紀錄繼續寫在原任務的 `evidence/`，原始輸出留在其 `data/`；報告引用它們，不另存一份可各自修改的結果。
- 已完成的分支與 worktree 由[歷史索引](../archive/worktree-history-index.md)查來源及恢復方式。封存 tag 保存完整提交，目錄快照提供閱讀；兩者用途不同。
- 本次整理沒有推送，也沒有宣稱 ignored 暫存都有遠端備份；保存範圍與未處理材料見[整理紀錄](../archive/repository-organization-2026-10-02.md)。
