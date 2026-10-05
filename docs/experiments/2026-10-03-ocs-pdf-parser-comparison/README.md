# OCS 公版 PDF 解析工具比較

- 執行日期：2026-10-03 至 2026-10-04。
- 狀態：隔離實測；不改正式 `apps/pdf-to-json`、共用契約或既有 JSON。
- 問題：替換抽取工具能否改善 OCS 表格、文字與跨頁續文，並減少本元件的修正成本？
- 目標責任：[PDF → JSON 設計](../../specs/2026-10-03-public-ocs-pdf-to-json-design.md)。

## 方法

固定 [10 份原件及 SHA-256](cases.json)，均未在檔名標示「歷史資料」；沒有藉此宣稱它們全是官方現行版。樣本合計 55 頁，以已知反例、文字長短、框線畫法與跨頁內容選取，並非隨機抽樣。

採用 Python 3.12.13 的隔離環境，鎖定 pdfplumber 0.11.9（現行 App 基準）、Camelot 2.0.0 與 Docling 2.133.0；完整相依版本見 [requirements-frozen.txt](requirements-frozen.txt)。Docling 用 standard pipeline、CPU 四執行緒、TableFormer accurate、cell matching 開啟、OCR 關閉。所有樣本均有文字層。沒有 GPU／OCR／VLM／付費 API 比較。

pdfplumber 使用預設 `find_tables` 與 `extract_text`。Camelot 先測 `auto`，觀察到逐行拆列後，額外測有框線的 `lattice`，分別報告，不混算。Docling 使用原生文字及表格 cell 結構；將 span 的起點放入 grid，保留原始 cell span 與 provenance，不在比較中替任何工具補做 OCS 任務解析。

裁決以 [rubric.json](rubric.json) 的原件檢查點為準：20 個任務的 T／P／級別／K／S 必須在同一列的不同、依序儲存格；8 個正文片段；3 個跨頁延續所在儲存格的 code 與末文。人工視檢了 13 個來源頁：01 的 2／5、02 的 2／4、03 的 4、04 的 2／5、05／06／08／09／10 的 2、07 的 3。這不是完整逐頁、逐字或全部任務的 golden。

比對只移除空白，不修改保存的原始輸出；因此未驗證英文詞間空格保真。續文儲存格通過表示下一頁內容仍在相應 cell，**不表示工具已把跨頁任務組成 OCS**。Camelot 是表格工具，正文檢查只問其表格輸出是否足以替代本元件的全部抽取，不能推論它對一般全文抽取的準確率。

rubric revision 1 曾要求 grid 恰為七欄，因 pdfplumber 的空白子欄而誤判。revision 2 改核對同列有序且分離的來源欄位，原件預期值未改；Docling 尚未跑 trial。初始 `auto` 的暫存檔清理受到 sandbox 限制，後續將暫存位置固定在實驗工作目錄。相關診斷不能算成 PDF 內容失敗。

## 重跑

下列命令在儲存庫根目錄執行，`probe_python` 指向依 frozen requirements 建立的 Python；CPU torch wheel 使用 PyTorch 官方 CPU index，其他套件使用 PyPI。`probe_dir` 是自行指定的可寫隔離目錄，不要指向正式 JSON 位置。

```powershell
$probe_python = '<isolated-env>/Scripts/python.exe'
$probe_dir = '<writable-probe-directory>'
$env:PYTHONIOENCODING = 'utf-8'
$env:HF_HOME = "$probe_dir/hf-cache"
$env:HF_HUB_DISABLE_XET = '1'
& $probe_python -c "from pathlib import Path; from docling.utils.model_downloader import download_models; import sys; download_models(output_dir=Path(sys.argv[1]),with_code_formula=False,with_picture_classifier=False,with_rapidocr=False)" "$probe_dir/models"
foreach ($engine in @('pdfplumber', 'camelot', 'camelot-lattice', 'docling')) {
  & $probe_python docs/experiments/2026-10-03-ocs-pdf-parser-comparison/run.py $engine --repo . --output "$probe_dir/raw" --models "$probe_dir/models"
}
& $probe_python docs/experiments/2026-10-03-ocs-pdf-parser-comparison/score.py "$probe_dir/raw" --output "$probe_dir/anchor-results.json"
& $probe_python docs/experiments/2026-10-03-ocs-pdf-parser-comparison/diagnose_stacking.py --repo . --output "$probe_dir/stacking.json"
```

模型只下載權重，本機解析不啟用 remote services。實際 model 權重的 SHA-256 另列在結果證據中；上游 main 的模型日後可能更新，重跑須核對權重，不只核對 Python 套件版本。

## 保存與判定

每份輸出保存頁碼、原始 cell 文字與可取得的位置；Docling 額外保存 span／provenance，Camelot 保留 parsing_report。耗時從抽取呼叫到完成資料結構，包含 Docling 第一次 lazy model load，但不含網路下載；初始化時間另記。RSS 每 50 ms 取樣，只計該程序，未量 GPU／子程序／系統峰值，也未多輪取中位數。

停止條件：三套工具完成固定樣本及相同檢查；針對已觀察的模式失配只做一次有界的 `lattice` 診斷。不逐份反覆調參找最高分。選擇能保留已核對來源關係、診斷可回查、且對現有元件增加最少必要成本的方案；檢查點相同時再比較耗時與依賴成本。

原始輸出、逐文件時間、檢查結果與 Camelot stacking 診斷保留在 `trials/`；[report.md](report.md) 說明實測、限制與建議。環境與模型留在本次聊天的本機隔離目錄，未加進 App 依賴。實測建議寫回目標設計的取捨，沒有自行切換 production。

可直接對保存的 ZIP 重算檢查，不需重跑模型：

```powershell
& $probe_python docs/experiments/2026-10-03-ocs-pdf-parser-comparison/score.py docs/experiments/2026-10-03-ocs-pdf-parser-comparison/trials/raw-extraction.zip --output "$probe_dir/recomputed-anchor-results.json"
```
