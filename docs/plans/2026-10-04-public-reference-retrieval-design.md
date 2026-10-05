# 公版參考檢索設計與分段驗證計畫

> 由目前代理 inline 執行已授權的隔離研究，沿 superpowers:executing-plans；不新增 production 接線或提交；早期目錄核對未啟動付費模型，後續實驗依各自有效授權、事前協定與費用界線執行。

**Goal:** 先交付可核對的兩層參考設計與來源查閱原型，再逐元件驗證 Memory、檢索單位及參數；完整旅程至 PDF 保留為後續目標。

**Architecture:** 公版正文及來源只保存一份，工作與職位導覽共享固定引用。職位目錄能查其他未命中任務；目前文件命中不冒充任務片段匹配。

**Tech Stack:** 本輪 Python 標準庫及既有凍結 JSON／JSONL；後續 Qdrant、BGE-M3、BGE reranker 沿版本固定的研究基線比較。

**Spec:** [候選設計](../specs/2026-10-04-public-reference-retrieval-design.md)、[整體／任務收尾用途補充](../specs/2026-10-04-public-reference-completion-design.md)、[本輪協定](../experiments/2026-10-04-retrieval-reference-views/protocol.md)。

參考進度與新資料提供方式的方案比較見[研究紀錄](../research/retrieval/2026-10-04-public-reference-progress-and-context-selection.md)；推薦粒度與最小資料仍待討論／驗證，本計畫不因此取得新 production 接線授權。

**最新範圍（2026-10-04）：** 使用者決定先不補單項 JD 任務完整度分析／收尾機制，現行分析方法繼續使用；consumer 先以職位整體公版的任務目錄及確認進度協助整份 JD 收尾。工作任務細節參考與單項驗證留待後續，完整度判斷仍是候選且未實測。

**當前元件：** 先以[五份固定合成需求](../experiments/2026-10-04-representative-occupation-top5/README.md)討論怎麼找代表主要工作的公版，每員工／方法最終最高五份，逐份評分不相加；依[評分 v2](../specs/2026-10-04-representative-occupation-scoring-protocol.md)比較整段／分段與有無 rerank。[第一輪](../experiments/2026-10-04-representative-occupation-top5/run-01/README.md)已執行，整段 dense 暫留控制組，rerank 未呈現整體優勢，混合前後端未齊；接續[A 訪談原文四法](../experiments/2026-10-04-a-interview-occupation-retrieval/run-01/README.md)已完成三類同人初期／完整對照，無穩定增加強代表；[原話與發布B1 B2六組比較](../experiments/2026-10-04-memory-layer-retrieval/run-01/README.md)亦已完成；B2逐理解列下一輪候選，帳務有退步，全端仍缺後端。評審語意邊界、新案例及更新仍待驗，DB方案或相似度切線尚未選定。[職位整體搜尋設計](../specs/2026-10-04-occupation-overview-reference-retrieval-design.md)同步維護用途邊界。

## 本輪有界交付

- [x] 寫候選設計，區分現行 indexer、既有實測、兩層查閱目標及未驗能力。
- [x] `docs/experiments/2026-10-04-retrieval-reference-views/prepare.py`：先保存 manifest，再核來源 hash、建立單份原始來源、完整任務 group 目錄及 22 個兩層導覽，保留所有命中邊。
- [x] `docs/experiments/2026-10-04-retrieval-reference-views/verify.py`：獨立重算全部來源／目錄／22 結果；錯 hash、少 group、漏查詢邊、假片段匹配均拒絕。資料轉換／機制核對不冒充模型品質 TDD。
- [x] 保存 README、核對及唯讀 review，更新 current-decisions／specs 路由；核此前 132／69／86／96／78 份封存原件未變，封存本輪輸出。

## 後續依序執行

