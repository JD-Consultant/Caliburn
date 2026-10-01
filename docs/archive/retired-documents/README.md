# 已退役文件與被取代方案

2026-10-02 首次從 `target-rebuild@b4157033` 歸位 8 份文件；後續依 Owner 授權將其中五份三行退役通知只留 Git，三份有內容的歷史材料仍保留。首次搬移見[對照表](../document-classification-2026-10-02.csv)，移除通知與恢復方式見[去重紀錄](../docs-cleanup-2026-10-02.md)。本區不作新施工入口。

| 封存文件 | 判定依據／接續入口 |
|---|---|
| [OCS authored schema](../docs-cleanup-2026-10-02.md) | 原文明示 Retired；舊 schema 已退役，不能由此恢復 contract |
| [OCS source JSON pipeline](../docs-cleanup-2026-10-02.md) | 原文明示 Retired；通知描述舊產品 hard cut，不等於獨立 RAG 全部被刪 |
| [舊 service split framework](../docs-cleanup-2026-10-02.md) | 原文明示 Retired；內文的「現行」指當時，不是今日服務拓撲 |
| [舊 editor knowledge pack](../docs-cleanup-2026-10-02.md) | 原文明示 Retired；保留禁令與沿革，不恢復舊 editor seam |
| [舊 interview engine](../docs-cleanup-2026-10-02.md) | 原文明示 Retired；不恢復舊 route／provider／schema |
| [2026-09-15 進度與 worktree 地圖](worktree-progress-map-2026-09-15.md) | 日期限定的接線／分支狀態；新進度見[任務表](../../plans/2026-09-29-target-rebuild/tasks.md)，工作樹見[歷史索引](../worktree-history-index.md) |
| [Evidence-first 舊候選](specs/2026-07-15-evidence-first-stateful-workflow-reconstruction-research.md) | 原文已於 07-16 明示不再是實作目標；研究推導保留，不沿舊 C0–C2 施工 |
| [Job Authoring v2 儲存](specs/2026-07-24-job-authoring-v2-relational-storage-research.md) | 原文已於 07-29 明示被取代；不恢復舊資料模型 |

上述舊通知可能指向已不存在的 `task-analysis-engine.md`，是既有歷史斷鏈，不替它虛構目前繼任契約。當前產品分工查 [ADR0077](../../adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md)，新目標查[架構地圖](../../target-architecture-map.md)。

此分類**不將仍保留的 [RAG pipeline](../../design/rag-pipeline.md) 退役**，也不代表其他尚未逐項核對的舊文件可以刪除。
