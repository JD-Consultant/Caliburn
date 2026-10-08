# 實驗原件與私人封存

日常查閱的公開實驗資料保留在 Git；已結案且不需常駐的私人材料存於 GitHub Release，按需下載。只保存支持結論或延續工作的必要資料，不永久保存全部測試環境。

## Git 內的大檔原件

目前保存清單共收錄 16 份超過 20 MiB 的 JSON／JSONL 原件，以 gzip 保存，共由 1,315,805,154 bytes 壓縮為 213,952,758 bytes。內容、評分與歷史結果不變；每份解壓後的 SHA-256 已與原檔核對。

[保存清單](compressed-artifacts.json)記錄原路徑、原始大小與 SHA-256，以及壓縮檔的路徑、大小與 SHA-256。壓縮檔與其他實驗資料一起納入 Git；原路徑供分析時按需還原，由 `.gitignore` 排除。Git attributes 禁止轉換實驗原件的換行，避免跨平台 checkout 改變既有雜湊。

gzip 可直接下載、解壓，不需要 Git LFS。這個整理方式避開 [GitHub 的 100 MiB 單檔限制](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)，也保留完整輸入、排名和 trace。

## 重現前還原

既有分析程式沿用原路徑。新 checkout 要重算清單中的原件時，先在 repository 根目錄執行下列命令。它只檢查、解壓本機檔案，不呼叫模型或資料庫；已存在的原檔會核對內容，不會覆寫。

```powershell
@'
from pathlib import Path
import gzip
import hashlib
import json

root = Path.cwd().resolve()
scope = root / "docs/experiments"
manifest = json.loads((scope / "compressed-artifacts.json").read_text(encoding="utf-8"))
for item in manifest["artifacts"]:
    archive = (root / item["archive"]).resolve()
    target = (root / item["path"]).resolve()
    assert archive.is_relative_to(scope) and target.is_relative_to(scope)
    compressed = archive.read_bytes()
    assert hashlib.sha256(compressed).hexdigest() == item["archive_sha256"]
    original = gzip.decompress(compressed)
    assert len(original) == item["bytes"]
    assert hashlib.sha256(original).hexdigest() == item["sha256"]
    if target.exists():
        assert hashlib.sha256(target.read_bytes()).hexdigest() == item["sha256"]
    else:
        with target.open("xb") as output:
            output.write(original)
    print(item["path"])
'@ | uv run --project apps/api --locked python -
```

還原出的原檔仍被 Git 排除，不會在重現後重複提交。原實驗的程式、artifact hashes、payload hashes 與評分檔保持原樣；保存清單只描述檔案的包裝方式，不取代各實驗的證據與判準。

## 分析完成後釋放空間

本機解壓副本不必常駐。確認沒有分析程序使用原路徑後，逐份核對原檔、gzip 及解壓內容的大小與 SHA-256，並確認 gzip 已提交、原檔未追蹤且被忽略，再精確刪除清單中的原檔。保留 gzip、保存清單及所有未列入清單的實驗資料；下次分析前依上節還原。

這只回收本機重複副本，不改寫 Git 歷史，也不刪除實驗證據。其他暫存、執行環境及資料庫的處理見 [runbook](../runbook.md#磁碟空間維護)。

## 私人歷史材料與資料庫封存

已結案且不需日常讀取的本機材料，使用 [Caliburn-archives 私人 repository](https://github.com/JD-Consultant/Caliburn-archives) 的 Release 附件保存，按需下載。公開的實驗摘要、既有 gzip 原件及重現程式維持目前 Git 保存方式；不把未審閱的本機歷史直接轉成公開研究證據。

每批附件清單記錄來源範圍、排除項目、大小、SHA-256、工具／schema 版本及還原結果。一般檔案還原須核對逐檔內容；資料庫另依 [runbook](../runbook.md#資料庫與備份) 做實際隔離還原。先從遠端重新下載核對，再移除對應的本地副本；單純 `git push` 不會釋放本地 Git object 或工作目錄空間。

金鑰、角色密碼、瀏覽器登入狀態及個人設定排除外送。用途未明的材料先核對來源與內容；不因 repository 是 private 就全部上傳。原始 Git bundle 也要檢查舊 refs 與內容，不以目前分支已公開推定整份歷史可以公開。

### 2026-10-08 精選封存

[私人 Release：storage-2026-10-08](https://github.com/JD-Consultant/Caliburn-archives/releases/tag/storage-2026-10-08) 保存下列附件；須以具存取權的 GitHub 帳號登入。ZIP 的 manifest 記錄原路徑、包內位置與逐檔 SHA-256；Git bundle 另附 refs、HEAD 與 `fsck` 的還原核對紀錄。整理範圍、實際驗證及清理結果見[本次維護紀錄](../plans/2026-10-08-project-storage-cleanup.md)，不由封存存在推定產品品質通過。

| 附件 | 保存用途 |
|---|---|
| `minimal-history-evidence-20261008.zip` | 115 份舊 UI／模型驗證、PDF 檢查及研究腳本；約 3.3 MiB |
| `minimal-research-evidence-20261008.zip` | 335 份未入 Git 的研究結果、trace、腳本及代表性截圖；約 15.0 MiB |
| `minimal-top-level-evidence-20261008.zip` | 91 份零散研究腳本、結果與代表性圖像；約 3.5 MiB |
| `caliburn-selected-c-evidence-20261008.zip` | 七場正式訪談比較、選問優先研究及其設定、原件與評分；約 221.1 MiB |
| `caliburn-retired-production-db-20261008.zip` | 舊 production 容器的兩份小型資料庫與還原證據；約 33.1 MiB |
| `caliburn-target-demo-20261008.zip` | 需保留的 Demo 資料庫與還原證據；約 92.5 MiB |
| `before.bundle` | 作者資訊修正前的 Git refs，供舊提交雜湊追溯；約 335.7 MiB |

已在 Git 的正式原件不重複入包。舊依賴、快取、瀏覽器 profile、普通測試中間態及非必要的中間迭代不保留；支持失敗診斷或費用追溯的前批原件仍列入精選清單。已結案的合成測試資料庫以實驗證據為保存單位，未保留整庫重播能力。

取回時使用已授權的 GitHub 帳號，從 Release 的清單選附件，下載到新的 `.tmp/` 目錄：

```powershell
$asset = 'caliburn-target-demo-20261008.zip'
gh release download storage-2026-10-08 --repo JD-Consultant/Caliburn-archives --pattern $asset --pattern archive-index.json --dir .tmp/archive-restore
$index = Get-Content -LiteralPath .tmp/archive-restore/archive-index.json -Raw | ConvertFrom-Json
$expected = $index.assets | Where-Object { $_.name -eq $asset }
$actual = (Get-FileHash -LiteralPath (Join-Path .tmp/archive-restore $asset) -Algorithm SHA256).Hash
if ($expected.Count -ne 1 -or $actual -ne $expected.sha256) { throw '封存雜湊不符' }
```

核對附件清單後再解壓／還原；不執行備份中的歷史腳本，也不覆蓋現用資料。Release 附件須小於 [GitHub 的單檔限制](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases#storage-and-bandwidth-quotas)，過大的封存依可獨立還原的範圍拆包，不改動原件內容。
