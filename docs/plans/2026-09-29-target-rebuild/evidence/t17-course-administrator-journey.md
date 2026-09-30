# 課程行政訪談到 JD 的真模型旅程

2026-09-30；T16／T17 的有界垂直驗證，起始 commit `936ca485`。本輪先驗現有產品，不改 prompt、不重造評測服務；不因一例通過宣告全部 gate 完成。沿[任務表](../tasks.md)、[品質 rubric](../../../../apps/api/tests/fixtures/job_analysis_quality/rubric.md)及原工作分析／JD 指南。

## 外送前固定的範圍

- 全合成課程行政專員，最多 8 次員工輸入；只透過正式 HTTP 輸入，不人工代寫 JD、灌理想 Memory 或告訴模型指定工具順序。依實際追問回應，完整輸入與產物另留測試資料區供審讀。
- 已知背景為成人進修課程行政，非授課／課程核准角色。分段提供報名核對、課前資料、異動通知、課後紀錄，以及較低頻的停課通知；後段更正一個明確周期，不更改其他責任。未知退款核准範圍不補猜。
- 模型 `gpt-6-luna`，reasoning `medium`，保持目前 16,384 output 上限、原生串流及 `store=false`；保留 App 的既有 context／工具／角色組裝。沒有 provider 替代或 SDK 外重試。
- 每個 A Turn／Memory 批次最多 32 model steps、96 outbound attempts、同請求 2 attempts、2 compactions、600 秒、US$0.50；B1／B2 沿同批既有預算。最多 8 A＋8 B 批次的保守工作預算上界 US$8，不等於實際帳單。持續失敗、輸入拒絕或達上限即停止新輸入，核對原因，不無限重跑。
- 獨立 loopback `_test` DB 的新 `t17_course_20260930a` schema、8102 後端；不操作 Demo 8100／5173 或其資料。保留本次 schema 供後續唯讀核對，不自動清理。
- 既有 PostgreSQL saver／budget／operations 保存足夠的原生接續；一般證據只輸出合成公開內容、正式產物、安全狀態、用量與指紋，不匯出金鑰或 opaque reasoning。

## 先定判準

確認實際保存的 JD，而不是顧問口頭說已改：主要工作逐步成形、責任不升格、低頻工作不被日常覆蓋、更正只改正確範圍、未知不成確定。Memory 若自然觸發，核對 B1→B2 正式發布與來源範圍；未觸發就記未觀察，不由測試擅自發布。另讀取完成 Turn 差異及來源，最後匯出正式 PDF。

方法參考 [OpenAI Evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices)：評任務實際結果與工具使用，不能以 API 接受或模型自評代替內容品質。這是本案小樣本工程驗證，不是人類領域專家校準，也不估計普遍成功率。

## 執行結果

有界觀察已結束：7 個成功 A Turn、4 批背景 Memory、正式保存與 PDF 均實際執行；另保留 1 個生成前連線失敗的 A Turn。已發現錯誤來源引用，**本 trial 品質不通過**，不能勾 T16／T17。全程未修改 prompt、人工補 JD／Memory 或換模型。

### 隔離環境與已確認的失敗收尾

職務檔案 `6bd4640f-a032-41d0-9cd9-85bfdd461e17`。第一次 A execution `8c8ae2c8-ae24-470f-99f3-feb59a1b3a18` 在 token count 連線失敗：sandbox 內不帶金鑰的 `/v1/models` GET 也在 HTTP proxy 處得到 WinError 10061；獲准在 sandbox 外同一檢查得到預期的 401，證實可連線而未附認證。沒有把這次環境故障當作模型品質問題，也沒有更改產品代理或繞過安全設定。

該 execution 已收尾 `failed`，current Turn 為 null，正式訪談仍只有開場序號 1；沒有可用候選或新增的正式 JD 改動，也沒有模型生成呼叫。token count 留下兩筆未取得遠端結果的嘗試。只停止自有 8102 測試後端，獲准重啟後，透過新 command 將同一員工原文當新輸入提交；不是修改失敗 Turn 或重用其正式序號。Demo 8100／5173 未啟停。

