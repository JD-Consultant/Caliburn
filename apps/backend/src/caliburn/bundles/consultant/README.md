# 顧問 Bundle

顧問 Bundle 提供職務顧問的角色提示、訪談與 JD 寫作方法。它另提供 App 建立工作區時使用的固定開場。工具、上下文、服務、狀態與保存均由各能力提供，顧問 Bundle 沒有自己的資料表。

## 啟用

在 Agent 設定的 `bundles` 陣列加入以下項目。

```json
{"module": "caliburn.bundles.consultant", "config": {}, "plugins": ["consultant"]}
```

`caliburn.bundles.consultant.create_bundle(config)` 接受空設定，提供一個名為 `consultant` 的提示插件。省略 `plugins` 時選用該插件，`"plugins": []` 時不提供顧問提示。比較另一份提示時，可在相同位置換入提供顧問角色的 Bundle，保留其餘能力配置。組裝變更依 Agent 規則管理 `resume_version`。[Agent 組裝設定](../../modules/agent/README.md#明示設定)

維護角色、訪談順序及 JD 寫作判準時，編輯 [instructions.py](instructions.py)。查讀、保存、引用及錯誤修復的工具契約由各能力維護。公版服務由 Host 啟動，Agent 是否取得搜尋及查讀工具由 `job_reference` 插件選取決定。[公版 Bundle](../job_reference/README.md)

## 開場與訪談流程

1. Workspace Application 在同一筆交易保存工作區、空 JD 與 App 開場。Host 將 `OPENING_TEXT` 傳給 Interview 的 `stage_opening`。開場請員工說明目前職位與主要工作，初始化獨立於顧問角色插件的選取。[訪談模組](../../modules/interview/README.md#公開方法)
2. 顧問從員工已說明的工作建立輪廓，先辨認主要工作與本人責任。本輪有公版搜尋工具時，用它來查漏。主要工作足以區分、員工有機會補充後，再挑有實質缺口的工作深入。深問發現新工作時先補進輪廓，再安排後續。有 Plan 寫入工具時可記下本人範圍、進度與重要剩餘工作。選用 `plan_prompt` 時，按各工作大項安排子任務。JD 依正式來源與欄位定義另行編排。[顧問提示](instructions.py) · [Plan Bundle](../plan/README.md)
3. 顧問依本輪提供的工具查讀、提問或編修，依回傳核對結果。JD 編修工具可用時，由 JD 能力驗證並保存；缺少工具時仍可訪談、文字整理，並交代尚未入稿。輪次恢復與取消由 Agent 和各參與能力執行。[JD Bundle](../job_description/README.md) · [Agent 等待回答與取消](../../modules/agent/README.md#等待回答與取消)

## 模型收到的請求

| 請求欄位 | 來源與用途 |
|---|---|
| `instructions` | 顧問 `prompt_sections` 提供角色和工作方法。其他選取的插件可各自提供能力、來源及操作說明。 |
| `tools` | 當次可用工具的名稱、用途與參數 Schema。是否可讀、可寫或可詢問，由各能力的工具宣告決定。 |
| `input` | 本輪輸入、已組入窗口的材料與已配對的工具回傳。App 開場屬於正式訪談，可隨訪談材料提供。Plan、Memory、JD 和訪談依實際選取的能力提供各自的模型投影。 |

上下文中的 Plan、Plan 工具讀取與成功編修指向同一份工作區計畫。以最新已確認的正文與工具結果回報目前狀態。近期正式訪談、本輪正式原話和 `read_interview` 查回的原話使用同一類訪談訊息短碼，符合來源資格的訊息可用來建立 JD 引用。上下文或工具結果帶來的定位和保存效果，由各資料所有者確認。[Context Bundle](../context/README.md) · [Interview Bundle](../interview/README.md) · [Memory Bundle](../memory/README.md) · [Agent 執行流程](../../modules/agent/README.md#執行流程)
