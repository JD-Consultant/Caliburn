# 程式組織、依賴方向與命名

Caliburn 採模組化單體，按資料責任與共同變更理由組織程式。完整模組圖與公開能力由[系統規格](../../apps/backend/architecture.md)維護；本頁定義修改與審查的依賴、命名及維護要求。

## 1. 目錄依業務責任組織，機制集中在少數邊界

```text
apps/backend/
  src/caliburn/
    host/              HTTP、資源生命週期及應用程式組裝
    modules/           Workspace、JD、Interview、Memory、Plan、Agent 等能力
    bundles/           Prompt、Tool、Context 與能力接入
    shared/            少數共用型別及技術機制
    migrations/        隨後端套件交付的業務遷移
  tests/               單元、契約與整合驗證
apps/frontend/
  src/app/             路由、主題與跨功能畫面組裝
  src/features/        Workspace、訪談、Memory、JD
  src/shared/          HTTP／SSE、生成契約與共用 UI
packages/              公版文件及查讀契約
```

Application 協調用例與交易，Domain 維護不變量，Infrastructure 實作儲存與外部 I/O，Presentation 轉換傳輸資料。按實際責任建檔，不強制每個模組有四個空目錄；也不將每個模組拆成部署服務。

業務 SQL 留在負責模組；共享連線與框架存取機制才共用。跨模組協調使用公開方法／型別，不能直接操作別人的私有表。Agent Checkpoint 沿官方公開介面，不自製框架資料表或第二套執行權威。

## 2. 依賴方向與可檢查限制

- Domain 不依賴 HTTP、ORM、SDK、Agent 或其他模組的持久層。Application 使用自有 Domain 及窄契約；Infrastructure 實作契約，Presentation 呼叫用例。
- Bundle 與 modules 同層；Bundle 可使用能力公開介面與通用 Plugin 契約，Agent 不反向匯入具體 Bundle。
- Host 使用模組的公開入口組裝具體實作、管理共用資源。組裝時只注入用例所需的依賴。跨模組用例的步驟與提交時機由負責的 Application 決定。整份 Workspace 建立與刪除由 Workspace Application 編排，Host 接上具體資源。
- Host 依賴能力模組及 Bundle，依賴方向由外向內。Shared 不反向依賴能力或 Bundle。
- HTTP 與模型工具是不同接入方式，共用業務用例；工具參數、傳輸 DTO 不流入純 Domain。
- 前端依賴為 `app → features → shared`；feature 之間不直接匯入私有實作。跨功能刷新由 app 組裝，正式資料使用 Query cache，局部輸入由元件管理。

後端 [.importlinter](../../apps/backend/.importlinter)與前端 [ESLint](../../apps/frontend/eslint.config.js)檢查可靜態表達的規則；具體例外須有責任與成本理由，不能藉動態 import、TYPE_CHECKING 或大範圍 ignore 隱藏循環。靜態通過不代表所有業務分責合理。

真正需要替換外部 I/O 或策略時才使用窄 Protocol／callable。Prompt、Tool 或組裝比較在既有責任邊界替換；其他正式保存、取消及恢復路徑共用，不複製整個 Agent 或把旗標散入 Domain。

## 3. 名稱要能表達身分、時間與效果

Python module／函式採 `snake_case`，類型採 `PascalCase`；TypeScript 非元件函式及變數採 `camelCase`，元件與型別採 `PascalCase`。名稱要表達範圍、時點與效果，少數短區域索引可簡短，跨模組結果不能只叫 `data`。

讀取名稱不偷偷保存；`create`、`publish`、`restore`、`cancel` 等須反映真實效果。Service 是用例責任，不是必須的 class 後綴。不為一個函式包 class，也不另造沒有目前消費者的泛用框架。

Workspace、Turn、Step、JD version、Memory publication、模型短碼與正式 UUID 各有身分，不因形狀相似就合併成同一型別或通用 ID。原始訪談、原生模型 items 及既定工具名稱不得因命名整理而改寫。

## 4. 讓修改容易理解

每個不變量、權限及保存條件集中在負責模組；以「改一項行為要同步理解多少責任」檢查內聚，不用檔案數、class 數或層數評分。拆分應沿具體職責，不把一次交易切散到難以找到提交點。

系統文件保留跨模組視角，模組 README 解釋公開能力與局部資料，Bundle README 說明 Plugin、Prompt 與 Tool 接入。詳細欄位沿正式 Schema；圖源只保留一份，各文件引用同一份。

函式、資源、錯誤及測試寫法見[程式撰寫規範](coding-standard.md)，跨邊界格式見[契約策略](contract-strategy.md)。
