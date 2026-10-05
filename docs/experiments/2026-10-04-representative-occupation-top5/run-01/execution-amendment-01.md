# 執行修正：現有 Qdrant client 的生命週期

首輪已完成 15 個新查詢 embedding，接著在進入 `with QdrantClient(...)` 時發生 `TypeError: 'QdrantClient' object does not support the context manager protocol`。錯誤發生在任何 DB 排名及 reranker pair 之前；校準請求獨立且不受此 Python 用法影響。

依已安裝 client 及前輪有效用法，改成明確建構、try/finally close，並重用首輪已保存的同版新向量，不重算、不覆寫。queries、員工需求、corpus、評審可見內容及參數不變。原 execution-manifest.json 保留，execution-manifest-02.json 綁修正腳本與已完成向量／runtime，且保存原 manifest hash。不是根據排名或評分調方法。
