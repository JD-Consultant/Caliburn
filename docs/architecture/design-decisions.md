# 目標工程設計取捨

- 狀態：**現行產品架構及設計要求**；核對日期：2026-10-02。正式後端為 [`apps/api`](../../apps/api/README.md)，介面為 [`apps/web`](../../apps/web/README.md)；切換依據為 Accepted [ADR0079](../adr/0079-target-rebuild-production-cutover.md)。設計要求不等於逐項已驗證，與實作仍有差異處另行標示。
- 驗證範圍：T01–T18 已標記完成，但不代表所有驗收情境通過。逐項實測與限制見 [T17 V01–V28 對照](../plans/2026-09-29-target-rebuild/evidence/t17-v01-v28-closure.md)及[實驗發現的問題](../reports/experiment-findings.md)；分析品質、真人使用效果與未覆蓋分支仍須分別評估。
- 維護者：應用程式架構維護者。產品決策仍以[產品概念](../product-concept.md)與[決策沿革](../current-decisions.md)為準；本頁不改寫 Accepted ADR。
- 目的：說明架構選擇、替代方案、證據與重新評估條件，區分已採用機制與尚待驗證的效果。

## 1. 文件結構：多視角、單一責任、可逐層深入

文件以簡短總覽、邏輯分工圖及專題說明組成，並交代跨層生命週期、資料保存、運作與驗收。已有詳細契約保留單一內容來源，不因調整目錄而複製。檔名中的日期不決定文件是否仍有效；導覽會標明持續維護的設計文件與僅供沿革研究的資料。

不將所有內容集中成一份長文，也不在每輪討論後新增「最終版」，或完全依技術工具名稱分類。只有職責不同且內容可獨立維護時才分檔，不為每個 CRUD 操作另建圖表或文件。

