# 早期 JD 分析與匯出研究收錄

這是 2026-10-02 整理本機分支時，從兩條舊分支補收的歷史材料：23 筆來源對應 20 份不同原文，3 份完全相同的內容只保存一份。用途是查研究、取捨與驗證經過，不是恢復舊架構施工。原文件中的 Accepted、模型選擇及完成狀態只代表該提交當時；有效規則仍查[目前決策](../../../current-decisions.md)。

## 按主題閱讀

| 主題 | 原文入口 |
|---|---|
| 避免把人工 JD header 當成員工已說過的事實 | [2026-08-05 合成場景複驗](review-origin-main/docs/experiments/2026-08-05-jd-header-packet-live-verification/README.md)；報告明列單次樣本與歸因限制，未把它當品質 gate |
| JD header、readiness 與能力層次 | [header 計畫](review-origin-main/docs/plans/2026-08-04-job-analysis-jd-header-and-readiness-slice-plan.md)、[職責／任務能力層次計畫](review-origin-main/docs/plans/2026-08-05-job-analysis-duty-and-task-competency-level-plan.md) |
| Task Analysis 分析與互動流程 | [分析引擎設計](review-origin-main/docs/design/task-analysis-engine.md)、[Web UX 流程](review-origin-main/docs/design/job-analysis-web-ux-flow.md)、[子對話／職責分組 ADR](review-origin-main/docs/adr/0061-per-task-subconversation-and-duty-grouping-suggestion.md) |
| AI 輔助職責建議 | [研究](review-origin-main/docs/specs/2026-08-06-ai-assisted-duty-research.md)、[ADR](review-origin-main/docs/adr/0059-ai-assisted-duty-suggestion.md)、[計畫](review-origin-main/docs/plans/2026-08-06-ai-assisted-duty-plan.md) |
| 行為指標深度與 iCAP 參照 | [研究](review-origin-main/docs/specs/2026-08-07-behavioral-indicator-depth-and-icap-reference-flow-research.md)、[ADR](review-origin-main/docs/adr/0060-enterprise-jd-indicator-depth-and-icap-reference.md) |
| 確定性匯出、組裝／渲染責任及 OPKS 排序 | [匯出研究](review-origin-main/docs/specs/2026-08-06-jd-deterministic-export-research.md)、[ADR0058](review-origin-main/docs/adr/0058-jd-deterministic-export-shape-and-format.md)、[匯出計畫](review-origin-main/docs/plans/2026-08-06-jd-deterministic-export-plan.md)、[排序計畫](review-origin-main/docs/plans/2026-08-06-job-analysis-opks-display-order-plan.md) |
| 舊整合分支的不同版本 | [ADR0056](integrate-reviewed-origin-main/docs/adr/0056-jd-deterministic-export-shape-and-format.md)、[引擎設計](integrate-reviewed-origin-main/docs/design/task-analysis-engine.md)、[匯出研究](integrate-reviewed-origin-main/docs/specs/2026-08-06-jd-deterministic-export-research.md)、[匯出計畫](integrate-reviewed-origin-main/docs/plans/2026-08-06-jd-deterministic-export-plan.md)、[排序計畫](integrate-reviewed-origin-main/docs/plans/2026-08-06-job-analysis-opks-display-order-plan.md)；保留差異，不合成一份新規格 |

## 來源與完整性

| 原分支 | 精確提交 | 本機封存 tag |
|---|---|---|
| `archive/review-origin-main-20260915` | `db98bfecb312a3b91fb9a7177f6b2241a16b4b4b` | `archive/review-origin-main-20261002` |
| `archive/integrate-reviewed-origin-main-20260915` | `26cbe906640170b27849f8cfa424229f18b205f7` | `archive/integrate-reviewed-origin-main-20261002` |

[manifest.csv](manifest.csv) 列原分支、commit、原路徑、原 Git blob ID 及目前 repo 相對保存位置。20 份原件用 `git hash-object --no-filters` 逐檔比對原 blob；未修改正文、結論或引用。

這是**選錄，不是完整 checkout**。原件的相對連結及程式路徑保留歷史語境，可能指向本選錄未收的檔案；要追完整上下文，從同一封存 tag 依原路徑查閱，不以現行同名文件冒充。例：

```powershell
git show refs/tags/archive/review-origin-main-20261002:docs/design/task-analysis-engine.md
```

原實驗報告提及 ignored raw capture；本次沒有驗證它們是否仍在，也不把報告正文當成已收齊 raw data。完整提交由 tag 保留；本選錄沒有引入舊程式、環境檔或工具依賴。[返回報告材料入口](../../../reports/README.md)。
