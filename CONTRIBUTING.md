# Caliburn 開發指南

正式產品位於 `apps/backend` 與 `apps/frontend`。修改前先讀[架構導覽](docs/architecture/README.md)與受影響的模組／Bundle README；跨模組責任由[系統規格](apps/backend/architecture.md)維護。

## 正式結構

```text
apps/backend/   Python／FastAPI、業務能力、Agent、內聚公版與測試
apps/frontend/  React／TypeScript／MUI 工作畫面
packages/          公版文件與查讀的正式共用契約
docs/              產品、架構、程式規範及操作入口
```

標準部署為單一應用程序、PostgreSQL 與 Qdrant。Agent Plugin 可配置啟停，能力模組的資料、HTTP 與必要清理責任保留。

## 工具與安裝

使用 Node 24、pnpm 12、Python 3.14 與 uv；確切要求及版本由根 package、後端 pyproject 與 lock 維護。根目錄執行：

```powershell
pnpm install --frozen-lockfile
uv sync --project apps/backend --locked --extra local-models
```

Node 使用根唯一 `pnpm-lock.yaml`，Python 使用 `apps/backend/uv.lock`。公版模型權重與資料須事先備妥，安裝不代替索引建立。原生與 Docker 的設定檔、連線、PDF 資源及明示遷移見[原生開發](docs/operations/native-development.md)與[快速開始](docs/operations/getting-started.md)。

## 日常開發

```powershell
pnpm app:status
pnpm dev
```

開發後端為 `127.0.0.1:8101`，Web 為 `127.0.0.1:5174`。production 同源模式：

```powershell
pnpm build
pnpm start
```

明示資料遷移用 `pnpm app:migrate`；首次啟用官方 Checkpoint 另加 `--with-checkpoints`。啟動不自動遷移或恢復模型工作。Docker 啟停與更新沿[操作手冊](docs/operations/README.md)。

## 程式規範

遵循[程式組織](docs/standards/code-organization.md)、[程式撰寫規範](docs/standards/coding-standard.md)與[契約策略](docs/standards/contract-strategy.md)。能力模組按資料責任組織；Bundle 接入模型，Core 不反向依賴具體 Bundle。後端 Import Linter 與前端 ESLint 檢查依賴方向，規則以實際配置為準。

有行為改動先建立有效反例，再完成 Red → Green → Refactor；純文件與生成比對使用適當內容檢查，不製造假 Red。

## 驗證與提交

```powershell
pnpm check
```

根 gate 執行文件、Ruff／ESLint／Prettier、mypy／TypeScript、腳本及單元／前端測試、前端契約生成比對與 build。真 PostgreSQL、Qdrant、瀏覽器及真模型另外明示執行；skip 或離線綠燈不能冒充整合與品質證據。命令與限制見[驗證責任](docs/implementation/verification-plan.md)。

使用 Conventional Commits，一個可審工作單位一個 commit，不加工具署名。保留他人未提交內容與本機原件；公開提交只含程式、必要測試與產品／架構／開發文件。未經 Owner 明確要求，不 push、merge、發布或執行付費模型驗證。

## 公版能力

公版解析、索引、搜尋及回讀由 `occupation_reference` 管理，HTTP 與 Agent 工具共用能力。`packages/ocs-contract`、`packages/indexer-contract` 是正式依賴。來源、權重及索引不隨 Git 或 wheel 交付，維護命令沿[公版操作](docs/operations/rag.md)。

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
