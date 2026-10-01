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

> **已知風險（2026-10-02 靜態查核，尚未修正）：**目前 `check-codegen` 先生成至 tracked 檔案，差異分支會執行 `git checkout --`，可能覆寫這兩份生成檔的未提交修改；它不是唯讀檢查。不要在含未保存修改的工作目錄執行。後續應改為暫存生成再比較，並驗證原工作檔不變；本次整理未執行此命令或修改腳本。

schema 變更後先執行 `codegen` 並檢查生成 diff；不要直接編輯 Python／TypeScript 生成檔。
