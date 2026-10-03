# Caliburn 目前決策與維護狀態

本頁只列現行狀態及責任文件，不累積逐輪交接。正式決策以 ADR 及其接續文件為準；完整演進從[歷史索引](history.md)查閱。本次整理不改產品行為、授權或驗收結論。

## 正式產品

- 正式程式為 `apps/api`、`apps/web`。T01–T18 於 2026-10-02 結案並完成本機切換，依 [ADR0079](adr/0079-target-rebuild-production-cutover.md) 取代 ADR0077。
- 舊程式已退役，不整合舊資料。獨立 RAG 保留但不接入 JD App；啟停依 [runbook](runbook.md)。
- 產品模型採 Luna／high；已決定不改用 Sol 作預設或備援。來源引用及分析品質的既有不足仍依實驗結果處理，不因工程結案宣稱普遍達標。
- [架構導覽](target-architecture-map.md)維護產品規則；[實作文件](implementation/README.md)維護程式接線；[產品驗證資料](experiments/product-validation/README.md)保留可核對的實驗原件。已結案施工存本機封存，不隨 Git 發布。

## 按主題查有效規則

| 主題 | 已確認的方向 | 責任文件 |
|---|---|---|
| 訪談與 JD | 有效訪談、候選 JD 及正式完成分開；取消未完成工作不產生正式訪談資格 | [核心生命週期](specs/2026-09-29-core-value-loop-lifecycle.md)、[資料交易](architecture/persistence.md) |
| Memory | B1 整理情境，B2 分析理解，再發布；不回交 B1，顧問讀固定的已發布快照 | [背景生命週期](specs/2026-09-25-b1-b2-information-gap-lifecycle.md)、[Memory 保存](implementation/memory-storage.md) |
| Context 與恢復 | App 組裝及保留原生接續資料；已有安全點則接續，不能續作時安全結束；不以一般摘要取代原生狀態 | [顧問 Context](specs/2026-09-26-consultant-context-and-state-design.md)、[共用執行](specs/2026-09-27-shared-agent-execution-and-state-design.md) |
| 容量與重試 | 區分容量、次數及時間上限；產品不以預估金額攔截正常執行，付費驗證另管預算；限流按等待政策處理 | [執行接線](implementation/agent-execution.md)、[技術選型](implementation/technology-decisions.md) |
| 模型工具 | 模型只填分析需要的參數；App 綁定身分、範圍與版本；按需讀取，不重複大量內容 | [工具規範](specs/2026-09-27-agent-tool-contract-design-research.md) |
| JD 定位與依據 | 模型使用 App 配發的短定位，資料庫保留 UUID；引用核對仍須明確提交，不因看過 diff 自動清除待核對 | [JD 保存](implementation/jd-storage.md)、[JD 工具契約](specs/2026-09-29-jd-model-tool-contract-review.md) |
| Memory 定位與編輯 | 保留既定標題定位、候選讀寫與 V4A 正文編輯，不與 JD 短定位混用 | [讀取及來源](specs/2026-09-27-memory-read-and-source-navigation-contract.md)、[更新工具](specs/2026-09-27-memory-object-update-tool-contract.md) |
| 公開過程與推理摘要 | 可串流及回看；與完整正式答覆、訪談來源資格分開；不公開完整內部推理 | [介面與交付](implementation/interface-and-delivery.md) |
| 工程與文件維護 | 高內聚、低耦合、依風險驗證；責任文件不複製，已結案施工歸歷史 | [程式組織](implementation/code-organization.md)、[寫法規範](implementation/coding-standard.md)、[開發規範](implementation/development-standard.md) |

## 尚需處理或保留的限制

以下不是重開已結案的 T01–T18，而是後續維護的定位入口。

| 項目 | 目前狀態及接續方式 |
|---|---|
| 短 ID 在示範服務啟用 | 程式、migration 與離線／真 PG 驗證已有紀錄；仍需在示範 DB 升級及重啟後確認啟用。依[後端 README](../apps/api/README.md)在安全點處理，實作契約見[JD 保存](implementation/jd-storage.md) |
| Luna 的來源選擇及核對 | 已有跨輪漏引、未提交對齊與定位錯誤反例。短 ID 不等於語意品質已改善；後續自然旅程須分別觀察。原件見[產品驗證資料](experiments/product-validation/README.md)，結果見[實驗彙整](reports/experiment-findings.md) |
| Memory 最終失敗後的整理時機 | 現行程式在有效訪談再前進三輪後允許新批次，這個政策仍待確認；不阻止顧問繼續訪談，見[背景生命週期](specs/2026-09-25-b1-b2-information-gap-lifecycle.md) |
| 尚未覆蓋的實測 | B1／B2 壓縮後發布等分支、真人顧問與員工的省時效果仍有未驗範圍；見[驗證範圍](architecture/verification.md)及[實驗彙整](reports/experiment-findings.md) |
| PDF 文字層 | 既有部分字型的複製／搜尋限制保留追蹤，見[介面與交付](implementation/interface-and-delivery.md)及[實驗彙整](reports/experiment-findings.md) |
| 專題報告 | 目前為 [Markdown 主稿](reports/project-report/report.md)；尚未製作專題報告 PDF。個人分工與送件草稿留在本機，不混入團隊報告正文 |

## 歷史與更新方式

完整沿革見[歷史查閱方式](history.md)。其中「當時未完成」「本輪授權」等文字均屬歷史情境，不覆蓋較後決策。

後續變更先維護相應契約和證據，再更新本頁的狀態或連結；不要重新累積逐日工作日誌。重大取捨依[決策流程](decision-process.md)記錄，Accepted ADR 保留原意，不因整理改寫。
