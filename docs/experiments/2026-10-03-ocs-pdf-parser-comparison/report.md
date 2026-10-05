# OCS PDF 工具比較結果

- 執行：2026-10-03 至 2026-10-04；最後核對：2026-10-04。
- 狀態：10 份／55 頁比較完成；正式 PDF → JSON 元件尚未修正。
- 方法、重跑與限制：[README](README.md)；來源身分：[cases.json](cases.json)；逐文件結果：[results.csv](results.csv)。

## 結論

建議本輪繼續使用 **pdfplumber** 作為抽取主體，先修正現有 OCS 解讀與輸出檢核。它保留全部已人工核對的檢查點，且成本最低；目前沒有代表反例要求更換主解析器。

**Camelot 的 lattice 模式**能直接還原本批有框線表格，適合保留為具體表格問題的診斷候選；不必先加入每份文件都跑兩套工具的正式流程。**Docling**有乾淨的七欄表頭、明確 span 與 provenance，但這次也出現任務列拆散及 K-code 歸屬改變，CPU 成本更高；本輪不建議直接替換。這是 Caliburn 在本批有文字層 OCS 表格上的取捨，不是通用 PDF 工具排名。

## 數據

20 個檢查要求 T／P／級別／K／S 在同列的不同、有序儲存格，8 個檢查驗正文片段，3 個驗下一頁延續的 code 與末文仍在相同 cell。原文／預期值見 [rubric revision 2](rubric.json)，完整裁決與實際 matching row 見 [anchor-results.json](trials/anchor-results.json)。

| 工具及設定 | 任務關係 | 正文片段 | 續文 cell | 55 頁抽取合計 | 程序 RSS 取樣峰值 |
|---|---:|---:|---:|---:|---:|
| pdfplumber 0.11.9，預設 | 20/20 | 8/8 | 3/3 | 3.36 秒 | 69.9 MiB |
| Camelot 2.0.0，auto | 0/20 | 0/8 | 0/3 | 4.04 秒 | 167.5 MiB |
| Camelot 2.0.0，lattice | 20/20 | 6/8 | 3/3 | 9.82 秒 | 257.0 MiB |
| Docling 2.133.0，accurate／CPU 四執行緒／OCR 關閉 | 18/20 | 8/8 | 3/3 | 142.38 秒 | 1777.4 MiB |

每個 arm 的十次抽取呼叫均完成。`ok`／Docling `SUCCESS` 只是呼叫結果，不能取代來源關係檢核。auto 的零通過是未直接保留指定的完整任務列／完整 cell，**不表示文字全部消失**。Camelot 正文欄只評估表格輸出能否涵蓋本元件需要的正文，不把表格工具當成通用全文工具評分。

初始化另為 0.26／0.50／0.50／4.45 秒；Docling 第一份的 28.87 秒含 lazy model load，後九份合計 113.50 秒。不是多輪平均、吞吐量 SLA 或全量批次預估。Docling 官方 downloader 此次取得約 668.7 MiB artifacts，包含本次推論未使用的 ONNX layout 與 fast TableFormer；網路下載約十分鐘，沒有算進抽取時間。各權重／設定的 SHA-256 見 [model-manifest](trials/model-manifest.json)。

## 可以回查的差異

### pdfplumber：原文存在，現行轉換仍會丟失或改寫

「3D列印技術」完整存在於[配修人員第 5 頁](trials/source-pages/01-p5.png)與原始抽取；註 2／4 的續行完整存在於[珠寶設計第 4 頁](trials/source-pages/02-p4.png)；級別 6 和沒有 A-code 的態度存在於[機械設計第 4 頁](trials/source-pages/03-p4.png)。因此既有 JSON 的刪字、分條、級別改為 3 與態度清空，應修在 section／契約／檢核的責任位置，換工具不會自動修掉這些行為。

缺點是預設表格有多餘空白子欄。例如配修人員第 2 頁視覺上七欄，raw grid 有十三欄；級別表頭與正文值還落在不同子欄。正文關係仍在同一列且順序一致，但不能以固定七欄 index 解讀。應保留 bbox／cell 幾何，依每份表頭與真實欄位邊界核對 mapping，不能把 header index 或第一頁 mapping 盲目套到所有頁。

### Camelot：有框線模式有效，自動模式與全文用途不合本批

auto 在本批常把同一任務拆成逐行資料。例如配修人員的 T1.2 所在列只留 P1.2.1 第一行與 K01／S01 的開頭，其後 P／K／S 各自落到下面的列。有些空白欄也不保留。必須另做列分組與跨欄關係復原，不能把其 DataFrame 直接當成 OCS task。