**閱讀入口與正式規則分開（2026-09-29）：**README 簡述產品價值、現況及閱讀入口；[產品介紹](../product-introduction.md)透過問題、使用旅程、設計與驗證說明產品的用途，解釋既有規則而不另定規則。需要技術細節的讀者可由目標地圖進入對應的設計文件；圖稿與正文在同一檔案維護，避免出現重複的架構描述。這種安排借鑑 [GitHub README 指引](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes)的簡短入口及 [Diátaxis explanation](https://diataxis.fr/explanation/)著重理解的寫法，不視為大型專案唯一適用的模板。圖面依 [C4 檢查指引](https://c4model.com/diagrams/checklist)標示範圍、圖例與箭頭意義，並依 arc42 runtime view 選擇具代表性的正常與異常時序，不逐一繪製函式。

依據：[C4](https://c4model.com/diagrams)按讀者問題逐層放大，且不必畫滿四層；[arc42 building blocks](https://docs.arc42.org/section-5/)描述責任及內部結構，[runtime view](https://docs.arc42.org/section-6/)補代表性互動。這支持多視角，不規定本案目錄名稱。[Microsoft 架構規格](https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-design-specification)支持業務目標、功能／非功能選擇、操作與驗證一併說清；[Google 文件工程](https://abseil.io/resources/swe-book/html/ch10.html)支持面向讀者及持續維護。查閱：2026-09-29。

## 2. 程式邊界：模組化單體優先

架構採本機 Web、內含明確業務模組的單一 App 後端、PostgreSQL 與外部 Responses API。A 與背景 Graph 可透過非同步工作並行，同一職務檔案的寫入則依業務規則控制順序。AI 角色、工具、業務與持久化分別負責不同工作，不各自部署為獨立服務。

若採微服務或讓每個 AI 角色各自成為服務，會增加跨資料庫一致性、部署與診斷的負擔；若執行環境完全不分模組，則會讓 UI、模型與資料庫各自複製規則。首版因此保留明確的模組界線，不另建通用架構框架。

依據：[AWS hexagonal pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/hexagonal-architecture.html)可借用業務與技術接線分離，但不能由此推導每層都需要 adapter。重開條件：實際部署／負載／獨立發版需求證明單體有具體限制。

## 3. 保存：明確業務候選與不可變正式修訂，不以事件重播作唯一真相

正式訪談、JD／Memory 修訂與關係由業務模組保存於 PostgreSQL；可恢復的候選也由對應的資料模組保存。LangGraph checkpointer 保存執行進度、原生 items 及候選固定位置的引用，不另存第二份可獨立編輯的全文。供讀取或顯示的資料按需產生。詳見[資料與交易](persistence.md)。

這項選擇考慮的不只是其他模組的讀取需求。候選須支援單次 CRUD 的原子性、來源身分、兩個 AI 角色共用的工作稿、預覽與差異比較，以及 Step 恢復時的一致位置。候選與操作結果在同一保存邊界內，恢復時更容易核對。若實測證明以 checkpoint 保存候選也能達到相同效果，且機制更簡單，可以替換內部表示而不改變產品規則；兩種保存方式不能同時作為可獨立修改的正式資料來源。

比較：全版全文複製簡單但重複；Git 式差異鏈需要重建與更多格式／清理規則；event sourcing 需要事件版本與 replay 正確性。首選「物件修訂重用 + 快照選用」已足以保留固定歷史，無需額外版本框架。暫不做正文內容位址去重；未變物件不重存，變動物件保存完整正文，之後以真實容量決定是否增加壓縮／去重，不能捏造容量估算。

## 4. 交易：短交易、條件提交、原操作核對

每次必須一起成立的內容由業務規則決定，並以 PostgreSQL 短交易執行。提交時檢查職務檔案或候選的有效資格及預期版本，防止過期操作生效；唯一約束則避免操作重複。僅設定 Serializable 不足以解決所有流程問題，也不能在等待模型回應時持有交易。

[PostgreSQL transactions](https://www.postgresql.org/docs/current/tutorial-transactions.html)支持原子／持久保存；[isolation](https://www.postgresql.org/docs/current/transaction-iso.html)說明讀取隔離及重試責任。應以真資料庫競爭測試選鎖與隔離級別，不能由 Graph checkpoint 推導資料庫交易保證。選型採 PostgreSQL 18；相容性與鎖定依賴見[技術選型](../implementation/technology-decisions.md)，實際部署環境與驗證範圍以對應任務證據為準。

正式 A 完成與 Memory 待處理上界同次持久成立；調度從該業務事實恢復，首版不必有外部 broker 或第二套 outbox。[AWS transactional outbox](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html)揭示寫 DB 與發通知的雙寫風險；本案以可重掃的正式待處理事實解決同一問題，不宣稱已導入完整 outbox 平台。

<a id="5-agent-機制已選框架內薄接線"></a>
## 5. 模型執行：以既有框架整合產品流程

已確認採用 LangGraph 與 OpenAI direct Responses SDK，不採 LangChain agent／message adapter 或 OpenAI Agents SDK。Graph 負責執行控制與 checkpoint，各角色的工具連接業務模組，原生模型輸出依原契約保存與重播。執行節點、SDK 傳輸格式、取消資格與模型容量詳見[共用執行設計](../specs/2026-09-27-shared-agent-execution-and-state-design.md)。

不新增通用模型供應商抽象層、第二套工作階段引擎、每步必填的工作狀態筆記或獨立的壓縮 AI 角色。只有實測反例顯示原生接續不足，才評估需要補充哪些分析資料；不可讀的推理內容不作為 App 可讀取的工作計畫。

**上下文控制權（2026-09-29 產品方向補充）：**App 的組裝與接續契約是唯一政策來源；框架／adapter 不另選要保留的歷史、不暗中摘要或換角色。沿用 `store=false`、不使用 `previous_response_id` 的已選方向，由 App 明確提供接續 items。實作須檢查 SDK 邊界的實際請求，不能只看 App 組裝前的資料就宣稱不存在隱含變換；不為此預設永久保存所有請求副本。

App 仍可明確呼叫模型的原生能力。[OpenAI standalone compaction](https://developers.openai.com/api/docs/guides/compaction#standalone-compact-endpoint)允許送入完整視窗，並採用完整的返回視窗；其中加密的 compaction item 無法由人解讀。官方頁已於 2026-09-29 核對，門檻於 2026-10-01 依產品決策調整。App 控制壓縮的觸發時機、範圍與安全採用條件，但不掌握供應商內部如何取捨內容。已確認的規則是不啟用伺服器端自動壓縮，由 App 在完整 Step 交界按 160K 主動壓縮，因此 Turn 內壓縮並未全面排除。門檻與回退規則以[共用執行 §6.3](../specs/2026-09-27-shared-agent-execution-and-state-design.md#63-輪前主動壓縮與中途保險)為準；對話接續仍由 App 管理。

## 6. 工具與格式：以任務效果選擇，不機械統一

工具用動賓 snake_case；模型只選目標／內容／引用意圖，App 注入範圍／版本／操作身分。Memory 長正文以物件工具承載 V4A；JD 短欄位及關係採型別化局部修改。map 用精簡 JSON，詳細 diff／閱讀長文用 Markdown。共同欄位與錯誤語意見[工具規範](../specs/2026-09-27-agent-tool-contract-design-research.md)，不另造全業務共用 `execute`。

<a id="7-如何改變這些建議"></a>

## 7. 架構變更的評估條件

表、索引、函式與套件可在產品效果等價的前提下調整，並以反例驗證及責任文件記錄其依據。來源資格、歷史回查、取消／提交、外送範圍或可觀察產品效果的改變，屬於需由產品決策者評估的取捨。重新評估選型須有具體收益或已知缺陷的證據。

重大取捨依[決策流程](../decision-process.md)保留可追溯紀錄；正式切換不包含舊資料遷移或刪除，範圍依 ADR0079。
