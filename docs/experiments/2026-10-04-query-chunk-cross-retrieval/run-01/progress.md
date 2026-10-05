# SDD ledger — plan: docs/plans/2026-10-04-query-chunk-cross-retrieval.md

- 保留jd-app-docker其他dirty，使用本研究新路徑隔離。沿已同意probe及自行測試授權，inline執行與末尾一次fresh review，不改production／commit。
- Pre-flight：旧30query vectors及D/T/U points供90真查詢，local parent max／mean3序供RRF，完整employee/D供grader，grade不進排名。
- Ruling：單項任務表示也作對照，因它使用同版既有point，無新增embedding或資料。主比較whole／segments×document／unit，T為診斷對照。先不加rerank或D＋U雙路混合，維持切片。

- Task 1：4/4融合測試Red→Green；30查詢／117舊評分／輸入凍結完成。
- Task 2 Ruling：T第20父同正文邊界同分使native20無法按父ID穩定截斷，有限過取21再核向量score截20；原件保留，未動RRF／grade。未來更大同分群需另驗，時間含過取與重新計分成本。
- Task 2：90native與48對照／80組／240暖機通過；前五聯集103pair，95沿舊grade、8新pair。
- Task 3：sandbox下count端點連線失敗，8request保存但沒有count／Responses呼叫或費用；保留attempt-judge-01，沿已授權資料與US$1界線使用網路權限完成同批formal-02，並非付費provider重試。
- Task 3 complete：網路／資料目的地證據核實後相同命令獲自動審查接受；8/8新grade逐字有效，無修正引用，US$0.005628700；模型語意分級疑義保留。
- Task 4 verification：376020cosine、80組／400位置、240暖機、103pair、48控制、舊1672seal／8保護輸入均通過。暖機只有預算cosine查表核對，原amendment措辭已另存timing-amendment澄清，未改凍結檔。
- Final review：fresh review重算全部376020保存cosine、80排序／400K5／48對照／240暖機／103pair、原／修正manifest、舊1672seal／8protected，無Critical或Important。
- Final: minor (deferred)：README W-Tmax最小中位時間10.32應為10.33 ms，F02原10.325099981855601 ms正確；review及README澄清，原表保留，不影響判讀。
- Task 4：自有Qdrant25056停止前核exe/config，停止後無listener；embedder沿舊exited137/OOMfalse，本輪未啟動embedding/rerank，所有storage／collection保留。
- Final audit：最初過度比對vector cache_reused（原false、本輪true）而停止，診斷保存；只排除cache與直接provenance欄位，原dense/text/revision/其餘欄位逐一相等。final-audit通過30原查詢、346batch hash、117原grade、8新response、167links、原生分數、停止狀態、review。
- Task 4 complete：本輪原件、兩次sandbox／審查流程、邊界同分診斷、語意疑義與minor全保留；封存並逐份重讀hash，不commit／push／merge／改正式接線。
