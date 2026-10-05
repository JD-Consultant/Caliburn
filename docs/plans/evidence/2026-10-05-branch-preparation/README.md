# 分支整理與推送準備

2026-10-05。使用者授權整理全部已完成工作，包含公版檢索、Agent 工具、Memory 指引、Docker、文件、實驗及 MIT 授權。這份記錄保存本次提交範圍與工程驗證，不取代各功能的設計與實驗判準。

## 分支與工作目錄

- 基準：`origin/main`，`13c0663a7d42e2e73b5c2ef45d20faa9e1b1fa11`；fetch 後與本機 `main` 一致。
- 工作分支：`reference-and-maintenance`，由原 `jd-app-docker` 改名，依使用者指定不加代理工具前綴。
- `target-rebuild` 已合併至 `main`，遠端也已移除；本次以 `git branch -d` 移除本機舊分支。
- 唯一 worktree 為 `S:/caliburn`，無其他 attached 或待清理的 worktree。保留工作目錄及原資料。

## 提交分組

| 順序 | 內容 |
|---|---|
| 1 | MIT 授權與套件宣告 |
| 2 | PDF to JSON 的完整內容解析、來源保真、契約及測試 |
| 3 | 獨立 RAG 職位參考 API、兩路召回、rerank 及固定來源讀取 |
| 4 | 可選公版工具、排除範圍保存、角色接線及 Memory 讀取指引 |
| 5 | 本機 Docker 啟動配置與後端入口 |
| 6 | 檢索與 Memory 實驗、研究、完整原件及大檔保存方式 |
| 7 | 產品 README、架構各層、分析指南、操作手冊與專題報告 |

## 本次驗證

完整結果摘要與命令見 [verification.json](verification.json)。

| 層級 | 實際結果 |
|---|---|
| 正式根閘門 `pnpm check` | ESLint、Prettier、Ruff、TypeScript、mypy、契約生成核對與 production build 通過；mypy 319 個來源檔，Ruff format 480 個檔案 |
| 根閘門測試 | 啟動器 5、後端單元／契約 1,402、前端 270 項通過 |
| PDF to JSON | 完整本機測試 67 項通過 |
| 獨立 RAG／embedder | 86 項通過，provider 與 GPU 使用測試替身；包含 QdrantLocal 契約 |
| 公版工具真 PostgreSQL | 六組保存／恢復／重入測試 55 項通過；只操作明示隔離 `_test` 資料庫的自有隨機 schema |
| 專題報告 | 兩個數據核對程式及核對程式本身的 3 項測試通過 |
| 文件導覽 | 329 份文件的 2,800 個本地連結與錨點通過；修正一處過期報告錨點 |
| Docker 配置 | 使用合成設定執行 `docker compose -f compose.jd-app.yaml config --quiet` 通過；本次沒有重新建置映像或啟動產品 |

首次根閘門停在 Windows sandbox 的 uv cache 權限，核准後以相同命令通過。PG runner 初次讀不到實際 port；唯讀確認容器仍在 running、loopback 55441 已發布且可連線後，以原命令通過。沒有重啟共用服務、清 volume 或新增付費模型呼叫。

## 實驗原件與提交內容

八份大檔以 gzip 無損保存，原件總計 470,586,946 bytes、壓縮後 52,640,587 bytes；逐份解壓 SHA-256 一致。[保存清單](../../../experiments/compressed-artifacts.json)與[還原步驟](../../../experiments/artifact-storage.md)可在新 checkout 重現。原檔保留本機並排除重複提交，模型輸入、回應、評分與排名內容不改寫。

文件導覽檢查不改模型當時收到的 23 份文件副本：其相對連結沿當時來源位置解讀，不能為修導覽而改變已保存輸入。大檔的現行導覽連結改指 gzip，歷史 hash 與來源副本保持原樣。

程式與維護文件的 staged diff 做空白檢查，允許 Windows 的 CRLF。`docs/experiments/` 與 `docs/plans/evidence/` 的資料則逐檔比對 Git index blob 與本輪保存的 SHA-256，保留原輸出的換行、Markdown 換行和空白，不為格式檢查改寫實驗內容。

提交候選沒有超過 50 MiB 的檔案；文字、gzip 與 zip 中的來源已做憑證格式檢查，唯一命中是未修改的既有測試 sentinel。`.tmp/`、服務初始化 marker、填好設定的 `.env`、依賴快取及本機歷史封存不納入提交。

## 推送

本輪完成本機整理與提交，尚未 push、merge 或建立 PR。下一步推送這個工作分支：

```powershell
git push -u origin reference-and-maintenance
```
