# 職位向量搜尋實驗執行計畫

> 執行方式：superpowers:executing-plans，由本代理逐階段執行；本次使用者已授權測試及選型，毋須重複施工確認。不 commit／push／改 production。

**Goal:** 有證據地選擇員工工作輸入，再驗職位搜尋，最後校準參數。
**Architecture:** 隔離實驗腳本重用現有 HTTP 嵌入服務，離線 exact 作 ground truth，Qdrant 只寫專用測試 collection。
**Tech Stack:** Python、NumPy、BGE-M3、Qdrant 1.18.2。
**Spec:** [事前實驗方法](../experiments/2026-10-04-occupation-retrieval/protocol.md)。

## 全域限制與審查重點

保留失敗／來源／所有分數；職稱不進查詢或 corpus text；OPKS code／表頭不嵌入；同版發布 Memory、來源截止點；合成資料限制必須寫入結論。高風險反例為：相近主管職務壓過執行人員、反覆出現的 K/S 被過度加權、空查詢／超長截斷、資料集洩漏或 holdout 調參、少量庫存資料被誤稱完整員工職位。

### Task 1：凍結來源與可靠計分

**Files:** 本實驗 `prepare.py`、`evaluation.py`、`test_evaluation.py`、`cases.json`、`manifest.json`。
**Interfaces:** 清理文本／corpus records；`ranking_metrics(ranked_ids, grades)`；`rrf(rankings, depth, constant)`；凍結的 source hashes 與案例。

- [x] 先驗排序反例、多可接受答案、重複 ID 不雙計、空／非有限向量與 no-match 不強制命中。
- [x] 實作最少評分與清理／資料準備，保留原件及每處 transformation。
- [x] 執行受影響研究測試；比對 cutoff、去職稱、code 清理與 corpus count。

### Task 2：本機模型與分階段配對比較

**Files:** 本實驗 `experiment.py`、`compose.eval.yaml`、每個 run 的 immutable JSONL／NPZ／CSV／logs。
**Interfaces:** Task 1 的凍結 records／grades → 以模型 fingerprint cache 的 dense+sparse → complete rankings／metrics。

- [x] 先啟动並保存實際 runtime／revision，小批驗證維度、有限值、token 長度／截斷。
- [x] 全量固定 corpus 比較 A／B／C，保存逐例排名後選試點輸入。
- [x] 只在 development 比較表示及搜尋；固定選擇後評 holdout，不回調。
- [x] Qdrant exact／ANN 比離線 ground truth，保留失敗、recall、延遲。

### Task 3：校準、報告與獨立核查

**Files:** 本實驗 `README.md`、`results.csv`、`summary.json`、`verification.json`；實驗入口只加路由。
**Interfaces:** 未改原件 → 重新計分／雜湊核查 → 可點閱選擇及限制。

- [x] development 網格後固定參數檢查 holdout；拒答資料不足則明列未定。
- [x] 離線重算全部結果、檢查 manifest；執行研究測試及一次 fresh-context review。
- [x] 回報實測結果與驗證層級；不宣稱已解決 JD 結束或真員工泛化。

執行結果：[實驗報告](../experiments/2026-10-04-occupation-retrieval/README.md)。原短案例勝出方案在完整 B2 上失配，保留原結果後探索性改選 TOP+dense；因此最終同一 holdout 只屬回歸，另見報告的限制。正式門檻未定，ANN 校準證據不足，不把此計畫勾選完成當品質驗收。
