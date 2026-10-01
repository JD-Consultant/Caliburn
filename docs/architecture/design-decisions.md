# 目標工程設計取捨

- 狀態：**研究後工程建議／未實作、未驗收**；2026-09-29。Owner 授權整理架構文件與研究，不是施工或切換授權。
- 維護者：App 架構維護者。產品決策仍以[產品概念](../product-concept.md)與[決策沿革](../current-decisions.md)為準；本頁不改寫 Accepted ADR。
- 目的：讓後續工程代理知道為何選這個方向、何時才值得重開，不再把成熟機制當作新的產品問題逐項詢問。

## 1. 文件結構：多視角、單一責任、可逐層深入

選擇：短總覽 + 邏輯責任圖 + 專題責任文件 + 跨層生命週期 + 共同資料／運作／驗收。已有詳細契約維持唯一內容來源，不為改資料夾而再抄一份。日期檔名不決定狀態；導覽明列哪些是持續維護的責任文件，哪些只供沿革研究。

拒絕：一份超長全集、每輪新增「最終版」、所有內容按技術工具名排列。只在責任不同且內容可獨立維護時分檔；不為每個 CRUD 造一張圖或文件。

**讀者入口與工程權威分開（2026-09-29）：**README 簡述產品價值、現況及入口；[產品介紹](../product-introduction.md)用問題、旅程、設計解法與驗證回答「為何需要它」。它是對責任文件的解說，不另定規則。工程讀者由目標地圖進入，依圖的問題深入唯一 owner；圖稿與正文同檔維護，避免另外一份手抄架構。這借鑑 [GitHub README 指引](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes)的短入口及 [Diátaxis explanation](https://diataxis.fr/explanation/)面向理解的寫法，並非宣稱有唯一大型專案模板。依 [C4 圖面檢查](https://c4model.com/diagrams/checklist)補範圍、圖例、箭頭意義；依 arc42 runtime view 選代表性正常／異常時序，不畫每個函式。

依據：[C4](https://c4model.com/diagrams)按讀者問題逐層放大，且不必畫滿四層；[arc42 building blocks](https://docs.arc42.org/section-5/)描述責任及內部結構，[runtime view](https://docs.arc42.org/section-6/)補代表性互動。這支持多視角，不規定本案目錄名稱。[Microsoft 架構規格](https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-design-specification)支持業務目標、功能／非功能選擇、操作與驗證一併說清；[Google 文件工程](https://abseil.io/resources/swe-book/html/ch10.html)支持面向讀者及持續維護。查閱：2026-09-29。

## 2. 程式邊界：模組化單體優先

選擇：本機 Web + 單一 App 後端內的明確業務模組 + PostgreSQL + 外部 Responses API。A 與背景 Graph 可由異步工作並行，但同檔案寫入依業務准入序列化。Agent、tool、業務、持久化是責任，不先拆部署。

替代方案：微服務／每 Agent 一個服務會增加跨庫一致性、部署與診斷負擔；全部混成一個 runtime 則讓 UI、模型與 DB 各自複製規則。首版選中間的模組界線，不實現通用架構框架。

依據：[AWS hexagonal pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/hexagonal-architecture.html)可借用業務與技術接線分離，但不能由此推導每層都需要 adapter。重開條件：實際部署／負載／獨立發版需求證明單體有具體限制。

## 3. 保存：明確業務候選與不可變正式修訂，不以事件重播作唯一真相

選擇：PostgreSQL 中的正式訪談、JD／Memory 修訂與關係由業務保存；可恢復候選也由相應業務 owner 保存。LangGraph checkpointer 保存執行進度、原生 items 及候選固定位置的引用，不再保存第二份可獨立編輯的全文。投影按需生成。詳見[資料與交易](persistence.md)。

原因不只是「外部也要讀」：這些候選需要同次 CRUD 原子性、來源身分、兩個 Agent 的同一工作稿、預覽／差異與 Step 回復到一致位置。業務候選與操作結果在同一保存邊界，恢復時更易核對。若實測 checkpoint-backed 候選同樣滿足這些效果且更簡單，可替換內部表示，不改產品規則；不能兩邊都成 owner。

比較：全版全文複製簡單但重複；Git 式差異鏈需要重建與更多格式／清理規則；event sourcing 需要事件版本與 replay 正確性。首選「物件修訂重用 + 快照選用」已足以保留固定歷史，無需額外版本框架。暫不做正文內容位址去重；未變物件不重存，變動物件保存完整正文，之後以真實容量決定是否增加壓縮／去重，不能捏造容量估算。

## 4. 交易：短交易、條件提交、原操作核對

選擇：業務指定一次必須一致成立的內容，由短 PostgreSQL transaction 執行；以檔案／候選目前資格與預期版本條件防止過期提交，唯一約束保護操作去重。不是「設定 Serializable 就解決所有流程」，也不在模型等待期間持有 transaction。

[PostgreSQL transactions](https://www.postgresql.org/docs/current/tutorial-transactions.html)支持原子／持久保存；[isolation](https://www.postgresql.org/docs/current/transaction-iso.html)說明讀取隔離及重試責任。應以真資料庫競爭測試選鎖與隔離級別，不能由 Graph checkpoint 推導資料庫交易保證。研究核對 PostgreSQL 18 的相關契約；施工時再核對並鎖定受支援穩定版本，不以「版本較新」為由直接採用預覽版。

正式 A 完成與 Memory 待處理上界同次持久成立；調度從該業務事實恢復，首版不必有外部 broker 或第二套 outbox。[AWS transactional outbox](https://docs.aws.amazon.com/prescriptive-guidance/latest/cloud-design-patterns/transactional-outbox.html)揭示寫 DB 與發通知的雙寫風險；本案以可重掃的正式待處理事實解決同一問題，不宣稱已導入完整 outbox 平台。

## 5. Agent 機制：已選框架內薄接線

LangGraph + OpenAI direct Responses SDK 是已確認的方向；不採 LangChain agent／message adapter 或 OpenAI Agents SDK。Graph 管控制與 checkpoint；角色工具接業務；原生模型輸出按原契約保存與重播。工程節點、SDK wire、取消資格與模型容量由[共用執行設計](../specs/2026-09-27-shared-agent-execution-and-state-design.md)維護。

不新增通用 provider abstraction、第二套 session engine、每步必填 Working State 或獨立 compaction Agent。原生接續不足以解決哪個實測反例時，才討論補什麼分析資料；不把 opaque reasoning 當 App 可讀取的工作計畫。

**上下文控制權（2026-09-29 產品方向補充）：**App 的組裝與接續契約是唯一政策來源；框架／adapter 不另選要保留的歷史、不暗中摘要或換角色。沿用 `store=false`、不使用 `previous_response_id` 的已選方向，由 App 明確提供接續 items。實作須檢查 SDK 邊界的實際請求，不能只看 App 組裝前的資料就宣稱不存在隱含變換；不為此預設永久保存所有請求副本。

這不排斥明確委派給原生能力：[OpenAI standalone compaction](https://developers.openai.com/api/docs/guides/compaction#standalone-compact-endpoint)提供顯式呼叫、送入完整視窗及採用完整返回視窗的方式；其加密 compaction item 不供人解讀。2026-09-29 已核對官方頁，2026-10-01 依 Owner 決策校準門檻。本案保留這項已選能力，App 控制觸發／範圍／安全採用，不宣稱可掌握供應商內部取捨。**不啟用的是 server-side 自動壓縮；App 在完整 Step 交界按 160K 主動壓縮已獲確認**，不可再寫成所有 Turn 內壓縮都被否決。唯一門檻及回退語意見[共用執行 §6.3](../specs/2026-09-27-shared-agent-execution-and-state-design.md#63-輪前主動壓縮與中途保險)。這是可控的委派，不是未知的對話代管。

## 6. 工具與格式：以任務效果選擇，不機械統一

工具用動賓 snake_case；模型只選目標／內容／引用意圖，App 注入範圍／版本／操作身分。Memory 長正文以物件工具承載 V4A；JD 短欄位及關係採型別化局部修改。map 用精簡 JSON，詳細 diff／閱讀長文用 Markdown。共同欄位與錯誤語意見[工具規範](../specs/2026-09-27-agent-tool-contract-design-research.md)，不另造全業務共用 `execute`。

## 7. 如何改變這些建議

效果等價的表、索引、函式切法或套件由工程代理研究並用反例驗證，記到責任文件；不用 Owner 選。若改變來源資格、歷史回查、取消／提交、外送範圍或可觀察產品效果，先提出差異再裁決。選型不得只因「更流行」重開；新證據必須指向具體收益或已知缺陷。

施工時按[決策流程](../decision-process.md)形成可驗證切片；本文件不是 implementation plan，也不授權遷移或刪除舊資料。
