# 工作分析與 JD 指南

這裡找「顧問應如何理解工作、訪談及撰寫 JD」，不是 API 操作教學，也不是工程規範。指南正文保留既有 `specs/` 路徑，避免改動 Prompt 的內容權威引用；本頁只提供方法入口，不維護第二份正文。

## 依工作順序閱讀

| 要解決的問題 | 指南 |
|---|---|
| 各份指南如何分工 | [工作分析與高品質 JD](../specs/2026-09-09-job-analysis-and-jd-content-research.md) |
| 需要理解哪些工作事實、細節及脈絡 | [完整工作分析與訪談指南](../specs/2026-09-09-complete-work-analysis-guide.md) |
| 如何追問、何時已有足夠深度 | [個別化 JD 深度與訪談校準](../specs/2026-09-09-customized-jd-depth-and-interview-calibration.md) |
| 欄位的意義、內容與寫作方式 | [JD 欄位與寫作指南](../specs/2026-09-09-jd-field-and-writing-guide.md) |
| 看一份具體成品及其限制 | [前端工程師樣稿](../specs/2026-09-09-frontend-engineer-jd-sample.md)、[樣稿依據與審查](../specs/2026-09-09-jd-sample-basis-and-review.md) |

樣稿是寫作示例，不是可以填入任何員工 JD 的事實。外部職能標準、雇主文件比較及原始研究，見[工作分析研究](../research/README.md#工作分析訪談與-jd-內容)。

## 接到產品與程式

- 哪些概念已成為產品要求：查[產品概念](../product-concept.md)與[目前決策](../current-decisions.md)。
- Prompt、Tool、Context 如何共同設計及驗收：查[開發規範](../implementation/development-standard.md)與[工具共同規範](../specs/2026-09-27-agent-tool-contract-design-research.md)。
- 實際分析品質、失敗與修正：查 [T14 品質證據](../plans/2026-09-29-target-rebuild/evidence/t14-job-analysis-quality.md)，不以指南寫好推導模型品質已達標。
