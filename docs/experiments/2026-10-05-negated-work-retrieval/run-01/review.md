# 獨立唯讀審查

2026-10-05，代理 audit_negation_retrieval 依固定輸入及實際輸出獨立核對，未啟動模型或修改來源。由主代理保存回報。

- 3案24query、21唯一正文，ID與文字hash、8種變體齊備。
- 805份D向量正文與rerank corpus逐份相同，SEO／採購probe chunk對應事前指定責任。
- 從既有npz重新計算212952筆cosine，48條完整父排名及24個probe chunk名次一致，最大差7.77e−16。
- 24組候選等於D20/T20完整聯集；1392筆保存pair＝1218新推論＋174同文字快取重用。每案共同池、各自候選排序及Top5通過。
- 18組相對分數差、全部輸入hash、實際import的reranking.py hash通過。

解讀限制：3案短否認都升僅適用D cosine、事前指定probe chunk與reranker相對原文。N03的T父最大分數反而下降0.001610。N02加問題後D分數0.636720，短否認降至0.626875，但名次31→17，使公版進入候選後成為最終第3；分數與名次不能混用。

人工確認投影與base同字同快取是恆等控制，不證明自動Memory有效。肯定有做不等於主要工作；未答問題是壓測；否認某任務不等於整份公版無關；沒有顧問旅程就不能斷言顧問實際重問。

執行證據補存於execution.json，包括實際Docker inspect的network=none、唯讀mount與import來源hash。來源hash在推論中取得，完成後再次核對，不冒充已納入事前manifest。
