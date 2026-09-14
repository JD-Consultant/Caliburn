# Task 5 pywin32 312 官方 artifact 前置核對

**保存說明：**本頁保留下載／靜態盤點時的結果；非執行材料按原bytes保存。wheel留本機隔離plan scratch，不納Git，來源與官方hash仍完整記錄。實際安裝／Win32功能與故障結果另由Task5交付。

日期：2026-09-10。工作樹：`S:/caliburn/.worktrees/analysis-only-agent`，branch `codex/analysis-only-agent`。範圍：已採 Windows lifecycle 方案的固定依賴材料；不重開設計。

**結果：artifact 前置 PASS。** 官方提供 CPython 3.12／Windows x64 wheel；下載 bytes 的 SHA256／大小與 PyPI metadata 相符，必要模組及授權檔存在。這不代表安裝、DLL 載入、Win32 呼叫、nested Job 或 crash 行為已通過。

## 官方 fact／實際材料

來源：[PyPI 312 JSON metadata](https://pypi.org/pypi/pywin32/312/json)、[固定 wheel](https://files.pythonhosted.org/packages/03/d9/77040d3b43df3f3be32ea289433d660d2727f5ba327bc73be835127d9d60/pywin32-312-cp312-cp312-win_amd64.whl)。完整 JSON 與 wheel 已保留於同目錄下 `task5-pywin32-preflight/`，不是 uv cache／venv 安裝。

| 欄位 | 官方 metadata／實際核值 |
|---|---|
| Filename | `pywin32-312-cp312-cp312-win_amd64.whl` |
| PyPI upload | `2026-06-04T07:49:31.850318Z` |
| Yanked | `false` |
| Size | `6,914,841` bytes；下載一致 |
| SHA256 | `b457f6d628a47e8a7346ce22acb7e1a46a4a78b52e1d17e1af56871bd19a93bc`；下載一致 |
| METADATA | Version 312；Metadata-Version 2.4；Requires-Python `>=3.9`；無 Requires-Dist 行 |
| WHEEL | Tag `cp312-cp312-win_amd64`；Root-Is-Purelib `false`；Wheel-Version 1.0；Generator setuptools 82.0.1 |
| 選定內部 RECORD | METADATA／WHEEL、授權／NOTICE、兩個 wrapper 與 pywintypes DLL，共22項 SHA256／size，0 mismatch |

PyPI hash 是下載內容對官方索引的完整性核對，不稱數位簽章、獨立 reproducible build 或二進位程式安全稽核。

## 必要模組：只讀 ZIP／PE header

| ZIP entry | Bytes | PE Machine | SHA256 |
|---|---:|---|---|
| `win32/win32job.pyd` | 29696 | `8664`（x64） | `bfc31798ccf0bcf9b4453903918866abcfb546f5b1d6bd59e4691b83cbe44fa8` |
| `win32/win32event.pyd` | 30208 | `8664`（x64） | `a6b896456443447a663fe25783dfa95929dc8ade8d7970fd78d3b4e65100371e` |
| `pywin32_system32/pywintypes312.dll` | 136192 | `8664`（x64） | `9bd7f8c39a84d7b1ea43bfcd33c04631c60f4ff28167e82bb21987cc1c353766` |

上述 binary 只在 ZIP stream 中讀 bytes，沒有解出作載入、import 或執行。另定點保存官方 [b312 win32job.i](https://raw.githubusercontent.com/mhammond/pywin32/b312/win32/src/win32job.i)、[b312 win32event.i](https://raw.githubusercontent.com/mhammond/pywin32/b312/win32/src/win32event.i)：確認 Create/Open/Assign/Terminate/Query/Set Job、IsProcessInJob、KILL_ON_JOB_CLOSE 及 CreateMutex／ReleaseMutex／WaitForSingleObject 宣告。**原碼宣告與 wheel 內模組存在，不能代稱該 wheel API 實際可用**；Task 5 在隔離安裝後驗。

## 實際 license／notices

METADATA 寫 `License: PSF`、PSF classifier，但同份 description 明示各元件混合授權，以原碼及個別 notices 為準。不能把整包標成 MIT 或把全部內容一概稱 PSF。

以下8個 `License-File` 均存在於 wheel 的 `pywin32-312.dist-info/licenses/`，已保存完整原文；這是內容盤點，不將單一套件標籤代替分項條款。

| Metadata License-File | 實際內容 |
|---|---|
| `adodbapi/license.txt` | GNU LGPL 2.1 全文 |
| `com/License.txt` | Greg Stein／Mark Hammond copyright；source/binary redistribution 條件、保留 notices／disclaimer、不得未經許可背書 |
| `pythonwin/License.txt` | Mark Hammond，同型 source/binary redistribution 條件 |
| `pythonwin/Scintilla/License.txt` | Neil Hodgson Scintilla／SciTE 授權及 copyright／permission notice 保留條件 |
| `pythonwin/pywin/idle/LICENSE.txt` | Python 歷史及各代授權全文，不只一行 PSF |
| `win32/License.txt` | Mark Hammond source/binary redistribution 條件；與官方 [b312 win32/License.txt](https://raw.githubusercontent.com/mhammond/pywin32/b312/win32/License.txt) 正規化換行後全文相同 |
| `com/win32comext/mapi/src/MAPIStubLibrary/LICENSE` | Microsoft 2018 MIT 全文 |
| `isapi/README.txt` | Phillip Frantz／Blackdog Software 2002–2003 copyright 與元件說明；該檔本身不是完整 permissive license 文字，不冒稱其為 MIT |

wheel 另有 `win32comext/mapi/NOTICE.md`，指明 mapi/exchange 含 MIT 的 MAPIStubLibrary，亦已保存；一般位置的重複 license 檔一併保留。Task 5 應完整保留 wheel 內 notices，不因只使用 job/event 就把其餘打包內容改標成相同授權。本案仍是本機隔離依賴導入；沒有據此核准再散布成品，也不以此盤點聲稱所有未讀單檔 copyright 均完成法律判定。

## 可重用證據與 Task 5 邊界

材料目錄：`S:/caliburn/.worktrees/analysis-only-agent/.superpowers/sdd/2026-09-10-jd-editor-core-implementation/task5-pywin32-preflight/`。

- `pypi-pywin32-312.json`、固定 `.whl`：官方原 artifact。
- `METADATA.txt`、`WHEEL.txt`、`RECORD.csv`：從 ZIP 讀出的 metadata。
- `artifact-verification.json`：wheel expected/actual hash、大小及22项 RECORD 核對。
- `wheel-inventory.csv`、`license-inventory.csv`：ZIP entry／文字證據對照；授權內容用 `__` flatten 原路徑保存在同資料夾。
- `b312__win32__License.txt`、`b312__win32__src__win32job.i`、`b312__win32__src__win32event.i`：官方固定 tag 的定點原碼／授權。

沒有 artifact 反證要求重選已採方案。Task 5 才修改 Windows-only `pywin32==312` marker／隔離 lock，按固定 artifact 導入 CPython3.12 x64，驗 import／實際函式、ACL、mutex、nested job、子程序 membership、bootstrap／crash 與 PG barrier。wheel 名稱／PE machine 不能替代這些 runtime 驗收。官方 METADATA 的安裝指引也註明 venv 不應跑全域 post-install script；本輪完全沒有安裝或執行該 script。

本次初次 sandbox 網路請求被拒連線；經工具自動審核允許的官方 metadata／wheel／三個 tag 檔下載完成。沒有 approval rejection 或未解下載阻擋。沒有安裝／import wheel 或 DLL、修改 lock／venv／runtime、操作 Job／活程序、啟 API／DB／模型、commit 或子 agent；Task 4 Node 工作未碰。
