# JD 關聯式 App：業務、保存、畫面與顧問接線施工計畫

- 日期：2026-09-13；Topic：JD-R002；狀態：G4 WORKING；RS-1 八操作／結果已局部實作，RS-2 十三表已隔離初始化，完整 runtime／保存流程尚未完成。
- Owner 授權：最後核完整客製化 JD 欄位後，繼續推進 App、業務邏輯、LLM 及測試；Excel 延後。沿[最新需求](../specs/2026-09-12-jd-relational-editing-requirements.md)。
- 本計畫取代[9/10 成品計畫](2026-09-10-jd-product-delivery.md)中**新版 JD 的施工順序／Plate／三工具／v2 前提**，不改寫舊六切片的成果與失敗。舊文件末尾 Task6 不是新工作指令。
- 正式產品仍依 ADR0060，ADR0075／0074 Proposed；隔離驗證不等於 G6 切換，不混接正式 API／Web。

**同日Owner修正技術選型前提：**不優先沿用現有框架或原生元件，不要求整合舊代碼。新增下方RS-F選型前置；本計畫中的舊路徑只供查需求、接口與失敗證據，不是新實作必須修改的落點。先按[選型準則](../specs/2026-09-13-jd-native-framework-and-integration-preflight.md)比較現行方案，結果成立後再固定框架／版本／程式落點；不能用已安裝或省舊碼改動作主要採用理由。

**同日研究收束：**Owner 澄清框架名稱僅為例子，不記為技術偏好。研究者依[比較與採用理由](../specs/2026-09-13-jd-app-stack-selection.md)選 TypeScript／React／Next.js App Router 與 Python／FastAPI 為方向，MUI 為第一 UI 驗證候選；不是沿舊碼的決定。下方「不預選」描述研究前提，後續框架狀態以該稿為準；精確版本、資料層與 Agent 接點、恢復格式及新實作落點仍待閉合，RS-F 未全部完成。

**同日續行收斂：**Owner 要求框架保持可替換並停止無效研究。RS-F 按實際依賴逐項閉合，不作全部技術研究完成才開工的大閘門；已定效果與來源規則先做[RS-1 完整任務／一次更正切片](../specs/2026-09-13-jd-relational-command-slice.md)。新落點為 `experiments/jd-relational-app`，先做純候選與離線契約驗證；其他具名操作、HTTP／讀取／回執契約仍在 RS-1，不因兩工具通過便開始宣稱真 DB／完整 App 已完成。

## 1. 成品範圍與可觀察結果

**同日實作續行：**[結果與資料庫基礎](../specs/2026-09-13-jd-result-and-storage-foundation.md)完成生成式結果驗證、HTTP 投影及十三表固定 migration；404 離線 tests、22 真 PG tests 通過。資料層沿[官方前置](../specs/evidence/2026-09-13-jd-relational-db-preflight.md)在獨立 PostgreSQL 18.6 驗證，不修改舊資料庫；[讀取／refs 前置](../specs/evidence/2026-09-13-jd-read-reference-preflight.md)已收斂永久 receipt 與對外投影責任。下一工作集中 RS-1／2 的一致讀取、永久 snapshot／receipt 與完整保存／對帳；HTTP endpoint／App／顧問仍未完成，不重開品牌比較。

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

2026-09-13 進度：RS-0 文件單位完成。RS-F 已閉合 RS-1 所需生成／驗證／SDK離線依賴，UI／資料層／Agent 接點仍待相依施工前驗證。[首單位](../specs/2026-09-13-jd-relational-command-slice.md)的兩操作／128 項保留為歷史結果；目前[八個編輯操作與共用 App 準備邊界](../specs/2026-09-13-jd-management-operations-slice.md)隔離驗證為 289 tests、codegen、TS 檢查通過。刪職責保留任務、受限移動、選區及來源規則已實作，人工／AI 同一行為已驗；完整讀取／HTTP／錯誤回執契約仍未完成。RS-2–7 尚未執行新版驗收，整體 G4、G6 及成品狀態不因局部 PASS 而改判。

本輪[分層／錯誤／紀錄官方證據](../specs/evidence/2026-09-13-jd-app-boundaries-errors-logging-evidence.md)已收束。RS-1 下一單位閉合 typed result 合法組合、ref 發配及 HTTP 查回／寫入差異；RS-2 承接 BEL-R01–05 的真 DB 結果、logging 配置／容量／故障及交錯文件歸屬。純候選的安全診斷已驗，不代表宿主 logging 或 DB 保存已完成，不另開 logging 品牌研究。

## 4. 第一個可執行工程工作單位

**先闭合RS-F中契約生成及離線驗證依賴，接RS-1：具體契約＋兩家工具契約相容性fixture＋純業務反例，零付費、零production接線。**不能先照舊SDK／generator生成一套再補選型理由；兩家必查官方資料，不等於產品必須新增雙provider切換功能。新前端、資料層及 Agent runtime 在其相依切片前各自閉合。

1. 依RS-F固定的新技術與程式落點準備單一契約來源及生成方式；舊DTO／Node bridge只提供反例及正式切換時需退出的路由清單，不要求新碼相容或包裝它們。
2. 定義 current read、item/field/container refs、具名 commands、保存回執／unknown、人工事件、history/source view 的 SSOT。catalog／run等已驗形狀可沿用語意；新舊版本明確分開，不加允許兩者混寫的fallback。
3. 以完整新增任務與一次正文＋要求＋K/S更正做首個縱向契約反例；證明有效未完整草稿被接受，錯誤類型／同文件關係／重複引用／過時refs被拒絕，不只測JSON能parse。
4. 用選定SDK／adapter捕捉離線請求形狀，參照兩家現行契約驗strict／nullable／variants／隱藏context及結果call identity，不以舊安裝版本為基準；缺少的另一家只作有界契約fixture，不暗加production provider。結果不代表服務端接受或模型自然選對工具。
5. codegen檢查、所選技術的受影響測試與獨立review通過後精確提交。下一切片RS-2前閉合DDL初始化／恢復細節；DA-03可平行，不能讓尚未決定的暫存格式默默進UI。

本輪的 DA-01 已形成操作設計，尚缺實際可操作畫面證據；DA-03仍是最明確的設計前置。不因延後Excel而假稱所有G4工作已完成，也不讓Excel／多餘功能阻擋獨立可做的契約研究與離線驗證。

## 5. 框架、測試與停止規則

依[框架選型前置](../specs/2026-09-13-jd-native-framework-and-integration-preflight.md)比較並決定新組合；成熟現成能力能降低複雜度時採用，原生元件沒有預設優先權。必要JD業務才由本案補齊；不先發明通用ORM、生成器、agent loop、定位或事件回放引擎。官方版本／主流採用證據與本案適用性分開記錄。

每切片保存首敗、最後結果與證據種類。純文件核連結／差異；契約測真實生成；DB測專用PostgreSQL；瀏覽器測完整操作；自然模型與真人分開。新反證才擴大測試或重開研究。

0付費核心規則沿用。模型預算／真人尚未安排不阻無依賴施工，不能代填通過。沒有產品需要不加入額外功能；但替代元件庫／工作流框架／Agent SDK不得僅因不是原先套件就排除，須依能力、授權、運行與保存責任比較。遇不支援先列可重現缺口、替代及代價，再決定有界接合。
