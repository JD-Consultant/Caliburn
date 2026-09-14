# Docker Desktop Windows 啟動修復

> 2026-09-06 · Owner 已授權修復反覆啟動失敗。範圍是本機 Docker；保留容器、volumes 與既有資料，不重設、不解除註冊 WSL、不變更 Caliburn production。

## 證據與處理選擇

- 本機：Docker Desktop `4.77.0.228796`；Windows `26200.9168`；WSL `2.3.26.0`。開始時 Docker 程序未運行、`docker-desktop` distro 已停止。
- 最新 backend log 的致命錯誤：初始化 Inference manager 時，無法移除 `C:/Users/chenb/AppData/Local/Docker/run/dockerInference`，`The file cannot be accessed by the system`。此項為零長度 `ReparsePoint`；run 內另有 Docker 通訊 sockets，Secrets Engine 也有 `engine.sock`。不能把 socket 當成資料庫檔案。
- [Docker 官方 4.89.0 發行說明](https://docs.docker.com/desktop/release-notes/#4890)（2026-08-31）明確列出 Windows 不正常關閉留下 stuck socket 導致啟動失敗的修正。**與本機故障高度吻合；升級是否解決仍要實測，不先宣稱永久修好。**
- [官方 issue tracker #531](https://github.com/docker/desktop-feedback/issues/531) 的使用者報告包含相同 Inference／Secrets Engine 錯誤與父目錄改名 workaround；這是問題回報，不冒充官方保證。本機 `EnableDockerAI` 已是 false，不能再靠切換此設定宣稱修好。

優先使用官方修正版原地升級；不先寫每次啟動都清 socket 的自製修補程式。若新版仍不能自行處理舊 socket，才依實際新日誌考慮限定通訊目錄的可恢復改名；不得碰 `Docker/wsl` 或 `docker_data.vhdx`。

## 執行與驗收

1. `docker desktop update --check-only` 回報 Desktop 未啟動，無法走內建更新路徑。
2. 改由[官方 Windows 安裝說明](https://docs.docker.com/desktop/setup/install/windows-install/#install-from-the-command-line)的原地 installer 路徑；保持既有 all-users／WSL 模式，不解除安裝。
3. 官方 build `238018`：`https://desktop.docker.com/win/main/amd64/238018/Docker%20Desktop%20Installer.exe`。[校驗碼](https://desktop.docker.com/win/main/amd64/238018/checksums.txt)：SHA256 `854626704af28a160d5af68b96b3e32eacf08ab397ce6c12eb02a04788d73681`。執行前同時驗 Docker 發行者有效簽章。
4. 安裝後檢查 Desktop／Engine 版本、容器及資料仍在、專用 PG 可連線。
5. 透過官方 stop/start 做乾淨關閉及再次啟動；不以强制 kill 生產容器模擬斷電。

## 實測結果與尚未解決的差異

- 官方 installer 共 624,612,784 bytes；初次下載在 240 秒限時剩約 15 MB 時停止，以 HTTP resume 完成。SHA256 相符、Authenticode `Valid`、發行者 Docker Inc。
- 原地安裝 exit code 0，安裝日誌 `Installation succeeded`；保留 all-users／WSL-2 模式。Desktop 升為 `4.89.0.238018`。沒有解除安裝、接受新條款、修改資料位置或重設 WSL。
- 新版首次仍不能 rename 舊 `dockerInference`。正常停止 Docker 並確認相關程序全退出後，只把兩個「父目錄為普通目錄、內容只有零長度 socket reparse point」的路徑改名備份：
  - `C:/Users/chenb/AppData/Local/Docker/run.stale-backup-20260906-1640`
  - `C:/Users/chenb/AppData/Local/docker-secrets-engine.stale-backup-20260906-1640`
- 隨後 Engine `29.7.2` 成功運行；11 個原容器、11 個 volumes 可列出。只啟動既有 `caliburn-q019-postgres`，確認 PostgreSQL `16.14`／`q019_agent_test` 可查詢，仍掛載 `caliburn-q019-postgres-data`。起始一次 pg_isready 在初始化期間拒絕連線，後續通過，不算資料庫毀損。
- **重啟驗證未通過：**正常關閉 PG／Docker 後，自動化 `docker desktop start` 遇到 `sailor-ingest.sock` rename 失敗。Owner 確認 16:42–16:43 手動重開 Docker，16:43 查詢 Engine／Desktop 正常。不能把這次手動恢復算為自動重啟通過。
- 為區分入口，在沒有運行容器時，正常停止並等程序完全退出，再測直接桌面執行檔 `Start-Process`：仍遇 `engine.sock` rename 失敗。之後 Windows `Shell.Application.ShellExecute` 測試亦遇 `sailor-ingest.sock` rename 失敗。**停止反覆自動重啟、沒有新增清理腳本／排程／登錄檔 workaround。請 Owner 再手動開啟，以先恢復測試。**
- 同一工具執行環境的獨立 .NET AF_UNIX 測試可正常 bind／listen／Dispose，close 後 socket 自動消失。故不能宣稱整台 Windows AF_UNIX 都損坏，也不能僅由手動／自動差異斷言是特定 agent 軟體 bug。

[Microsoft AF_UNIX lifecycle 說明](https://devblogs.microsoft.com/commandline/af_unix-comes-to-windows/)可作機制參考；[Anthropic tracker 相似啟動環境報告](https://github.com/anthropics/claude-code/issues/76383)只提供待驗證假說，不證明本機根因。本機的最小 socket 測試反而通過，因此不照抄該報告的因果判斷。

設定備份：`C:/Users/chenb/AppData/Local/Temp/caliburn-docker-repair-7ee795bda95c4e9099556d7af8576349/settings-store.before.json`；原設定 SHA256 `472BD8C17FE4519B6A65772D50463A917982CC02BDADC2DB2FA1A7DD87FF5C20`。升級僅觀察到 SettingsVersion 44→45；`EnableDockerAI=false` 保持不變。安裝程式同目錄保留，兩個損壞 socket 備份目錄也保留，沒有刪除業務資料。

### Owner 操作後的恢復與資料庫補測

Owner 隨後回覆「我按 reset to factory defaults 就可以了」，並同意先測試。這是 Owner 的介面操作，不是 agent 執行資料重設；不能因此宣稱僅靠升級已解決。16:48 新程序的父程序確認為 `explorer.exe`。重設與啟動入口同時改變，因此無法用這次成功單獨證明某個因素是根因。

重新盤點：原 11 個容器、11 個 volumes 及既有映像仍可列出；Q019 原 volume／localhost55433 port binding 仍在，`q019_agent_test` 可查詢到既有 public tables。**沒有觀察到資料清空，不需要重建 DB；但未逐一驗證所有其他 volumes 內容。**設定則出現 `EnableDockerAI=true`、`DesktopTerminalEnabled=false` 等變更；這發生於 Owner 操作後，agent 未回寫或擅自還原。

只啟動 Q019 原容器，使用其既有 credential（只在程序內取得，不輸出、不落檔）補跑：

```text
# 專用 localhost:55433/q019_agent_test；PYTHONUTF8=1
.venv/Scripts/python.exe -m pytest -q -rs --tb=short
177 passed in 36.60s
```

0 skipped、0 付費模型呼叫；包含原 16 個 PG 與新 2 個 root→child→C 重建 clients 案例。過程沒有改應用程式或 schema 設計，測試只使用既有隔離 test DB。結果同步至[Task 1 結果](2026-09-06-analysis-only-agent-conversation-lifecycle-results.md)。

**目前結論：Docker／專用 PG 已恢復可用，Q019 PG 補驗證通過；自動重啟仍未通過，不能宣稱永久修好。**依 Owner「先測試」，停止重啟實驗，讓 Docker 與 Q019 PG 保持運行。再次排查自動啟動需獨立、受控比較；不再反覆重設、升級或新增自製啟動清理器。
