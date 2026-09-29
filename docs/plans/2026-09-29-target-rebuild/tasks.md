# 可驗證任務與交付責任

- 狀態：**T01–T05 已完成；T06 施工中；T07–T18 未開始**。每項遵守[SDD／TDD](../../implementation/development-standard.md)。以下交付須依實際證據判定，不由規劃名稱推導已存在。
- 勾選表示相應層級實際驗證通過，不是「寫了文件」。每項完成後補實際命令、結果、證據連結及有授權的 commit。
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

- [ ] T06；依賴：T01。
- **第一切片（2026-09-30）：**接續 T05 寫入提交 `d87b3c86`，實作原生回應原件／重送投影、phase／多 call 路由及對應配對。獨立審查後補空白 final／compact 保留 user 反例；Unit／contracts＋真 saver 新程序 **413 passed**。目前只是元件與正常保存往返，沒有宣稱 E01–E04 整體、完整 Graph、費用／取消或 provider 已驗收。[研究、反例及下一步](evidence/t06-agent-execution.md)。
- **第二切片（2026-09-30）：**承接 `5cfbb1da`，單一原生模型／有序工具 Step、官方 serializer 明確 allowlist，接上實際 Memory 候選寫入與跨程序 saver。公開入口統一 sync／有界呼叫／恢復准入；模型保存故障／確認遺失、部分工具恢復與元件集合 **452 passed**。雙保存失敗的官方補存已有能力反例；正式 supervisor、完整 loop、預算／compact 與 provider 仍未完成。
- **第三切片（2026-09-30）：**承接 `a52d76d9`，官方直連 SDK 關閉隱含 retry／redirect，count／create 共用固定 payload；新增不洩漏原文的錯誤分類。Unit／contract **469 passed**，獨立複核 redirect P2 已修；[第三切片證據](evidence/t06-agent-execution.md#3-第三切片直連請求與安全失敗分類)。持久額度、完整 loop、串流與 provider 仍待交付，T06 不勾選。
- **第四切片（2026-09-30）：**承接 `a48b39a1`，executions owner 固定 policy／每次外送預留，原 attempt 重入不給重送許可，未知成本不歸零，取消後可記帳但不授權採用。Unit／contracts＋相關真 PG／新程序 **503 passed**；[額度證據及未接線邊界](evidence/t06-agent-execution.md#4-第四切片不可重置的工作額度與外送預留)。尚未將元件接成完整 HTTP／Graph supervisor，T06 維持施工中。
- **第五切片（2026-09-30）：**承接 `6b0eb918`，原 R／operation seed 在保存故障時交回公開恢復路徑；核原位置／資格後補存或承接，不重新推論、不覆寫後續工具結果。新增真 PG 取消／writer 替換及原交易不跨模型 I/O；受影響 **515 passed**，獨立複核 P2 已修。[本切片證據與限制](evidence/t06-agent-execution.md#5-第五切片原-r-保存失敗的公開恢復與工作資格)。完整外送 supervisor、loop／compact／控制與 provider 仍待交付。
- **契約：**[共用執行](../../specs/2026-09-27-shared-agent-execution-and-state-design.md)、[Agent 接線](../../implementation/agent-execution.md)。
- **程式／交付：**`agent_execution`、Responses／saver adapter、typed State／serializer、窄工具 handler 介面、單一 retry／計量責任；先使用測試工具與 fake Responses，不依賴產品工具完成。
- **Red：**R 已保存卻重呼模型、只存 output_text、兩工具平行／配錯 call、公開文字誤判 final、serializer 丟 opaque／phase、role namespace 污染、SDK 隱含 retry。
- **完成：**E01–E04 對應框架部分、E11／E15 計量與 compact mock；真 PG 新程序 round trip；零／一／多 call；`sync` 邊界先 R 後工具。
- **提前消除遠端風險：**準備獨立全合成 preflight，依[本 Goal 有效授權](README.md#3-狀態與施工順序)及 T16 同樣的資料／費用 manifest，先驗少量原生接續、strict、compact 與 token count，不需逐次請示。這不是品質驗收，也不取代 T16；未執行須明示，不能因 mock 通過就稱 provider 相容。
- **不做：**LangChain Messages adapter、OpenAI Agents SDK、另一份 ResponseStore、通用 Provider、每 Step 必填分析筆記。

## T07 A 的 JD／來源／差異按需工具

- [ ] T07；依賴：T03、T04、T05。
- **契約：**[JD 八入口與分支](../../specs/2026-09-29-jd-model-tool-contract-review.md)、[A 的 read／map](../../specs/2026-09-26-consultant-context-and-state-design.md)、共同工具規範。
- **程式／交付：**`agents/job_consultant` 工具 schema／handler；JD service 的 source links、兩類 diff、精確來源確認；全稿 Markdown、map 精簡 JSON、局部讀取定位與下鑽。
- **Red：**同名新建被當舊來源、人工改待核對 JD 後丟舊基準、只讀 diff 解除待核對、確認後再改文字仍視為已核對、current_input 取消仍被引用、全稿重貼全部關係鏈。
- **完成：**JDT-01～06 離線層及 V17／V18／V20；scope／kind 非法明確拒絕；完整 read 不靜默裁切；來源屬正確 profile field／item／detail／relation。
- **不做：**自製額外 JD 短 ID、Memory read_ref／版本參數、任意舊 Memory 全文工具、tool search、修改已定 map。

## T08 A Turn：固定資料、正式完成與控制

- [ ] T08；依賴：T02、T06、T07。
- **契約：**[A context](../../specs/2026-09-26-consultant-context-and-state-design.md)、[閉環](../../specs/2026-09-29-core-value-loop-lifecycle.md)、[資料接線](../../implementation/data-and-contracts.md)。
- **程式／交付：**`workflows/consultant_turn.py`、A 起始 projector、控制 API；原生基底／128K／272K、Memory pin、有效近期歷史、正式完成交易及取消 fencing。
- **Red：**Memory 半途換版、恢復重加輸入／maps、A final 尚未保存就宣告完成、取消與 final 同時成立、含 a 的輪中 C 帶入新 b、input 取消仍成正式序號。
- **完成：**V04–V09／E07–E09／E12 對應 A；原本候選與有效來源、答覆、background intent 原子完成；同 Step 內部保存可續；暫停停在下一請求前。
- **不做：**把網路中斷視為取消、對所有失敗自動新 Turn 重送、逐 token 恢復、JD map 起始預載。

## T09 訪談 UI、候選即時預覽與重連

- [ ] T09；依賴：T08。
- **契約：**[介面設計](../../implementation/interface-and-delivery.md)、閉環公開訊息／控制邊界。
- **程式／交付：**interview／jd-editor UI、SSE transport、公開歷史讀取、重連狀態查詢；A 控制的狀態呈現。
- **Red：**斷流自動重送輸入、公開中間訊息消失／拿去引用、UI 私有 reasoning 洩漏、兩個 tab 人工改稿突破鎖定、候選顯示成正式稿。
- **完成：**V09／V21／E14 UI 部分；模型尚未回覆不阻止已保存輸入可辨認；正式答覆重連讀同一份；工具顯示僅必要公開資料。
- **不做：**永久 stream event 平台、逐 token 歷史、Memory 控制按鈕、讀取／來源的第二份前端業務規則。

## T10 B1／B2 私有角色與 context

- [ ] T10；依賴：T05、T06。
- **契約：**[B1／B2 分責](../../specs/2026-09-25-b1-b2-information-gap-lifecycle.md)、[原話 read](../../specs/2026-09-27-memory-read-and-source-navigation-contract.md)、[工作分析 §9](../../specs/2026-09-09-complete-work-analysis-guide.md#9-工作理解正文要寫到多清楚2026-09-25-研究補核對)。
- **程式／交付：**兩角色 instructions、handlers、起始投影與私有 graph history；typed gap／完成輸出；fake provider 分工測試。
- **Red：**B1 透過錯誤／gap 看理解、B2 修改情境、回交重置分析／compact、B2 只看已有引用而漏新增情境、原話上界偷偷用 A 最新輪。
- **完成：**V10／V11／V14 的角色層；fixed F、共同訪談 read；B2 讀現在情境＋必要 diff、只改理解；gap 具體、不要求固定互審。
- **不做：**新增審核 Agent、B1 閱讀理解、全層永久問題表、每輪重新生成全部 Memory。

## T11 背景調度、交接與共同發布

- [ ] T11；依賴：T08、T10。
- **契約：**背景生命週期的①②③、[保存 §5](../../architecture/persistence.md#5-背景要求不能只留在記憶體)、共用執行 §5–7。
- **程式／交付：**`workflows/memory_batch.py`、Parent、App lifespan 調度；pending frontier／單批資格、交接快照diff、完成／失敗投影。
- **Red：**A 完成後 crash 漏通知、在途批次擴大 F、B2 gap後回到初始工作稿、發布確認遺失重發新版、失敗後跳過未發布區間、quota 未變仍無限重跑。
- **完成：**V10–V15／E10／E13；B 讀寫同一候選，A 只讀已發布；系統重啟承接，最終失敗 A 可用原話工具繼續。
- **不做：**broker、Memory 人工重試、按引用逐條核對、沒有新證據的語意 retry loop。

## T12 真 PostgreSQL 故障與競爭整合

- [ ] T12；依賴：T09、T11。
- **契約：**[E01–E15](../../specs/2026-09-27-shared-agent-execution-and-state-design.md#71-職責異常測試映射全部待執行)、[驗證矩陣](../../implementation/verification-plan.md)。
- **程式／交付：**整合／程序故障 harness；兩連線受控交錯、獨立程序重啟、COMMIT 確認遺失；必要缺口回原 owner 修。
- **Red：**逐一注入 R 已存／工具已 commit／Step 已存／final 已 commit／C 採用／B交接後故障；舊 writer 恢復與新 runner 競爭。
- **完成：**E01–E15 所需離線＋真 PG 證據；斷言外送數、程式進入次數、業務效果次數、context 與固定候選位置，不只 assert success。
- **不做：**用 sleep 猜 race、用 memory saver 冒充耐久、放寬取消邊界、以新結果補造舊結果。

## T13 正式 PDF 與條件撤回

- [ ] T13；依賴：T03。
- **契約：**[介面交付](../../implementation/interface-and-delivery.md)、[驗證 V21／V23](../../architecture/verification.md)。
- **程式／交付：**PDF endpoint／renderer／UI；已完成 JD 修改的條件撤回 API。T09 完成後追加候選預覽中匯出旅程測例。
- **Red：**匯出候選／姓名、中文缺字、長任務斷頁遺失、撤回覆蓋後續人工改稿或倒退訪談／Memory。
- **完成：**短／長中文正式 PDF 實際渲染；正式版本固定；撤回只對允許的 JD 基準成立，衝突明示不覆蓋。
- **不做：**通用文件報表平台、DOCX／CSV、全產品 undo／跨機還原。

## T14 訪談方法、角色指引與品質試例

- [ ] T14；依賴：T07、T10。
- **契約：**[工作分析指南](../../specs/2026-09-09-complete-work-analysis-guide.md)、[JD 寫作](../../specs/2026-09-09-jd-field-and-writing-guide.md)、[方法研究入口](../../specs/2026-09-09-job-analysis-and-jd-content-research.md)。
- **程式／交付：**版本化角色 prompt／方法內容與全合成 fixtures／rubric；基於既有研究裁取適用內容，不複製整套指南到每次請求。
- **先驗：**fixture 必須能辨責任混淆、舊案更正、沒有主語、低頻工作、只掌握 10% 案例、人工稿不等於事實；離線驗指引組裝／工具權限；自然品質標待 provider。
- **完成：**每角色都有明確品質判準與正反例，JD 精簡不漏重要工作；不以字數／欄位填滿評滿分；T16 可用同資料集重跑。
- **不做：**全稿審核 Agent、固定問卷、每輪硬改 JD、自造員工事實、固定唯一工具序列。

## T15 安全、容量與維護性審查

- [ ] T15；依賴：T12、T13。
- **契約：**[運作責任](../../architecture/delivery-and-operations.md)、[程式規範](../../implementation/code-organization.md)、V24／V26／V27。
- **程式／交付：**同源／Host、敏感 log、prompt injection／跨檔案反例；大資料投影量測；import 邊界、慢查詢與實際保存容量報告。
- **Red：**偽造 tool 範圍、user-role 內容誘使越權、history JSON 洩漏密鑰、前端不同檔案 cache 串用、compact 後清掉回退／公開歷史依據。
- **完成：**安全拒絕可觀察、token／查詢量／保存量有量測；需要優化才加索引或局部 cache；新程式不 import 底稿或退役 package。
- **不做：**以 100% coverage 代替風險驗證、RBAC 平台、提前垃圾回收、未量測的 vector/cache 元件。

## T16 有界官方模型／schema／容量驗證

- [ ] T16；依賴：T14、T15。
- **契約：**[選型與參數](../../implementation/technology-decisions.md)、JDT-01／08／09、V05／V06／V22／V26。
- **交付：**先寫測試 manifest：模型／有效 reasoning、SDK／prompt hash、資料範圍、次數／token／時間／費用限額、停止條件，再用有效授權外送。缺付費授權不阻塞離線工作，但不能進此 gate。
- **驗證：**strict wire 真接受、原生多 call 與跨 Turn 更正、compact 完整返回／重播、實際 request 計量、門檻與預留、工具選對及恢復成本；依同 fixtures 校準候選數值。
- **完成：**每案例實際結果與成本可核對；不可達數值明示，不偷偷切模型。provider 接受與內容品質分開記錄，不以 API 200 代替 JD 正確。
- **不做：**引用舊的無界授權、測試失敗無限重送、擅自擴量／換模型、讀 opaque reasoning 自證延續。

## T17 長訪談與完整產品旅程

- [ ] T17；依賴：T16。
- **契約：**[架構驗收](../../architecture/verification.md)、全部 V01–V28（V25 依試點範圍）、JDT-09。
- **交付：**獨立 fresh DB 的代表旅程：早期情境後期補充、Memory未發布續談、來源換版與人工改稿同時出現、取消／重試／重啟、JD 完成及 PDF；必要時瀏覽器真操作。
- **驗證：**員工只訪談、無人工代寫也可逐步產出有據 JD；工作範圍與責任不失真、關鍵差異保留；參照可追讀；定量記品質缺陷、模型／工具步數、context 與費用。
- **完成：**核心旅程與安全 gate 通過，剩餘限制明列。V25 顧問時間／員工學習成本的真實用戶比較另列試點待驗，不能捏造已節省三四小時。
- **不做：**以單一樣稿宣稱普遍滿分，為驗收增加專用全稿審核功能，放寬重大資料錯誤。

## T18 新產品入口切換與舊程式退役

- [ ] T18；依賴：T17；依[本 Goal 的條件式切換授權](README.md)執行，先核對 gate、精確 tracked 退役清單及可恢復性，不擴張刪除範圍。
- **契約：**[決策流程](../../decision-process.md)、ADR0077 的正式權責沿革、[交付規則](../../implementation/interface-and-delivery.md#5-安全與新舊切換)。
- **交付：**新 successor ADR、根 pnpm scripts／workspace、App READMEs／runbook／CONTRIBUTING、架構現況 map；列出舊 tracked 程式與依賴逐項退役。正式 authority 不在此前任務偷換。
- **先驗：**乾淨 clone 安裝／建庫／啟動／重開，production build 不引用 experiments；新入口故障可保留原環境及完整證據，不做舊資料 ETL。
- **完成：**入口、程式、schema、lock、文件及證據一致；未使用 package 已退役；歷史研究可回查；刪除精確清單與可回復方式已說明。
- **不做：**刪整個 workspace、舊 DB／volume／密鑰、獨立 RAG、使用者未追蹤檔；不自動 push／merge。
