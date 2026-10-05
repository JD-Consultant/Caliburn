# Caliburn 模型實驗紀錄

本目錄保存顧問、Memory、公版檢索與 PDF 資料處理的**小型實證**：測試方法、案例、完整輸入與輸出、評分及限制。
涉及模型的實驗另保留模型實際看見的輸入及最終輸出，便於重查結果。

大份 JSON 與 trace 以 gzip 無損保存；原始位元組、SHA-256 及重現前的還原步驟見[大檔原件保存](artifact-storage.md)。

現行產品的合成訪談、指引比較、來源差異及長旅程原件，從[產品驗證資料](product-validation/README.md)查閱。
本目錄不是通用 eval 平台，也不取代 [research/](../research/README.md) 的研究或 `docs/adr/` 的決策。

## 1. 與其他文檔的邊界

| 位置 | 回答的問題 |
|---|---|
| `docs/research/` | 外部資料告訴我們什麼？有哪些設計選項與限制？ |
| `docs/specs/`／`docs/architecture/` | 本產品的責任、流程與契約是什麼？有效性由決策入口判定 |
| `docs/experiments/` | 我們實際怎麼測？輸入、輸出與結果是什麼？ |
| `docs/adr/` | 最後採納哪個架構決策，理由是什麼？ |
| `docs/plans/` | 核准後如何實作？ |

實驗報告可以否定既有假說，但**不會自行改寫架構 authority**。若結果需要更改已 Accepted 的 ADR，
應另開新 ADR。

## 2. 一個實驗目錄至少包含

```text
<date>-<experiment-name>/
├─ README.md       # 問題、假說、arms、方法、停止與採納條件
├─ rubric.md       # 實驗前固定的裁決標準
├─ cases/          # 輸入案例與人工裁決重點
├─ trials/         # 每次受測模型實際看見的 prompt/input 與最終 output
├─ results.csv     # 執行後的逐 trial 摘要
└─ report.md       # 執行後的分析、限制與下一步
```

實驗設計階段可以先只有 `README.md`、`rubric.md` 與 `cases/`／`trials/` 的格式說明；
不得用虛構結果填充 `results.csv` 或 `report.md`。

## 3. 保存規則

- 保存**我們實際送出的可見 prompt/input**與受測模型最終回覆，不聲稱能取得平台隱藏 system
  instructions、私有 reasoning 或完整內部執行軌跡。
- 不要求、不保存 chain-of-thought；需要理由時只保存短而可檢查的 decision rationale。
- 每個 trial 記錄 requested/resolved model、provider/endpoint、reasoning effort、case、arm、執行環境與時間。
- 同一比較中的模型、rubric、輸出格式與非受測條件必須相同。
- 案例與 rubric 在開始跑 trial 前固定；中途修正就升實驗 revision，不能默默改完繼續混算。
- 小型 constructed 實驗可將完整 trial 提交 Git；大量或敏感資料另訂保存規則，不能把秘密或 API key
  放進本目錄。
- 實驗失敗、平手與限制都要保留，不能只提交看起來成功的輸出。

## 4. 實驗清單

- [公版工具回傳的離線資料量比較](2026-10-05-reference-context-projection/README.md)：重用一筆 F01 五份候選，比較現行完整目錄與候選概覽＋按需目錄。保存完整投影、來源 hash 及逐份字元／bytes；讀前兩份累計少 49.14%，五份全讀多 10.76%。非模型選擇、token 或品質結果，未改 production。

- [顧問提問＋員工否認檢索反例](2026-10-05-negated-work-retrieval/run-01/README.md)：三案24文字變體、805 D／8068 T、22新本機embedding含控制、1218共同池rerank配對。短否認三案觀察公版D cosine與logit皆高於原文，兩案進前五；保存全庫名次與任務chunk分數。禁網無付費LLM，未測顧問重問／自動Memory投影，API未改。

- [主要工作面向優先重評](2026-10-05-adaptive-reference-selection/main-work-addendum-01/README.md)：同一八案7038組改按面向涵蓋與弱參考取捨；原8/8至少11份弱主要參考，降到2份則只有7/8。無弱來源最多5/8；未證明主要涵蓋與避免無關追問能只靠分數切線達成。CPU重播，API未改。

- [廣蒐與精搜動態數量比較](2026-10-05-adaptive-reference-selection/run-01/README.md)：八案271初搜規則、69末端選法與7038組快取完整交叉；保守條件D5/T20將247配對降至169，保留12/12已知初搜代表。排除兩個原有疑義標註後，cosine下限加保底另有89配對候選；不能跳過標註限制選門檻。零新模型／外送／服務操作，時間與JD效果未測，API未改。

