# 程式設計與實作文件

本目錄說明如何用程式落實產品契約，包含現行技術選型、接線與驗證對照。正式產品位於 `apps/api`、`apps/web`；先確認要改的行為，再查下表。

整體責任見[架構](../architecture/README.md)，程式要求見[規範入口](../standards/README.md)，修改與文件維護見[貢獻指南](../../CONTRIBUTING.md)。

圖面由獨立 `.mmd` 生成並在正文引用。各圖旁可直接開啟圖源；整體路由與重繪命令見[圖源索引](../diagrams/README.md)。

## 從哪裡開始

| 開始工作前要確認 | 閱讀入口 |
|---|---|
| 產品應達成什麼、現行責任與限制 | [架構與責任文件](../architecture/README.md) |
| 目前限制及驗證責任 | [驗證範圍](../architecture/verification.md) |
| 模組、程式與契約要求 | [程式規範](../standards/README.md)；修改及驗證見[貢獻指南](../../CONTRIBUTING.md) |
| 選哪些框架、為何、不選什麼 | [技術選型與機制驗證](technology-decisions.md) |

### 依改動範圍讀接線

#### 業務與資料

| 改動範圍 | 責任文件 |
|---|---|
| 業務、SQL、來源、快照及生成契約如何接 | [業務與資料接線](data-and-contracts.md) |
| 職務檔案、正式訪談與准入如何保存 | [訪談保存接線](interview-storage.md) |
| JD 修訂、原結果與人工編輯如何保存 | [JD 保存接線](jd-storage.md)：人工／候選隔離、固定修訂、定位、來源核對及完成採用 |
| Memory 候選與固定快照如何接入保存 | [Memory 保存接線](memory-storage.md)：固定修訂、候選恢復、單向交接及原子發布 |
| Memory／Plan 長文如何局部修改，並保留其他正文 | [正文編輯接線](memory-body-editing.md)：V4A 格式、唯一定位及候選交易的分責 |
| Memory 模型工具如何生成、綁角色與可見基準、按需回查 | [模型工具接線](memory-tools.md) |

#### 執行與介面

| 改動範圍 | 責任文件 |
|---|---|
| Graph、原生 Responses、Step 與 Context 如何接續 | [Agent 執行接線](agent-execution.md) |
| 固定模型請求、容量、重試與費用如何處理 | [模型外送接線](model-requests.md) |
| runner 啟停、暫停／取消及 Memory 如何調度 | [程序監督與背景調度](agent-supervision.md) |
| 工作畫面、JD 人工編輯、草稿與鍵盤互動如何接 | [Web 工作畫面](web-workspace.md) |
| HTTP、公開串流、來源回查、PDF 及本機服務如何交付 | [介面與交付](interface-and-delivery.md) |

驗證需求與測試層級看[驗證對照](verification-plan.md)；既有結果與尚未覆蓋範圍看[架構驗證](../architecture/verification.md)。最後核對相關程式與測試，任務摘要不能取代完整契約。

## 文件維護責任

產品效果及跨層權責由[架構](../architecture/README.md)維護，工程要求見[程式規範](../standards/README.md)；本目錄負責現行選型、實現機制與驗證對照。JSON 格式由[契約來源](../../apps/api/contracts/)生成，各層引用同一來源；文件只解釋欄位與狀態的用途，不另維護一份 schema。

需求改變時更新負責該規則的正文；只換實現機制時，更新接線及受影響測試。程式與文件不一致時，先核對現行行為及規則適用範圍，再修正落差，不能把候選或歷史方案寫成已實作。既有文件持續更新，只有需要獨立維護的主題才新增文件。
