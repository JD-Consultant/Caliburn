# 分析紀錄：startup 與逐字引句

第二版計時 F01-R02-1 在模型 ready 前送出，59.194 秒含載入／啟動等待；原 trial 與三個樣本全部保留。分析單列該 cold/startup 樣本，F01-R02 的暖機中位數使用其餘兩筆，其餘組各三筆。不是按數值高低篩選，該排除依初始化狀態；不能宣稱全部各三次暖機或使用該59秒當一般rerank延遲。三次 fresh GPU forwards 仍完整。

49 次正式模型回應中，48 次逐字證據自動核對通過。J014 員工引句漏掉「也」，原分數為1。grading-reconciliation.json 保存原引句及唯一原文修正，沒有重判分數／理由／責任、沒有新增模型請求。judgments.json 的48筆及grading-summary.json 的失敗保留；分析使用 judgments-02.json 49筆，不能把這筆稱為模型原本引句正確。
