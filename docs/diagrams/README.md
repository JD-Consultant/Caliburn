# 文件圖源與圖片

本目錄集中現行文件設計圖，供公開責任文件共用。圖源依能力 owner 分目錄，保存 `.mmd`、同名 PNG 與可放大的 SVG。公開圖源只收架構及操作說明所需內容。

產品權責、圖說及適用範圍由各責任文件維護；研究與報告專用圖源留在本機，不列入公開圖庫。圖名保留「現行」「目標／未實作」「候選」或「歷史」，截圖註明日期及受測範圍；集中存放不會改變狀態。

依用途查閱：[讀圖約定](#讀圖約定) · [查找圖源](#按責任文件查圖) · [編輯與重繪](#編輯與重繪)。

## 讀圖約定

各圖的範圍、狀態、省略與產品含義以其圖說為準。以下約定用來對照正文，不藉圖種推導新元件、部署或產品保證。

### 系統、容器、部署及模組關係

按圖例辨認元素種類、邊界、技術及具名單向關係。C4 容器不等於 Docker 容器，模組圖也不表示呼叫順序。依據：[C4 notation](https://c4model.com/diagrams/notation)。

### 基本流程

| 符號 | 意義 |
|---|---|
| 終端形 | 局部起訖 |
| 矩形 | 處理 |
| 菱形 | 互斥分支 |
| 平行四邊形 | 跨邊界資料交接 |
| 兩側雙線矩形 | 另有定義的子流程 |
| 六角形 | 初始化／準備 |
| 箭頭 | 控制順序；暫停與後續接續須有明確條件 |

依據：[Microsoft 流程圖](https://support.microsoft.com/en-us/visio/create-a-basic-flowchart-in-visio)、[Mermaid 形狀](https://mermaid.js.org/syntax/flowchart.html)。

### 時序及狀態

- 同步訊息：實線實心箭頭。
- 非同步訊息：開放箭頭。
- 回覆（reply）：虛線。
- 狀態轉移：分清事件、條件與效果。

圖中終態只屬該圖，不代表業務正式完成。依據：[UML 2.5.1](https://www.omg.org/spec/UML/2.5.1/PDF) §17.4.4、§14.2.4，以及 [Mermaid 時序](https://mermaid.js.org/syntax/sequenceDiagram.html)／[狀態](https://mermaid.js.org/syntax/stateDiagram.html)。

### ER

- **基數**：圈是零、短線是一、鳥足是多；兩端各讀最小／最大基數。
- **關係**：實線識別關係表示父鍵參與子表主鍵，虛線是非識別關係。
- **鍵與約束**：PK／FK／UK 分別為主鍵／外鍵／唯一鍵；複合約束看圖說與 DDL。

關係線不表示提交順序。依據：[Mermaid ER](https://mermaid.js.org/syntax/entityRelationshipDiagram.html)。

### 圖面與正文

正文嵌入 PNG 並附圖源／SVG。更新時核對圖面語意與正文是否一致，檢查解析渲染、中文、裁切、箭線與圖例，並同步引用；能渲染不證明符號或產品契約正確。截圖與既有來源素材保留原格式與位元組，搬移時核對雜湊及來源說明。

## 按責任文件查圖

| 責任文件 | 圖面內容 | 圖源目錄 |
|---|---|---|
| [ Workspace 模組](../../apps/backend/src/caliburn/modules/workspace/README.md) | 直接歸屬 ER、Workspace 整份刪除與清理流程 | [來源](workspace/) |
| [模型短碼](../../apps/backend/src/caliburn/modules/model_references/README.md) | 持久短碼映射、Workspace FK 與唯一性 | [來源](model-references/) |
| [公版模組](../../apps/backend/src/caliburn/modules/occupation_reference/README.md) | 匯入、索引、搜尋與固定來源回讀 | [來源](occupation-reference/) |
| [ JD 模組](../../apps/backend/src/caliburn/modules/job_description/README.md) | Application 接線、關聯式內容、完整快照與來源引用 ER | [來源](job-description/) |
| [ Plan 模組與 Bundle](../../apps/backend/src/caliburn/modules/plan/README.md) | 單一聚合根、目前正文與恢復快照 ER；編修、取消與下一輪窗口時序 | [來源](plan/) |
| [訪談模組](../../apps/backend/src/caliburn/modules/interview/README.md) | 輪次、逐題訊息及同輪回答外鍵 ER | [來源](interview/) |
| [ Memory 模組](../../apps/backend/src/caliburn/modules/memory/README.md) | 單根、情境／理解與完整發布三表 ER | [來源](memory/) |
| [ Agent 模組](../../apps/backend/src/caliburn/modules/agent/README.md) | 固定組裝、四接點 Loop／State、同 Thread 輪次、工具 wrapper、人工回答與取消收尾 | [來源](agent/) |
| [系統責任規格](../../apps/backend/architecture.md) | 系統邊界、模組歸屬、應用／資料容器、資料權責；引用局部流程，不複製圖源 | [來源](system/) |
| [插件分責](../../apps/backend/architecture.md#4-bundleplugin-與依賴) | Host、通用 Core、能力模組與 Bundle 的靜態依賴 | [來源](agent/plugin-dependencies.mmd) |
| [問答分責](../../apps/backend/src/caliburn/modules/human_questions/README.md) | 問答能力、提問工具與通用恢復時序 | [來源](human-questions/) |
| [ JD Bundle](../../apps/backend/src/caliburn/bundles/job_description/README.md) | 工具參數、可信執行資料與 JD 交易接線 | [來源](bundles/job-description/) |
| [ Memory Bundle](../../apps/backend/src/caliburn/bundles/memory/README.md) | 固定訪談窗口、B1／B2、發布與後續換窗 | [來源](bundles/memory/) |
| [ Context Bundle](../../apps/backend/src/caliburn/bundles/context/README.md) | 輪首換窗、歷史壓縮與每個模型步前的原生壓縮 | [來源](bundles/context/) |

## 圖面重用

同一張公開設計圖只維護一份可編輯圖源，引用方補充其視角與省略範圍。

系統的 README 層次沿[文件分責](../../apps/backend/architecture.md#10-readme-與圖面的閱讀層次)：系統放跨模組視角；模組放局部流程、資料與交易；Bundle 放配置與 Agent 接入，只有複雜流程才另畫圖。圖源按負責能力歸檔，正文各自引用同一 PNG／SVG，不在每個 README 再存一份圖片。

## 編輯與重繪

每組 Mermaid 設計圖維持同名 `.mmd`、`.svg`、`.png`。修改節點、形狀或連線時，只編輯 `.mmd` 再重繪。產圖器遍歷受維護正文的圖片引用，略過 `screenshots/`，核對中央圖源並依來源路徑去重；新增設計圖須同時接好責任正文的圖片與圖源連結。

`%% title:` 提供獨立圖片的圖名與狀態，未提供時取責任正文的圖片 alt；`%% legend:` 提供必要圖例。既有 `%% diagram:` 只作唯一性檢查，不是產品 ID，也不需要再維護報告對應程式表。

在 repository 根目錄執行；先以 `pnpm install --frozen-lockfile` 安裝根開發依賴。Mermaid 是文件工具，不加入產品執行依賴。

```powershell
npm install --prefix .tmp/doc-diagram-runtime --no-save --package-lock=false mermaid@12.1.0
pnpm exec playwright install chromium
node scripts/render-doc-diagrams.mjs --list
node scripts/render-doc-diagrams.mjs --mermaid-dir .tmp/doc-diagram-runtime/node_modules/mermaid/dist --output .tmp/doc-diagrams
```

已有相容 Chromium 可加 `--browser <執行檔路徑>`。`--select <路徑>` 可指定圖源、引用正文或其目錄，且可重複使用，只重繪本次修改的圖；不加則渲染全部。`--list` 只驗證及列出來源／引用，不需要瀏覽器或 Mermaid。

```powershell
node scripts/render-doc-diagrams.mjs --mermaid-dir .tmp/doc-diagram-runtime/node_modules/mermaid/dist --select docs/diagrams/agent --output .tmp/doc-diagrams-agent
```

命令更新圖源旁的 SVG／PNG；`--output` 只指定本次驗證 manifest 的暫存目錄。每份 manifest 記錄成功時間、發現總數、選中數、所有正文引用，以及 renderer／圖源／輸出的 SHA256；局部重繪不能當成全圖驗證。`--list` 的現有輸出 hash 只是盤點，不代表本次已重新渲染。中央圖源缺正文引用、受維護正文仍留內嵌 Mermaid、來源不存在或 marker 重複時直接報錯。

### 產圖細節

渲染鎖定 Mermaid 12.1.0、`theme: neutral`、`securityLevel: strict` 及本機中文字型。工具只啟動 loopback 的本機資源伺服器，不載入 CDN。圖的 ID 帶文字前綴，避免數字開頭造成 CSS selector 失效，見 [MDN ID selectors](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Selectors/ID_selectors)。

解析後以 `XMLSerializer.serializeToString()` 序列化 SVG DOM，保留 XHTML 的命名空間並正確關閉標籤；不用 HTML 字串或逐一替換 `<br>` 補 XML。依序確認 SVG 可解析、以獨立 `Image.decode()` 載入，再產生 2 倍 PNG，見 [MDN XMLSerializer](https://developer.mozilla.org/en-US/docs/Web/API/XMLSerializer/serializeToString)。SVG 保留文字與向量，PNG 供正文穩定顯示。

內容相同時不重寫；異動先寫完整新檔再替換，完整渲染成功才寫本次 manifest。仍須確認 manifest 是否屬本次成功執行，不能把先前輸出當作本次結果。

完成後逐圖檢查中文、裁切、節點含義、分支、箭頭與圖例，再核正文引用。能渲染不等於符合圖種語意，圖面通過也不代表產品或模型品質通過。
