# 廣蒐＋精搜：員工相關工作的覆蓋與時間

2026-10-04，**兩種檢索表示均已完成本機實驗；尚未通過參數採納條件**。本輪的要求是保留員工主要、次要及低頻工作的相關參考，再交給後續模型判斷。主要職位進入前五，不代表這個要求已達成。沒有接 production、另一次決策模型或主 LLM，也沒有設定 JD 完成指標。

分段廣蒐＋精搜改善了開發情境的覆蓋，但開發資料選出的 cosine 0.65 門檻，刪掉保留情境的庫房盤點參考。**目前不能採用「相似度達 0.65 就保留」，也不能宣稱員工相關工作已完整涵蓋。** 此失敗保留原件，不以看完保留情境後降低門檻來補作驗收。

## 實際比較與結果

使用前輪封存的 805 份 T/O/P 正文與 BGE-M3 向量，公版 OPKS 代碼與表頭已移除，正文及項目名稱保留。職位名稱供回傳與回查，沒有額外拼進向量正文。這輪沒有重選 embedding 模型或向量資料庫；用真 Qdrant exact 核對候選，以免把索引近似誤差混入表示／rerank 實驗。

共 18 個合成員工情境、64 個在公版中核對過支持文字的工作主題。舊 14 個已觀察情境與 M01/M03 作 development，其中 10 個有已標註支持主題、6 個為資訊不足／無主要公版職位的觀察反例。M02/M04 在選完參數後才揭露結果；主要工作衍生自舊情境，存在 family overlap，不能稱為獨立真實員工驗證。標註非窮盡，未確認動作另保留為 unscored。

| 表示 | 廣蒐與精搜方式 | 選參數結果 |
|---|---|---|
| 整體查詢 | B2／整份員工原話各作單一向量；單一查詢對候選全文 rerank | dense-only 與 rerank 均無設定能完整保留全部 development 支持主題 |
| 原話分段 | 每段員工原話分別廣蒐；文件取各段最大 cosine 去重，再取各段最大 rerank logit | rerank 開發選出 N=200、cosine≥0.65、K=20、無 sigmoid 門檻；保留情境失敗，未採納。dense-only 無通過設定 |

N 比較 20／50／100／200；cosine 比較無門檻／0.50／0.60／0.65／0.70；K 比較 5／10／20／50；rerank sigmoid 比較無門檻／0.10／0.30／0.50／0.70。先要求 development 每個支持主題都有至少一份已核對參考被保留，再比較平均正文字符數與 N。參數選擇原件：[整體](selection-development.json)、[分段](passage-pool/selection-development.json)。

分段開發選出設定的結果如下；沒有用 M02/M04 重新調參：

| 範圍 | 完整正例／支持主題保留 | 次要工作保留 | 平均最終文件數／正文字符數 |
|---|---:|---:|---:|
| development：16 個情境、10 個正例 | 10/10／52/52 | 2/2 | 9.56／10,540 |
| 保留情境 M02/M04：2 個正例 | 1/2／11/12 | 1/2 | 14／18,587 |
| 合併描述：18 個情境、12 個正例 | 11/12／63/64 | 3/4 | 10.06／11,434 |

合併共保留 **63/64 支持主題（98.44%，按主題計）**；macro 平均主題覆蓋率是 98.61%，兩者分母不同。完整正例只有 11/12，不能用平均覆蓋率掩蓋漏掉一整項次要工作。合併平均正文字符數約為 805 份全量的 1.44%，但不等於 LLM token 或實際費用節省。6 個無支持標註的觀察反例不算作完整覆蓋，也不把它們回傳的全部參考視為錯誤。原件：[分段結果](passage-pool/comparison.json)、[64 主題逐項追蹤](result-diagnostics.json)。

為區分表示與參數效果，另比較相同原話、同一批 development、N=200／無 cosine 門檻／K=50／無 sigmoid 門檻：

| 查詢表示 | 只按 cosine 保留 | 加 rerank 保留 |
|---|---:|---:|
| 整份員工原話 | 8/10 完整正例 | 8/10 |
| 各段原話合併 | 9/10 | 10/10 |

這是已觀察 development 的控制比較，顯示分段加 rerank 對這批已知工作有幫助；不能當成新員工泛化品質。沒有以這個設定改寫保留情境的選參數結論。

## 漏失發生在哪裡

