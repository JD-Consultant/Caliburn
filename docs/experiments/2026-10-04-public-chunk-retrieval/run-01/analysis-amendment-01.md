# 引句定位的分析修訂

35模型回應均完成並有usage，原29筆逐字引用驗證通過，6筆失敗；原回應、grading-summary及judgments不改。自動唯一定位可恢復3筆的空白／逗號。另逐筆檢查J014／J034在員工同一句漏「也」，J016公版同一句漏「進行」；恢復完整來源句後均可唯一逐字定位。分數仍為0／0／1，理由、主要工作及其他證據不改，沒有模型重評。

保存自動修正原版及3筆未解清單，再以reconcile_manual.py保存6筆完整分析版judgments-reconciled-02.json及逐筆before/after。report-02.py只改讀這個分析版本，原report.py及其他凍結輸入不改。

這是引用字面恢復，沒有驗收模型語意分級；不能宣稱35筆模型原引句均正確，也不以原始無法定位引句當合格證據。原協定所稱失敗保存及不改分依然成立，額外引用分析修訂明列於此。

新增H評審傳入相同四個欄位，但JSON順序是employee／facets／reference／interview_context，舊H是employee／facets／interview_context／reference；F欄位順序保持原版。未重跑已付費回應，這個序列化差異保留為新舊評分比較的小限制，不能稱新增H請求位元組完全相同。
