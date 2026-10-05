# 廣蒐＋精搜：覆蓋、參數與時間實驗

- 狀態：使用者授權的隔離研究；2026-10-04，尚無正式採納參數。
- 目標：先保存員工相關工作參考，再縮減交給後續 LLM 的資料。這輪不執行決策模型／主 LLM，也不把搜尋結果當 JD 完成判定。
- 流程：BGE-M3 dense 廣蒐 → BGE reranker 精搜 → 保留職能標準及來源。另一次決策模型篩選是後續實驗。

## 固定與比較

沿用封存的 805 份 T/O/P 正文、BGE-M3 FP16 向量、14 個情境的 B2 與原話。移除 OPKS 代碼及表頭、保留正文；職位名稱是回傳 metadata，沒有額外拼入向量正文。另補四個混合工作情境，使用原話作查詢；這不是新 B2 效果測試。舊情境已觀察過，全部作 regression／development，不稱為新 holdout。

1. 廣蒐候選數 N：20、50、100、200；dense cosine 最低分：無、0.50、0.60、0.65、0.70。
2. 精搜：同一查詢／候選的 cross-encoder 原始 logits；另外保存 sigmoid 分數。sigmoid 不是正確機率，也不與 cosine 共用門檻。
3. 精搜保留數 K：5、10、20、50；sigmoid 最低分：無、0.10、0.30、0.50、0.70。
4. 同一候選池比較未 rerank／rerank；先算品質，再以通過覆蓋的候選比较資料量與時間。不用少送資料掩蓋漏搜。

BGE reranker 使用官方模型 `BAAI/bge-reranker-v2-m3`，先保存實際 revision、權重／tokenizer hashes、套件及 GPU。使用 transformers 官方 cross-encoder 方式，不另接產品服務。FP16、batch=1；關閉 truncation。超長文件依段落及 token 長度分窗，保留全部文字，文件取最大 window score；保存所有 window 長度、分數與計算時間。此長文件策略是本輪研究取捨，不是已驗證最佳策略。

## 覆蓋怎麼判定

在 rerank 結果產生前固定工作主題標註：每項含員工原話、本人行動／對象／成果、頻率／權限邊界，以及公版正文的任務代碼與支持文字。代碼只供回查，不進向量或 reranker。混合工作保留次要、低頻責任。無對應公版／未確認工作的項目另列，不把它們算成搜尋漏失。

本輪標註是工程語意核對，非領域專家真值；相關文件清單非窮盡。至少一個已標註的支持文件被保留，才算該主題具備可回查參考；這不表示該文件所有任務都是員工責任。任務代碼與支持文字仍須逐項核對，避免用職位命中冒充工作覆蓋。

保存：主題覆蓋率／完整覆蓋的情境數、次要主題覆蓋、標註文件 recall、主要職位／已知易混淆職位排名、被各階段刪掉的主題及 ID。資訊不足與無主要公版職位的舊負例用於觀察分數，不能將所有回傳參考自動判為錯誤。

選參數只看 development，較新的混合情境 holdout 固定前不得觀察 rerank 結果，測完不調參回稱 holdout。以 development 全部可支持主題保留為實驗篩選條件；若未通過就列出反例，不放寬門檻聲稱驗收。真實員工與更大樣本仍待驗。

## 時間與成本

保存 embedding 的 cache 狀態／新增推論、精確向量檢索、rerank 每一對的 GPU 同步時間及總時間、冷啟動／下載時間、候選／最終文件數、正文 Unicode 字數與 tokenizer token 數。tokenizer 不是下游 LLM 計費 token；本輪無付費 LLM 呼叫。比較固定查詢的 805 份全量 rerank 與先廣蒐再 rerank，不能把未 rerank 的向量搜尋時間當作兩階段時間。

品質參數 sweep 可重用保存的相同 pair 分數；計時另用固定 development 情境實跑 N=20/50/100/200/805，至少兩次暖機後量測。以本機小樣本 median／範圍報告，不能推論正式負載 p95。離線向量與 Qdrant exact 核對已在前輪完成；若本輪只有離線檢索，不宣稱 ANN latency 或向量 DB 新驗收。

最多 45 分鐘模型推論；若無法完整量測，保留失敗與完成範圍，不偷偷截斷輸入或以估算當實測。只啟停本輪自有 GPU 容器；保留前輪封存與資料。

## 第一手契約

查閱 2026-10-04：[BGE reranker](https://bge-model.com/bge/bge_reranker.html)、[官方模型卡](https://huggingface.co/BAAI/bge-reranker-v2-m3)、[模型 config](https://huggingface.co/BAAI/bge-reranker-v2-m3/raw/main/config.json)、[Qdrant candidate depth](https://qdrant.tech/documentation/search-tuning/candidate-depth/)。官方支持先取候選再 rerank；本案候選數、分數門檻、覆蓋標註與選參數規則由實驗檢驗，不是官方推薦值。