- [x] 保存五份固定員工需求草稿與[代表職位評分 v2](../specs/2026-10-04-representative-occupation-scoring-protocol.md)：主要領域為目標、員工全域前五、逐份分級不相加；v1 局部有用判準與七例保留沿革，沒有模型結果。
- [x] 使用者同意五案四組；[有界第一輪](../experiments/2026-10-04-representative-occupation-top5/run-01/README.md)已固定拆分／排序／模型／費用，執行前五對照。七規則例首輪 6／7、加近似失配例後同批 7／7；只屬回歸。49 唯一正文盲評與全部證據、計時、失敗保存，不宣稱全庫 Recall。
- [x] 依使用者要求比較三類 A 訪談原文的完整四法與同人第一則整段控制，保存[原件、分段及判讀](../experiments/2026-10-04-a-interview-occupation-retrieval/run-01/README.md)，未新增真人或全端訪談。
- [x] 使用者同意公版切chunk；[八案五法比較](../experiments/2026-10-04-public-chunk-retrieval/run-01/README.md)已執行。固定whole查詢，T/U保留概述，父候選20再留5；冷氣改善但全端／倉庫掉代表。整份維持控制，合併整份＋chunk尚未測，評審語意與正式參數未驗收。
- [x] 使用者同意員工分段×公版chunk；[八案十法交叉](../experiments/2026-10-04-query-chunk-cross-retrieval/run-01/README.md)完成。倉庫找回既有代表、冷氣保留改善、全端仍缺漏；48控制、240暖機與103pair保留，未選正式方案或相似度線。
- [ ] 先補領域粒度、額外責任及孤立動作 1／2 邊界的新評審反例；以相同工作事實比較主要工作查詢表示，R01 整段 dense 保留控制組，再以新案例驗證，不依本輪結果回改原答案。
- [x] [原話與發布B1／B2八案六法](../experiments/2026-10-04-memory-layer-retrieval/run-01/README.md)完成：同截止點、真Memory parent／PostgreSQL／provider，35情境、12理解。保存93查詢、完整805排名、48組前五及78唯一pair評分；16原話控制及144暖機核對，模型估算US$0.044934290。B2逐理解列下一輪候選，帳務退步及全端後端缺漏保留，沒有回改Memory或選出正式最佳。
- [x] [原話／B2×D/T/M與rerank十二法](../experiments/2026-10-05-memory-public-unit-retrieval/run-01/README.md)完成：96組480位置、158pair（113重用＋45新增、6引句抄錄修正不改分）；24控制、177460cosine、144無R＋144fresh R暖機通過。原話T-R找到前後端共同參考，但M截20／B2漏候選、R在其他案例退步；未選單一最佳。
- [x] [聯集保留至rerank重播](../experiments/2026-10-05-rerank-union-candidate-replay/run-01/README.md)完成：固定N20／K5，16組80位置、71既有盲評、48控制與551seal通過；原話找回全端共同參考，其他案例無一致改善。628／400是候選配對量、無fresh時間；零新增外送，不選正式方案。
- [x] [初搜N20／40／80](../experiments/2026-10-05-initial-retrieval-depth/run-01/README.md)完成：48組、12固定3來源／8已知面向、20控制及581seal通過。原話N20已保留全部已知，B2 N40補全端後端；H01無3不可判涵蓋。更深候選更多，無fresh時間或全庫Recall。冷氣B2已進初搜池、R掉前五，階段問題分開。
- [x] [B1整合／逐情境雙路](../experiments/2026-10-05-b1-dual-route-retrieval/run-01/README.md)完成：96組、63query，B1 N20 11/12、N40 12/12；原話N20已12/12。B1-W40／S40為485／2174候選配對，沒有本清單逐情境增益；離線新算558999cosine、83路及48深度控制、1318旧seal通過，H01未評，沒有fresh DB／R／時間或全庫Recall。
- [ ] 下一檢索小切片：原話D20/T20維持控制，B1整合與B2逐理解D40/T40作候選，先比較reranker針對主要工作代表性的適配與最終K5，再驗fresh品質／時間及新holdout；固定新協定／費用，不將回歸值當通用正式參數。
- [ ] 輸入比較後，再加入更新前後、新增次要工作、更正責任、純重述／改名、拆合及同正文而來源改變，驗完整查詢重組／排名重用與本輪來源綁定，不先做語意增量引擎。
- [ ] 凍結支持片段標註後比較文件候選內定位、直接任務群組檢索，驗相關內容減量與來源涵蓋。
- [ ] 在選定輸入／單位上比較 DB 方案及參數、exact／ANN 排名與時間；不能直接搬用旧 N20／K5 品質结論。
- [ ] 檢索後額外決策模型／直接交顧問、按需查閱及未知線索實驗。原本要問的「是否做這項工作」比較自由文字／LLM 解讀與員工直接選答，分別驗部分責任、未知、操作時間及模型成本，不把所有檢索任務做成問卷。先設計 App 保存整體任務目錄的確認結果、依據及訪談中進度，驗已處理線索不重問、Memory 更新不全清進度、局部重核、多對多／部分適用及取消／恢復；任務細節用途留待後續。正式接線仍另訂契約，不提前實作。
- [ ] 補測分析方法是否主動發現未知；優先比較有／無職位整體參考及確認進度對整份 JD 收尾的效果，納入公版／JD 多對多、部分涵蓋及公版外實際工作反例；單項任務完整度及細節參考比較暫緩。最終從空白檔案完整訪談、JD 核對至正式 PDF，驗內容與排版。

