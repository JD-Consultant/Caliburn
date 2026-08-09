# ocs-contract

OCS 文件 seam 的 typed contract。`schema/ocs-document.schema.json` 是唯一 source of truth；
`src/ocs_contract/models.py` 與 `types/ocs-document.ts` 都是生成物，不可手改。

主要消費者：`apps/pdf-to-json` 的輸出驗證、`apps/ocs-indexer` 的 ingestion，以及仍可執行的
legacy OCS Web（`apps/web` 的 legacy editor）。它不屬於 current `job_analysis` Current JD contract。

```bash
npm run codegen -w @caliburn/ocs-contract
npm run check-codegen -w @caliburn/ocs-contract
```

schema 變更後先執行 `codegen` 並檢查生成 diff；不要直接編輯 Python／TypeScript 生成檔。
