# 驗收、問題與實驗證據索引

任務狀態只由[任務表](../tasks.md)維護；這裡按問題分類既有紀錄，不另判定產品完成。文件內較早的失敗、未完成與後續修正都保留，閱讀同題最新小節。記錄方式沿[開發規範 §8](../../../implementation/development-standard.md#8-問題與解法紀錄)。

## 現在先看

- [剩餘工作分類](../tasks.md#收尾分類與下一步)：先核對證據，不盲目重跑。
- [T17 長訪談、事故與續跑](t17-course-administrator-journey.md)：45 輪原旅程的成果與未驗範圍。
- [T16 原生接續與容量](t16-compaction-continuity.md)：門檻、模型／共用 runner／角色的不同驗證層級。
- [T14 分析品質與已知不足](t14-job-analysis-quality.md)：Prompt 比較、來源漏選、採用／否決與限制。
- [T18 交付候選](t18-same-origin-web.md)：不是正式切換已放行。

## 按主題查找

| 主題 | 紀錄 |
|---|---|
| 工具鏈、資料與來源資格 | [T01 基礎](t01-foundation.md)、[T02 檔案／訪談](t02-job-files-and-interviews.md)、[T03 關聯式 JD](t03-relational-jd.md) |
| Memory 物件、工具、角色與發布 | [T04 保存](t04-work-memory.md)、[T05 工具](t05-memory-tools.md)、[T10 分析角色](t10-memory-analysis-roles.md)、[T11 背景批次](t11-memory-batch.md) |
| 共用模型／工具接續與恢復 | [T06 執行](t06-agent-execution.md)、[結果交接](t06-result-handoff-recovery.md)、[T12 程序恢復](t12-consultant-process-recovery.md) |
| JD 工具、引用、移動與差異 | [T07 工具](t07-jd-tools.md)、[來源操作](t07-jd-source-actions.md)、[差異來源](t07-jd-changes-source.md)、[項目移動](t07-jd-item-movement.md) |
| 顧問、輸入與完整 UI 旅程 | [T08 顧問 Turn](t08-consultant-turn.md)、[原輸入重送](t08-input-replay-readiness.md)、[T09 旅程](t09-consultant-journeys.md)、[候選預覽](t09-consultant-preview.md)、[UI 改版](t09-ui-redesign.md) |
| 串流、中間訊息與歷史 | [Responses 串流](t09-response-streaming.md)、[訊息傳輸](t09-commentary-transport.md)、[訊息 UI](t09-commentary-ui.md)、[歷史定位](t09-history-turn-locator.md)、[找回當前 Turn](t09-current-turn-discovery.md) |
| 來源查看、徽章與本輪 JD 改動 | [來源讀取](t09-source-viewer.md)、[來源 UI](t09-source-viewer-ui.md)、[共用查詢](t09-shared-source-queries.md)、[本輪 JD 差異](t09-turn-jd-changes.md) |
| 撤回與 PDF | [T13 撤回](t13-jd-undo.md)、[PDF 交付](t13-pdf-export.md) |
| 安全、容量量測與維護性 | [T15 HTTP 安全](t15-local-http-security.md)、[容量量測](t15-capacity-measurements.md)、[程式結構審查](t15-code-organization-review.md) |
| 前次交接及全局審查 | [歷次交接](2026-09-30-pause-handoff.md)、[計畫／施工審查](../review.md)；不是覆蓋較新證據的完成清單 |

## 報告用原始材料

| 資料包 | 用途 |
|---|---|
| [訪談指引比較與長旅程](data/instruction-experiments-2026-10-01/README.md) | Q1／Q2／Q2b／Q3 比較、可讀逐字稿、指標、失敗與長旅程 JSON／事件／PDF |
| [執行、品質與來源探測](data/runtime-probes-2026-10-01/README.md) | 原先散在本機暫存的模型／容量／來源／合成旅程輸出；含搬移對照與原件雜湊，不重新解讀為通過 |

實驗原件、衍生摘要與報告分開：本目錄解釋如何發現、診斷與驗證；`data/` 保存可核對材料；[教授報告](../../../reports/system-architecture/README.md)負責介紹。不能用一張成功截圖代替失敗紀錄或完整驗收。
