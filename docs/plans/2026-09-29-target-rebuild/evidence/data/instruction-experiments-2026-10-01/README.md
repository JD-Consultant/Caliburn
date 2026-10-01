# 指引實驗資料包（2026-10-01）——供專題報告引用

本目錄保存 2026-10-01 對顧問 A 指引所做的**對照實驗**的原始資料與整理後的指標，目的是讓專題報告可以直接引用數字、逐字稿與最終 JD，也讓別人能重新核對。結論、取捨、限制與是否採用，以任務證據為準：[T14 證據的 Q1／Q2／Q2b 各節](../../t14-job-analysis-quality.md)與 [T17 證據](../../t17-course-administrator-journey.md)；本頁只描述資料，不是第二份結論。

**全部是合成資料**：員工由模擬模型（Luna／low）依人設回答，沒有任何真實員工、repo 內容或 Demo 資料；不含金鑰與 provider 的不透明 reasoning。

## 實驗設計一覽

| 批次 | 指引版本 | 份數 | 說明 |
|---|---|---|---|
| `q1` | c0＝實驗前的主指引（程式基準 `d41e75f7`） | 課程行政 3、倉庫 3 | 基準線：依序執行，每份最多 12 個 A Turn |
| `q2` | c1（提交 `ec3c143a`） | 課程行政 3、倉庫 3 | 一次補入四處指南衍生文字：隱藏面向引導、任務粒度與成果／要求不重抄、知識技能／條件／協作對象寫入時機、職務目的早寫 |
| `q2b` | c1b（提交 `4b9da041`） | 課程行政 3、倉庫 3 | c1 的補跑：只收窄知識技能那一句。倉庫第 3 份的 harness 在第 11 輪因員工模型被限流而終止，**結果檔由產品保存的資料復原**（檔內 `"recovered": true`） |
| `q3` | c3（提交 `1e9edcea`） | 課程行政 3、倉庫 3 | 成分拆解：c1 去掉「寫入條件／協作對象／知識技能」那一條。**依預先登記的規則採用**（單批對照改善，不是普遍保證） |
| `long` | c3 | 1 | 採購人設的長訪談（含取消、後端硬停止、人工改稿、更正、PDF）；跨 2026-10-01–02 完成45輪，續跑與限制見下節及 T17 A2 |

其餘條件各批相同：A、B1、B2 為 `gpt-6-luna`／reasoning `high`（`store=false`、`all_turns`），員工模擬為 `gpt-6-luna`／`low`；隔離的 PostgreSQL 18.6（loopback `caliburn_t01_test` 的 `eval_b` schema）與本機後端 8103；同一時間只有一場訪談。人設在 `apps/api/tests/fixtures/job_analysis_quality/personas.json`，harness 是 `apps/api/scripts/simulate_interview.py`（付費、明確執行）；各批的預先登記判準、停止條件與費用上界寫在 T14 證據的對應小節（先於執行提交）。

## 檔案

| 路徑 | 內容 |
|---|---|
| `runs/*.json` | 每份訪談的原始輸出（harness 直接寫出，**位元組不變**）：公開逐字稿 `turns`、事件 `events`、最終 JD `jd`、引用與來源原文 `references`／`source_contents`、自動檢查 `checks`。雜湊在 `runs/SHA256SUMS.txt`（`sha256sum -c`） |
| `transcripts/*.md` | 由上面的 JSON 產生的**可讀版**：逐輪員工／顧問對話、最終 JD、自動檢查（寫報告時可直接摘錄） |
| `metrics.csv` | 每份一列的指標（欄位見下）；`version`／`instruction`／`instruction_commit` 標明指引版本 |
| `summary.txt` | 各批平均與 `compare_versions.py` 依登記規則算出的判定輸出 |
| `tools/` | 產生這些數字的本機工具的**參考副本**（含絕對路徑，環境特定；用來看定義與算法，不是產品程式） |

長旅程的正式 PDF 匯出、逐輪 progress 與事件 JSONL 亦放在 `runs/`，雜湊同列 `runs/SHA256SUMS.txt`。以下長旅程原件是後續補入，**尚未加入本資料包既有的 `metrics.csv`、`summary.txt` 或 `transcripts/*.md`**；不要將這些短程對照統計當成已涵蓋長旅程。

## 採購長旅程原件

