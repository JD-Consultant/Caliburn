# 可驗證任務與交付責任

- 狀態：**T01–T13、T15 已完成；T14、T16–T18 未完成。2026-09-30 晚 Owner 以新 Goal 恢復施工（先前為純文件推送後的安全暫停）**。T08 已有四輪真模型訪談、三批背景 Memory、同輪暫停／重開／接續及正式 PDF 證據；不等於 T16／T17 長訪談與完整產品驗收。最新安全點、T06／T07 收尾驗證及 T08 已定位缺口見[暫停交接最新補記](evidence/2026-09-30-pause-handoff.md#最新補記文件推送與再次安全暫停)，接續不重置。每項遵守[SDD／TDD](../../implementation/development-standard.md)。以下交付須依實際證據判定，不由規劃名稱推導已存在。
- 勾選表示相應層級實際驗證通過，不是「寫了文件」。每項完成後補實際命令、結果、證據連結及有授權的 commit。
- **恢復範圍 successor（2026-09-30）：**T06／T08／T11／T12 依[共用執行 §6.4](../../specs/2026-09-27-shared-agent-execution-and-state-design.md#64-首版恢復範圍能續作不能續作則安全退出)保留核心接續與安全退出；罕見原件遺失的全面追蹤／同工作再准入不再列為首版阻擋條件。已保存的結果及資料安全測試不刪減；本次最外層收尾證據見 [T12 §6](evidence/t12-consultant-process-recovery.md#6-首版恢復減法與最外層失敗收尾2026-09-30)，尚未勾選整項任務。
- 每項「Red」為先寫的代表反例，非唯一測試；完整覆蓋見[驗證對照](../../implementation/verification-plan.md)。同一任務可拆多個小提交，但不脫離依賴與非目標。

## T01 工具鏈、契約生成與可測邊界

- [x] T01；依賴：無。
- **證據（2026-09-29）：**health schema 原失敗已修；乾淨 uv／pnpm 安裝、20 項後端測試（含真 PG 跨程序 saver）、1 項前端測試、lint／型別／格式／生成／建置及實際啟停通過。精確命令、版本、授權、限制及後續接縫見[實測紀錄](evidence/t01-foundation.md#3-修正後實測2026-09-29)。基礎程式與此證據共同提交；根正式入口不變，尚未做產品／真模型驗收。
- **同日補強：**Owner 補充的 code 寫法規範已連入施工流程；命名／非同步／typed lint 的反例與回歸見 [evidence §5](evidence/t01-foundation.md#5-程式撰寫規範與自動檢查補強2026-09-29)，不重新勾選或重做全部 T01。
- **契約：**[程式組織](../../implementation/code-organization.md)、[選型](../../implementation/technology-decisions.md)、[契約策略](../../contract-strategy.md)。
- **程式／交付：**新 API package、Web build、fresh PG 測試配置、lint／typecheck、契約生成與 import 邊界測試；新路徑 README 說清目標狀態。先只做 health／最小 schema round trip，不生全部空模組。
- **先驗：**記實際穩定版本、license、Windows 支援及 lock；fake transport 能構造原生 SDK 回應，PG saver 可初始化。設定／生成任務不假稱 TDD；schema 非法 payload 與越界 import 應有失敗測例。
- **完成：**乾淨環境可安裝、build、單元測試、codegen:check；未設定模型金鑰也能離線跑；根現行入口不變。
- **不做：**讀舊 `.env`、重用舊 venv／DB、刪 ignored 目錄、開真模型、替代產品資料保留政策。

## T02 職務檔案、正式訪談與執行准入

- [x] T02；依賴：T01。
- **證據（2026-09-29）：**檔案／開場保存 `e3889e28`、輸入／准入 `a630f957`、正式化／原話查詢 `f51d6ccf`、建立／隔離 UI `598daff2`；第五切片補列表改名及其重送／競爭，後端 **158 測試通過**（117 項真 PG）、前端 **15 項**、真 PG 瀏覽器 **5 項旅程**。T02 底層與檔案 UI 範圍完成；完整 A 完成、Graph 控制／回退仍待 T08，不能視為 AI 已可用。詳見[切片證據與下一步](evidence/t02-job-files-and-interviews.md#9-第五切片列表改名與-t02-完成2026-09-29)。
- **契約：**[產品概念](../../product-concept.md)、[來源範圍](../../specs/2026-09-27-memory-read-and-source-navigation-contract.md)、[資料交易](../../architecture/persistence.md)。
- **程式／交付：**`features/job_files`、`interviews`、`executions`；建立／改名 API、列表／選取 UI；開場正式序號 1，原輸入保存及受控正式化介面；schema migrations。完整 A final 在 T08 接，不新增假正式對話入口給 UI。
- **Red：**重送同一命令兩次、跨檔案讀取、取消輸入占正式序號、兩個 runner 同檔案准入、另一檔案無法前進。
- **完成：**V01／V02／V28 對應底層部分真 PG 通過；原話不可改寫；接受輸入不等於正式資格；同檔案唯一 A、獨立 Memory 資格。
- **不做：**使用者帳號平台、全局單檔鎖、A 控制 UI、背景工作佇列框架。

## T03 關聯式 JD 與人工編輯垂直切片

- [x] T03；依賴：T02。
- **進度（2026-09-29）：**profile 正式保存／人工 API `52b55951`、基本資料人工 UI `32e3ea5e`、職責集合後端 `f8aca13f`、任務／成果／要求後端 `129f60f1`；第五切片完成職責／任務人工 UI、局部明細編輯、排序／跨組移動、刪職責保留任務，以及單一固定修訂的組合讀取。後端 269 項（193 項真 PG）、前端 37 項及真 PG 瀏覽器 12 項通過；範圍與限制見[第五切片證據](evidence/t03-relational-jd.md#7-第五切片職責任務人工-ui-與同版讀取2026-09-29)。K／S 等集合與關係、候選及相應 UI 仍未完成，不先勾選 T03。
- **續進度：**第五切片已提交 `cb6e8e9f`；第六切片完成共用知識／技能及任務關係後端、固定歷史與原操作恢復。後端 **312 項**（213 項真 PG）、前端既有 37 項通過；[第六切片證據](evidence/t03-relational-jd.md#8-第六切片共用知識技能與任務關係後端2026-09-29)。知識／技能 UI、協作／條件及候選仍待完成，不將人工端點直接當成模型工具。
- **第七切片：**第六切片已提交 `536ea774`；第七切片接上知識／技能及任務關係人工 UI，共用同版讀取、原基底與待確認命令。後端 **312 項**、前端 **44 項**及真 PG 瀏覽器 **14 項**通過；[第七切片證據](evidence/t03-relational-jd.md#9-第七切片共用知識技能與任務關係人工-ui2026-09-29)。
- **第八切片：**第七切片已提交 `2bf929e6`；第八切片完成協作對象／共通條件人工後端、固定修訂與重送恢復，後端 **381 項**（258 項真 PG）、前端既有 **44 項**通過；[第八切片證據](evidence/t03-relational-jd.md#10-第八切片協作對象與共通條件後端2026-09-29)。
- **第九切片：**第八切片已提交 `ad6211af`；第九切片 `f9d710eb` 接上協作／條件人工 UI 與同版集合讀取。受影響後端 **166 項**、前端 **49 項**、真 PG 瀏覽器 **16 項**通過；獨立靜態審核未找到阻擋缺陷。[第九切片證據](evidence/t03-relational-jd.md#11-第九切片協作與條件人工-ui2026-09-29)。
- **完成證據：**第十切片完成全部 JD 集合共用的候選／固定正式稿隔離、原結果、位置回退與交易內採用；後端全套 **405 項**通過，新增 24 項真 PG。獨立靜態審核未找到阻擋缺陷。[第十切片證據](evidence/t03-relational-jd.md#12-第十切片候選位置與-t03-完成2026-09-29)。T03 的人工垂直切片及候選底層完成；T07 來源／模型工具、T08 完整 A、T09 候選 UI、T12 故障 gate 均未冒充完成。
- **契約：**[JD 欄位指南](../../specs/2026-09-09-jd-field-and-writing-guide.md)、[JD 工具能力覆蓋 §2.1](../../specs/2026-09-29-jd-model-tool-contract-review.md#21-欄位與操作覆蓋)、[資料接線](../../implementation/data-and-contracts.md)。
- **程式／交付：**`features/job_description`、HTTP DTO／mapper、`jd-editor`；profile、職責／未歸屬任務、成果／要求、共用 K／S 與關係、協作／共通條件；候選及固定正式修訂機制。
- **Red：**刪職責誤刪任務、成果與要求錯配、已用 K／S 被刪、跨任務明細操作、後段 change 失敗留下前半修改、活躍 A 時人工寫入。
- **完成：**人工 CRUD／移動／排序可用，V16／JDT-02／05 底層通過；正式／候選不同投影；同一命令重入返回原結果。
- **不做：**Markdown 整份 JD、富文字編輯器、來源由文字相似自動推論、姓名寫回 JD。

## T04 Memory 可變候選、不可變修訂與快照

- [x] T04；依賴：T02。
- **完成（2026-09-30）：**固定來源、候選 CRUD、分層權限、回交／回復位置、原結果、固定 map/read 與原子發布已驗。全後端 545 passed；審查補上 no-work 重入後，受影響 43 passed。接線及 schema 見[保存接線](../../implementation/memory-storage.md)，精確層級見[實際證據／未驗邊界](evidence/t04-work-memory.md#4-第四切片候選交接位置與原子發布)。未交付模型工具／diff／B1／B2 真執行；這些是 T05／T10／T11，不把本項完成當完整 Memory 產品可用。
- **第二切片（2026-09-30）：**第一切片 `5c5b09b8`；接著完成本批固定員工來源 F、正式來源身分查詢與必處理區間的真 PG 驗證。[來源邊界證據](evidence/t04-work-memory.md#2-第二切片正式來源身分與-memory-固定範圍)。這不是批次持久化／候選／發布完成，T04 仍未勾選。
- **第三切片（2026-09-30）：**第二切片 `acc5e85e`；新增固定物件修訂、正文重用與不可變來源關係，SQL 拒絕歷史改寫、封存後追加及半套提交。[固定修訂證據](evidence/t04-work-memory.md#3-第三切片固定物件修訂與正文重用)。尚未交付候選 CRUD／位置、角色資格及整版原子發布，不把 storage 當作可用 Memory Agent。
- **第四切片（2026-09-30）：**接續 `28397311`／`566a3529`，完成前述待接保存路徑；前兩行「尚未」是該切片當時狀態。獨立審查發現已涵蓋要求的完成結果無法重入，補反例並修復，沒有新建空批次／快照或第二套收據。
- **契約：**[資料保存 §2–4](../../architecture/persistence.md)、[B1／B2 生命週期](../../specs/2026-09-25-b1-b2-information-gap-lifecycle.md)、[凍結接線](../../implementation/data-and-contracts.md#3-memory可變工作稿與固定快照不是兩個相反模型)。
- **程式／交付：**`features/work_memory` 的候選 CRUD、位置／階段快照、發布及固定 map／read；原操作結果與同 transaction 修改；schema 圖及 migrations。
- **Red：**相同物件不同引用路徑得到不同修訂、修改歷史、只改下層引用卻沿用上層舊修訂、回改舊文字冒充原修訂、刪情境破壞歷史。
- **完成：**V12／V13／V27 底層通過；未變修訂重用；候選綁定跟隨 identity、刪情境解除候選入邊；空來源合法；原子發布確認遺失可查原結果。
- **不做：**B2 逐引用確認、Git delta／event sourcing、正文內容定址去重、Memory 使用者 UI。

## T05 Memory 讀寫工具與唯一 V4A

- [x] T05；依賴：T04。
- **完成證據（2026-09-30）：**V4A `3dc82ff7`、讀取 `40dc7d7c`，第三切片接上 scoped create/update/delete、原命令 prepare/execute、多欄共同採用與真實效果回傳。受影響 unit／contract／真 PG **518 passed**；含提交確認遺失、改名／重用、過時候選與歧義反例。獨立審查發現 diff 分行不一致，先 Red 再修正。詳見[第三切片與未驗邊界](evidence/t05-memory-tools.md#4-第三切片受限寫入與原操作接續2026-09-30)。完成的是 T05 元件及 V19 確定性層；V20 的 JD 下鑽與真模型 gate 仍屬 T07／T16，未宣稱整項 V20 通過。T06 持久接續、T10 角色／交接 diff、T16 provider 仍未完成。
- **契約：**[共同工具規範](../../specs/2026-09-27-agent-tool-contract-design-research.md)、[讀取](../../specs/2026-09-27-memory-read-and-source-navigation-contract.md)、[更新](../../specs/2026-09-27-memory-object-update-tool-contract.md)；修改語意時須完整讀相應章節。
- **程式／交付：**schema、角色可用 handlers、Memory 投影與受限 V4A adapter；沿既有研究定位 parser／helper，鎖來源及 license。
- **Red：**零／多處精確或近似匹配、兩個相似段落、multi-hunk 後段失敗、正文外 path 操作、跨層越權、title 改名重用後原 operation 重入。
- **完成：**V19／V20；只唯一合格定位才全部寫入，多處拒絕並給可改進線索；來源不進 body；map／正文／來源按需讀，不露 scope／版本讓模型填。
- **不做：**filesystem shell tool、泛用 patch engine、為省回傳丟掉模糊匹配的實際修改位置；尚未跑 provider 不能宣稱 strict 已通過。

## T06 共用原生模型／工具執行機制

- [x] T06；依賴：T01。
- **完成（2026-09-30 恢復後）：**共用原生模型／工具執行機制已逐條對照 Red 與 E01–E04（框架部分）、E11／E15 的既有測試，見 [T06 §21](evidence/t06-agent-execution.md#21-任務完成對照2026-09-30-恢復後)；補上任務要求但一直缺的**真 API compact 協定預檢**（5 次 HTTP、零重試，遠端接受 compact 視窗並可續作，[§20](evidence/t06-agent-execution.md#20-真-compact-協定預檢2026-09-30-恢復後)）。完整後端 **1847 passed、2 skipped**（跳過的是需字型的 PDF 渲染，歸 T13）。**不含**：A 控制／完成（T08）、B1／B2 調度（T10／T11）、跨程序故障矩陣（T12）、大視窗 compact 延遲與費用及帳單核對（T16／T17）；Owner 首版恢復 successor 已把「未明 attempt 的 production 再准入」移出必做，共用接縫保留未接線。以下為各切片的歷史紀錄。
- **2026-09-30 金額減法：**Owner 確認正常產品不設金額 gate、付費驗證保留 manifest 限額；沿既有共用 owner 調整，保留容量、次數、deadline 與恢復。接線與實際測試見 [T06 §19](evidence/t06-agent-execution.md#19-產品移除金額攔截與按請求計數預留2026-09-30)，不據此勾完整 T06／T17，不宣稱 Demo 已遷移。
- **第一切片（2026-09-30）：**接續 T05 寫入提交 `d87b3c86`，實作原生回應原件／重送投影、phase／多 call 路由及對應配對。獨立審查後補空白 final／compact 保留 user 反例；Unit／contracts＋真 saver 新程序 **413 passed**。目前只是元件與正常保存往返，沒有宣稱 E01–E04 整體、完整 Graph、費用／取消或 provider 已驗收。[研究、反例及下一步](evidence/t06-agent-execution.md)。
- **第二切片（2026-09-30）：**承接 `5cfbb1da`，單一原生模型／有序工具 Step、官方 serializer 明確 allowlist，接上實際 Memory 候選寫入與跨程序 saver。公開入口統一 sync／有界呼叫／恢復准入；模型保存故障／確認遺失、部分工具恢復與元件集合 **452 passed**。雙保存失敗的官方補存已有能力反例；正式 supervisor、完整 loop、預算／compact 與 provider 仍未完成。
- **第三切片（2026-09-30）：**承接 `a52d76d9`，官方直連 SDK 關閉隱含 retry／redirect，count／create 共用固定 payload；新增不洩漏原文的錯誤分類。Unit／contract **469 passed**，獨立複核 redirect P2 已修；[第三切片證據](evidence/t06-agent-execution.md#3-第三切片直連請求與安全失敗分類)。持久額度、完整 loop、串流與 provider 仍待交付，T06 不勾選。
- **第四切片（2026-09-30）：**承接 `a48b39a1`，executions owner 固定 policy／每次外送預留，原 attempt 重入不給重送許可，未知成本不歸零，取消後可記帳但不授權採用。Unit／contracts＋相關真 PG／新程序 **503 passed**；[額度證據及未接線邊界](evidence/t06-agent-execution.md#4-第四切片不可重置的工作額度與外送預留)。尚未將元件接成完整 HTTP／Graph supervisor，T06 維持施工中。
- **第五切片（2026-09-30）：**承接 `6b0eb918`，原 R／operation seed 在保存故障時交回公開恢復路徑；核原位置／資格後補存或承接，不重新推論、不覆寫後續工具結果。新增真 PG 取消／writer 替換及原交易不跨模型 I/O；受影響 **515 passed**，獨立複核 P2 已修。[本切片證據與限制](evidence/t06-agent-execution.md#5-第五切片原-r-保存失敗的公開恢復與工作資格)。完整外送 supervisor、loop／compact／控制與 provider 仍待交付。
- **直連預檢準備（2026-09-30）：**承接 `44828016`，新增固定兩次生成的合成協定腳本及[批次 manifest](evidence/t06-agent-execution.md#6-第六切片有界直連協定預檢)。指定檔案缺 `OPENAI_API_KEY`，於外送前停止，HTTP／模型費用均 0；不以第三方 key 替代。靜態檢查通過，遠端 gate 待憑證，不阻止其餘 T06 施工。
- **第七切片（2026-09-30）：**承接 `946c663f`，checkpoint 固定完整 request／logical ID，首次 HTTP 前提交預留；原 R／attempt 先保存，後做可恢復結算，再按資格派工具。真 PG 驗准入／記帳確認遺失、取消與零重呼；受影響 **525 passed**，獨立複核取消補存 P2 已修。[實測與未驗範圍](evidence/t06-agent-execution.md#7-第七切片固定請求與保存後計量)。費率／容量、更多 attempts 的 supervisor、loop／compact／角色控制仍待交付，T06 不勾完成。
- **第八切片（2026-09-30）：**承接 `082d4d5f`，同一 Graph 接上有界多模型 Step，完整原生歷史與有序工具接到 final；原限額／request 恢復不重置。獨立審查的初始 checkpoint P2 已以 Red 修正；真 PG 新程序承接第二個 R、零重呼，受影響 **534 passed**。[本切片與限制](evidence/t06-agent-execution.md#8-第八切片有界多-step-接續)。容量／compact、重試 supervisor、角色控制與 provider 仍未完成。
- **第九切片（2026-09-30）：**承接 `62e463fe`，count 接既有外送額度、原 request 與 checkpoint；同次恢復不重計、容量超限不生成、完整 Step 間達272K明確交回 compact 需求。[證據與限制](evidence/t06-agent-execution.md#9-第九切片固定計數與容量准入)。compact 執行／控制、重試及真 provider 仍未完成，不勾 T06。
- **第十切片（2026-09-30）：**承接 `00c3449b`，完整 C 先保存再結算／採用，中途接續不重貼輸入、重新計數、不反覆壓同一視窗；compact 共用外送額度與 canonical payload。真 PG 新程序驗 C→父圖交接中斷不重壓，審查取消補帳 P2 已修並複核。[證據與未完範圍](evidence/t06-agent-execution.md#10-第十切片完整-c-安全採用與中途接續)。輪前準備／角色控制、retry與provider仍待交付，T06不勾完成。
- **第十一切片（2026-09-30）：**承接 `4266ee0d`，沿既有 execution owner 保存暫停要求，完整 Step 後原生 interrupt 停妥，明確原 interrupt 續作；真 PG／新程序驗普通重開不發模型，取消及舊 writer 不得復活。[證據與未接線交界](evidence/t06-agent-execution.md#11-第十一切片完整-step-暫停與原生續作)。尚非完整 UI／控制調度，T06 不勾完成。
- **第十二切片（2026-09-30）：**承接 `0641beff`，沿原 saver／recovery 補回仍在程序內的完整 count，不另計數、不回退後續結果，取消仍拒絕採用。真 PG 重開與原預算接線見[證據與限制](evidence/t06-agent-execution.md#12-第十二切片原計數結果補存)。不是遠端結果備份／完整重試 supervisor，T06 仍施工中。
- **第十三切片（2026-09-30）：**承接 `9d38e038`，create／count／compact 共用持久 failure、Retry-After 與原工作預算；只有已核明故障可新准入，保存／結果不明不盲送。獨立審查的安全錯誤出口、例外鏈及耗盡前停止等待均補反例修正。[研究、回歸與未完邊界](evidence/t06-agent-execution.md#13-第十三切片共同外送的持久有界重試)。輪前準備、未明 attempt 調度、角色整合與真 provider 尚未完成，T06 不勾選。
- **第十四切片（2026-09-30）：**承接 `bbe55f59`，輪前歷史計數／門檻／Agent 意圖共用原 C 保存流程；未壓縮決定亦可恢復，原 count／C 不因保存故障重送。[證據與限制](evidence/t06-agent-execution.md#14-第十四切片輪前歷史的門檻判斷與可恢復準備)。合法基底跨工作選用、角色資料綁定與取消回退尚未接完，不宣稱 T06 或產品安全點完成。
- **第十五切片（2026-09-30）：**承接 `62d547f9`，沿 executions 管理 reference-only 歷史資格，原生完整窗口仍由官方 saver 保存；取消後新工作重用輪前基底、不帶被取消輸入、不重壓。[證據與限制](evidence/t06-agent-execution.md#15-第十五切片跨工作合法歷史與取消後基底)。角色固定資料、正式業務完成及背景回退調度仍待接線，T06 施工中。
- **第十六切片（2026-09-30）：**承接 `cc564072`，借既有 Tenacity 為原 R／C／count 的 typed handoff 接有限保存重試；沿原 thread 核對，不重送原模型請求、不重設持久外送預算。[證據與限制](evidence/t06-agent-execution.md#16-第十六切片原件補存的有限自動恢復)。程序遺失後的未知 attempt、角色調度及真 provider 仍待接線，T06 未完成。
- **第十七切片（2026-09-30）：**承接 `7c4a383d`，固定官方文字費率與模型綁定接原 budget，分算 cache read／write 與長 context，未明 usage 保留預留；受影響 **755 passed**。[證據與界線](evidence/t06-agent-execution.md#17-第十七切片固定費率與原-usage-結算)。是 usage 成本估算、非已核 provider 帳單；角色組裝與未知 attempt 調度仍未完成，不勾 T06。
- **契約：**[共用執行](../../specs/2026-09-27-shared-agent-execution-and-state-design.md)、[Agent 接線](../../implementation/agent-execution.md)。
- **程式／交付：**`agent_execution`、Responses／saver adapter、typed State／serializer、窄工具 handler 介面、單一 retry／計量責任；先使用測試工具與 fake Responses，不依賴產品工具完成。
- **Red：**R 已保存卻重呼模型、只存 output_text、兩工具平行／配錯 call、公開文字誤判 final、serializer 丟 opaque／phase、role namespace 污染、SDK 隱含 retry。
- **完成：**E01–E04 對應框架部分、E11／E15 計量與 compact mock；真 PG 新程序 round trip；零／一／多 call；`sync` 邊界先 R 後工具。
- **提前消除遠端風險：**準備獨立全合成 preflight，依[本 Goal 有效授權](README.md#3-狀態與施工順序)及 T16 同樣的資料／費用 manifest，先驗少量原生接續、strict、compact 與 token count，不需逐次請示。這不是品質驗收，也不取代 T16；未執行須明示，不能因 mock 通過就稱 provider 相容。
- **不做：**LangChain Messages adapter、OpenAI Agents SDK、另一份 ResponseStore、通用 Provider、每 Step 必填分析筆記。

## T07 A 的 JD／來源／差異按需工具

- [x] T07；依賴：T03、T04、T05。
- **完成（2026-09-30 恢復後）：**八個 JD 入口、來源與兩類 diff 已逐條對照 Red 與 JDT-01～06、V17／V18／V20 的既有測試，見 [T07 §5](evidence/t07-jd-tools.md#5-任務完成對照2026-09-30-恢復後)；補上兩個缺口的守門測試：A／B1／B2 全部 28 個工具的遞迴 strict schema 檢查（32 案），以及模型工具路徑刪除任務／協作對象／共通條件（連明細與知識連結清除、共用知識保留、重送不多刪）。完整後端 **1847 passed、2 skipped**。**不含**：官方 API 逐 schema 接受（T16 wire gate）、模型是否先讀再寫等行為（T14／T16）、A 完整 Turn 的恢復與競爭（T08／T12）、JDT-09 的模型比較。以下為各切片的歷史紀錄。
- **最新切片（2026-09-30）：**八入口、完整集合編輯／來源與兩類 diff 已接上；提交 `4b20f1ed`、`a2168f63`。真 A3 使用當次原文及引用對齊完成更正；工具完整覆蓋與產品 gate 仍依 [T07 寫入](evidence/t07-jd-tools.md)、[來源／差異](evidence/t07-jd-changes-source.md)，不以一輪成功代全部驗收。
- **第一切片（2026-09-30）：**承接 `79b773ee`，接既有候選／固定修訂的精簡 JD map 與同範圍物件定位；不新增 map 儲存、名稱 ID 或 LLM 摘要。專項 **14 passed**，unit／contracts 與受影響候選真 PG **731 passed**；[證據與未完範圍](evidence/t07-jd-tools.md)。完整 read／編輯／來源及兩類 diff 尚未接好，不勾 T07、不當作 A 已可用。
- **契約：**[JD 八入口與分支](../../specs/2026-09-29-jd-model-tool-contract-review.md)、[A 的 read／map](../../specs/2026-09-26-consultant-context-and-state-design.md)、共同工具規範。
- **程式／交付：**`agents/job_consultant` 工具 schema／handler；JD service 的 source links、兩類 diff、精確來源確認；全稿 Markdown、map 精簡 JSON、局部讀取定位與下鑽。
- **Red：**同名新建被當舊來源、人工改待核對 JD 後丟舊基準、只讀 diff 解除待核對、確認後再改文字仍視為已核對、current_input 取消仍被引用、全稿重貼全部關係鏈。
- **完成：**JDT-01～06 離線層及 V17／V18／V20；scope／kind 非法明確拒絕；完整 read 不靜默裁切；來源屬正確 profile field／item／detail／relation。
- **不做：**自製額外 JD 短 ID、Memory read_ref／版本參數、任意舊 Memory 全文工具、tool search、修改已定 map。

## T08 A Turn：固定資料、正式完成與控制

- [x] T08；依賴：T02、T06、T07。
- **2026-10-01 補審修正：**原完成對照漏了「A 按需要求下一輪壓縮」；已沿既有歷史 binding 補零參數工具、成功資格及取消後 C 重用，Red→Green，受影響範圍 1173 項分批通過、獨立審查無阻擋。真 Luna 自主選用／分析品質未驗；[T08 §9](evidence/t08-consultant-turn.md#9-a-要求下一輪壓縮的接線補足2026-10-01)。不改模型或容量門檻。
- **完成（2026-09-30 恢復後）：**A Turn 的固定資料、正式完成與控制已逐條對照 Red 與 V04–V09／E07–E09／E12，見 [T08 §8](evidence/t08-consultant-turn.md#8-任務完成對照2026-09-30-恢復後)；四輪真模型、三批背景 Memory、暫停後同輪續作與重啟為實測證據，另補首請求超量的近期訪談縮減（§7）。**不含**：廣泛故障競爭矩陣（T12）、UI 與斷線重連的瀏覽器旅程（T09）、A 的自然訪談品質與來源選擇（T14／T16／T17；T17 的品質 trial 仍是 fail）。以下為各切片的歷史紀錄。
- **2026-09-30 恢復後：**補上暫停交接定位的缺口——首請求超量時的有界近期訪談縮減（V05「超量」）。共用迴圈只多一條有界路由，A 以純函式保留最新完整訊息、員工回答的必要前問，並在起始資料明示未預載範圍，A 用既有 `read_interview` 回讀。unit／contracts＋10 個真 PG 整合檔 **1058 passed**；[證據與未驗範圍](evidence/t08-consultant-turn.md#7-近期訪談預載超量的有界縮減2026-09-30-恢復後)。真模型是否實際回讀、未知 attempt 的 production 核對仍未完成，不勾 T08。
- **控制入口恢復增量：**typed 原件可交回既有 runner；換 writer、pending pause／續作、取消保護有定向證據，見 [T08 §6](evidence/t08-consultant-turn.md#6-原件交接穿過正式控制入口2026-09-30)。尚非 supervisor 自動交回／跨程序遺失再准入完成。
- **最新整合：**`76f99867` 接通正式完成／控制、原生接續、背景要求與公開歷史；三輪真模型、兩批 Memory、暫停重開同輪續作、902 unit/contracts、725 PG integration（另補兩項真 Chromium）及重啟證據見 [T08 §5](evidence/t08-consultant-turn.md#5-顧問--背景整理的整合2026-09-30-1057-台北)。未知 attempt 的 production 核對接線、廣泛故障／品質仍未完成。
- **2026-09-30 第一切片：**固定起始資料、共用模型／工具 loop、正式答覆／JD／歷史共同完成及 HTTP 派送通過合成 provider＋真 PG；缺模型設定不接受無法執行的輸入。控制、公開進度、背景要求及真 provider 仍待接線，見 [T08／T09 evidence](evidence/t08-consultant-turn.md)，不提前勾完成。
- **契約：**[A context](../../specs/2026-09-26-consultant-context-and-state-design.md)、[閉環](../../specs/2026-09-29-core-value-loop-lifecycle.md)、[資料接線](../../implementation/data-and-contracts.md)。
- **程式／交付：**`workflows/consultant_turn.py`、A 起始 projector、控制 API；原生基底／128K／272K、Memory pin、有效近期歷史、正式完成交易及取消 fencing。
- **Red：**Memory 半途換版、恢復重加輸入／maps、A final 尚未保存就宣告完成、取消與 final 同時成立、含 a 的輪中 C 帶入新 b、input 取消仍成正式序號。
- **完成：**V04–V09／E07–E09／E12 對應 A；原本候選與有效來源、答覆、background intent 原子完成；同 Step 內部保存可續；暫停停在下一請求前。
- **不做：**把網路中斷視為取消、對所有失敗自動新 Turn 重送、逐 token 恢復、JD map 起始預載。

## T09 訪談 UI、候選即時預覽與重連

- **2026-09-30 本輪 JD 變更檢視：**補上已交接缺口 2：完成回答可按需讀原輪前／採用 JD 的正文淨 diff 與來源變更筆數；沿既有修訂，無新增表／模型呼叫。後續人工修改或撤回不換比較端點；未完成候選不外露。局部測試與限制見[本輪變更證據](evidence/t09-turn-jd-changes.md)，未重啟 Demo、未驗新入口的真瀏覽器旅程，T09 不勾完成。

- **2026-09-30 UI 發現接線與審查修正：**無 hint 使用 current 發現工作後承接原 execution；未知不當 idle，頁面與 Composer 共用 hint 訂閱／query cache，已開啟 JD 表單也隨未知狀態唯讀且保留草稿。27 檔／160 前端測試通過；Demo 真 API 與固定訪談來源面板唯讀確認。保留基本多分頁，沿後端資格與版本衝突保護，不新增分頁鎖／同步平台。完整跨瀏覽器、故障與真模型 gate 仍未完，見[後續證據](evidence/t09-current-turn-discovery.md#ui-承接與多分頁取捨2026-09-30)。

- **2026-09-30 UI 交接後端增量：**已提供依職務檔案查目前 active／paused A 的唯讀 `/consultant-turns/current`，沒有則 null；重用 execution owner、公開 DTO 與來源 schema，不新增執行／保存權威。獨立審核發現含知識／技能候選的 Enum 轉接缺陷，已先重現再修正；主線最後相關真 PG＋contract **55 passed**，既有訪談前端 **43 passed**、新 Ajv **9 passed**及 tsc 通過。UI 尚未使用此 API、跨瀏覽器旅程尚未驗，T09 不勾完成。見[發現入口證據](evidence/t09-current-turn-discovery.md)。

- **2026-09-30 正式来源唯讀切片：**共享固定來源查詢、三個 GET、生成契約及按需 UI 已接線；946 unit／contract、13 專項真 PG、20 來源 UI 測試及型別／生成檢查通過。Demo 瀏覽器已讀正式來源列表與訪談原文，重新下載正式 PDF；尚未以此 Demo 驗 Memory 來源鏈 UI（目前直接來源均為原話），不冒稱全旅程通過。見[整合證據](evidence/t09-source-viewer.md)。

- **2026-09-30 公開串流切片：**原生 typed events／phase 白名單接有界暫態 hub、同源 SSE 及 scoped UI，原完整訊息仍由 checkpoint 投影回看；terminal 清理取消承接原 R，不改正式完成邊界。945 unit／contract、21 專項真 PG、95 前端測試通過。真 A 已產生並保存可回看的 commentary，但未截得完成前即時畫面，不宣稱完整真串流時序／T09 完成。見 [T08 §5.7](evidence/t08-consultant-turn.md#57-串流接線後的第四個真-a-turn1202-台北核對) 與 [provider／shared 接線](evidence/t09-response-streaming.md)。

- **2026-09-30 UI 改版（粗版）：**主畫面改為左訪談／右 JD 並排、窄螢幕分頁；JD 唯讀鎖、候選獨立檢視、來源滑出面板與項目徽章（後端小改：`Reference.target`）、章節導覽與可收合職責、檔案清單改版。前端 25 檔／138 測試、tsc／ESLint／Prettier／build 通過；Playwright e2e、真後端徽章、完整鍵盤走查、真模型旅程未驗，不勾 T09。見 [UI 改版證據與 API 缺口](evidence/t09-ui-redesign.md)。
- [x] T09；依賴：T08。
- **完成（2026-09-30 恢復後）：**補上最後缺口——A 已准入時的畫面行為。用最小的離線腳本化模型（只替換 SDK 的 HTTP transport，其餘為真後端／PostgreSQL）在真 Chromium 驗：即時公開訊息、JD 唯讀、重開與另一分頁找回同一處理且不重送輸入、暫停停妥後續作不多打模型、取消丟棄候選並可取回原文、模型拒絕後可重新開始、PDF、畫面不含私有推理或工具內容。整套 e2e **21 passed**（含先前無法驗的兩項「A 已准入」），見 [T09 旅程證據](evidence/t09-consultant-journeys.md)。**不含**：真模型完成前的逐片段畫面、完整鍵盤走查、跨瀏覽器、長訪談效能（非核心分析效果，留 T15／T17 依需要驗）；腳本化模型是合成替身，不證明模型品質。以下為各切片的歷史紀錄。
- **最新切片：**`b8fb4a62` 接上輸入、候選、控制、按歷史答覆回看公開訊息及條件撤回 UI；前端 86 項、型別與 build 通過，[證據](evidence/t09-consultant-preview.md)。目前以 status polling 顯示已保存訊息；逐字 SSE 正在後續切片，不宣稱已可用。
- **契約：**[介面設計](../../implementation/interface-and-delivery.md)、閉環公開訊息／控制邊界。
- **程式／交付：**interview／jd-editor UI、SSE transport、公開歷史讀取、重連狀態查詢；A 控制的狀態呈現。
- **Red：**斷流自動重送輸入、公開中間訊息消失／拿去引用、UI 私有 reasoning 洩漏、兩個 tab 人工改稿突破鎖定、候選顯示成正式稿。
- **完成：**V09／V21／E14 UI 部分；模型尚未回覆不阻止已保存輸入可辨認；正式答覆重連讀同一份；工具顯示僅必要公開資料。
- **不做：**永久 stream event 平台、逐 token 歷史、Memory 控制按鈕、讀取／來源的第二份前端業務規則。

## T10 B1／B2 私有角色與 context

- [x] T10；依賴：T05、T06。
- **完成（2026-09-30 恢復後）：**B1／B2 私有角色權限、固定資料與 context 已逐條對照 Red 與 V10／V11／V14，見 [T10 完成對照](evidence/t10-memory-analysis-roles.md#任務完成對照2026-09-30-恢復後)；補了 V14 的缺口：B2 收到的情境差異專項測試（新增含未被引用者、刪除、改名、改正文、改回、只有 B2 階段可取得）。真模型：三批 A→B1→B2 正式發布與課程行政旅程的背景批次。**不含**：背景整理是否讓長訪談更好（T14／T17）、按需差異在超長批次的容量（T15／T16）。以下為歷史紀錄。
- **最新切片：**`8eb469e1` 接兩個私有角色與同一共用 runtime，保留分層寫入權限；兩批真模型已共同發布，[T10 證據](evidence/t10-memory-analysis-roles.md)。局部真模型成功不代完整異常與品質 gate。
- **契約：**[B1／B2 分責](../../specs/2026-09-25-b1-b2-information-gap-lifecycle.md)、[原話 read](../../specs/2026-09-27-memory-read-and-source-navigation-contract.md)、[工作分析 §9](../../specs/2026-09-09-complete-work-analysis-guide.md#9-工作理解正文要寫到多清楚2026-09-25-研究補核對)。
- **程式／交付：**兩角色 instructions、handlers、起始投影與私有 graph history；typed gap／完成輸出；fake provider 分工測試。
- **Red：**B1 透過錯誤／gap 看理解、B2 修改情境、回交重置分析／compact、B2 只看已有引用而漏新增情境、原話上界偷偷用 A 最新輪。
- **完成：**V10／V11／V14 的角色層；fixed F、共同訪談 read；B2 讀現在情境＋必要 diff、只改理解；gap 具體、不要求固定互審。
- **不做：**新增審核 Agent、B1 閱讀理解、全層永久問題表、每輪重新生成全部 Memory。

## T11 背景調度、交接與共同發布

- [x] T11；依賴：T08、T10。
- **完成（2026-09-30 恢復後）：**背景調度、交接與共同發布已逐條對照 Red 與 V10–V15／E10／E13，見 [T11 完成對照](evidence/t11-memory-batch.md#任務完成對照2026-09-30-恢復後)。**已知限制（如實記錄，待 Owner 確認）：**`release_block` 沒有 production 呼叫者，背景整理一旦最終失敗該檔案就不再自動整理（A 仍可用近期原話與 `read_interview` 繼續；規格把解除偵測列為待細設），附有界建議。以下為歷史紀錄。
- **最新切片：**`8eb469e1` 接 Parent／固定範圍、差異交接、共同發布；`76f99867` 接 A 成功完成後登記與啟動重掃，[證據](evidence/t11-memory-batch.md)。已發布到正式員工序號 4、6；完整冷啟未知結果恢復仍未完成。
- **契約：**背景生命週期的①②③、[保存 §5](../../architecture/persistence.md#5-背景要求不能只留在記憶體)、共用執行 §5–7。
- **程式／交付：**`workflows/memory_batch.py`、Parent、App lifespan 調度；pending frontier／單批資格、交接快照diff、完成／失敗投影。
- **Red：**A 完成後 crash 漏通知、在途批次擴大 F、B2 gap後回到初始工作稿、發布確認遺失重發新版、失敗後跳過未發布區間、quota 未變仍無限重跑。
- **完成：**V10–V15／E10／E13；B 讀寫同一候選，A 只讀已發布；系統重啟承接，最終失敗 A 可用原話工具繼續。
- **不做：**broker、Memory 人工重試、按引用逐條核對、沒有新證據的語意 retry loop。

## T12 真 PostgreSQL 故障與競爭整合

- [x] T12；依賴：T09、T11。
- **完成（2026-09-30 恢復後）：**在 Owner 的首版恢復減法範圍內，E01–E15 已逐項對照既有真 PG／真程序測試，見 [T12 完成對照](evidence/t12-consultant-process-recovery.md#7-任務完成對照2026-09-30-恢復後)；本輪另在真模型評測中發現並修正兩個真實故障：串流中的限流被誤判為不可重試（[T06 §22](evidence/t06-agent-execution.md#22-串流中的限流被誤判為協定錯誤2026-09-30-恢復後的診斷與修正)）與重試耐心不足。**明確不含**（依 Owner 減法）：未明 attempt 的 production 再准入、任意位置自動續作；不含長時間 soak 與完整跨瀏覽器。以下為歷史紀錄。
- **跨程序已保存工作恢復（2026-09-30）：**正式 A Runner／控制 wrapper＋真 PG，四個 hard-exit 邊界與全新程序承接通過；已存 count／R 不重呼、工具交易不重複修訂、正式完成保留原引用。是合成 SDK 傳輸與明確 writer 接管，不是未知原件遺失的自動恢復；[證據與未完範圍](evidence/t12-consultant-process-recovery.md)。T12 不勾完成。
- **契約：**[E01–E15](../../specs/2026-09-27-shared-agent-execution-and-state-design.md#71-職責異常測試映射全部待執行)、[驗證矩陣](../../implementation/verification-plan.md)。
- **程式／交付：**整合／程序故障 harness；兩連線受控交錯、獨立程序重啟、COMMIT 確認遺失；必要缺口回原 owner 修。
- **Red：**逐一注入 R 已存／工具已 commit／Step 已存／final 已 commit／C 採用／B交接後故障；舊 writer 恢復與新 runner 競爭。
- **完成：**E01–E15 所需離線＋真 PG 證據；斷言外送數、程式進入次數、業務效果次數、context 與固定候選位置，不只 assert success。
- **不做：**用 sleep 猜 race、用 memory saver 冒充耐久、放寬取消邊界、以新結果補造舊結果。

## T13 正式 PDF 與條件撤回

- [x] T13；依賴：T03。
- **完成（2026-09-30 恢復後）：**PDF 與條件撤回已逐條對照 Red 與完成條件，見 [T13 完成對照](evidence/t13-pdf-export.md#任務完成對照與-pdf-文字層診斷2026-09-30-恢復後)；補了瀏覽器點頁面上的 PDF 下載連結的驗證，並設好字型／Chromium 後把原被跳過的真渲染測例補跑（6 passed）。**已知限制**：Noto／正黑體字型的 cmap 讓 PDF 複製或搜尋時部分常見字（如「長」「目」「黃」）變成部首字元，視覺正確；依 Owner 的簡化要求不新增字型加工流程。**不含**：乾淨環境交付（T18）。以下為歷史紀錄。
- 2026-09-30：PDF renderer／正式版讀取／UI 下載、條件撤回已接通。真 Chromium 中文長短版與 IAB 下載已驗；撤回限原基準、保留訪談／Memory 並拒絕覆蓋後續修改，見 [PDF 證據](evidence/t13-pdf-export.md)及[撤回證據](evidence/t13-jd-undo.md)。乾淨交付與完整 UI 旅程 gate 仍未完。
- **契約：**[介面交付](../../implementation/interface-and-delivery.md)、[驗證 V21／V23](../../architecture/verification.md)。
- **程式／交付：**PDF endpoint／renderer／UI；已完成 JD 修改的條件撤回 API。T09 完成後追加候選預覽中匯出旅程測例。
- **Red：**匯出候選／姓名、中文缺字、長任務斷頁遺失、撤回覆蓋後續人工改稿或倒退訪談／Memory。
- **完成：**短／長中文正式 PDF 實際渲染；正式版本固定；撤回只對允許的 JD 基準成立，衝突明示不覆蓋。
- **不做：**通用文件報表平台、DOCX／CSV、全產品 undo／跨機還原。

## T14 訪談方法、角色指引與品質試例

- [ ] T14；依賴：T07、T10。
- **2026-10-01 Luna Memory 代表例補驗：**部分資訊與一次工作更正兩例、三批真 B1→B2 正式發布；舊快照不變、8條引用邊及29份原生請求核對通過。獨立工程審讀本例內容 pass、冗餘 minor；一次非法 patch 被拒後模型自行修正。不加 Prompt 或改模型、不抵銷原 JD 漏引，不勾整體 gate。[結果與限制](evidence/t14-job-analysis-quality.md#2026-10-01luna-memory-部分資訊與跨批更正驗收)。
- **2026-10-01 Luna effort 診斷收斂：**同原長歷史只改 xhigh，一次生成返回四個合法工具請求，未執行工具；保留既有任務來源，但沒有重現新任務拆分，因此原漏引反例未判定。沒有足以採用的收益，維持 Luna／high、不補跑或加 Prompt，原品質 gate 不變；[結果與限制](evidence/t14-job-analysis-quality.md#2026-10-01luna-xhigh-的單次有界診斷)。
- **2026-10-01 Luna 情境精度診斷：**原「還有人→一人」定位於首批 B1 建立參數，非資料庫或長歷史遺漏；三例各基準／候選一次，皆保留正確精度，未證明擴寫指引有改善，因此不採用、不加同類重測。只觀察參數、不執行工具、不勾品質 gate。[結果與限制](evidence/t14-job-analysis-quality.md#2026-10-01b1-資訊精度的有界診斷)。
- **2026-10-01 核心 App 模型對照：**相同現行 Prompt／工具／Context，以新合成檔案指定 GPT-6.1 Sol／high，六輪 A、三批 Memory 完成；5 任務、1 知識、4 技能、54 引用可回讀，出席工作保留原第 8＋10 則依據。實際 Context 邊界／角色資料核對無錯放；Memory 仍偏長。只增兩 runner 共用的明確模型 profile，預設 Luna 不變；停止本輪比較，不抹除原 Luna 品質限制或勾整體完成。成本、回歸及跨模型歷史限制見 [T14 對照結果](evidence/t14-job-analysis-quality.md#2026-10-01較高能力模型的核心-app-旅程對照)。
- **2026-10-01 長 Context 欄位順序診斷：**原請求重播仍見拆分漏引；僅調來源欄位順序的候選未重現拆分且另有無依據內容，不採用、不追加試次。兩次自然 Step 均未執行工具或改業務資料；現行 Prompt／schema／Context 不變。[結果及結論邊界](evidence/t14-job-analysis-quality.md#2026-10-01長-context-的來源欄位順序診斷)。
- **2026-10-01 短來源診斷：**同現行指引／工具、全合成資料、強制單一建立操作下，Luna 與 GPT-6.1 Sol 各兩例都選對新舊／無關來源；僅參數選擇觀察，素材另有前問邊界 metadata 誤填，不作正式 Context 或模型優劣證據。沒有執行業務工具，不消除原長歷史拆分漏引；不換模型、不加描述、不重複短例。[manifest、結果與限制](evidence/t14-job-analysis-quality.md#2026-10-01來源參數選擇的模型能力診斷)。
- **2026-10-01 指引／Context 收斂：**B1／B2 真保存請求的角色、導覽、取材與原生歷史符合該批預期，31 項接線／PG 回歸通過。只修任務能力排序的工具指引矛盾、補上兩角色「未解衝突不自動採信最後一句」；文字契約 Red→Green，22 項局部測試通過。來源選項 description 的 4 次有限比較未得到可用改善證據，不採用、不重跑；[完整結果與限制](evidence/t14-job-analysis-quality.md#2026-10-01來源選項的參數語意對照)。沒有宣告引用／語意品質全過。
- **2026-10-01 專業提煉續驗：**既有 high 合成旅程續談，正式保存 1 項技能、2 個任務關係並拆出每日出席任務，37 筆來源原文可回讀；實際 Context／角色／工具組裝符合預期。收尾輪受服務錯誤阻斷；新拆任務的跨輪來源涵蓋、Memory 未支持精確化及精簡仍待改善，不加提示補丁或繼續重跑。範圍、一次補驗與未完事項見 [續驗證據](evidence/t14-job-analysis-quality.md#2026-10-01既有-high-旅程的專業提煉檢查)。
- **2026-10-01 指南覆蓋收斂：**三角色方法／工具與品質素材已逐項對照；40 素材／組裝及 14 既有寫入契約／真 PG 測試通過。本片不再加 Prompt；下一個代表性品質缺口是從已確認工作提煉 K/S 與合適成稿粒度，舊樣本空集合不直接當成新預設或保存故障。串流警告未離線重現，不增恢復程式；見 [審查與限制](evidence/t14-job-analysis-quality.md#2026-10-01指南覆蓋與下一個品質缺口收斂)。
- **2026-10-01 有限推理校準：**相同請求僅改 Luna effort，partial 0/2→2/2、whole-field 維持通過；四輪真 App／PG 旅程保留原來源並完成季度更正，28 筆可回讀。預設改 `high`，不加 Prompt／reviewer；三角色設定接線 Red→Green，相關 59 passed。仍有任務過大、Memory 語意細節及廣泛品質待驗，不勾完成；見 [比較、取捨與限制](evidence/t14-job-analysis-quality.md#2026-10-01來源保留的-reasoning-effort-對照)。
- **2026-10-01 跨面向審核：**核角色指引／工具說明／參數與實際 Context；補四份 JD schema 的欄位、增刪來源及逐筆確認語意，不改角色權限或歷史組裝。71 契約／接線測試及 13 真 PG 測試通過；有限模型檢查仍重現綜合職責漏保留來源，**未宣告品質修復**。審核範圍、研究、正反例及 Context 證據見 [T14 續頁](evidence/t14-job-analysis-quality.md#2026-10-01指引參數語意與實際-context-交叉審核)。停止同假說的提示微調，後續沿原品質 gate 判斷，不加來源猜補或新審核平台。
- **最新材料：**13 個合成品質情境、oracle／rubric、角色組裝契約及固定 Demo 樣本人工式審讀，見 [T14 證據](evidence/t14-job-analysis-quality.md)；v3 新增跨輪來源兩例，實際對照與仍未通過的邊界見 [T17 來源驗證](evidence/t17-course-administrator-journey.md#真後端保存確認結果與保留缺口)。離線契約通過不代表模型品質已達標；獨立領域校準、全部情境真模型及長訪談仍待驗。
- **契約：**[工作分析指南](../../specs/2026-09-09-complete-work-analysis-guide.md)、[JD 寫作](../../specs/2026-09-09-jd-field-and-writing-guide.md)、[方法研究入口](../../specs/2026-09-09-job-analysis-and-jd-content-research.md)。
- **程式／交付：**版本化角色 prompt／方法內容與全合成 fixtures／rubric；基於既有研究裁取適用內容，不複製整套指南到每次請求。
- **先驗：**fixture 必須能辨責任混淆、舊案更正、沒有主語、低頻工作、只掌握 10% 案例、人工稿不等於事實；離線驗指引組裝／工具權限；自然品質標待 provider。
- **完成：**每角色都有明確品質判準與正反例，JD 精簡不漏重要工作；不以字數／欄位填滿評滿分；T16 可用同資料集重跑。
- **不做：**全稿審核 Agent、固定問卷、每輪硬改 JD、自造員工事實、固定唯一工具序列。

## T15 安全、容量與維護性審查

- [x] T15；依賴：T12、T13。
- **2026-10-01 有界完成審查：**已逐項核對安全拒絕、隔離、token／查詢／保存量及依賴邊界；本次主線連容量／compaction 回歸 44 passed，原證據不重算成新驗收。無須先加 cache／索引／GC，完成依據與未驗範圍見[條件對照](evidence/t15-capacity-measurements.md#6-t15-完成對照2026-10-01-有界收尾)。本項完成不代表 T14／T16／T17 品質通過。
- **2026-10-01 容量收斂：**重用合成旅程完成 token／查詢／保存量測，最大已保存 A 請求 42,524 tokens；JD 投影約 5–14 ms，較慢的是 commentary history 投影。沿 Owner 指示不為非核心慢點加 cache／新儲存；原容量與 import 邊界 41 passed，詳見[量測與限制](evidence/t15-capacity-measurements.md)。大視窗 provider 與完整品質仍非本片證據。
- **2026-10-01 接手收尾：**既有憑證隔離草稿完成有限驗收：合成 key 不進 request body、真 PG checkpoint／產品資料、公開讀取及 log；provider 回顯秘密也不外露。4 例連既有局部安全回歸 69 passed，範圍見 [T15 末節](evidence/t15-local-http-security.md#2026-10-01-接手收尾憑證不進接續歷史與公開資料)。不新增產品子系統，不將整個容量／安全 gate 勾選。
- **2026-09-30 UI 交接修正：**隔離 Vite proxy 改為保留原 Origin，後端可顯式配置一個精確 loopback dev Origin；預設安全邊界不變。新增 red→green 代理與配置測試、原安全測例回歸見 [HTTP 證據](evidence/t15-local-http-security.md#隔離前端的來源保留修正2026-09-30)。僅修此接縫，不勾選整個 T15。
- **契約：**[運作責任](../../architecture/delivery-and-operations.md)、[程式規範](../../implementation/code-organization.md)、V24／V26／V27。
- **程式／交付：**同源／Host、敏感 log、prompt injection／跨檔案反例；大資料投影量測；import 邊界、慢查詢與實際保存容量報告。
- **Red：**偽造 tool 範圍、user-role 內容誘使越權、history JSON 洩漏密鑰、前端不同檔案 cache 串用、compact 後清掉回退／公開歷史依據。
- **完成：**安全拒絕可觀察、token／查詢量／保存量有量測；需要優化才加索引或局部 cache；新程式不 import 底稿或退役 package。
- **不做：**以 100% coverage 代替風險驗證、RBAC 平台、提前垃圾回收、未量測的 vector/cache 元件。

## T16 有界官方模型／schema／容量驗證

- [ ] T16；依賴：T14、T15。
- **2026-10-01 限流診斷：**各一次小型 Luna 生成與壓縮均回報 200K token 額度，零重試；這不是大視窗成功證據，也不能斷言先前 429 的全部細項。原門檻未改，已提出按配額校準候選，待 Owner 確認；見 [T16 §6](evidence/t16-compaction-continuity.md#6-429-的帳戶容量診斷2026-10-01)。不重送原大請求或增加恢復機制。
- **2026-10-01 共用 Runtime 大視窗補驗：**真 call＋合成工具結果計數 285,204，實際觸發 272K Step 間壓縮；遠端 compact 回 429 即停止，零重試，512K 未執行。只證實路由，不宣告大窗口壓後接續；原限額、結果與再驗前提見 [T16 §5](evidence/t16-compaction-continuity.md#5-共用-runtime-的-272k512k-有界補驗)。不以未知帳戶細項更動產品門檻。
- **2026-10-01 接續容量補驗：**141,777-token 合成工具視窗成功 compact，完整返回 C 續接更正、帶真 reasoning 再 compact，兩次答覆三項事實均正確；首輪探針過嚴假設、一次補跑及成本完整記錄於 [T16 證據](evidence/t16-compaction-continuity.md)。不勾整項、不等同正式 A/B 自動觸發或 JD 分析品質；272K／512K 真視窗仍未驗。
- **契約：**[選型與參數](../../implementation/technology-decisions.md)、JDT-01／08／09、V05／V06／V22／V26。
- **交付：**先寫測試 manifest：模型／有效 reasoning、SDK／prompt hash、資料範圍、次數／token／時間／費用限額、停止條件，再用有效授權外送。缺付費授權不阻塞離線工作，但不能進此 gate。
- **驗證：**strict wire 真接受、原生多 call 與跨 Turn 更正、compact 完整返回／重播、實際 request 計量、門檻與預留、工具選對及恢復成本；依同 fixtures 校準候選數值。
- **完成：**每案例實際結果與成本可核對；不可達數值明示，不偷偷切模型。provider 接受與內容品質分開記錄，不以 API 200 代替 JD 正確。
- **不做：**引用舊的無界授權、測試失敗無限重送、擅自擴量／換模型、讀 opaque reasoning 自證延續。

## T17 長訪談與完整產品旅程

- [ ] T17；依賴：T16。
- **2026-10-01 安全診斷補強：**收尾失敗只留下粗分類，無法區分限流／服務錯誤；共用外送邊界已補白名單 code、HTTP status 與本地請求身分的安全 log。相關 159 項測試通過，未新增付費請求、不改重試或模型、不宣稱舊失敗原因已確定。見 [T06 §23](evidence/t06-agent-execution.md#23-保留安全-provider-診斷2026-10-01)；T14／T16／T17／T18 狀態不變。
- **2026-10-01 Luna 收尾補驗已停止：**沿五輪既有真歷史，只重送未成正式訪談的收尾句一次；四次模型完成、第五次 `transient_service` 終止，八次工具的候選／整理意圖未生效，正式 JD／訪談／Memory 不變且無 active 殘留。候選仍見把收尾輸入當事實來源的問題；60項串流／分類離線測試通過不等於警告已修復。不再追加同例或提示微調，沒有產品變更、不勾品質 gate；[結果與下一步](evidence/t17-course-administrator-journey.md#2026-10-01luna-長訪談收尾的有界接續)。
- **2026-10-01 Luna 純來源換版接續：**保留上一真 A 歷史，只追加受控 M3、不人工改 JD；六次模型／十次工具自主讀來源 Markdown diff、正確改稿、明確對齊原引用，正式保存與無模型重開、舊鏈回讀通過。補上前片未觀察的 source 分支，不等同自然長訪談或 B1／B2 品質；[結果與限制](evidence/t17-course-administrator-journey.md#2026-10-01同一合成案例的純來源換版接續)。不追加同例、不勾整體完成。
- **2026-10-01 Luna 換版／人工改稿：**受控 fixture 下，一個真 Luna／high Turn 正確把每月改為每季、移除誤加核准權，並明確對齊既存 Memory 引用；正式保存、舊引用鏈及無模型重開可回讀。5 次生成、10 次工具，沒有改 Prompt／程式。模型讀人工 diff、新 Memory 全文與原話，**來源 diff 分支未觀察**；短單項案例不消除長訪談品質限制、不勾完成。見[結果與證據邊界](evidence/t17-course-administrator-journey.md#2026-10-01luna-的-memory-換版與人工改稿定向驗收)。
- **2026-10-01 UI／PDF 續驗：**原 Sol 合成產物以無模型後端唯讀開啟，來源／JD 變更可回看，3 頁 PDF 逐頁及 49 個已填文字欄位核對完成；發現並修正「無模型配置使已保存 commentary 無法回讀」的 bootstrap 接線，37 項相關測試通過。沒有新外送、人工補稿或改資料；這不是 Luna 品質驗收。界線與既有 PDF 文字層限制見[續驗證據](evidence/t17-course-administrator-journey.md#2026-10-01既有真模型產物的-ui-與-pdf-續驗)。Owner 已因成本[決定產品使用 Luna](evidence/t14-job-analysis-quality.md#2026-10-01owner-決定維持-luna)，後續不推進 Sol 切換。
- **2026-10-01 有限續驗已停止：**局部更正的來源保留候選僅 1/2 改善，未採用、不改產品 Prompt、不增機制；[全部四次結果](evidence/t17-course-administrator-journey.md#2026-10-01-續驗局部更正與仍有效的來源)保留。下一切片先對照既有 provider／核心旅程證據，補真正缺口，不重跑全部訪談或重試同一提示；來源語意限制未因此消除。
- **2026-10-01 接手核心品質：**六組 b0 共 64 個完成 Turn，仍有一份空任務稿及一筆收尾錯引；只修工具可操作的錯誤回饋，拒絕把提示詞候選的一次成功當成可靠改善。局部 probe、真後端短旅程、限制及下一步見[接手紀錄](evidence/t17-course-administrator-journey.md#2026-10-01-接手只處理影響成稿的兩個反例)。不重新開始全部長訪談，不以 API 成功代替品質通過。
- **2026-09-30 課程行政真模型切片：**7 成功訪談 Turn、4 背景 Memory、正式 JD 與 3 頁 PDF 已完成；周期更正及既有工作保留成立。但 3 個身分欄位引用錯輪，品質 trial **fail**，未勾本任務；接續優先處理來源選擇反例，詳見[有界旅程證據](evidence/t17-course-administrator-journey.md)。首次沙箱連線失敗已正常收尾，未擴充恢復系統。
- **來源選擇續驗：**僅澄清 A 逐項定位出處的既有指引，不新增機制；定向 probe 與主管更正的真保存有改善，但另一例仍漏 profile 來源，且月報收件人被局部更正擴大影響，品質未全過。背景 1 批發布、1 批預算失敗已收尾，無 active 殘留；詳見[結果與下一步](evidence/t17-course-administrator-journey.md#真後端保存確認結果與保留缺口)，不勾本任務。
- **契約：**[架構驗收](../../architecture/verification.md)、全部 V01–V28（V25 依試點範圍）、JDT-09。
- **交付：**獨立 fresh DB 的代表旅程：早期情境後期補充、Memory未發布續談、來源換版與人工改稿同時出現、取消／重試／重啟、JD 完成及 PDF；必要時瀏覽器真操作。
- **驗證：**員工只訪談、無人工代寫也可逐步產出有據 JD；工作範圍與責任不失真、關鍵差異保留；參照可追讀；定量記品質缺陷、模型／工具步數、context 與費用。
- **完成：**核心旅程與安全 gate 通過，剩餘限制明列。V25 顧問時間／員工學習成本的真實用戶比較另列試點待驗，不能捏造已節省三四小時。
- **不做：**以單一樣稿宣稱普遍滿分，為驗收增加專用全稿審核功能，放寬重大資料錯誤。

## T18 新產品入口切換與舊程式退役

- [ ] T18；依賴：T17；依[本 Goal 的條件式切換授權](README.md)執行，先核對 gate、精確 tracked 退役清單及可恢復性，不擴張刪除範圍。
- **2026-10-01 PDF 交付續驗：**獨立非 editable wheel、同機新下載的鎖定 headless Chromium／繁中字型，透過真 HTTP 正式保存及匯出 1 頁／3 頁 PDF；逐頁目視及 80 段文字完整性通過。CLI 下載逾時，改以同一官方 ZIP＋既有顯式路徑完成，不宣稱 installer／跨平台已驗。[範圍與限制](evidence/t18-same-origin-web.md#非-editable-安裝的中文-pdf2026-10-01-續驗)。僅補安裝文件、零模型費用，不勾 T18 或前置品質 gate。
- **2026-10-01 交付接線預備：**按既定單程序同源方案，使用 FastAPI 原生 frontend 接通已建置 UI；6 個行為反例修正後，相關 83 測試、mypy 與真 Web build／ASGI 資源深連結檢查通過。[範圍與限制](evidence/t18-same-origin-web.md)。只是可提前完成的隔離接線，不勾 T18、不更換正式入口／退役舊碼；T14／T16／T17 前置 gate 仍保留。
- **2026-10-01 乾淨安裝預驗：**從固定 Git 匯出、獨立非 editable venv 與新測試 schema，重现 migration 依賴 checkout 而無法啟動；改用 Alembic 套件資源，19 份 revision 不變。30 項局部／真 PG 回歸、實際 wheel 啟動、人工 JD 保存／重開及真建置深連結通過。[證據與未驗範圍](evidence/t18-same-origin-web.md#乾淨安裝與套件化-migration2026-10-01)。無付費呼叫、不動 Demo，模型品質／PDF 乾淨交付與正式切換仍待驗，不勾 T18。
- **契約：**[決策流程](../../decision-process.md)、ADR0077 的正式權責沿革、[交付規則](../../implementation/interface-and-delivery.md#5-安全與新舊切換)。
- **交付：**新 successor ADR、根 pnpm scripts／workspace、App READMEs／runbook／CONTRIBUTING、架構現況 map；列出舊 tracked 程式與依賴逐項退役。正式 authority 不在此前任務偷換。
- **先驗：**乾淨 clone 安裝／建庫／啟動／重開，production build 不引用 experiments；新入口故障可保留原環境及完整證據，不做舊資料 ETL。
- **完成：**入口、程式、schema、lock、文件及證據一致；未使用 package 已退役；歷史研究可回查；刪除精確清單與可回復方式已說明。
- **不做：**刪整個 workspace、舊 DB／volume／密鑰、獨立 RAG、使用者未追蹤檔；不自動 push／merge。
