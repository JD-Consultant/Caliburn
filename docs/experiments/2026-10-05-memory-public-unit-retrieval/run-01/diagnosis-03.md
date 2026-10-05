# Judge runtime 的不必要依賴

明確45組授權後，首個judge命令在Python import時失敗；API venv沒有NumPy，common eager載入僅供檢索使用的aggregate，連帶引入NumPy。發生於client／judge-trials／usage建立之前，零provider呼叫。

最小修訂：judge_common.py保留同一read／hash／來源檢查／既有H驗證器，排除未使用的chunk聚合與窗口載入；judge_02.py只換此loader並核新修訂hash。沒有安裝或更改production依賴，也沒有改payload、prompt、schema、模型、jobs、budget或外送目的地。原judge及console保留，另存judge-02-console。

暖機controller修訂的shell產生腳本曾因字典括號SyntaxError未執行，後續命令找不到新檔；該次console另保留。修正shell語法後才成功產生02controller，未建立暖機任務或模型請求。
