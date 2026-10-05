
# 系統設計與工具介面

本目錄定義 AI 分析、工作記憶、模型上下文與工具的詳細行為，包括角色能做什麼、可用哪些資料，以及操作何時正式生效。整體關係先看[架構導覽](../target-architecture-map.md)，再依問題閱讀下面各章；程式如何實現契約，則由實作文件說明。

各文件標示現行、已確認目標、候選或歷史內容，閱讀時先核對有效狀態。JSON、差異格式與操作範例用來解釋交換資料的方式；正式格式沿契約來源生成，不由範例另定義。


## 核心系統設計

| 文件 | 主要內容 |
|---|---|
| [分層架構](2026-09-24-caliburn-layered-architecture-map.md) | A、B1、B2、JD 與 Memory 的權限、候選及發布關係 |
| [B1／B2 生命週期](2026-09-25-b1-b2-information-gap-lifecycle.md) | 單向 B1 → B2 → 發布、同一候選、來源範圍及安全點 |
| [顧問 Context](2026-09-26-consultant-context-and-state-design.md) | A 固定 Memory、按需 JD／原話、Turn／Step 與壓縮恢復 |
| [輪前摘要與輪中壓縮](2026-10-04-context-summary-and-compaction-design.md) | 已確認目標、尚未實作：輪前 App 文字摘要，輪中原生 compaction；B1／B2 壓後只補目前候選導覽，安全點不變；摘要 Prompt 待討論 |
| [共同工具設計](2026-09-27-agent-tool-contract-design-research.md) | 工具命名、輸入、結果、錯誤與設計理由 |
| [Memory 更新契約](2026-09-27-memory-object-update-tool-contract.md) | 單物件修改、正文 diff、來源集合與操作完整性 |
| [Memory 讀取與來源](2026-09-27-memory-read-and-source-navigation-contract.md) | 導覽、最新候選／固定發布版、訪談訊息與回查 |
| [共用執行與 State](2026-09-27-shared-agent-execution-and-state-design.md) | 原生模型接續、保存交界、控制、恢復與執行限制 |
| [Memory CRUD 範例](2026-09-28-memory-tools-crud-examples.md) | 以合成資料示範建立、讀取、修改、刪除及錯誤處理 |
| [核心價值閉環](2026-09-29-core-value-loop-lifecycle.md) | 訪談、JD、背景整理的跨層時序與正式生效界線 |
| [JD 模型工具](2026-09-29-jd-model-tool-contract-review.md) | 按需讀寫、短定位、直接來源與兩類差異；逐筆引用確認限 JD |
| [公版參考的整體與任務收尾用途](2026-10-04-public-reference-completion-design.md) | 現行可選工具：A 按需查讀、多選主要參考與維護明確否認範圍；B1／B2 只讀排除範圍。工具輸入、結果、跨輪資格與原請求相容性均在此維護；公版不自動判定 JD 完成 |
| [JD 與公版按需取用](2026-10-05-jd-and-reference-demand-loading-design.md) | 三層取用為已確認設計方向，搜尋概覽尚未切換；JD 沿現有局部讀取。工具說明、錯誤指引及精簡寫入回傳已實作，模型取用品質仍待比較 |

## 獨立 RAG 範圍

- [公版職位參考 API](2026-10-05-occupation-reference-api-design.md)：已實作獨立 API；原話 D20/T20 完整聯集後 rerank、完整已解析任務目錄與固定來源讀取。實作驗證與重播見[施工紀錄](../plans/2026-10-05-occupation-reference-api.md)，可選 App／Agent consumer 依 [ADR0080](../adr/0080-opt-in-public-reference-agent-tools.md)，未採納通用最佳品質參數。

