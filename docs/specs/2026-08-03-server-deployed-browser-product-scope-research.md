# Caliburn 伺服器部署與瀏覽器產品範圍校正

- 日期：2026-08-03
- 狀態：支援 owner 已確認的產品範圍校正
- 範圍：產品執行位置、使用者存取方式、第一個部署單元，以及不因此自動成立的 SaaS／身分能力

## 診斷

現行權威文件把兩種不同的「本地」混為一談：

1. **員工個人本機應用**：Web、API、資料庫與模型周邊服務全部在每位員工電腦執行，使用者開 `localhost`。
2. **企業本地伺服器部署**：服務在企業管理的伺服器或私有環境執行，員工從其他電腦以瀏覽器存取。

Owner 已明確否決第一種產品定位。Caliburn 應由企業或我們操作伺服器，使用者只需要瀏覽器；未來可以延伸為企業網路應用。
開發者在自己電腦使用 `localhost` 仍是開發環境，不再代表產品交付邊界。

## 權威資料

| 來源 | 與本決策的關係 |
|---|---|
| [Docker：Use Compose in production](https://docs.docker.com/compose/how-tos/production/) | Docker 官方明確支援以額外 production Compose 設定在單一伺服器部署，並建議調整 image、port、environment、restart 與 logging。現有 Compose 可演進，不必先上 Kubernetes。 |
| [Microsoft Azure：Deployment Stamps pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/deployment-stamp) | 同一套 application／datastore 可成組部署為獨立 stamp；每個 stamp 可服務單一或一組客戶，並獨立部署與更新。 |
| [Microsoft Azure：Tenancy models](https://learn.microsoft.com/en-us/azure/architecture/guide/multitenant/considerations/tenancy-models) | 單一企業專屬 deployment 可用基礎設施隔離資料，無須立刻在 application layer 實作共享多租戶。 |
| [NIST SP 800-207A](https://csrc.nist.gov/pubs/sp/800/207/a/final) | 企業內網位置本身不應被當成使用者或服務身分；對外或多人存取前仍須明確的 authentication／authorization policy。 |
| [OpenID Connect Core 1.0](https://openid.net/specs/openid-connect-core-1_0-final.html) | 若後續需要登入，OIDC 提供可互通的外部身分層，較適合企業 SSO，無須先自建帳號密碼。 |
| [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/) | 瀏覽器 Web application 應以可驗證的安全控制為 release 條件；不能因部署在企業內網就省略威脅模型。 |

## 選項

### A. 每位員工電腦各自執行完整 stack

優點是沒有共享伺服器與身分系統。缺點是每台電腦都要承擔 PostgreSQL、Qdrant、GPU embedder、升級、備份與故障排除，
也無法符合 owner 指定的「企業或我們運行伺服器、瀏覽器即可存取」。否決。

### B. 單一企業部署單元，可由企業自管或我們代管

同一套 Web／API／PostgreSQL／Qdrant／embedder stack 形成一個可重複部署單元；一個 deployment 第一階段服務一個企業。
企業自管時部署於內網／私有環境，我們代管時部署於我們控制的基礎設施。使用者只接觸 HTTPS browser UI。
這保留最大資料隔離，也不要求先建共享租戶 control plane。採用。

### C. 立即建立共享多租戶 SaaS

可集中營運多家企業，但需要 tenant routing、organization/member、ACL、身分、onboarding、跨租戶安全測試、quota／billing
與 control plane。這些都不是本次校正所授權的產品能力。延後，若商業模式確定再另開研究與 ADR。

## 校正後的部署語言

- **Caliburn deployment**：一套可獨立安裝、設定、升級、備份與還原的 Caliburn 服務及資料。
- **企業自管部署**：deployment 由企業在自己的伺服器、內網或私有環境操作。
- **我們代管部署**：deployment 由 Caliburn 團隊操作，使用者透過核准網址存取。
- **瀏覽器使用者**：只操作 Web UI，不負責啟停服務、設定 port、資料庫、GPU 或 OpenRouter key。
- **開發環境 localhost**：開發者用的執行 profile，不是產品型態。

## 現行範圍與延後決策

第一個 production target 是**單一 deployment、單一企業**。這不建立共享多租戶 SaaS，也不恢復 ADR 0006 的 Pool + RLS
產品模型。多人並行、角色、企業 SSO 與 managed-hosted 對外暴露的 access policy 必須在 R8 production deployment 前另開
研究與 ADR；在那之前不得用「內網可信」假設取代 authentication／authorization 設計。

R1–R7 的職務分析、Evidence、proposal、current-row 與真人 pilot gate 不因部署位置改變。受影響的是 orientation、
產品範圍、R8 release candidate、production Compose／TLS／secret／backup 的交付條件，以及規劃中的 `local_workspace` 命名。

## 文件處理

- 新 ADR 取代 ADR 0039、0041、0043 的「員工電腦 localhost」部署字句，但保留其文件權威、單寫者切換與真人 pilot 決策。
- Accepted ADR 不回寫；以 ADR 0057 與索引標示 partial supersession。
- 歷史研究保留原文；現行 orientation、living design、active roadmap 與 plan 直接校正並鏈回 ADR 0057。
- 規劃中的 `local_workspace` 改名 `job_workspace`，避免 deployment topology 滲入 domain/application seam。
