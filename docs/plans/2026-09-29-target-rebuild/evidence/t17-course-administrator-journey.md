# 課程行政訪談到 JD 的真模型旅程

> 最新結果（2026-10-02）：原採購長旅程已續完 45 輪、3 批 Memory 與 4 頁 PDF，沒有從頭重跑。安全收尾與成稿成立；10 筆 JD 依據仍待核對，且本例未自然產生 JD→Memory 引用，不能視為全部品質與換版 gate 已通過。見 [A2 實測結果](#a2-實測結果2026-10-02原旅程完成-45-輪)。以下保留各次 manifest／結果，不將歷史結論當最新狀態。

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

### 2026-10-01 續驗：局部更正與仍有效的來源

沿上一片保留的 `core_journey_20261001_c2e1fcd8` 原件診斷：A 第四輪完整讀取了職責及其來源 2，之後明確送出 `remove_source`，不是 projection 未給引用或 DB 自行清除。原話 2 同時提供報名、課前與課後工作；本次只更正出席彙整頻率，不能由局部更正推出整則舊原話都失效。

最小假說：把[分析指南 §4](../../../specs/2026-09-09-complete-work-analysis-guide.md#4-案例工作理解與-jd如何取捨而不丟失)「更正看語意範圍」落到既有來源動作的指引，區別局部更正與整筆來源移除。工具與來源模型不變、不強制引用數量、不由程式猜補來源；若原依據確已不適用，仍允許移除。研究沿 [OpenAI 工具設計](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)的清楚時機／限制及任務實測，不宣稱提示能保證正確。

**局部外送 manifest（執行前）**：只讀上述合成第四輪 `1f1bcf19-6520-6c9d-8007-e9acb8a5dc69` 的原生請求，保留全部接續 items／工具；比較 baseline 2 次、來源保留指引候選 2 次，最多 4 次生成＋4 次 count，`gpt-6-luna`／medium、store=false／all_turns。每次 input ≤ 40K、output ≤ 8,192、120 秒、零自動重試／compact，總預算 US$1。只改新診斷請求中的指引，不寫原 checkpoint、JD 或 Memory；不執行模型要求的工具、不偽造成功。保留每次工具選擇、用量、request 指紋於 ignored `source-retention-20261001.json`；沒有相關修訂則記未觀察。評讀最終文字、更正及剩餘來源是否共同支持完整範圍；不以保留某個固定 ID 當唯一答案。此片不是完整旅程驗收，也不重跑六組 baseline。

**結果：不採納指引候選。**四次依 baseline／candidate／baseline／candidate 交錯執行，均完成請求並提出相關修訂；沒有執行工具或改動產品資料。

| 試次 | 指引 | 輸入／輸出 tokens | 實際選擇與判斷 |
|---|---|---|---|
| 1 | baseline | 14,109／276 | 正確改為每季，但移除仍支持其他工作範圍的原來源，只留本次更正：缺口仍在 |
| 2 | candidate | 14,187／517 | 保留原來源並加本次更正，這一次改善；未宣告完成核對，仍可留待核對 |
| 3 | baseline | 14,109／750 | 再次移除原來源；另正確提出兩個新任務，不抵銷綜合職責的依據缺口 |
| 4 | candidate | 14,187／755 | 仍移除原來源；候選改善未能穩定重現 |

候選只補充「局部更正不使整則舊原話失效，仍支持保留內容的來源應保留」，未改 schema、模型或工具權限。兩次中僅一次改善，不足以採用；**不再堆提示詞、不禁止合法刪來源，也不由程式猜補事實依據**。本輪到此停止品質試驗，保留此已知限制供後續品質切片，不把 API completed 當作 T17 通過。

共 4 次生成、4 次 count、零重試／compact；生成 input 合計 56,592、output 2,298（含 reasoning），沒有讀取私有推理。ignored 原件 SHA-256：`a1e0377aadafa9ff44ca863fc1d9014fc1a351516cbf2b71482d484d06563185`。本次沒有產品 Prompt／Tool 程式變更，既有可操作拒絕提示修正仍維持。

## 2026-10-01：既有真模型產物的 UI 與 PDF 續驗

沿 [T14 六輪核心 App 對照](t14-job-analysis-quality.md#2026-10-01較高能力模型的核心-app-旅程對照)已保存的同一份 JD 補完整交付路徑；**零新模型外送、沒有人工補稿或改寫原產物**。這份原產物來自 Sol，不能冒充 Luna 品質證據；Owner 隨後已因成本決定產品維持 Luna／high，見 [T14 決策補記](t14-job-analysis-quality.md#2026-10-01owner-決定維持-luna)。

### 環境與唯讀旅程

新自有 loopback 58142 程序使用同一隔離 `core_journey_20261001_2331dc65` schema，**明確 `model=None`、不載入憑證**；使用目前 Web build、已驗 Chromium／中文字型，Demo 8100／5173 及其資料不變。瀏覽器只回看及匯出，不送新訪談、改稿或撤回。

- 職務檔案 `3450e704-3cb5-4b38-8d10-c2aae7156416` 的正式訪談序號 1–13、五項任務及能力／協作資料可顯示；正式 JD 仍為 `4ee14de2-f1cd-4893-9f96-912071f83c58`。
- 來源面板列出 54 筆依據；按出席紀錄任務的序號 8 讀回原話，日常出席、指定資料夾、每月→每季、人次口徑及不連帶變更其他工作均與保存原文相符。全部 54 筆逐字回讀已在 T14 驗過，本次不冒稱逐一點擊全部項目。
- 最後一輪「查看這輪 JD 變更」能顯示新增報名資料核對與異常分流技能及關係；這是該輪已保存的淨變更，不是推理或逐 Step trace。
- 已保存兩則公開中間訊息經下述修正後可展開，明示「非正式訪談、不可引用」；不新增正式訪談序號、不重新產生回答。

### 真實接縫：無模型設定意外停用了歷史投影

首次瀏覽器展開已完成回答時顯示「公開處理訊息目前無法讀取」。不是原訊息遺失：HTTP status 返回 `commentary:null`；`ConsultantStatusWorkflow` 沒有 checkpointer 時不投影。根因是 composition root 把既有 PG saver／status 接線放在 model 配置分支內，使**只讀已保存歷史**意外依賴模型金鑰。

依 [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/)的共用資源生命週期與 [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) 的已保存 state 查詢機制，將 saver 的既有建立／setup／關閉放到 DB lifespan，模型 client／runner／supervisor 仍留在 model guard。這是 Caliburn 的權責修正，不是聲稱官方強制此分檔。沒有增加新 store、快取、歷史副本或恢復平台。

既有 `test_http_input_reaches_saved_formal_answer_and_reopens_without_model` 先完成一次真 PG＋合成 provider 的顧問答覆，再關閉 App，以無模型設定重開同 DB：

1. 原 execution 應回原 commentary 與 completed；不能因無 key 丟失回看能力。
2. 模型呼叫仍只有一次；新員工輸入返回 `503 model_not_configured`。

修正前 **1 failed、2 deselected**（commentary 為 null），修正後相關 **22 passed、13.68s**；涵蓋 HTTP execution／status／controls／commentary stream、bootstrap 與公開投影。scoped mypy、兩檔 Ruff check／format 通過。真瀏覽器重開後，原兩則 commentary 亦可讀；此測例使用合成 HTTP provider，不是新的真模型品質驗收。

提交前唯讀審查另指出 `/current` 的舊測試仍期待 `commentary:null`；實跑 **1 failed、12 passed**，只有此項不符。現在 saver 已可讀、尚無訊息，正確表示應為 `[]`（不是不可用的 null）；只更新該預期，未放寬契約。合併上述六檔與 `test_current_consultant_turn.py`、`test_interview_history_turns.py`，提交前 **37 passed、21.65s**，scoped mypy、三個變更 Python 檔 Ruff check／format 通過。審查確認 SDK／supervisors 仍受模型配置 guard；額外建構次數 spy 屬非阻擋補強，未增加測試框架。

### 同份 JD 的正式 PDF

從畫面「匯出目前 JD（PDF）」實際下載 `job-description (3).pdf`，SHA-256 `f016a1114052cea96f4d4722fb560406adc3dfc6f2bda5e3f6613413cc48e2a9`，**754,092 bytes／3 頁 A4**。Poppler 逐頁渲染並檢視全部三頁：中文可讀，無遮疊或截斷；跨頁任務及成果／要求、知識／技能、四個協作對象均保留，頁碼正確，不含員工姓名。沒有來源鏈／中間訊息混入 JD 成品。

pypdf 抽取後對照原保存 JD 的 **49 個非空文字欄位**，經明示的 Unicode NFKC、`⻑`→`長` 及空白正規化後全部可找到。**這只是比對方式，不修改 PDF，也不是原文字元完全相同的證明**；未正規化有 37 欄因既有字型 cmap 部首字元而不相同，沿 [T13 已知文字層限制](t13-pdf-export.md#任務完成對照與-pdf-文字層診斷2026-09-30-恢復後)，不新增字型加工系統。三頁 PNG 留於 ignored `.research-tmp/eval/core-journey-sol-pdf-1.png` 至 `-3.png`；原下載留在本機 Downloads。瀏覽器下載橋接回應耗時異常，未取得可靠端到端耗時量測，不能將工具等待時間當產品匯出延遲。

### 結論與未驗

本片確認**同一已保存產物 → UI 回看／來源 → PDF**可用，並修正無模型時的歷史投影接線。沒有修改 Prompt／Tool descriptions／Context 組裝、產品模型或正式資料；不把機制通過當成 Luna 的來源語意缺口已修復。JD→Memory 換版 diff 的真模型判斷、廣泛長訪談品質及 T16／T18 原 gate 仍按原文件，T17 不勾選完成。後續以 Luna 及既有原件處理核心缺口，不再追加 Sol 比較。

自有驗證程序已正常完成 shutdown，唯讀分頁關閉；合成 DB／PDF／PNG 保留，沒有停止 Demo 或刪除資料。本次新增／修改的 12 個相對文件連結均可找到目標，`git diff --check` 通過；全檔檢查所見舊 worktree 歷史連結失效不在本片改寫。

## 2026-10-01：Luna 的 Memory 換版與人工改稿定向驗收

### 外送前 manifest

基準 `67ebea87`；Owner 已決定產品使用 Luna。本片補前節尚未驗的 JD→Memory diff 判斷，不重播長訪談、比較 Sol、追加提示詞或自動猜補來源。[OpenAI 完整工作流驗收建議](https://developers.openai.com/cookbook/examples/agent_optimization/optimizing_agents_for_cost_and_quality#track-the-complete-support-workflow)強調同時看實際操作軌跡與結果，不只看最後答覆；本案沿用既有 rubric，沒有另建評測平台。

- **受控前提，非自然成稿證據：**獨立 `recheck_luna_20261001_7dce0494` schema，合成職務檔案 `4ea25807-4f55-4bdc-8dcc-52f937a9f1bc`。透過現有領域／交易入口建立兩則正式員工原話、兩版 Memory 與舊 JD 引用，不捏造原生 reasoning／checkpoint。M1 是每月盤點；M2 根據後續更正改為每季、情境改名，帳物核對／差異清單／主管核准界線不变。理解仍引用同身分的新情境；JD 保留 M1 來源。人工再把 JD 加上不實的「本人核准補貨」。這只是換版接縫的前提，不冒充 B1／B2 真分析或 AI 初始成稿。
- **實際執行：**只送一則員工請求，說明先前已更正盤點周期，人工誤寫核准補貨、實際由主管核准，請顧問核對修稿。模型自主使用完整現行工具；不強制特定 call，不直接替它完成核對或修稿。開始前先用無模型後端準備並核對前提，尚無付費外送。
- **上限：**`gpt-6-luna`／high、`store=false`／all_turns，單次執行最多 16 create／48 outbound、零傳輸重試、1 compact、8,192 output、120 秒單請求／240 秒執行；測試預算每執行 US$0.25。一個 A Turn，至多一個由該輪自然要求的背景批次（B1／B2 共用批次上限），總預留 US$0.50、32 create／96 outbound；不使用 Sol、不擴量補跑。A 或背景達上限／非 completed 即記錄並停止新工作；觀察逾時須核對原執行，不能另送一次。
- **判準：**A 能定位舊 JD 與既存 citation，閱讀需要的人工／來源差異及本 Turn 固定新 Memory；正式稿改為每季，保留核對與差異回報，不把人工新增的核准權當事實。只有實際重評後才確認既存依據對齊，或作有理據的來源變更；不能只讀過 diff 就自動解除待核對。保存後核對來源身分／版本與內容，再檢查舊固定引用仍可讀。若需要追問，允許保留未解狀態，但不能把它記成此案例已完成。
- **本機重現：**ignored `verify_memory_jd_recheck.py` 預設僅準備；`--run` 才外送且 evidence 已開始就拒絕重跑。新 schema／原件保留，不讀寫 Demo、不輸出憑證／opaque payload；只保存合成公開內容、必要定位及用量。本片是品質驗收，不宣稱 TDD 或整段員工只訪談的旅程通過。

### 網路環境診斷與一次補驗

第一次 A `40f6bf9f-402d-4b26-8c1f-37a14a87690f` 於 3.39 秒失敗，ledger 僅有一次 `token_count / remote_result_unknown`，沒有 model 外送；未重試，沒有正式訪談／JD／引用變化，無 active 殘留。checkpoint 終止原因為 `request_attempts` 上限，不是模型判斷錯誤。無金鑰的同一官方 `/v1/models` 探測：沙箱內 `ConnectError`，沙箱外 HTTP 401，確認是執行網路環境差異；無需改產品重試、Prompt 或資料。

在檢查前後業務資料相同後，追加**一次**沙箱外補驗，仍使用上節模型、內容、單執行限額及 US$0.50 總預留，另存 `memory-jd-recheck-luna-network-20261001.json`。原失敗紀錄保留，不清理 DB 或宣稱遺失請求免費；補驗以同文字新輸入啟動，不冒充恢復舊未產生的回應。若再失敗就停止，不繼續擴量。

### 真 Luna 結果：修稿與引用對齊成立，來源 diff 使用未觀察

補驗 execution `0c21a3fb-d872-4c3f-aec8-33e8812da0dd` completed；觀察區間 32.22 秒（含輪詢，不是純模型延遲）。模型自主完成 5 次 Responses／5 次 token count、10 次工具操作，零傳輸重試／compact，未要求新背景批次。沒有修改產品 Prompt、工具、Context 或程式。

| 檢查面向 | 實際結果 |
|---|---|
| 改稿效果 | 原任務身分保留；每月改為每季，保留帳物核對及差異回報，移除員工的補貨核准權，明確由倉庫主管核准 |
| 實際閱讀 | 讀 JD map、人工差異、訪談 1–4、新版情境與理解全文、任務與既存來源；沒有讀任意舊 Memory 的工具入口 |
| 明確核對 | `revise_jd_item` 同次修改 description、加入更正原話 4，並對原 citation 明確執行 `confirm_reference_alignment`；之後重讀任務確認結果，不是 App 因讀過內容而自動解除待核對 |
| 保存及引用 | 正式 JD 修訂 `14b6664d-b2ee-4737-a673-f00750161f46`；原 citation `69791929-b372-4e55-9677-b69bf0a0c6be` 身分不變，已對齊 M2 的理解修訂且不再待核對；新增引用 4 可支持更正後內容 |
| 舊依據不被改寫 | 原 JD 修訂仍指 M1；M1 理解、情境、原話鏈仍可讀。M2 引用指向其選用的情境修訂，不偷換舊快照 |
| Context／歷史 | 五次請求的固定 App 資料 hash 相同；App 資料為 user、當次原話另外提供，接續 items 由 2→14→22→26→29 增長，保留原生輸出／工具結果。正式訪談最後為 1–7，失敗輸入未佔正式序號、未混入本次 Context |
| 重開 | 關閉後以無模型 App 重開，同一正式 JD 可由 HTTP 取回；無 active 執行殘留，不額外呼叫模型 |
| 尚未觀察 | 模型只呼叫 `read_jd_changes` 的 **manual** 分支，沒有使用 **source** 分支。因此不得將本次記成「來源 diff 已被真模型按需使用」通過 |

實際正式任務正文：

> 每季核對庫存帳與實物，將差異清單交給倉庫主管；本人負責核對與回報，補貨由倉庫主管核准。

最後答覆正確摘要修訂，並追問交付差異清單後是否仍須追蹤，不把整份職務宣稱為完整。兩則公開中間訊息亦可回看，沒有成為正式訪談依據。

**證據邊界：**這是短 Context、單項工作的受控換版／人工改稿接縫，不是自然長訪談。前兩個正式交流及兩批 Memory 為現有 domain workflow 建立的 fixture，非此次模型產物；沒有先前真 A checkpoint，故人工差異比較基準是初始空 JD，包含建立任務、加引用、人工誤改共三個操作。模型有根據新全文及原話修稿與對齊，但未觀察到來源 diff；不藉此消除 Luna 長歷史漏保留依據的已知限制，不勾整體 T14／T17／T18，也不為單例再加提示或強制工具呼叫。

生成 usage 合計 input **50,994**、output **1,926**（含 reasoning）；ledger 模型費用估算 **US$0.002804150**，不是帳單，不含未確認的 count 費用。首次失敗另有一次 count 嘗試，原紀錄保留；沒有把它算成新生成或宣稱免費。

本機 ignored 原件均只含合成資料。結果由 `audit_memory_jd_recheck.py` 唯讀核對已保存請求／輸出、正式引用鏈與重開結果，不輸出 encrypted reasoning。保留以下 SHA-256 供重現比對（前兩項為有界 harness，後兩項為原結果）：

- `verify_memory_jd_recheck.py`：`299482a759ff2377ab7cae3cc560f750c2fd0156fb27539e96e4366c08990195`。
- `audit_memory_jd_recheck.py`：`81250cf200bd5cc8ecff8670485798ca23ccddfe3cd557bfd32c402f49234022`。
- `memory-jd-recheck-luna-network-20261001.json`：`07c191f7aa9677e5dea23202b506a0265584b34984497fb7a29413d77dc18bf7`。
- `memory-jd-recheck-luna-audit-20261001.json`：`fbd285d992b9917c3445e846bd55e1f2c9dd7fb6d8e1c22a87cf78d871a86fbc`。

實際 instructions hash `028a05d80d6e71b37094b989ff764576f7ed49eef1610b63b243b27d6b39b3fe`、tools hash `f424fc85dc708422444da3546d8103d29735aec7e44bd11a6b67ba9c3b86b373`；沿現行 Luna／high／all_turns／store=false。其餘既有容量及正式切換 gate 不變。

## 2026-10-01：同一合成案例的純來源換版接續

### 外送前 manifest

基準 `583aec0d`。前片已驗人工差異與新全文修稿，未觀察來源 diff；本片改變的是**前提**，不是 Prompt 或工具：沿同一已完成 Luna 案例及真原生歷史，追加一則合成有效訪談，透過原 domain workflow 發布 M3。已知事實改為每半年盤點、差異交財務專員；本人核對／回報及主管補貨核准不變。JD 不人工修改，保留原 M2 引用，讓來源換版與人工改稿分開。準備資料是 fixture，非 B1／B2 真分析；本片只驗一個後續真 A Turn。只升級此隔離 schema 至目前 migration head，不碰 Demo。

使用既有 `recheck_luna_20261001_7dce0494`，先核對原完成記錄與無 active 執行、JD 及引用；原 M1／M2、舊 JD／原件不改寫。A 新输入只請核對目前盤點 JD，不提示新頻率／交付對象或指定工具名稱。模型自由選完整現行工具；不強制先讀 diff、不用人工完成來源確認。依 [OpenAI 工作流評估](https://developers.openai.com/api/docs/guides/agent-evals)同時檢查實際 trace 與最後效果，不因最後文字正確就假設模型有讀 diff，也不要求唯一工具序列。

限制：Luna／high／all_turns、store=false；一個 A Turn，至多一個自然要求的 Memory 批次；各執行最多16 create／48 outbound、1 compact、8,192 output、120秒單請求／240秒執行、US$0.25，合計預留 US$0.50、32 create／96 outbound，零傳輸重試、不重送同案例。達上限或失敗就記錄、核對原工作狀態並停止，不把觀察逾時當執行結束。只外送合成資料，沿既有憑證 loader，不保存秘密／opaque reasoning。

檢查：按需工具是否讀到來源 Markdown diff；是否用本 Turn 新 Memory 修成每半年、交財務專員，同時保留核對／回報及主管核准界線；是否以明確動作核對既存引用，或如實保留尚未解決；正式保存、舊引用鏈、只讀重開及實際 Context／用量一併核對。來源 diff 未被使用便維持該分支未觀察，不追加提示求過關。本片不重開上一輪 B1 精度假說、不消除長訪談漏引限制、不勾整體 T14／T17。

### 結果：來源 diff → 修稿 → 明確對齊 → 正式保存成立

execution `17ac9ab4-64db-4ff1-bce4-6dc0547dcb78` completed；觀察區間 **33.64 秒**，不是純模型延遲。六次 Responses、七次 count（含歷史準備）、十次工具、零重試／compact；沒有要求新 Memory 批次。fixture 準備與此次真 Turn 結束後均無 active／paused 殘留，沒有啟停 Demo。

| 檢查 | 實際證據 |
|---|---|
| 自主按需閱讀 | 讀 JD map／task、新情境及理解全文、訪談6–8；之後以既存 citation 呼叫 `read_jd_changes(query.kind=source)`，未強制 tool choice |
| 真正差異內容 | 回傳 Markdown 包含理解的描述／正文變更、直接情境改名／描述／正文及新增訪談引用8。不是只列「有更新」，也沒有提供任意歷史 Memory 全文入口 |
| 精確修改與核對 | 同一 `revise_jd_item` 改任務 description、移除被新做法取代的直接訪談4、引用8，並 `confirm_reference_alignment` 原 Memory citation；然後重讀 task 核對實際結果 |
| 正式稿 | 「每半年核對庫存帳與實物，將差異清單交給財務專員；本人負責核對與回報，補貨由倉庫主管核准。」其他集合未新增；任務身分保留 |
| 引用與歷史 | 原 citation 身分不變，從 M2 更新到 M3 理解修訂，已核對 JD 基底為新正式修訂 `a9354a53-32e1-4b22-856e-d7e62ef38894`；兩筆現行引用不再待核對。舊 JD 仍指 M2，M2／M3 的理解及其固定情境修訂皆可回讀 |
| Context | 六份實際請求的本輪 App 資料 hash 一致、全部 user role，本次原話獨立提供。Memory 處理至8，近期只預載9；8的細節由模型按需查回。原歷史後追加本輪資料，items 33→43→50→54→57→60；五次相鄰請求保留原 input 前綴及既定原生出站投影 |
| 重開與答覆 | 無模型重新建立 App，HTTP 讀回同一份正式 JD；最後答覆正確交代改動，追問差異清單交出後是否仍須追蹤，沒有假稱整份 JD 完成 |

本片沒有修改產品 Prompt／schema／Context 或規則。instructions hash 與前片相同；tools hash `ba7a05849563dd9c8d26b46d2b342dea9b2c8360b1208467f72473945e794a5e` 反映先前已提交的 A 輪前壓縮要求工具，非本片為驗收改工具。生成 input **83,809**、output **1,727**，ledger 估算 **US$0.003459375**（非帳單，不含未確認的 count 計費）。不以成本低或樣本通過推論普遍可靠。

稽核先出現兩個**探針假設錯誤**，均唯讀核對、不重送模型：泛查 execution 所有 checkpoint 混入 `prepared_history`／`initial_context` 尚未追加本次輸入的快照，改為精確查既有 `completed_work` 模型迴圈；另原 output 直接等同比對出站 items 過嚴，逐欄確認差異只在頂層 `status`，沿 [T06 已驗投影](t06-agent-execution.md)與 `response_input_items` 再核五個接續邊界通過。沒有因此刪歷史、放寬產品或改接續邏輯。

**限定通過與未完：**前片的「source 分支未觀察」由此次實際工具軌跡補上；本案例有來源差異閱讀、正確修稿、明確對齊及正式保存／回查證據。這是受控單項來源換版、沿一次既有真 A 歷史的接續，不是完整工作訪談、自然 B1／B2 分析或長 Context 的跨輪來源保留已達標；T14／T16／T17／T18 保持原未完成狀態。不再重測此案例。

本機 ignored 原件（全合成）SHA-256：

| `.research-tmp/eval/` 原件 | SHA-256 |
|---|---|
| `verify_source_only_recheck.py` | `b9626e23abf65b4636740a5ed38d5a7207dfdb8ff76d9e1909c85afd78b313fa` |
| `audit_source_only_recheck.py` | `cbc0bb5513c90d6230300d21349accd75a4acb60d62c7b15592e86f56f04d4d9` |
| `source-only-recheck-luna-20261001.json` | `6d739c480a35f15058a771a7ce8d82aa5091603b8c15e2f9b19825a44184a991` |
| `source-only-recheck-luna-audit-20261001.json` | `4d6416ed271b6242ea633e2126b7f84e743d0fc3a916712dafc424332eecf956` |

## 2026-10-01：Luna 長訪談收尾的有界接續

### 執行前範圍與判準

沿 [T14 已完成五輪的 high 旅程](t14-job-analysis-quality.md#補驗正式結果與限制)，不重跑訪談、不重測已否決的來源提示候選。第六輪先前因 `transient_service` 最終失敗；其後上節 Luna 已完成六次 Responses，故本片只重新送出尚未成為正式訪談的收尾輸入一次。這是新 Turn，不冒充取回先前遺失的模型結果，也不把服務現已成功當成品質已修復。

沿 [OpenAI 評估指南](https://developers.openai.com/api/docs/guides/evaluation-best-practices)分開工具選擇／參數及最終效果，使用原 App 的真實接續；內容判準依 [工作分析 §6](../../../specs/2026-09-09-complete-work-analysis-guide.md#6-如何檢查整份工作已被適當涵蓋)、[JD 寫作 §3–7](../../../specs/2026-09-09-jd-field-and-writing-guide.md#3-職務目的職責任務同一份工作的不同縮放程度)及 [訪談校準 §6](../../../specs/2026-09-09-customized-jd-depth-and-interview-calibration.md#6-怎樣才是整份工作被理解而非只問透一案)。不使用官方託管 Evals 平台、不新增 reviewer 或驗收子系統。

- 基準 `7d631737`；專用 DB `caliburn_t01_test`、schema `core_journey_20261001_635da286`，職務檔案 `a40b19dc-da6f-4105-9a4c-2c068edcaafa`。已唯讀確認無 active／paused 工作；原稿 `f76545e8-d4b9-43ce-871b-2e72fe07252a`、正式訪談末序號11。只在此 schema 明確升級0019→0020，不動 Demo。
- 只送既有合成收尾句：「目前我主要做的工作大致都說了。我想先整理目前已談到的工作，其他不清楚的部分先保留未知。請幫我檢查現在的職務說明書還缺什麼。」不加入預期答案、來源序號提示或強制工具選擇。
- 一個 A Turn、至多一個自然要求的 Memory 批次；Luna／high／all_turns、store=false。每 execution 最多16 model steps、48 outbound attempts、1 compact、16,384 output、120秒單請求／300秒執行、US$0.50，整批預留 US$1，零請求重試。輸出上限沿現行產品預設，不宣称與過去8,192探針完全同條件。
- 失敗停止，不再重送同句；觀察逾時先核原 execution，不能當成工作已終止。所有外送僅既有合成訪談、App 指引及其產物；原始秘密與 opaque reasoning 不進報告。
- 檢查既有有效工作是否保留、任務粒度與 K/S 是否有據、已知更正與未知是否忠實、來源是否支持每項主張、答覆是否如實；再查正式保存、原來源回讀、無模型重開及實際 Context／用量。既有拆分漏引或 Memory 精確化若仍在，就保留缺口，不替模型補資料、不降低 gate。

探針 `.research-tmp/eval/verify_luna_closing_turn.py`；結果獨占建立為 `luna-closing-turn-20261001.json`，不覆蓋前次證據。本節先記執行範圍，尚不宣稱通過。

### 結果：第五次模型請求失敗，安全收尾成立，品質未通過

execution `35367359-e385-49c7-b992-a2d44ccda79e` 最終為 `failed`，觀察區間 **52.85 秒**。四次 Responses 完整返回，第五次 model attempt 記為 `transient_service`；五次 count、八次已完成工具、零重試／compact。依 manifest 停止，沒有再次重送收尾句，也沒有切模型、改 Prompt 或工具。

| 檢查 | 實際結果 |
|---|---|
| 已完成工作 | 自主讀 JD 全文／map／協作對象、情境／理解 map 及訪談4、6；候選新增協作對象「學員」，提出 Memory 整理意圖。沒有最終正式答覆 |
| 正式資料與回退 | JD 修訂仍為 `f76545e8-d4b9-43ce-871b-2e72fe07252a`，37筆正式來源仍可回讀；正式訪談維持1–11。候選與整理意圖沒有生效，已發布 Memory 仍為 `0ad00867-27c1-4f28-b8c5-8409a417aa59`、處理至10，沒有新背景批次 |
| 可繼續使用 | 執行統計為5個完成 A、3個失敗 A、5個完成 Memory，無 active／paused 殘留；無模型重開取回同一正式 JD。這證明本次失敗安全退出，不代表所有失敗都已驗證 |
| 接續觀察 | 五份已保存請求的本輪 App 資料指紋一致，原生視窗 items 為242→250→261→264→269，均為 `high`／`all_turns`。不是因工具後重建成只有最新問答；本片沒有執行 compaction |
| 品質反例仍在 | 「學員」候選引用4、6及 `current_input`；當次只是要求整理，未提供協作事實。核對聯絡資料、說明確認事項、名冊記錄的直接出處在10，不在當次輸入。不能以4、6可查到或新增工具成功，就稱整組依據精確。此候選未正式提交，不宣稱正式稿多了一筆錯引 |

**串流診斷：**再次看到 `ValueError: async generator already executing` 的 generator 清理警告。依[官方串流事件契約](https://developers.openai.com/api/docs/guides/streaming-responses)、本機鎖定 OpenAI 3.20.0／httpx2 2.13.1 原碼與現行 adapter，完整 terminal 與串流／HTTP error 是不同路徑；`transient_service` 只由相應 APIError 分類而來，普通 generator `ValueError` 不是該分類的充分原因。既有 ledger 只留下安全類別，沒有這次原 HTTP status／stream code，**無法回推究竟限流或服務錯誤，也不能證明警告與失敗有因果關係**。不憑猜測加 SDK 私有補丁、重試層或恢復系統。

離線執行 `python -m pytest tests/unit/test_openai_failures.py tests/unit/test_response_streaming.py tests/contracts/test_openai_responses.py -q`（`apps/api/.venv-target`，工作目錄 `apps/api`）：**60 passed**。涵蓋 terminal 保存、cleanup／取消交接、stream error 分類與 SDK 零隱式重試；未重現該 generator 警告，不當作修復證據。唯一 pytest warning 是沙箱不能寫既有 cache，不影響測例結果；沒有為此提升權限重跑。

四份完整生成 usage 合計 input **279,841**、output **3,871**；ledger 可核對估算 **US$0.012182045**，不是帳單。第五次失敗請求及 count 的未確認費用不當作零。沒有新 B1／B2 費用紀錄，不追加大視窗測試。

本片只增加驗收證據，沒有產品程式／規則變更，不宣稱 TDD。T14／T16／T17／T18 仍未完成：既有跨輪來源涵蓋、Memory 精確度及成稿粒度限制沒有消除。停止這個收尾案例；下一切片先處理未完成 gate 的具體缺口，不再用同句重跑或同義提示微調求過關。若另有必要的真模型驗收，先讓探針安全保存 HTTP status／已知 stream code 等診斷資訊，再依當時配額與既有有界重試契約訂新 manifest；不外露 provider 原文、秘密或另建產品診斷平台。

本機 ignored 原件 SHA-256（只含合成公開資料、指紋及用量）：

| `.research-tmp/eval/` 原件 | SHA-256 |
|---|---|
| `verify_luna_closing_turn.py` | `2d568bedd1260598f949c4b0dd587ee3636191c23e8f9d99f2e4d5756d26c171` |
| `luna-closing-turn-20261001.json` | `064107372180c046254954dc335c0e42094205c565b8afe2a86763e4bfd04df2` |

## 2026-10-01：結構整理後的核心品質基準（Q1）——執行前 manifest

基準 `d41e75f7`（程式與 `2be43132` 相同；其後只有 lint 設定與評測腳本）。前面的 b0 六份是**舊預設 medium** 的產物；產品現在是 Luna／**high**，且已有結構整理與 Memory 解阻接線，所以先在**目前程式與預設**重量一次基準，再決定是否值得改任何指引。不沿用 b0 結論當作現況。

| 項目 | 界線 |
|---|---|
| 目的 | 量現行產品在兩個既有人設上的核心訪談與成稿效果（任務覆蓋、更正、未知、K／S、條件、協作對象、來源支持、簡潔、提問方式），並確認結構整理沒有改變行為 |
| 模型／資料 | A、B1、B2 為產品預設 `gpt-6-luna`／high（`store=false`、`all_turns`）；員工模擬 `gpt-6-luna`／low；全合成人設，不含任何真實員工或 repo 資料 |
| 次數 | `course_admin`、`warehouse` 各 3 次，每次最多 12 個 A Turn（人設預設）；背景 Memory 依 A 的要求自然觸發；**依序執行**，同時只有一場訪談（帳戶 TPM 200K，不並行） |
| 費用 | 以 b0 與 T17 實測推估單次 US$0.1–0.4，本批總上界 **US$4**；產品不設金額攔截，上界由次數與人設決定，不是帳單保證 |
| 停止／重跑 | 任一 Turn failed／逾時（900 秒）即停止該次並先診斷，不自動重跑；同一人設連續兩次失敗即停止本批；非 provider 的 5xx 或結構錯誤立即停止。不因結果不好無界重試，也不挑最好一次呈現 |
| 環境 | 隔離 loopback `_test` DB 的新 schema `eval_b`、後端 8103（`scripts/run_backend.py --port 8103`，PDF 字型／Chromium 以環境變數明示）；不動 Demo 8100／5173 及舊 `eval_a`／8102；憑證只經既有 loader 從 `apps/api/.env` 取 OpenAI key，不輸出、不記錄 |
| 量測 | `scripts/simulate_interview.py` 既有檢查，另加粗略的**引用審計**（JD 項目所述的人設事實，其引用來源是否含該事實）；每次一份 JSON 在 ignored `.research-tmp/eval/q1-*.json`，不含 opaque reasoning 與金鑰。仍須人工讀逐字稿與 JD 對照指南，自動檢查只用來比較 |
| 判讀 | 只在重複出現且可由指南指出的缺口才考慮最小指引改動，且須另設假說、保留例與停止條件；一次成功不算改善，不重做已被否決的來源說明／欄位順序／effort／壓縮方案 |

## 2026-10-01：長訪談與完整旅程（採購專員）——執行前 manifest

基準 `c1066873`。T17 要求的是一個獨立、從頭到尾的代表旅程，而不是十二輪短測：早期情境後期補充與更正、Memory 尚未發布時續談、人工改稿與來源換版同時出現、取消與重試、後端硬停止後的恢復、JD 完成與 PDF。Q1／Q2／Q3 只有十二輪，量不到這些；所以這一份用 36 項事實的採購人設跑長訪談。後端載入的是**已含「限流等待不算失敗」**的程式（[T06 §24](t06-agent-execution.md#24-限流是等待不是失敗2026-10-01)），指引是 T14 採用的 c3（提交 `1e9edcea`）。

| 項目 | 界線 |
|---|---|
| 目的 | 在同一份職務檔案的長訪談中驗上述旅程，並記錄 context 增長、壓縮（A 輪前 128K、B1／B2 輪前 128K、中途 160K 若自然觸發）、Memory 批次、耗時、限流等待與費用；同時是 T14「跨輪來源漏引」限制在長歷史下的量測 |
| 模型／資料 | A、B1、B2 為產品預設 `gpt-6-luna`／high（`store=false`、`all_turns`）；員工模擬 `gpt-6-luna`／low；全合成採購人設（36 項事實：核心／被問到才說／低頻／兩項員工確實不知道），不含任何真實員工或 repo 資料 |
| 次數 | 先 1 次≤4 輪的**操作演練**（只驗 harness 的取消／硬停止／人工編輯／PDF 路徑，不當品質證據）；再 1 次主旅程 `--persona procurement --max-turns 50 --human-edit-at 14 --cancel-during 20 --kill-during 30 --export-pdf --think-seconds 20 --retry-failed 3`，最少 45 輪才允許結束。**只跑這一次**，不重跑、不挑結果 |
| 費用 | Q1 十二輪約 US$0.05；長歷史使每輪變貴，推估 US$1–2，**停止上界 US$4**（產品不設金額攔截，上界是我的停止條件，不是帳單保證）；耗時預估 2–4 小時（受 TPM 200K 限制，約每分鐘 20–29 萬 token） |
| 停止 | 同一輪連續 4 次（原送＋3 次重送）都失敗、harness 崩潰、累積估算費用達 US$4 或總時間逾 6 小時即停止並診斷；被限流只是等待，不是停止條件；取消與硬停止是刻意注入 |
| 環境 | 隔離 `eval_b` schema 的 8103 後端（已升到 migration 0021；`scripts/run_backend.py`，PDF 字型／Chromium 以環境變數明示）；硬停止＝強制結束後端程序後重啟（DB 不動）；不動 Demo 8100／5173、8101、8102、8104；憑證只經既有 loader，不輸出 |
| 量測 | harness 檢查（事實浮現／入 JD／兩次更正／引用審計／形狀／風格）；DB：executions、outbound attempts（含 `rate_limited`）、compaction、估算費用、Memory 快照與批次、checkpoint 大小與逐請求 provider 計數；逐 Turn 耗時；PDF 頁數與文字。一律另讀逐字稿與 JD 對照指南 |

**預先判準（逐項通過／不通過，不合成分數）：**

| # | 判準 |
|---|---|
| J1 完成度 | 每個非刻意注入的 Turn 最終 completed（限流等待後完成算完成；被重送的失敗輪次逐筆列出原因）；刻意注入的取消與硬停止各依預期收尾；沒有卡住的 execution |
| J2 取消 | 被取消的輸入不在正式訪談重複出現、不佔正式序號；重送的同一句話只成為一則正式員工訊息 |
| J3 硬停止 | 重啟後同一 execution 走到 completed 或安全終止，harness 可繼續；正式訪談／JD 沒有重複寫入；沒有 active 殘留 |
| J4 人工改稿 | 第 14 輪的人工目的與人工任務到最後仍在，或有員工原話支持的明確改寫 |
| J5 更正 | 兩次更正（績效評鑑頻率、核准金額）都生效：新值出現、舊值不當成現行、其他工作保留 |
| J6 引用 | 引用審計支持率 ≥ 0.9；所有被標記項目逐筆讀原文判定（引用顧問訊息作上下文不算錯，看員工原話有沒有被引到）；profile 欄位來源皆有支持 |
| J7 Memory | 背景批次發布且涵蓋最終正式訪談前沿至多落後一批；失敗批次與解阻路徑如實記錄（限流不再算失敗） |
| J8 Context | 記錄各角色最大請求與壓縮發生處；若自然觸發壓縮，壓縮後仍使用壓縮前的事實（逐字稿核對）；沒有未預載而被當成已讀的範圍 |
| J9 PDF | 成功匯出，頁面目視可讀，內容與目前正式 JD 一致 |
| J10 無捏造 | 人工讀 JD：沒有員工未說過的事實，兩項未知（付款條件依據、關稅稅則）維持未知 |
| J11 限流 | 記錄限流等待次數、最長一次等待與 `rate_limited` 嘗試占比；沒有輪次因限流而失敗（新機制的真模型驗證） |

單次、單一人設；通過只說明這條旅程在這份資料上成立，不是普遍保證，也不替代 V25 的真人試點。

### 執行中事故與續跑修訂 A1（2026-10-01 22:57–23:20，在第 25 輪之後的任何付費請求之前寫下）

**交接狀態：**以下保留前位執行者的事故紀錄；A1 是續跑提案，不代表 harness v4 已完成或已重啟續跑。後續唯讀核對及須先釐清的差異見下一節。

**事實（唯讀取得）：**主旅程 22:21:58 起跑，第 1–24 輪全部 completed（含第 14 輪人工改稿、第 20 輪取消後重送、第 20 輪輪前 128K 壓縮）。到此為止 308 次外送嘗試、估算費用 US$0.13；34 次失敗嘗試**全是 `rate_limited` 等待**，沒有別種失敗。第 25 輪 22:56:08 開始，22:57:22 最後一次外送嘗試是限流等待。**22:57:40 前後，本機測試 PostgreSQL（loopback 55439 的原生 EDB 叢集，非 Docker）被外力硬殺**：日誌停在 22:57:26 的 checkpoint 開始、沒有任何關機紀錄，最後一個 WAL 寫入 22:57:39。Demo 的 8100／5173 同時不再監聽（消失時間未確認），Docker Desktop 的 WSL 發行版也是停止狀態。同一秒的 Windows 系統日誌有一組服務設定變更（含 ChatGPT 桌面程式的服務）；**只能說時間吻合，無法證明因果，原因未確認**。我沒有執行任何停止這些程序的命令。

**處置：**23:16 以原參數（`postgres -D .research-tmp/postgresql-t01-data -p 55439 -h 127.0.0.1`）用 `pg_ctl` 重啟；日誌顯示 `not properly shut down; automatic recovery` → `redo done` → `ready to accept connections`，資料未損。評測後端 8103 與 harness 在伺服器消失期間仍活著；資料庫回來的瞬間 harness 因輪詢拿到 HTTP 500 而崩潰（`wait_for_turn` 只把連線錯誤當暫時性）。**登記的停止條件「harness 崩潰」成立**：我停下、沒有再送任何請求，改為診斷。

**診斷：**
1. **環境事故，不是旅程結果。**第 25 輪沒有完成，也沒有失敗結論；資料庫裡它仍是 `active`，第 1–24 輪的資料完整。
2. **產品面（列為已知不足，不在跑測期間改 `src`）：**後端的 LangGraph checkpointer 只持有一條資料庫連線，leader lock 設計上「不重連、不重新取得」（`process_lock.py`：原 session 消失即不可恢復所有權）。資料庫**伺服器**被殺後，這條連線永久關閉，讀 checkpoint 的端點（如輪次狀態）持續回 500，即使資料庫已回來也不會自己恢復；`/api/health` 仍回 200（它不檢查這兩條連線）。這與設計一致——文件只規範「程序中斷／重開」，未規範「資料庫伺服器重啟、App 不重啟」——恢復方式是重啟 App，與下面的「硬停止恢復」是同一條路徑。
3. **harness 面：**輪詢只容忍連線錯誤、不容忍 5xx；事件（人工改稿、取消）只留在記憶體，崩潰時遺失。

**修訂 A1（續跑，不是重跑）：**「只跑這一次、不重跑」的目的是不挑最好一次；本修訂不丟棄任何已完成輪次，也不重來，而是在**同一份職務檔案**上繼續，因此仍是同一次旅程。
- 重啟 8103（用主工作樹，與計畫中的第 30 輪硬停止同一指令）；產品啟動時恢復那一輪 `active` 的執行。這次**非計畫的強制中斷也成為一次真實的恢復證據**，與第 30 輪的刻意硬停止分開記錄（J3 兩筆）。
- harness 升 v4（工具修補，不改量測規則）：輪詢容忍 5xx（到該輪逾時為止）；事件逐筆寫進 `.progress.jsonl`；`--resume-job-file` 讀回已有的輪次與事件，用 `consultant-turns/current` 找出進行中那一輪（含原句）接續等待，不重送；之後照原旗標完成：晚期更正（≥第 26 輪）、第 30 輪硬停止、最少 45 輪、PDF。第 25 輪的耗時不可與其他輪比較（含中斷與恢復），資料中標 `resumed`。事故前遺失的兩個事件（第 14 輪人工改稿、第 20 輪取消）依產品資料重建並標明「重建」。
- 費用／時間上界不變：累積估算 US$4、自 22:21:58 起 6 小時（至 04:21）；到此 US$0.13。其餘判準 J1–J11 不變；J1 另列「第 25 輪的資料庫事故」一筆，不算旅程失敗也不算通過，依恢復結果如實記錄。

### 接手核對與工作樹整理（2026-10-01）

**本次範圍：**Owner 要求先保全他人做到一半的工作、整理分支與 worktree，再討論下一步。本次只做唯讀診斷與文件整理；未呼叫模型、未啟停服務、未修改產品／harness、未合併或推送分支，未刪除資料。T17／T18 仍未完成。

**23:30–23:35（Asia/Taipei）重新核對：**

- `eval_b`／職務檔案 `2be168b7-a13f-4313-bc28-fa9cbee770fa`：24 個 consultant execution completed、1 個 cancelled、1 個 active；2 個 Memory 批次 completed。正式訪談 49 則、序號上界 49；Memory 2 版、處理上界 44。計數與前人交接相符，但這不是全庫逐筆無損驗證。
- 原第 25 輪 execution 是 `b7e011c1-6090-401c-a753-f0d8585bc4fa`。其 `job_consultant:completed_work` thread 最新 checkpoint 為 `1f1bda86-22cb-6dca-801c-bab70a690695`，保存於 22:57:12，Graph metadata step=28；另有 initial_context／prepared_history。**thread 名稱中的 completed_work 不表示本 Turn 已完成；metadata step 也不直接等於第幾次模型呼叫。**這只證明保存項目存在，尚未驗證能成功續作。
- 308 次外送嘗試，最後准入 22:57:22；其中有 failure code 的 34 筆全為 `rate_limited`。這個分類只涵蓋外送紀錄，不包含另已確認的 DB／HTTP 500／harness 崩潰，不能概括成「本次沒有其他錯誤」。
- `reported_cost_usd` 合計約 US$0.130，是**產品端**嘗試紀錄的估算；員工模擬器直接呼叫 provider，不在這份 SQL 合計內。續跑前須另外核對或保守預留員工端費用，不把此數字宣稱為整次帳單。
- PostgreSQL 55439 的 PID 25700 始於 23:16；8103 的 PID 45876 始於 22:20，仍是 DB 重啟前的後端。8101／8102／8104 也仍在監聽；8100／5173 當時未監聽。未找到命令包含 `simulate_interview` 的存活 Python 程序；未改動任何一個服務。這是時點盤點，之後操作前須重查 PID，不沿用此處 PID 直接停止。
- 本機 `.research-tmp/eval/long-procurement-1.progress.jsonl` 已保留第 1–24 輪的 completed 紀錄，stdout 與之相符；stderr 指向第 25 輪狀態查詢的 HTTP 500。**既有 harness 已逐輪寫入 transcript，缺的是事件即時落盤與續接模式，不是全部進度都遺失。**原資料與 log 留在原處，不因 Git 整理清除 ignored 目錄。

**分支／工作樹責任（接手時基準）：**

| 工作樹 | 分支／HEAD | 處置 |
|---|---|---|
| `S:\caliburn` | `target-rebuild`／`57db0b5f` | 原本僅本頁 A1 未提交；保留原紀錄並提交本次核對與交接路由，後續從此分支繼續 |
| `S:\caliburn-cutover` | `target-cutover-candidate`／`5bccf4fb` | clean；有 6 個尚未合入主施工線的切換提交，包含舊碼退役；保留隔離，不提前放行 T18 |
| `S:\caliburn\.worktrees\professor-architecture` | `docs/professor-architecture`／`c5650c15` | clean；保留教授報告與圖檔，與產品施工分開，不重寫／移除使用者正在閱讀的路徑 |

其餘 archive／歷史分支未因名稱或 upstream 消失而刪除。此處「整理乾淨」指保全待提交成果、釐清各工作樹責任與保持 clean，不表示將未整合成果全部合併或刪除。

**下一切片建議（尚未執行）：**

1. 只補評測 harness 必需的續接：依既有職務檔案／execution 等待原第 25 輪，不建立第二份檔案或再次送入同一句話；續用原 24 輪與事件。第 14／20 輪事件如須由產品紀錄重建，明示重建，不能當作當時完整保存的 harness 事件。以離線反例驗「不重送、不重做已發生事件」。
2. A1 的「容忍 5xx」限已確認服務重啟的有界恢復窗口；保存錯誤，逾界停止，不一律吞掉所有 500 直到 timeout。恢復就緒不能只看 `/api/health`，還須成功讀取原 execution／checkpoint；一般狀態讀取失敗不授權重送輸入。
3. 先補明等待界線：目前 `TURN_TIMEOUT_SECONDS = 2_100`；本頁 900 秒屬於較早的 Q1 manifest，**不能直接套用於這次長旅程或據此宣稱本次違規**。長旅程 manifest 尚未明列單輪及事故後續等的期限，續跑前補明，不能默默重設計時器。整次六小時界線仍從 2026-10-01 22:21:58 起，至 **2026-10-02 04:21:58**；若不再可行，先記停止／變更原因與修訂，再決定續測。產品與員工模擬器費用合併受原 US$4 測試界線控管。
4. 核對以上接縫後，只重啟經確認的 8103 後端，保持同一產品版本與模型，不動 DB、Demo 或其他評測服務。啟動可能自動恢復原 execution 並產生費用；不能當成純健康檢查。續跑如成立，再完成原晚期更正、刻意硬停止、Memory／JD／PDF 檢查；事故恢復與原第 30 輪故障注入分列，不混算通過。

**研究與取捨：**[PostgreSQL 官方 advisory lock 契約](https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS)說明 session 結束會釋放 session-level lock；本案 `PostgresProcessLock.check()` 刻意不重連取回舊所有權。bootstrap 使用 `AsyncPostgresSaver.from_conn_string()`，本機鎖定套件原碼建立並持有一條連線；[LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)提供 checkpoint 保存，不等於所有外部連線自動恢復。此處建議先沿既有 App 重啟恢復，不為這次事故擴建熱重連／重新選主平台；是否另補產品故障提示，待完成必要驗收後按影響判斷。

**驗證邊界：**唯讀 SQL 使用 `default_transaction_read_only=on`，只查狀態／計數及 checkpoint metadata，未讀取或輸出 opaque reasoning。已核本機程序、log、相關接線及官方契約；文件變更檢查差異、連結與狀態，不以此代替產品恢復或 T17 真旅程驗收。

### 續跑修訂 A2：最小 harness 恢復（2026-10-02，新增付費請求前）

Owner 已指示接續上述切片。A2 取代 A1 的 harness 接法，不改產品、Luna 模型、c3 指引、量測規則或 J1–J11；仍是同一份採購旅程，不重新起跑。

- **原進度**：保留 `long-procurement-1.progress.jsonl` 的 24 輪，明示原職務檔案及第 25 輪 execution。續跑前比對正式訪談與 progress 前綴；等待原 execution，即使重新接上時它已完成，也不重送。第 14／20 輪不再執行；事故前缺失事件只能標成事後重建。
- **保存**：既有 progress 仍逐輪追加；新事件即時追加至獨立 `.events.jsonl`。原輸入與 execution 身分留在事件及新 progress；最終報告不存在時不表示前段資料消失。破損或不相符的 progress 停止，不靜默跳過。這些是評測證據，不是產品的第二套執行儲存。
- **等待**：單輪及本次恢復後第 25 輪等待上限沿既有 2,100 秒，後者从續接等待開始計時，標示 `resumed`，不可拿來當原完整耗時。**總截止仍為 2026-10-02 04:21:58 +08:00**，CLI 必須明示原絕對期限；兩者先到者停止。期限到／查詢失敗／timeout 不授權重送未確認結果。
- **重啟容錯**：只在本次已知恢復及計畫第 30 輪重啟後，允許最多 90 秒的連線失敗或 HTTP 500／502／503／504；第一次成功讀到原 execution 即結束窗口。其他 HTTP 錯誤、一般執行期間 5xx 均停止並保留錯誤；不把 `/api/health` 的 200 當成 checkpoint 可用。
- **付費界線**：原 US$4 上界不提高；目前產品 ledger 為 US$0.129711115，不含員工模擬。以現有已固定的 Luna pricing record 作估算、保守預留 US$1 給全部員工模擬（含前段未保存 usage），產品 ledger 接近 US$3 就停止加送並核對，不宣稱 provider 帳單保證。這是本次評測操作界線，不新增產品金額 gate。執行中持續核對外送數、ledger 及 elapsed，若預留不再足夠先停止。
- **服務隔離**：只以精確 executable／script／port 核對並重啟 8103；新 log 以時間戳命名，舊 log 不覆蓋。不重啟 PG，不改 8101／8102／8104／Demo。忽略目錄中的 `eval/tools/restart-longrun-8103.ps1` 保存本機故障注入指令；不作通用程序管理服務。
- **剩餘旅程**：原 ≥26 輪晚期更正、第 30 輪故意硬停止、45–50 輪、Memory 與 JD 來源、PDF 均保留；沒有因恢復測試而放寬品質判準。第 25 輪環境事故與第 30 輪注入分開報告。

**實作與離線證據（尚不等於真旅程通過）：**`scripts/simulate_interview.py` 增加明示 job/execution 的續接；評測 progress／event 小工具拆至 `scripts/interview_progress.py`。Red 為 7 failed／15 passed（缺續接與有界重啟方法）；Green 為 24 passed，包含新增的 timeout 不重送與絕對期限檢查。後兩項為補充回歸，不冒稱先 Red。Ruff check／format 與原直接執行 CLI `--help` 通過；Windows sandbox 的 pytest 暫存目錄權限錯誤另以授權的專案內獨立暫存路徑重跑，不算產品 bug。獨立審查及真續跑结果後補。

**參考契約：**依 [HTTPX exception hierarchy](https://www.python-httpx.org/exceptions/) 區分 transport 與 HTTP status error，並以本機鎖定的 `httpx2` MockTransport 驗證实际行為；[官方 transport retry](https://www.python-httpx.org/advanced/transports/) 不把任意 503 視為自動安全重試。本次只對唯讀狀態查詢加有界窗口，POST 不因此重送。全程期限採 [Python asyncio.timeout](https://docs.python.org/3/library/asyncio-task.html#asyncio.timeout)，不重造排程器。

**審查修正：**獨立 reviewer 找到真實開場角色是 `app`，原測試誤用 consultant；另指出重試在 deadline 後仍可能再送，以及 Windows 預設編碼下測試讀 UTF-8 失敗。依實際 persistence 接線更新 fixture／前綴驗證；每次重試前查剩餘期限，該次查詢亦受 `asyncio.timeout` 約束；測試明示 UTF-8。先重現 4 failed／7 passed，再修至 harness＋既有品質檢查 **25 passed**（不依賴 `-X utf8`），Ruff 通過。沒有因此修改產品來源或增加 DB 熱重連機制。

### A2 實測結果（2026-10-02）：原旅程完成 45 輪

**結論：同一份職務檔案已完成原長旅程，停止新增付費請求。**保留前 24 輪，續完第 25–45 輪，於 **00:39:31（Asia/Taipei）**取得最終 JSON 與 PDF；沒有換模型、重跑選最好結果、人工補正模型產物或修改產品 Prompt。`40f7c1f9` 只修評測 harness／測試／證據；產品仍沿原 `c1066873` manifest 的 Luna／high、c3 指引及當時接線。原 22:21:58 起算至完成約 2 小時 18 分，包含環境事故與接手時間，**不是純訪談耗時**；未延長 04:21:58 截止或 US$4 上界。

| 最終可核對項目 | 結果 |
|---|---|
| 職務檔案／隔離範圍 | `2be168b7-a13f-4313-bc28-fa9cbee770fa`；原 `eval_b`、8103，沒有新建另一份旅程 |
| 執行 | 45 個完成 A、1 個刻意取消 A、2 個失敗 A；3 個完成 Memory。最終無 active／paused，沒有 open Memory 批次 |
| 正式訪談 | 91 則：開場1、員工45、顧問45。取消及兩次失敗原輸入的正式訪談計數均為0；重送後各只保存一次 |
| JD | 正式修訂 `7f8b83a4-5a82-4320-a080-131f2503e8f0`；4 職責、16 任務（含1人工測試任務）、14 成果、28 要求；知識技能、獨立協作對象及條件集合均為0，不因此推定每項都必須補填 |
| Memory | 3 版處理至2、44、82；最新 `aa08e56c-3d73-4df6-85ec-e58751daf8e2` 於00:32:46發布，含13情境、2理解。正式前沿91，尾段83–91尚未整理；不是宣稱全部訪談已整理 |
| 來源 | 81筆全部直接引用訪談，81筆原文皆成功讀回；**10筆依據仍為 `needs_recheck`，涉及9個JD目標** |
| PDF | 正式路徑匯出4頁 A4、946,590 bytes；逐頁 PNG 目視及85個非空成品文字欄位核對，見下方界線 |

#### 中斷與恢復：安全結束後重送，不冒稱原 execution 無縫接續

| 事件 | 原執行與實際結果 |
|---|---|
| 第20輪取消（前段已發生） | `42583c7b-6d81-4cfe-947f-9cff7d6f2c1d` 為 cancelled，原輸入未進正式序列。事件依 DB 重建，沒有再次注入取消，也沒有補造當時的精確事件時間 |
| 第25輪環境事故 | `b7e011c1-6090-401c-a753-f0d8585bc4fa` 在重啟時已超過原23:26:08執行期限；保存錯誤為 `BudgetExceededError`。確認 failed 後才以原句新送 `fa2452e6-c5d2-4452-aa65-f0980514b192`，完成並取得員工序號50 |
| 第30輪計畫硬停止 | `bc1b096a-cea9-4bb7-90f3-2e65953d08f0` 重啟後因未確認的既有模型嘗試，以 `PriorModelAttemptError` 安全結束。確認 failed 後才新送 `233826d8-9950-450f-91af-b76c23e02cd0`，完成並取得員工序號60 |

兩次失敗 JD candidate 均為 `discarded`；45個完成 A 的 candidate 均為 `adopted`。取消／失敗的原輸入被 Memory 引用的筆數也是0。這符合首版「能接續則接續，不能則安全退出」的界線；**不證明已送出但未可靠保存的模型結果可以取回**，也不把查詢500或沒有回應視為可以重送。第25輪 progress 的70.3秒只量重新接手後的等待／重送；不代表原 Turn 從22:56起的完整耗時。沒有重啟 PG 或操作其他服務。

#### 原 J1–J11 對照

| 判準 | 本例判定與證據限制 |
|---|---|
| J1 完成度 | **限定通過**：45個邏輯訪談輪次最後均完成，無卡住；上述2個原執行失敗明列，不抹成零失敗 |
| J2 取消 | **通過**：取消輸入無正式序號，重送後未重複形成正式訪談 |
| J3 硬停止 | **通過安全收尾分支**：原執行安全終止後新送，未把候選當正式資料；沒有宣稱原執行 completed |
| J4 人工改稿 | **通過**：第14輪人工目的及任務原內容保留；人工任務仍未歸屬，不把它當 AI 自主產出的品質證據 |
| J5 更正 | **通過**：半年取代每季；依T26–27更正為未達五萬本人、超過五萬未達一百萬主管、一百萬含以上副總，正好五萬保留未確認。未交貨／比價等其他工作保留；新 Memory 也吸收更正 |
| J6 引用 | **達原粗查門檻，非全部已核對**：76個「事實×JD項目」marker 檢查為0.99，唯一標記人工核對後是「寄信／電子郵件」同義誤報；81個來源可回讀。實際已填職稱／主管均由訪談2支持；單位T18說不確定，留空不是錯引。人工目的沿原引用仍待核對，不能以來源可讀視為已確認 |
| J7 Memory | **本例發布與尾段界線成立**：3批皆完成，最新處理至82，只有83–91這一段未整理尾端，無失敗／卡住批次；未強制多跑一批求齊頭 |
| J8 Context | **觀察部分成立**：A自然輪前壓縮後繼續使用較早的採購、交期、核准及半年評鑑事實。各角色計數見下方；B1／B2未自然觸發壓縮，未逐一重驗所有模型請求或完整原生 items，不因此勾T16 |
| J9 PDF | **通過本例可見成品**：4頁可讀、無裁切／重疊／缺字；85欄經明示文字正規化皆可找到。不宣稱複製／搜尋逐字無損 |
| J10 無捏造 | **內容審讀未見違反，未知測項有限**：不替員工承擔未確認的建檔、ERP測試細節或新人考核。付款條件的決策依據及關稅稅則沒有被補造，但也沒有直接問出這兩項未知，不能稱兩個指定反例皆已跑到 |
| J11 限流 | **通過本例等待分支**：99個 rate_limited 嘗試後繼續，沒有因限流最終失敗的輪次；第25／30輪終止原因另列，不混作 provider 失敗 |

唯一引用標記是「每週一整理未交貨清單；對交期落後的項目以電話或電子郵件催貨……」，其來源訪談20原文明說「打電話或寄信催貨……回報生管預估的新交期」。原計算0.99保留，沒有改 rubric 後重跑成100%。`schedule` 的「已說未寫」marker 也需人工解讀：員工T20明說不確定其他出差安排，已確認的十一月陪同稽核則在 JD；不能把 persona 裡尚未說出口的加班／出差頻次當作模型已知漏寫。

#### 仍需保留的品質與覆蓋限制

1. **待核對不是錯引的同義詞，也不是已完成核對。**10筆都是既有引用隨 JD 正文修訂而保留的待核對狀態；原訪談不可改寫，本例沒有 Memory 來源換版。包含人工目的、Excel比價／績效／談判成果、主檔整理、稽核任務／成果、緊急採購及補貨任務。`carry_source_references` 刻意在目標內容改變時保留 `needs_review`；本次不由驗收程式代替 A 解除它。需沿已存在的明確核對工具／指引處理，不能只隱藏徽章。
2. **本例沒有自然驗到 JD→Memory 換版鏈。**81筆全部是原始訪談依據；B1／B2已發布並被後續輪次使用，不等於 A 曾為 JD 建立 Memory 引用並處理其 diff。既有[受控來源換版](#2026-10-01同一合成案例的純來源換版接續)證據仍有效，但不冒充本次自然觀察。
3. **覆蓋與精簡仍有限。**主要採購任務集中14項要求，停線通知在正文／成果／要求重複；回簽追蹤、每週行情及5%通知、降本、外語溝通等 persona 面向未被問出。這是探索不足，不是已知原話消失。T45員工說「已涵蓋主要工作」不能單獨證明完整覆蓋；沒有為了塞滿欄位補造K／S。
4. 獨立唯讀 reviewer 已按工作分析與 JD 指南審讀至最終45輪；確認T43報關分工與T44不負責考核均有原話支持，與主代理核對一致。這不是人類領域專家校準或普遍成功率估計。本次不再重跑長旅程、擴建恢復平台或即席改 Prompt 求通過。

#### 容量、時間、費用與 PDF 驗證層級

- 固定資料抽查：保存的 `binding` 顯示T41／42沿第二版Memory，T43／45沿新發布第三版；各選定Turn只見單一綁定，訪談讀取上界分別81／83／85／89。這證明後續Turn取得新版及各自邊界，不把T42執行中的發布改成T42中途換版，也不宣稱已稽核每個request的所有內容。
- provider 保存的最大 token **計數視窗**：A **136,061**、B1 **42,259**、B2 **48,783**；包含輪前檢查，不能全部稱為實際生成輸入。7次 compaction 外送中，1次取消期間未確認結果、1次被限流、5次有返回用量；後5次落在T20重送、T33、T41、T44、T45。不是7次成功採用。B1／B2和160K中途保險本次未自然觸發，保留為未觀察。
- 539次外送：290 model、242 token count、7 compact；99次 rate_limited（98 model、1 compact），占18.4%。61個logical request曾限流，最長同請求連續6次；其第一次至最後一次嘗試最大230秒，**不是純等待時間**。按保存的准入／下次重試時間差，最大約58.44秒，亦不是高精度排程延遲量測。
- 有耗時且排除T25／T30的42個普通輪次：平均71.2秒、中位約54秒、最長240.1秒；T45收尾無獨立seconds欄位，不補造。多角色並行時限流明顯，仍需按實際性能取捨，不因本次完成就稱快速。
- 產品 ledger 累計 **US$0.353573150**；員工模擬不在此數字內，沿A2保守預留US$1，不當成完整帳單或漏記費用為零。沒有突破原測試停止界線，也沒有把金額攔截加回產品。
- 本檔案 checkpoint blobs＋writes 的序列化 payload 合計約 **402,359 KiB（393 MiB）**，不是整個DB磁碟用量，也未證明有洩漏。保留為容量觀察，不為這次驗收新增GC／存儲平台。
- PDF用 Poppler 渲染4頁逐頁查看，並以 pypdf 對85個非空成品欄位核對；先去空白仍有53欄不完全相等，沿既有T13文字層限制，明示使用 NFKC、`⻑`→`長` 和空白正規化後皆可找到。沒有改 PDF 或 JD 原文；不把此比對宣稱文字抽取逐字無損。

**保存與下一步：**最終JSON、逐字稿、事件、PDF及4頁PNG留在本機 ignored `.research-tmp/eval/long-procurement-1*`；後端8103與PG55439保留供唯讀查看，harness已結束。主線沿 `target-rebuild`；教授報告與切換候選 worktree 原樣保留，沒有 merge／push／切換。T16–T18仍未勾：先用本次證據核對剩餘 gate，若要改善分析效果，優先診斷「改稿後既有依據未明確核對」及探索／精簡，不再從零跑另一份長訪談。本次結果不擴張後續付費範圍。

| 本機原件（`.research-tmp/eval/`） | SHA-256 |
|---|---|
| `long-procurement-1.json` | `d20d0542cb0e736559c5beab18fa821bb0e460009f413b08f60ba4874b46eac8` |
| `long-procurement-1.progress.jsonl` | `e16746046ada5f42722334a97f04ca02b7b7599246490c8f8ba7f40ca77146d5` |
| `long-procurement-1.events.jsonl` | `faef5a53f8a56666f3cea2eeafc3dabe00ed8dd58713428cc0bde9fcde8eccae` |
| `long-procurement-1.pdf` | `335a4762e140a446b3b728948a0257a05c5cb85708a51a3f6f8d024022f9c451` |
