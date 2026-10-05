# 廣蒐＋精搜實驗進度

2026-10-04；研究授權沿本輪對話，限隔離本機試驗；不 commit／push／接 production。

- 固定：18 個合成情境、66 項來源支持的工作主題；舊 14 情境作 regression。四個新增混合情境有 family overlap，M01/M03 作 development，M02/M04 只在 development 選參數後揭露。未標註動作／頻率／權限例見 frozen.json；不能說已涵蓋真實員工全部工作。
- 廣蒐參數：N=20/50/100/200，cosine=None/.50/.60/.65/.70；精搜K=5/10/20/50，sigmoid=None/.10/.30/.50/.70。
- 本機 BGE-M3 用前輪封存 cache，另產生四個新增查詢；原有 28 個完整排名已重現。自有 `caliburn-ocs-eval-embedder-1` 已停。
- 準備程式最初用未正規化內積，與舊 cosine 排名不符（342 個尾段位置差異）；改動 dtype 本身不能修正。核對 `validate_dense`，使用 float64 並正規化後差異為 0。失敗沒有被拿來算結果，原始四個新增向量保存於 new-query-cache.jsonl。
- 評分反例 5 個 Red → Green；再新增「rerank 不能還原廣蒐已刪候選」反例 Red → Green。6 個單元測試通過；原始輸出已保存。
- `caliburn-ocs-rerank-eval` 是本輪自有容器，image SHA f21629b9ae4ed11231768edfaed0f40d41d85d6ea9a71e8096a3d96ea0311772。公開模型正在下載；實際 hub cache 位於 /workspace/.cache/huggingface，容器內保存；只回報權重 hashes，不把 2.27GB 寫入剩約2.2GB的 S: workspace。
- Reranker revision 已解析為 953dc6f6f85a1b2dbfca4c34a2796e7dde08d41e；公開 model.safetensors LFS SHA256 為 d9e3e081faff1eefb84019509b2f5558fd74c1a05a2c7db22f74174fcedb5286，2,271,071,852 bytes。尚未核完下載。
- 下載進程是舊版已載入的 download_model.py，不會自動執行後來追加的 gpu_worker。下載結束後需 `docker start caliburn-ocs-rerank-eval`；它會從已有 cache 讀取權重，才執行現在已追加的 GPU worker。檢查 model.json 與 GPU 輸出再動作，不重複下载或删除 cache。
- worker 保存32查詢×200候選的全部分數，另 E01/raw、E04/B2 各 N=20/50/100/200/805 兩次暖機計時。quality outputs 尚未存在。download cold time 與推論45分鐘上限分開。後續執行 analyze.py，只用development選參數。
- 獨立只讀 reviewer：/root/review_occupation_experiment 正核對工作來源、評分及計時界線。結果／報告審查尚未完成。
- reviewer 在任何分數產生前指出 E04/M02 的遠端權限不應推定 VPN，改引用 T1.3/P1.3.4；M01/M02 催貨補 T2.1/P2.1.1。原cases/frozen保留，修正版 cases-v2.json／frozen-v2.json 是評分有效標註，支持文件 ID 與查詢文字不變。計時／token 分窗補充見 protocol-amendment-01.md。
- 新實跑 640 次 Qdrant exact：32 查詢×4N×5cosine門檻，全部與完整離線 cosine排名／分數一致，最大誤差小於 1e-6。collection與查詢原件已保存；這不驗 ANN 或主LLM。

承接：查看 downloader 與model.json → 驗 upstream LFS hash → 同一容器重新 start 執行worker → 收齊rerank-pairs與timings → analyze.py → review → report/seal/入口 → 停自有容器、保留原件。沒有決策模型或主 LLM 呼叫；新正式JD完成條件未定。

## 第一表示結果與第二表示

