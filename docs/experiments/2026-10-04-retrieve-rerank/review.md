# 最終唯讀審查

2026-10-04，reviewer `/root/review_occupation_experiment`。範圍為本輪研究原件、實驗計算與报告；不評為真實員工品質達標，未改資料、啟服務或付費呼叫。

最終沒有未解除 Critical／Important，可封存為 **「實驗完成、涵蓋採納未通過」**。

- 兩份 audit 與10個測試唯讀重跑均通過；假開發摘要／選擇、缺comparison、DB回傳ID變更均拒絕。核對器缺口與修正已保留Red／Green，不更改原模型分數或選擇。
- 獨立由凍結標註及逐筆結果重算480設定摘要／選擇：整體無passing；分段dense無passing，rerank有8個development passing，最小選擇N200／cosine0.65／K20／無sigmoid門檻。
- 分段選中設定：development52/52支持主題、10/10完整正例、次要2/2；holdout11/12、1/2、次要1/2；合併63/64、11/12、次要3/4。M04盤點cosine第12名／0.6357555763被0.65刪除，不能拿平均值掩蓋次要工作漏失。
- 控制比較是同16 development cases與相同原話，N200／無cosine／K50／無sigmoid：whole dense/rerank均8/10，segments dense9/10、rerank10/10；不單獨歸因某stage。
- 時間14.8959／65.703秒：同E01三段／文件、2次、暖機預tokenize、無門檻固定N200／805模型迴圈。不是chosen設定（E01只118候選）、主LLM费用或端到端時間。
- 640組DB ID／count與58組分段原生分數重新核對；DB輸入重建hash精確吻合歷史manifest。整體原生分數未逐項保存的限制已明示，沒有補造。
- 舊兩輪132／69項封存hashes全未變。報告清楚限制family overlap、工程標註非窮盡、已觀察holdout只能作下輪regression、資訊不足案例未全部拒絕。

數字支撐「本輪未通過採納、不能作為JD完成證據」；檢索元件的實際工作涵蓋驗收仍待後續新情境／完整標註及真實員工核對。
