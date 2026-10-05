# 一次fresh review

2026-10-05，review_rerank_union_replay，獨立gpt-6-astra／high、fresh context，唯讀；沒有再次派review或修改資料。

結果：Critical0／Important0／Minor0。獨立重算16組80位置、完整union／logit／RRF／K5、48舊控制、17 frozen inputs與551seal。20query各26–35父，628pair；109個僅T路且原M融合>20的候選仍參與R。F01網站系統由原M25入新1、既有3；B2仍只前端強代表。

71unique pair逐筆向前追used-prior-judgments／judgments-final，核employee／doc hash、完整judgment、引用檔與230組字面evidence；其中4unique pair沿前輪明示引句修正，標記仍保留。未評清單確為空。6測試以py -3.13 -B另跑通過，未覆寫原驗證；comparison／summary／workload一致，628/400=1.57只表示配對量。

Declined to judge：模型grade語意／人工真值、83/30 JSON順序影響及6引句修正語意驗收；fresh推論穩定性、GPU／DB／端到端時間與成本；全庫Recall、holdout泛化、JD完整度、production適用性；README／report／路由／封存由主代理完成。

主代理另核F01整個top5序列，發現初稿一句誤稱與O-T-R完全相同；兩者僅網站系統#1相同，完整序列不同。已另存report-source-correction.json並修正文句，report.py與report-input-manifest保留原件；方法／logit／grade均不改，不宣稱U優於T。

主代理裁定限制見progress；沒有新服務或外送。這次review通過只支持有限cached候選保留重播，不是職位語意或完整JD驗收。
