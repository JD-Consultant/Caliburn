# Compaction 與長訪談：四種資料管理方式比較

狀態：**`main-03` 已停止，第一組保存 60／61 段、四批 Memory；e061 碰到累計 16 次 compaction 上限，其餘三組未開始，尚無四組比較結論。** 累計估算占用 US$1.000591120，新階段約 57 分鐘；費用與四小時未用完。本資料包不改正式產品，不覆寫原件。[本次停止核對](main-03/stopped-observation.md)已定位 App 參考訊息累積及壓縮後反覆展開 JD 的截面；[局部正式答覆判讀](main-03/partial-probe-review.md)分開呈現已完成回提的 30／32 個完整符合單位及兩項部分遺漏，不當成 Memory 因果效果。原界線與方法見 [續跑計畫](continuation-plan.md)、[付費前檢查](continuation-review.md)；前次 51 段的 [停止觀察](main-02/stopped-observation.md)仍保留。

## 本次要比較什麼

相同 Luna/high 與原生 Compaction 下，比較三層 Memory、自然更新的單層摘要、完整原話按需回查、只有近期原話。各組保留自己的完整原生接續；原話按需組不是每次預載全部歷史，也不強迫從頭掃描。

完整方法見 [比較設計](protocol-draft.md)。本輪準備的資料只解決「訪談內容、判準及已知請求材料是否明確」，尚未證明哪組能找回早期事實、降低總用量或產出較佳 JD。

## 合成職位與資料

案例為庫存與物流行政專員，從空白 JD 開始。包含收貨及異常追蹤、退貨狀態、盤點、缺貨、調撥、報表、單據與計量單位、召回、稽核、交接，以及設備備品等工作；另說明成果用途、本人／協作者責任、知識技能與工作條件。

- [員工來源](employee-scenario.json)：61 段固定員工輸入，共 4,589 字元；其中 e001–e052 為主要工作、補充與更正，e053–e061 為回提、查核、模糊指涉及澄清。這些是合成員工資訊，不是已執行的 61 輪或既有模型答覆。
- [獨立判準](grading-cases.json)：14 案、51 個事實單位、12 個 JD 工作涵蓋領域。32 個單位對應明確回提／更正後的答覆；另 19 個查核正式 JD／答覆實際採用的主張，未採用就不計入精確事實率分母。工作遺漏另以涵蓋判準檢查，不把 51 列項當成同等回憶題總分。正文、引用與 JD 改動分開判讀，允許等價表達、合理合併與不同查閱順序。
- 研究事件 eNNN 只用於重現資料時間線。當次輸入原文不加工；正式序號由實際成功完成的訪談分配，另建立事件對照，不能先給本次輸入發明序號。
- 標準答案、預期來源與評分欄位不進入 Context 或讀取工具。情境／摘要須從實際完成的訪談自然產生，不手工補上判準。
- 一則真正省略主語的回答另作條件式案例：須有實際、可唯一辨認的前問；沒有前問就記未施測，不插入研究者假造的顧問訊息。固定主案例已包含明確回題及近期／早期回提。「之前那張表」也按實際前文檢查模糊資格，不能因原文相同就假定每組的指涉都相同。

## 容量預檢結果

使用現行顧問指引、產品工具 schema、`ResponseRequest.count_payload()` 與 OpenAI `input_tokens.count`，不是按字數估算。保留 16,384 output tokens；推理包含在輸出預留內。

| 預檢請求 | 實測 input tokens | 能說明什麼 |
|---|---:|---|
| Compaction＋三層 Memory 起始模板 | 8,326 | 空白 JD／空 Memory，開場與第一則員工原文 |
| Compaction＋單層摘要起始模板 | 7,862 | 尚無摘要，無分層 Memory 讀取工具 |
| Compaction＋原話按需回查起始模板 | 7,851 | 有原話讀取能力，無 Memory 整理產物 |
| Compaction＋只有近期起始模板 | 7,530 | 不開放更早原話查閱，仍保留共用 JD 工具 |
| 全部員工原文預載的容量反事實 | 11,919 | 只計量全部員工原文、指引與工具；不是主比較組 |

