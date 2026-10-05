# B1雙路廣蒐最後審查

獨立review_b1_dual_route唯讀審查：Critical 0／Important 0／Minor 3。全部是措辭，排名與候選計算不受影響。

1. B1整合不是訪談時序，原queries.py按正文SHA與object_id排序串接。
2. Top40為所測20／40／80中首次達到既有清單涵蓋，不是精確最低N；全端診斷最低29。
3. 12來源為案例×公版配對，涉及11份不同公版；敏感度10配對涉及9份。

主代理已逐項核原碼/資料，定稿README/report明示以上三點，[文案修正紀錄](report-wording-corrections.json)保存before/after與理由；原report.py及生成輸入manifest保持不變。不改分、排名、候選、凍結輸入或實驗程式。

reviewer獨立執行4測試及verify.py均exit0，另核63query／55Memory查詢body與revision、原話來源片段、805正文／12target雙SHA、558999cosine／126父rank／96候選組、83舊排名／48深度控制及1318舊seal。report生成內容在定稿措辭修改前逐字可重建，6個report輸入SHA吻合，2174／485＝4.482474。原獨立驗證見[reviewer-verification](reviewer-verification.json)。

Declined to judge：全庫Recall、語意真值、fresh DB／ANN、精搜K5品質、真人／新holdout泛化及服務延遲。主代理維持這些未驗範圍，不由離線資料宣稱通過。原有H查詢含必要顧問問題與角色標籤，F01–F05與固定員工需求全等，不把不同输入範圍說成等成本純改寫。

最後審查後沒有程式修正；只有報告措辭澄清，不需再執行模型。最終來源/數值核驗及封存由主代理完成。
