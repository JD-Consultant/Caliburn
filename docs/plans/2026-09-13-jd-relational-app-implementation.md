# JD 關聯式 App：業務、保存、畫面與顧問接線施工計畫

- 日期：2026-09-13；Topic：JD-R002；狀態：G4 WORKING；RS-1／2 核心、人工 HTTP 與配置已隔離驗證；RS-3 第一段六章管理畫面、自動保存與瀏覽器候選恢復已接真 API／DB。完整 AI 生命週期、歷史還原、其餘故障／IME 驗收及完整 App 尚未完成。
- Owner 授權：最後核完整客製化 JD 欄位後，繼續推進 App、業務邏輯、LLM 及測試；Excel 延後。沿[最新需求](../specs/2026-09-12-jd-relational-editing-requirements.md)。
- 本計畫取代[9/10 成品計畫](2026-09-10-jd-product-delivery.md)中**新版 JD 的施工順序／Plate／三工具／v2 前提**，不改寫舊六切片的成果與失敗。舊文件末尾 Task6 不是新工作指令。
- 正式產品仍依 ADR0060，ADR0075／0074 Proposed；隔離驗證不等於 G6 切換，不混接正式 API／Web。

**同日Owner修正技術選型前提：**不優先沿用現有框架或原生元件，不要求整合舊代碼。新增下方RS-F選型前置；本計畫中的舊路徑只供查需求、接口與失敗證據，不是新實作必須修改的落點。先按[選型準則](../specs/2026-09-13-jd-native-framework-and-integration-preflight.md)比較現行方案，結果成立後再固定框架／版本／程式落點；不能用已安裝或省舊碼改動作主要採用理由。

**同日研究收束：**Owner 澄清框架名稱僅為例子，不記為技術偏好。研究者依[比較與採用理由](../specs/2026-09-13-jd-app-stack-selection.md)選 TypeScript／React／Next.js App Router 與 Python／FastAPI 為方向，MUI 為第一 UI 驗證候選；不是沿舊碼的決定。下方「不預選」描述研究前提，後續框架狀態以該稿為準；精確版本、資料層與 Agent 接點、恢復格式及新實作落點仍待閉合，RS-F 未全部完成。

**同日續行收斂：**Owner 要求框架保持可替換並停止無效研究。RS-F 按實際依賴逐項閉合，不作全部技術研究完成才開工的大閘門；已定效果與來源規則先做[RS-1 完整任務／一次更正切片](../specs/2026-09-13-jd-relational-command-slice.md)。新落點為 `experiments/jd-relational-app`，先做純候選與離線契約驗證；其他具名操作、HTTP／讀取／回執契約仍在 RS-1，不因兩工具通過便開始宣稱真 DB／完整 App 已完成。

## 1. 成品範圍與可觀察結果

**Owner 最新收斂要求：**先大致完成核心流程並收尾，問題集中在[唯一收尾清單](../specs/2026-09-13-jd-app-open-issues.md)；既有採用證據足夠的地方停止廣搜，只針對新反例修正。本次[整輪改動 API／畫面接合](../specs/2026-09-13-jd-run-change-view-slice.md)承接下方材料成果，實際驗證層級與限制以該結果為準；已承諾但未完成的恢復／來源等不默默刪除。

**最新 CV-01 比較材料接點：**[固定 AI 操作集合讀取](../specs/2026-09-13-jd-run-change-material-slice.md)完成單一唯讀交易、版次連續性及首末已保存內容核對；人工／別輪插入不混為同輪，改後改回仍保留操作。新純反例54、獨立真PG13、差異回歸70、原history25（含12真PG）通過，獨審未發現P1／P2。這是內部讀取，公開整輪DTO／HTTP／欄位標記／刪除清單仍待接合。[Fetch有限診斷](../specs/evidence/jd-relational-chat-web/transport-diagnosis.md)另取得第三組TypeError／13ms／未abort；根因OPEN，臨時診斷已移除且乾淨build通過，不再無證據重送。

**最新 RS-3／4 同頁聊天接點：**[原話保護與已保存改動](../specs/2026-09-13-jd-chat-web-slice.md)已接 Web：手改先保存、原聊天 request 重開保護、最新對話、原 run 查回及逐 operation 前後內容。最後 Web 233 PASS、後端與 helper 219 PASS、生成／TS／build 及分工審查通過；真瀏覽器兩輪後 PG 獨立核 head3／operation2 與原生訪談一致。第一輪 fetch 中斷後明示恢復，限定重現仍有未定位的瀏覽器連線問題，不能稱無故障完成。日常 AI 仍未啟用，完整 CV-01／HR-02、Memory／source、自然品質與完整 App 未完成。

