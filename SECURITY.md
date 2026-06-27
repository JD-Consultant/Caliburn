# Security Policy

## 回報漏洞

請**私下**回報,不要開公開 issue:
- GitHub Security Advisories(本 repo → Security → Report a vulnerability),或
- Email:`<security-contact>`(請填入維護者安全聯絡信箱)。

我們會盡快確認收到並回覆處理時程。請給合理的修補時間後再公開。

## 適用範圍 / 安全姿態

Caliburn 是多租戶 B2B SaaS。安全上特別關注:

- **租戶隔離(最關鍵邊界)**:公司(租戶)間資料必須隔離。實作為 `apps/api` 的 **`tenant_id` + Postgres Row-Level Security (RLS)**(見 [ADR 0006](docs/adr/0006-multitenancy-pool-rls.md))。任何可跨租戶讀寫的問題視為**最高嚴重度**。
- **認證**:外接 B2B IdP(OAuth2/OIDC/JWT);不自行保管密碼。
- **內部服務**:`ocs-indexer`(Qdrant)、Postgres 僅內部、不對公網;只有 `api`/`web` 可達。
- **機密**:`.env` / 金鑰不入版控;依 `pyproject` + lockfile 管依賴。

## 支援版本

產品 pre-launch,僅維護 `master` 最新狀態;尚無多版本支援承諾。