lattice 的 20 個任務關係與 3 個續文 cell 都通過；它通常還原七欄矩陣。兩個正文檢查未通過是珠寶補充說明的私用區項目符號被放入換行續文中間，例如 `標準作業\n\uf09f\n流程。`，不是「流程」的文字被刪除。這仍需要項目符號與續文解讀，且 Camelot 本身只輸出表格。

目前版本的[官方功能](https://github.com/camelot-dev/camelot)包含 `auto`、`lattice`、`network`、選用 ML／OCR 與 `stack_contiguous()`，不能沿用「只支援文字 PDF、沒有跨頁功能」的舊說法。這次只測 auto／lattice，未測 ML／OCR。stacking 的另行實測見 [stacking.json](trials/stacking.json)：三份文件表格數分別 8→3、7→3、11→3。按相同欄數直接 stack 會連態度與補充說明的一欄表格一起併入，且 stacked table 的 page 保留第一頁；它做矩陣堆疊，不裁決 T-code／block 延續關係，來源頁碼與章節仍須由本元件保存。

### Docling：部分合併格較好，但有新的結構錯置

珠寶設計第 2 頁的 `T2 設計珠寶與物件` 正確標示 `row_span=3`，且常直接得到乾淨七欄表頭。這些是實際優點。來源位置與 row／col span 可由 [DoclingDocument](https://docling-project.github.io/docling/reference/docling_document/) 回查。

但[機械設計第 4 頁](trials/source-pages/03-p4.png)的 T3.2 實際是一個完整儲存格／任務列；Docling 把它切成 `T3.2進行`、`設計製整`等多列，各 cell 的 row_span 為 1，P3.2.3、K33、S23 不再與 T3.2 同列。文字與 6 還在，關係需要額外復原。

在[電控工程師第 2 頁](trials/source-pages/04-p2.png)，原件 K17 屬 T1.2；Docling 將 K17 與下一個 T2.1 的 K18／K19 合成一格並放到下一列。全頁掃描仍找得到 K17，但任務歸屬已改變。這證明只比代碼集合或接受 `SUCCESS` 不足以驗收 OCS JSON。

case 09 另發出「2 of 34 pdf cells … were dropped from the table」的 MatchingPostProcessor 警告，回傳狀態仍為 `SUCCESS`。警告保留在 [warnings](trials/warnings.txt)；沒有把它直接計為兩筆已人工證明的全文遺失。使用 pdfplumber 作參照的逐頁代碼集合診斷沒有找出缺少代碼，該診斷不是獨立 golden，也不能否定上述錯置。

[官方 pipeline 選項](https://docling-project.github.io/docling/usage/advanced_options/)允許調整 cell matching、FAST／ACCURATE、OCR 與 accelerator；本次未逐份調參，未測 GPU、OCR 或 VLM。結果不能推論其他設定必定相同，也不能宣稱任何工具對全部 PDF 都完整。

## 設計去向與未驗範圍

本輪比較已寫回[元件設計 §7](../../specs/2026-10-03-public-ocs-pdf-to-json-design.md#7-技術取捨與官方依據)：保留 pdfplumber，Camelot lattice 為候選診斷工具，Docling 暫不替換。抽取層共用來源位置；OCS 章節、欄位 mapping、跨頁任務組裝及來源關係檢核仍由本元件負責。

下一個施工切片仍是已重現的補充說明保真與空內容拒絕，再處理級別 1–6／未編碼態度；各切片依原文預期值做 Red–Green–Refactor。這份比較完成不等於該切片完成，也沒有重轉 908 份 PDF、重建 embedding／向量索引或接入 JD App。

未驗：掃描 PDF、無框線／圖片表格、未抽到的版型、官方最新狀態、全部任務與文字、英文有效空格、GPU、調參最佳結果與全量 corpus。AIoT 文件實際十頁但頁腳寫共十一頁，工具機機械設計實際七頁但頁腳寫共八頁；只能記來源差異，不能把不存在的頁面補造為完整。

原始抽取 44 份 JSON（40 份文件輸出＋4 份 metrics）壓縮保存於 [raw-extraction.zip](trials/raw-extraction.zip)，沒有改寫其正文；13 個人工視檢頁面與裁決結果均保存。所有證據的大小／SHA-256 見 [evidence-manifest](evidence-manifest.json)。
