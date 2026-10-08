# 快速開始：在 Windows 使用 Caliburn

用 Docker 啟動 App、資料庫與 PDF 匯出。資料庫密碼自動產生，其餘設定使用預設值；不必另裝 Node、Python 或 PostgreSQL。

## 準備 Docker 與專案

安裝 [Git for Windows](https://git-scm.com/install/windows) 與 [Docker Desktop](https://docs.docker.com/desktop/setup/install/windows-install/)。依 Docker 提示完成 WSL 2 設定，使用 Linux containers，並保持 Docker Desktop 開啟。

在 PowerShell 取得專案；已有專案時，直接進入原目錄：

```powershell
git clone https://github.com/JD-Consultant/Caliburn.git
cd Caliburn
```

不使用 Git 時，可從[專案頁](https://github.com/JD-Consultant/Caliburn)選 **Code → Download ZIP**，解壓後在含 `compose.jd-app.yaml` 的目錄開啟 PowerShell。

## 設定 AI 金鑰（可略過）

要使用 AI，在 `apps/api/.env` 寫入一行：`OPENAI_API_KEY=` 後接自己的 key。確認檔名不是 `.env.txt`；已有檔案時沿用，金鑰勿提交或分享。

沒有 key 可略過，仍可人工編輯 JD 與匯出 PDF。

## 初始化並啟動

在專案根目錄執行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-docker.ps1
```

首次需連網下載依賴。腳本會檢查 Docker、完成初始化並啟動服務；保留既有設定，失敗即停。`Bypass` 只作用於本次 PowerShell 程序。

完成後開啟 [Caliburn](http://127.0.0.1:8100/)。下次使用按[日常啟停](README.md#日常啟停與更新)，不需重新初始化。

## 建立第一份職務檔案

1. 按「建立職務檔案」，填入檔案名稱與受訪員工姓名，再按「建立」。進入工作區即表示檔案已保存。
2. 已設定 key 時，送出一句工作說明，確認收到顧問回應；這會使用 OpenAI 額度。未設 key 時，訪談送出會被拒絕，輸入仍保留。

頁面能開啟不代表 key 有效；操作失敗時查[問題診斷](README.md#診斷)。

## 之後要做什麼

- [操作手冊](README.md)：啟停、更新、備份與自訂設定。
- [原生開發](native-development.md)：修改程式與測試。
- [公版參考與 RAG](rag.md)：加入公版查找。
