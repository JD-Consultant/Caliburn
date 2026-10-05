# Caliburn 目前決策與維護狀態

本頁只列現行狀態及責任文件，不累積逐輪交接。正式決策以 ADR 及其接續文件為準；完整演進從[歷史索引](history.md)查閱。本頁不另訂產品規則或驗收結論。

## 正式產品

- 正式程式為 `apps/api`、`apps/web`。T01–T18 於 2026-10-02 結案並完成本機切換，依 [ADR0079](adr/0079-target-rebuild-production-cutover.md) 取代 ADR0077。
- 舊程式已退役，不整合舊資料。RAG 保持獨立，依 [ADR0080](adr/0080-opt-in-public-reference-agent-tools.md)可用明示設定接入公版工具，並非 JD App 預設啟動依賴；啟停依 [runbook](runbook.md)。
- 產品模型採 Luna／high；已決定不改用 Sol 作預設或備援。來源引用及分析品質的既有不足仍依實驗結果處理，不因工程結案宣稱普遍達標。
- [架構導覽](target-architecture-map.md)維護產品規則；[實作文件](implementation/README.md)維護程式接線；[產品驗證資料](experiments/product-validation/README.md)保留可核對的實驗原件。已結案施工存本機封存，不隨 Git 發布。

## 按主題查有效規則

