# 獨立結果核查

2026-10-04，由 `/root/review_occupation_experiment` 按 requesting-code-review skill 唯讀核查；不改檔、不操作模型或服務。

初次審查的三項 Important 已在主流程正式比較前修正：共用排除 sparse 零分票的 RRF、完成 run 的 cache byte-prefix hash／used keys、足額且唯一有序並允許同分的 exact ranking check。反例與修正見研究測試及 progress.md。

最後審查重新執行離線 audit，核 818 份來源、2454 個向量、725 份排名、320 份 DB 回傳；128 份 exact／RRF 正確。另以獨立 nDCG 公式及 statistics 核 README 的輸入分數、holdout 命中數、B2 失配、參數及延遲。A/B/C nDCG 為 0.508993／0.691321／0.567041；原短案例 holdout Hit@1/5/10 為 7/11/12，最終候選回歸為 6/11/11，主要 B2 職位排名 3/1/1/1/1；0.675 門檻對 0.698433 的資訊不足輸入錯誤接受，均符合保存原件。

結論：沒有 Critical。補足下列證據界線後，沒有阻擋本輪隔離試點結案的 Important；不構成正式採用、真人泛化或 JD 完成判斷。

| 意見 | 處理 |
|---|---|
| ANN 起測 status=yellow，indexed count 1253/1317、points805；count 包含 named dense/sparse，原等待條件無法證明 dense HNSW 建成 | README 表改為 exact=false／requested hnsw_ef 診斷；明列穩定 ANN 校準未完成。最終選 exact，不依賴該證據 |
| Minor：重算未加 --check-seal，glob 不直接拒絕完整排名檔缺失 | README 重算命令加 seal 核對；audit另核必要階段、每階段筆數、唯一case/arm、分組與候選數量 |

ANN 判斷追溯 [Qdrant 官方調參前置檢查](https://qdrant.tech/documentation/search-tuning/before-tuning-a-qdrant-collection/) 與 [collection 契約](https://qdrant.tech/documentation/manage-data/collections/)；正文數值依本機原件，沒有用外部資料替代本輪實測。
