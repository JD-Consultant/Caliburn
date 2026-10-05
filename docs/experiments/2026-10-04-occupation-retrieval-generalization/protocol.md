# 固定候選的跨職務自然 B2 驗證

狀態：使用者「好繼續」承接前輪自主測試授權；隔離研究，不接 production。目的為檢查既選候選對新職務的表現，不重新調參。

生成前標註複核：E03主參考改為公版正文涵蓋完整製作的烘焙助理，技術人員為grade2；E04資安檢測與E07機械銲接的正文有局部交集，列grade1而非絕對無關。grade3代表主要參考，不代表符合公版全部任務；grade1可同時是「不宜作主要職位」的難例。複核未看本輪搜尋結果。

## 固定條件與判準

- 沿用前輪封存的805職位、BGE-M3 revision、FP16、1024維、TOP正文與精確dense cosine；職稱metadata、TOPKS代碼/表頭不嵌入。候選top10，正式接受門檻未定。前輪provisional0.675只作失敗規則的回歸觀察，不把它升格正式門檻。
- 新14個合成員工情境，8有預期職位、4資訊不足、2公版無適當主要職位。development與holdout各7：4正例、2不足、1無對應。holdout的正例職務領域与development及前輪主要probes不同。資料不是真人、不是專家ground truth。
- 每情境3段員工原話與3段提問，同一批固定截止序號6，經現行B1→B2→發布的真模型流程。不手寫B2、無檢索結果進生成context、不把預期OCS答案或labels送給B1/B2。這是短型訪談，不宣稱跨職務長旅程或完整JD。
- 生成前凍結原話、分級、負例原因、重點責任邊界與hash。工程代理標註，另一核查代理只讀公版正文與原話複核（非真人專家）。一個主要職位可有多個可接受相關參考；grade0是未標註，不是絕對無關。
- 凍結選擇後一次評B2：全部805排名、score、Hit@1/5/10、MRR、nDCG@10、主要職位rank，正/不足/无對應分开。原話全文作为診斷基準同時查；不据holdout改換輸入/索引/threshold。補充B1僅保存，不自动全部拼入。
- B2逐例人工讀原話核核心工作、決定權/交接/更正/未知。資訊不足不得在B2中變成已知職責；有模型擴寫則另列memory錯誤，不能只以命中職位當成品質通過。
- 本輪不新增reranker、任務切塊、任務覆蓋或JD結束機制；不做資料庫產品競赛或ANN效能結論。Qdrant只用已驗exact，同B2向量比離線基準。

## 執行與保存界線

只用`127.0.0.1:55439/caliburn_t01_test`，隨機`eval_occ2_`schema，保留schema/快照/工具公開trace。key由現行後端credential reader取得，不輸出或保存key。只送本輪合成訪談給OpenAI，模型gpt-6-luna/high及現行角色指引不改。

模型生成總上限256次、admitted input總上限4,000,000、每次≤125,000 input與8192 output、每情境正式64步、總60分鐘；所有生成前count及保守rate pacing。provider錯誤停批，單次attempt1，不無限重試、不重跑成功情境。token上界按Luna短context與cache-write最高輸入率估算≤US$1.549（4M×0.125/M＋256×8192×0.50/M），本輪費用界線US$2。額外count/token及compact請求亦入trace；若觸發compact會停止本輪而非漏算。模型API費用有界的合成驗證属于用户已交付的测试；不將此上限接入產品。

[OpenAI官方Luna契約](https://developers.openai.com/api/docs/models/gpt-6-luna)與[官方標準價](https://developers.openai.com/api/docs/pricing)於2026-10-04核對；實際usage另存，不把估算當官方帳單。

每個run新建目錄；原前輪132檔封存保持不動，向量cache複製到本輪後才append。原話、指引全文/hash、generation公開請求/回應（排除私有推理與加密內容）、published snapshot与exact revision引用、向量、全部排名/CSV、失敗/用量、離線核查和SHA清單全保留。本輪報告不倒改前輪結果。