**最新 RS-4 聊天 HTTP 接點：**[聊天控制與原修改結果](../specs/2026-09-13-jd-chat-http-slice.md)完成生成契約、原run狀態／取消／恢復、固定root/source對話頁與真SQL效果全集核對。最後完整離線2211 PASS／209 SKIP；三個真PG HTTP情境分批通過，生成／TS及獨立窄審通過，CH-R01收尾誤顯執行中已修。日常入口明確ai_unavailable、不開模型；下一接同頁聊天Web，Memory／source／自然品質與完整App未完成。

**最新 RS-4 聊天准入接點：**[已保存版次與原回合查回](../specs/2026-09-13-jd-chat-admission-and-original-run-slice.md)完成 V2 原請求、V1 原樣恢復、同 slot 原結果優先／新 head 准入、唯讀排空及有效原生祖先查回；完整離線1961 PASS／201 SKIP、真PG4及新程序PG4通過，四組獨審無阻擋，AC-R01已修。使用者提供的工具研究已核官方並留下適用取捨。256祖先上限與缺鏈仍回待查明；公開續頁／聊天HTTP／Web未完成。

**最新 RS-4 新宿主接點：**[AI 原回合恢復](../specs/2026-09-13-jd-ai-restart-recovery-slice.md)完成同宿主 startup／foreign proof／原 receipt／native closed 接合；相同 Agent 檢視結構不開 provider、不重播。最終新程序真PG4 PASS、原PG回歸8 PASS、受影響293 PASS；先前全組1830 PASS／197 SKIP，最後互斥pending P2 已修並獨審關閉。這不包含聊天 HTTP、Memory／source 或自然模型驗收。

**最新 RS-4 接點：**[本程序 AI 回合與具名工具](../specs/2026-09-13-jd-ai-runtime-and-tools-slice.md)已接同文件 owner、原生 after_model／sync checkpoint、共用 JD writer、取消／原 receipt 恢復與 App 自動閉合。真 PG 固定 SDK 完成 AI→手改→AI、純訪談及 COMMIT 回覆遺失；最後窄組253 PASS、真 PG14 PASS，完整範圍及首敗見結果稿。新宿主 AI 恢復、Memory／來源與聊天入口仍未接，不是完整 RS-4／自然品質完成。

**先前 RS-4 通知接點：**[人工通知與模型回覆保存](../specs/2026-09-13-jd-consultant-context-slice.md)已完成 LangChain／Anthropic adapter 精確相容導入、真正 wire、同版 notice 及原生 Agent／PG Saver 接合。受影響 74 PASS（13 真 PG），全組及 ACL 補跑合計 1624 非 PG 案例通過／193 PG 未全跑；codegen 與獨立審查通過，交錯串流 P2 已修。這是固定離線回覆接點，沒有完整 AI 生命周期或自然品質完成宣稱。

**本次追加驗收：**[回覆遺失與重開查回](../specs/2026-09-13-jd-browser-reply-loss-slice.md)完成真瀏覽器／原生宿主／PG端到端：真提交但回覆未到，重開以原operation GET查回，1POST／1GET／1execute，head2、任務及digest一致。對話框關閉誤落封存分支已修；新build／TS、Web99及helper23通過，獨立審查PASS。此處承接下方先前UI成果，不重跑或重算其全組數字。

**最新實作進度：**[六章手動管理與恢復切片](../specs/2026-09-13-jd-manual-ui-and-browser-drafts-slice.md)完成 Read v2 穩定 UI 身分、React／Next／MUI 管理畫面、原操作與輸入世代恢復、同頁歷史；真瀏覽器完成多成果／要求、共用知識引用、未完成表單重開、任務移動、刪職責保留任務、封存恢復及續改。Python 全組1540 PASS／180 PG SKIP，Web 99 PASS、生成／TS／build PASS；受影響真 PG 與最終 DB head11 唯讀核對通過。独立審查提出的缺口已修，首敗／層級／未驗範圍以結果稿為準；不是完整 RS-3／AI 成品通過。[配置](../specs/2026-09-13-jd-managed-configuration-slice.md)及[文件目錄](../specs/2026-09-13-jd-catalog-http-slice.md)保留原成果。

