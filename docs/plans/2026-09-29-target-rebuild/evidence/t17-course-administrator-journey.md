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

### 後續唯讀診斷：Memory 的 App 金額預留誤攔（2026-09-30）

核對原隔離 schema 的 `ead82a17-95f5-43db-97fb-ce5ea53ba905`，再對照當時 runner 算式：已記模型估算 0.005708160＋17 次 count 行政預留 0.001700000＝0.007408160；舊接線對下一次生成固定預留 0.242788000（把 922K 最大輸入當成實際輸入），合計 **0.250196160 > 0.25**。因此已具體定位 App 金額 gate 的反例；不是 API 帳戶額度不足，也不是 24-step 限制耗盡。這是後續 DB／程式核對，原失敗回執本身仍未記錄 budget subtype。

Owner 隨後採納「正常產品不設金額攔截，保留 token 容量、次數與時間限制；付費測試另定預算」。共用接線及確定性證據見 [T06 §19](t06-agent-execution.md#19-產品移除金額攔截與按請求計數預留2026-09-30)。明示付費測試保留上限並改用同一請求已保存的實際 count 預留；不為產品設巨大假上限。

沒有重跑或修改原 trial，原批次仍 failed、候選 discarded；沒有將來源品質 fail 改成 pass。這次全為離線模型／真測試 DB 驗證，不新增付費 manifest；profile 漏來源與局部更正泛化仍須另行驗證，不能因移除金額 gate 宣稱整條訪談旅程已驗收。

## 核心分析品質：模擬員工基準與有界改善（2026-09-30 恢復後）

Owner 在恢復後提醒**不要過度設計、以核心分析效果為主**。以下是本輪的取捨與界線；不新增產品功能，只用最小工具量測顧問的訪談與 JD 品質，並依證據做最小的指引改動。

### 為什麼先審讀，再決定改什麼

先以工作分析／JD 撰寫指南親自審讀上文課程行政旅程的完整逐字稿與 JD（不是看機制測試）。**做得好的**：追問順序自然（先全貌、再挑異動與課後紀錄、再問低頻工作）、界線與未知保留（退款核准不推定）、更正只改該項並保留其他工作、結尾用目的段落確認。**指南有要求、實際卻缺的**：

1. **已知且有影響的工作條件沒有記下。**員工第一句就說「服務平日晚上和週末的成人進修班」，[JD 指南 §2](../../../specs/2026-09-09-jd-field-and-writing-guide.md)的「工作關係與重要條件」要求已知且有影響的輪班／工作時間要寫；最終 JD 的協作對象與工作條件集合都是空的，全文找不到「晚上」或「週末」。原因可定位：`create_jd_item` 的工具說明寫明能建立協作對象與全職務條件，但 A 的主指引**從未說什麼時候該記**，七輪一次都沒用。
2. **「合格完成要求」與「最容易出錯的情境」幾乎沒問。**[分析指南 §2](../../../specs/2026-09-09-complete-work-analysis-guide.md)列出「哪些狀況會被退回？交付前一定確認什麼？」與「最容易出問題的是什麼情況？」；逐字稿裡 JD 的「要求」多是作業流程與權限界線，不是被退回的情況或交付前檢查。
3. **一句誘導式提問**：第 11 則把預期答案放進是非題（「通常是從逐堂出席紀錄加總而來嗎？…是『出席人次』而非不同學員人數嗎？」），員工只是附和；[rubric](../../../../apps/api/tests/fixtures/job_analysis_quality/rubric.md)把「誘導答案」列為 A 引導的失敗型。
4. 每輪回覆用一大段複述剛改了 JD 的什麼，JD 就在旁邊；[指引](../../../../apps/api/src/caliburn/agents/job_consultant/instructions.py)要的是「必要時簡述」。

我一度也想批評「同一段權限界線在多個任務重複」，讀回指南 §5 後**撤回**：它明說「必要的短句重述比為去重而造成誤導更合理」。這提醒審讀要對著指南，不憑口味。

### 量測方式（最小，不是評測平台）

- `apps/api/scripts/simulate_interview.py`：明確執行、付費、全合成、測試與啟動都不會呼叫。由人設驅動的**模擬員工**（同一個 `gpt-6-luna`，low）透過 HTTP 回答真後端的顧問，整條產品路徑（A、背景 Memory、PostgreSQL）都是真的，只有員工是模擬。員工只看私人筆記、只答顧問剛問的、標記「被問到才說」的事實只有問到相關面向才說；`nothing_more` 收尾。
- 人設在 `apps/api/tests/fixtures/job_analysis_quality/personas.json`：課程行政（沿本旅程）與倉庫管理員（非辦公室：輪班、搬運、冷藏、堆高機證照、月底盤點、供應商退貨更正）。每個事實有 `kind`（core／hidden／rare／unknown）與檢查用 `keys`（不給任何模型）。
- 自動檢查刻意粗略，只用來**比較指引版本**：把每個事實分成「員工說過嗎（surfaced）」與「JD 有嗎（in_jd）」，分出**引導缺口**（沒問到）與**記錄缺口**（問到了卻沒寫）；更正是否生效且其他工作保留；profile 三欄來源是否引用到真正含該事實的訪談；JD 形狀（各集合數量）；風格（每輪字數、每輪問題數、誘導用語）。**不取代**對逐字稿與 JD 的人工閱讀。

### 批次 manifest（執行前設定）

| 項目 | 界線 |
|---|---|
| 目的 | 比較「現行指引」與「依上述證據最小修改的指引」在兩個人設上的分析效果；先量基準，只有基準顯示問題才改，改後同樣人設重跑，並保留每次結果 |
| 模型／資料 | A、B1、B2 沿產品預設 `gpt-6-luna`／medium；員工模擬 `gpt-6-luna`／low；全合成人設，不含任何真實員工或 repo 資料 |
| 次數 | 每個指引版本 × 兩個人設 × 3 次；每次最多 12 個 A Turn；總計不超過 12 次完整訪談（約 150 個 A Turn） |
| 費用 | 參考本旅程實測（7 個 A Turn＋4 批背景合計估算約 US$0.04），單次完整訪談估 ≤ US$0.15，本批總上界 US$3；不是帳單保證，產品本身不設金額攔截（[T06 §19](t06-agent-execution.md#19-產品移除金額攔截與按請求計數預留2026-09-30)），上界由次數與人設決定 |
| 停止／重跑 | 任何 Turn failed／逾時（單 Turn 900 秒）即停止該次並診斷，不自動重跑；同一版本同一人設失敗兩次即停，先找原因；不因結果不好無界重試，也不挑最好一次呈現 |
| 環境 | 隔離 loopback `_test` DB 的新 schema `eval_a`、後端 8102（`scripts/run_backend.py --port 8102`）；不動 Demo 8100／5173；憑證只由既有 loader 從 `apps/api/.env` 取 `OPENAI_API_KEY`，不輸出、不記錄 |
| 紀錄 | 每次一個 JSON（公開逐字稿、完整 JD、來源全文、檢查結果）在忽略區 `.research-tmp/eval/`；不含 opaque reasoning 與金鑰 |

### 2026-10-01 接手：只處理影響成稿的兩個反例

Owner 要求以核心分析效果為主、避免過度設計。本輪不重跑六組完整訪談、不增建 reviewer／恢復平台；先讀六份 b0 產物及原工具軌跡。64 個 A Turn 都 completed，不等於品質皆通過：五份有任務草稿，一份只有 profile；另有一筆協作對象來源錯引。

- `b0-course_admin-2`：第二輪 `create_jd_item` 將本次輸入猜成尚未正式成立的序號 4，App 正確拒絕；但 `InterviewScopeError` 與執行資格错误共用「由 App 處理」提示，模型之後十輪未再建立任務。只分開錯誤回覆，維持 `scope_not_allowed` 與原範圍：本次事實用 `current_input`，歷史事實先讀原序號，不刪必要來源或改引無關訊息。
- `b0-course_admin-1`：協作對象「主任」的具體事實出自序號 14；收尾新增時模型選 `current_input`，實際映射為僅說沒有補充的序號 18。這是模型語意選擇錯誤，不是 App 映射或保存錯誤。現有主指引已區分來源時點；僅比較一句「收尾沒有補充不支持先前具體事實」的補強，不重試已否決的 schema description 方案。

依 OpenAI [工具指令與參數設計](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)及[任務型 eval](https://developers.openai.com/api/docs/guides/evaluation-best-practices)以實際參數選擇驗證。官方建議清楚說明使用與不使用時機，但不保證提示詞能消除錯引。

**有限外送 manifest（執行前）**：原合成案例保存的請求作唯讀對照；2 次錯誤後接續（改為實際新拒絕回覆），1 次原收尾基準＋2 次收尾指引候選，共最多 5 次生成與 5 次 count。`gpt-6-luna`／medium、store=false、all_turns，保留原 native items／phase；單次最多 8,192 output tokens、120 秒、零自動重試／compact；count 超過 32K 即停止，總測試預算 US$1。只在新診斷請求中替換待比較部分，不改任何既有 checkpoint／JD／Memory。使用全套原工具，不強迫指定工具；首次回應即停止、不執行寫入、不偽造工具成功。輸出只含公開工具參數、用量與指紋。未發生目標操作記未觀察，不算成功；這是局部模型選擇驗證，不是新的完整產品旅程。

容量預檢補記：前三次生成完成；候選多一句後的 count 為 32,029，較原基準 31,992 多 37，依原 32K 上界停止，未生成。僅將剩餘兩次候選的上界調至 33K，仍最多 5 次生成、總共最多 6 次 count，時間／US$1 不變；不重跑前三次、不裁切歷史。最初沙箱連線失敗未取得任何 API 結果，改在准許聯網的執行環境人工啟動，沒有 SDK 自動重試。

局部 probe 結果：兩次錯誤後接續均重新選擇有效來源建立職責，無未成立的序號；一次只用本次、一次保留歷史 2＋本次。原收尾 baseline 改選讀取，未觀察新增來源。收尾候選一次仍將主任錯指 `current_input`，另一次正確指 14，**不採納候選、不修改主指引、不宣告來源品質修復**。保留全部試次於 ignored `core-corrections-20261001.json` 與 `core-corrections-source-20261001.json`。

**短真後端確認 manifest（執行前）**：新隨機 `core_journey_20261001_*` schema，同一 loopback `_test` DB；只重用課程行政 b0-2 前四則合成員工原文，最多 4 A Turn 及自然觸發的最多 4 批 Memory，不人工代寫、不指定模型工具或修改原案例。不使用模擬員工模型；此為工作流程／更正的定向重播，不是自然訪談能力對照。A／B1／B2 沿 `gpt-6-luna` medium、原串流／all_turns，每 execution 最多 16 steps／48 outbound attempts／1 attempt per request／1 compact／240 秒、僅評測配置 US$0.25 上限，整組最多 US$2；失敗停止、不重跑。保留已發布內容、回讀逐項來源及背景狀態，等自有工作收尾再關閉 App；不動 Demo、原 eval 資料或現行程序。不重驗未改動的 PDF 視覺與 UI；沿 T13 原有效證據。

#### 本片結果與收斂

程式反例先加到既有 `test_jd_model_item_roundtrip.py`：猜本次輸入的未成立序號被拒、候選不變，且回傳合法修正方向。產品修正前 **1 failed**（提示缺 `current_input`）；分開錯誤處理後，JD 寫入／建立／來源相關 **16 passed**。再與憑證／HTTP 安全測試合併，提交前 **85 passed，14.35s**；三個變更 Python 檔 Ruff check／format 通過，`jd_writes.py` scoped mypy 通過。獨立 reviewer 無 blocking；提示語句的更细粒度契約測試屬可延期 minor，本輪不擴測試框架。

短真後端結果（新 schema `core_journey_20261001_c2e1fcd8`，檔案 `c0aaed2f-22e5-40fa-98f5-a6bc12c0a2ef`）：

| 核心效果 | 實際證據 | 限制 |
|---|---|---|
| 訪談逐步成稿與保存 | 4 A completed；正式 JD 有 1 職責、5 任務、6 成果、8 要求；修訂 `df1c8fb3-8868-4db8-8f75-021c1193eaba` 可由 HTTP 回讀 | 四輪仍在訪談，不是完整職務品質驗收；不能推定所有空稿都被消除 |
| 更正而不抹除既有工作 | 出席彙整改為每季；日常出席整理、課前兩個工作天交付、財務／主管權限界線仍保留 | 本片只驗這個明確更正，不外推任意跨主題更正 |
| 引用可回查 | 25 筆來源全部 HTTP 回讀成功；profile 三欄及目的引用 2，任務／明細使用相應 4／6／8 原文 | **可回查不等於來源涵蓋完整**：修改綜合職責時，模型明確移除舊來源、只留 8；8 不足以單獨支持保留的全部範圍，記為來源品質缺口，不由 App 猜補 |
| 背景 Memory | 2 批 completed，已發布快照涵蓋至序號 8；正式訪談 1–9，沒有 active 殘留 | 沒有在本片窮舉 Memory 正文品質或換版 diff |

真後端共 33 次生成、38 次 token count、零 compact，attempt 無 failure_code；正式回執的模型估算合计 **US$0.015535370**，不是帳單。自有 TestClient App 已正常關閉，合成 schema 保留供回查；Demo 程序及原 eval schema 未動。局部 probe 共 5 次生成／6 次 count，生成用量合計 input 113,082、output 5,042（含 reasoning；快取另見原件），不把 count 當成免費保證。

ignored 證據指紋（均全合成；不提交原 native reasoning）：

- `core-corrections-20261001.json`：`aa192bcfdbfea93d03721b259926deca6abec628ffb2533f989d05e4840b6b5a`。
- `core-corrections-source-20261001.json`：`08bd988753e4dab58e8467aa21e70e1e2cc7a137d274aa6e465571ca315da89f`。
- `core-journey-20261001.json`：`ef47ac8ee2246c6f2376059c96b489e9e3a7c075291dce0084209b3cfec80652`。

**本輪到此收斂，不無限跑到綠。**採用的產品改動只有可操作的來源越界拒絕提示；主指引／schema／Context／資料 owner 均未改。空任務稿的已定位接縫有局部修復證據，核心成稿／保存／背景流程可用；收尾錯引、綜合內容更新時漏保留依據仍待改善。T14／T17 品質與 T18 切換不勾選。下一個分析品質切片應沿既有原件研究「多項事實的來源保留與選擇」，不要再堆相同提醒或自動猜引用；部署／完整容量屬原 gate，不以本片替代。
