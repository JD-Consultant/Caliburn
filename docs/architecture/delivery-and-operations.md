# 交付與運作邊界

標準交付為一個 FastAPI 應用程序、一個 PostgreSQL 與一個 Qdrant。建置後的 Web 由同一應用同源提供；公版解析及本機模型內聚在後端，資料服務一起啟停。部署圖由[系統規格](../../apps/backend/architecture.md#程序與技術)維護。

## 1. 啟動與部署

Docker 沿根 Compose 的 `app`、`postgres`、`qdrant`。先建置與啟動資料服務，再明示遷移，最後啟動應用；日常啟動不自動改 Schema、建索引或下載模型。操作見[快速開始](../operations/getting-started.md)。

原生開發使用 Vite 與後端兩個程序，正式模式只需後端提供 Web。標準 port 與 `/api` 轉接見[原生開發](../operations/native-development.md)。後端使用單 worker，不將記憶體活動鎖描述成多程序鎖。

## 2. 設定與資源

程序環境保存秘密與連線，Agent JSON 保存非秘密模型設定及 Bundle／Plugin 選取。公版配置屬能力模組，不以 Agent 是否啟用為條件。模型權重及來源事先備妥，讀取時不自動下載。

Host 管 client、pool、背景工作、PDF renderer 與公版 worker 的生命週期。關閉先停止准入並等待自有工作收尾，再釋放資源；強制結束可能只保留最後保存點，不等於取消完成。完整流程沿 [Agent](../../apps/backend/src/caliburn/modules/agent/README.md)及[公版模組](../../apps/backend/src/caliburn/modules/occupation_reference/README.md)。

## 3. Web 與正式資料

前端沿正式 OpenAPI 生成契約，Query cache 是伺服器資料來源。未確認草稿、串流與已保存資料分開；未知結果保留輸入並重新查讀，不自動重送。跨檔案切換、刪除與遲到回覆按 scope 隔離。

目前 JD 顯示保存內容，沒有候選採用畫面。未完成或未知輪次在 UI 讓 JD 唯讀；完成輪比較及 JD-only 撤銷沿後端固定版本。具體互動與瀏覽器驗證見[前端 README](../../apps/frontend/README.md)。

## 4. 信任與權限邊界

產品僅供本機單一操作者使用，沒有登入、ACL、多租戶或多人協作。Compose host ports 綁 loopback；不要以容器內監聽 `0.0.0.0` 推定具備公開網路部署的安全邊界。

OpenAI key 只在後端程序環境，不放入 Agent JSON、提示、工具參數、Web 建置、URL 或一般日誌。模型使用外部 API，本機保存不表示資料離線；模型外送與費用須符合實際授權。公版權重與查讀可在本機執行，不代表 Agent provider 也在本機。

訪談、Memory、JD、公版與工具回傳均是資料，不能改變指令或權限。HTTP／工具的可信 scope 由 App 綁定，正式歸屬、來源及寫入資格由各 owner 驗證。內容顯示使用安全 Markdown；日誌與完整工作正文的診斷存取分開，沿[執行證據規範](../standards/coding-standard.md#71-讓執行證據可查可比較可驗證)。
