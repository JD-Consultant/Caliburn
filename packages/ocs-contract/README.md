# ocs-contract

本套件定義 OCS 文件交換的型別與結構。唯一來源是 `schema/ocs-document.schema.json`；
`src/ocs_contract/models.py` 由它生成，不可手改。已無消費者的 TypeScript 產物與後處理鏈已移除。

目前消費者是 `apps/pdf-to-json` 的輸出驗證與 `apps/ocs-indexer` 的 ingestion。
它屬於獨立 RAG bounded context。正式 JD App 使用自己的 contract；已退役的 legacy Web 也不消費本套件。

```bash
pnpm --filter @caliburn/ocs-contract run codegen
pnpm --filter @caliburn/ocs-contract run check-codegen
```

兩個命令使用本套件鎖定的 Python 生成器，Windows PowerShell 與 POSIX 使用相同入口。
`check-codegen` 只在暫存目錄生成，再比較 Python 正文（容許 checkout 的 LF／CRLF 差異）；
一致、不一致及生成器失敗都不修改原檔或 Git index。不一致回非零，明確執行 `codegen` 才寫入。

檢查器回歸：`pnpm --filter @caliburn/ocs-contract test`，涵蓋原檔 bytes／mtime 保留及失敗情境。

schema 變更後先執行 `codegen` 並檢查生成 diff；不要直接編輯 Python 生成檔。
