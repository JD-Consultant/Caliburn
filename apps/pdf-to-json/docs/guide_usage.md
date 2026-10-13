# 使用方式

CLI 命令、參數、輸出及退出碼由 [README](../README.md#cli-使用方法)維護。以下命令從 repository 根目錄執行，使用鎖定環境：

```powershell
uv run --project apps/pdf-to-json --locked jd-convert convert input.pdf --output output.json
uv run --project apps/pdf-to-json --locked jd-convert batch pdfs --output converted
uv run --project apps/pdf-to-json --locked jd-convert validate output.json
```

轉換共用必要的結構、內容及來源檢核。失敗候選與診斷獨立存放；失敗不覆蓋既有正常輸出。批次中的單檔失敗不阻止其餘文件，存在拒絕結果時整批退出碼為 1。

## 從 Python 使用

需要完整轉換時使用共同入口，保留同樣的來源檢核與原子保存：

```python
from pathlib import Path

from jd_pdf_to_json.conversion import convert_file, write_report

source = Path("input.pdf")
output = Path("output.json")
diagnostics = Path("output.diagnostics")
result = convert_file(source, output, diagnostics)
write_report(result, diagnostics / "report.json")
print(result["status"])
```

`convert_file` 回傳 `converted` 或 `rejected`，不把失敗當空成功。`validate` 命令只檢查給定 JSON，無法代替轉換時對原始 PDF 的來源核對。

資料形狀與欄位語意見 [OCS 欄位契約](../README.md#6-field-contract)；修改程式見[擴充與修改](guide_extending.md)。