以上都未達 128,000 的輪前門檻、160,000 的完整 Step 門檻，也未超出 Luna 的硬輸入容量。**不能據此宣稱完整訪談已經放不下，或已驗證壓縮。** 開場、工具輸出、顧問完整答覆、原生 reasoning items、JD 讀寫及各組整理產物尚未生成，不能把它們的未知大小補算成實測值。

四個起始模板只供量測，並非從資料庫捕捉的正式執行請求。三層模板使用空導覽；單層以一份摘要作參考資料；比較用的整理批次固定，因此四組模板皆不提供 `request_memory_consolidation`。其餘 JD 讀寫、差異及壓縮請求的定義取自現行工具，不重寫縮水版來降低計數。這是受控研究條件，不修改產品的通知政策。

### 原件與失敗紀錄

- [offline-01](offline-01/result.json)：只準備請求，外送零次。
- [preflight-01](preflight-01/result.json)：第一個計數遇 `APIConnectionError`，立即停止；未知容量保留為 `null`。不是模型生成或容量拒絕。
- [preflight-02](preflight-02/result.json)：改在允許直連的執行環境，五個計數成功。生成零次、Compaction 零次；沒有為修正連線重跑模型。

每份原件包含實際待計數 payload、雜湊、來源及程式基準。全為合成資料，不包含金鑰、私人訪談或 opaque reasoning。計數後的研究審查補足評分來源、收回過強判準並區分觀察對象，沒有更動員工原文或已計量 payload；原件保留當時的評分檔案雜湊，不追改成現值。計數端點沒有生成 usage；本頁不推定服務免費或填造帳單金額。

## 下一階段與停止條件

有界的端到端先導旅程已接現行 Runtime、JD 工具及隔離 PostgreSQL：五輪訪談和一批 B1 → B2 → Memory 發布成功保存，A 發布後實際讀取情境、理解及 JD。23 次生成、27 次計數；最高單次輸入 22,072，未觸發 Compaction。方法、數值保留、真實 Context、引用與審查原件見 [先導結果](pilot-results.md)，界線見 [先導計畫](pilot-plan.md)。

本先導不是四組比較；早期原話仍在 A 的原生歷史內，JD 引用仍是原始訪談。下一步根據實際呼叫與用量凍結四組主執行的外送界線，再施測完整資料與合法壓縮，不用先導結果宣稱 Memory 帶來因果改善。

主比較的固定來源批次建議為 e012、e028、e044、e052 處理成功後；三層和摘要取得相同已完成來源，原話及近期組沿相同研究邊界供給近期語境。這些是執行初值，須在生成前凍結；不是模型自行宣稱已整理。自然互動補問的來源供給差異另列，不混入固定輸入的配對分數。

訪談廣度與壓縮壓力分開完成：

1. 主要職務與重要例外已具備可成稿資訊後，以工作 → JD 和 JD → 依據檢查涵蓋、責任、來源及冗餘，不要求把 51 個評分單位全部抄成 JD。
2. 每次模型請求計量真正的完整 payload，在合法交界採用完整 `compacted.output`；壓前、壓後及後續使用均保留證據。
3. 若自然旅程未達壓縮門檻，如實呈現未施測；不降低正式門檻或灌水宣稱成功。再以有意義的持續工作案例作獨立容量擴展，與主要職務成稿分開報告。
4. 若要證明全部歷史不能預載，須計量實際累積的完整材料；超過模型硬容量與超過主動壓縮門檻是兩件事。不發必定超量的生成請求。

主實驗的批次、外送、時間及估算用量界線已寫入 [主執行計畫](main-plan.md)。研究接線保留正式 Runtime／JD 工具，只在初始 Context 保存前調整可用資料；HTTP 記錄不重寫請求。[真 PostgreSQL 前置檢查](main-preflight.json) 已確認四組投影能保存並重入，20 項檢查通過、模型外送零次。這不恢復產品的金額攔截，也不表示主實驗或分析品質已通過。

