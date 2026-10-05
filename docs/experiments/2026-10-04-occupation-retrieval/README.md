# 員工整體工作 → 職位：第一輪向量搜尋實驗

狀態：**隔離研究／試點候選，未接入正式 JD App**。使用者授權依序比較輸入、搜尋方案及參數，並保留詳細數據。本輪暫選 **已發布 B2 正文 → 職務描述與 T／O／P 工作正文 → BGE-M3 dense → Qdrant 精確 cosine 搜尋 → 前 10 個候選職位**。

輸入比較支持 B2 作這批資料的試點預設；加上全部 B1 並沒有改善排序。短工作案例原本選出的 K/S＋混合搜尋，在完整 B2 上反而退步，因此保留原結果後改選 TOP＋dense。**尚未選定可靠的職位接受門檻**；本輪也沒有驗證 JD 的任務覆蓋或訪談結束條件。

## 1. 資料、清理及答案的範圍

| 資料 | 本輪實際使用 | 限制 |
|---|---|---|
| OCS／iCAP 公版 | 新轉換的 815 份合格 JSON，隔離 10 份後固定 805 職位 | schema 合格不代表逐字或身分全部已核驗；未確認官方最新版本 |
| 已發布 Memory | 採購 1 個長訪談快照、庫存 control／compacted 各截止序號 2／4，共 5 個快照 | 只有 **2 個合成員工情境**；庫存 4 快照相關且資訊局部，不能算 4 位員工 |
| 搜尋 probes | 32 個人工合成工作正文，development／holdout 各 16；各含 13 有預期職位及 3 負例 | 沒有另生成自然 B1／B2；兩組職務領域重疊，主要是新措辭，不能代表未見過的職務泛化 |
| relevance grades | 搜尋前固定：3 主要參考、2 可接受相關、1 弱相關、0 未標註 | 工程代理核對，沒有真人專家背書，也沒有逐一標註 805 職位；**0 不等於已證明無關** |

資料來源、原始與清理後輸入、B1 引用及快照截止點見 [cases.json](cases.json)；全文與來源 SHA-256 見 [corpus.json](corpus.json)。固定規則與修訂見 [protocol.md](protocol.md)、[manifest.json](manifest.json)。

清理移除代碼、通用 OPKS 表頭、Markdown 標記及案例內自報職稱，保留項目名稱／正文、否定、責任邊界及未知事項。職位名稱留在 metadata 供回傳，沒有額外拼入 embedding 文本。每個職位目前嵌入成一份文字，重複正文穩定去重；**尚未比較任務切塊、權重聚合或 reranker**。

本輪比較的是從 JSON 欄位組成的不同語意正文，沒有把 JSON keys／大括號當向量輸入。「保留 JSON」與「嵌入正文」可以同時成立；尚未實驗 PDF 直接文字、OCR 與原始 JSON 序列化的檢索優劣，不能宣稱其中一種全面勝出。

索引前隔離的 10 份包含 4 組 code 碰撞的 8 份及 2 份無職位名稱，完整原件與原因見 [quarantine.json](quarantine.json)。其餘 805 份仍有 34 份 code 不符合慣常格式、部分為職位名稱 fallback，保留原值與來源作試點 ID。2 份 description 缺失，因此簡短表示對照明示 fallback 到 TOP，見 [description-missing.json](description-missing.json)。沒有擅修原始檔或任選碰撞版本覆寫。

## 2. 先比較員工輸入

固定 805 職位的 TOP 正文、相同模型及全量精確搜尋。A 是核對原話後人工整理的工作事實基準；B 是已發布 B2；C 是相同 B2 加全部明確引用、exact revision 的 B1。不是把尚未發布候選或不同截止點混入。

| 輸入 | Hit@1 | Hit@5 | MRR | nDCG@10 | 平均 tokens |
|---|---:|---:|---:|---:|---:|
| A：工作事實基準 | 0.250 | 1.000 | 0.500 | 0.509 | 132.2 |
| **B：B2 正文** | **0.500** | **1.000** | **0.667** | **0.691** | **528.4** |
| C：B2＋引用的 B1 | 0.375 | 1.000 | 0.604 | 0.567 | 969.0 |

