# 程式設計與實作文件

本目錄說明如何用程式落實既有產品契約：模組分工、資料與工具接線，以及開發規範。正式產品位於 `apps/api`、`apps/web`，權責依 [正式產品與選型](../architecture/design-decisions.md)。先確認要改的行為，再讀對應接線；不必循序讀完本目錄。

圖面由獨立 `.mmd` 生成並在正文引用。各圖旁可直接開啟圖源；整體路由與重繪命令見[圖源索引](../diagrams/README.md)。

## 從哪裡開始

| 開始工作前要確認 | 閱讀入口 |
|---|---|
| 產品應達成什麼、哪些規則不能改 | [架構與責任文件](../architecture/README.md) |
| 目前限制與驗證責任 | [驗證範圍](../architecture/verification.md) |
| 研究、SDD、TDD、審查與長任務接手 | [開發規範](development-standard.md)；接手方式見 [§10](development-standard.md#10-長任務goal-與工作上下文) |
| 選哪些框架、為何、不選什麼 | [技術選型與機制驗證](technology-decisions.md) |
| 模組、命名、依賴與 Prompt／Tool 替換 | [程式組織與命名](code-organization.md)；對照公平性沿[開發規範 §7](development-standard.md#7-分析方法prompttool-與-context-共同驗收) |
| 前後端寫法、錯誤、測試與觀測 | [程式撰寫規範與實例](coding-standard.md)，含 [Log 格式與查閱](coding-standard.md#72-log-的格式責任與查閱) |
| 工程文件如何分工、拆合、敘述與繪圖 | [文件與圖面規範](documentation-standard.md) |

### 依改動範圍讀接線

| 改動範圍 | 責任文件 |
|---|---|
| 業務、SQL、來源、快照及生成契約如何接 | [業務與資料接線](data-and-contracts.md) |
| 職務檔案、正式訪談與准入如何保存 | [訪談保存接線](interview-storage.md) |
| JD 修訂、原結果與人工編輯如何保存 | [JD 保存接線](jd-storage.md)：人工／候選隔離、固定修訂、定位、來源核對及完成採用 |
| Memory 候選與固定快照如何接入保存 | [Memory 保存接線](memory-storage.md)：固定修訂、候選恢復、單向交接及原子發布 |
| Memory／Plan 長文如何局部修改，並保留其他正文 | [正文編輯接線](memory-body-editing.md)：V4A 格式、唯一定位及候選交易的分責 |
| Memory 模型工具如何生成、綁角色與可見基準、按需回查 | [模型工具接線](memory-tools.md) |
| Graph、原生 Responses、Step 與 Context 如何接續 | [Agent 執行接線](agent-execution.md) |
| 固定模型請求、容量、重試與費用如何處理 | [模型外送接線](model-requests.md) |
| runner 啟停、暫停／取消及 Memory 如何調度 | [程序監督與背景調度](agent-supervision.md) |
| 工作畫面、JD 人工編輯、草稿與鍵盤互動如何接 | [Web 工作畫面](web-workspace.md) |
| HTTP、公開串流、來源回查、PDF 及本機服務如何交付 | [介面與交付](interface-and-delivery.md) |

驗證需求與測試層級看[驗證對照](verification-plan.md)；既有結果與尚未覆蓋範圍看[架構驗證](../architecture/verification.md)。最後核對相關程式與測試，任務摘要不能取代完整契約。

## 文件維護責任

產品效果、權責與規則由架構及契約文件維護；本目錄維護實現機制；本機工作紀錄記錄施工範圍、依賴、驗收及證據。正式 JSON 格式由契約來源生成，各層引用同一來源，不重抄欄位或狀態機。

需求改變先改原責任文件；只換實現機制時，更新接線及受影響任務／測試。完成狀態由本機工作紀錄維護，研究、歷史及候選不能覆蓋最新有效契約。既有文件持續更新，只有需要獨立維護的主題才新增文件。

正式產品不依賴退役程式，不提供舊資料相容層、搬遷或雙寫。維護時可參考歷史演算法／測例，不能從產品 import `experiments` 或舊 Memory package。既有密鑰、資料庫、volume、未追蹤檔案不因舊程式退役而自動刪除。
