# SDD ledger — plan: docs/plans/2026-10-04-public-chunk-retrieval.md

- 保留jd-app-docker所有無關dirty；沿原實驗目錄隔離，不改production、不commit/push。此為使用者已同意的研究probe，inline沿已授權自行完成，不重問施工批准。
- Pre-flight：chunk正文／父定位供embedding及分組；完整D正文供評審；排名不讀grade。已核805父／2858單元／7265 task nodes，其中20節點有多個task碼。
- Ruling：T/U保留獨立概述chunk，使D資訊不因分割被捨棄；工作單元作已有結構的群組，不用LLM新造群組。mean3只重排max取得的20父候選，候選集合與max相同。
- read-only調查曾把前輪cases誤指run-01/cases.json，實際在父cases-v1.json；檔案不存在即停止讀取，未改舊資料，依原prepare.py更正來源。

- Task 1：完成。4個行為測試先Red缺chunks，再Green4/4；805來源hash一致，D正文非空行全部保留於T/U。凍結805 D、8068 T（含803概述）、3661 U（含803概述）、11064唯一文字；8whole查詢與82既有pair逐字hash一致。
- Task 2：新chunk向量生成進行中；原D与8query向量重用，只新增新正文。execution-manifest是原judge需要的固定US$1／100calls介面，另存指向input-manifest；未改先前凍結檔。

- Task 2：11064唯一正文向量完成，9460新算、1604逐字cache重用；346批、embedding HTTP合計114.396秒，最長新正文1315tokens，沒有截斷。真Qdrant新三collection及exact分組核對進行中。

- Task 2：完成，三個新collection共12534points，24真exact分組与全chunk離線排名一致；8原R01前五ID全相同。40結果組／200位置／120真DB暖機trial，保存每chunk分數与父前三。
- Task 3：依前五聯集去重，重用既有pair，僅新增pair付費盲評，最多US$1、100calls、重試0。

- Task 3：35responses／US$0.037831530，原29引用valid／6literal失敗；3筆空白或逗號自動唯一定位，3筆原句漏也／進行逐筆恢复，沒有改grade或新modelcall。原29judgments、35responses及失敗summary保留，6分析修正另存。
- Task 4核對：首次舊seal檢查假設全部有files包裝，4舊manifest實為flat path map，出現KeyError；改以實際兩格式讀取，先前805來源、40排名及120trial核對已成立，不重搜或重評。
- 舊seal格式進一步核實：passage-quota／input-boundaries值是hash string，另兩flat map值是sha256 object；依實際3格式解析，兩次validator錯誤均未改舊資料或新排名。

- Task 4：完成。84pair逐字有效（49重用＋29原valid＋6分析quote恢復）；40組200位置／120trial、346向量批hash、8保護輸入與1125原seal成立。獨立唯讀review重算100272cosine零差、1109原生hit誤差<1e-6；Critical0／Important0／Minor1。
- Minor已處理：冷氣T-max最高命中是獨立概述，而U-max是檢修中央空調單元，README補明，無重搜／重評。
- 自有Qdrant21244不存在、0listeners；embedder stop後exited137，inspect OOMKilled=false，發生在全部embedding／DB完成後。storage與collections保留，未操作其他服務。
- 結果：切塊局部改善冷氣、混合前後端及倉庫丟失代表；整份保留控制，整份＋chunk混合尚未測，不定正式切法／相似度線、不驗Memory或JD/PDF。五份當前RAG路由更新，原封存不動。本輪無commit／push／merge。