**最新 OI-02 接點：**[當輪原話來源接合](../specs/2026-09-13-jd-consultant-source-integration-slice.md)接通已保存原話、真正 request metadata、人工／AI 共用來源驗證及原話固定回查。來源44、受影響103及真 PG 縱向1通過；故障歸因與人工讀取排空缺口已修。0 provider，不新增原話表或模型工具；完整 Memory、較早來源與來源 UI 仍未完。

**最新 OI-02 核心接點：**[獨立 Memory 套件與新來源](../specs/2026-09-13-jd-memory-core-adoption-slice.md)完成保存／發布／固定讀取，沿既有 CAS／回執規則；新 App 用 proper package，核心44、來源71、受影響113、真 PG1及獨審98通過（重疊不相加），獨立 wheel 可用。只明示初始化專用測試 Memory schema，未改一般 host profile、未加模型工具／provider。

**唯一下一工作：**接同宿主 Store 的資源、明示初始化與排空，接續既有模型 Memory／案例能力、專業指引、完整來源窗口及按需回查，集中完成 OI-01／02 的完整顧問流程；不直接 import 研究路徑、不重做 Memory 研究。日常模型維持明示未啟用，自然案例依 OI-09 的資料／呼叫數／預算另驗。其餘依[唯一收尾清單](../specs/2026-09-13-jd-app-open-issues.md)推進；Fetch 只按新證據診斷，不無據重送。當輪改動 UI 真瀏覽器未驗範圍保留，不增舊對話選輪入口。Excel 延後；需求不清或無據增加複雜度時先記錄並討論。

員工可以從空白手動建完整 JD，也可主要透過訪談取得客製化內容。職責、任務、多成果、多要求及共享知識技能在同一 App 真正保存為關聯式資料；可反覆改、看差異、回查依據、自動保存、重開及續談。

第一版 App 必備：建立／更名／列表／封存／恢復、六章完整 CRUD 與排序／移動、人工與 AI 共用規則、手改通知、按需寫稿、來源、歷史／整份還原／符合條件的整輪 JD 撤回、取消與恢復、設定提示、啟停、完整備份還原。

PARKED：Excel 與原始訪談下載、其他電腦安裝、真人顧問流程、永久刪除、登入／多人／雲端／RAG／舊資料搬移、持久 AI 試稿分支。延後匯出不刪正式資料，也不改六章內容。

## 2. 工作區與責任來源

既有隔離checkout `S:/caliburn/.worktrees/analysis-only-agent` 是歷史實證參考，不要求在其舊模組上整合新版。RS-F選型後建立明確隔離新實作落點；需要時可另開隔離checkout，保留原dirty及證據。每切片核branch/status／局部指引，不在root正式apps下順便施工；不reset舊實證或搬舊資料。

| 範圍 | 檔案責任／施工原則 |
|---|---|
| 需求與正文 | [六章格式](../specs/2026-09-10-jd-format-review.md)、[欄位審核](../specs/2026-09-13-jd-field-sufficiency-audit.md)；不新增必填分析欄 |
| DB 與操作結果 | [13 表與保存](../specs/2026-09-12-jd-relational-schema-and-write-contract.md)；只開新專用測試 DB，fresh schema |
| Domain／App | [完整操作與範圍](../specs/2026-09-12-jd-business-operations-and-scope-design.md)約束效果；依RS-F選定框架建立新模組，不被舊service／ports類別形狀綁定 |
| 契約 | [契約策略](../contract-strategy.md)＋[新工具語意](../specs/2026-09-12-jd-relational-agent-tool-contract.md)；維持單一正式來源與機械生成，生成器／語言／精確落點由RS-F確認，不必整合舊generator。變更Accepted跨語言策略另做successor |
| Web | 依[完整旅程](../specs/2026-09-13-jd-complete-app-journey-design.md)比較成熟設計系統／元件與App框架，不預選React／Next或裸原生控制項，不要求改造舊JdEditor |
| 專業顧問／Memory | 保留已研究的內容方法、能力、資訊保留與資料責任；runtime／Skill接合方式／adapter可依現行證據重選。沒有證據不重做研究，但舊碼不是整合義務 |
| 採用與維護 | [ADR0075](../adr/0075-relational-jd-authority-and-structured-editor.md)、[採用設計](../specs/2026-09-10-jd-production-adoption-design.md)、[維護前置](../specs/2026-09-11-jd-maintenance-exclusion-preflight.md)；新版要求逐項映射，不直接沿舊 whole-document write |

