# ADR 0002 — 三個 bounded context,各為模組化單體

- **狀態**:Accepted（2026-06-27）

## 脈絡

要決定服務邊界:該切幾塊?要不要在服務內再拆微服務?

## 決定

維持**三個 bounded context**,語言在三處切換:
- **解析**(`apps/pdf-to-json`)— PDF → OCS JSON 的 ETL。
- **檢索**(`apps/ocs-indexer`)— Qdrant+BGE-M3 知識/查詢服務。
- **著作**(`apps/api` + `apps/web`)— 職務說明書 app + agent。

每個 context = **模組化單體**(modular monolith)。**不更細**(context 內不拆微服務 → 避免 nano-service),**不合併**。

## 後果

- ✅ 對齊 DDD bounded context(邊界畫在語言改變處)。
- ✅ 單人/小團隊適用(微服務在此規模只增成本)。
- ✅ monorepo 內邊界=`apps/` 資料夾,日後要併要拆都是搬資料夾,低風險。
- 判準見 [memory: service-split-framework] / spec §一.3。

依據:Eric Evans(DDD)、Martin Fowler、Sam Newman。