### 第一個核心缺陷：跨輪已知事實引用了錯誤的當次輸入

第二個成功 A Turn `f91eb6b2-a918-44ab-b638-b9812babd049` 建立了正確的職稱、單位、主管文字，但三個 profile 欄位均引用正式訪談序號 **4**。實際身分背景在序號 **2**；序號 4 只談報名、付款核對及出席彙整，沒有提供完整職稱、單位與匯報關係。`needs_recheck=false` 不是語意正確的證據。

從既有官方 saver 唯讀抽取公開 function call（不輸出 reasoning）可見 `revise_jd_profile` 的三筆 `add_source` 都由模型選了 `{"kind":"current_input"}`。HTTP 來源全文也正確回到序號 4：目前證據指向**模型選錯來源**，不是 DB 把序號 2 誤解析成 4。現有 prompt 已有「每一項主張只附真正支持它的來源」，因此不能只用再加一句相同提醒宣稱根治。

後續先評估當次輸入／歷史來源在 context 和工具契約中的辨識，再用「前輪背景、後輪工作細節」正反案例重跑；不另造 LLM validator、不讓 App 猜員工事實，也不把有合法來源 ID 當作支持內容。尚未修改 prompt 或宣稱已修正。

該 Turn 原生 request 的 SHA-256（以 `json.dumps(value, ensure_ascii=False, sort_keys=True)` UTF-8 計）：instructions `2d7cbca2d79b751717f07601be7acc49f05f08537fd690488ade4509b7fa4769`；tools `0970ca616d2a19ff4a9690775ff89afdea1652e2207eafc8739fa4a4c40b1027`。

### 實際產物與逐項觀察

最終正式 JD revision：`a177e0ed-75b5-4153-aa6f-99554449786a`。包含職稱／單位／主管／目的、3 職責、5 任務、成果與執行要求、1 知識、1 技能及 3 個任務能力關係。協作／條件集合未另外建立，不能把欄位有無填滿當作完成依據。

| 檢查 | 實際觀察 | 判斷 |
| --- | --- | --- |
| 訪談到實際 JD | 員工只回答與補充；原生工具建立並保存上述內容，不只是回答聲稱已寫 | 本例流程成立 |
| 周期更正 | 第 5 個成功 Turn 將職責 scope、任務名、正文與成果的「每月」改為「每季」 | 本例正確 |
| 其他工作保留 | 每日報名核對、逐堂出席、課前兩工作天交接、颱風通知均仍存在 | 本例正確 |
| 責任／未知 | 財務查帳後才更新；不自行核准退款、改期／停課、設備維修；不清楚的退款核准條件仍在 Memory 表為未知 | 本例未發現升格 |
| 跨層 Memory | 4 次正式發布；最終 4 情境／1 理解保留背景、例外、周期更正及後補計算方式 | 本例有效，仍有跨層正文重複可改善 |
| 固定引用與歷史 | 最早快照的 2 情境＋1 理解重新讀取，內容、修訂及來源與更新前完全一致；最新理解的 4 筆情境修訂均吻合本快照 | 確定性核對成立 |
| 正式訪談資格 | 開場及 7 問答形成序號 1–15，失敗輸入來源不在其中 | 本例成立 |
| 中間說明與完成變更 | 完成 Turn API 可讀回 commentary；7 輪的固定 JD 差異 API 全部成功讀取，更正 diff 僅影響相應範圍 | HTTP 層成立，未做本輪瀏覽器走查 |
| JD 引用 | 35 筆來源全文全部可讀，但職稱／單位／主管的 3 筆來源錯配保留至最後 | **fail，不以其餘成功抵銷** |
| 訪談交付 | 最後確認職務目的後保存，稱目前為草稿、未宣稱滿分 | 未見過度宣告；不是專業人審認證 |

