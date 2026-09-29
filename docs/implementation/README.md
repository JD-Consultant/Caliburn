# 新目標實作文件入口

- 日期：2026-09-29；狀態：**工程設計進入已授權施工；進度與實際驗證依任務表，不代表產品已完成**。
- 範圍：將[目標架構](../target-architecture-map.md)轉成可交付程式的設計；不重訂產品需求，不把舊程式接回新產品。本次 Goal 授權與限制見[實作計畫](../plans/2026-09-29-target-rebuild/README.md)。
- 施工位置：新 `apps/api`、`apps/web`。這是重用路徑名稱，不是復活該路徑已退役的舊產品。現行 production 仍依 ADR0077，直到最後切換 gate。

## 從哪裡開始

| 問題 | 唯一入口 |
|---|---|
| 產品應達成什麼、哪些規則不能改 | [目標架構與責任文件](../target-architecture-map.md) |
| 如何研究、SDD、TDD、審查與維護 | [開發規範](development-standard.md) |
| 先做什麼、依賴誰、何時算完成 | [實作計畫](../plans/2026-09-29-target-rebuild/README.md)與[任務](../plans/2026-09-29-target-rebuild/tasks.md) |
| 長 Goal 如何持續接手、不漏要求 | [Goal 持久入口](../plans/2026-09-29-target-rebuild/README.md)與[長任務工作規則](development-standard.md#10-長任務goal-與工作上下文)；當前實測及下一步從任務 evidence 深入 |
| 選哪些框架、為何、不選什麼 | [技術選型與機制驗證](technology-decisions.md) |
| 程式如何分模組、命名、限制依賴 | [程式組織與命名](code-organization.md) |
| 函式／類別／Service 怎麼寫、錯誤與非同步如何處理 | [程式撰寫規範與實例](coding-standard.md)；與模組架構分責，不另造產品契約 |
| 業務、SQL、來源、快照及生成契約如何接 | [業務與資料接線](data-and-contracts.md) |
| 已實作的職務檔案／正式訪談如何保存 | [訪談保存接線](interview-storage.md)；區分已驗切片與尚未完成的正式化／准入 |
| 已實作的 JD 修訂、原結果與人工編輯如何保存 | [JD 保存接線](jd-storage.md)；全部人工集合、候選／正式隔離、位置回退及交易內採用；完整 Agent／來源／候選 UI 另依 T07–T09 |
| Memory 候選與固定快照如何接入保存 | [Memory 保存接線](memory-storage.md)；T04 候選／固定修訂、回復與原子發布已驗；模型工具／diff／背景 Agent 依 T05／T10／T11 |
| Memory V4A 長文怎麼解析、唯一定位、保留未改正文 | [正文編輯接線](memory-body-editing.md)；T05 純編輯器與工具／交易接線分開驗證 |
| Memory 模型工具如何生成、綁角色與可見基準、按需回查 | [模型工具接線](memory-tools.md)；讀取已驗，寫入及 Runtime 接續仍依 T05／T06 |
| Graph、原生 Responses、恢復與取消如何接 | [Agent 執行接線](agent-execution.md) |
| UI、串流、PDF、啟停及安全如何交付 | [介面與交付](interface-and-delivery.md) |
| 哪個需求由哪個任務與測試證明 | [驗證對照](verification-plan.md) |
| 這批文件審查結果與未驗證事項 | [計畫審查](../plans/2026-09-29-target-rebuild/review.md) |

**閱讀方式：**先讀本頁與開發規範；領一項任務後，完整閱讀它指定的上位責任章節與對應實作文件。不要一次把所有研究、歷史討論與程式塞進 Agent context；也不能只讀任務摘要而漏掉上位契約。較早規格中的歷史／候選內容不覆蓋最新有效狀態。

## 文件不是四份規格

架構文件定義「效果、權責、不變量」；本目錄定義「用什麼程式結構及機制實現」；任務表只定義「依賴、工作範圍、驗收與證據」。正式 JSON shape 於施工時落在生成來源。相同欄位、工具格式、狀態機不在這幾層各抄一份。

需求改變先改原責任文件；機制替換只改本目錄及受影響任務／測試；完成狀態只在任務表維護。新文件確有獨立維護責任才新增，不每輪建立另一個 final。

新程式與現行底稿不要求相容層、資料搬遷或雙寫。可借用經測試的演算法／測例，但須改成新命名及新依賴方向，不能從新產品 import `experiments` 或舊 Memory package。既有密鑰、資料庫、volume、未追蹤檔案不因「無需整合」而自動刪除。
