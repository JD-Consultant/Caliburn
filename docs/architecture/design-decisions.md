# 系統設計取捨

Caliburn 採用模組化單體、PostgreSQL 與原生模型接續，讓訪談、JD 編輯及背景 Memory 整理共用明確的資料與恢復規則。本章說明這些選擇的理由、替代方案與代價，也交代哪些效果仍缺實測。

核心機制以截至 2026-10-03 的產品為基礎，後續目標調整另標示狀態。分析品質、真人使用效果與未覆蓋分支的證據見[驗證範圍](verification.md)及[實驗發現的問題](../reports/experiment-findings.md)；本章說明選擇的理由，不以架構機制推定效果已達標。

## 1. 文件結構：多視角、單一責任、可逐層深入

讀者可從簡短總覽與邏輯分工圖理解全貌，再深入跨層生命週期、資料保存、運作與驗證等專題。詳細契約集中在對應專題，避免同一規則出現互相矛盾的版本。檔名中的日期不決定內容是否仍有效；導覽區分現行設計與歷史研究。

一份涵蓋所有細節的長文不易定位問題，完全依技術工具分類也難以看出產品流程。按職責分開的專題讓讀者選擇所需深度；代價是跨層問題需要配合總覽與互動流程閱讀，而非只看單一章節。

