# JD 關聯式 App：業務、保存、畫面與顧問接線施工計畫

- 日期：2026-09-13；Topic：JD-R002；狀態：G4 WORKING，分切片前置與通過條件如下，尚未執行新 runtime／migration。
- Owner 授權：最後核完整客製化 JD 欄位後，繼續推進 App、業務邏輯、LLM 及測試；Excel 延後。沿[最新需求](../specs/2026-09-12-jd-relational-editing-requirements.md)。
- 本計畫取代[9/10 成品計畫](2026-09-10-jd-product-delivery.md)中**新版 JD 的施工順序／Plate／三工具／v2 前提**，不改寫舊六切片的成果與失敗。舊文件末尾 Task6 不是新工作指令。
- 正式產品仍依 ADR0060，ADR0075／0074 Proposed；隔離驗證不等於 G6 切換，不混接正式 API／Web。

## 1. 成品範圍與可觀察結果

員工可以從空白手動建完整 JD，也可主要透過訪談取得客製化內容。職責、任務、多成果、多要求及共享知識技能在同一 App 真正保存為關聯式資料；可反覆改、看差異、回查依據、自動保存、重開及續談。

第一版 App 必備：建立／更名／列表／封存／恢復、六章完整 CRUD 與排序／移動、人工與 AI 共用規則、手改通知、按需寫稿、來源、歷史／整份還原／符合條件的整輪 JD 撤回、取消與恢復、設定提示、啟停、完整備份還原。

PARKED：Excel 與原始訪談下載、其他電腦安裝、真人顧問流程、永久刪除、登入／多人／雲端／RAG／舊資料搬移、持久 AI 試稿分支。延後匯出不刪正式資料，也不改六章內容。

## 2. 工作區與責任來源

施工續用 `S:/caliburn/.worktrees/analysis-only-agent` 的指定隔離 checkout。每切片先核 branch/status／局部指引；不在 root apps 下順便施工。舊核心保存點以[register](../current-decisions.md)的 54cdfb3420d074d1f4566cb04f12d1fb9a868022 為證據基準，目前 checkout 可有後續修正，不 reset 到舊點。

| 範圍 | 檔案責任／施工原則 |
|---|---|
| 需求與正文 | [六章格式](../specs/2026-09-10-jd-format-review.md)、[欄位審核](../specs/2026-09-13-jd-field-sufficiency-audit.md)；不新增必填分析欄 |
| DB 與操作結果 | [13 表與保存](../specs/2026-09-12-jd-relational-schema-and-write-contract.md)；只開新專用測試 DB，fresh schema |
| Domain／App | [完整操作與範圍](../specs/2026-09-12-jd-business-operations-and-scope-design.md)；沿 `experiments/analysis-agent/src/analysis_agent` 的 service、ports、tools、來源接點形成新版模組 |
| 契約 | [契約策略](../contract-strategy.md)＋[新工具語意](../specs/2026-09-12-jd-relational-agent-tool-contract.md)；隔離 checkout 的 `docs/specs/contracts/jd-relational-v3.schema.json` 為新候選唯一手改來源，沿 `experiments/jd-editor/contract` 生成器生成 Python/TS，root 不另建可漂移的 schema 副本 |
| Web | `experiments/jd-editor/web`，依[完整旅程](../specs/2026-09-13-jd-complete-app-journey-design.md)；沿既有 React／Next，原生文字／選擇能力優先 |
| 專業顧問／Memory | 保留既有 Skill、provider/runtime、Memory／source owners，只改 JD 接口與必要方法文字；不因新 JD 重選整個 Agent 架構 |
| 採用與維護 | [ADR0075](../adr/0075-relational-jd-authority-and-structured-editor.md)、[採用設計](../specs/2026-09-10-jd-production-adoption-design.md)、[維護前置](../specs/2026-09-11-jd-maintenance-exclusion-preflight.md)；新版要求逐項映射，不直接沿舊 whole-document write |

## 3. 切片順序與驗收

