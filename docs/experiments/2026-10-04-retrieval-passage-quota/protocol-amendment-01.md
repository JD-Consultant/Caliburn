# 推論前計時介面補充

2026-10-04，任何本輪新GPU分數／新情境排名前固定。品質與選參數規則不變。

GPU worker使用既有公開模型cache、network=none。主機控制器做本機Qdrant HTTP檢索，將已核對候選pair交給模型常駐worker；研究介面是工作目錄的固定JSON請求／回覆，不另建產品API。worker逐次重新tokenize請求候選及原話，量tokenize／GPU精搜時間，再回覆控制器。

本機暖機兩階段benchmark總時間含HTTP檢索、控制器組候選、檔案交接／輪詢、tokenize、GPU推論、精搜保留與合併。保存每段實測，不把各階段相加冒稱實際總時間；也不把這個研究檔案介面速度當正式產品服務速度。公開模型冷載入與原話embedding另記。worker只接受benchmark-plan列出的case／method／N／K，原話與正文從凍結输入讀取，拒絕未知ID／額外請求。

只有選中的rerank配置需要GPU benchmark；dense-only配置另量真DB檢索／選擇與資料量。固定E01／M04兩次，另E01全805兩次，不對新holdout調參或量測來重選。每段quota只計算該段自己的N個候選；global基線計算每個段與全域N個候選。
