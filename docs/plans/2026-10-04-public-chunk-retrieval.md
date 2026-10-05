# 公版切塊與職位合併比較

2026-10-04。使用者已同意比較公版整份、任務及任務群組向量；延續自行測試、保存詳細數據的授權。隔離研究，不改產品、不提交。沿用 brainstorming 的已同意探查、writing-plans、executing-plans 與 TDD；工程細節 inline 完成，末尾一次唯讀獨立審查。

目標是找員工主要領域的代表公版，最後去重前五、逐份0–3分不加總。固定前五案原始需求與三案完整A訪談，分開呈現兩種來源；不改員工文字、不加rerank。公版來源仍是凍結805份JSON。

1. Red–Green 驗任務不拆散、複數任務碼不複製正文、代碼表頭及職稱不添加、概述獨立保存、合併不因同公版多命中佔位；凍結協定、來源、八查詢及chunk定位。
2. 本機同版BGE-M3產生新chunk向量；整份及八查詢向量逐字hash重用。新Qdrant collections只存本實驗，exact分組取得20份公版、各最多3個chunk；離線全排名核對。比較整份、任務max／前三均值、單元max／前三均值；均值只重排同max初搜的20候選。
3. 同員工×完整公版重用之前可定位的評分，新pair用對應原Prompt／Luna high盲評。預算US$1、100 Responses、重試0、只外送合成員工／公開資料；原件、引用失敗、用量分開保存。既有評審疑義不藉本輪改分。
4. 暖機三次真DB查詢與合併，embedding/index建立成本另列；逐份輸出分級與命中chunk，追蹤既有強來源。唯讀核對、独立review、停自有程序、封存與更新本題路由。

驗收是完整可重算的比較資料及有範圍的結論，不把前三均值當正式排名契約，不宣稱全庫Recall、真人／Memory或JD收尾已驗收。

協定及執行：[本輪資料](../experiments/2026-10-04-public-chunk-retrieval/run-01/protocol.md)、[ledger](../experiments/2026-10-04-public-chunk-retrieval/run-01/progress.md)。
