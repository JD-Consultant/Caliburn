# Security Policy

## 回報漏洞

請私下回報，不要開公開 issue：

- GitHub Security Advisories（本 repository → Security → Report a vulnerability）；或
- Email：`f1206009@cloud.dyu.edu.tw`

請附上可重現條件、影響範圍與必要的最小證據，並給予合理修補時間後再公開。

## 現行安全邊界

Caliburn 目前是單一操作者的本機 Web App，不是多租戶 SaaS，也沒有登入、OAuth／OIDC、JWT、ACL、
Row-Level Security 或公網部署承諾。安全重點是：

- API 與 Web 僅在受控本機環境使用；API 綁 loopback，unsafe request 必須符合已設定的 Origin 與資料集身分。
- PostgreSQL 保存 JD、對話、執行狀態與 Memory；普通啟動不自動 migration、清資料或重建資料庫。
- OpenRouter key 只存同一 Windows 使用者的 Windows 認證管理員，不進 `.env`、App 設定、資料庫、前端、log 或 Git。
- 有副作用的寫入使用 request identity、版本條件與永久 receipt；transport 結果不明時不能盲目重送。
- RAG 服務是隔離、明示啟用的本機 bounded context，不是正式 JD App 的隱含依賴。

若未來加入登入、多使用者、公網或雲端部署，必須先重新定義威脅模型與資料隔離；目前文件不能被解讀為已提供這些能力。

## 支援版本

產品仍在 pre-launch；只維護 `main` 最新狀態，尚無多版本安全更新承諾。