| 主題 | 已確認的方向 | 責任文件 |
|---|---|---|
| 職務檔案管理 | 清單可建立、改名及確認刪除整份檔案；刪除含所屬歷史且不可復原，有執行中或暫停工作時拒絕 | [檔案刪除](implementation/interview-storage.md#11-整份職務檔案刪除)、[清單介面](implementation/interface-and-delivery.md#11-讀寫邊界) |
| 訪談與 JD | 有效訪談、候選 JD 及正式完成分開；取消未完成工作不產生正式訪談資格 | [核心生命週期](specs/2026-09-29-core-value-loop-lifecycle.md)、[資料交易](architecture/persistence.md) |
| Memory | B1 整理情境，B2 分析理解，再發布；不回交 B1，顧問讀固定的已發布快照 | [背景生命週期](specs/2026-09-25-b1-b2-information-gap-lifecycle.md)、[Memory 保存](implementation/memory-storage.md) |
| Memory 內容組織 | 2026-10-05 收斂：保留原話 → 情境 → 理解分層；B1 按工作脈絡整理，B2 按工作意義重組。以可定位、可直接使用、可局部修訂決定理解粒度，A 依當前工作範圍選讀。單集合替代暫不推進；方法及教材已更新。正式 B2 提示已局部加入跨案數值副本維護規則，其餘方法未整體替換 B1／B2 提示 | [分析分工](specs/2026-09-25-b1-b2-information-gap-lifecycle.md#分析分工與內容方法)、[方法與範例](guides/2026-09-09-complete-work-analysis-guide.md#107-收斂後的整理與選讀準則)、[研究收斂與採用證據](research/agent-systems/2026-10-05-demand-loaded-memory-and-incremental-updates.md#10-研究收斂與可重算證據)、[既有 B2 比較](experiments/product-validation/data/memory-organization-2026-10-05/capability-aligned-results.md) |
| Context 與恢復 | 現行輪前／輪中均用原生 compaction。已確認目標改為輪前按需 App 文字摘要、輪中原生 compaction；A 壓後不重加起始資料，B1／B2 只補目前候選 map。安全點、權限及回退保證不變；尚未實作，摘要 Prompt 待討論 | [輪前摘要與輪中壓縮](specs/2026-10-04-context-summary-and-compaction-design.md)、[顧問 Context](specs/2026-09-26-consultant-context-and-state-design.md)、[共用執行](specs/2026-09-27-shared-agent-execution-and-state-design.md) |
| 容量與重試 | 區分容量、次數及時間上限；產品不以預估金額攔截正常執行，付費驗證另管預算；限流按等待政策處理 | [執行接線](implementation/agent-execution.md)、[技術選型](implementation/technology-decisions.md) |
| 模型工具 | 模型只填分析需要的參數；App 綁定身分、範圍與版本；按需讀取，不重複大量內容 | [工具規範](specs/2026-09-27-agent-tool-contract-design-research.md) |
| JD 定位與依據 | 模型使用 App 配發的短定位，資料庫保留 UUID；引用核對仍須明確提交，不因看過 diff 自動清除待核對 | [JD 保存](implementation/jd-storage.md)、[JD 工具契約](specs/2026-09-29-jd-model-tool-contract-review.md) |
| Memory 定位與編輯 | 保留既定標題定位、候選讀寫與 V4A 正文編輯，不與 JD 短定位混用 | [讀取及來源](specs/2026-09-27-memory-read-and-source-navigation-contract.md)、[更新工具](specs/2026-09-27-memory-object-update-tool-contract.md) |
| 公開過程與推理摘要 | 可串流及回看；與完整正式答覆、訪談來源資格分開；不公開完整內部推理 | [介面與交付](implementation/interface-and-delivery.md) |
| 本機交付 | 原生啟動及 JD App 專用 Docker Compose，沿用同一份正式產品；不自動搬移既有資料 | [Docker 交付](implementation/interface-and-delivery.md#42-docker-交付)、[操作手冊](runbook.md#docker-操作) |
| 工程與文件維護 | 高內聚、低耦合、依風險驗證；責任文件不複製，已結案施工歸歷史 | [程式組織](implementation/code-organization.md)、[寫法規範](implementation/coding-standard.md)、[開發規範](implementation/development-standard.md) |
| 獨立 RAG：公版 PDF → JSON | 使用者已授權轉換／補齊；保留 pdfplumber，已實作單次抽取、內容／來源檢核及隔離失敗輸出，原有 JSON 保留。新資料與待處理版型見批次紀錄；官方最新狀態及全部逐字品質未驗收 | [元件設計](specs/2026-10-03-public-ocs-pdf-to-json-design.md)、[補齊紀錄](experiments/2026-10-04-ocs-json-repair/README.md)、[工具比較](experiments/2026-10-03-ocs-pdf-parser-comparison/report.md) |
| 獨立 RAG：員工工作 → 公版參考／完整度檢查 | 公版只作任務及整體客製 JD 完整度參考，允許跨多公版及任務拆合／多對多，以本人實際工作為準。當前先定義職位整體參考如何搜尋，收尾規則保留為用途參考；方向以職位整體任務目錄的確認進度協助整份 JD 收尾，原本要問的是否負責改由員工選答；現行分析方法繼續使用，單項任務完整度機制及細節參考暫緩。使用者要求先處理檢索與設計，暫不依賴無線索未知探索，該能力、收尾及空白訪談至 JD／PDF 留待補測。805 來源、22 舊情境的兩層目錄／查詢邊離線核對通過，未新增排名。先以固定合成需求比較主要職位代表性，再驗 Memory 輸入、資料單位與廣蒐＋rerank 參數，之後比較額外決策模型／直接交主 LLM。使用者最新指定比較能代表主要工作領域的公版，局部兼任不作主要目標；每員工／方法最終最高五份去重公版，0–3 分逐份列出不相加。五案四組前五及後續三類 A 訪談原文比較已執行：整段 dense 暫留控制基線。倉庫／採購在初期已找到同樣強代表，完整原文及 rerank 沒有穩定增加代表來源；評分的額外責任降級與孤立動作給2仍有疑義。公版切塊八案五法完成：冷氣前五改善，混合前後端與倉庫失去部分既有代表；整份保留控制基線，未選正式切法／合併，分段×chunk交叉八案十法完成：倉庫找回既有代表，冷氣保留改善，全端仍缺後端且丟前端；分段有局部效果，未選正式方案。整份＋chunk混合已在後續十二法比較，並不自動保證涵蓋。原話／現行發布B1／B2八案六法已比較：B2讓全端前端名次提升，但四個Memory帳務第一名均為0分，全端仍缺後端強代表；六案B2僅一物件，逐理解只列下一輪候選，沒有選出通用最佳。後續原話整段／B2逐理解×整份／任務／雙路M，再加rerank十二法完成：原話任務R找到同時支持前後端的網站系統設計公版；B2與M截前20漏掉它，rerank亦讓其他案例掉代表。原話需保留對照、B2單獨及必跑R未獲支持；完整聯集保留至rerank的八案重播已驗：原話找回全端共同參考，其他案例沒有一致改善；628／400配對增加57%，只重用品質logit，未證明fresh時間下降。初搜N20／40／80亦完成：原話N20保留12/12已知3來源、8/8已知面向，B2 N20 11/12與7/8、N40找回全端後端；H01無3不能判涵蓋，非全庫Recall。原話加深未增已知命中，配對量增加；冷氣B2 T7已召回但R排17。原話D20/T20保留控制、B2 D40/T40作候選；R適配、最終K5與fresh時間待驗，未選正式參數。B1雙路補測亦完成：整合／逐情境N20均11/12、N40均12/12，全端D29/T48；N40配對485／2174，逐情境沒有已知涵蓋增益。原話N20仍作控制，B1整合N40可接續精搜；離線新算、無fresh DB／R／時間，非全庫Recall。舊五案混合前後端未齊，不宣稱全庫 Recall。前輪原話段及逐句 86／86、合併 78／86 支持主題；N20／K5 仍是文件層研究候選，未採納正式參數、未接 JD 完成判斷 | [候選檢索設計](specs/2026-10-04-public-reference-retrieval-design.md)、[當前職位整體參考搜尋定義](specs/2026-10-04-occupation-overview-reference-retrieval-design.md)、[整體收尾優先／細節後續](specs/2026-10-04-public-reference-completion-design.md)、[參考進度／提供資料研究](research/retrieval/2026-10-04-public-reference-progress-and-context-selection.md)、[輸入與有效輸出評判研究](research/retrieval/2026-10-04-retrieval-relevance-judgment-methods.md)、[代表職位評分 v2](specs/2026-10-04-representative-occupation-scoring-protocol.md)、[B1雙路廣蒐](experiments/2026-10-05-b1-dual-route-retrieval/run-01/README.md)、[初搜深度比較](experiments/2026-10-05-initial-retrieval-depth/run-01/README.md)、[聯集保留至rerank重播](experiments/2026-10-05-rerank-union-candidate-replay/run-01/README.md)、[輸入×公版粒度／合併／rerank十二法](experiments/2026-10-05-memory-public-unit-retrieval/run-01/README.md)、[原話／發布B1 B2六組比較](experiments/2026-10-04-memory-layer-retrieval/run-01/README.md)、[分段×切塊交叉比較](experiments/2026-10-04-query-chunk-cross-retrieval/run-01/README.md)、[公版切塊／父合併比較](experiments/2026-10-04-public-chunk-retrieval/run-01/README.md)、[A 訪談原文／四法比較](experiments/2026-10-04-a-interview-occupation-retrieval/run-01/README.md)、[五案前五比較／第一輪結果](experiments/2026-10-04-representative-occupation-top5/run-01/README.md)、[兩層參考結構核對](experiments/2026-10-04-retrieval-reference-views/README.md)、[輸入邊界實驗](experiments/2026-10-04-retrieval-input-boundaries/README.md)、[每段候選實驗](experiments/2026-10-04-retrieval-passage-quota/README.md)、[前輪廣蒐＋精搜](experiments/2026-10-04-retrieve-rerank/README.md)、[候選覆蓋基線](experiments/2026-10-04-retrieval-coverage-baseline/README.md)、[第二輪原件](experiments/2026-10-04-occupation-retrieval-generalization/README.md)、[前輪選型](experiments/2026-10-04-occupation-retrieval/README.md) |

## 尚需處理或保留的限制

Memory 一般分析的充分性（2026-10-05，內容方向已確認）：已整理的現行工作應由理解或情境支援；原話保留給原句、歷史追溯及具體疑點查證，不作日常整理漏項的固定補救。[分析指南](guides/2026-09-09-complete-work-analysis-guide.md#104-小範圍足夠深理解應能直接使用)與[閱讀停止條件](specs/2026-09-27-memory-read-and-source-navigation-contract.md#a-顧問的閱讀與停止條件)已同步；[既有路徑核對](experiments/product-validation/data/early-interview-recall-2026-10-05/analysis/organized-work-sufficiency.md)區分一般工作與歷史題，不修改原判準／成績。後續[五對局部指引比較](experiments/product-validation/data/early-interview-recall-2026-10-05/reading-probe-01/README.md)完成：缺導覽時候選少讀一份情境 map，細節回答補回確認者，已有導覽時兩邊都未重讀。只支持局部候選，未改正式 Prompt／工具；本次占用 US$0.016609010，累計 US$1.442270635，外送已停止。

公版工具契約接續（2026-10-05，已授權並實作）：[原審核](experiments/engineering/2026-10-05-occupation-reference-tools/tool-contract-audit.md)三項反例已修正：全集合替換說明、各工具錯誤下一步、新寫入只回小型成功結果，完整 state 按需讀。舊 captured request 保留原回傳格式，重複／缺漏／格式混用在候選建立前拒絕；[回歸與獨立審查](experiments/engineering/2026-10-05-occupation-reference-tools/hardening-verification.md)維護本輪驗證。搜尋仍回完整目錄，三層概覽仍是比較設計；共用服務未重啟，未將工程驗證當模型品質驗收。

JD／公版按需取用（2026-10-05，WORKING／方向已確認）：使用者確認只拿當前需要的資訊，同意 JD 局部讀取、公版候選概覽 → 選讀完整任務目錄 → 必要正文。[設計稿](specs/2026-10-05-jd-and-reference-demand-loading-design.md)沿既有讀取與 state，候選概覽優先放 App 模型工具投影，保留任何候選的完整目錄可讀，不改 RAG 排名。[單案離線字元量測](experiments/2026-10-05-reference-context-projection/README.md)已完成；全讀五份時輸出反而增加。搜尋 wire 尚未切換；接續工具說明及寫入 hardening 另見上項，不重寫執行中請求。模型選讀、實際 token／耗時及 JD 品質比較後再決定三層取用正式切換。

動態 JD 任務與重問（2026-10-05，研究／候選）：使用者再次確認 JD 是總目標，底下工作可新增、拆合及修訂，沒有永久固定完成點。[多方研究](research/agent-systems/2026-10-05-adaptive-jd-task-state-and-repeated-questions.md)比較論文、OpenAI／Anthropic／Microsoft／Google 與 LangChain 公開做法，建議先驗必要排除範圍主動提供，另做短接續點消融。沿現有獨立否認 state，不為每項公版建立必問進度表；未改正式 context、提示、工具或新增模型結果。

長訪談換窗比較（2026-10-05，兩批完成）：[首批24段結果](experiments/product-validation/data/context-reset-comparison-2026-10-05/results.md)與[早期找回24段結果](experiments/product-validation/data/early-interview-recall-2026-10-05/results.md)已保存。補測確認理解可支援早期精確事實、歷史值可沿情境來源查回、三組JD局部更新與引用皆保留正確；兩批token差距不同，不能概括Memory一定省用量。105則原話皆放得下，尚無超容量勝出證據。[施測前協議](experiments/product-validation/2026-10-05-context-reset-comparison-design.md)與各批原件不覆寫；補測占用US$0.033961610，累計US$1.425661625，已停止外送。不改正式Context政策，不把腳本化測試當模型品質。

Memory 比較（2026-10-05，研究證據）：[三批分層與完整原話配對](experiments/product-validation/data/memory-layered-value-2026-10-05/results.md)已完成 6 次整理及 8 次作答；分層四題各讀一項理解、未展開下層，JD 15／16 完整，原話組 16／16。B1 保存 33／33，B2 31／33；跨案期限副本及一次接手分工省略已回饋分析指南。後續[五對局部修訂驗證](experiments/product-validation/data/memory-local-preservation-2026-10-05/results.md)中，新 B2 排除網站案例的舊期限副本，倉庫兩組皆符合；A 六次均保住指定內容、各讀一項理解，未重現分工漏項，候選窄題多一次 map 讀取。前批小材料 reading input 為原話組 3.17 倍，支持按需取用機制，不宣稱超容量或成本優勢。局部採用只涉及 B2 的兩句跨案數值規則，A 指引、正式工具與保存契約未變；完整正式提示組合尚未重跑真模型。另重算[同 Memory 的閱讀策略對照](experiments/product-validation/data/memory-reading-policy-2026-10-04/results.md)：共同完成三對 input 少 56.23%，指定核心事實均 33／33；支持充分性停止規則，不代表全稿品質等價。較早的[三批增量先導](experiments/product-validation/data/memory-structure-incremental-2026-10-05/results.md)、[自足單元配對](experiments/product-validation/data/memory-coherent-units-2026-10-05/results.md)與[顧問指引比較](experiments/product-validation/data/jd-scope-preservation-2026-10-05/results.md)保留原判準與結果，不合併成同一受控比較。

長任務收尾（2026-10-05，研究／未實作）：使用者提出子任務可反覆優化、沒有唯一完成答案。[JD 長任務收斂研究](research/work-analysis/2026-10-05-jd-long-task-convergence.md)比較動態分解、修訂回饋、必要條件及提問價值，推薦以具體未決問題推進、按目前用途判斷當前版本可交付，區分品質完成、暫停與相關新證據後局部重開。先以固定快照測誤收尾／不必要追問，再驗完整訪談至 PDF；論文與既有檢索實驗均未驗證 JD 收尾效果，未改正式顧問、單項任務細節機制或保存契約。

檢索數量優化（2026-10-05，研究）：使用者要求廣蒐也不預設TopK，已完成[271初搜規則、69末端選法與7038組快取交叉](experiments/2026-10-05-adaptive-reference-selection/run-01/README.md)。D5/T20在保留原12個已知代表下將247配對降至169；排除兩個原有疑義標註後，相似度下限加保底另有更省候選。動態門檻尚未通過新案例／fresh時間驗證，API控制參數未切換；本輪無新模型費用。

主要工作優先補充（2026-10-05，研究）：使用者再次確認公版應以主要工作為主，避免顧問無止境追問；檢索目標不要求同面向每份已知公版都保留。[主要面向重評](experiments/2026-10-05-adaptive-reference-selection/main-work-addendum-01/README.md)顯示原8/8已知面向條件仍至少留下11份弱主要參考，降至2份則漏掉視覺面向；目前沒有證明分數截斷足以同時保住主要工作並排除附帶參考。公版清單不是逐項必問清單；這是研究取向，未切換API或顧問行為。

否認輸入反例（2026-10-05，研究）：[三案24變體本機BGE實测](experiments/2026-10-05-negated-work-retrieval/run-01/README.md)顯示加入顧問問題及「沒有做」後，觀察公版D cosine及rerank logit三案皆高於原工作描述，兩案入最終前五；reranker對短否認相較僅問題有降分，但不足以移除前兩案。不能依相似度當成責任確認，建議將已確認主要工作查詢與否認範圍紀錄分開；未實作自動Memory投影、顧問不重問或否認生命週期。只用本機禁網模型，無付費LLM／外送。

否認內容早期方向（2026-10-05，研究沿革；現行切片以下文為準）：使用者先提出Memory與沒做紀錄分離，隨後放寬為允許保存但不得讓否認描述干擾工作檢索。比較與沿革見[隔離搜尋輸入](research/retrieval/2026-10-05-long-running-agent-progress.md#再次調整允許-memory-保留隔離搜尋輸入)。目前推薦先驗顧問從完整Memory組出有來源的已確認主要工作query，embedding／rerank均只用該query；否認與未知仍供LLM閱讀。衍生查詢保存／分欄及獨立否認紀錄仍是選項，未選正式格式；現行B1／B2與RAG接線未切換，抽取品質及顧問不重問尚未驗。

公版 consumer 最新確認（2026-10-05，再次簡化）：使用者確認只需避免重問，不保存回答來源或一般確認紀錄。改為獨立 `excluded_work`，記員工明確沒做／不負責的具體範圍，與 Memory 分開，不自動加入向量 query；員工更正可解除。未知、拒答與尚未回答不能當作沒做。最新責任以[只保留明確否認範圍](specs/2026-10-04-public-reference-completion-design.md#最新確認只保留明確否認的工作範圍)為準；已授權並完成可選角色接線，避免重問與收尾品質另以模型實驗評估。

主要參考選擇 state（2026-10-05）：目前兩欄為 `selected_reference_ids` 與 `excluded_work`。候選公版先看概述／任務目錄，可多選或不選，需要才讀正文；重選不清除否認範圍。採用、取消、重播及回復沿既有 Turn 資格。[工具契約](specs/2026-10-04-public-reference-completion-design.md#工具與保存契約未接模型)、[實作與驗證](experiments/engineering/README.md#公版參考工具)維護現況，前版回答來源方案留作沿革，不是並存工具。

Memory 排除範圍唯讀（2026-10-05）：`read_excluded_work({})` 沿既有 Memory binding／持久 F 讀取有效正式 state，不把後輪新增或更正帶回舊批次；沒有複製到 Memory 或增加寫入權限。[唯讀契約](specs/2026-10-04-public-reference-completion-design.md#memory-的排除範圍唯讀入口未接模型)與[元件驗證](experiments/engineering/2026-10-05-occupation-reference-tools/memory-read-verification.md)維護責任；接續[可選角色接線](experiments/engineering/README.md#角色接線)保留原請求工具清單，現有共用服務未重啟。

獨立 RAG API：2026-10-05 使用者已授權[公版職位參考 API](specs/2026-10-05-occupation-reference-api-design.md)
及必要重構，實作沿原話 D20/T20 完整聯集至 rerank 控制初值，提供最多五份去重公版、完整
已解析目錄及固定來源任務正文讀取。驗證與重播見[驗證紀錄](experiments/engineering/README.md#公版參考-api)。
App／Agent consumer 可由明示設定啟用，操作及恢復依 [ADR0080](adr/0080-opt-in-public-reference-agent-tools.md)；控制初值不升格為通用最佳品質參數，收尾效果另測。

以下不是重開已結案的 T01–T18，而是後續維護的定位入口。

| 項目 | 目前狀態及接續方式 |
|---|---|
| 短 ID 在示範服務啟用 | 程式、migration 與離線／真 PG 驗證已有紀錄；仍需在示範 DB 升級及重啟後確認啟用。依[後端 README](../apps/api/README.md)在安全點處理，實作契約見[JD 保存](implementation/jd-storage.md) |
| Luna 的來源選擇及核對 | 已有跨輪漏引、未提交對齊與定位錯誤反例。短 ID 不等於語意品質已改善；後續自然旅程須分別觀察。原件見[產品驗證資料](experiments/product-validation/README.md)，結果見[實驗彙整](reports/experiment-findings.md) |
| Memory 最終失敗後的整理時機 | 現行程式在有效訪談再前進三輪後允許新批次，這個政策仍待確認；不阻止顧問繼續訪談，見[背景生命週期](specs/2026-09-25-b1-b2-information-gap-lifecycle.md) |
| 輪前接續摘要 | 方式與時點已確認，尚未實作／驗收；保留內容、Prompt、長度、容量及品質處置仍待討論。不能以文字摘要冒充加密推理或正式來源，見[摘要契約與待討論範圍](specs/2026-10-04-context-summary-and-compaction-design.md#7-下一個討論與驗證範圍) |
| 實測範圍 | B1／B2 已補到小型真模型壓縮後發布與固定回讀；跨職務長旅程、正式容量邊界及真人省時仍有未驗範圍。見[驗證範圍](architecture/verification.md)與[報告證據索引](experiments/product-validation/2026-10-04-report-evidence-audit.md) |
| PDF 文字層 | 既有部分字型的複製／搜尋限制保留追蹤，見[介面與交付](implementation/interface-and-delivery.md)及[實驗彙整](reports/experiment-findings.md) |
| 專題報告 | 目前為 [Markdown 主稿](reports/project-report/report.md)；尚未製作專題報告 PDF。個人分工與送件草稿留在本機，不混入團隊報告正文 |

## 歷史與更新方式

完整沿革見[歷史查閱方式](history.md)。其中「當時未完成」「本輪授權」等文字均屬歷史情境，不覆蓋較後決策。

後續變更先維護相應契約和證據，再更新本頁的狀態或連結；不要重新累積逐日工作日誌。重大取捨依[決策流程](decision-process.md)記錄，Accepted ADR 保留原意，不因整理改寫。
