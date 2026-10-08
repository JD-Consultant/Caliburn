# Caliburn 目前決策與維護狀態

本頁只維護目前採用、未決問題與責任文件。正式決策依 ADR 及其接續文件；完整規則、實驗數字與限制沿正文或原件查閱，不在本頁另立契約或驗收結論。

## 正式產品

- 正式程式為 `apps/api`、`apps/web`，依 [ADR0079](adr/0079-target-rebuild-production-cutover.md)取代 ADR0077；舊程式退役，不整合舊資料。T01–T18 已結案，取回方式見[歷史索引](history.md)。
- RAG 保持獨立，依 [ADR0080](adr/0080-opt-in-public-reference-agent-tools.md)以明示設定接入公版工具，不是預設啟動依賴；操作依 [runbook](runbook.md)。
- 產品模型採 Luna／high，不採 Sol 作預設或備援，依[技術選型](implementation/technology-decisions.md)。來源引用及分析品質仍依實驗判讀，不因工程結案宣稱普遍達標。
- 系統責任從[架構導覽](architecture/README.md)查閱，接線從[實作文件](implementation/README.md)查閱；已驗／未驗範圍由[驗證文件](architecture/verification.md)維護。

## 按主題查有效規則

| 主題 | 目前採用與重要界線 | 責任文件 |
|---|---|---|
| 職務檔案管理 | 建立、改名及確認刪除整份檔案；刪除含歷史且不可復原，有執行中或暫停工作時拒絕 | [檔案刪除](implementation/interview-storage.md#11-整份職務檔案刪除)、[清單介面](implementation/interface-and-delivery.md#11-讀寫邊界) |
| 訪談與 JD | 有效訪談、候選 JD 及正式完成分開；取消未完成工作不產生正式訪談資格 | [核心生命週期](specs/2026-09-29-core-value-loop-lifecycle.md)、[資料交易](architecture/persistence.md) |
| Memory | B1 整理情境，B2 分析理解，再發布；不回交 B1，A 讀固定發布快照。保留原話 → 情境 → 理解，單集合替代暫不推進 | [背景生命週期](specs/2026-09-25-b1-b2-information-gap-lifecycle.md)、[Memory 保存](implementation/memory-storage.md) |
| Memory 內容與選讀 | 依工作脈絡／意義組織，以可定位、可直接使用及可局部修訂決定粒度；一般已整理工作應由理解或情境支援，原話用於原句、歷史及具體疑點。正式 B2 只局部採用跨案數值副本規則，其餘方法未整體替換提示 | [方法與範例](guides/2026-09-09-complete-work-analysis-guide.md#107-收斂後的整理與選讀準則)、[閱讀停止條件](specs/2026-09-27-memory-read-and-source-navigation-contract.md#a-顧問的閱讀與停止條件)、[採用範圍與證據](research/agent-systems/2026-10-05-demand-loaded-memory-and-incremental-updates.md#10-研究收斂與可重算證據) |
| Context 與恢復 | 現行輪前／輪中均用原生 compaction；輪前 App 文字摘要屬已確認、尚未實作目標 | [顧問 Context](specs/2026-09-26-consultant-context-and-state-design.md)、[共用執行](specs/2026-09-27-shared-agent-execution-and-state-design.md)、[摘要目標](specs/2026-10-04-context-summary-and-compaction-design.md) |
| 容量與重試 | 容量、次數及時間上限分開；產品不以預估金額攔截正常執行，付費驗證另管預算，限流依等待政策 | [執行接線](implementation/agent-execution.md)、[技術選型](implementation/technology-decisions.md) |
| 模型工具與定位 | 模型只填分析參數，App 綁定身分、範圍及版本。JD 使用短定位、資料庫保留 UUID；Memory 沿標題定位、候選讀寫及 V4A，不混用 | [共同工具規範](specs/2026-09-27-agent-tool-contract-design-research.md)、[JD 保存](implementation/jd-storage.md)、[Memory 讀取](specs/2026-09-27-memory-read-and-source-navigation-contract.md)與[更新](specs/2026-09-27-memory-object-update-tool-contract.md) |
| JD 依據與變更 | 引用核對須明確提交，看過 diff 不會自動清除待核對；Changes 與 Plan 各自獨立 | [JD 工具](specs/2026-09-29-jd-model-tool-contract-review.md)、[JD 工作計畫](specs/jd-work-plan.md) |
| 顧問增量整理 | 沿既有 Prompt 掌握輪廓、逐題深入及增量編修；不要求每輪改稿，但沒有新事實不代表既有事實已整理完。主要工作充分處理後才按需查公版與收尾，不新增角色、Skill 載入、資料表或固定分組數 | [訪談節奏](guides/2026-09-09-customized-jd-depth-and-interview-calibration.md#訪談節奏與-jd-的形成)、[內容方法](guides/2026-09-09-jd-field-and-writing-guide.md#增量整理調整分組也修正受影響的概述) |
| 工作條件與選問 | 正常流程清楚不等於重要條件已探索；分清答不出與尚未探索，以及可改稿、可轉題、可收尾。集中重排 Prompt 與隔離選問候選未採用，既有分組、知識技能及條件指引保留 | [三種判準](guides/2026-09-09-customized-jd-depth-and-interview-calibration.md#可改稿可轉題與可收尾是三種判準)、[條件比較](experiments/product-validation/data/jd-condition-exploration-2026-10-07/results.md)、[選問比較](experiments/product-validation/data/jd-question-selection-2026-10-07/2026-10-07-priority-probe-results.md) |
| JD 工作計畫 | ADR0082 部分取代 ADR0081 的未知限定；同一顧問用 Markdown 保留主要方向、焦點及剩餘訪談／分析／JD 編修工作。原保存與恢復契約保持，工程與有限比較已結案 | [ADR0082](adr/0082-consultant-jd-work-plan.md)、[Plan 現行契約](specs/jd-work-plan.md)、[工程證據](plans/evidence/jd-work-plan-2026-10-08.md) |
| 公開過程與推理摘要 | 可串流及回看，與完整答覆和訪談來源資格分開；不公開完整內部推理 | [介面與交付](implementation/interface-and-delivery.md) |
| 本機交付 | 原生啟動及 Docker 基本／公版模式沿同一正式 App 與 PostgreSQL；不自動搬移資料或建立索引 | [Docker 交付](implementation/interface-and-delivery.md#42-docker-交付)、[操作手冊](runbook.md#docker-操作)、[驗證範圍](experiments/engineering/2026-10-06-docker-rag-startup.md) |
| 工程與文件維護 | 高內聚、低耦合、可讀、可測及可診斷為基線，工程與產品品質分別驗收。MCP、插件、harness 及觀測／評測平台依實際用途選用；避免過度設計不是技術禁令 | [程式組織](implementation/code-organization.md)、[寫法規範](implementation/coding-standard.md)、[開發規範](implementation/development-standard.md)、[文件規範](implementation/documentation-standard.md) |

## 獨立 RAG 與公版參考

### 目前採用

| 範圍 | 目前狀態與唯一契約 | 證據入口 |
|---|---|---|
| PDF → JSON | 已授權轉換／補齊，保留 pdfplumber；單次抽取、內容／來源檢核與失敗隔離已實作，原 JSON 保留。契約見[解析設計](specs/2026-10-03-public-ocs-pdf-to-json-design.md) | [工具比較](experiments/2026-10-03-ocs-pdf-parser-comparison/report.md)、[批次補齊](experiments/2026-10-04-ocs-json-repair/README.md) |
| 公版檢索 API | 獨立 API 已實作，以原話 D20／T20 完整聯集至 rerank 為控制初值，回傳最多五份去重公版、完整已解析目錄及固定來源正文。正式 HTTP／檢索契約見[公版 API](specs/2026-10-05-occupation-reference-api-design.md)；初值不代表通用最佳品質參數 | [API 驗證](experiments/engineering/README.md#公版參考-api)、[檢索比較原件](experiments/README.md#檢索與資料處理) |
| App／Agent 可選查讀 | 沿 [ADR0080](adr/0080-opt-in-public-reference-agent-tools.md)明示啟用。選用集合與明確否認範圍分開保存；未知、拒答及未回答不是沒做。A 可多選／不選、解除更正，B1／B2 依固定批次唯讀；不把否認自動拼入 query。工具、資格、保存與原請求相容性由[公版工具契約](specs/2026-10-04-public-reference-completion-design.md)維護 | [工具與角色驗證](experiments/engineering/README.md#公版參考工具)、[接續修正](experiments/engineering/2026-10-05-occupation-reference-tools/hardening-verification.md) |

### 未決問題

- 檢索品質仍未選出通用最佳輸入、切法、合併、rerank 或數量門檻。研究以主要工作領域代表性為目標，保留原話控制，B1／B2 與動態數量仍屬比較候選；不要求保留同面向每份已知公版。判準沿[搜尋定義](specs/2026-10-04-occupation-overview-reference-retrieval-design.md)與[逐份評分 v2](specs/2026-10-04-representative-occupation-scoring-protocol.md)，不把有限已知涵蓋稱作全庫 Recall。
- 公版以本人工作為準，可跨來源及多對多拆合；候選清單不是必問清單，相似度不是責任確認。額外責任、孤立動作及否認輸入仍有評分／檢索反例。資料、門檻與判讀限制沿[檢索實驗](experiments/README.md#檢索與資料處理)逐案核對。
- 當前優先整份 JD 收尾，單項任務完整度與細節機制暫緩；公版不自動宣告 JD 完成。無線索未知探索、避免重問、模型選公版、空白訪談至 JD／PDF 的效果仍待驗，沿[工具的後續範圍](specs/2026-10-04-public-reference-completion-design.md#驗證與後續範圍)。
- 候選概覽 → 完整目錄 → 必要正文的[三層取用方向](specs/2026-10-05-jd-and-reference-demand-loading-design.md)已確認，搜尋投影尚未切換。字元量測不代替模型選讀、token、耗時及 JD 品質驗證。
- PDF 官方最新狀態、全部逐字品質與未支援版型尚未全面驗收，沿[補齊紀錄](experiments/2026-10-04-ocs-json-repair/README.md)處理。

### 下一步去向

檢索接續先沿[職位整體搜尋](specs/2026-10-04-occupation-overview-reference-retrieval-design.md)與[實驗原件](experiments/README.md#檢索與資料處理)定位輸入、資料單位及廣蒐／rerank 反例，再比較新案例、fresh 時間與品質取捨；額外決策模型或直接交主 LLM 的比較在其後。收尾及按需取用沿各自設計驗證，不因 API 工程通過而切換品質政策。

## 尚需處理或保留的限制

以下是後續維護入口，不重開已結案的 T01–T18 或 Plan 比較。

| 項目 | 目前狀態及接續方式 |
|---|---|
| JD 工作計畫品質 | 有限比較未見可辨整體增益，不能證明穩定改善。未探索方向／選問、計畫與成品一致、打斷／換窗回收及維護負擔，沿[架構待辦](architecture/verification.md#41-jd-工作計畫後續待辦)討論與最小驗證；舊未知筆記八案不是現行方案效果證據，不自動恢復八場或採用新 Prompt |
| 訪談與 JD 分析品質 | 增量整理的局部及完整旅程證據見[局部比較](experiments/product-validation/data/jd-analysis-followup-2026-10-06/results.md)與[完整旅程](experiments/product-validation/data/jd-analysis-full-journey-2026-10-06/results.md)。冷藏、錯儲位及旺季漏問仍待改善；來源選擇有跨輪漏引、未提交核對及定位錯誤反例，短 ID 不等於語意品質改善 |
| Memory 效果 | [分層與原話比較](experiments/product-validation/data/memory-layered-value-2026-10-05/results.md)、[局部修訂](experiments/product-validation/data/memory-local-preservation-2026-10-05/results.md)、[閱讀策略](experiments/product-validation/data/memory-reading-policy-2026-10-04/results.md)及[換窗比較](experiments/product-validation/data/context-reset-comparison-2026-10-05/results.md)分開判讀。局部充分性／停止規則不代表全稿等價、超容量或成本優勢，完整正式提示組合尚未重跑真模型；早期精確／歷史回查另見[原件](experiments/product-validation/data/early-interview-recall-2026-10-05/results.md) |
| 輪前接續摘要 | 方式與時點已確認，尚未實作／驗收；保留內容、Prompt、長度、容量及品質處置待討論，不以文字摘要冒充加密推理或正式來源，見[摘要契約](specs/2026-10-04-context-summary-and-compaction-design.md#7-下一個討論與驗證範圍) |
| 長任務與重問候選 | JD 是總目標，子任務可新增、拆合及反覆修訂；必要排除範圍主動提供、短接續點及用途導向收尾仍沿[任務 state 研究](research/agent-systems/2026-10-05-adaptive-jd-task-state-and-repeated-questions.md)與[收斂研究](research/work-analysis/2026-10-05-jd-long-task-convergence.md)討論，不為每份公版建立必問進度表。先驗固定快照反例，再驗完整旅程 |
| Memory 最終失敗後的整理時機 | 現行正式訪談再前進三輪才允許一次新批次，政策仍待確認；不阻止 A 繼續訪談，見[背景調度](implementation/agent-supervision.md#5-memory-背景工作) |
| 示範服務與部署 | 短 ID 仍需在示範 DB 升級、重啟後確認；近期 Prompt 修改未更新既有 Docker，本輪[全系統重構](plans/2026-10-08-full-system-review-and-refactoring.md)未部署至共用服務。依[後端 README](../apps/api/README.md)及 [runbook](runbook.md)在安全點處理 |
| 實測範圍 | 跨職務長旅程、正式容量邊界及真人省時仍有未驗範圍；B1／B2 小型真模型壓縮後發布／固定回讀等已驗項目，沿[驗證範圍](architecture/verification.md)及[證據索引](experiments/product-validation/2026-10-04-report-evidence-audit.md)查閱 |
| PDF 與報告 | 部分字型的複製／搜尋限制沿[介面與交付](implementation/interface-and-delivery.md)追蹤。專題報告目前為 [Markdown 主稿](reports/project-report/report.md)，尚未製作報告 PDF；個人分工及送件草稿留本機 |

## 歷史與更新方式

完整沿革見[歷史查閱方式](history.md)。「當時未完成」「本輪授權」等文字屬原時點情境，不覆蓋較後決策。後續先維護責任契約和證據，再更新本頁狀態與路由；重大取捨依[決策流程](decision-process.md)，Accepted ADR 保留原意。