## 下一輪原話與 B1 B2 輸入比較

**狀態：使用者已授權，2026-10-05完成[八案六組隔離比較](../experiments/2026-10-04-memory-layer-retrieval/run-01/README.md)，原件已封存；以下保留事前範圍。** 目的仍是找出能代表員工主要工作的公版職位參考；不把檢索成功當成 Memory 分析正確或 JD 已完整。

B1／B2 的內容與物件定義沿[產品概念](../product-concept.md#核心概念與資訊關係)、[工作分析指南 §9](../guides/2026-09-09-complete-work-analysis-guide.md#9-工作理解正文要寫到多清楚2026-09-25-研究補核對)及[固定關係網](../specs/2026-09-24-caliburn-layered-architecture-map.md#來源與版本)。B1 整理可辨認的事件、委託或例行流程，保留本人行動、判斷及條件；B2 從一個或多個情境形成有據的工作理解，保留責任範圍、共同模式、適用條件及重要例外。情境與理解可以多對多，B2 不等於把 B1 切得更短，也不預先對齊 JD 任務。

| 輸入層 | 整合搜尋 | 各自搜尋後合併 |
|---|---|---|
| 員工原話 | 同一截止點的員工回答及必要顧問問題合為一份 | 沿既有保留脈絡分段；顧問假設不當成員工事實 |
| B1 工作情境 | 同一已發布快照的情境正文合為一份 | 每個原有情境物件正文各查一次 |
| B2 工作理解 | 同一已發布快照的理解正文合為一份 | 每個原有理解物件正文各查一次 |

這是本輪事前固定的六組範圍，不按句子、動詞或固定字數重切 B1／B2。正文內容依現行分析角色形成；不能為命中特定公版而補入職稱、工作或專業詞。初輪 Memory 查詢使用 `body`，另保存 `title`、`description`、物件／修訂及來源關係供核對，不只用導覽標題作輸入。沒有對應快照的案例須先在隔離流程產生並核對 B1／B2，不手寫期待的職位答案冒充已發布 Memory。

先固定公版整份表示、embedding 模型與候選／合併規則，避免與公版 chunk 變因混在同輪；每員工／方法仍全域去重，保留最高五份，依固定原話事實逐份評分，不將分數相加。保存各物件查詢、逐查排名、合併前後排名及原始判讀；查詢 embedding、DB 搜尋、合併與 Memory 產生成本分開記錄。較少物件或較短正文不直接推成品質更好或總成本更低。

## Review Focus

來源變動不能讀成原版；共享能力區塊不能因多個 T 名稱變成多份證據；整體目錄不能再按已知工作向量過濾；本輪前五要看不同主要領域是否被重複或局部來源擠掉；公版未命中／資料抽取不全不能推成員工工作不存在或 JD 完成。舊次要主題涵蓋與新代表職位評分不可混算。
