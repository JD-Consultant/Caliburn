# R01／R01-F 封存重現補充

原 README 與 RESULTS 保留各次範圍及結果。此目錄不含 node_modules／cache；請複製到可寫暫存目錄 `jd-editor-review-probe`，依 package-lock 使用 `npm ci --ignore-scripts --no-audit --no-fund`，從該目錄執行原腳本。Node 固定 v22.12.0。

- `node review-probe.mjs`：另建新時間結果，預期原四組 2 PASS／2 FAIL、exit 1，不覆寫已封存 run。
- `node review-order-followup.mjs`：使用已封存、固定的原 R3 pending 檔案，預期四組 3 PASS／1 FAIL、exit 1。腳本末段為保存來源副本，另要求相鄰 `../jd-oss/plate/packages/suggestion/src/lib/utils/SkipSuggestionDeletes.ts`；將封存 `results/order-followup-2026-09-09T14-53-39-183Z/SkipSuggestionDeletes.source.ts` 原樣複製到此暫存位置即可，勿改原 script 或測試資料。

`capture-source.mjs` 是當時擷取已下载官方原始碼的輔助程式，重跑功能不需要它；原 selected source 已封存。所有雜湊比對見 results/artifact-hashes.json。這份重現說明是封存補充，不列入原執行前 README hash。