- [B1整合／逐情境雙路廣蒐](2026-10-05-b1-dual-route-retrieval/run-01/README.md)：八案96組、63query與126個805父排名；558999既有向量cosine新算、83舊路及48舊深度控制、1318舊seal不變。B1兩法N20 11/12、N40 12/12，原話N20已12/12；B1-W40 485配對、B1-S40 2174，未證明逐情境增加已知涵蓋。H01未評、非全庫Recall；沒有新DB／embedding／rerank／外送／費用或fresh延遲。
- [初搜Top20／40／80比較](2026-10-05-initial-retrieval-depth/run-01/README.md)：八案48組、20query與40個完整805父rank，固定158判讀中12主要代表及8已知面向；177460已存chunk scores重聚、20N20控制與581舊seal通過。原話N20已保留12/12與8/8，B2 N20漏全端後端、N40補回；課程行政無3不可判涵蓋，非全庫Recall。N80無已知增益、候選增加；冷氣B2已初搜召回但R掉前五，定位排序問題。零新推論／外送／費用、無fresh延遲；保留全部候選與逐target名次、敏感度。
- [完整聯集保留至rerank重播](2026-10-05-rerank-union-candidate-replay/run-01/README.md)：八案16組80位置，20query完整聯集26–35父，628相同query／公版品質logit重用；48舊R控制與551seal不變，71唯一pair皆有既有盲評，零新增外送／費用。原話找回全端共同參考，B2仍只前端強代表，其他案例無一致改善；候選配對較舊M-R 400增加57%，未實测fresh延遲，不選正式方案。
- [原話／B2與整份／任務／合併及rerank十二法](2026-10-05-memory-public-unit-retrieval/run-01/README.md)：八案96組、480位置，158唯一pair（113重用＋45新增，6引句抄錄修正不改分），177460cosine、24控制與288暖機／3600fresh rerank通過。原話T-R找回前後端共同參考，但B2／M的N20截斷漏掉它，R在其他案例掉代表；未選單一最佳或正式參數。保存完整原件、修訂及估算US$0.044907465，服務停止資料保留。
- [原話與發布B1／B2六組比較](2026-10-04-memory-layer-retrieval/run-01/README.md)：八案48組，35情境／12理解、93查詢；78唯一pair（60重用＋18新增盲評）、16原話控制、144暖機，全部cosine及舊封存核對通過。B2逐理解列下一輪候選，帳務有退步、全端仍缺後端，未選通用最佳。保存快照、來源、完整排名與模型估算US$0.044934290；Memory少量無來源細節及source pin時點已揭露。
- [員工分段×公版切塊交叉比較](2026-10-04-query-chunk-cross-retrieval/run-01/README.md)：八案十法，95舊pair＋8新pair；倉庫找回代表、冷氣保留改善，全端仍缺後端。48控制及240暖機通過，整份留作控制；未選正式方案，語意評審待驗。
- [公版切成任務或工作單元的比較](2026-10-04-public-chunk-retrieval/run-01/README.md)：固定八whole輸入與805父，五種粒度／合併結果，200位置、84唯一pair、120暖機。冷氣前五新增較合適來源，混合前後端及倉庫失去部分既有代表；整份保留控制基線，未選正式切法。保存11064唯一向量、35新增Responses及6引句恢復，評審語意疑義仍在。

