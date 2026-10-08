# 產品驗證與實驗資料

這裡保留專題報告使用的合成訪談、模型輸出、工具互動、指標、雜湊與分析程式。
先依下表找到問題，再讀該批方法與結果；需要核對時，沿同一批材料回查原始輸入、輸出及用量。

各批實驗有自己的程式與資料基準。腳本化模型、真模型子任務及完整訪談旅程支持的結論不同，不能只合併「通過」數量判斷產品品質。
已結案的施工清單和交接日誌不放在這裡；實驗原件不因後續修改產品而改寫。

## 按問題找資料

| 問題 | 保存資料 |
|---|---|
| 短大綱、焦點與剩餘成品工作，能否改善長任務的正式 JD？ | [JD 工作計畫有限比較](jd-work-plan-comparison-2026-10-07/runs/comparison-v2/results.md)：**倉儲各一場、各 20 輪完成，未見可辨整體品質增益**。兩組使用相同優化後指引，P2 加入 Plan；合成員工依實際問句披露固定事實，獨立 AI 匿名評閱。Plan 保存與跨輪接續成立，重要未探索缺口仍在；[實際比較方法與限制](jd-work-plan-comparison-2026-10-07/runs/comparison-v2/results.md#實際怎麼比較)分開交代。原八場排程由使用者縮減，先導及中止案例不列完整品質樣本 |
| 焦點與未釐清筆記能否改善長訪談的最後正式 JD？ | [指引／指引＋筆記比較](interview-plan-comparison-2026-10-07/results.md)：八案各完成 20 Turn 與共同收束；四個 P2 筆記皆非空、78 次編輯成功、零拒絕。四組品質判讀先鎖後解盲：P2 較好兩組、P1 較好一組、一組各有得失；八案均有重要缺口或錯誤，課務 r1 披露越界限制因果比較。精確換窗成立，未證穩定 JD 增益；舊格式失敗、短測與中斷全部保留 |
| 在可問缺口間比較答案對工作理解的影響，能否改善選問優先順序？ | [隔離實測](data/jd-question-selection-2026-10-07/2026-10-07-priority-probe-results.md)：24 案完成、匿名全鎖後解盲。直接目標問句兩版同 1／6，有限窗口取得／入稿原版 1／6、候選 0／6；末問未答與未問分開，候選未採用。12／12 界線核心行為維持，但正式分工及引用仍有限。時間取消後按原額度補完，新增估算 US$0.133723300；production 未切換 |
| 集中定義可改稿、可轉題與可收尾，能否改善重要條件探索？ | [選下一問與收尾對照](data/jd-question-selection-2026-10-07/results.md)：24 次回覆完成；五個指定探索案在短段窗口內舊版取得 2 件回答、新版 0 件，三個界線反例兩版均通過。這一版重排未採用，方法釐清與原件保留；估算占用 US$0.0730。未更新 Docker，不改前批結果 |
| 補清重要條件的探索指引，能否改善環境、常見差錯及負荷漏問？ | [工作條件探索對照](data/jd-condition-exploration-2026-10-07/results.md)：16 次首輪加 6 次同檔案接續完成；兩版首輪各 0／5 觸及指定面向、三個界線反例均未違反。接續新版在上架案問到負荷，但未穩定找到各案指定條件；不宣稱三項漏問已解決，不注入私人答案。估算占用 US$0.0573，後續聚焦結束深入與選下一問的判準 |
| 新顧問指引能否在完整訪談中實際分組、提煉能力並收尾？ | [新指引完整旅程](data/jd-analysis-full-journey-2026-10-06/results.md)：17 輪有效訪談、四組職責與六項任務、一項知識及一項技能、兩條能力關係；年度盤點由追問帶出，真 RAG、九版 Memory、58 筆來源回查與三頁 PDF 完成。明確核對三筆自然引用，唯一待核對為獨立人工探針；冷藏、錯儲位及旺季仍未問出。與前批是描述性比較，不當作所有隱藏工作已發現 |
| 不熟悉 JD 的員工能否經追問、公版查漏及背景整理完成訪談與交付？ | [完整模擬訪談與 RAG 結果](data/full-interview-rag-2026-10-06/results.md)：25 輪有效訪談、三版 Memory、真公版查漏、42 筆來源回查及三頁中文 PDF；最後完成供應商退貨跨欄更正與有保留的收尾。年度工作由員工補充，知識／技能及三筆待核對仍待處理，不將核心旅程成功當成專業完整度全部達標 |
| 如何改善職責總類過大、更正未同步概述、知識技能未提煉及低頻工作未被問出？ | [顧問增量整理對照](data/jd-analysis-followup-2026-10-06/results.md)：22 次真模型比較完成，初版未改善分組及能力；澄清「無新事實」不等於「已整理完」後，客服題形成兩項職責，能力題產生一項知識、一項技能及兩條任務關係，保留原任務與直接引用。單一工作及資訊不足回歸未強拆或硬改稿；年度探索及公版後完整收尾仍未驗。基準、一次修正、反例與用量分開記錄 |
| 如何避免多讀導覽，並保留已讀數值的確認責任？ | [五對唯讀問答](data/early-interview-recall-2026-10-05/reading-probe-01/README.md)：分開測工具說明與回答限定；缺導覽題讀取3→2、input少7.88%，細節候選補回確認者；已有導覽時兩邊均未重讀。每題僅一對，未改正式產品或驗JD保存 |
| 早期原話不在 Memory 組目前 Context 時，能否找回精確資訊及更正？ | [三組早期找回結果](data/early-interview-recall-2026-10-05/results.md)：24段完成，M首題選讀理解後4/4符合，歷史日期沿來源找回；三組JD更新及最終保留皆完成。M起始input較原話少45.93%，但累計多7.32%，不是全面省token或超容量勝出。[前批取用追查](data/context-reset-comparison-2026-10-05/analysis/early-recall-audit.md)另保留 |
| 大 Context 換窗後，原話、單層摘要與 Memory 如何延續中後期訪談？ | [三組真模型結果](data/context-reset-comparison-2026-10-05/results.md)：24段完成。Memory累計input比原話少21.0%，與摘要差1.4%；摘要／Memory最後修正跨欄舊值，原話仍有一處殘留。105則原話均放得下、未觸發compact，因此不是超容量勝出證據；[施測前設計](2026-10-05-context-reset-comparison-design.md)保持凍結 |
| 如何避免跨案舊數值殘留，並保住 JD 必要分工？ | [五對局部修訂驗證](data/memory-local-preservation-2026-10-05/results.md)：十次完成，新 B2 排除網站案例的舊期限副本；倉庫新舊均符合。A 六次均保住指定內容、各讀一項理解；候選窄題多讀一次 map。後續只採用 B2 兩句跨案規則，A 未切換，見[局部採用紀錄](data/memory-local-preservation-2026-10-05/execution-notes.md#後續採用2026-10-05) |
| 收斂後的 B1 → B2 能否承接增量資訊，讓顧問只選讀所需理解？ | [三批分層與完整原話配對](data/memory-layered-value-2026-10-05/results.md)：四題各讀一項理解、未展開下層；JD 15／16 完整，完整原話 16／16。B1 保存 33／33，B2 31／33，抓到跨案舊期限副本；reading input 為原話組 3.17 倍，支持按需機制，不宣稱小材料節省。正式提示未替換 |
| Memory 已讀到，如何保留 JD 必要限定又不帶入無關工作？ | [固定 Memory、顧問指引 16 次對照](data/jd-scope-preservation-2026-10-05/results.md)：原指引 21／25 完整，候選 24／25；局部片段兩組皆符合範圍。輸入少 12.36%，生成估算費用多 5.46%；仍有漏項與分數外的責任推論，未採用 |
| 理解單元帶齊必要限定、局部撤換舊說法，能否減少漏讀與錯用？ | [自足理解與局部修訂配對](data/memory-coherent-units-2026-10-05/results.md)：兩組保存均 33／33；候選閱讀 7→4 次、reading input 少 35.48%，但 JD 14 完整／2 部分，原方法 15 完整／1 部分。已結案，不以少讀宣稱品質等價，未切換產品 |
| 是否需要情境、理解兩套正文，或可直接維護工作理解集合？ | [三批增量先導結果](data/memory-structure-incremental-2026-10-05/results.md)：維護檢查雙層32完整／1錯誤、單集合33完整；單集合維護input少35.92%，但完成的閱讀題少了分工。第二題回覆格式失敗後停止，未切換產品 |
| 指引如何影響追問、JD 粒度與引用？長訪談如何延續？ | [24 份指引比較與 45 輪旅程](data/instruction-experiments-2026-10-01/README.md) |
| 舊指引、模型與推理設定的比較結果是什麼？ | [早期實驗索引](data/earlier-experiments-2026-10-01/INDEX.md) |
| 原生接續、Context、來源工具及換版核對如何驗證？ | [執行探測](data/runtime-probes-2026-10-01/README.md) |
| 用差異代替重複全文，對輸入量與完成率有何影響？ | [24 次來源差異子任務](data/source-diff-eval-2026-10-02/README.md) |
| B1／B2 壓縮是否生效？哪些部分尚未驗到？ | [背景壓縮觀察](data/b-role-compaction-2026-10-02/README.md) |
| 顧問在引導示範中讀了什麼、引用了什麼？ | [倉庫訪談原件](data/inventory-demo-guided-20261003/) |
| 來源核對指引與定位錯誤如何重現？ | [引用核對實驗原件](data/reference-alignment-prompt-20261003/) |
| Docker 是否可建置、保存 JD、匯出中文 PDF 並保留重建前的資料？ | [Docker 交付驗證](2026-10-03-docker-delivery.md) |
| 整份檔案刪除是否完整、隔離，並保留未結束工作與原文保護？ | [刪除驗證](2026-10-05-job-file-deletion.md)：真 PostgreSQL 交易、競爭及故障注入；介面與示範站檢查另列 |
| 現有 Docker 示範站是否已更新，錄影前還需要哪些準備？ | [10／5 更新檢查](2026-10-05-docker-demo-update.md)：新版映像、migration、畫面與 PDF 核對完成；完整訪談案例及公版服務接線仍待準備 |
| 報告各項成果有什麼證據，還缺哪種比較？ | [主張與證據索引](2026-10-04-report-evidence-audit.md) |
| 兩角色壓縮後能否接續分析、發布並回查舊稿？ | [Memory 兩組整合對照](data/memory-compaction-publish-2026-10-04/README.md) |
| 導覽按需閱讀與短定位是否減少輸入、保持所需事實及正確物件？ | [36 次真模型配對試驗](data/design-comparisons-2026-10-04/README.md) |
| 取消、來源核對、工具提交及壓縮等核心規則如何重驗？ | [163 項核心反例](data/mechanism-checks-2026-10-04/README.md) |
| 早期原話不在當次 Context 時，三層 Memory 能否保留並找回？ | [45 段重播與四組比較](data/long-interview-memory-2026-10-04/README.md)，分開呈現事實、原話序號與完整用量 |
| 原生 Compaction 搭配 Memory、摘要或原話按需回查，如何支援完整 JD 訪談及早期資訊？ | [長訪談組合比較](data/compaction-long-interview-2026-10-04/README.md)：主執行已停止，第一組保存 60／61 段與四批 Memory；已觀察壓縮及重複資料負擔，其餘三組未開始，沒有四組結論 |
| 完整原話已可容納時，額外 Memory 是否改善 JD 分析？ | [八次配對分析](data/memory-added-value-2026-10-04/results.md)：兩組核心判準均 42／42，未觀察到穩定額外收益；Memory 組總輸入多 37.3%，引用品質另行核對 |
| 近期原話＋Memory 能否替代每次提供完整原話？ | [八格替代價值比較](data/memory-replacement-value-2026-10-04/results.md)：完整組 4／4、近期組 3／4 交付；近期組首次輸入少 46.1%，累計多 148.1%，保存的資訊仍出現定位與雙重閱讀負擔 |
| 理解已足夠時停止深入，能否降低雙重閱讀？ | [新舊指引八格對照](data/memory-reading-policy-2026-10-04/results.md)：同材料、同工具，新組 4／4、舊組 3／4 交付；累計 input 少 60.1%，共同交付三對少 56.2%，跨欄位一致性仍另列反例 |
| 理解足夠、情境補缺與原話補缺時，是否正確停止與對齊任務？ | [六格讀取界線驗證](data/memory-reading-boundaries-2026-10-04/results.md)：理解／情境各兩格交付，20 項指定判準通過；原話兩格達研究上限未交付，另保留局部改寫的細節退化 |
| JD 局部更正與合理去重，能否保留有效期限、數值、狀態與責任界線？ | [有效資訊保留配對實驗](data/jd-edit-preservation-2026-10-04/README.md)：五類案例、新舊指引各兩次，先隔離改寫，再判讀成品；不與超容量 Memory 比較混為同一結論 |
| 三層Memory是否比單層摘要更能保留資訊、減少取用負擔？ | [八格先導結果](data/memory-summary-capacity-2026-10-05/results.md)：兩份產物均保留19項；讀者各35完整／3部分，三層累計input為單層3.31倍，未顯示較優。新增估算占用US$0.0393；超128K摘要後主比較仍未施測 |
| 說明何時讀／不讀，能否進一步減少來源展開？ | [固定 Memory 的八格配對](data/memory-summary-capacity-2026-10-05/reading-policy-update.md)：兩組各16次讀取、累計input近似；控制36完整／2部分，候選33完整／5部分。未採用候選，不修改B2；本批估算占用US$0.0236 |
| B1 如何整合碎片，B2 如何重組可獨立使用的理解？ | [第三批 B2 結果](data/memory-organization-2026-10-05/capability-aligned-results.md)：對齊正式能力後完成一對；候選保留更多指定細節且較可單獨選讀，但仍有跨工作引用缺口與舊理解限定未校準。正式提示未替換，同條件重複與 A 效果未完成；前批沿革由[實驗入口](data/memory-organization-2026-10-05/README.md)查閱 |

方法、結果與判讀見[專題報告第四、五章及附錄 B](../../reports/project-report/report.md)；跨情境的已驗範圍見[驗證說明](../../architecture/verification.md)，問題整理見[實驗發現](../../reports/experiment-findings.md)。不同批次不能合併成同一次受控實驗，也不將合成訪談當成真人使用成效。

最新完整訪談的工作條件漏問，已另做[診斷與指引校準](data/jd-analysis-full-journey-2026-10-06/exploration-followup.md)，並完成[局部真模型對照](data/jd-condition-exploration-2026-10-07/results.md)。本機修改、首輪與探索性接續分開保存，不改前批原件或成功判準；這批尚未證明漏問已解決。

## 離線核對

在儲存庫根目錄執行，不呼叫模型、不連資料庫、不產生費用：

```powershell
uv run --project apps/api --locked python -X utf8 -B docs/reports/project-report/verify_evidence.py
uv run --project apps/api --locked python -X utf8 -B docs/experiments/product-validation/data/source-diff-eval-2026-10-02/analyze.py --check-report
uv run --project apps/api --locked python -X utf8 -B docs/experiments/product-validation/data/long-interview-memory-2026-10-04/analysis.py docs/experiments/product-validation/data/long-interview-memory-2026-10-04/live-01 --check-report
```

第一個命令核對報告表格、訪談原件、來源核對及本輪導覽／定位、Memory 與核心反例數據；第二個命令重算來源差異實驗；第三個核查長訪談比較的凍結檔案、Context 隔離、用量及 B.13 表格。它們驗證保存資料與計算，不代表重新完成真模型評測。

原始 manifest 中的舊路徑保留為執行當時紀錄。資料曾存於重建計畫目錄，現獨立保存；分析程式只調整取檔位置，不修改原始輸出、雜湊或判準。資料包中的工具副本保留當時環境設定，重跑付費實驗前須另行確認設定與授權。