| 切片 | 要交付的實際效果 | 實作前須閉合 | 證偽／通過条件 |
|---|---|---|---|
| RS-0 欄位與旅程基線 | 最後內容審核、Excel 延後、完整手動操作及新計畫 | 本輪兩路審核及窄修正 | 沒有重要已知資訊無落點；不增加無用途欄；文件狀態與來源一致 |
| RS-1 契約及完整業務操作 | 新 schema／generated DTO；純 domain commands 與 validators；完整樣稿的 relational fixture | 工具 variants／nullable／source 及 HTTP envelope 同一來源；本切片設計獨立複核 | 人工／AI adapter 對同意圖形成相同 command；多成果／要求、K/S、未分組、無名稱草稿、繁中／LF、原子最終候選、跨文件／過時拒絕；两家離線 wire shape 無 DB／provider 副作用 |
| RS-2 真 DB 保存與恢復 | 建立目錄＋profile＋初始 head/revision；十三表 migration；current rows／snapshot／receipt 共同交易；恢復與 read ports | SSOT＋RS-1；明定 initial 全套初始化、約束、restore順序、receipt未知與既有writer接點 | 真 PG 執行 D01、移動、K/S限制、來源exactly-one、重複operation與COMMIT結果遺失；r1不得兩successors；失敗無半筆發布；新程序重開全值一致 |
| RS-3 員工完整手動 App | 真 API＋六章 CRUD，同頁完整文本／引用／差異／來源／歷史；自動保存與重開保護 | RS-2；DA-03 IndexedDB schema／容量／版本／資料集識別、原生欄位驗證前置 | 不開模型由空白做完完整 JD；A晚回不清B、中文組字、原生選取、移動／刪除、切文件／封存／重開；Web/DB同版，不能靠瀏覽器cache當保存 |
| RS-4 接既有 AI 顧問 | App注入scope／run／refs／版本；JD具名工具、真實錯誤、人工改動通知；繼續用既有 Memory與來源 | RS-1/2/3交接；兩家adapter序列化、provider結果對帳；既有方法改稿時機與新命令對齊 | 固定模型回應完成初稿→手改→AI續改→純訪談不改→部分成功後取消→安全閉合；真DB/聊天/Memory/歷史一致，沒有強制每輪寫JD |
| RS-5 歷史／撤回與日常維護完整驗證 | 同頁實際差異、原始來源；整份還原及HR-02；備份還原、更新、缺設定與啟停 | RS-2/3/4；[歷史](../specs/2026-09-12-jd-history-and-recovery-design.md)、[整輪撤回](../specs/2026-09-12-jd-ai-turn-undo-design.md)、維護程序前置 | 撤回只改JD、不回退Memory／原話；不可撤晚於該輪的修改；還原後所有資料scope一致；未知結果不重複新增；操作可由員工完成 |
| RS-6 首份自然 JD | 顧問自行訪談、決定時機、調用工具、反覆更正並收尾 | RS-4/5可靠性；首批資料範圍／呼叫數／美元上限與硬停止可審且獲授權 | 不指定工具腳本；保留實際model input/output、用量、耗時及首敗；工作→JD、JD→依據，不能靠自評滿分 |
| RS-7 正式接合／品質交付 | 完整採用清單／G6、正式API/Web單一路徑、固定版本；未見案例與員工驗收 | 已驗核心、受測runtime來源／依賴、必要ADR；自然與真人批次分別授權／安排 | 正式程式不import研究目錄；舊writers退出；3職位各2自然流程＋長訪談＋3員工依既定材料實測，不能平均分抵消重大錯誤；全體備份／恢復與日常入口可用 |

RS-5 的還原／撤回 domain 與 DB 基礎在 RS-2 就實作驗證，RS-5 接全旅程與維護，不把 API 局部通過當整體通過。RS-7 採用研究、驗收材料、維護設計可以先並行；正式切換保留 G6，無須等到切換當天才研究。

2026-09-13 進度：RS-0文件單位完成，欄位／管理旅程及框架／計畫已分別獨立審查，首敗與修正留責任文件；RS-1–7 尚未執行新版實作／驗收。整體G4、G6及成品狀態不因局部文件PASS而改判。

## 4. 第一個可执行工程工作單位

**接 RS-1：具體 successor 契約＋兩家離線 fixture＋純業務反例，零付費、零 production 接線。**先完成同一切片的精確設計／独立審查，再生成／施工；本總計畫不假稱目前 DTO 已存在。

1. 讀現有 generator 與 DTO 使用位置，列 v2 root references／native bridge 的替換清單，不手改生成物，也不把研究 Node bridge 當新 relational domain。
2. 定義 current read、item/field/container refs、具名 commands、保存回執／unknown、人工事件、history/source view 的 SSOT。catalog／run等已驗形狀可沿用語意；新舊版本明確分開，不加允許兩者混寫的fallback。
3. 以完整新增任務與一次正文＋要求＋K/S更正做首個縱向契約反例；證明有效未完整草稿被接受，錯誤類型／同文件關係／重複引用／過時refs被拒絕，不只測JSON能parse。
4. 用實際安裝的 OpenAI／Anthropic adapter 捕捉離線請求形狀，不建立模型client的網路呼叫；檢查strict、所有required／nullable、nested variants、ToolRuntime隱藏欄位與結果call identity。結果仍不代表provider實際接受或模型自然選對工具。
5. codegen檢查、受影響Python／TS測試與獨立review通過後精確提交。下一切片RS-2前閉合DDL初始化／恢复細節；DA-03可平行，不能讓尚未決定的暫存格式默默進UI。

本輪的 DA-01 已形成操作設計，尚缺實際可操作畫面證據；DA-03仍是最明確的設計前置。不因延後Excel而假稱所有G4工作已完成，也不讓Excel／多餘功能阻擋獨立可做的契約研究與離線驗證。

## 5. 框架、測試與停止規則

沿[原生能力與版本前置](../specs/2026-09-13-jd-native-framework-and-integration-preflight.md)：React原生欄位、FastAPI／Pydantic、PostgreSQL／psycopg、既有LangChain／LangGraph與生成器。必要業務命令、DB mapper與恢復接線由本案實作；不自造通用ORM、schema生成器、agent loop、文檔定位或事件回放引擎。

每切片保存首敗、最後結果與證據種類。純文件核連結／差異；契約測真實生成；DB測專用PostgreSQL；瀏覽器測完整操作；自然模型與真人分開。新反證才擴大測试或重開研究。

0付費核心規則沿用。模型預算／真人尚未安排不阻無依賴施工，不能代填通過。沒有需求證據的drag-and-drop、通用欄位配置、CRDT、工作流平台或另一套Agent SDK不納入。遇框架不支援，先列可重現缺口、替代及代價，再決定有界接合。
