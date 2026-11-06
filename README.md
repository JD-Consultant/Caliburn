# Caliburn

**從實際工作出發，透過 AI 訪談建立有依據的職務說明書。**

Caliburn 是本機 Web AI 職務分析工具。員工說明日常工作，AI 顧問依回答釐清責任、方法與條件，逐步整理職務說明書（JD）。訪談與 JD 放在同一工作區，可回查來源、人工編修、比較歷史及匯出 PDF。

## 可以做什麼

- 引導訪談與逐題問答，保留員工補充、更正及來源。
- 管理多份資料隔離的職務檔案，同頁查看訪談與 JD。
- 編修結構化 JD，查閱完整版本、比較差異與恢復內容。
- 以工作情境與工作理解延續長訪談，保留已發布版本及引用。
- 查看 AI 處理紀錄、恢復未完成輪次及取消；完成輪可在安全條件成立時只撤銷該輪 JD 改動。
- 查找公版職能資料，作為追問與查漏的參考；公版不代表員工實際負責的工作。
- 匯出目前保存 JD 的 PDF，之後仍可繼續訪談與編修。

JD 修改按操作保存並留歷史；整輪取消由各模組撤回本輪效果。畫面上的未保存輸入與串流片段不等於正式資料。

## 開始使用

依[快速開始](docs/operations/getting-started.md)啟動單一應用程式、PostgreSQL 與 Qdrant。AI 訪談須配置 Agent 與 OpenAI API key；未啟用 Agent 時仍可管理檔案、人工編修及使用已配置的 PDF 匯出。公版搜尋另需事先準備來源、模型權重及索引。

服務僅供本機單一操作者使用，尚無登入或多人協作。

程式位於 [apps/backend](apps/backend/README.md) 與 [apps/frontend](apps/frontend/README.md)，系統分責見[架構導覽](ARCHITECTURE.md)。開發見[貢獻指南](CONTRIBUTING.md)，日常啟停、更新與備份見[操作手冊](docs/operations/README.md)。

## 延伸閱讀

- [產品介紹](docs/product/README.md)：使用情境與內容品質判準。
- [架構導覽](docs/architecture/README.md)：能力模組、Agent 插件與資料責任。
- [文件導覽](docs/README.md)：開發、操作及驗證入口。

## 授權

本專案自有程式與文件採 [MIT 授權](LICENSE)。第三方元件、字型、模型及外部資料依各自授權使用；見[第三方聲明](apps/backend/THIRD_PARTY_NOTICES.md)。
