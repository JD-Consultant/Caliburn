# 一次fresh review

2026-10-05，review_initial_retrieval_depth，獨立gpt-6-astra/high、fresh context、唯讀研究原件。Critical／Important／Minor均0，沒有第二次review。

獨立核7反例測試、177460 chunk scores重聚、40×805父rank、48組候選／20N20控制、全部target名次／min-depth／summary／敏感度／工作量。158判讀向used-prior-judgments／judgments-final追溯一致，12個3的main_work／SHA與47組字面引句可定位，原分未變；兩輪551＋30seal不變。

另核628品質cache配對與來源SHA，三深度缺cache為0／600／1736。reviewer唯一新增tmp/initial-retrieval-depth-fresh-review-verification.json，依授權隔離保存，主代理複製為review-verification.json；沒有修改原研究檔、啟服務、外送或提交。

結果：原話三N皆12/12來源、8/8已知面向；B2 N20 11/12、7/8，N40／80恢復已知全部。唯一漏F01網站系統，B2 D24/T41；原話D40而T15所以N20已有，union邊界正確。H01維持null／unassessed；O15／B2 24僅已觀察最小深度診斷。

Declined to judge：原模型3是否等同人工真值、兩項既有疑義；未評公版、全庫Recall／真人泛化／JD完整性；fresh延遲、N40／80 rerank品質及最終K5；README／report／路由／seal由主代理收尾，不列缺陷。

主代理在報告另讀既有N20 U-R定位階段，沒有重評或增加N40／80 rerank：冷氣B2 T7入池而舊U-R17未留5。報告、來源、邊界及主代理裁定沿progress記錄，封存readback不由review替代。
