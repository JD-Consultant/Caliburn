# SDD／TDD 與工程交付規範

- 狀態：**新目標施工工作規則**；不替代產品決策，實作與付費授權由[計畫](../plans/2026-09-29-target-rebuild/README.md)記錄。查閱日：2026-09-29。
- 上位：[架構討論規範](../architecture-discussion-standard.md)、[決策流程](../decision-process.md)。本頁的 SDD 指 **Specification-Driven Development**，不是增加一套產品需求副本。

## 1. 研究後採用什麼

| 第一手來源 | 可借鑑做法 | 本案採用與限制 |
|---|---|---|
| [GitHub Spec Kit](https://github.com/github/spec-kit/blob/main/spec-driven.md) | 規格、技術計畫、任務與驗證可相互追溯；先研究限制 | 借流程，不安裝其全部命令或複製 constitution；不照搬每功能獨立 library／CLI 等示例規則 |
| [AWS Kiro Specs](https://kiro.dev/docs/specs/) | requirements → design → tasks，設計包含錯誤與測試 | 已有架構即需求來源，不重新寫另一份 requirements；任務可回查原章節 |
| [Google 小型變更](https://google.github.io/eng-practices/review/developer/small-cls.html) | 一個可理解的改動，包含相應測試，能獨立審查 | 優先產品效果切片；不硬訂行數、不把全部 DB 做完才碰 API，也不為拆 commit 留不可用接線 |
| [Google 測試工程](https://abseil.io/resources/swe-book/html/ch12.html) | 自動化測試支援修改；測試也要可維護 | 斷言行為與結果，不鎖死內部函式呼叫順序；交易／恢復不能只靠 mock |
| [Fowler：TDD](https://martinfowler.com/bliki/TestDrivenDevelopment.html) | 先列測例，再 Red → Green → Refactor；測試先驅動介面 | 每個有行為的子切片先證明反例；不能省略重構，也不把事後補測叫 TDD |
| [Anthropic Agent eval](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) | 區分執行軌跡與最終效果，選適當評分方式 | 程式安全性用確定測試，工作理解品質用情境 rubric；不要求唯一工具序列 |

這些來源支持可追溯、小步驗證及持續維護，**沒有一個全業界唯一的 SDD 模板或「最新框架必然最佳」保證**。下列規則是對本案的取捨，不是假稱所有大廠採同一套架構。

## 2. 每項任務的固定流程

1. **定位契約：**讀任務所列有效責任文件、非目標、相關 V／E／JDT 測例；確認工作目錄、分支、未提交內容與局部 AGENTS。
2. **驗機制：**查當前官方 API、穩定版本、相依與 license；已有機制先用。對會改變設計的疑點做有限 spike；記錄實際版本、反例、取捨，不以搜尋排名當證據。
3. **定介面與反例：**本次 effect、owner、輸入／輸出、正常及失敗例；有跨層 shape 才更新唯一 schema。效果等價的細節自行決定；涉及產品效果才問 Owner。
4. **Red：**新增一個能在目前實作上因缺少該行為而失敗的測試，記錄命令與失敗原因。環境壞掉、未安裝依賴或拼錯 import 不算業務反例成立。
5. **Green：**只實現本測例及該切片需要的能力。交易與原生 SDK 接縫同步加整合測試；不提前建立無使用方的 API。
6. **Refactor：**名稱、責任、重複與依賴方向一起整理；測試保持綠色。框架已提供的能力不再造一套。
7. **Review：**回到上位契約查漂移、權限、取消／恢復、資料留存與 context；更新本次相關文件、測試證據及任務狀態。

任務可包含多個 Red–Green–Refactor 循環。機制 spike、生成物及純設定不必表演假 Red；說清驗證方法，不假稱它們已通過產品測試。自然模型的非確定品質 eval 也不是單元測試 TDD 的替代品。

## 3. 開始與完成的門檻

**Ready：**已有有效規格、確定範圍與 owner、依賴可用、至少一個正常例與高風險反例、可執行驗證方式。未定的非阻塞參數可列測試初值；不能讓實作者自行猜新的業務語意。

**Done：**程式、schema／生成物、測試與相應文件一致；包含 Red／Green 證據或不適用理由；對應 gate 已通過且標明層級；無金鑰／員工原話進一般 log；沒有未實作的必要分支。`TODO`、mock 成功或 Graph END 都不是產品 Done。

以下任一未滿足就不能勾完成：正式效果／取消競爭只測 happy path、用 SQLite 代替 PG、只測框架可編譯、只看 `output_text`、把工具 schema 合法當成模型用對。失敗測試不得刪掉或放寬需求來使其通過。

## 4. 防止經過文件層層轉述後走偏

每個任務保留五項：**上位章節、程式責任、依賴、可觀察驗收、非目標**。驗證表維護 V01–V28／E01–E15／JDT-01–09 的覆蓋，不再給每句話發一個新需求 ID。

契約衝突時先查 current-decisions 的 successor 與責任文件。修規格必須交代舊效果、反例、新效果及受影響測試；不能默默改 prompt／返回內容規避測試。技術方案與產品契約衝突時，不讓底層文件優先。

合併審查應能從任一差異找到：它為哪個需求而存在、誰使用、哪個反例證明必要。找不到就先刪掉或移出本切片。新抽象須有目前使用者與不同實作／可測邊界的需要，不能只因「以後可能」新增 factory、registry、generic repository 或 provider framework。

## 5. 研究及版本規則

- 官方文件 → 鎖定版本原碼／測試 → 最小反例；查足以做選擇即停。不是每次小修固定巡查所有廠商。
- 選**受支援穩定版且通過本案契約**，不預設 beta、追 main 安裝或依 `latest` 浮動。依賴、生成器、瀏覽器 revision 及測試環境一起鎖定。
- 套件功能相同先選較少元件的路徑；新增依賴記用途、替代選項、license、維護／安全狀況、退出方式。底稿已有套件不等於已被新架構採用。
- 機制不符先報可重現差距。只允許有界 adapter／補強，不能偷偷放寬唯一匹配、原生接續、取消隔離或來源資格。

## 6. 交付與審查紀錄

每完成任務在既有 task entry 填：狀態、commit（有授權才提交）、實際命令／結果、產物與尚未驗證事項。較長的故障注入或真模型證據放該計畫的 `evidence/`，任務連結到它；不複製全量測試輸出到架構正文。

提交以單一可審查效果含測試為單位；共用重構與行為改動可分開，但不能交付破損中間態。實作授權、付費資料外送、切換 production、刪資料分開判定，不能由「下一步」自動推導。

## 7. 分析方法、Prompt、Tool 與 Context 共同驗收

角色／Prompt／工具設計前先讀[完整工作分析](../specs/2026-09-09-complete-work-analysis-guide.md)、[訪談校準](../specs/2026-09-09-customized-jd-depth-and-interview-calibration.md)、[JD 撰寫](../specs/2026-09-09-jd-field-and-writing-guide.md)及相應工具規範。保留已研究方法與防錯意圖，舊接線／歷史 gate 不搬入新架構；A、B1、B2 各取其責任，不把 Memory 當隱藏 JD 草稿。工程代理自主實作不等於顧問可以猜員工事實。

Prompt／Skill／工具說明與程式一起版本管理、審查及測試；只提供本角色所需目標、限制、判斷準則及必要示例，不每輪載入全指南。按需能力須驗模型實際可取得並使用。對實際 GPT-6 型號查當前官方規範，不跨型號推定能力或照抄工程代理的自主權限。參考 [OpenAI Prompt 工程](https://developers.openai.com/api/docs/guides/prompt-engineering#version-prompts-in-code)與 [GPT-6 指引](https://developers.openai.com/api/docs/guides/latest-model/gpt-6-astra#prompting-best-practices)；這些是一般提示方法，產品分析仍由本案指南定義。

失敗先區分方法、提示、Context、Tool、Runtime／資料與模型限制，再修真正 owner；不一律加 MUST 或提高步數。改動先有基準與假設，再以代表例／未用於調整的保留例比較，記錄事實保真、工作涵蓋、引導、衝突／未知、引用、JD 品質及工具／token／費用／延遲。品質達標後才削減冗餘。沒有新證據時停止無界調 prompt，已有影響的 prompt／模型／工具／context 變動執行相應回歸。角色行為與真模型結果仍由 T14／T16／T17 交付，文件補規則不等於驗收。

## 8. 問題與解法紀錄

代表性、反覆或影響設計的問題在既有 task evidence／研究／ADR 留下：問題及影響、重現與證據、已確認原因／假設、參考方案、選擇及取捨、驗證及未解限制。失敗與否決方案保留；不記每次拼字修正、不傾倒完整敏感請求或 opaque payload、不另造台帳。連結測試、提交與責任規格即可。

專題介紹可據此呈現「痛點 → 原方式限制 → 研究比較 → 設計 → 實測 → 限制」，但不是另一份規格。沒有測量的收益標預期，不把 API 200 或少數樣例包裝成完整產品品質或普遍節時。

## 9. 分支與提交

- 新主題分支採小寫英文連字號，不加 `codex/`；可沿用合適工作分支，不強制每任務／Agent 一條分支。先核正確基底與 dirty，不在預設分支施工，不建立無必要 Git Flow。平行工作隔離 index／HEAD，worktree 依產品工具管理。
- `type(scope): effect` 採 Conventional Commits；scope 用領域／模組，必要正文記任務、原因、驗證及限制。同一完整效果含程式／測試／文件；無關大量格式／升級另分。TDD 不要求提交破損 Red 狀態。
- 提交前核 staged diff、`git diff --check`、相應測試與秘密；精確 stage，不全收不明變更、不繞過測試。本 Goal 已授權本地 commit，不預設 push／merge／PR／tag／外部部署，不重寫共享歷史。
- 提交後核 SHA、狀態及剩餘差異，task 可連一組 commits。Commit 不是產品通過／遠端備份，Git 回退不會替業務資料或外部效果回退。

依據：[Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/)、[GitHub flow](https://docs.github.com/en/get-started/using-github/github-flow)與前述小型變更；本地操作授權與不用分支前綴是 Owner 的本案政策。

## 10. 長任務、Goal 與工作上下文

這裡管理的是**工程代理執行本專案的工作方式**，不是 Caliburn 產品中 A／B1／B2 的模型 Context 契約。

| 層次 | 保存什麼 | 不做什麼 |
|---|---|---|
| Goal | 最終成果、必要界線、完成條件及計畫入口 | 不重貼每份規格；縮短不等於刪除要求 |
| 計畫 README | 整體交付、有效授權、依賴及完整退出條件 | 不複製產品狀態機／tool schema |
| AGENTS／架構／實作責任文件 | 跨任務方法／產品語意／工程機制，各有原 owner | 不將任務摘要升格為契約，不以本地規則擴張使用者授權 |
| 任務表與 task evidence | 任務表管完成狀態；evidence 記實測、反例、取捨與下一步 | 不每輪新增進度報告或重複 authority |

每次接續先確認 repo／分支／dirty、有效決策、目前任務與實際檔案；再完整讀本切片所需責任章節、相關程式與測試。已讀且未變的無關文件不用每 Step 重讀，但不能只憑交接摘要猜契約。發現摘要與現況不符，核對原證據並更新，不把後來的推測寫成先前實測。

任務尚未完成時，沿用該 task 的 evidence 留下：已成立結果、失敗／未驗範圍、必要命令與環境、未解問題、下一個可執行步驟。只記可驗證決策與工作產物，不保存隱藏推理、秘密或整份敏感 Context。既有有界測試證據仍有效就重用，受相關改動影響才重驗；不因壓縮、交接或短 Goal 而重開整個計畫。

遇到插入問題先處理，再回未完主線；一般工程細節自主完成。真正影響產品效果／資料權責／跨層契約、重要安全保證、不可逆結果或明顯費用擴張時，帶問題、證據、影響、選項及建議提問，並繼續不受影響的工作。環境或外部限制如實標記，不能繞過安全限制或把無法驗證說成通過。

依據：OpenAI 的[長任務](https://learn.chatgpt.com/docs/long-running-work)說明成果、限制與驗證；[GPT-6 Astra 提示建議](https://developers.openai.com/blog/rethinking-skills-and-prompts-for-gpt-6-astra)支持精簡入口及按需深入；[Exec Plans 範例](https://developers.openai.com/cookbook/articles/codex_exec_plans)示範可持續更新的計畫／進度。本案借鑑這些原則，**不照搬單一文件模板，也不宣稱官方有固定 Goal 字數上限或已證明本次縮短提升模型品質**。
