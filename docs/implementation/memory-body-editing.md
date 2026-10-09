# Memory 正文編輯接線

- 狀態：**現行 Memory 正文編輯機制**。2026-10-07 依 [Plan 保存與採用](../architecture/persistence.md#plan-從本輪候選到後輪可採用)將純核心移至 `adapters/body_edits.py`／`body_matching.py`，Memory 原入口保留薄相容包裝；焦點筆記重用同一解析／唯一定位／套用機制，只有 App 筆記用途允許空正文，Memory 仍拒空。純運算、模型工具與候選交易分責；共用執行與角色接線見 [Agent 執行](agent-execution.md)。驗證見本次切片證據及正文與工具驗證。
- 產品契約：[Memory 工具與寫入](memory-tools.md)、[模型工具的共同邊界](../standards/contract-strategy.md#模型工具的共同邊界)。本頁只決定既有 V4A 能力的解析、定位與套用機制，不重定產品效果或資料保存責任。

閱讀路徑：[採用來源](#1-重用來源與有限補強) → [語法與定位](#2-語法與唯一定位) → [套用與容量](#3-套用錯誤與容量) → [接縫驗證](#4-接縫及驗證層級)。純編輯核心處理一份正文；角色權限、工具回傳與候選交易由各自的接線文件維護。

這裡的 **V4A** 是以文字上下文定位修改位置的 patch 格式。每個 **hunk** 是一段局部修改：以原文上下文或明確的檔尾（EOF）條件定位，再用 `-`／`+` 指定刪除與新增行；一份 diff 可以包含多段 hunk。先看[Memory 工具與寫入](memory-tools.md)，再讀下方解析與歧義處理規則。

## 1. 重用來源與有限補強

[OpenAI 官方契約](https://developers.openai.com/api/docs/guides/tools-apply-patch)由執行方解讀 V4A。官方 helper 提供 section／chunk 解析，但不承諾多處匹配拒絕，亦不是 Memory Domain。保留其成熟語法算法，不安裝 Agents SDK runner；來源 commit、SHA-256、MIT 聲明及本地差異見 [第三方註記](../../apps/api/THIRD_PARTY_NOTICES.md)。

[RapidFuzz Levenshtein](https://rapidfuzz.github.io/RapidFuzz/Usage/distance/Levenshtein.html)負責文字相似度，鎖定 3.14.6（MIT）。候選枚舉、唯一政策與保存不是套件保證。先前 contextual hunk 探針只作案例參考，不將實驗程式或「精確優先」搬成正式規則。

選定流程：

```text
App 已綁定的一份候選正文 + body diff
  → 完整解析所有 hunks（拒絕 body 外操作與尾端垃圾）
  → 在原文上找每個 hunk 的唯一合格位置
  → 全部成立後，只套用指定增刪行，保留實際 context
  → 返回完整新正文供 Memory 候選服務做同次內容／引用交易
```

前四步是純運算；無 DB、filesystem、網路、scope 推測或自行重試。最後的候選採用及原結果恢復沿 [Memory 保存](memory-storage.md)，不是編輯器再造一套收據。

## 2. 語法與唯一定位

`adapters/v4a_parser.py` 抽取舊側 context 與相對 edit chunks，返回不可變型別。允許 `@@`、原文 anchor／stacked anchors、多 hunk、可選終端 `*** End Patch`／`*** End of File`；第一段亦可直接以增刪／context 開始。以換行分隔完整來源行，不接受數字 unified header、Markdown fence、檔案路徑或 create/delete/move envelope。所有輸入必須被消耗，不能修改前段後忽略非法後段。

`adapters/body_matching.py` 的唯一規則（Memory 原路徑轉出同一型別）：

- 在完整原文、目前順序游標以後枚舉同列數的整行窗口；context 包含未改行與刪除行，新增行不參與定位。
- 比對視圖只去每行首尾空白。相同文字合格；非相同的行，雙方至少 10 字元且 Levenshtein normalized similarity ≥0.90 才合格。**每行** 都須合格，不讓大量相同背景掩蓋短標題／短事實不符。
- 精確與近似位置一同計數；即使精確一處、近似另一處，也拒絕。重疊窗口不合併、分數不同不挑最高分。遇第二處即可確定歧義，提供兩個真實行範圍及有界片段，明說「至少兩處」，不冒充列完所有候選。
- Anchor 是 skip-ahead 的真實來源行，不是範圍標籤或替代 context。首個重用父 anchor 可位於游標之前，但不回退游標；後續 stacked anchor 必須向前找到。找不到就拒絕；使用最早合格 anchor 保留後方所有可能窗口，不以後一個 anchor 隱藏較早候選。
- EOF 是硬定位條件，不回退到正文其他位置。EOF 純新增可成立；無 context 且無 EOF 的插入則拒絕，要求提供定位依據。

這些是 Caliburn 的保守工程選擇，**不是通用 V4A 標準、語意正確性保證或已證模型最優門檻** 。目前不猜行內片段、不自動重新折行。模型若拿到零／多處匹配，須重新讀取完整來源行或補足辨識上下文；不可默默放寬政策。定位門檻是否適合真實模型行為，仍須以相應模型品質與旅程證據判斷。

## 3. 套用、錯誤與容量

### 正文保留與全成全拒

`body_edits.py` 的 `apply_body_diff` 對全部 hunk 使用原文座標；前段新增／刪除不推移後段基準。只有全部解析與定位成功才形成新正文。保留行使用原文，不將模型的模糊 context 寫回；未改字元、LF／CRLF 混用、尾端換行與 Unicode 保持。

某 chunk 的替換文字與實際來源相同時，整段原樣保留，避免 no-op 偷改混合換行符。新增行使用編輯位置的換行樣式；原文無尾端換行時，EOF 新增也不強加最終換行（必要行分隔除外）。Memory 的來源與結果均不可為空白 body；建立／刪物件走各自能力。共用核心供 Plan 使用時的空正文政策，依頁首所列契約處理。

### 錯誤與容量政策

錯誤為 `BodyEditError`，承接契約既有 `invalid_patch`、`patch_context_not_found`、`ambiguous_patch_context`；容量另用 `patch_limit_exceeded`，不能冒充無匹配或掃完後唯一。帶必要 hunk 編號／候選片段，工具邊界轉譯合法下一步；不將 raw exception／scope 交模型。

預設上限集中 `BodyMatchPolicy`：來源及結果 body 均至多 2,000,000 字元、diff 64,000 字元、128 hunks、估算完整掃描 20,000,000 字元工作量。估算涵蓋 context 與 anchors；超限整次拒絕，不只掃前段，也不能成功產生編輯器自身無法再處理的正文。這不是 token 門檻或時間保證；工具回傳容量由工具邊界檢查，發送前 token 容量由共用執行核對。政策由 App 配置，不是模型參數；測例可用較小界線驗拒絕。

## 4. 接縫及驗證層級

讀寫 schema／generated DTO、B1／B2 權限、map／read、title → ID、原操作命令、正文與 metadata／來源共同採用已接真 PostgreSQL；Update 回真實前後差異與定位，不 echo 模糊輸入。單物件寫入接線及容量在 [工具接線](memory-tools.md)維護。

原命令保存、`call_id` 配對與 Step 恢復由[共用執行](agent-execution.md)負責；B1 → B2 → 發布沿[背景工作](agent-execution.md#7-memory-背景工作)。純編輯器及交易測試不證明模型會選對內容或正確修正 patch。測試責任見[驗證對照](verification-plan.md)，B1／B2 的既有模型證據及未驗範圍由[架構驗證](../architecture/verification.md#memory-整理與發布)維護。

既有規格的欄位與例子維持單一權威；本頁不另複製所有工具 JSON。
