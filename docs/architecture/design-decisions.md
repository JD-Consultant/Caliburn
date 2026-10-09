# 系統設計取捨

Caliburn 採用模組化單體、PostgreSQL 與原生模型接續，讓訪談、JD 編輯及背景 Memory 整理共用明確的資料與恢復規則。本章說明這些選擇的理由、替代方案與代價，也交代哪些效果仍缺實測。

本章描述現行選擇；未實作的目標另標示狀態。版本及框架設定見[技術選型](../implementation/technology-decisions.md)，分析品質與未覆蓋分支見[驗證範圍](verification.md)。

按問題查閱：

- 程式如何分工：[模組化單體](#2-程式邊界模組化單體優先)。
- 資料如何保存：[修訂保存](#3-保存明確業務候選與不可變正式修訂不以事件重播作唯一真相)、[短交易](#4-交易短交易條件提交原操作核對)。
- 模型如何工作：[模型執行](#5-模型執行以既有框架整合產品流程)、[編輯格式](#6-工具與格式依內容與操作選擇)。

## 1. 文件結構：多視角、單一責任、可逐層深入

架構依系統責任、資料、運作與驗證分題，讓讀者先理解整體，再沿需要深入契約及程式。這借鑑 [C4](https://c4model.com/diagrams)的逐層放大與 [arc42](https://docs.arc42.org/section-6/)的代表性執行情境；沒有必要畫滿所有層級或把全部細節收在一張圖。代價是跨層問題要沿明確連結查閱，因此[架構入口](README.md)維護唯一的主題路由與文件分工。

圖面符號見[圖庫讀圖約定](../diagrams/README.md#讀圖約定)，文字與圖稿的維護責任見[文件維護](../../CONTRIBUTING.md#文件維護)。

## 2. 程式邊界：模組化單體優先

架構採本機 Web、內含明確業務模組的單一 App 後端、PostgreSQL 與外部 Responses API。A 與背景 Graph 可透過非同步工作並行，同一職務檔案的寫入則依業務規則控制順序。AI 角色、工具、業務與持久化分別負責不同工作，不各自部署為獨立服務。

若採微服務或讓每個 AI 角色各自成為服務，會增加跨資料庫一致性、部署與診斷的負擔；若執行環境完全不分模組，則會讓 UI、模型與資料庫各自複製規則。因此保留明確的模組界線，不另建通用架構框架。

這項選擇借鑑 [AWS hexagonal pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/hexagonal-architecture.html)將業務與技術接線分開的方式，並不要求每層都有 adapter。只有實際部署、負載或獨立發版需求顯示單體有具體限制時，才需要重新評估服務拆分。

## 3. 保存：明確業務候選與不可變正式修訂，不以事件重播作唯一真相

正式訪談、JD／Memory 修訂與關係由業務模組保存於 PostgreSQL；可恢復的候選也由對應的資料模組保存。LangGraph checkpointer 保存執行進度、原生 items 及候選固定位置的引用，不另存第二份可獨立編輯的全文。供讀取或顯示的資料按需產生。詳見[資料與交易](persistence.md)。

候選需要支援單次修改的原子性、來源身分、B1／B2 共用工作稿、預覽與差異比較，以及 Step 恢復時的一致位置。候選與操作結果在同一保存邊界內，checkpoint 則記錄接續位置；恢復時可核對原結果，不讓兩種保存方式各自判定正式資料。

現行採「物件修訂重用 + 快照選用」保留固定歷史：變動物件建立必要修訂，正文變更才新增內容，未變正文可重用。這讓正文可直接讀取，但多個不同正文仍可能含有重複文字。

目前不做正文內容位址去重；是否需要壓縮或去重，尚缺真實容量量測。

其他做法各有代價：

| 做法 | 代價 |
|---|---|
| 每版複製全部正文 | 較簡單，但重複較多 |
| Git 式差異鏈 | 需要重建正文及更多格式／清理規則 |
| event sourcing | 須維護事件版本與 replay 正確性 |

## 4. 交易：短交易、條件提交、原操作核對

短交易讓模型等待與資料提交分開；持久資格及原操作結果則處理取消競爭和結果不明。若用一筆長交易包住模型呼叫，會延長資源占用；只提高隔離級別，也不能替代業務完成及恢復的判定。各次共同提交的內容由[交易邊界](persistence.md#3-交易邊界)維護，鎖、隔離及重入方式由[交易接線](../implementation/data-and-contracts.md#2-sql交易責任)落實。

[PostgreSQL transactions](https://www.postgresql.org/docs/current/tutorial-transactions.html)支持原子／持久保存；[isolation](https://www.postgresql.org/docs/current/transaction-iso.html)說明讀取隔離及重試責任。鎖與隔離級別的適用性取決於真資料庫競爭測試，Graph checkpoint 本身不提供資料庫交易保證。選型採 PostgreSQL 18；相容性與鎖定依賴見[技術選型](../implementation/technology-decisions.md)，實際部署環境見[後端說明](../../apps/api/README.md)，證據範圍見[反例矩陣](verification.md)。

正式 A 完成與 Memory 待處理上界同次持久成立；調度從該業務事實恢復，不另設外部 broker 或第二套 outbox。[AWS transactional outbox](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html)揭示寫 DB 與發通知的雙寫風險；本案以可重掃的正式待處理事實解決同一問題，不宣稱已導入完整 outbox 平台。

## 5. 模型執行：以既有框架整合產品流程

現行採用 LangGraph 與 OpenAI direct Responses SDK，不採 LangChain agent／message adapter 或 OpenAI Agents SDK。Graph 負責執行控制與 checkpoint，各角色的工具連接業務模組，原生模型輸出依原契約保存與重播。

執行節點、SDK 傳輸格式、取消資格與模型容量詳見[共用執行與恢復](../implementation/agent-execution.md)。

不新增通用模型供應商抽象層、第二套工作階段引擎、每步必填的工作狀態筆記或獨立的壓縮 AI 角色。只有實測反例顯示原生接續不足，才評估需要補充哪些分析資料；不可讀的推理內容不作為 App 可讀取的工作計畫。

**上下文控制權：** App 決定組裝與接續內容，框架／adapter 不另選歷史、不暗中摘要或換角色。使用 `store=false`，不使用 `previous_response_id`，由 App 明確提供接續 items。

驗證這項分工時，須核對 SDK 發送邊界的實際請求；僅看組裝前資料不足以排除隱含變換。這項驗證要求也不表示所有請求副本都永久保存。

App 仍可明確呼叫模型的原生能力。[OpenAI standalone compaction](https://developers.openai.com/api/docs/guides/compaction#standalone-compact-endpoint)允許送入完整視窗，並採用完整的返回視窗；其中加密的 compaction item 無法由人解讀。App 控制觸發時機、範圍與安全採用條件，但不掌握供應商內部如何取捨內容。現行採 App 主動壓縮；門檻、Step 交界及回退規則只在[共用執行與恢復](../implementation/agent-execution.md)維護。

現行能力與驗證限制由[執行接線](../implementation/agent-execution.md)及[驗證範圍](verification.md)維護。

## 6. 工具與格式：依內容與操作選擇

長正文需要精確保留未改文字，短欄位與關係則需要明確的型別及操作意圖，因此 Memory 與 JD 不強用同一種修改格式。模型表達內容與目標，App 管理範圍、版本及保存身分；這讓格式貼近分析工作，也避免模型重建系統已知資料。

命名及共同輸出見[模型工具的共同邊界](../standards/contract-strategy.md#模型工具的共同邊界)，格式解析與錯誤處理由 [Memory 正文編輯](../implementation/memory-body-editing.md)和 [JD 接線](../implementation/jd-storage.md)維護。

## 7. 保持架構範圍有限

現行架構處理訪談、工作資訊累積、有據改稿與可靠保存。高內聚、低耦合、可讀、可測及可診斷是工程基線，各項實作都須遵守，不以能否直接提高 JD 品質作為前提。微服務、通用規則引擎及事件重播平台目前沒有必要用途；後續技術選擇依維護、測試與運作成本比較，不將現行未採用寫成永久禁令。工程與產品品質各自驗收，依[貢獻指南](../../CONTRIBUTING.md#驗證與提交)維護。

產品範圍見[產品概念](../product/concepts.md)，測試及品質限制見[驗證章節](verification.md)。
