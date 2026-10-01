# 產品與架構演進材料

回到[演進總覽](README.md)。以下按當時問題整理，保留設計、實測與後來改向的差別；不是用現在的架構替過去補寫理由。

## 前身專案與最初資料流

### 2026-03-19：先把職能基準 PDF 變成可處理的資料

最早可查提交不是 AI 顧問，而是 `jd-pdf-to-json`：把 OCS／iCAP 的版本、職務概況、工作內容、態度與補充事項轉為結構化 JSON，服務後續交換、檢索與分析。當時已要求代碼與名稱並存、不要把多筆資料串成一個字串。

**引用：**[初始 README 原文](../../archive/early-projects/2026-03-19-pdf-to-json-readme.md) §1–§7；[來源提交](../../archive/early-projects/README.md)。這是元件前身的資料設計，不是 Caliburn 整體產品已完成。

### 2026-03-27 至 05-15：真實 PDF 版型使解析假設失效

`S01 3D列印…` 的數字邊界、合併產出儲存格、跨頁多 T code 等，不能只靠一套過度壓平文字的假設處理。3/27 留下以 `3D` 開頭技能名稱的反例測試；5/13 補產出繼承測試；5/15 修正沒有 P-code 的跨頁資料誤建 Task。

資料模型也在 5/11 改為 **P-centric competency blocks**，同步修改 model、parser、validator、README 與 tests。因此這段不只有 bugfix，也包含「資料應以什麼單位表示」的重設計。