## 3. 切片順序與驗收

| 切片 | 要交付的實際效果 | 實作前須閉合 | 證偽／通過條件 |
|---|---|---|---|
| RS-0 欄位與旅程基線 | 最後內容審核、Excel 延後、完整手動操作及新計畫 | 本輪兩路審核及窄修正 | 沒有重要已知資訊無落點；不增加無用途欄；文件狀態與來源一致 |
| RS-F 技術方案選型 | 依所需能力比較現行UI／App／保存／Agent方案，固定推薦、版本／授權與新實作邊界 | §1產品需求；官方來源、相容性與必要有限反例；不以已安裝優先 | 每個必要效果有現成能力或有據的有限接合；已棄用路線排除，預覽能力單列限制；最多三個實質方向，不默默增通用引擎 |
| RS-1 契約及完整業務操作 | 新 schema／generated DTO；純 domain commands 與 validators；完整樣稿的 relational fixture | RS-F 中本切片實際所需的契約／驗證依賴；工具 variants／nullable／source 及 HTTP envelope 同一來源；各有界單位獨立複核 | 人工／AI adapter 對同意圖形成相同 command；多成果／要求、K/S、未分組、無名稱草稿、繁中／LF、原子最終候選、跨文件／過時拒絕；兩家離線 wire shape 無 DB／provider 副作用 |
| RS-2 真 DB 保存與恢復 | 建立目錄＋profile＋初始 head/revision；十三表 migration；current rows／snapshot／receipt 共同交易；恢復與 read ports | SSOT＋RS-1；明定 initial 全套初始化、約束、restore順序、receipt未知與同文件writer協調契約 | 真 PG 執行 D01、移動、K/S限制、來源exactly-one、重複operation與COMMIT結果遺失；r1不得兩successors；失敗無半筆發布；新程序重開全值一致 |
| RS-3 員工完整手動 App | 真 API＋六章 CRUD，同頁完整文本／引用／差異／來源／歷史；自動保存與重開保護 | RS-2；DA-03 恢復儲存方案／格式／容量／版本／資料集識別、所選欄位元件驗證前置 | 不開模型由空白做完完整 JD；A晚回不清B、中文組字、實際選取、移動／刪除、切文件／封存／重開；Web/DB同版，不能靠瀏覽器cache當保存 |
| RS-4 接 AI 顧問能力 | App注入scope／run／refs／版本；JD具名工具、真實錯誤、人工改動通知；滿足已研究Memory與來源能力 | RS-F/1/2/3交接；所選adapter序列化、provider結果對帳；專業方法與新命令對齊 | 固定模型回應完成初稿→手改→AI續改→純訪談不改→部分成功後取消→安全閉合；真DB/聊天/Memory/歷史一致，沒有強制每輪寫JD |
| RS-5 歷史／撤回與日常維護完整驗證 | 同頁實際差異、原始來源；整份還原及HR-02；備份還原、更新、缺設定與啟停 | RS-2/3/4；[歷史](../specs/2026-09-12-jd-history-and-recovery-design.md)、[整輪撤回](../specs/2026-09-12-jd-ai-turn-undo-design.md)、維護程序前置 | 撤回只改JD、不回退Memory／原話；不可撤晚於該輪的修改；還原後所有資料scope一致；未知結果不重複新增；操作可由員工完成 |
| RS-6 首份自然 JD | 顧問自行訪談、決定時機、調用工具、反覆更正並收尾 | RS-4/5可靠性；首批資料範圍／呼叫數／美元上限與硬停止可審且獲授權 | 不指定工具腳本；保留實際model input/output、用量、耗時及首敗；工作→JD、JD→依據，不能靠自評滿分 |
| RS-7 正式接合／品質交付 | 完整採用清單／G6、正式API/Web單一路徑、固定版本；未見案例與員工驗收 | 已驗核心、受測runtime來源／依賴、必要ADR；自然與真人批次分別授權／安排 | 正式程式不import研究目錄；舊writers退出；3職位各2自然流程＋長訪談＋3員工依既定材料實測，不能平均分抵消重大錯誤；全體備份／恢復與日常入口可用 |

