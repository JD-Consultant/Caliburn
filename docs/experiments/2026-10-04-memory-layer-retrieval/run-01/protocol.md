# 原話與 B1 B2 六組檢索事前協定

2026-10-04。使用者同意：同一員工固定原話，經現行 B1／B2 產生情境與理解；比較整合搜尋及逐物件搜尋。所有案例為已保存合成需求或「真 A 顧問＋合成員工」歷史實驗，不是真人員工。

八案 F01–F05、H01–H03 沿既有分段×chunk交叉原件，不增補預期職位。F 用原需求作一則員工回答；H 重播原實驗已完成的員工／顧問輪次，移除檢索用標記、case label、主要面向及評分提示，不向 B1／B2 提供公版。單一最終批次捕捉固定訪談上界；H 的完整歷史顧問答覆對 B1 可見，但原話檢索控制仍只用原固定「員工回答＋必要問題」。這是產品現行資料可見範圍；顧問假設不得升為事實。單批重播不能代表連續更新品質。

Memory：沿現行角色 instructions、tool schema、MemoryBatchWorkflow、真 PostgreSQL，loopback 專用 caliburn_rag_memory_test 庫＋隨機 schema；只新增隔離資料，既有 DB／服務不停止。gpt-6-luna/high，max_output_tokens=8192，角色最多32模型步、單請求一次嘗試；沒有正式快照則該案失敗，禁止手工替代。

方法 O-W／O-S、B1-W／B1-S、B2-W／B2-S。O 沿凍結 whole／segments 查詢；B1/B2 依發布快照的物件順序（按正文 hash、物件身分穩定排序）各取 body，W 用兩個換行串接、S 逐物件。保持原 Markdown body，不按句子／字數再切，不加入 title、description、來源 ID 或公版職稱。沒有物件則明列無輸入，不自動回填其他層。

公版 D805、既有 BGE-M3 revision 5617a9f61b028005a4858fdac845db406aefb181、1024 dense、FP16、max_length8192 固定；cache 只按完整文字 hash、同模型版本使用。新文字實際 token 長度必記；超8192即停止該案，不默默截斷。Qdrant exact cosine 逐查 N20，父 ID 去重；多查沿既有零起算 RRF k2，最終 K5。保留所有805分數、逐查20及合併前後全排序。若 float 邊界 tie，沿已驗 canonical float64 cosine／ID排序並記錄 native誤差與 overfetch，不能悄悄換候選。

評審用各案固定原話、必要上下文、相同公版正文與既有 v2 Prompt、gpt-6-luna/high。沿舊 schema／證據逐字定位機制；不給方法、查詢表示、名次、cosine、舊評分。完全相同 pair／Prompt／模型的舊評分可重用，新增 pair 盲評一次。語意疑義保留，不回改分數迎合結論。沒有全庫 qrels，不報全庫 Recall 或正確率。

Memory 輸出人工核對主要範圍、否定責任、未知、更正及次要工作是否忠實；可疑項目照原輸出留存並標註，不能把較短 body 或較好排名當忠實證據。資訊更正只按已確認範圍，不採最後一句蓋全部。

新 provider 呼叫總預算 US$1.00（Memory＋新評分共用），至多160 responses、90分鐘；官方 OpenAI adapter store=false，不自動重試未知結果。每次用 count 先保留最壞費用，回應使用固定 pricing 估算；原始 request／public response／usage 保存，未知費用保守入帳並停止。計價估算不是帳單。

搜尋暖機三輪，順序交錯；query embedding、DB、融合、Memory capture 分別記。不把已快取向量的搜尋時間說成 end-to-end；本輪未加 rerank，未比較 ANN、DB產品或正式 threshold。所有舊封存資料不改，新原件用 exclusive create；診斷／修訂另存。