最終 Memory snapshot `574def10-495f-414e-95ef-a68a68dda13a`，涵蓋至有效員工訪談序號 **12**，不是最後的 14；第 7 輪只確認職務目的，未另行要求整理。這是按需整理的觀察，不把 Memory 說成全部最新。最新理解保存「以前每月、目前每季」，又從後一批吸收「逐堂加總，同一人三堂算三人次」；不再保留已解決的計算來源未知。

本例 JD 的 35 筆來源皆為訪談，**沒有驗到 JD 直接引用 Memory 後的換版 diff／確認**。不要以「Memory 發布成功」代替那一條驗收。

### PDF：可讀產物與抽取限制

由正式 HTTP `GET /api/job-files/{id}/jd/export.pdf` 取得 719,047 bytes、A4 3 頁、tagged PDF，無受訪者姓名欄位。bundled Poppler 將全部 3 頁渲染 PNG 並逐頁目視：中文可讀、內容無重疊／截斷、頁碼正常；第 3 頁僅 K/S 定義，留白較多，未為排版美化擴大本輪。

逐欄抽取比對 **41 個非空 JD 文字欄位**：最初 NFKC 比對有 8 筆不匹配，原因均為 PDF 文字抽取把「長」U+9577 表為「⻑」U+2ED1（NFKC 不轉換）；目視沒有字缺。僅在 QA 明示套用此單一等價映射後，41 欄皆可找到。**因此證明本例可見內容存在，不宣稱 PDF 複製／搜尋逐字無損。**該文字層相容性留作後續小修，不偷偷改正式 JD 或放寬來源品質判準。

### 用量與執行邊界

- SDK／框架實際安裝：OpenAI 3.20.0、LangGraph 1.2.12、PostgreSQL checkpointer 3.1.2、psycopg 3.3.6、Playwright 1.63.0。
- 成功 A 的模型呼叫依輪為 **1、6、5、4、6、6、3**；4 個 Memory 批次為 **8、11、8、10**；總計 **68** 次模型呼叫。token count 共 **82** 次，其中 2 次為前述環境連線失敗；無 compaction。不是 7 輪就只有 7 次請求。
- `execution_outbound_attempts.reported_cost_usd` 的模型合計 **US$0.039375710**，是 App 依用量記錄的估算，不是 OpenAI 帳單核對；token count 沒有 reported cost。不能把每次 request 的預留上限相加（16.509584）當實際花費或本批同時保留金額。
- 最終 12 個 execution：7 A completed、4 Memory completed、1 A failed，**沒有 active execution**。限額內停止新輸入；沒有擴量或只挑成功嘗試。模型等待沒有永久卡住，但這不代表已測完所有硬崩潰時機。

### 本機證據與接續

結束時再查 DB 確認零 active execution，已停止本輪自有的 8102 後端；隔離 schema 保留供唯讀核對，未清理。以下合成產物位於 ignored `.research-tmp`，不提交為產品資料或第二份規格：

- `t17-course-before-correction.json`：第 3 輪後的正式內容、最初已發布快照及來源全文。
- `t17-course-before-frequency-update.json`：周期更正前的正式內容。
- `t17-course-final.json`：公開訪談、完整正式 JD、來源全文、完成 Turn 變更、最新 Memory 及執行摘要；SHA-256 `c6e2ac59128f7567399e2fc170b5d588b81c10478b95688dfc2b15877337be05`。
- `t17-course-jd.pdf`：SHA-256 `e184bf0c79a7e15cdab70329a1cdf9286bea42529f81734db1b893be0682dcce`；對應 `t17-course-jd-{1,2,3}.png` 已目視。
- `t17_course_read.py`／`t17_course_trace.py`／`t17_course_verify.py` 是本輪唯讀取證 scratch，不是新增產品 API／評測框架。最後一支實測通過歷史不變、15 則序號、失敗輸入隔離、同快照引用一致及 35 筆來源可讀；第一版 scratch serializer 少處理巢狀 dataclass 曾失敗，修正後重跑，非產品 Red–Green 證據。