- [A 訪談原文的四種職位參考檢索](2026-10-04-a-interview-occupation-retrieval/run-01/README.md)：三類歷史自然 A／合成員工，原話＋必要問題，完整四法與同人第一則整段對照。69回答、18查詢、33唯一盲評、54暖機；初期與完整均保留倉庫／採購同樣強代表，無穩定新增。額外責任／孤立動作分級仍待釐清，未測真人、全端或Memory；保留全部原件與引句格式修正。
- [代表主要職位的最終前五比較](2026-10-04-representative-occupation-top5/run-01/README.md)：五案四組已執行，805 公版、全域去重前五、49 組正文盲評，逐份分級不相加。整段 dense 暫留基線；rerank 排除部分強代表，混合前後端未齊。保存全部排名、兩輪計時、63 次模型 usage、修訂／失敗及評分語意限制，未選正式方案。
- [公版兩層參考結構核對](2026-10-04-retrieval-reference-views/README.md)：離線重用 805 份來源及 22 個封存情境；保存共同正文、完整已解析任務目錄及全部查詢命中邊。不新增排名，不宣稱 Memory 檢索或 JD 完整度已過。
- [OCS 公版 PDF 解析工具比較](2026-10-03-ocs-pdf-parser-comparison/README.md)：獨立 RAG，十份／55 頁的 pdfplumber、Camelot auto／lattice 與 Docling 本機比較；保存原件檢查點、原始抽取及時間／記憶體結果。比較完成，後續修正見補齊紀錄。
- [OCS JSON 補齊與來源檢核](2026-10-04-ocs-json-repair/README.md)：單次抽取、資料保真、拒絕缺漏與原子輸出；保存 908 份來源的批次結果、前後差異與待處理文件，原 corpus 保留。
- [員工工作內容 → 職位向量搜尋](2026-10-04-occupation-retrieval/README.md)：隔離試點暫選 B2＋T/O/P 正文＋精確 dense；保留輸入、全部排名／分數、混合搜尋失配、資料庫核對及參數試驗。只有兩個合成員工情境，正式接受門檻與 JD 完成條件未定。
- [固定職位候選的跨職務驗證](2026-10-04-occupation-retrieval-generalization/README.md)：新增14個自然B2合成情境，原話並列；8主要參考均進前五，但不能直接採第一名，輸入尚無一致優勝。保留新holdout、負例、28份完整排名與exact核對，前輪封存不改。
- [初搜候選涵蓋基線](2026-10-04-retrieval-coverage-baseline/README.md)：由封存排名重算候選深度；前五主職位命中仍有2/8情境未保留全部已標註相關文件，這不是工作主題完整覆蓋證據。
- [廣蒐＋精搜覆蓋／時間實驗](2026-10-04-retrieve-rerank/README.md)：整體／分段隔離量測已完成；固定64項來源支持主題與參數sweep，698次真Qdrant exact已核對。分段開發10/10正例完整，但保留情境1/2，盤點被0.65門檻刪除；未通過涵蓋採納，不接決策模型／主LLM或JD完成指標。
- [每段保留候選實驗](2026-10-04-retrieval-passage-quota/README.md)：56配置在18個已觀察情境選參數後才測4個新合成組合；每段N20／rerank K5後去重保留64/64及22/22支持主題，兩例暖機約1.7／1.9秒，全域方案約14.6／18.9秒。保存逐段805排名、pair trace、58次本輪真Qdrant及14次計時；合成來源涵蓋工程gate通過，真訪談／Memory與JD完整性仍未驗收。
- [公版參考用途／輸入邊界實驗](2026-10-04-retrieval-input-boundaries/README.md)：公版供客製任務／整體JD完整度參考，允許多對多，不以職位或任務ID一對一評分。22個已觀察情境原話無損比較原段、合併、逐句；固定N20/K5，rerank涵蓋86/86、78/86、86/86，合併漏全部8項次要工作，逐句回傳正文與工作量較多。保存372次真Qdrant與24次暖機時間；沒有新holdout、Memory生成或JD拆合／完成驗收，查詢設計仍待後續實驗。
- [較早實驗與驗收原件](legacy-evidence/README.md)：原 `specs/evidence/` 歸位；涵蓋當時 JD、UI、Memory、工具與保存的反例和驗證。
- [歷史工作樹的獨有實驗](historical/README.md)：CT 系列、JD 整合初審與修正、R1 方法資產、Agent 任務報告；重複副本不另存。
- [產品驗證資料](product-validation/README.md)：原始輸出、比較指標、保存雜湊與離線核對，不混入已結案施工日誌。
- [跨校可用的問題分析案例](../reports/research-casebook.md)：給教授與報告讀者的解讀入口，不取代原始結果。
- [從早期開始的開發演進](../reports/development-history/README.md)：串起原問題、研究、不同架構與實測；含未採用及未執行的方案，不只選近期成功結果。

- [`2026-07-26-r1-p0-context-representation/`](2026-07-26-r1-p0-context-representation/) —
  **Closed／不執行**（[ADR 0041](../adr/0041-r1-p0-closure-first-version-context-and-holdout.md)，2026-07-27）。
  原欲比較 Raw-only、Raw+Spans、Hybrid 與 Structured-only 四種 Context 對 Task 邊界分析的影響；
  六份 constructed cases、rubric 與 assembler 已凍結為 revision 1，**零個 trial 曾被執行**。
  原 Codex-subagent 執行法先被停止（平台不允許把 subagent 當外部 API 受測模型），
  其後 owner 裁定不另付真 provider 成本，改以
  [外部權威證據審查](../research/agent-systems/2026-07-26-professional-consultant-context-representation-external-evidence-review.md)
  收斂為「不建 literal-claim layer」。**該結論的依據是 YAGNI 與外部證據，不是本實驗的結果。**
  frozen 案例、rubric 與 assembler 保留為可重用資產，再使用須另升 revision。

- [`2026-07-27-r1-task-discovery/`](2026-07-27-r1-task-discovery/) —
  ADR 0040 正式 R1 六 arm 快篩的實驗資產。**Segment 1–4 完成**（八案凍結、rubric、契約、
  deterministic verifier、mocked transport、六 arm assembler／runner／blind grader，
  加上一個不使用正式案例的 live plumbing preflight）；
  scripted 48-observation／80-call 骨架已跑通但不具品質結論資格。experiment revision 1，suite hash
  `6c8863863a233830a9216a3ebae46389c91082f097b337c25404400bc93694f7`；
  上述為早期準備狀態；後續 [R1a 結果](2026-07-27-r1-task-discovery/r1a-results.md)已完成八案 × A1／A6／A2 的 24 observations，含兩次中止嘗試與 grader 漏判。A3／A4／A5 未執行；不是六 arm 全跑，也不是 SME 驗證。
  設計 authority 在
  [`2026-07-27-professional-consultant-r1-task-discovery-experiment-design.md`](../research/work-analysis/2026-07-27-professional-consultant-r1-task-discovery-experiment-design.md)，
  分段見 [實作計畫](../history.md#source-7661202d166acae889f4)。
