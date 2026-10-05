# 公版工具回傳的離線資料量比較

2026-10-05。狀態：**單筆既有資料的字元量測已完成；沒有新檢索或模型試驗**。目的：檢查候選概覽＋按需目錄是否一定減少整段工具輸出。設計方向見[JD 與公版按需取用](../../specs/2026-10-05-jd-and-reference-demand-loading-design.md)。

## 資料與方法

輸入是既有 [F01 API 原件](../../plans/evidence/2026-10-05-occupation-reference-api/live-search-result.json)。讀既有五份 reference，重建目前 App 搜尋工具投影，再建立候選概覽。概覽只帶固定 ID、名稱、原始概述及全部工作單元名稱；不送 similarity、任務目錄、OPKS 正文或新的模型摘要。

兩組皆用 `json.dumps(ensure_ascii=False, separators=(",", ":"))` 序列化。額外讀第 1／前 2／全部 5 份完整目錄，僅作大小敏感度情境；不是顧問實際選擇，不判定哪份適合員工。累計字元包含第一份概覽及每次完整目錄結果，未計提示、工具參數、state 或任務正文。

[probe.py](probe.py)不 import App 或啟動服務，零 embedding、rerank、Qdrant、GPU 或付費模型呼叫。[projection-results.json](projection-results.json)保存輸入 SHA256、完整候選投影、逐份來源身分／目錄大小及累計結果。原始檔沒有改寫。

## 結果

| 情境 | 工具結果數 | 累計字元 | 相較現行搜尋 |
|---|---:|---:|---:|
| 現行一次回五份完整任務目錄 | 1 | 8,779 | 基準 |
| 只看候選概覽 | 1 | 966 | 尚未讀目錄，不能作等效完成比較 |
| 概覽＋第 1 份完整目錄 | 2 | 3,341 | 減少 61.94% |
| 概覽＋前 2 份完整目錄 | 3 | 4,465 | 減少 49.14% |
| 概覽＋全部 5 份完整目錄 | 6 | 9,724 | 增加 10.76% |

**分層取用的收益取決於實際展開範圍。** 五份全讀時多出概覽與呼叫；不能只以概覽較短宣稱流程成本下降。字元與 UTF-8 bytes 不是模型 token；本次沒有量測時間、費用、候選選擇、JD 品質或完整度。

這筆 F01 已觀察過，不是 holdout。後續需固定同一批候選及員工資料，實測模型是否選到足夠的主要參考，並量測整段閱讀量和品質。輸出較小但漏掉主要工作不構成採納依據。

## 重算

在 repository 根目錄執行：

```powershell
& apps/api/.venv/Scripts/python.exe docs/experiments/2026-10-05-reference-context-projection/probe.py
```

腳本只重建本目錄的量測 JSON；不接外部服務、不改正式契約或部署。