`main-01` 完成八段後，因研究 hook 遺失速率快照而主動停止，第九段沒有取得正式訪談資格。原件與資料保留：[停止說明](main-01/external-stop.json)、[用量與接續分析](main-01/stopped-analysis.json)。29 個生成都取得回應，無 compact；不列為四組比較。接線與離線查閱計數問題已經反例重現並修正，見 [審查紀錄](review.md)。新 run 從空白資料重做四組，最多 US$1.90 本機估算占用，另留 US$0.10 給前次執行；不把前後版本或兩次用量混成同一次旅程。

修正後的 `main-02` 依順序開始四組比較，於 2026-10-04 14:42（臺灣時間）停止。第一組完成 51 段與三批 Memory，第 52 段整理整份 JD 時用完研究設定的 16 次模型回應，尚未得到最終答覆；其他三組未開始。固定基準見 [外送前 manifest](main-02/manifest.json)，原始請求與回應見 [trace](main-02/trace.jsonl.gz)及各組逐段 `exchange`／`product` 原件；[結果](main-02/result.json)、[例外堆疊](main-02/failure.json)及[離線分析](main-02/analysis.json)均已保存。[停止觀察紀錄](main-02/stopped-observation.md)區分研究的 16 步限制與正式程式的 64 步預設，不把此停止當成三層 Memory 品質失敗。凍結原件不追改，不自動重跑或擴大界線；人工事實、工作涵蓋與來源支持仍須另行判讀，不能以生成有回應或自動接續審核代替。

第一組已完成首批整理，發布六個情境與一個理解；e013 的 A 實際按需讀取這兩層，再編輯 JD。[首批觀察](main-02/first-batch-observation.md)分開記錄保留的數值、範圍偏移、Memory 閱讀與引用，以及來源格式限制。此時早期原話仍在原生歷史，尚無 compact，不據此宣稱長距離 Memory 因果改善。執行原件持續追加，觀察截面及原判準不追改。

## 重現準備與計數

在儲存庫根目錄執行；離線模式不讀金鑰、不連資料庫、不外送：

```powershell
uv run --project apps/api --locked python -X utf8 -B -m pytest docs/experiments/product-validation/data/compaction-long-interview-2026-10-04/test_preparation.py -q -p no:cacheprovider
uv run --project apps/api --locked python -X utf8 -B docs/experiments/product-validation/data/compaction-long-interview-2026-10-04/preparation.py --output docs/experiments/product-validation/data/compaction-long-interview-2026-10-04/offline-02
```

需要重新遠端計數時，選新的輸出目錄並加 `--count-only`。最多五個計數、單次 60 秒、整批 180 秒、無 SDK 重試，第一個失敗即停止。既有輸出目錄不能覆寫；不要為檢查文件或單元測試重跑遠端計數。

本輪行為測試先確認九個未實作反例，再通過；計數界線另經四個 Red–Green 測例。13 項離線測試、Ruff 及 strict mypy 通過，只證明準備腳本的資料隔離、工具權限、來源時間線及計數護欄，不代表主實驗或分析品質通過。研究審查的發現及修正見 [審查紀錄](review.md)。

## 參考方法

- [OpenAI Token counting](https://developers.openai.com/api/docs/guides/token-counting)：用完整輸入、指引及工具計數；純字數或本地文本 tokenizer 不等於實際請求。
- [OpenAI Compaction](https://developers.openai.com/api/docs/guides/compaction#standalone-compact-endpoint)：在可容納窗口內壓縮，完整承接 canonical output。
- [OpenAI Memory Evals](https://developers.openai.com/cookbook/examples/agents_sdk/context_personalization#memory-evals)：把捕捉、整理及後續使用分開評估，保存時間與來源關係。
- [工作分析指南](../../../../guides/2026-09-09-complete-work-analysis-guide.md)、[訪談校準](../../../../guides/2026-09-09-customized-jd-depth-and-interview-calibration.md)及[JD 欄位指南](../../../../guides/2026-09-09-jd-field-and-writing-guide.md)：涵蓋主要與重要低頻工作，保留實際責任與精簡高訊號成品。

準備工作與審查記錄見 [本輪計畫](preparation-plan.md)。
