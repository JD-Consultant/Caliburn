# Caliburn 實驗原件導覽

本目錄保存實際測試的方法、案例、輸入／輸出、評分及限制。以下按產品、工程、檢索與較早材料閱讀；原件留在原目錄，數據、受測版本與完整限制由各次報告維護。實驗完成不等於方案採用或產品驗收。

大份 JSON 與 trace 的 gzip、原始位元組、SHA-256 及還原方式，見[大檔原件保存](artifact-storage.md)。判斷現行產品已驗與未驗範圍，先讀[驗證文件](../architecture/verification.md)。

## 產品驗證

- [產品驗證資料](product-validation/README.md)：現行顧問、Memory、合成訪談、指引比較、來源差異、長旅程及 JD／PDF 原件。
- [問題分析案例集](../reports/research-casebook.md)與[開發沿革](../reports/development-history/README.md)：面向報告讀者解釋問題與方案演進，完整結果仍回各次原件核對。

## 工程驗證

- [工程驗證紀錄](engineering/README.md)：公版 API、工具、角色接線、Docker 等反例、回歸、重播與保存驗證；工程通過不代替模型品質比較。

## 檢索與資料處理

屬獨立 RAG 及其 App 消費端的實驗。按變因找原件，不把不同資料、判準或階段的數字合併成一次比較；現行 API 及候選取捨見[目前決策](../current-decisions.md#獨立-rag-與公版參考)。

| 比較主題 | 原件與用途 |
|---|---|
| PDF 解析與來源保真 | [解析工具比較](2026-10-03-ocs-pdf-parser-comparison/README.md)、[JSON 補齊與來源檢核](2026-10-04-ocs-json-repair/README.md)：工具、批次結果、前後差異及未支援版型 |
| 前期輸入與跨職務基線 | [員工工作 → 職位搜尋](2026-10-04-occupation-retrieval/README.md)、[跨職務驗證](2026-10-04-occupation-retrieval-generalization/README.md)：固定輸入、全部排名、負例及保留案例 |
| 初搜涵蓋與候選配額 | [涵蓋基線](2026-10-04-retrieval-coverage-baseline/README.md)、[廣蒐＋精搜](2026-10-04-retrieve-rerank/README.md)、[每段配額](2026-10-04-retrieval-passage-quota/README.md)：候選深度、支持主題、去重與時間比較 |
| 用途、輸入及參考結構 | [輸入邊界](2026-10-04-retrieval-input-boundaries/README.md)、[兩層參考結構](2026-10-04-retrieval-reference-views/README.md)：原段／合併／逐句與完整目錄查閱；不代表 JD 完整度驗收 |
| 主要職位代表性 | [固定需求前五](2026-10-04-representative-occupation-top5/run-01/README.md)、[A 訪談原文四法](2026-10-04-a-interview-occupation-retrieval/run-01/README.md)：整體代表、正文盲評及評分語意疑義 |
| 公版切塊與員工分段 | [公版粒度／父合併](2026-10-04-public-chunk-retrieval/run-01/README.md)、[分段 × 切塊](2026-10-04-query-chunk-cross-retrieval/run-01/README.md)：整份、任務、工作單元及查詢分段的交叉比較 |
| 原話與 Memory 輸入 | [原話／發布 B1／B2](2026-10-04-memory-layer-retrieval/run-01/README.md)、[輸入 × 公版單位／合併／rerank](2026-10-05-memory-public-unit-retrieval/run-01/README.md)：同案輸入、來源快照、排名及評分；[B1 回溯材料](2026-10-05-b1-retrieval-retrospective/)保留原位置 |
| 截斷、深度與 B1 廣蒐 | [完整聯集重播](2026-10-05-rerank-union-candidate-replay/run-01/README.md)、[初搜深度](2026-10-05-initial-retrieval-depth/run-01/README.md)、[B1 整合／逐情境雙路](2026-10-05-b1-dual-route-retrieval/run-01/README.md)：候選截斷、已知涵蓋與工作量，快取／離線結果不當成 fresh 時間 |
| 動態數量與主要面向 | [動態數量比較](2026-10-05-adaptive-reference-selection/run-01/README.md)、[主要面向重評](2026-10-05-adaptive-reference-selection/main-work-addendum-01/README.md)：門檻、保底、弱參考及已知主要面向的取捨 |
| 否認輸入與按需取用 | [顧問問題＋員工否認](2026-10-05-negated-work-retrieval/run-01/README.md)、[工具回傳資料量](2026-10-05-reference-context-projection/README.md)：否認的相似度反例與候選概覽／完整目錄投影；不代替顧問重問率、token 或 JD 品質驗證 |

## 較早原件

| 材料 | 閱讀時的狀態與用途 |
|---|---|
| [早期實驗與驗收原件](legacy-evidence/README.md) | 原 `specs/evidence/`，涵蓋當時 JD、UI、Memory、工具及保存 |
| [歷史工作樹的獨有實驗](historical/README.md) | CT 系列、JD 整合初審／修正、R1 方法資產與 Agent 任務報告；重複副本不另存 |
| [R1 P0 Context 表示](2026-07-26-r1-p0-context-representation/) | Closed／不執行；沒有執行 trial。凍結案例、rubric、assembler 保留，再用須升 revision；「不建 literal-claim layer」依 [ADR0041](../adr/0041-r1-p0-closure-first-version-context-and-holdout.md)及[外部證據](../research/agent-systems/2026-07-26-professional-consultant-context-representation-external-evidence-review.md)，不是本實驗結果 |
| [R1 Task Discovery](2026-07-27-r1-task-discovery/) | 早期骨架與 preflight 不具品質結論資格；實際執行、未執行 arm、中止及評審漏判沿 [R1a 結果](2026-07-27-r1-task-discovery/r1a-results.md)核對，不是六 arm 全跑或 SME 驗證；[設計](../research/work-analysis/2026-07-27-professional-consultant-r1-task-discovery-experiment-design.md)與[歷史計畫](../history.md#source-7661202d166acae889f4)保留脈絡 |
| [工作分析 live smoke](2026-07-31-job-analysis-attributed-live-smoke/README.md) | 早期工作分析實測原件 |
| [OPKS live smoke](2026-08-02-opks-attributed-live-smoke/README.md) | 早期 OPKS 實測原件 |
| [OPKS 漸進訪談 live smoke](2026-08-06-opks-progressive-elicitation-live-smoke/README.md) | 早期漸進提問實測原件 |

## 實驗與其他文件的邊界

| 位置 | 回答的問題 |
|---|---|
| `docs/research/` | 外部資料告訴我們什麼？有哪些設計選項與限制？ |
| `docs/specs/`／`docs/architecture/` | 本產品的責任、流程與契約是什麼？有效性由決策入口判定 |
| `docs/experiments/` | 我們實際怎麼測？輸入、輸出與結果是什麼？ |
| `docs/adr/` | 最後採納哪個架構決策，理由是什麼？ |
| `docs/plans/` | 核准後如何實作？ |

實驗報告可以否定既有假說，但**不會自行改寫架構 authority**。若結果需要更改已 Accepted 的 ADR，
應另開新 ADR。

## 新實驗的最低內容

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

## 保存規則

- 保存**我們實際送出的可見 prompt/input**與受測模型最終回覆，不聲稱能取得平台隱藏 system
  instructions、私有 reasoning 或完整內部執行軌跡。
- 不要求、不保存 chain-of-thought；需要理由時只保存短而可檢查的 decision rationale。
- 每個 trial 記錄 requested/resolved model、provider/endpoint、reasoning effort、case、arm、執行環境與時間。
- 同一比較中的模型、rubric、輸出格式與非受測條件必須相同。
- 案例與 rubric 在開始跑 trial 前固定；中途修正就升實驗 revision，不能默默改完繼續混算。
- 小型 constructed 實驗可將完整 trial 提交 Git；大量或敏感資料另訂保存規則，不能把秘密或 API key
  放進本目錄。
- 實驗失敗、平手與限制都要保留，不能只提交看起來成功的輸出。