2026-10-02 將 `.research-tmp/eval/long-procurement-1*` 的下列四份原件原樣複製入庫；複製前後逐一核對 SHA-256，未修改數據或重新生成 PDF。這可避免只靠可清理的暫存目錄保存；目前為本地 Git 保存，不是已推送或已有異地備份。結論、事故發現／查證、修正、測試及未完成項目仍只維護在 [T17 A2 實測結果](../../t17-course-administrator-journey.md#a2-實測結果2026-10-02原旅程完成-45-輪)。

| 原件 | 用途與判讀限制 |
|---|---|
| [最終 JSON](runs/long-procurement-1.json) | 45輪公開訪談、最終 JD、來源與粗查結果。`started` 是續跑啟動時間，不是原旅程開始時間；完整時間線見 T17 |
| [逐輪 progress](runs/long-procurement-1.progress.jsonl) | 保留前24輪並追加後續結果；早期列不具備後來新增的 execution ID，末輪沒有獨立耗時，不補造 |
| [事件 JSONL](runs/long-procurement-1.events.jsonl) | 人工改稿、取消、事故續跑、硬停止、重送及 PDF 匯出；前兩個事件標記 `reconstructed`，依既有保存結果重建，並非原時刻日誌 |
| [正式 PDF](runs/long-procurement-1.pdf) | 產品匯出的4頁可見成品；包含刻意人工修改的測試內容，不當成純 AI 自主成果。文字抽取限制見 T17 |

此例仍是 **Luna 合成人設的單次旅程，不是真人顧問效果或普遍成功率**。前段沿 `c1066873` 實驗基準，續跑修正為 `40f7c1f9`（只改 harness／測試／證據），結果紀錄為 `aa5c82fb`。逐字稿可用最終 JSON 的 `turns` 核對；未保存供入庫的原生模型接續 items 或整份資料庫，所以這四檔不能單獨證明每個模型請求的完整 Context。其餘資料庫查核以 T17 記錄的範圍與限制為準，不將缺少的原件說成可完整離線重播。

## `metrics.csv` 欄位與指標定義

| 欄位 | 定義 |
|---|---|
| `turns`／`turns_completed`／`minutes` | A Turn 數、完成數、逐輪耗時加總（分鐘；含 429 重試等待） |
| `areas`／`tasks`／`max_task_chars`／`outcomes`／`requirements` | 最終 JD 的職責數、任務數、最長任務敘述字數、成果數、要求數 |
| `capabilities`／`capabilities_restating_task` | 知識技能數；其中「名稱二元組至少 60% 落在某任務自己的標題＋敘述內」者（近似任務改寫） |
| `collaborators`／`conditions` | 協作對象數、全職務條件數 |
| `near_copy_details`／`details_total` | 成果／要求中「字元二元組至少 70% 落在所屬任務標題＋敘述內」者／全部成果與要求 |
| `purpose_written` | 職務目的欄位是否有內容 |
| `hidden_aspects_asked` | 人設的「被問到才說」事實中，`limits`／`quality_roster`／`risk_peak`／`tools`／`physical`／`license` 於員工發話出現者（代表顧問問到該面向） |
| `elicitation_gaps`／`recording_gaps` | 人設事實從未被說出（沒被問）／說了但最終 JD 沒有 |
| `questions_per_turn`／`chars_per_turn`／`leading_phrases` | 顧問每輪問句數、每輪字數、引導式問法片語數 |
| `citations_checked`／`citations_unsupported` | 引用審計：JD 項目所述的人設事實，其引用來源的原文是否含該事實（粗略標記檢查）；未支持＝該項目引用的來源都不含該事實 |
| `correction_effective` | 更正是否生效（新值在、舊值不當成現行、其他工作保留） |
| `counted_input_tokens_a`／`counted_input_tokens_memory`／`counted_input_tokens_per_minute` | 由已保存 checkpoint 讀出、對每個請求計數的輸入 token 加總（A／背景 Memory），以及除以 `minutes` 的每分鐘量；它貼近帳戶的 TPM 上限，是耗時的主因 |
| `a_model_calls`／`a_max_calls_in_a_turn`／`memory_batches`／`memory_model_calls`／`compactions` | 從資料庫統計的模型呼叫數（A 全部／單輪最大）、背景 Memory 批次數與其呼叫數、壓縮次數 |
| `attempts`／`failed_attempts` | 對 provider 的送出嘗試總數／失敗的嘗試（絕大多數是 429 `rate_limit_exceeded` 被重試吸收；帳戶 TPM 為 200K） |
| `cost_usd` | 依產品固定的 Luna 費率與回報的 usage 估算（**估算，不是帳單**） |
| `max_a_request_tokens`／`max_memory_request_tokens` | 由已保存 checkpoint 讀出的 provider 計數最大請求（input tokens） |

## 判讀注意

- 樣本很小（每批 6 份，每份 12 輪）、員工是模型、檢查是粗略標記：這組資料適合比較指引版本在**大效果**上的差異，不能當普遍品質保證，也不能當真人試點（V25）的替代。
- 每份耗時主要受帳戶 TPM 200K 的限流影響（大量 429 被重試吸收），不只是模型延遲：每份約處理 1.6M–5.4M 輸入 token、每分鐘 20–29 萬；單份耗時、`failed_attempts` 與 `counted_input_tokens_*` 要一起看。
- 引用審計只問「項目所述的人設事實，其引用來源是否含該事實」。**引用指向顧問的訊息是設計允許的上下文（Owner 2026-10-01 確認），不算誤引**；看的是說出該事實的員工原話有沒有被引到。審計是標記檢查，會有誤判（例如事實的措辭不含標記字），被標記的項目要逐筆讀原文（見 T14 證據的人工判讀）。
- harness 的已知缺陷：員工模擬偶爾把控制旗標 `{"nothing_more":false}` 附在回答後面（Q1 為 2／48 則、Q2 一份 3／12 則），已在後續 harness 修正；Q1／Q2／Q2b 沿用同一版 harness 以保持對照一致。
- `source_contents` 內是模擬訪談原文（合成）；JD 的引用只審計人設事實，其他語句的來源品質需人工讀。

## 重新核對

```powershell
# 在 runs/ 目錄
sha256sum -c SHA256SUMS.txt
```

重新產生衍生檔（需本機評測資料庫與忽略目錄中的原始結果，未必能在別的機器重現）：`tools/export_experiment_pack.py`。
