# CT36：續談、背景整理與記憶回查驗收

2026-09-08 · LLM-Q019／Q019-MEM-CADENCE-01 · G5完成／整體G8 OPEN，不是新產品設計。結果見[CT36報告](../specs/2026-09-08-ct36-interview-background-recall-results.md)。

## 已核准的範圍

Owner核准本次 **Luna／medium，最多40次模型請求、US$0.20保守預留**，共用帳本涵蓋A、B1、B2、回查及SDK重試；達上限停止。只複製CT16合成長訪談資料庫，不動原資料，不接production／JD，不重跑整套訪談，不改產品設定。

依[CT35最新決定](../specs/2026-09-08-ct35-attempted-repair-recovery-review.md#5-owner改採共用框架機制實際接線核對與結論)，沿用官方Agent錯誤→模型修正迴圈。不新增final攔截、不強制工具、不追修零工具C。背景是否真正補存須實測，不能只看回答。

## 方法與停止規則

1. 六組既有離線回歸：80 passed；第一次18個setup error為Windows暫存目錄權限，換新的隔離basetemp後通過，未改code。
2. 從CT16 closed證據的42則問答／Memory revision 3建立唯一新DB副本。保留目前Memory月報10日、對話已更正5日的真實差異；不手改Memory、不塞答案、不重開舊帳本。
3. 用合成員工自然補充月報／售後工作細節、回答顧問問題；經真實服務入口續談，讓既有段落通知自行觸發B。必要時少量續談，不手動通知B。逐段檢查真實執行結果；工具／預算／背景中斷保留，不擅自擴額、放寬驗證或重跑。
4. B若發布，檢查更正5日、全部售後月報範圍、石橋吸塵器與其他案例身份、權限／低頻工作／未知界線、既有細節保留與原文引用。正文不要求抄滿全部案例，詳記可按需找回。
5. 用新的空對話context、同一已發布Memory導覽與現有唯讀工具做回查；近期聊天／隱藏oracle不提供。這是Memory能力的診斷，不宣稱等同完整產品context或全長訪談驗收。
6. 離線audit檢查原42則＋新問答完全保存、引用確實對應canonical原文、重開後Memory一致；原DB另唯讀查核。關閉帳本並封存去敏trace、文本、工具結果和測試程式hash。

沿用ct15服務驅動與ct26計費護欄，不新建產品機制。診斷維持既有fixture的compaction12000／output8192、通知路徑（不啟用字數後備）、無自動背景中斷恢復；回查額度19模型／18工具。這些是測試配置，不改產品預設。未自然整理或中斷皆列未通過，不算已完成驗收。

## 來源與回看路由

- [完整職位驗收定義](2026-09-07-long-interview-acceptance.md)：覆蓋職位全範圍，不是單一任務。
- [CT16真實基準及已知限制](../specs/2026-09-08-ct16-notification-live-results.md)：fixture不是新造Memory；其既有語意缺陷與本輪新增問題分開記錄。
- [CT17更正／背景前例](../specs/2026-09-08-ct17-correction-persistence-calibration.md)：不將那次7日輸入混入本次5日情境。
- [OpenAI官方價格](https://developers.openai.com/api/docs/pricing)，2026-09-08核對：Luna標準短context input .20／cached .02／cache-write .25／output1.20美元每百萬token。既有護欄按完整request bytes×2及輸出預留先攔截，實際usage估費，非正式帳單。

唯一下一gate：依保存內容、回查與實際成本判定本段效果；發現產品問題先報告，不在本輪偷改流程。整體G8仍OPEN。
