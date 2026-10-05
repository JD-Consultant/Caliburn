# 唯讀審查紀錄

2026-10-04，由既有reviewer `review_occupation_experiment` 獨立核對，未修改實驗檔案或執行GPU／DB。最終沒有未解除的Critical／Important，可封存本輪研究。這不是產品採納或領域專家完整性驗收。

來源預審先於新排名，確認初始22主題／16段原話及source hashes；指出H01跨句支持及未明示維護、H03採購支持範圍，另提醒H02備份不等於調校、H04未明示環境措施。初始檔保留，以獨立修正版與amendment凍結，複核通過。

實作審查自己重建56配置×18情境共1,008筆開發結果，包含完整selected／段落matches、涵蓋、次要主題、字符及pair數；與保存結果一致。通過配置數為global_dense 0、global_rerank 2、quota_dense 6、quota_rerank 7；依預定criteria選出N200/K20、N20/K10、N20/K5，沒有使用新情境調參。依內容鍵核所需集合，缺少的512個配對與補算結果完全吻合，無缺件／重複，805份正文hash唯一。

審查發現兩個Important核對器問題，均在保留Red／Green後解除：

- 三筆既有開發標註使用單段anchor加多段context indices，不能要求它們的舊quote直接等於兩段join。只對已核的三個topic支援legacy契約，完整context衍生保存；新H01仍嚴格核多段join，原labels與前輪seal不改。
- 計時不能只看request_id集合。補核request_id／case_id／repeat／config、response ID，且每個非full配置恰有每段一次DB搜尋、limit=N；缺DB或誤標配置必須拒絕。

最新核對程式與11個測試唯讀重跑通過。新情境12筆結果及3,210補算一致：quota_dense／quota_rerank各22/22，global_rerank 21/22，漏H04季度盤點。14次實跑時間吻合每段方案E01／M04 1.692／1.915秒、全域14.633／18.864秒；58次本輪原生DB回傳及4,476個可與品質cache對照的暖機logit均獨立一致。前輪132／69／86項sealed hash全未變。

報告的結論與證據一致，限制保留：合成來源支持主題不是員工全工作、完整相關文件全集、precision或職位責任驗收；Memory切段、下游LLM與JD停止尚未驗證。時間比較是各自選定的不同N／K配置，不能單獨歸因於配額機制。沒有正式p95、併發或ANN實驗。
