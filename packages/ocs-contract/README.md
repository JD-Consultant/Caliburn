# ocs-contract

本套件定義 OCS 文件交換的型別與結構。唯一來源是 `schema/ocs-document.schema.json`；
`src/ocs_contract/models.py` 與 `types/ocs-document.ts` 都由它生成，不可手改。

目前消費者是 `apps/pdf-to-json` 的輸出驗證與 `apps/ocs-indexer` 的 ingestion。
它屬於獨立 RAG bounded context。正式 JD App 使用自己的 contract；已退役的 legacy Web 也不消費本套件。

```bash
pnpm --filter @caliburn/ocs-contract run codegen
pnpm --filter @caliburn/ocs-contract run check-codegen
```

`check-codegen` 會呼叫 `bash scripts/check-codegen.sh`。Windows PowerShell 環境須可使用 Git Bash／
WSL Bash（或直接從 Bash 執行）；這不是原生 PowerShell script。

> **已知風險（2026-10-02 靜態查核，尚未修正）：**目前 `check-codegen` 先生成至 tracked 檔案，差異分支會執行 `git checkout --`，可能覆寫這兩份生成檔的未提交修改；它不是唯讀檢查。不要在含未保存修改的工作目錄執行。後續應改為暫存生成再比較，並驗證原工作檔不變；本次整理未執行此命令或修改腳本。

schema 變更後先執行 `codegen` 並檢查生成 diff；不要直接編輯 Python／TypeScript 生成檔。
