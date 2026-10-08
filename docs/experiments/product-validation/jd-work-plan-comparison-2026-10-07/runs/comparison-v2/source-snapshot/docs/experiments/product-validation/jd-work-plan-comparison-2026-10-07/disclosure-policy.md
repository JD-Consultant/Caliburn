# 新批逐問披露政策（施測凍結材料）

沿原協議 §3 與舊批匿名語意政策；由只見本題、近期已正式送出的員工原話、正式披露狀態與本批 private_facts.json 的獨立裁決者判定。不得看 arm、Plan、成本、營運目錄或另一組成果。營運者不能同時充當匿名裁決者；若做不到，先記匿名限制並停止宣稱完整匿名。

每次 decision.json 包含 question_id、mode、fact_ids、reason、subquestions。subquestions 為實際子問逐題裁決清單，每項含 quote（實際問題逐字片段）、mode、fact_ids、reason。一般流程與未提供的特殊情境／普遍適用細節要分開；unknown/refused/clarify/no_question 的 fact_ids 必須為空。頂層 fact_ids 按子問順序去重且最多四項；有答案則頂層 mode=answer，否則用第一個非 no_question 子問的 mode，全部無問題才用 no_question。整體無問題時列一項 no_question，quote 可為空。refused 子問另帶 refused_topic，必須是本批凍結拒答範圍（課務 evaluations）；程式逐項呈現拒答／澄清，並在候選狀態保留拒答範圍。裁決者須涵蓋所有實際子問，程式只核格式與凍結資格，不能取代語意判斷。

known confirmation 可重播正式已知答案；training 已有 training-boundary 更正時程式同時重播更正，防止恢復較早的錯誤權限。更正依先前正式披露與當下相關提問；不能按輪次送新事實。已拒答個案無明示重新願談則不重開；一般隱私流程不被個案拒答阻斷。sensitive-evaluation 原字串只含匿名滿意度公開流程與明確拒答，沒有個案細節；先拒談個案後仍可按相關提問取得這一固定流程，拒答範圍持續有效，不預先把整個 fact 標為已披露。

新可見線索依 protocol §3.2 原字串。未知先正式披露，再首次實際送出 training/refund 的回答才加一次線索；已選未送不生效，後續重播不加第二次。後續责任答案仍要相關回訪才取得。最終收束不送任何已選未用事實。

review 上界 300 秒，讀取 decision 前後都核逾時；超時停止且無 keyword fallback。pending→decision→selected→HTTP accepted→當次 source_id 正式可見才更新员工狀態。若 Turn 未正式採用，保留 accepted 原件並停止，不把內容相同的舊原話當本次採用。

manual_jd_edit 是獨立匿名公開事件裁決：只見匿名目前 JD、初始公開原話與固定修訂文字，選已有 task 局部修訂并保留其他有效细節；無相應 task 可 create_task（area_id=null）；等價则 no_op。不能看 oracle、Plan、arm，不能引入新事實。