- 第一表示完成：32查詢×200候選=6400對cross-encoder，20個暖機benchmark；15360個參數結果已重算核對。development沒有任何組合完整保留64標註範圍內的相關主題，因此dense_only與rerank均無選定參數，未揭露holdout評估來調參。
- development反例：M01整體query的採購參考rank369/.5640，超過200池；M03盘點參考rank67/.6261。rerank N200/K50仍漏M01、M03，另E04/E05/E07的B2主要來源被排出保留範圍。
- 已告知使用者，依持續研究授權測第二表示：[passage-pool/protocol.md](passage-pool/protocol.md)。原訊息分段廣蒐max cosine去重，同一員工各段joint score最大值精搜；還是回傳整體參考集合，不推定唯一職位或JD完成。
- 第二表示18原話員工、46個去重段落embedding、58次真Qdrant查詢，合併top200與805份exact max cosine一致。新模型沒有下載；Docker snapshot symlink複製在Windows失敗兩次，改複製已核對公開blob實檔至允許C槽快取，model權重雜湊保持不變。
- `caliburn-ocs-rerank-passages` 本輪自有容器，network=none，公開model與第一表示唯讀，僅passage-pool目錄可寫；第二表示正在GPU推論。自有embedder已停；Qdrant自有PID38468待本輪結束後核身分停止。
- v4是有效標註，共64項；6個評分反例仍通過。第一表示worker、source與結果保持不改；最终報告／seal待第二表示及独立审查。

## 本輪結果與核對

- 第二表示GPU完成：18員工×200候選=3600文件分數，11600段落／文件比較，10次暖機bench，8640參數結果列；所有原話及805正文完整保留，無截斷。分段MAX全量排名、58次真Qdrant及全部結果ID／主題已重算。
- 開發選參數rerank N200／cosine0.65／K20／無sigmoid門檻；dense-only無通過設定。開發52/52支持主題、10/10正例完整；保留情境11/12主題、1/2正例完整。合併63/64主題、11/12正例完整，次要工作3/4。**涵蓋採納未過，無正式參數**。
- M04盤點支持MMP4321-003v4，分段max cosine第12名／0.6357555763，被0.65門檻初搜刪除。保存未套cosine top200的精搜第14名／sigmoid0.0326513785，僅作漏失診斷，不修改選擇或重作holdout採納。
- 控制開發比較：原話相同、N200／無cosine／K50／無sigmoid，whole dense/rerank完整8/10，segments dense9/10、rerank10/10。原話分段有支持證據，尚非真實Memory自動切主題驗收。
- 分段E01三段／每候選文件，暖機已tokenize且無cosine，N200中位14.8959秒，全量805為65.703秒，模型迴圈少77.33%。不是chosen設定時間（該E01只118候選）、主LLM費用或端到端負載p95。
- 分段原分析入口import失敗留下analysis-cli-red，analysis-v2與amendment另存，不改frozen原程式／模型分數。實際選參數／coverage不變。
- reviewer另找核對器錯信保存開發摘要及未強制comparison=chosen的Important；已用兩個真保存資料篡改反例Red重現，補audit_selection自逐筆結果／frozen metadata重算480組全部摘要與選擇／comparison集合。9個測試Green，兩份audit重跑通過，原scores／參數結果未改。
- 已核對Qdrant PID38468 exe路徑後停止；6335/6336無listener，三個本輪自有GPU容器均exit0。公開模型cache與全部實驗原件保留，服務狀態見service-state.json。
- 本輪完成實驗／反例定位，檢索涵蓋驗收仍未完成。未呼叫另一次決策模型或主LLM，未接JD完成。M02/M04已觀察，下一輪只能作回歸；下一輪須固定方案後有新的保留情境與完整工作標註。
- 最後來源審查找到DB manifest的prepared hash與現件不同：embedding origin／新增推論時間metadata後補。由現件移除origin及重置M01-M04新增時間為0後，反向重建副本SHA256精確符合DB當時65be6481…；corpus、查詢、排名／分數、dense計時未變。重建與限制另存provenance amendment，原manifest／prepared保留。
- 原640次DB查詢未保存逐項native scores，只保存IDs/count/max error；README已界定其誤差為實跑assert與保存統計，不冒稱離線可逐項重算。新增DB返回ID竄改Red，補root verify重算32×805cosine及640返回ID／設定；分段58次有native scores，已逐段重算，maxerr1.1947672e-7。最終10測試Green，兩份audit通過，不重啟服務或補造分數。
- 最終獨立唯讀審查無未解除Critical／Important；重算選擇、全部支持主題與時間範圍吻合，舊兩輪132／69封存hashes未變。詳見review.md。封存本輪為「實驗完成、涵蓋採納未通過」，不是產品品質驗收。
