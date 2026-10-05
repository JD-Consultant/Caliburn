# 2026-10-05 Caliburn 初搜廣蒐 CPU 快取探索協定

目的：比較固定數量與分數自適應初搜能否保留已判定的主要參考及工作面向，並記錄候選工作量。此為研究，不修改正式 API 或 production。只讀凍結分數，不呼叫 embedding、reranker、LLM、provider、DB，也不啟停服務。

固定使用 O 原話整段八個 query，BGE-M3 1024 dense exact cosine，805 父公版。D 為整份公版，T 為每父任務 chunk 最高 cosine。讀取前輪 all-rankings.json，獨立由原 chunk score 重建 parent max 與排序檢查。父排名按分數降序、ID 升序。

輸入釐清（grid尚未執行）：F01–F05 的O為員工原話；H01–H03既有O快取含角色標籤及顧問提問的歷史原對話，而評判cases.employee_statement僅連接員工回答。保留既有O輸入與hash，按source_spans重建員工摘錄驗證一致。首次preflight因錯把两者假定字串相等而停止；preflight-failed-input-manifest.json、preflight-policies.json留存當時設定，修正驗證後才首次計算grid，不新增或更換模型輸入。

以下 grid 在本輪計算前固定，完整保留每個參數的結果，不能只報事後最好的門檻。每個規則分別套 D-only、T-only、D/T 完整聯集（兩路各自選取，再去重，不另截斷）。

| 規則族 | 事前參數 | 邊界定義 |
| --- | --- | --- |
| 固定 K | 5、10、20、40、80 | 每路前 K 父 |
| 絕對 cosine | .500 至 .850，每 .025 | score >= 門檻；可選零份 |
| 距最高分區間 | .01、.02、.03、.05、.08、.10、.15 | top_score - score <= 區間；每 query、每路使用自己的最高分 |
| 首次相鄰 score gap | .005、.01、.02、.03、.05 | 找到第一個相鄰差 >= 門檻時，保留斷點上側 prefix；完全沒有則保留805 |
| 絕對 cosine＋保底 | 上述15門檻 × 前3／前5保底 | threshold 選取與小 prefix 聯集；獨立規則族 |
| 自然全集上界 | 805 父 | 全部保留，只作已知保留上界 |

另在首次執行前加入兩路不同參數的小型 grid：D-K × T-K 為上述5×5；D/T絕對門檻各為 .60/.65/.70/.75/.80 的5×5；D/T相對區間各為上述7×7。只新增非對角（不同值）20＋20＋42個，避免重複。沒有展開所有不同規則族的笛卡爾乘積。

共 63 規則 × 3 路徑模式 ＋82 = 271 policies，2,168 個 policy×case。所有規則的唯一自然上限為可用805父，除固定 K 外沒有硬 cap。全部輸出完整 selectedIDs；每路數量及其已知保留單獨列出，完整 prefix 可由 full-route-rankings.json 的名次與 selected_count 還原。

評判沿 initial-retrieval-depth/targets.json 的12個已知 grade3 case×doc、8個已有支持的工作面向。H01 的 grade3 及面向保持 unassessed，不用0/0=100%。F05/AVA2172-001v4 與 H03/MMP1324-001v4 排除後的10個代表作獨立敏感度結果；不改原標註。未評公版不當negative，初搜僅判已知正例保留，不計精確率或全庫Recall。

候選總數／每案數量是後續可能的 rerank pair 工作量，不是實测latency。絕對分數不保證跨 query 同尺度；按query列top/bottom、邊界及保留，另呈各規則族完整範圍。相對最少候選且保留全部已知正例只能是此既有池的探索結果，不能視作全庫最優或holdout驗證。

執行前後驗 memory-public-unit-retrieval、rerank-union-candidate-replay、initial-retrieval-depth 三份seal（原檔不得改），固定 source hashes。重現 O/D/T/Top20 原控制247去重pairs與12/12代表、8/8面向，執行規則機制邊界測試；結果封存自己的artifact-hashes.json。