**引用：**[早期修改與精確 Git 出處](../../archive/early-projects/README.md#更早期程式修改線索)。目前能核對提交差異與部分測試程式；本次沒有重跑當時環境，不能聲稱所有歷史 PDF 已通過。

### 2026-05-20：JobIntel 用固定階段訪談形成 JD

原架構是 pgvector 參考檢索，接 LangGraph 的訪談、任務萃取、STAR、5W2H、行為指標、K/S/A 與文件產出。跨呼叫狀態放在 `graph_state`，不是後來的情境／理解分層 Memory。

當時文件保留了幾個已修正問題：用戶訊息達三則就前進、靠 AI 特定字串判定 STAR 結束、中文短答長度門檻過高、AI／user phase 過濾不一致造成重問、任務完成後錯誤重跑。也留下關鍵字 readiness 仍可能被亂答拉高的未決問題。

**引用：**[原架構與保存方式](../../archive/early-projects/2026-05-20-jobintel-architecture.md)、[原狀態機及 Review 結論](../../archive/early-projects/2026-05-20-jobintel-graph-pipeline.md)。原文的「已解決」是當時自述，不是本次測試。早期的補答／推斷機制亦不能當成現行允許猜測員工事實的規範。

### 2026-06-14 至 06-16：從檢索生成改為知識選單與顧問深問分工

當時流程明確區分「做哪些工作」與「每項工作怎麼做」：先從多個職類取得任務選單，再逐任務深問，K/S、態度與條件另處理。Indexer 提供無狀態知識；JobIntel 管使用者選擇、修改、訪談與產出。不是每一次取資料都做向量搜尋，未改過的標準項目可精確讀取。

控制流則研究以單一 LangGraph、`interrupt/resume` 與深問子圖取代中文關鍵字路由。這是當時選擇，不代表後來一直沿用同一圖。

**引用：**[6/14 流程與讀取分工](../../archive/jobintel-v3/specs/2026-06-14-jd-authoring-flow.md)、[6/16 決策日誌 D2–D9](../../archive/jobintel-v3/specs/2026-06-16-refactor-decision-log.md)、[當時架構](../../archive/jobintel-v3/specs/2026-06-16-jobintel-ai-v3-architecture.md)。檢索本身的問題另見[檢索沿革](retrieval.md)。

### 2026-06-18：保存設計曾由關聯表改向整份 JSONB

6/16 原先選「業務表＋工作態、write-through」，兩天後因實際任務／KSA 尚無獨立查詢需求，改成文件導向 MVP：工作態交 checkpointer，成果保存為有版本 JSONB。設計明記不能用 SQL 方便地查或改各任務，將來需要再正規化。

**引用：**[文件導向重設計](../../archive/jobintel-v3/specs/2026-06-18-db-document-centric-design.md) §1、§5–§6；[D25 及接續紀錄](../../archive/jobintel-v3/specs/2026-06-16-refactor-decision-log.md)。這可與 9 月 relational JD 的實際管理需求對照，不能寫成「JSONB 一定差，關聯式一定好」。

### 2026-06-27 至 06-28：三專案整合，同時釐清共用契約與依賴

PDF parser、indexer、JobIntel 原本分開。整合研究辨認出跨服務資料契約、API／Graph 雙向依賴，以及約 1,492 行 parser 類別的維護問題；因此規劃保留歷史的 monorepo、共用 OCS 契約、內外分層與分區 parser。

研究不只提出「拆檔」：parser 文件指出當時只有 11 個測試，宣稱的真實 PDF fixtures 並不存在，先補 characterization／golden 安全網再移動邏輯。Git 有 6/27 subtree 匯入及 6/28 section extractor 拆分；計畫中的 `Expected` 結果仍不能當成已執行 log。

**引用：**[6/27 架構研究](../../specs/2026-06-27-system-architecture-design.md)、[parser 問題、研究與取捨](../../research/retrieval/2026-06-28-pdf-to-json-transformer-decomposition-research.md)、[拆分計畫](../../plans/2026-06-28-phase3b-transformer-decomposition.md)。Git 線索：`91c52237`／`bae48a95`／`01168af7` 匯入三元件，`67041179` 拆 API／Web；`08c2a670`／`13678f13`／`0bfc468d` 拆解析區段。

## 訪談能跑，不代表會分析工作

### 2026-07-06：真人試訪指出「顧問」實際像填表機

逐字稿顯示系統按 11 個槽位前進：員工問「我要說什麼」未獲引導、答不出仍追同一格、氣話被填入等待瓶頸，並出現已說完卻不轉題。研究據此重看 BEI、職能編碼及對話／萃取分工，而不是只補幾句 prompt。

同一研究文件內又先後提出「顧問＋書記」及統一 agentic 顧問，後續才收斂到 ADR0027。文中的五個對抗案例測到 strict tool 的選項限制，**沒有證明訪談品質已改善**。

**引用：**[診斷、研究及方案翻修](../../specs/2026-07-06-consultant-not-formfiller-redesign-research.md) §1、§3、§7；[當時 v2 決策](../../adr/0027-interview-engine-v2-consultant-agent.md)。

### 2026-07-09：修好開場後，再出現零任務與態度轟炸

後續真人試訪記錄 **25 回合、0 任務／OPKS，卻有 39 條態度建議**。原文診斷職類選擇沒有接到任務建立，書記可寫的通道只剩態度；引用逐字正確，仍可能分類錯誤。這是「格式與引文檢查通過，不等於分析有效」的早期材料。

接著研究任務裁剪、既有 UI 選單與彈性流程，並把態度改為整體故事佐證。先前修好一個斷點，後續試訪才露出下一個，不應被壓成「一次設計就解決」。

**引用：**[試訪證據與因果診斷](../../specs/2026-07-09-interview-flow-task-curation-and-flexibility-research.md) §1–§3；[ADR0028](../../adr/0028-interview-flow-shared-ui-curation.md)。目前主要入口是當時診斷文件，不假稱本次已取得原 DB 全部逐字稿。

### 2026-07-14：長聊不產出，不只是模型能力不足

新手 persona 的 28 輪、70 分鐘訪談仍沒有 P（行為指標）。稽核找到多個接線問題：空白文件被權限檢查阻擋、行為指標 Skill 沒注入、`next_gap` 先走大量槽位導致 P 不可達，以及把任何寫入當成當前問題已有進度。

研究轉向事件議程、全寬接收一次回答中的多個訊號，讓固定帳本不再主導所有對話。這段可用來說明：**要檢查模型實際收到什麼，而不是只看 prompt／Skill 檔案寫得好不好。**

**引用：**[事故四項診斷與研究](../../specs/2026-07-14-interview-agenda-architecture-research.md) §1–§2；[事件議程決策](../../adr/0033-episode-agenda-consultant-tools.md)。該議程後來又被 vNext 部分取代，不能說沿用至今。

### 2026-07-16 至 07-20：Evidence workflow 與短答前後文

vNext 明確不再包裝舊 `consultant/scribe/harvest/select`，改以 observations、更正、reducer、提問與投影分工。後續又發現：只允許本輪員工逐字 quote，無法解釋「是」「每週」「主管」指向哪個問題，也會把「以前每週」誤標成現在。

當時選擇 QuestionFrame 與 literal／contextual support 來保留問題與回答的關係。這是**當時的修訂設計**，不是現在仍要求同名資料結構；與後來歷史訪談前問、原話回讀可一起取材。

**引用：**[vNext 與舊架構差異](../../specs/2026-07-16-interview-ai-vnext-greenfield-architecture.md) §1–§2；[短答研究](../../specs/2026-07-20-interview-vnext-professional-job-analysis-and-short-answer-architecture-research.md)；[ADR0037](../../adr/0037-interview-vnext-question-frame-contextual-evidence-and-employee-authority.md)。

### 2026-07-26 至 07-30：用比較與減法收斂，不把複雜當進步

R1a 用八案比較三個實際執行的方案，共 24 observations；兩階段未取得預設的實質改善，任務拆分／合併仍有共通缺口，model grader 也漏判。之後以時程取捨暫留 A6 one-stage，並先接最小 durable 訪談閉環。

另有 **R1-P0 完全沒執行 trial**，只是保留凍結資產、依研究與 YAGNI 結案。這兩件事要分開：不能把未跑的 P0 寫成比較結果，也不能把停止後續實驗寫成所有方案都已驗完。

**引用：**[R1a 原結果](../../experiments/2026-07-27-r1-task-discovery/r1a-results.md)、[P0 結案](../../adr/0041-r1-p0-closure-first-version-context-and-holdout.md)、[時程裁決](../../adr/0042-r1-screening-stop-and-a6-first-version-default.md)、[最小閉環](../../adr/0046-professional-consultant-minimal-durable-loop.md)。

### 2026-08-01：來源支持、員工核准與資料結構不能混為一談

OPKS 研究先把單一支持度等級拆為來源與任務連結兩軸，隨後又決定由 refs 推導兩軸，避免持久化互相矛盾的標記；單純接受模型建議也不能變成新的員工事實。K/S 則改為文件層物件、與任務多對多。

**引用：**[ADR0048](../../adr/0048-opks-evidence-axes-and-document-level-competencies.md)、[下一次修正 ADR0049](../../adr/0049-opks-derived-axes-evidence-whitelist-and-document-authority.md)、[8/2 smoke](../../experiments/2026-08-02-opks-attributed-live-smoke/README.md)、[8/6 progressive elicitation smoke](../../experiments/2026-08-06-opks-progressive-elicitation-live-smoke/README.md)。兩批 smoke 有提交結果，但原件均標示 `quality_eligible=false`，不能當正式品質證據。

## 編輯、保存與整體權責持續更換

### 2026-08-12 至 08-14：減少自己維護的狀態與生命週期

舊實作為 Work Model、Focus、Progress、Proposal、Current JD 等建立各自的機制。研究後改採 LangChain／LangGraph 的既有 loop、state、checkpointer／Store 與必要薄政策，不再只包住舊 writers。

當時記錄四個機制目的 probe 與 PostgreSQL Saver／Store 測試，並明說是 **conformance，不是模型品質 eval**。這與後來重建採 direct Responses 的選擇不同，兩者不能合成「一開始就這樣設計」。

**引用：**[產品流程研究](../../specs/2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md)、[ADR0060 脈絡與取代範圍](../../adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md)。

### 2026-08-21：巨型工具表單與模型定位錯誤，轉為虛擬工作區

真模型 smoke 先後碰到 integer sentinel、模型自填 UUID、重複 linkage、欄位錯置、quote offsets 不符。當時判斷不該讓模型為大量無關欄位填中性值，或替 App 做字元定位，因此借鑑 coding agent 的編輯方式，以 Deep Agents VFS 與 App 的 Evidence anchor 取代 mega-form。

**引用：**[問題、選型與邊界](../../adr/0064-deep-agents-virtual-jd-workspace-and-deterministic-evidence-anchor.md)、[研究](../../specs/2026-08-21-provider-neutral-virtual-jd-editor-and-evidence-anchor-research.md)、[live smoke](../../specs/2026-08-21-virtual-jd-workspace-live-smoke.md)。這是當時的工具簡化，並非現在要求 JD 一律用檔案工具。

### 2026-08-22 至 08-26：一次性候選，再改為持續且人機共用的工作面

VFS 解決部分編輯問題後，每輪仍從 approved 重建 candidate，未核准工作難以自然接續；因此先改成持久 working draft。接著人工 editor 與 AI workspace 又成為兩份競爭稿，rebase 衝突與 retry-only UI 不符合共同編輯的使用方式，才改成一個「目前 JD」主編輯面。

**引用：**[持久草稿 ADR0066](../../adr/0066-persistent-ai-jd-working-draft-and-semantic-review.md)、[完成紀錄](../../specs/2026-08-22-persistent-store-backed-jd-working-draft-completion.md)、[共用稿研究](../../specs/2026-08-25-shared-current-jd-working-copy-and-semantic-approval-research.md)、[ADR0069](../../adr/0069-shared-current-jd-working-copy-and-semantic-approval.md)。當時仍有 approved／semantic approval；後來再被修改，不能當現行 UX。

### 2026-09-09 至 09-12：能編文件，不等於能管理 JD 項目

Plate 候選以完整文件樹、JSONB revisions 與原生編輯承接 JD，曾完成有限隔離驗證。但 Owner 試看後指出它像一篇文件，職責、任務、成果、要求與 K/S 缺少清楚的獨立欄位和關係操作，於是轉向 relational JD 與結構化管理畫面。

**引用：**[Plate 候選及未採用界線](../../adr/0073-plate-jd-app-working-document-and-revision-authority.md)、[關聯式改向原因](../../adr/0075-relational-jd-authority-and-structured-editor.md)、[早期核心審查及修正](../../experiments/historical/20260918-analysis-only-agent/evidence/jd-editor-core-review/README.md)。0075 原文仍保留當時 Proposed 狀態；後續正式採用要看 0077，不改寫舊文。

### 2026-09-22：實作換了，正式入口也必須同步

新關聯式 App 已有分層實作／驗證，但根文件與命令仍把舊 apps/API/Web 呈現成正式產品。ADR0077 處理的是這個權責分裂：以 `experiments/jd-relational-app` 及 consultant-memory 作正式實作，退出舊可執行接線，保留研究歷史。

**引用：**[ADR0077](../../adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md)。目錄叫 `experiments` 不等於當時仍非正式；反過來，後來重新使用 `apps/api`／`apps/web` 也不代表舊架構復活。

### 2026-09-24 至 10-02：重新劃分新架構，再用實測檢查

新目標重新定義訪談、工作情境、工作理解與 JD 的分工，補上發布快照、引用差異、工具、Context、候選提交與恢復等契約，再拆成 T01–T18 施工。這不是把舊 A／B1／B2／C 接線原樣搬家。

後續留下 Prompt 候選比較、漏引、限流與長旅程中斷等新問題，詳既有近期案例與原始證據。架構文件、程式可跑、有限驗證、正式切換是不同狀態；本次基準下 ADR0079 仍是 Proposed。

**引用：**[分層架構討論](../../specs/2026-09-24-caliburn-layered-architecture-map.md)、[新目標地圖](../../target-architecture-map.md)、[計畫與驗收路由](../../plans/2026-09-29-target-rebuild/README.md)、[近期案例](../research-casebook.md)、[切換草案](../../adr/0079-target-rebuild-production-cutover.md)。

## 素材怎麼接著使用

目前不替這些歷史節點選「最佳故事」。例如「固定訪談 → 顧問重設計」可以沿 5 月、7/6、7/9、7/14 四份反例往下讀；「JSONB → relational」則要先說各時期的使用需求不同，不寫成技術排名。待原件與個人貢獻確認後，再決定正文與附錄。