1. **整體向量淹沒次要工作。** M01「車輛維修＋每週兼做備品採購」，採購參考在 cosine 第 369 名，分數 0.56405；候選最多取 200，rerank 已無法補回。M03 的盤點參考第 67 名，進入廣蒐但未留在 K=50 的最終結果。B2 的部分主要工作也曾被整體 rerank 排出保留範圍。
2. **固定相似度門檻刪掉正確參考。** M04「寵物美容＋每季用品庫房盤點」，盤點支持 `MMP4321-003v4` 在分段 max cosine **第 12 名、0.63576**，仍被開發選出的 0.65 門檻排除。初搜已刪掉的參考，精搜無法恢復。這個公版只支持盤點任務，沒有據此推定員工負責該職位所有任務。
3. **rerank 分數不能當正確機率。** 同一盤點參考在保存的未套 cosine top200 精搜中是第 14 名，但 sigmoid 僅 **0.03265**。這是失敗原因診斷，沒有據此重選設定；也反證「sigmoid 太低就不相關」不是本輪已驗證的判斷規則。

cosine 與 rerank sigmoid 是不同尺度。MAX 不會自行確認否定、團隊或未來責任；本輪 E10 的團隊背景仍保留 2 份參考，部分已知不應直接當成員工主要職位的參考也被保留。這輪衡量的是**來源參考可取得性**，不是完整 precision、本人責任確認或職位判定正確率。後續 LLM 仍須逐項判斷適用任務及權限邊界。

## 時間與資料量

本機 RTX 4060 Laptop 8GB、FP16／batch=1／SDPA，官方 `BAAI/bge-reranker-v2-m3` revision `953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e`。2,271,071,852 bytes 權重 SHA256 與官方 LFS 相符。所有輸入關閉 truncation；超長文件以 token 分窗保留全文，取最大 window 分數，逐窗長度／分數均保存。

分段 E01 的固定工作量實測，每候選文件對 3 段原話精搜，暖機後兩次、文件與查詢已 tokenize、無 cosine 門檻：

| 候選文件 N | 中位數精搜模型迴圈秒數 |
|---:|---:|
| 20 | 1.438 |
| 50 | 3.704 |
| 100 | 7.250 |
| 200 | 14.896 |
| 全量 805 | 65.703 |

同一分段方式下，200 相對全量 805 的模型迴圈時間少 **77.33%**，約 4.41 倍；N=200 表示 600 次段落／文件比較，4 段情境則為 800 次，超長文件另增加 windows。**這不是開發選出 cosine 0.65 設定的實際時間**：該設定 E01 剩 118 份候選；本表用無門檻固定 N，沒有量其端到端時間。它也不是主 LLM 的時間／費用或正式負載 p95。

單一整體查詢的 E01/raw N=200 中位數 6.245 秒、全量 805 為 26.291 秒；它較快但漏次要工作。分段帶來額外精搜工作，不能只引用較快的單一查詢時間來推薦分段。

整體表示 640 次真 Qdrant exact（32 查詢×4N×5cosine）的保存 ID／count 與完整 805 排名一致，已逐筆離線重核。實跑時 assert 分數誤差小於 10⁻⁶，保存統計最大誤差 1.13×10⁻⁷、本機含 HTTP 中位數約 4.20ms；當時未保存每項原生 Qdrant 分數，所以**整體表示的分數誤差統計不能逐項離線重算**。分段另做 58 次 top200 Qdrant exact，保存了原生分數，已逐段由 cache 重算排名／分數，最大誤差 1.19×10⁻⁷；合併候選與離線 805 max cosine top200 一致。E01 三段這一次查詢合計約 0.228 秒；只量 top200 一次，不是每個 N 的檢索中位數，兩項也非正式負載比較。未調 ANN。

首次公開權重下載 1378.016 秒另記，非模型推論；整體／分段 model load 分別 4.634／44.907 秒，不能混入暖機表。本輪新增 4 個整體原話與 46 個去重段落的本機 embedding，**無付費 LLM 呼叫**。下游費用只能在後續真正送出資料時量測。

## 保存、核對與重現

