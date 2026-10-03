# Memory 長文定位：隔離離線探針

- 日期：2026-09-27。
- 狀態：有限合成案例已執行；不是正式 parser、工具或產品驗收。
- 範圍：全合成字串、無模型請求、無資料庫與產品資料。RapidFuzz 只安裝於被忽略的 `.research-tmp/` 隔離環境；未改 App 依賴、鎖定檔或 production。
- 決策入口：[產品概念 009](../../../product-concept.md#分層工作記憶)；判讀與後續 gate：[工具研究 §10.6](../../../research/agent-systems/2026-09-09-llm-app-tool-use-and-document-editing-common-practices.md#106-帶上下文-hunk-的有限離線驗證2026-09-27)。本頁保存證據，不建立第二份產品規則。

## 問題與驗證順序

先驗證成熟字串比對元件能否支援「列出候選、唯一才改、多個拒絕」，再依 Owner 提醒補正主要情境：**正常 patch 使用帶前後文的 hunk 定位，只套用 `-`／`+` 指定的變化；不能用裸片段的缺點否定 patch。**

RapidFuzz 提供相似度計算，不提供 Caliburn 的候選範圍、歧義政策或 patch 執行器。本輪接法都是可丟棄的研究程式，不能直接搬成正式產品。官方 API 見 [Levenshtein normalized similarity](https://rapidfuzz.github.io/RapidFuzz/Usage/distance/Levenshtein.html)；相似度不是業務正確性的保證。

## 主要結果：帶上下文的 hunk

[hunk_probe.py](hunk_probe.py) 使用已解析的 context／delete／add fixture，不解析 unified diff 或 V4A。新鮮執行 exit 0，**7 項預期行為通過**；原始輸出：[hunk_probe-result.json](hunk_probe-result.json)。

| 案例 | 實際結果 |
|---|---|
| 兩個函式都有相同待修改行 | 藉完整上下文選中正確函式，只修改指定行。 |
| 前方增加內容、目標位置後移 | 仍可按上下文定位；未驗數字行號解析。 |
| 上下文有空白／換行差異 | 模糊定位後保留來源實際上下文及 CRLF，不用 hunk 中的近似文字覆寫它。 |
| 完整 hunk 出現兩次 | 拒絕，全文不變。 |
| 多個近似完整 hunk | 拒絕，全文不變；本例含重疊視窗，共 3 個合格候選，不宣稱恰好兩處。 |
| 上下文指向不相干函式 | 無匹配，全文不變。 |
| 117,145 字元的中文長文 | 容忍一處上下文用字差異，只改指定正文行，其餘原文保持不變。 |

這些案例支持「上下文負責定位，新增／刪除行負責變更」的用法，沒有證明所有模糊情境、安全門檻或完整編輯生命週期已驗收。

## 前置探針：防護、限制與反例分開記錄

[probe.py](probe.py) 的 [probe-result.json](probe-result.json) 記錄 18 項 assertion，其中：

- **14 項防護檢查**：長文精確／近似定位、格式差異、重複及重疊候選、不同相似度候選仍拒絕、上下文消歧、無匹配、增刪、空輸入、短字串及計算量限制。計算量超限不得冒充無匹配。
- **2 項已重現的能力限制**：同文字重新折行、行內模糊片段，這個同列數整行視窗探針尚不支援。不是產品已接受的限制，也不是 patch 必然的缺點。
- **1 項語意反例**：裸區塊替換即使只有一處相似匹配，仍可能帶入未指定的事實改動。這不能外推成帶上下文 hunk 也會覆寫 context；主要探針另驗保留實際 context。
- **1 項政策觀察**：探針先精確、後模糊；有精確位置時不另枚舉模糊位置。這個跨階段優先政策尚未定案，不能說已證明全域無歧義。

不得將它們合稱「18 項功能 PASS」。額外門檻觀察不作驗收計數：此合成錯字在 0.90／0.95 被接受、0.98／0.99 被拒絕；不是正式門檻選型。

## 重現

實際環境：Windows、Python 3.12.13、RapidFuzz 3.14.6；相似度實作為 `rapidfuzz.distance.metrics_cpp_avx2`。下列命令使用本輪已備妥的隔離快取，不修改正式 Python 環境；新機器需另取得相同版本，不能假設已有快取。

```powershell
uv run --offline --no-project --isolated --cache-dir S:/caliburn/.research-tmp/memory-edit-spike/uv-cache --python S:/caliburn/experiments/jd-relational-app/.venv/Scripts/python.exe --with rapidfuzz==3.14.6 python -B docs/experiments/legacy-evidence/2026-09-27-memory-fuzzy-edit/probe.py
uv run --offline --no-project --isolated --cache-dir S:/caliburn/.research-tmp/memory-edit-spike/uv-cache --python S:/caliburn/experiments/jd-relational-app/.venv/Scripts/python.exe --with rapidfuzz==3.14.6 python -B docs/experiments/legacy-evidence/2026-09-27-memory-fuzzy-edit/hunk_probe.py
```

JSON 耗時只是單次合成執行觀察，非 benchmark；長度單位是字元，不是 token。

## 尚未證明

- 實際 patch 格式、解析器及錯誤回傳契約；未裁決 unified diff／V4A／其他輸入格式。
- 多 hunk 座標變化、重疊編輯及任一 hunk 失敗時整次不寫入。
- 正式模糊容許範圍、門檻、候選去重與精確／模糊優先規則；同列數視窗、0.90、長度與計算量門檻均為實驗值。
- title 定位、版本／權限／候選保存接線、真模型產生 patch 的效果及產品回歸。

後續只對收斂的編輯契約核對成熟 parser 的最小接法及上述缺口；不擴建通用 patch engine，不重開 Memory 發布、JD 業務工具或資料權威。