README 簡述產品價值與現況；[產品介紹](../product-introduction.md)透過問題、使用旅程、設計與驗證說明用途。架構導覽連到詳細專題，圖與正文放在一起，方便對照。這種安排借鑑 [GitHub README 指引](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes)的簡短入口及 [Diátaxis explanation](https://diataxis.fr/explanation/)著重理解的寫法，不視為大型專案唯一適用的模板。

圖面以 [C4 檢查指引](https://c4model.com/diagrams/checklist)說明範圍、圖例與箭頭意義，並以 arc42 runtime view 呈現代表性的正常與異常時序，避免函式細節掩蓋互動關係。

依據：[C4](https://c4model.com/diagrams)按讀者問題逐層放大，且不必畫滿四層；[arc42 building blocks](https://docs.arc42.org/section-5/)描述責任及內部結構，[runtime view](https://docs.arc42.org/section-6/)補代表性互動。這支持多視角，不規定本案目錄名稱。[Microsoft 架構規格](https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-design-specification)支持業務目標、功能／非功能選擇、操作與驗證一併說清；[Google 文件工程](https://abseil.io/resources/swe-book/html/ch10.html)支持面向讀者及持續維護。查閱：2026-09-29。

## 2. 程式邊界：模組化單體優先

架構採本機 Web、內含明確業務模組的單一 App 後端、PostgreSQL 與外部 Responses API。A 與背景 Graph 可透過非同步工作並行，同一職務檔案的寫入則依業務規則控制順序。AI 角色、工具、業務與持久化分別負責不同工作，不各自部署為獨立服務。

若採微服務或讓每個 AI 角色各自成為服務，會增加跨資料庫一致性、部署與診斷的負擔；若執行環境完全不分模組，則會讓 UI、模型與資料庫各自複製規則。因此保留明確的模組界線，不另建通用架構框架。

這項選擇借鑑 [AWS hexagonal pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/hexagonal-architecture.html)將業務與技術接線分開的方式，並不要求每層都有 adapter。只有實際部署、負載或獨立發版需求顯示單體有具體限制時，才需要重新評估服務拆分。

## 3. 保存：明確業務候選與不可變正式修訂，不以事件重播作唯一真相

正式訪談、JD／Memory 修訂與關係由業務模組保存於 PostgreSQL；可恢復的候選也由對應的資料模組保存。LangGraph checkpointer 保存執行進度、原生 items 及候選固定位置的引用，不另存第二份可獨立編輯的全文。供讀取或顯示的資料按需產生。詳見[資料與交易](persistence.md)。

候選需要支援單次修改的原子性、來源身分、B1／B2 共用工作稿、預覽與差異比較，以及 Step 恢復時的一致位置。候選與操作結果在同一保存邊界內，checkpoint 則記錄接續位置；恢復時可核對原結果，不讓兩種保存方式各自判定正式資料。

現行採「物件修訂重用 + 快照選用」保留固定歷史，無需額外版本框架：未變物件不重存，變動物件保存完整正文。這讓正文可直接讀取，但仍有重複文字的儲存成本；目前不做正文內容位址去重，是否需要壓縮或去重，尚缺真實容量量測。

其他做法各有代價：每版複製全部正文較簡單，但重複較多；Git 式差異鏈需要重建正文及更多格式／清理規則；event sourcing 則須維護事件版本與 replay 正確性。

## 4. 交易：短交易、條件提交、原操作核對

每次必須一起成立的內容由業務規則決定，並以 PostgreSQL 短交易執行。提交時檢查職務檔案或候選的有效資格及預期版本，防止過期操作生效；唯一約束則避免操作重複。僅設定 Serializable 不足以解決所有流程問題，也不能在等待模型回應時持有交易。

[PostgreSQL transactions](https://www.postgresql.org/docs/current/tutorial-transactions.html)支持原子／持久保存；[isolation](https://www.postgresql.org/docs/current/transaction-iso.html)說明讀取隔離及重試責任。鎖與隔離級別的適用性取決於真資料庫競爭測試，Graph checkpoint 本身不提供資料庫交易保證。選型採 PostgreSQL 18；相容性與鎖定依賴見[技術選型](../implementation/technology-decisions.md)，實際部署環境見[後端說明](../../apps/api/README.md)，證據範圍見[反例矩陣](verification.md)。

正式 A 完成與 Memory 待處理上界同次持久成立；調度從該業務事實恢復，不另設外部 broker 或第二套 outbox。[AWS transactional outbox](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html)揭示寫 DB 與發通知的雙寫風險；本案以可重掃的正式待處理事實解決同一問題，不宣稱已導入完整 outbox 平台。

## 5. 模型執行：以既有框架整合產品流程

現行採用 LangGraph 與 OpenAI direct Responses SDK，不採 LangChain agent／message adapter 或 OpenAI Agents SDK。Graph 負責執行控制與 checkpoint，各角色的工具連接業務模組，原生模型輸出依原契約保存與重播。執行節點、SDK 傳輸格式、取消資格與模型容量詳見[共用執行設計](../specs/2026-09-27-shared-agent-execution-and-state-design.md)。

不新增通用模型供應商抽象層、第二套工作階段引擎、每步必填的工作狀態筆記或獨立的壓縮 AI 角色。只有實測反例顯示原生接續不足，才評估需要補充哪些分析資料；不可讀的推理內容不作為 App 可讀取的工作計畫。

**上下文控制權：** App 決定組裝與接續內容，框架／adapter 不另選歷史、不暗中摘要或換角色。使用 `store=false`，不使用 `previous_response_id`，由 App 明確提供接續 items。

驗證這項分工時，須核對 SDK 發送邊界的實際請求；僅看組裝前資料不足以排除隱含變換。這項驗證要求也不表示所有請求副本都永久保存。

App 仍可明確呼叫模型的原生能力。[OpenAI standalone compaction](https://developers.openai.com/api/docs/guides/compaction#standalone-compact-endpoint)允許送入完整視窗，並採用完整的返回視窗；其中加密的 compaction item 無法由人解讀。App 控制壓縮的觸發時機、範圍與安全採用條件，但不掌握供應商內部如何取捨內容。現行規則不啟用伺服器端自動壓縮，由 App 在完整 Step 交界達 160K 時主動壓縮，包含 Turn 內符合條件的交界。門檻與回退規則以[共用執行 §6.3](../specs/2026-09-27-shared-agent-execution-and-state-design.md#63-輪前主動壓縮與中途保險)為準；對話接續仍由 App 管理。

**已確認的目標調整，尚未實作：** 輪前使用 App 管理的文字摘要，輪中仍採全部原生 compact output；B1／B2 壓後只追加目前候選導覽。

這項調整回應長訪談實測中觀察到的問題：歷次 App 資料仍留在 compact 的返回視窗，而官方不允許自行裁切該結果。摘要內容及品質仍待設計，不能宣稱文字摘要保留了加密推理。此變更不新增壓縮 AI 角色或恢復框架，完整取捨見[輪前摘要與輪中壓縮](../specs/2026-10-04-context-summary-and-compaction-design.md)。

## 6. 工具與格式：依內容與操作選擇

工具用動賓 snake_case；模型只選目標／內容／引用意圖，App 注入範圍／版本／操作身分。Memory 長正文以物件工具承載 V4A；JD 短欄位及關係採型別化局部修改。map 用精簡 JSON，詳細 diff／閱讀長文用 Markdown。共同欄位與錯誤語意見[工具規範](../specs/2026-09-27-agent-tool-contract-design-research.md)，不另造全業務共用 `execute`。

## 7. 保持架構範圍有限

現行架構優先處理訪談、工作資訊累積、有據改稿與可靠保存。微服務、通用規則引擎、事件重播平台與跨機備份不在此範圍；各項設計的價值以能否改善核心流程判斷，不以元件數量衡量。

現行產品不承接舊架構資料，背景見 [ADR0079](../adr/0079-target-rebuild-production-cutover.md)。產品範圍見[產品概念](../product-concept.md)，測試結果見[驗證章節](verification.md)。
