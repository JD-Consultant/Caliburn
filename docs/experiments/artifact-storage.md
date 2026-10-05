# 大檔實驗原件保存

本次整理將八份超過 20 MiB 的 JSON／JSONL 原件以 gzip 保存，共由 470,586,946 bytes 壓縮為 52,640,587 bytes。內容、評分與歷史結果不變；每份解壓後的 SHA-256 已與原檔核對。

[保存清單](compressed-artifacts.json)記錄原路徑、原始大小與 SHA-256，以及壓縮檔的路徑、大小與 SHA-256。壓縮檔與其他實驗資料一起納入 Git，原檔仍保留於本機，但由 `.gitignore` 排除。Git attributes 禁止轉換實驗原件的換行，避免跨平台 checkout 改變既有雜湊。

gzip 可直接下載、解壓，不需要 Git LFS。這個整理方式避開 [GitHub 的 100 MiB 單檔限制](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)，也保留完整輸入、排名和 trace。

## 重現前還原

既有分析程式沿用原路徑。新 checkout 要重算這八份原件時，先在 repository 根目錄執行下列命令。它只檢查、解壓本機檔案，不呼叫模型或資料庫；已存在的原檔會核對內容，不會覆寫。

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
