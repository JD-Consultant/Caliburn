# 文件圖源與圖片

本目錄集中文件設計圖與產品截圖，供公開責任文件共用。設計圖依責任文件分目錄，保存 `.mmd` 圖源、同名 PNG 與可放大的 SVG；產品截圖放在 `screenshots/`。公開圖源只收架構及操作說明所需內容。

產品權責、圖說及適用範圍仍由各責任文件維護；本頁只提供路由與重繪方式。圖名保留「現行」「目標／未實作」「候選」或「歷史」，截圖註明日期及受測範圍；集中存放不會改變狀態。符號定義依[文件與圖面規範](../standards/documentation-standard.md#3-圖面種類與符號)。研究與報告專用圖源留在本機，不列入公開圖庫。

## 產品截圖

| 圖片 | 日期、用途與來源 |
|---|---|
| [職務檔案清單](screenshots/job-file-list.jpg) | 2026-10-05，呈現改名與刪除入口；此圖只展示操作位置，不是行為驗收證據 |

截圖保留原始格式，不配 `.mmd` 或衍生 SVG，也不交由 Mermaid 重繪。

## 按責任文件查圖

| 責任文件 | 圖面內容 | 圖源目錄 |
|---|---|---|
| [產品介紹](../product/README.md) | 使用者的核心流程 | [來源](product/README/) |
| [架構入口](../architecture/README.md) | 操作者主要流程 | [來源](architecture/README/) |
| [系統邊界](../architecture/system-boundaries.md) | C4 情境、容器 | [來源](architecture/system-boundaries/) |
| [保存與恢復](../architecture/persistence.md) | Plan 採用、已提交操作恢復 | [來源](architecture/persistence/) |
| [交付與運作](../architecture/delivery-and-operations.md) | 部署、選用 RAG 容器 | [來源](architecture/delivery-and-operations/) |
| [程式組織](../standards/code-organization.md) | 模組依賴 | [來源](standards/code-organization/) |
| [Agent 執行](../implementation/agent-execution.md) | 歷史、Step、迴圈、控制、準備、補存 | [來源](implementation/agent-execution/) |
| [模型外送](../implementation/model-requests.md) | 請求與結算、預算、重試 | [來源](implementation/model-requests/) |
| [訪談保存](../implementation/interview-storage.md) | 訪談及執行關係 | [來源](implementation/interview-storage/) |
| [Memory 保存](../implementation/memory-storage.md) | 批次發布、修訂、候選與快照 | [來源](implementation/memory-storage/) |
| [JD 保存](../implementation/jd-storage.md) | 資料關係、修訂讀取、人工編輯、候選 | [來源](implementation/jd-storage/) |
| [介面與交付](../implementation/interface-and-delivery.md) | 命令重送、串流、來源查詢 | [來源](implementation/interface-and-delivery/) |

## 圖面重用

同一張公開架構圖只維護一份圖源；引用方補充其視角與省略範圍。私人報告及研究的專用圖源不納入公開清單。

## Agent 六張流程圖

| 要看什麼 | 圖片 | 可編輯來源 |
|---|---|---|
| 跨工作採用哪份歷史 | [查看](implementation/agent-execution/history-adoption.png) | [Mermaid](implementation/agent-execution/history-adoption.mmd) |
| 單次模型及工具 Step | [查看](implementation/agent-execution/model-tool-step.png) | [Mermaid](implementation/agent-execution/model-tool-step.mmd) |
| 多 Step 如何接續 | [查看](implementation/agent-execution/response-loop.png) | [Mermaid](implementation/agent-execution/response-loop.mmd) |
| 暫停、續作及 final 如何分流 | [查看](implementation/agent-execution/step-control.png) | [Mermaid](implementation/agent-execution/step-control.mmd) |
| 輪前歷史如何準備 | [查看](implementation/agent-execution/history-preparation.png) | [Mermaid](implementation/agent-execution/history-preparation.mmd) |
| 原件保存失敗如何補存 | [查看](implementation/agent-execution/result-save-recovery.png) | [Mermaid](implementation/agent-execution/result-save-recovery.mmd) |

## 編輯與重繪

每組 Mermaid 設計圖維持同名 `.mmd`、`.svg`、`.png`。修改節點、形狀或連線時，只編輯 `.mmd` 再重繪。產圖器遍歷受維護正文的圖片引用，略過 `screenshots/`，核對中央圖源並依來源路徑去重；新增設計圖須同時接好責任正文的圖片與圖源連結。`%% title:` 提供獨立圖片的圖名與狀態，未提供時取責任正文的圖片 alt；`%% legend:` 提供必要圖例。既有 `%% diagram:` 只作唯一性檢查，不是產品 ID，也不需要再維護報告對應程式表。

在 repository 根目錄執行；先依 Web README 安裝既有開發依賴。Mermaid 是文件工具，不加入產品執行依賴。

```powershell
npm install --prefix .tmp/doc-diagram-runtime --no-save --package-lock=false mermaid@12.1.0
npm --prefix apps/web exec -- playwright install chromium
node scripts/render-doc-diagrams.mjs --list
node scripts/render-doc-diagrams.mjs --mermaid-dir .tmp/doc-diagram-runtime/node_modules/mermaid/dist --output .tmp/doc-diagrams
```

已有相容 Chromium 可加 `--browser <執行檔路徑>`。`--select <路徑>` 可指定圖源、引用正文或其目錄，且可重複使用，只重繪本次修改的圖；不加則渲染全部。`--list` 只驗證及列出來源／引用，不需要瀏覽器或 Mermaid。舊 `--reports` 命令仍接受，會提示報告已納入預設範圍，不再生成第二組報告圖片。

```powershell
node scripts/render-doc-diagrams.mjs --mermaid-dir .tmp/doc-diagram-runtime/node_modules/mermaid/dist --select docs/diagrams/implementation/agent-execution --output .tmp/doc-diagrams-agent
```

命令更新圖源旁的 SVG／PNG；`--output` 只指定本次驗證 manifest 的暫存目錄。每份 manifest 記錄成功時間、發現總數、選中數、所有正文引用，以及 renderer／圖源／輸出的 SHA256；局部重繪不能當成全圖驗證。`--list` 的現有輸出 hash 只是盤點，不代表本次已重新渲染。中央圖源缺正文引用、受維護正文仍留內嵌 Mermaid、來源不存在或 marker 重複時直接報錯。

### 產圖細節

渲染鎖定 Mermaid 12.1.0、`theme: neutral`、`securityLevel: strict` 及本機中文字型。工具只啟動 loopback 的本機資源伺服器，不載入 CDN。圖的 ID 帶文字前綴，避免數字開頭造成 CSS selector 失效，見 [MDN ID selectors](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Selectors/ID_selectors)。

解析後以 `XMLSerializer.serializeToString()` 序列化 SVG DOM，保留 XHTML 的命名空間並正確關閉標籤；不用 HTML 字串或逐一替換 `<br>` 補 XML。依序確認 SVG 可解析、以獨立 `Image.decode()` 載入，再產生 2 倍 PNG，見 [MDN XMLSerializer](https://developer.mozilla.org/en-US/docs/Web/API/XMLSerializer/serializeToString)。SVG 保留文字與向量，PNG 供正文穩定顯示。

內容相同時不重寫；異動先寫完整新檔再替換，完整渲染成功才寫本次 manifest。仍須確認 manifest 是否屬本次成功執行，不能把先前輸出當作本次結果。

完成後逐圖檢查中文、裁切、節點含義、分支、箭頭與圖例，再核正文引用。能渲染不等於符合圖種語意，圖面通過也不代表產品或模型品質通過。
