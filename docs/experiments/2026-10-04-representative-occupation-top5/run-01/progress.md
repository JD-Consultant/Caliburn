# SDD ledger — plan: docs/plans/2026-10-04-representative-occupation-top5.md

- 使用者同意五份合成需求與四組比較；已核分支 jd-app-docker 及未提交變更，全部保留。
- 本輪只施工隔離研究腳本，不改 production；沿原研究工作區 inline 執行，不新增 checkout／commit。舊零付費句限此前準備階段，本批模型授權及 US$1 上限已另明示於 protocol。
- Pre-flight：案例／查詢／rubric 由凍結準備供排名與評審；排名不讀評審答案，評審不看方法／名次。全域去重 K5 與舊每查詢 K5 聯集不同。
- Task 1：完成。原話／15 查詢／七規則例／Prompt／schema 及版本先綁 hash；融合去重、無證據高分及不確定反例先 Red（4 fail、2 缺資料 error），再 Green 6／6。沒有修改原案例或舊評分。
- Task 2：完成。15 新向量、15×805 全排名、15 真 Qdrant exact 前 20 核對；300 fresh rerank pairs 保存完整分窗，產生 20 組／100 位置。初輪計時 Windows 檔案鎖定中斷，保留 23 筆；第二輪完整重做 60 次及 900 fresh pairs。F01-R02 第一筆含 startup，實際 59 warm＋1 startup，該組兩個暖機樣本；不冒稱三個。QdrantClient close 修正與計時 amendment 皆留原件。
- Task 3：完成批次，語意有效性仍待後續驗證。首輪七例 6／7；補近似 C04 的 2 分例後，同批 7／7，只屬規則回歸。正式 49 唯一正文盲評，48 自動引句驗證；J014 只補原文「也」，原 1 分不改。共 63 Responses、usage 估算 US$0.035030905；所有請求／回應／失敗／修訂保留。
- Task 4：完成隔離研究交付。逐案逐份報分、暖機與新 embedding 分列、事後追蹤五組已有強代表的排序去留；沒有分數加總。機制核對及獨立唯讀 review 完成，8 保護輸入及 474 舊封存原件不變。已停止本輪自己的 Qdrant、實驗容器已退出，保留 weights／storage，未動 production、commit 或 push。
- 審查限制：F04 單一領域較粗，不能拿無 3 推論漏搜；網路／電腦維修跨對象 1／2 判讀理由未解。7／7 不是獨立校準成績；來源引用可定位不等於語意正確。
- 結果：R01 整段 dense 暫留控制基線，rerank 無整體優勢；全端四組仍未齊後端，沒有正式方案或門檻。下一輪先驗查詢表示與新評審反例，另凍結協定；Memory／ANN／完整 JD 或 PDF 收尾未驗。
