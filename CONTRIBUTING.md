# Caliburn 開發指南

Caliburn 的正式產品是本機 Web AI 職務分析與職務說明書 App。現行權責由
[正式產品與選型](docs/architecture/design-decisions.md)決定；
開始修改前先讀[架構與現行責任](docs/architecture/README.md)與相關設計文件，不從歷史目錄猜現況。

## 正式結構

```text
apps/api/        Python 3.14／FastAPI／LangGraph／PostgreSQL 後端（A／B1／B2、JD、Memory、PDF）
apps/web/        React／TypeScript／MUI 介面
docs/            現行架構、契約、開發規範與 runbook
```

舊關聯式 App 與獨立 Memory 套件已退役，不能接回 import 或啟動。歷史決策與研究原件只在本機保存；RAG 仍保留，與 JD App 隔離且只能明示啟用。

## 工具與安裝

- Node.js `>=24.19.0 <25`、pnpm `12.5.1`
- Python `3.14`，由 uv `0.12.20` 管理
- PostgreSQL `18.6`

在 repository 根目錄執行：

```powershell
pnpm install --frozen-lockfile
uv sync --project apps/api --locked
```

Node／TypeScript 使用根目錄唯一的 `pnpm-lock.yaml`；不要新增 npm lockfile。Python 使用
`apps/api/uv.lock`。資料庫與 OpenAI key 只經明示的環境變數／`apps/api/.env` 的單一 key 設定，
不由安裝或啟動偷偷建立、清除或搬移；步驟見 [runbook 的首次初始化](docs/runbook.md#第一次初始化)。

## 日常開發

```powershell
pnpm app:status   # 診斷設定，不啟動、不改資料
pnpm dev          # 後端 :8100 與 Vite :5173 同時啟動
```

production 形式（單一後端程序同源提供建置後的 Web）：

```powershell
pnpm build
pnpm start
```

## 程式規範

層次與依賴方向、命名與寫法依[程式組織](docs/standards/code-organization.md)與
[程式撰寫規範](docs/standards/coding-standard.md)：依賴只向下，模組以業務責任組織，Service
是用例責任而非必須的 class 後綴，不為想像的未來泛化。層方向與前端 feature 互不 import 由
`apps/api/tests/unit/test_import_boundaries.py` 與 `apps/web/eslint.config.js` 鎖定，違反會直接失敗。
有行為的改動先建立有效反例，再完成 Red → Green → Refactor；適用範圍見下方驗證要求。

## 驗證與提交

正式根閘門：

```powershell
pnpm check
```

它執行 lint（Ruff、ESLint、Prettier 格式）、型別（mypy strict、TypeScript）、不需資料庫的單元／契約／前端
測試，以及文件引用、契約生成核對與 production build。真 PostgreSQL、真瀏覽器及真模型驗收仍依各計畫明示執行
（見[後端 README](apps/api/README.md#測試與檢查)）；離線綠燈不能冒充 provider 或 UI 證據。

使用 Conventional Commits，一個可審工作單位一個 commit，不加工具署名。保留他人未提交內容；研究、計畫、實驗原件與報告只留本機；公開提交保留程式、必要測試與架構／開發文件。未經 Owner 明確要求，不 push、merge、發布或執行付費模型驗證。

## 隔離 RAG

```powershell
pnpm rag:up
pnpm rag:dev
pnpm rag:down
```

RAG 不在正式 JD App dependency graph。變更前讀
[RAG 設計](docs/design/rag-pipeline.md)，不要把它接進 JD App composition root。

## 變更範圍與審查

修改前確認工作目錄、分支、未提交內容及適用的局部指引，保留既有工作。沿受影響的公開責任文件與實際程式確認目的、範圍、非目標、負責模組及可觀察的驗收；局部修正只展開相關範圍。權責、相容承諾、資料來源、產品效果及明顯費用的重大取捨，須先確認授權並說明理由、替代方案與限制，再同步責任文件、契約及必要測試。

以一個可理解的產品效果或工程改善交付，審查者應能從差異找到受影響責任與驗證方式。工程品質與 JD 品質各有驗收；模組內聚、清楚依賴、可讀、可測與可診斷是工程基線，不以先證明 JD 提升為前提。新抽象或依賴須有目前用途及清楚邊界，核對鎖定版本、官方契約、維護與整合成本，並交代必要例外；不為想像中的未來泛化。

## 驗證要求

開始實作前須有有效契約、明確範圍、負責模組、可用依賴、代表正常例與高風險反例，以及可執行驗證。正確性問題先重現，建立原因假設，再修正負責模組。測試失敗必須是要驗的行為，環境或 import 錯誤不算有效 Red；實作後回到責任、名稱、重複與資源生命週期重構。

| 受影響範圍 | 必要驗證 |
|---|---|
| 交易、歷史／引用、隔離、取消／恢復、外部副作用 | 代表正常及競爭／失敗反例；交易、鎖與恢復使用真 PostgreSQL／必要程序，不能以 SQLite 或 mock 替代 |
| 跨層格式、生成物、薄轉接、同形欄位 | 唯一 schema 生成核對、型別、代表性契約與受影響行為測試；重用已有共同機制證據 |
| 使用者互動、串流或畫面生命週期 | 受影響 Web 測試及必要真瀏覽器旅程；API 或 build 成功不代替 UI 證據 |
| Prompt、Tool、Context 或模型設定 | 工程契約測試與下節品質比較分開；受影響跨輪／恢復行為仍須回歸 |
| 純文件、生成、設定或機制 spike | 用適合的內容／連結／生成比對或代表性反例核對，不製作假 Red；既有證據足夠的簡單改動可不加專屬測試，說明依據 |

日常先跑受影響範圍；共用保存、契約、恢復或里程碑整合，再完成相應全套及適用的最終 gate。完成必要檢查後，只有新變更、失敗或未解疑點才追加測試；可延後項目須明列範圍及所屬驗收，必要的安全、資料權威與錯誤診斷不能延後。

完成時，程式、schema／生成物、測試及文件須一致，適用 gate 已通過，必要分支已落實；回報實際命令、層級、結果、限制及未驗項目。TODO、mock 成功、Graph END、只看 output_text 或工具 shape 合法，都不等於正式保存、模型用對或整項產品完成。失敗測試不得靠刪除或放寬需求過關。詳細接縫由[驗證責任](docs/implementation/verification-plan.md)維護，具體命令沿 App README。

## 模型品質比較

比較前固定問題、基準／候選、變因、資料版本與可見範圍、成功／失敗判準、收束條件及有效的資料外送／費用授權。使用代表例及未參與調整的保留例；oracle、隱藏材料與未發生答案只供評閱，不能洩漏給受測角色。比較沿正式 App 的保存、權限與取消流程，隔離每組職務、Memory、Plan、JD 及執行資料；替身及其限制須明示。

| 比較層級 | 能支持的結論 |
|---|---|
| 工程行為／契約 | 具體輸入與 I/O 邊界的正常、失敗與競爭結果，不代替模型品質 |
| 固定 Context 的局部模型對照 | 相同可見資料、工具結果及重要設定下，某步／短段的差異；不能推定整份 JD 提升 |
| 自主完整旅程 | 相同案例背景、回答規則及初始資料下的整體訪談與正式 JD；實際問答、工具及 Context 可不同 |

保留實際程式、組裝後提示、工具契約／實作、模型與重要設定、Context 來源及初始狀態；沿實際請求、工具往返及正式產物核對。多項同改只對整組方案下結論。工程通過與分析品質分開報，重大事實、權限、範圍及引用錯誤逐項揭露，不能用平均分抵銷；工具成功、較少呼叫或 token 也不代替品質。

結果須交代樣本數、失敗／排除、途中改測法、人與模擬員工／AI 評閱的分工、必要人工校準、用量／成本／延遲與限制。依差異及模型波動決定必要重複，重跑不保證相同輸出；失敗修正加入適當回歸，缺失資料如實標明。先沿輸入、提示、Context、Tool、Runtime／保存及模型限制定位原因，沒有新證據就停止無界調整，單次小樣本較佳不能宣稱穩定提升。敏感內容與觀測責任沿[程式規範](docs/standards/coding-standard.md#71-讓執行證據可查可比較可驗證)。

## 文件維護

公開文件須能獨立支援理解、建置、修改與驗證：產品說明目的與內容判準，架構說明責任及保證，實作說明接線，三份核心規範說明程式要求，runbook／App README 維護操作命令。規則只在負責正文修改，入口只提供導航；同一變更同步受影響正文、入口、操作與圖稿，不手抄第二份 schema、狀態機或設定。

標明現行、目標／未實作、候選與歷史，保留施事者、條件、順序、確定程度與獨有例外。改名／拆分同步反向引用及真正必要錨點，新增頁從既有入口可達。圖源與重繪方式見[圖庫](docs/diagrams/README.md)。ADR、研究、方法原稿、設計、施工計畫、執行證據與實驗報告只留本機；公開正文保留必要結論、官方來源及限制，閱讀、建置與測試不依賴私人檔案或舊提交取回命令。

在根目錄安裝鎖定依賴後執行 `pnpm docs:check`；也可用 `node scripts/check-docs.mjs <文件路徑>` 指定本次受影響 Markdown。預設檢查全部 Git 可見的公開 Markdown（根目錄、App、套件及 docs），略過已不存在來源；本地檔案、圖片及跨頁錨點的目標也須屬公開檔案或含公開檔案的目錄，私人檔案即使在本機存在仍會拒絕。明示文件路徑可檢查本機紀錄。工具不連外網，也不證明圖面語意或產品行為；另核差異、狀態及內容一致性。一般日誌不放金鑰或員工原話；完整測試原件只保存有效授權內的必要資料，受控診斷與一般日誌依程式規範分開。

維護這份指南採用 [GitHub 貢獻指南](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/setting-guidelines-for-repository-contributors)的貢獻入口，以及 [Google review](https://google.github.io/eng-practices/review/reviewer/looking-for.html)的設計、複雜度、測試與文件審查原則；具體驗證門檻是本案選擇。