先在同員工情境內平均，再對 2 情境平均，避免 4 個庫存快照壓過採購。Hit 計 grade≥2；MRR 是第一個可接受職位排名的倒數；nDCG@10 兼顧 grade 及排名。Tokens 是 5 個輸入的直接平均。主要「採購人員」在 A／B／C 分別第 9／3／8；B2 的庫存主要參考職位在 4 快照均第 1。

**裁決：先用 B2 作自動輸入的試點預設。** 原始數據見 [run-05/input-rankings.jsonl](run-05/input-rankings.jsonl)、[逐例 CSV](run-05/input-metrics.csv)、[摘要](run-05/input-summary.json)。run-03 已先得到相同輸入結果，後續沿用快取重現，沒有增加獨立員工樣本。

## 3. 原短案例勝出方案，未通過完整 Memory 回查

原先依事前方法，在 development 短工作正文先選表示，再選搜尋。簡短 description、TOP、TOPKS 的 dense nDCG@10 分別 0.591／0.775／0.787；選 TOPKS 後 dense／sparse／固定 RRF 的 nDCG 分別 0.787／0.655／0.806。於是原方案為 TOPKS＋RRF；development 調得 RRF 常數 20、各路深度 50。

原方案在 13 個正向 holdout 的 Hit@1／5／10 是 7／11／12，nDCG 0.655。但將它用到實際選出的完整 B2，採購主要職位第 1，庫存 control 第 1／4；**兩個 compacted 快照的主要職位掉出前 10**。例如盤點、主管核准及協助年度查核的工作，被排到冷鏈物流、會計或內部稽核。分組 nDCG 降為 0.553。

這表示「短工作正文」不能代表「含未知、交接與責任邊界的整份 B2」。原方案沒有成為本輪最終選擇。保留 [原表示比較](run-05/representation-summary.json)、[原搜尋比較](run-05/method-summary.json)、[原 holdout](run-05/holdout-summary.json)、[完整 B2 回查](run-05/selected-memory-rankings.jsonl)，沒有事後修改 labels 讓它通過。

## 4. 再用完整 B2 比較搜尋方式

這是觀察到失配後的**探索性修正**。相同 B2、相同 corpus／模型，TOP／TOPKS 分別比較 dense、sparse、固定 RRF（常數 60、各路深度 50），先固定方法再調參。

| 表示與搜尋 | 分組 Hit@5 | 分組 Hit@10 | 分組 nDCG@10 |
|---|---:|---:|---:|
| **TOP＋dense** | **1.000** | **1.000** | **0.691** |
| TOP＋sparse | 0.000 | 0.000 | 0.020 |
| TOP＋RRF | 0.500 | 0.750 | 0.265 |
| TOPKS＋dense | 1.000 | 1.000 | 0.581 |
| TOPKS＋sparse | 0.500 | 0.500 | 0.157 |
| TOPKS＋RRF | 0.750 | 0.750 | 0.547 |

暫選 TOP＋dense。不是認定 K/S 沒價值，只是目前整份 embedding 的加入方式沒有改善此試點。K/S 原件完整保留，未刪資料。

原探索計算見 [memory-01](memory-01/memory-method-summary.json)。隨後存成 [compare_memory_methods.py](compare_memory_methods.py)，以同快取重現到 [memory-02](memory-02/memory-method-summary.json)，六組指標與原計算完全相同；重現不算新試驗樣本。完整排名各有 JSONL／逐例 CSV。

因這次修正發生於原 holdout 已看過之後，`candidate-01` 的同一 holdout **只能稱回歸檢查，不能再稱獨立未見資料驗證**。其 13 個正向案例 Hit@1 為 6／13、Hit@5／10 為 11／13、nDCG 0.632。網站案例的標註主要職位第 34、採購主管第 14；另有網站前端等未事先標註而可能相關的結果，亦說明標註不完整。沒有因重選後分數較低而隱藏這組結果。

## 5. 資料庫正確性與參數

同樣向量先用 NumPy 計算全量 cosine／sparse dot／RRF 作基準，再查實際 Qdrant。原 TOPKS 與最終 TOP 各 32 個 probes 的 exact dense 排名、逐項 score，以及 RRF 排名／score 都符合基準，計入同分允許、數量足額、唯一性及順序。最終 TOP＋dense 的 5 個 B2 亦全部一致；主要職位採購第 3、庫存 4 快照均第 1。這證明本輪資料庫計算與基準一致，**不等於候選職位全部語意正確**。