RS-5 的還原／撤回 domain 與 DB 基礎在 RS-2 就實作驗證，RS-5 接全旅程與維護，不把 API 局部通過當整體通過。RS-7 採用研究、驗收材料、維護設計可以先並行；正式切換保留 G6，無須等到切換當天才研究。

2026-09-13 進度：RS-0 文件單位完成。RS-F 已閉合生成／驗證／SDK離線、資料層、signer、查詢／保存／目錄HTTP、Windows宿主、持久配置、六章UI／瀏覽器恢復及本次原生Agent／通知保存接點。RS-1／2共同保存及RS-3／4局部結果以§1為準，DA-03已在UI切片實作驗證，不再列成未選定方案。還原／整輪撤回與AI生命週期仍未完成；RS-3–7尚未通過完整驗收，整體G4、G6及成品狀態不因局部PASS改判。

本輪[分層／錯誤／紀錄官方證據](../specs/evidence/2026-09-13-jd-app-boundaries-errors-logging-evidence.md)已收束。typed result 合法組合及 HTTP 純投影已完成，service 亦驗真 DB 結果、診斷不含正文、sink 故障不蓋原觀察及不同文件獨立保存。宿主 logging 配置／容量／實際接線仍由相依工作補驗，不另開 logging 品牌研究。

## 4. 起始工程工作單位（沿革，已完成）

本節保留起始順序與驗證目的；目前工作只依§1，不能將本節舊前置重開成新的施工阻擋。

**先闭合RS-F中契約生成及離線驗證依賴，接RS-1：具體契約＋兩家工具契約相容性fixture＋純業務反例，零付費、零production接線。**不能先照舊SDK／generator生成一套再補選型理由；兩家必查官方資料，不等於產品必須新增雙provider切換功能。新前端、資料層及 Agent runtime 在其相依切片前各自閉合。

1. 依RS-F固定的新技術與程式落點準備單一契約來源及生成方式；舊DTO／Node bridge只提供反例及正式切換時需退出的路由清單，不要求新碼相容或包裝它們。
2. 定義 current read、item/field/container refs、具名 commands、保存回執／unknown、人工事件、history/source view 的 SSOT。catalog／run等已驗形狀可沿用語意；新舊版本明確分開，不加允許兩者混寫的fallback。
3. 以完整新增任務與一次正文＋要求＋K/S更正做首個縱向契約反例；證明有效未完整草稿被接受，錯誤類型／同文件關係／重複引用／過時refs被拒絕，不只測JSON能parse。
4. 用選定SDK／adapter捕捉離線請求形狀，參照兩家現行契約驗strict／nullable／variants／隱藏context及結果call identity，不以舊安裝版本為基準；缺少的另一家只作有界契約fixture，不暗加production provider。結果不代表服務端接受或模型自然選對工具。
5. codegen檢查、所選技術的受影響測試與獨立review通過後精確提交。下一切片RS-2前閉合DDL初始化／恢復細節；DA-03可平行，不能讓尚未決定的暫存格式默默進UI。

起始時DA-01缺畫面、DA-03缺恢復格式；兩者已有§1所列實作與局部真瀏覽器證據，剩餘故障／接點仍照結果稿追蹤。不因延後Excel或局部通過而假稱所有G4工作已完成。

## 5. 框架、測試與停止規則

依[框架選型前置](../specs/2026-09-13-jd-native-framework-and-integration-preflight.md)比較並決定新組合；成熟現成能力能降低複雜度時採用，原生元件沒有預設優先權。必要JD業務才由本案補齊；不先發明通用ORM、生成器、agent loop、定位或事件回放引擎。官方版本／主流採用證據與本案適用性分開記錄。

每切片保存首敗、最後結果與證據種類。純文件核連結／差異；契約測真實生成；DB測專用PostgreSQL；瀏覽器測完整操作；自然模型與真人分開。新反證才擴大測試或重開研究。

0付費核心規則沿用。模型預算／真人尚未安排不阻無依賴施工，不能代填通過。沒有產品需要不加入額外功能；但替代元件庫／工作流框架／Agent SDK不得僅因不是原先套件就排除，須依能力、授權、運行與保存責任比較。遇不支援先列可重現缺口、替代及代價，再決定有界接合。
