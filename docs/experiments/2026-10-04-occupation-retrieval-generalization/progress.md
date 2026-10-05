# 本輪執行沿革

本輪沿用使用者委託的隔離測試範圍。前輪封存原件不改，14份原話與labels生成前經獨立核查；修正記於label-review.md。

- 準備guard先Red 5失敗再Green 5通過；只把3段原話/3段一般提問送入真Memory流程，空Memory不造查詢，錯B1 revision拒絕。
- run-01：Windows預設Proactor event loop不支援psycopg async，尚未模型呼叫（0calls/0input）即停止。失敗schema與manifest保留；依既有Windows研究harness用Selector修正，無成功生成重跑。
- run-02：生成前凍結805 corpus、14案例/分級、protocol、指引全文、309個責任程式來源/hash。只用隨機eval_occ2_schema、研究_test PG；模型沿當前Luna/high與Memory parent。
- 排名guard另先Red 2失敗再Green：空B2正例算0分、保留在正例分母，负例的Hit為null；總7通過。這是新增離線評分程式，未改生成helpers、原話、labels、模型指引或固定候選。生成source與檢索source各自保存。
- 獨立程式複核未見必要修正：模型預算及count/create接線、label隔離、完整正例分母、固定exact、805逐點比對、前輪cache不追加。空B2沒有cosine分數，後續報告須分清「流程未給候選」與分數門檻表現。

後续實際生成、排名、驗證及停服務狀態以run-02原件和README為準。本沿革不代表結果已通過。
