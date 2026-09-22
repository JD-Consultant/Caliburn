# ocs-contract

OCS 文件 seam 的 typed contract。`schema/ocs-document.schema.json` 是唯一 source of truth；
`src/ocs_contract/models.py` 與 `types/ocs-document.ts` 都是生成物，不可手改。

目前消費者是 `apps/pdf-to-json` 的輸出驗證與 `apps/ocs-indexer` 的 ingestion。
它屬於隔離 RAG bounded context，不是正式 JD App contract，也沒有 legacy Web consumer。

```bash
pnpm --filter @caliburn/ocs-contract run codegen
pnpm --filter @caliburn/ocs-contract run check-codegen
```

`check-codegen` 會呼叫 `bash scripts/check-codegen.sh`。Windows PowerShell 環境須可使用 Git Bash／
WSL Bash（或直接從 Bash 執行）；這不是原生 PowerShell script。

schema 變更後先執行 `codegen` 並檢查生成 diff；不要直接編輯 Python／TypeScript 生成檔。
