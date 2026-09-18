# ADR 0006 — 多租戶 Pool + Postgres RLS

- **狀態**:Accepted（2026-06-27;**登入功能實作時落地**)

## 脈絡

產品是給顧問用的多租戶 B2B SaaS:顧問跨多家客戶公司、公司間資料隔離。要選租戶隔離模型 + 認證方案。

## 決定

- **隔離模型:Pool**(共用 DB + `tenant_id` 欄 + **Postgres RLS** 強制隔離)起步;保留升級 **silo**(DB-per-tenant)給未來高價值/合規客戶(動態多租戶)。
- **租戶隔離只在 `apps/api`**;`ocs-indexer`/`pdf-to-json` 是全域共享知識,不多租戶化。
- **Organizations 模型**:顧問可跨多 org,每請求 scope 到一個 tenant。
- **認證**:外接 B2B IdP(WorkOS/Clerk,Organizations 一等支援),OAuth2/OIDC/JWT;別自己造 auth、別用 Auth0 硬湊。auth = `apps/api/auth/` 模組 + `apps/web` 當 OAuth client。
- **紀律:`tenant_id` 從第一天就埋進 schema**,即使登入晚做。
- 部署偏好:**先自架**(基礎設施;auth 真做時自架 Keycloak,別手刻)。

## 後果

- ✅ 便宜、可擴展;RLS 在 DB 層強制隔離(不靠應用層記得加 WHERE)。
- ✅ 可平滑升級 silo。
- ⏳ 尚未實作(登入功能尚未做)。
- ❓ 待釐清:是否有客戶/法規現在就要求實體隔離 → 該類客戶直接 bridge/silo。

依據:AWS Well-Architected SaaS Lens、Microsoft Azure(multitenancy)、OAuth2/OIDC。
