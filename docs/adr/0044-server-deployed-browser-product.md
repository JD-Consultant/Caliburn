# 0044. 伺服器部署、瀏覽器存取的產品交付邊界

- 狀態：**Accepted**（owner 於 2026-08-03 明確要求校正）
- 日期：2026-08-03
- 範圍：Caliburn 第一版的執行位置、存取方式與 deployment isolation
- 部分取代：[0039](0039-local-multi-document-canonical-public-form-workspace.md)、
  [0041](0041-document-boundary-single-writer-cutover.md)、[0043](0043-real-employee-pilot-release-gate.md) 中的
  員工電腦／localhost 產品部署假設；其 current-row、單寫者切換與真人 pilot 決策繼續有效
- 研究：[伺服器部署與瀏覽器產品範圍校正](../specs/2026-08-03-server-deployed-browser-product-scope-research.md)

## 脈絡

現行 orientation 把 Caliburn 定義為每位員工電腦各自執行 Web、API 與資料服務的 localhost 應用；owner 已澄清正確產品
是由企業或我們操作伺服器，使用者以瀏覽器存取。若只改 UI 用語而不改部署 authority，後續 R8 仍會產生錯誤的安裝、
安全、備份與維運邊界；但直接恢復早期共享多租戶 SaaS 又會把尚未要求的 control plane、ACL、計費與租戶路由帶回主線。

## 決定

1. Caliburn 是**伺服器部署、瀏覽器存取**的 AI 職務分析與職務說明書 Web application。Web、API、PostgreSQL、Qdrant、
   embedder 與 server secrets 在 deployment 端運行；使用者裝置只需瀏覽器。
2. 同一套 deployable stack 支援兩個營運 profile：企業在內網／私有環境操作的**企業自管部署**，以及由我們操作的
   **我們代管部署**。開發者 localhost 只屬 development profile。
3. 第一個 production scope 採**單一 deployment、單一企業**。若由我們服務多家企業，初期可使用彼此獨立的 deployment；
   本決策不建立共享多租戶 application、tenant control plane、organization/member、ACL、quota、billing 或 tenant admin。
4. 規劃中的 Web/API application seam 從 `local_workspace` 改稱 `job_workspace`；deployment topology 不進入 domain 名稱。
5. R8 必須交付可重複的 server production profile，包含 browser ingress、TLS、server-side secret、persistent data、migration、
   health、backup／restore 與 upgrade／rollback。單一伺服器先採 production Compose；不因未驗證的規模先導入 Kubernetes。
6. 本 ADR 不決定多人角色或登入產品。任何能被多名使用者或非受控網路存取的 deployment，在 R8 暴露前必須另案固定
   authentication／authorization 與 actor／organization scope；優先評估 OIDC／企業 SSO，不先自建密碼系統。
7. ADR 0040／0042 的顧問與職務分析 gate、ADR 0041 的 document-boundary single writer、ADR 0043 的真實員工 pilot
   仍成立。R1–R7 不為部署平台而延後，也不得把「未做共享 SaaS」誤寫成「只能在員工電腦 localhost」。

## 後果

使用者不再負責安裝與維運完整資料／GPU stack，企業自管與我們代管可共享相同 application artifact。代價是 R8 增加正式
server deployment、安全與維運 gate；在 access model 定案前，production exposure 仍被阻擋。早期 ADR 0006 的 Pool + RLS
不因本決策復活；未來若確定共享多租戶商業模式，必須再以新 ADR 取代本決策的單企業 deployment scope。
