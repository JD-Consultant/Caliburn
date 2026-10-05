# Fresh-context唯讀審查

2026-10-04，由獨立review_query_chunk_cross代理（gpt-6-astra high）完成。不修改檔案、不呼叫模型、不操作服務。範圍為本輪交叉實驗及五份相關路由，不審查其他dirty production改動。

**Critical：無；Important：無。**

**Minor（保留紀錄）：** README暖機表W-Tmax的最小中位數寫10.32 ms；F02原benchmark為10.325099981855601 ms，四捨五入應是10.33 ms。原benchmark與timing-summary.json沒有錯；摘要差0.01 ms不影響實驗判讀。沿本輪一次review、Minor不擴增修正範圍，保留原表並記錄本項；需要精確值時依原件。

獨立核對結果：

- 30筆query原文、定位、vector與F/H原件一致，只加來源與cache欄位。
- D805／T8068／U3661，各805父；重算376020個cosine與保存值誤差0。90組native hits最大誤差1.1751134398885199e-07。
- 80組完整父排名、相同20候選的mean3、zero-based RRF k2、400個K5位置一致；48舊控制、240暖機一致。
- 103唯一pair＝95既有＋8新增；103组逐字引文均在原文。8個request僅合成F、response全部completed且與保存grade完全一致；估算US$0.005628700。
- 386個原輸入hash、6個修正hash、1672舊seal檔、8protected都未變。
- 10個强來源×10方法追蹤與實際候選、排名一致；倉庫恢復代表、冷氣新增局部1、全端D融合第6／T/U未入20結論成立，五路由沒有宣稱後端解決／正式採納／全庫Recall。
- H03資材3及F02近似公版2／1語意疑義保留。

獨立review未驗末尾seal或服務實際停止，只讀主代理停止紀錄。主代理已核實自有PID執行檔與config後停止、確認無listener；最终audit及seal由主代理另完成。不把本review當語意評分真值驗收。
