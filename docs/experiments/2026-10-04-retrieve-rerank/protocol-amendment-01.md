# 推論前補充：分窗及計時界線

2026-10-04，在任何 reranker 分數產生前記錄；原 protocol.md／frozen.json 不改。

初版協定寫「依段落及 token 長度分窗」，worker 實際採 tokenizer token 滑窗、overlap=64，保留全部 token。此輪不再加段落切分，避免引入另一個尚未測的條件；查詢保留完整，若查詢本身使 passage 容量不足就明確失敗。

本輪 GPU benchmark 是**已載入模型、已預先 tokenize 文件與查詢的暖機 rerank loop**，保存 tensor 準備與 GPU forward、不是完整冷啟動端到端時間。文件預先 tokenize 是可重用的索引準備；另外保存全部文件 tokenize 的耗時及每份查詢 tokenize 的耗時。N benchmark 固定無 cosine 过滤、無 final score 過濾，量測 N 對模型實算的成本；不能將這些時間冒充另一組已套門檻的實測時間。

向量資料庫 exact 的不同候選數／cosine 門檻另行實跑，核對與離線 cosine 完整排名一致。只報各段實測及必要的加總估算，不將 cache hit 的 embedding 當成新查詢端到端推論，也不宣稱下游 LLM 延遲已測。