下一切片優先解決跨輪來源選擇反例，先比較 context／工具描述的最小改善與現有成熟建議，再用相同情境及相反方向案例有界驗證。不得重寫本次失敗產物冒充原 trial 通過。恢復系統維持核心收尾，不追加少見故障矩陣或新恢復平台。T16 容量／compact、T17 JD Memory 引用換版＋人工修改及完整瀏覽器旅程、T18 乾淨交付與切換仍未因此完成。

唯讀側線審查 `01a0f260-8367-7771-aefc-f07a979f8c61` 的下一步候選：`revise-jd-profile-arguments.schema.json` 已用互斥 kind 正確分開 current_input／interview，但來源分支沒有局部 description；先單獨補清「本輪才寫入的舊事實仍應引用歷史來源」，經 SSOT 生成並有限對照，而非再次加入籠統的正確引用指令。次選才比較 context 邊界，不同時改兩處導致無法歸因。這是**可驗假說，尚未採納為已修正方案**。依據是 OpenAI 的[工具參數說明建議](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)及[context 邊界建議](https://developers.openai.com/api/docs/guides/prompt-engineering#message-formatting-with-markdown-and-xml)，不是官方保證能消除此例。

驗收至少對照：① 前輪提供三個身分欄位、本輪只補工作，三欄須回指前輪；② 本輪只更正主管，職稱／單位維持前輪來源、主管使用本輪。實際產物、工具選擇、回讀原文三者比對；空白不寫、schema 接受與模型自評都不算來源品質通過。這位工程代理的覆核不是 rubric 所要求的人類領域專家校準。

## 跨輪來源選擇對照的外送範圍

2026-09-30 接續，基底 `9ea7ffb8`。先作有界選擇 probe，不改寫上方 trial 或正式資料。假說是 current_input／interview 的參數說明不足以區分「本輪寫入」與「本輪提供事實」；先只比較來源分支 description，不同時改 Context 或主指引。候選若無改善，不升格為修復。

- 原案例的已保存合成歷史作唯讀基底；另設本次只更正主管的變體。兩組各 baseline／candidate、各 2 次，共 8 trials，每 trial 最多 3 次生成；最多 24 次生成及 24 次 count、零自動重試／compact、每次 120 秒、16,384 output tokens。模型仍為 `gpt-6-luna`／medium，direct Responses、store=false、all_turns。候選只改模型看到的來源說明，無版本／ID 參數變動。
- 沿已保存的原生項目保留 phase／reasoning；變體只在尚未呼叫本次模型的輸入位置替換合成原文，不重用原本對另一輸入產生的本輪 reasoning。讀取 JD 工具以原案例空 JD 的真實保存回傳作固定 observation；不执行修改、不偽造寫入成功。這是**來源選擇評測，不是完整產品旅程或正式保存驗收**。
- 只輸出公開 tool call、使用量、指紋與判斷；opaque reasoning 不輸出。每 trial 首次 profile 修改後停止；未修改記未觀察，不算成功。以逐欄來源和實際文字評，不以是否出現某句 prompt 評。
- 使用隔離測試原件，不動 Demo。依既有模型費率，以 24 次均未命中快取的輸入與最大輸出先核上界，總預算 US$2；超過即不外送。僅在有改善時另行記錄必要的正式保存驗證範圍，不將這份 manifest 當無限測試授權。

### 第一個候選未採用；第二個有界假說

baseline／來源分支 description 候選各 4 trials、各 7 次生成及 7 次 count。原工具組 SHA-256 如上；候選為 `c13cb503af9907b8f14a197be97290ad4e9bb4bad4462bbc0ad5b9cd23f5fc8f`。候選沒有消除錯誤：歷史背景 trial 2 仍把三欄全部選成 current_input；trial 1 三欄回指 2 正確，卻在另外的目的／職責引用尚無正式資格的序號 4，正式工具會拒絕。主管更正 trial 2 選對兩個歷史欄位與當次主管，trial 1 因選擇 probe 未接其他工具而未觀察 profile。

baseline 的歷史 trial 1 未觀察、trial 2 只寫職稱及主管且引用 2 正確；兩個主管更正 trial 的首次 profile 修改有正確文字但未附來源。後兩者是本 probe 的未完成證據，不推定後續 Turn 必然不補來源。所有公開原呼叫保留於 ignored `t17-source-{baseline,candidate}.json`，不只保留每欄最後一筆來源。**不採用 description 候選、不修改原失敗資料、不宣告修復。**

第二個假說：主指引只以「當次／正式」列來源種類，沒有把逐項事實定位與一次多欄修改的選擇順序講清楚。沿 OpenAI [清楚組織指令](https://developers.openai.com/api/docs/guides/prompt-engineering#message-formatting-with-markdown-and-xml)及 [GPT-6 prompting guidance](https://developers.openai.com/api/docs/guides/latest-model#prompting-best-practices)，僅**替換**既有來源段落為「先定位支持各項內容的原話 → 按出處選來源；寫入時點不改變出處」，不堆加 reviewer／validator，不改 schema、context、模型或 effort。官方沒有保證此改動可解決語意錯引，須實測。

外送上界另限同兩情境各 2 trials，共 4 trials、最多 12 次生成及 12 次 count、US$1；其餘 timeout、output、零重試、停止與資料保護沿前一 manifest。只改尚未開始的測試請求 instructions，不覆寫保存歷史；同樣在首次 profile 工具選擇停止。若仍有錯誤，不繼續無限微調；須重新評估 context／模型能力與產品取捨。

第二個候選實際 4 trials／7 次生成及 7 次 count：三次觀察到 profile 修改，逐欄來源皆正確（歷史背景一次、只更正主管兩次）；另一次因同回應含背景整理請求，本選擇 probe 沒接續，標為未觀察。沒有把 3/3 外推成普遍成功率。instructions SHA-256（原文字串 UTF-8）為 `cc24662697dc920a9553267430ab15655a214765f23ce4232d0d46b66fafe90a`；原工具組未改。公開結果在 `t17-source-source_guidance.json`。

### 真後端保存確認的範圍

採相同最小指引變更作兩個全新職務檔案的正式 HTTP 檢查，各最多兩輪員工輸入；歷史背景與本輪只更正主管各一例。先送原合成背景，再送工作細節（或追加主管更正），不人工代寫 JD、補來源或操控模型工具序列。新 `t17_sources_20260930a` schema，既有 loopback `_test` DB、獨立 8102 程序；不動 Demo 或原 course schema。模型／串流／output 不變，每 execution 最多 24 steps、64 outbound attempts、同請求 1 attempt、1 compaction、480 秒及 US$0.25；至多 4 A＋4 背景批次，整體預留上界 US$2。失敗停止，無額外付費重跑。沿既有正式 owner／supervisor，不自造恢復接線。

讀回正式 JD 每欄來源全文與訪談，核對選擇確實保存；第一輪若已寫 profile，第二輪驗其保留／更正，不冒稱必然重現「延後寫入」路徑，後者仍由上述固定前置 probe 提供證據。不勾完整 T17，不改寫原失敗結果。

### 真後端保存確認結果與保留缺口

兩個新檔案各兩輪、共 4 A Turn 均完成並可回讀正式 JD。本輪只採用較清楚的既有來源指引，**不是宣告錯引已根治**；沒有新增 validator、reviewer、來源猜測、schema 或保存系統。

| 情境 | 保存後實際結果 | 判斷 |
| --- | --- | --- |
| 歷史職務背景＋本輪工作細節 | 檔案 `8ce3ce9e-5125-4188-aad2-9db0af925ebd` 第一輪就寫入 profile；第二輪後三個身分欄位及目的仍無來源。工作部分 2 職責／2 任務／5 細節，共 9 筆来源均指向本輪序號 4 | 流程成立，但 profile 引用缺漏，**品質不通過**；不是延後寫入 probe 的完整重演 |
| 本輪只更正主管 | 檔案 `28f798ee-52ce-41d4-b404-668a355860a7` 的職稱／單位維持序號 2，主管「教務主任」正確指向序號 4；正式回讀原文相符 | 指定三欄來源驗證通過，不能外推所有欄位或所有職務 |
| 更正作用範圍 | 同一原文仍說每月彙整出席給「組長」，只另更正直接匯報對象；實際任務／成果把月報收件人也改為教務主任 | 尚未取得「收件人也變更」的確認，有過度泛化風險；不能以主管欄正確抵銷 |

最後 JD revisions 分別為 `8ac4f9c6-7d84-42d3-8377-b015a7c880cf`、`1f2fcca2-2a1a-4a92-aad9-e2f2e076f3f7`。第二例工作部分 1 職責／2 任務／4 細節，連 profile 共 12 筆來源。兩例原始公開輸入、答覆、正式 JD 及來源全文保留於 ignored `t17-source-journey.json`，SHA-256 `17154cd278787c2a1ac5604e2e36bcfcccbf53fd890bd9a782077d956df48b1e`；不手動補正測試產物。

背景 Memory 自然觸發兩批：`c442efe9-35ff-480c-afea-393f937b1fdb` 發布 snapshot `e32fecf2-644f-49a5-b10d-948da6452cd0`，涵蓋至有效序號 4；`ead82a17-95f5-43db-97fb-ce5ea53ba905` 在理解階段以 `BudgetExceededError` 收尾，候選 `discarded`、execution `failed`，第二檔案沒有被誤標成已發布 Memory。既有安全回執僅保存錯誤類別，未保存哪一項 budget limit，**不能猜成 API 額度不足、24-step 耗盡或逾時**；本輪不擴充診斷平台或付費重跑。

最後唯讀核對：4 A completed、1 Memory completed、1 Memory failed，**零 active**。背景失敗沒有撤銷已保存 A／JD；沒有繼續送新輸入，故本輪不另宣稱已真測「失敗後下一輪訪談」。本輪 44 次模型生成、49 次 token count，無 compaction、provider 嘗試的 failure_code 均為 null；模型估算用量成本 US$0.013316090，不是帳單。失敗批次實際生成 14 次、count 17 次，不能把失敗簡化成模型呼叫數達 24。已核對並停止自有 8102 程序（PID 33576），保留隔離資料；Demo 8100／5173 未動。本輪未重驗 PDF 或瀏覽器。

版本化品質素材升 v3：新增 `historical_fact_keeps_historical_source` 與 `current_correction_keeps_other_sources`，只把失敗模式縮成可重跑全合成案例，oracle 仍僅供審讀。實驗先固定觀察再改指引，屬非確定性品質 eval，**不是宣稱單元測試 TDD Red–Green 已證明 prompt 語意**。來源 fixture integrity 與既有角色／工具契約離線檢查另列，不取代上述品質結果。

提交前在 `apps/api` 執行 `python -B -m pytest tests/unit/test_role_prompt_contracts.py tests/unit/test_consultant_tools.py tests/unit/test_job_analysis_quality_fixtures.py -q -p no:cacheprovider`：**56 passed**；兩個變動 Python 檔的 Ruff check／format check 通過，`git diff --check` 無空白錯誤。只驗此切片，不冒稱完整測試套件或十三例自然品質通過。

接續優先：依同一 rubric 解決漏附來源及局部更正泛化，先檢查既有工具／context／方法指引責任，不連續堆提醒、不替模型自動配來源。Memory 預算限制是否影響正常旅程留待有界核對，不為它增建全面恢復系統。先前 T16／T17／T18 未完項保持未完。
