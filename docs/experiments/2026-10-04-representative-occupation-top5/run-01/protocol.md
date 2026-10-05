# 代表主要職位的前五比較：執行協定 r1

2026-10-04。使用者已同意五份固定需求與四組比較，沿[評分 v2](../../../specs/2026-10-04-representative-occupation-scoring-protocol.md)。本輪為隔離研究，所有五案都是開發資料，不接 production、不重選 corpus、不把結果當真人驗收。

## 固定條件

- 員工：父目錄 `cases-v1.json` 五案原話不改，職稱與案例 metadata 不進查詢。
- 公版：既有封存 805 份概述與 T/O/P 正文及同版 dense 向量；OPKS 代碼／表頭、職位名稱不進向量，正文及項目名稱保留。
- Embedding：BGE-M3 revision `5617a9f61b028005a4858fdac845db406aefb181`、FP16、1024 維；新查詢由相同 GPU 服務計算。
- DB：既有隔離 Qdrant 1.18.2、同一 collection，exact cosine 前 20；另重算全庫 805 排名核對。不是 ANN 參數驗證。
- Reranker：BGE reranker v2-m3 revision `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`，相同 weights hash、FP16、batch=1、SDPA、8192 token 全文分窗／overlap=64／取最大 window logit；不截掉長文件。
- 本輪 N=20、最終全域 K=5，沒有絕對 cosine／rerank 門檻；N 與融合參數只是對照條件，尚未選為正式參數。

## 四組與合併

命名 R01–R04，避免與正式分析 Agent A／B1／B2 混淆：

| 方法 | 查詢 | 排序 |
|---|---|---|
| R01 | 整段 | dense 原序前五。 |
| R02 | 整段 | dense 前 20 → rerank 原序前五。 |
| R03 | 每案兩個保留脈絡分段 | 各 dense 前 20 → RRF 合併去重 → 全域前五。 |
| R04 | 與 R03 完全相同分段 | 各 dense 前 20 → 各 rerank → RRF 合併去重 → 全域前五。 |

分段在新排名前固定，以原話中的連續片段重組兩個主要工作視角，保留共同對象、主次及分工界線。各片段保存原文 start/end，聯集涵蓋整段原話，允許共同脈絡重用；沒有新增職稱、期待公版、LLM 改寫或把兼任單獨加成一個查詢。這是人工準備的分段控制，不冒充已驗收的自動 Memory 前處理。

RRF 只融合檢索名次：zero-based rank，`sum(1 / (2 + rank))`，同文件每個查詢只計一次，同分按固定公版 ID 排序。保留每個查詢的貢獻與原始分數，不把不同查詢 logit 直接混加。固定 k=2 是 Qdrant 現行預設的研究對照，不是已證明最佳。[Qdrant 官方契約](https://qdrant.tech/documentation/search/hybrid-queries/)查閱 2026-10-04。此檢索融合分數與逐份 0–3 評審分數完全分開，後者不相加，也不回頭挑前五。

## 評審、校準與界線

同一員工／公版組合只評一次。評審看完整固定員工原話、同版公版全文與 v2 準則，先隱藏檢索方法、名次、分數、公版職稱及舊支持標註。App 綁來源 ID／hash，評審回報分級、主要領域、短理由與逐字證據。3 表示強代表一個主要領域，局部直接匹配只屬 1；不是整份公版都適用。

先用七個獨立假設正文規則例校準，預期分級事前保存。校準失配、無法定位證據、schema／超長／截斷／服務問題均保留，該問題部分停止；不改期望分來遷就模型、不默默重試。規則例通過不等於真實職位語意有外部真值。

評審沿現行模型 `gpt-6-luna`／high，直接 OpenAI Responses、standard/default tier、store=false、background=false、無工具、max_output_tokens=4096、SDK retries=0、每請求最多 120 秒。只外送本輪合成原話與既有公版正文，不外送真人資料／Memory／金鑰。以目前官方價格及既有 pricing adapter 做 admission 與 usage 記帳，[模型](https://developers.openai.com/api/docs/models/gpt-6-luna)、[價格](https://developers.openai.com/api/docs/pricing)、[格式](https://developers.openai.com/api/docs/guides/structured-outputs)查閱 2026-10-04。

有效授權為使用者「都交給你測試、詳細記錄」及本輪對五案四組的「同意」。本批估算費用上限 US$1，最多 107 次模型回應及相同數量 input-count，總執行最多 30 分鐘；本機向量／rerank 不另作付費模型外送。實際 usage／估算費用與限額分開報，不聲稱帳單金額。校準失敗不啟動正式批次。

## 時間與比較

每組每員工保留一次實際初搜及三次暖機重跑；rerank 重跑不得用既有 pair cache 假裝新運算。保存 embedding、DB、tokenization、GPU、合併及總時間；模型初始化另列。查詢向量計算的批次速度不冒充串行互動延遲；另報同一表示的串行 embedding 時間。小樣本不報正式 p95。

按每案五個位置列檢索分數、0–3 或不確定、主要領域、重複／缺少的領域與正文證據，不列總分或平均分。兩個 3 都在同一領域不等於跨兩個領域已涵蓋；品質相近再看時間／正文量。沒有全庫 qrels，不報完整 Recall 或 JD 完成率。

所有輸入／腳本／Prompt 先 hash 綁定，原始排名、pairs、模型請求／回應、usage、錯誤與報告都保留。修改協定另記 revision；既有草稿與 474 份封存原件不改。
