# 程式設計與實作文件

本目錄維護現行程式的模組、資料接線、工具及工程規範。正式產品位於 `apps/api`、`apps/web`，權責依 [ADR0079](../adr/0079-target-rebuild-production-cutover.md)。驗證結果與限制見[驗證對照](verification-plan.md)。

## 從哪裡開始

| 問題 | 唯一入口 |
|---|---|
| 產品應達成什麼、哪些規則不能改 | [架構與責任文件](../target-architecture-map.md) |
| 如何研究、SDD、TDD、審查與維護 | [開發規範](development-standard.md) |
| 後續工作與驗證從哪裡找 | [目前決策](../current-decisions.md)、[計畫入口](../plans/README.md)、[架構驗證](../architecture/verification.md)與[產品實驗](../experiments/product-validation/README.md) |
| 多步驟工作如何持續接手、不漏要求 | [長任務工作規則](development-standard.md#10-長任務goal-與工作上下文)；沿本題責任文件及證據接續 |
| 選哪些框架、為何、不選什麼 | [技術選型與機制驗證](technology-decisions.md) |
| 程式如何分模組、命名、限制依賴 | [程式組織與命名](code-organization.md) |
| 函式／類別／Service 怎麼寫、錯誤與非同步如何處理 | [程式撰寫規範與實例](coding-standard.md)；與模組架構分責，不另造產品契約 |
| 業務、SQL、來源、快照及生成契約如何接 | [業務與資料接線](data-and-contracts.md) |
| 職務檔案、正式訪談與准入如何保存 | [訪談保存接線](interview-storage.md) |
| JD 修訂、原結果與人工編輯如何保存 | [JD 保存接線](jd-storage.md)：人工／候選隔離、固定修訂、定位、來源核對及完成採用 |
| Memory 候選與固定快照如何接入保存 | [Memory 保存接線](memory-storage.md)：固定修訂、候選恢復、單向交接及原子發布 |
| Memory V4A 長文怎麼解析、唯一定位、保留未改正文 | [正文編輯接線](memory-body-editing.md)：純編輯器、工具及候選交易的分責 |
| Memory 模型工具如何生成、綁角色與可見基準、按需回查 | [模型工具接線](memory-tools.md)，搭配共用執行與角色流程 |
| Graph、原生 Responses、恢復與取消如何接 | [Agent 執行接線](agent-execution.md) |
| UI、串流、PDF、啟停及安全如何交付 | [介面與交付](interface-and-delivery.md) |
| 哪個需求需要哪一層驗證 | [驗證對照](verification-plan.md) |
| 查驗證結果與尚未覆蓋範圍 | [架構驗證](../architecture/verification.md)、[產品驗證與實驗資料](../experiments/product-validation/README.md) |

**閱讀方式：**先讀本頁與開發規範；領一項任務後，完整閱讀它指定的上位責任章節與對應實作文件。不要一次把所有研究、歷史討論與程式塞進 Agent context；也不能只讀任務摘要而漏掉上位契約。較早規格中的歷史／候選內容不覆蓋最新有效狀態。

## 文件不是四份規格

架構文件定義「效果、權責、不變量」；本目錄定義「用什麼程式結構及機制實現」；任務表記錄「依賴、工作範圍、驗收與證據」。正式 JSON 格式由契約來源生成，不在這幾層各抄一份欄位、工具格式或狀態機。

需求改變先改原責任文件；機制替換只改本目錄及受影響任務／測試；完成狀態只在任務表維護。新文件確有獨立維護責任才新增，不每輪建立另一個 final。

正式產品不依賴退役程式，不提供舊資料相容層、搬遷或雙寫。維護時可參考歷史演算法／測例，不能從產品 import `experiments` 或舊 Memory package。既有密鑰、資料庫、volume、未追蹤檔案不因舊程式退役而自動刪除。
