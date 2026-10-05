# 最終獨立核查及修正

review_occupation_experiment只讀核查，未改labels、原件或程式，未呼叫模型或啟服務。

最初找到兩項Important離線audit缺口，實際保存數字並未發現錯誤：

1. 摘要top1 ID/職稱/score被改錯，原check仍可能passed。主代理以test_audit.py的3個in-memory反例重現Red 3 failed，再核重算排名的top1/全排名職稱及record/metric一致，Green。
2. 原check只看28列，漏E01改重複E03並同步所有摘要，仍可能passed。補完整14×2的唯一case/arm集合與query/capture/source evidence，以及CSV對JSON。counterexample不改實體原件；在記憶體移除pair guard可重現Red 1 failed，實際guard拒絕此錯誤。

代理已複核上述兩種錯誤現在均被拒絕，check唯讀重算通過，無Critical或尚未修正的Important，可以封存。其獨立重算也確認：

- 14×2 ranking/metrics/DB各一次，CSV與JSON一致；Hit/MRR/nDCG/主要rank/難例rank/top1均與保存數字一致。
- 8主要參考都進前五，B2第一名4/8、原話5/8；整體nDCG差0.001184363，不能稱B2優勝。
- 6新負例兩輸入都低於0.675，但舊不足反例0.698433095依然誤接受，正式門檻未定。
- 28份805排名及28次exact返回一致；原2454筆cache完整byte prefix保留、新增28；前輪132封存檔及309份生成時來源核驗通過。
- README及目前決策保持隔離研究、人工合成標註、原話診斷比較，未宣稱真人、完整JD或採納0.675。

之後只補query原始列數與難例rank的直接assert，未改搜尋結果或裁決。最終封存與再驗以artifact-hashes.json、verification.json及test-evidence.json為準。
