# 員工工作內容 → OCS 職位：分階段實驗

狀態：使用者於 2026-10-04 授權的隔離研究；不是正式 RAG 接線或 JD 完成條件。範圍依 ADR0079 的 RAG 獨立界線及本次對話。所有結果（含失敗）留存，不改原始 PDF、既有 JSON、Memory 或 JD。

## 固定資料與答案

- 初始 `apps/pdf-to-json/data/json-checked-2026-10-04` 的 815 份合格 JSON；來源 manifest 見相鄰 OCS JSON 修復實驗。索引前發現 4 組 code 碰撞（8 份，含 Unknown）及 2 份職位名稱空白；在未看搜尋結果前隔離，凍結剩餘 805 份，原件與原因見 `quarantine.json`。排除檔名標示歷史的資料；未向官方證實所有資料仍為最新版本。部分唯一 code 實為職位名稱 fallback，保留原值與來源、列警示，不當成已核驗的官方 code。
- 嵌入文字保留項目名稱／正文，排除 T/O/P/K/S 代碼、表头及 JSON keys；職位名稱只作回傳 metadata，不作嵌入捷徑。先以「職務描述＋所有 T/O/P 正文」每職位一份作固定比較基準；重複正文只算一次。
- 第一階段沿用已有自然生成、已發布 B1/B2 快照及相同截止點的合成員工原話：採購來源序號 44；庫存資料 control／compacted 各序號 2、4。庫存是局部工作資訊，只評候選參考職位，不能判定已完整描述員工。兩個生成組、两个截止點不算四名獨立員工。
- A 為依原話獨立整理及核對的工作事實基準（工程代理核對，沒有真人專家背書）；B 為發布 B2 的正文；C 為同版 B2＋所引用 B1 的正文。三組同截止點、同員工；排除自報職稱但保留上級／跨部門責任。原始文字與清理後文字都保存；未知與否定不擅自改成肯定。Markdown 標記拿掉，具語意的項目名稱及「尚待確認」標示保留，只有 OPKS 表頭等 generic 欄名排除。
- 答案由原話與 OCS 工作範圍人工核對，在搜尋前凍結，不由搜尋結果反推。相近職位以 3（主要參考）、2（可接受相關）、1（較弱相關）、0（無標註相關）分級；0 不是專家判定的絕對無關。保留標註理由及困難負例。
- 第二／三階段另存跨職務合成工作事實 probes，未複製 OCS 原句；development 用於比較／調參，holdout 不参与選型。這些沒有自然 B2 生成，只驗索引／搜尋，不混進第一階段品質分數。混合職務、資訊不足及沒有合適職位的案例分開記錄。

## 階段與選擇規則

1. **輸入比較**：固定 BGE-M3 dense、相同 OCS 文字，以 NumPy cosine 全量精確搜尋排除 ANN 影響。報每例完整 805 排名、top-1／5／10 命中、MRR、nDCG@10、查詢長度與主要負例排名。優先 graded ranking，再看輸入大小；樣本小或平手時只選試點預設，不宣稱跨員工最佳。
2. **表示與搜尋品質**：先固定第一階段選擇。比較 T/O/P 正文、加 K/S 正文及「職務描述，缺失則用 T/O/P」的簡短文本對照（805 份中 2 份 description 空白，在 representation 比較尚無結果前修訂為明示 fallback，見 `description-missing.json`）；比較 dense、sparse、兩者 RRF。先分開表示效果與搜尋效果。再核對 Qdrant 同向量的 exact 結果與離線全量結果，檢查 ANN recall、排名、誤差、延遲；資料庫算對與職位判得對分開。跨職務 probes 是人工合成的工作正文，沒有自然 B1/B2，因此只驗索引／搜尋，不能驗 B2 生成的跨職務品質。
3. **參數**：development 選 top-k／混合候選深度、RRF 常數及可否使用拒答門檻，再固定設定檢查 holdout。Cosine 不是職位適合機率；RRF 分數不可沿用 cosine 門檻。資訊不足、混合職務和 corpus 不含職位時，不強制 top-1 作正式職稱。若樣本不足以校準可靠拒答，記錄未能選定，不編造正式百分比。

## 可重算及執行界線

- 本機 BGE-M3，1024 維、max_length 8192、固定精度／tokenizer／實際模型 commit；記錄 token 長度、截斷、每次呼叫輸入雜湊、回傳向量及耗時。模型下載只有公開模型；員工資料不送外部 API。本次只有合成／公版資料。
- 專用 Docker project `caliburn-ocs-eval`、loopback 8082；Qdrant 官方 Windows 1.18.2 release 在工作區 `tmp/ocs-eval-qdrant`、loopback 6335／6336。預檢 collection 的 mmap 配置占用大量空間，令 run-01／02 保存失敗；其原件移存已允許的 C: 工作目錄，新 runtime 亦使用該目錄的獨立 storage，絕不刪正式資料。地址及設定見 `environment.json`。原 Docker pull 過慢而改用官方 binary，SHA-256 保留。不刪現有容器、collection 或 volume。模型環境若無法啟動，保留失敗原因及有限替代測試，不把字面搜尋冒充向量結果。
- 原件置於本資料夾：凍結資料、manifest、完整 rankings JSONL、逐例 CSV、向量快取、模型／容器版本、stdout／error logs、摘要及選擇理由。新 run 禁止覆寫；快取鍵包含模型 fingerprint 與文字 SHA-256，輸入改變則失效。
- 生成／嵌入不得靜默漏項、非有限值、空內容、重複職位 ID 或超長截斷；發生異常立即保存並停止該批。每批可從已成功快取接續，不重跑成功項目掩蓋失敗。
- 預估最多 3×815 corpus 表示＋少量 queries；先小批驗證再全量，單批只有一個 GPU encode 序列。快取向量不提交成巨大 Git 檔；詳細數據保留在工作區，衍生原件可追溯到 SHA-256。

## 方法來源

[BGE-M3 模型卡](https://huggingface.co/BAAI/bge-m3)提供 dense／sparse、1024 維、8192 tokens 與不需 query instruction 的公開契約；不代表本案職位辨識品質。[Qdrant hybrid queries](https://qdrant.tech/documentation/search/hybrid-queries/)說明 RRF 依排名融合；[IR evaluator](https://www.sbert.net/docs/package_reference/sentence_transformer/evaluation.html)提供 relevance-based 的 MRR／Recall／nDCG 評估方式。本案取捨是先控制變因再選參數。