| 原件 | 內容 |
|---|---|
| [協定](protocol.md)、[推論前補充](protocol-amendment-01.md)、[分段協定](passage-pool/protocol.md) | 比較範圍、選參數、時間界線 |
| [有效標註](cases-v4.json)、[標註 manifest](frozen-v4.json) | 64 主題的員工原話、支持任務／P 正文、來源 JSON hashes；v1–v3 保留演進 |
| [整體 execution](execution-manifest.json)、[分段 execution](passage-pool/execution-manifest.json) | 推論前固定程式／輸入／公版／模型來源 |
| [整體 prepared](prepared.json)、[分段 prepared](passage-pool/prepared.json) | 正文、查詢、完整805初搜排名及分數 |
| [DB 當時輸入重建](database-prepared-reconstructed.json)、[來源版本補充](database-provenance-amendment.json) | 審查後反向重建，SHA256 精確符合 DB 原 manifest；只差 embedding origin／新增時間 metadata。不是當時保存的副本；原件未覆寫 |
| [整體 GPU 分數](rerank-pairs.jsonl)、[分段 GPU 分數](passage-pool/rerank-pairs.jsonl) | 6,400 單一查詢／文件對；3,600 分段候選文件、11,600 段落／文件對，逐窗／逐段分數與時間 |
| [整體參數結果](final-metrics.jsonl)、[分段參數結果](passage-pool/final-metrics.jsonl) | 15,360／8,640 結果列、選擇 ID、缺失主題、字符數 |
| [整體計時](timing-summary.json)、[分段計時](passage-pool/timing-summary.json)、[首次下載](model-download-01.json) | 20／10 次暖機樣本，下載／冷啟動另列 |
| [診斷](result-diagnostics.json)、[進度沿革](progress.md) | 控制比較、漏失階段、失敗與修正 |
| [整體核對](verification.json)、[分段核對](passage-pool/verification.json) | 重算選擇 ID／覆蓋／來源 hashes；非領域專家品質驗收 |
| [最終審查](review.md)、[實驗封存](artifact-hashes.json)、[自有服務狀態](service-state.json) | 無未解除 Critical／Important；保存檔案 hashes，研究服務已停 |

實驗計算有 10 個有意義反例測試，含次要工作被漏掉、初搜刪掉後無法復原、空真值、無截斷分窗、最終結果／DB 返回 ID 被竄改，以及偽造開發摘要／選參數、漏存選定比較。Red／Green 原始輸出保留，最後輸出見 [test-final-green.txt](test-final-green.txt)。獨立審查指出核對器原先信任保存的開發摘要及 DB 完成標記，已補成由逐筆結果與凍結標註重算全部摘要，要求選擇與比較一致，並重核 DB 返回；修正原件見 [audit-amendment.json](audit-amendment.json)。實際模型分數／參數結果未改。分段原分析入口曾因 import 路徑失敗，原檔保持凍結，修正另存 [analyze-v2.py](passage-pool/analyze-v2.py) 與 [analysis-amendment.json](passage-pool/analysis-amendment.json)；只修入口與一次 top200 檢索的時間欄位名稱，未改評分、資料或選參數。

以 repository 根目錄的既有 Python 執行，無需重新跑模型：

```powershell
apps/ocs-indexer/.venv/Scripts/python.exe -X utf8 docs/experiments/2026-10-04-retrieve-rerank/verify.py --check-seal
apps/ocs-indexer/.venv/Scripts/python.exe -X utf8 docs/experiments/2026-10-04-retrieve-rerank/passage-pool/verify.py
apps/ocs-indexer/.venv/Scripts/python.exe -X utf8 -m unittest discover -s docs/experiments/2026-10-04-retrieve-rerank -p 'test_*.py' -v
```

## 未完成的驗收與下一步

這輪完成了實驗與漏失定位，**檢索元件的涵蓋驗收仍未完成**。分段是有證據的後續方向；相似度 cutoff 的安全性、各工作主題被全域排名擠掉、真實 Memory 如何保留低頻工作／否定與更正，都還需驗證。

下一輪先在已觀察資料上比較不依賴單一絕對門檻、各工作主題保留候選的機制，固定方案後以新的保留情境與完整工作標註驗證。M02/M04 已被觀察，只能作回歸反例，不能再稱新 holdout。公版無對應的工作須獨立列出，不能把「沒找到公版」當作員工沒有這項工作。需要真實員工及人工核對後，才有條件宣稱參考能涵蓋實際工作。

涵蓋通過後才進行「同一廣蒐＋精搜結果直接交主 LLM」與「先另一次決策模型篩選再交同一主 LLM」比較；JD 完成判定是更後面的驗收，不能用候選職位底下全部任務自動推定員工應負責的完整工作清單。

官方支持先取得候選再 rerank，相關契約見 [BGE 文件](https://bge-model.com/bge/bge_reranker.html)、[官方模型卡](https://huggingface.co/BAAI/bge-reranker-v2-m3)、[Qdrant candidate depth](https://qdrant.tech/documentation/search-tuning/candidate-depth/)。本輪的分段 MAX、候選數、門檻、標註及採納條件是 Caliburn 的研究取捨，並非官方推薦數值。
