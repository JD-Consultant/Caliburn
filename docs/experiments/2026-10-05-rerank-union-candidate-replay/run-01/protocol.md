# D20／T20完整聯集至rerank：事前協定

2026-10-05，隔離排序重播。使用者同意「兩路各取前20，合併去重後全部交rerank，最後前5」。用途是員工主要工作代表公版參考；沒有production、正式方案或JD完成判定。

沿上一輪固定八案的O原話整段及B2逐理解，共20query。D與T各前20不同父沿真DB已核排名，完整聯集每query20–40父。每query聯集直接按已保存BGE-reranker-v2-m3完整公版pair logit降序／父ID升序，**rerank前後均不另截20**；B2多query用完整排序池zero-based RRF k2融合，再取全域唯一K5。單query直接沿logit順序。新方法O-U-R與B2-U-R，U只指聯集，與前輪工作單元U不同。

對照上一輪O／B2的D-R、T-R及M-R。M-R仍是D20/T20先等權RRF k2、截20，再rerank；不改舊結果。新方法保留路徑及每父每路名次，能定位早截與聯集保留差異。候選深度不在本輪改動。

本輪唯讀重用同query文字×同完整公版正文的品質logit；query／document SHA與來源模型revision／FP16設定均須吻合。不把cached結果說成新GPU推論或新的穩定性批次，不用舊各pair秒數加總冒充warm端到端時間。只核實際配對數及相對M-R候選量；DB／GPU／LLM服務不啟動，外部費用0。

評分仍以固定員工原話與必要顧問問題為事實，沿同一0–3模型判讀，只按employee／document hash相同重用。無新prompt或模型評分。新增top5缺評pair須另存new-judge-jobs.json並明列尚未評；此前45組授權只覆蓋已送45組，不延伸其他資料。引句已明示修正／JSON欄位順序限制沿上一輪保存，不回改來源。

保存事前plan／protocol／code／input hashes、舊551封存核對、完整query union／選擇、所有0–3／理由／引用／unknown、48舊控制、獨立重算與負向probe、最後review／路由／seal。模型0–3不是真人qrels，局部強代表不能當員工整體JD已完整；這批資料已看過，不能算holdout。

Reranker官方契約：BAAI示範query與passage共同輸入、直接輸出相關性分數，分數越高越相關；sigmoid可轉0–1。官方來源：https://huggingface.co/BAAI/bge-reranker-v2-m3 。Caliburn本輪沿固定logit排序，不把0–1當經校準的職位機率，不設相似度門檻。
