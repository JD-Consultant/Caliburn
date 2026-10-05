# 公版參考 API 實作驗證

2026-10-05。本目錄是[已授權 API 施工](../../2026-10-05-occupation-reference-api.md)的工程證據，
沒有新增相關性盲評。舊實驗保持原貌；以下均不代表全庫 Recall、通用最佳參數或 JD 完整度達標。

| 證據 | 檢查內容 |
|---|---|
| [server-replay-02.json](server-replay-02.json) | 最終 adapter 版本，真 Qdrant 1.18.2；805 來源／8,068 T，八案前五一致；快取向量／logit、每案完整 API 回覆及輸入 hash |
| [server-replay-result.json](server-replay-result.json) | 權重 metadata 加入前的真 server 重播，保留先前結果 |
| [replay-result.json](replay-result.json) | 首次 QdrantLocal 重播，完整來源及結構檢核 |
| [model-smoke-result.json](model-smoke-result.json) | 禁網路 GPU，1 個 fresh embedding＋5 組 fresh rerank；版本及數值差 |
| [live-search-result.json](live-search-result.json) | 新 API TestClient＋真 Qdrant／GPU HTTP；F01 完整聯集 34 組 fresh rerank，64 個來源 task reads；索引向量仍為舊快取 |
| [pytest-final.txt](pytest-final.txt) | 最終 86 項回歸的命令結果 |
| [verification.json](verification.json) | 命令、結果、範圍及保留限制 |
| [source-hashes.json](source-hashes.json) | 本輪實作／測試／證據腳本與結果檔 SHA256 |
| [services.json](services.json) | 僅本輪標籤容器的身分與停止狀態、啟動失敗記錄 |

重現腳本：[replay.py](replay.py)、[model_smoke.py](model_smoke.py)、[live_search.py](live_search.py)。
`replay.py --qdrant-url <local-url> --collection <new-name> --output <new-file>` 僅可對新的
collection 及輸出檔執行；使用同一凍結資料，不改舊實驗。GPU 腳本沿這次固定公開權重及
本機測試服務，不呼叫付費 API。

環境起初有兩個邊界問題：Windows 沙盒拒絕 pytest 暫存目錄／uv cache，以核准的本機讀寫
權限完成；Docker Desktop internal network 的 host port 無法連線，另用只綁 localhost 的
自有 Qdrant。三次 GPU 容器準備失敗分別是映像沒有預期 Python 命令、沒有 /opt/venv 路徑、
以及 BGE 公開快取實在舊容器內而非舊 volume。讀取既有公開權重後固定 revision，禁網路
實測通過；失敗容器保留身份，不將它們列作通過。沒有啟動會寫封存實驗的舊 bootstrap。
