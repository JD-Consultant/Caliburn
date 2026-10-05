# B2／原話 × 公版整份／任務／合併，以及 rerank 的事前協定

2026-10-05。使用者已同意接續隔離檢索比較；沿前輪固定八案合成員工資料，不改 production、不重新生成 Memory、不重寫公版／查詢、不提交或清資料。研究用途為代表主要工作的公版參考，並非唯一職位或 JD 完成判定。

## 固定表示

輸入兩組：前輪 O-W 原話整段（八查詢）及 B2-S 已發布理解各查一次（十二查詢）。沿原 query ID、完整 body／原話、hash、vector、模型 revision 與來源關係；六案 B2 僅一物件的限制繼續保留。評分仍以完整固定員工原話為事實，Memory 未確認細節不升為評審事實。

公版 D805 整份與 T8068 任務表示沿前輪向量及 collection；T含803個獨立概述 chunk，名稱只供結果顯示，職稱／OPKS代碼／表頭不額外加入正文。每個查詢先取得每個父公版最高 chunk cosine，按分數及父ID排序，前20個不同父。chunk數不直接加分，但max仍可能受粒度及長度影響；保留命中chunk與完整805父排名。U工作單元本輪不混入。

## 兩階段十二方法

第一階段六組：O-D、O-T、O-M、B2-D、B2-T、B2-M。D整份、T任務max，M先在同一query將D前20與T前20等權zero-based RRF k2合併，取前20父；記兩路聯集及每路貢獻。每路同父只貢獻一次。M有兩路搜尋，成本不假稱與單路相等。

跨B2理解再用相同RRF k2合併各query前20父，最後全域去重K5。單query維持該query排名，不多加一次RRF。D/T/M每query交下一步均20父，最終各case／method均5份；M原聯集可達40，並非增加最終額度。grade不得參與候選或融合。

第二階段在第一階段六組各加-R：每query對同一20父，以相同完整D公版正文進行本機BGE-reranker-v2-m3，最高logit排序，保留20父全序，再跨query RRF及全域K5。不因第一階段結果選有利方法、不設新score threshold。固定revision953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e，權重SHA256 d9e3e081faff1eefb84019509b2f5558fd74c1a05a2c7db22f74174fcedb5286，FP16、SDPA、batch1、8192 pair tokens。沿既有不截斷窗口法、overlap64、文件logit取最高；必保存所有token/window/score。query超窗口容量停止，不默默截斷。模型已快取，GPU容器network=none。

相同query／D正文重疊pair在品質推論只算一次，六法共享實際結果；暖機不得當免費cache命中，需每方法三輪重新推論其全部20父。兩階段按相同固定方法順序輪轉，記本輪順序。query embedding全部重用，新的embedding耗時為零，不冒充cold-start或端到端；品質cache時間、GPU載入、DB、完整cosine核驗、各次融合、fresh rerank、tokenization分開。

## 確定驗證及原話判讀

新排名前固定協定、程式、來源hash與全部舊封存hash。真Qdrant1.18.2 exact／parent grouping只讀既有collection；完整float64 cosine／父排序另算，native誤差限1e-6。邊界差異可overfetch並明記，最後canonical前20必在native回傳中。D的16組前五須完全重現Memory輪 O-W／B2-S；O-T須重現前輪W-Tmax八案。M及-R是新增變因。獨立verify重算全部cosine、父聚合、兩次fusion及R排序；負向破壞查詢／候選／source hash須被拒絕。

八案十二法共96組480位置，聯集按相同employee×完整D正文盲評一次。完全相同原話、公版、Prompt、模型與參數的舊判讀重用；新pair沿既有F／H v2 prompt、schema、gpt-6-luna/high、4096output、store=false、default、SDK retries0、concurrency3。只送固定合成員工與公開正文，不送方法、rank、向量score或Memory。新評分總上限US$1／100 Responses／30分鐘；每請求先count預留，未知費用保守計入並停止，無自動重試。外送依本輪有效授權與自動審查執行，拒絕時先保留具體jobs並向使用者說明。

所有結果逐份列0–3分、理由、主要面向、雙方字面證據，不加總／平均；沒有全庫qrels，不算Recall／真人正確率。模型語意疑義、Memory少量無來源細節保留，不修改資料迎合搜尋。8案是已觀察回歸，不是新的holdout；未選正式DB／ANN／門檻／App接線，未測JD完整度。

只啟動已確認自有的Qdrant與本輪新離線GPU容器；完畢核身分停止，資料保留。最後一次fresh review及hash readback，入口只更新本題狀態。