| 最終 TOP 的請求設定（診斷） | 32 查詢平均 top-10 recall（對 exact） | 本機 3 次／查詢的中位延遲 ms |
|---|---:|---:|
| **exact dense** | **1.000000** | 14.29 |
| exact=false，requested hnsw_ef=16 | 0.950000 | 13.82 |
| exact=false，requested hnsw_ef=64 | 0.996875 | 14.96 |
| exact=false，requested hnsw_ef=128 | 1.000000 | 13.06 |

這批只有 805 職位，小樣本延遲受環境波動影響，沒有並行或負載壓測，不能據此宣稱哪個更快。兩個 collection 起測時 status=yellow，indexed_vectors_count 為 1253／1317，points_count=805；原腳本僅等 indexed count≥805，**沒有證明 dense HNSW 全部建成或所有查詢走 ANN**。Qdrant 的 named dense／sparse 各自計數且統計近似，未索引 segment 仍可 exact scan，官方要求等索引穩定再調 graph。因此上表保留為請求設定的診斷數據，ef=64 **尚未完成穩定 ANN 校準，也未採用**。見 [官方調參前置檢查](https://qdrant.tech/documentation/search-tuning/before-tuning-a-qdrant-collection/)。

目前暫用 exact，不依賴上述 ANN 判斷。collection 設 HNSW m=16、ef_construct=100，其設定及完整原件見 [collection.json](candidate-01/collection.json)、[database.json](candidate-01/database.json)。只驗 Qdrant 與離線基準；**沒有比較 Milvus／pgvector 等資料庫產品**，Qdrant 不是已證明的通用最佳選型。

TOP＋dense 在 development 比較候選數 1／3／5／10：有任一可接受職位的案例數是 9／11／12／13（共13）；所有 grade3 主要職位都出現的案例數是 8／10／10／11。選前 10 作查閱候選，沒有強制 top-1 就是員工職稱。混合職務不強迫只選一職位。

拒答門檻以 dense cosine 0.35–0.90、每 0.025 測試；development 要求零負例誤接受、保留至少 80% 正例，暫得 0.675。然而回歸負例中，兩個 corpus 無對應職位的研究案例被拒答，**資訊不足案例得 0.698433，仍被錯誤接受**。因此正式接受門檻維持未定；這些數字不是 67.5% 或 69.8% 的職位符合度。原 TOPKS 的 0.650 門檻也遇到同種失敗。見 [threshold.json](candidate-01/threshold.json)。

## 6. 環境、失敗與保存

| 項目 | 實際設定 |
|---|---|
| 模型 | BAAI/bge-m3，commit `5617a9f61b028005a4858fdac845db406aefb181` |
| 嵌入 | 本機 CUDA、FP16、1024 維、max_length=8192、encode batch_size=1；HTTP 每批最多 8 文本 |
| Runtime | torch 2.10.0+cu128、transformers 4.57.6、FlagEmbedding 1.4.0、huggingface-hub 0.36.2 |
| Qdrant | 官方 Windows release 1.18.2；client 1.18.0；loopback 6335／6336；telemetry 關閉 |
| 快取 | 2454 個唯一文本，原始 dense／sparse、token 長度、批次時間與 UTC；最長 4310 tokens，未截斷 |
| 外送 | 下載公開模型及套件；本輪嵌入資料未送外部模型 API，沒有新增付費模型呼叫 |

完整 image ID、模型 weights SHA-256（與官方 LFS 相同）、release zip hash 及實際儲存路徑見 [environment.json](environment.json)。母 image 的 `HF_HOME` 實為 `/workspace/.cache/huggingface`，原 compose 宣告的 `/root/.cache/huggingface` volume 未承接本次 weights；模型在保留容器的 writable layer，`stop/start` 可沿用，刪除／重建則須再準備模型。離線重算不需這個容器。

| Run／記錄 | 結果及原件 |
|---|---|
| run-01／02 | S: 滿導致保存失敗；分別保留 6／570 條完整快取 prefix、failure.json 及 log。自有 Qdrant mmap 預檢資料移到核准的 C: 工作目錄，全數保留 |
| 啟動診斷 | CUDA image 拉取過慢，重用本機既有 image；下載有界替代嘗試後停止，原下載完成。Windows Gridstore 長路徑失敗，改用專用短 junction 路徑；舊 runtime 保留 |
| run-03 | 15 個輸入比較完成；representation 因 2 份 description 空，在尚無該階段結果時停止。明示 fallback 修訂後固定同 805 集合 |
| run-04 | 表示、方法及 holdout 完成，但 threshold 摘要的 NumPy int64 JSON 序列化失敗；修正序列化後沿用快取重跑 |
| run-05 | 原短案例完整流程成功；完整 B2 補查暴露失配，因此保留但未採納 |
| memory-01／02 | 完整 B2 方法比較與持久腳本重現，相同快取、相同結果 |
| candidate-01 | 最終試點方法的參數、資料庫及完整 B2 回查；原 holdout 明示 regression only |

沒有刪原 PDF、JSON、Memory、JD 或正式 DB，也沒有 commit／push／接 production。詳細裁決見 [progress.md](progress.md)。已完成 run 的輸出不覆寫；重算報告是衍生資料，不算新自然生成樣本。

## 7. 原件導覽與重算

| 檔案 | 內容 |
|---|---|
| `cases.json`／`probes.json`／`corpus.json` | 實际向量輸入、固定分級、原文來源及 SHA-256 |
| 各 run 的 `*-rankings.jsonl` | 每例每 arm 的 score／排名／職位 metadata／grades／metrics。dense／sparse 保留全部 805；RRF 保留兩路候選 union，`returned_candidates` 明列數量；DB 補查保留實際 top10 |
| 各 run 的 `*-metrics.csv`、根目錄 [results.csv](results.csv) | 逐例可讀指標；根 CSV 匯整 725 記錄，包含參數網格和重現，不能當 725 個獨立案例 |
| [summary.json](summary.json) | 選擇、原短案例結果、最終候選結果及限制 |
| `cache/*.jsonl` | 完整向量、tokens、文字 hash、耗時；cache 檔名包含 runtime fingerprint。完成 run 保存所用 keys、byte-prefix 長度及 SHA，以容許未來 append |
| [verification.json](verification.json) | 已離線核查 818 份來源 hash、2454 個向量、725 份排名記錄及320份數據库回傳；128份 exact／RRF 回傳符合計算。DB 補查另包含在725份排名稽核中 |
| `artifact-hashes.json` | 最後封存的檔案清單、大小及 SHA-256，包含本機快取及 logs，排除衍生稽核時間戳檔；可核對資料有無改動 |

重算命令（專案根目錄 PowerShell）：

```powershell
apps/ocs-indexer/.venv/Scripts/python.exe docs/experiments/2026-10-04-occupation-retrieval/verify_results.py --check-seal
```

不用啟動模型或 DB，先核封存 inventory，再核凍結資料、來源、快取 prefix，從保存向量重新計算所有完整階段的排名、分數、固定 labels、指標、top-k／RRF／threshold 網格及 DB 回傳，生成 summary／results／verification。它不是第二個獨立模型品質試驗。19 個研究測試涵蓋清理、空／非有限向量、分級計分、B1 exact revision、RRF sparse 零分假票、真 Qdrant、排名順序與數據損壞。服務停止與資料保留核對見 [services-stopped.json](services-stopped.json)。

保留限制：早期失敗 run 只記腳本 hash，沒有逐版保存 executable；`memory-01` 原來是即時計算，隨後持久化且重現一致。run-05 的 B2 補查腳本 hash 對应新增 dense 分支之前的版本，精確舊腳本未封存；原始回傳、快取與現在的等價 RRF 重算均已保存。本輪成功主流程與最終候選的主腳本 hash 已核對。`cache/` 與 `*.log` 不提交 Git，但檔案實際保留在工作區；**這是本機保存，尚未做第二份備份**。

## 8. 接續元件的界線

已完成本輪輸入比較、搜尋探索、Qdrant 計算驗證及有界參數試驗；接受門檻測試結果為失敗／未定，不以任意分數補成「完成」。要正式採用前，需新增職務領域的自然 B2、凍結新 holdout、補足專家 relevance 與資訊不足標註，再測這個固定候選。

職位檢索目前只能提供參考清單。下一個獨立元件才是「候選職位的任務 ↔ 訪談證據 ↔ 不適用／未知／已確認」的覆蓋核對；尚未設計或實作。不能把公版所有任務都問過，直接當成公司內這名員工的 JD 已完整，仍需核對職務特有、混合與標準未涵蓋工作。