- [相似度匹配 V1](2026-07-04-similarity-matching-v1-spec.md)
- [RAG bounded context 與 retention](2026-08-11-rag-bounded-context-retention-design.md)
- [公版 PDF → JSON 保真與驗收](2026-10-03-public-ocs-pdf-to-json-design.md)：已授權轉換／補齊，核心修正已實作；批次結果、未支援版型及品質界限見補齊紀錄。
- [員工工作與公版參考檢索](2026-10-04-public-reference-retrieval-design.md)：較早候選研究；定義共同來源、工作內容與職位整體兩種導覽，逐元件驗 Memory／檢索單位／參數。未知探索、收尾及完整 JD／PDF 旅程留待補測，該稿的完整度流程尚未接入正式 App；現行可選查讀與 state 沿上方核心工具契約維護。
- [職位整體參考搜尋定義](2026-10-04-occupation-overview-reference-retrieval-design.md)：以固定需求比較能代表員工主要工作領域的公版，每位員工最終取前五份。這是候選搜尋定義；輸入、切法、合併排序及正式相似度門檻仍須比較，不預設員工只能對應唯一職位。

相關比較按變因分開閱讀，數字與完整條件沿各次原件核對：

| 比較變因與原件 | 已觀察的結果與適用範圍 |
|---|---|
| [原話與發布 B1／B2 六組比較](../experiments/2026-10-04-memory-layer-retrieval/run-01/README.md) | 已完成。當輪 B2 逐理解列為候選，但帳務退步，全端仍缺後端。 |
| [輸入與公版單位的接續十二法](../experiments/2026-10-05-memory-public-unit-retrieval/run-01/README.md) | 原話的任務檢索加 rerank（R）找到前後端共同參考；B2 與雙路合併（M）截斷後漏掉它，R 在其他案例也有退步，未選正式輸入。 |
| [完整聯集重播](../experiments/2026-10-05-rerank-union-candidate-replay/run-01/README.md) | 原話找回全端共同參考，但其他案例沒有一致改善，配對增加 57%。 |
| [初搜 N20／40／80](../experiments/2026-10-05-initial-retrieval-depth/run-01/README.md) | 原話 N20 保留固定 12 來源／8 面向；B2 需 N40 補全端。H01 無 3 分來源，不能判斷涵蓋；這不是全庫 Recall。加深初搜增加候選，未重新量測時間；R 的適用性與最終 K5 仍需接續比較。 |
| [公版切塊八案比較](../experiments/2026-10-04-public-chunk-retrieval/run-01/README.md) | 有局部改善與退步，整份公版保留為控制組。 |
| [分段 × 切塊交叉比較](../experiments/2026-10-04-query-chunk-cross-retrieval/run-01/README.md) | 找回倉庫代表，全端仍有缺漏；尚未定案切法與合併方式。 |

- [B1雙路廣蒐比較](../experiments/2026-10-05-b1-dual-route-retrieval/run-01/README.md)：同八案的離線初搜已完成。B1 整合與逐情境均需 N40 補全端，原話 N20 已保留全部已知；逐情境沒有增加已知涵蓋，配對卻較多。這輪沒有執行 B1 精搜或重新量測 DB／時間，不提供全庫 Recall，也未採納正式參數。
- [代表主要職位評分 v2](2026-10-04-representative-occupation-scoring-protocol.md)：當前討論；0–3 分與證據逐份列出、不相加，局部直接有用不足以拿 3。五份合成需求的[第一輪](../experiments/2026-10-04-representative-occupation-top5/run-01/README.md)已執行；後續[A 訪談原文四法](../experiments/2026-10-04-a-interview-occupation-retrieval/run-01/README.md)也已執行；領域粒度、額外責任與孤立動作判讀待驗，不宣稱完整 Recall。
- [公版參考評分協定 v1](2026-10-04-public-reference-scoring-protocol.md)：演進紀錄；局部正文有用分級及七個未執行校準例，當前主要職位比較改沿 v2。

上述文件分別維護獨立 RAG 的邊界、研究與產品取捨。API 使用的控制初值不代表已找出通用最佳品質參數；App 的可選 HTTP consumer 也不改變 RAG 的獨立服務權責，不成為預設啟動依賴。


## 方法與實驗

- 產品目的與資訊關係：[產品概念](../product-concept.md)。
- 工作分析、訪談及 JD 欄位方法：[指南入口](../guides/README.md)。
- 外部方法與方案比較：[研究入口](../research/README.md)。
- 測試方法、結果與限制：[驗證章節](../architecture/verification.md)、[產品實驗資料](../experiments/product-validation/README.md)。
- 設計如何隨問題演進：[開發沿革](../reports/development-history/README.md)。
