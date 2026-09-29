# Memory 正文編輯接線

- 日期：2026-09-30；狀態：**T05 施工切片；純字串編輯器已驗，尚未接模型工具及候選交易**。完整進度／驗證見 [T05 evidence](../plans/2026-09-29-target-rebuild/evidence/t05-memory-tools.md)。
- 產品契約：[單物件更新](../specs/2026-09-27-memory-object-update-tool-contract.md)、[共同工具規範](../specs/2026-09-27-agent-tool-contract-design-research.md)。本頁只決定既有 V4A 能力的解析、定位與套用機制，不重定產品效果或資料 owner。

## 1. 重用來源與有限補強

[OpenAI 官方契約](https://developers.openai.com/api/docs/guides/tools-apply-patch)由執行方解讀 V4A。官方 helper 提供 section／chunk 解析，但不承諾多處匹配拒絕，亦不是 Memory Domain。保留其成熟語法算法，不安裝 Agents SDK runner；來源 commit、SHA-256、MIT 聲明及本地差異見 [第三方註記](../../apps/api/THIRD_PARTY_NOTICES.md)。

[RapidFuzz Levenshtein](https://rapidfuzz.github.io/RapidFuzz/Usage/distance/Levenshtein.html)負責文字相似度，鎖定 3.14.6（官方 PyPI 查閱日 2026-09-30；MIT）。候選枚舉、唯一政策與保存不是套件保證。先前 [contextual hunk 探針](../specs/evidence/2026-09-27-memory-fuzzy-edit/README.md)只作案例參考，不將實驗程式或「精確優先」搬成正式規則。

選定流程：

```text
App 已綁定的一份候選正文 + body diff
  → 完整解析所有 hunks（拒絕 body 外操作與尾端垃圾）
  → 在原文上找每個 hunk 的唯一合格位置
  → 全部成立後，只套用指定增刪行，保留實際 context
  → 返回完整新正文供原候選 owner 做同次內容／引用交易
```

前四步是純運算；無 DB、filesystem、網路、scope 推測或自行重試。最後的候選採用及原結果恢復沿 [Memory 保存](memory-storage.md)，不是編輯器再造一套收據。

## 2. 語法與唯一定位

`adapters/v4a_parser.py` 抽取舊側 context 與相對 edit chunks，返回不可變型別。允許 `@@`、原文 anchor／stacked anchors、多 hunk、可選終端 `*** End Patch`／`*** End of File`；第一段亦可直接以增刪／context 開始。以換行分隔完整來源行，不接受數字 unified header、Markdown fence、檔案路徑或 create/delete/move envelope。所有輸入必須被消耗，不能修改前段後忽略非法後段。

`features/work_memory/body_matching.py` 的唯一規則：

- 在完整原文、目前順序游標以後枚舉同列數的整行窗口；context 包含未改行與刪除行，新增行不參與定位。
- 比對視圖只去每行首尾空白。相同文字合格；非相同的行，雙方至少 10 字元且 Levenshtein normalized similarity ≥0.90 才合格。**每行**都須合格，不讓大量相同背景掩蓋短標題／短事實不符。
- 精確與近似位置一同計數；即使精確一處、近似另一處，也拒絕。重疊窗口不合併、分數不同不挑最高分。遇第二處即可確定歧義，提供兩個真實行範圍及有界片段，明說「至少兩處」，不冒充列完所有候選。
- Anchor 是 skip-ahead 的真實來源行，不是範圍標籤或替代 context。首個重用父 anchor 可位於游標之前，但不回退游標；後續 stacked anchor 必須向前找到。找不到就拒絕；使用最早合格 anchor 保留後方所有可能窗口，不以後一個 anchor 隱藏較早候選。
- EOF 是硬定位條件，不回退到正文其他位置。EOF 純新增可成立；無 context 且無 EOF 的插入則拒絕，要求提供定位依據。

這些是 Caliburn 的保守工程選擇，**不是通用 V4A 標準、語意正確性保證或已證模型最優門檻**。目前不猜行內片段、不自動重新折行。模型若拿到零／多處匹配，須重新讀取完整來源行或補足辨識上下文；不可默默放寬政策。T16／T17 再以真模型效果檢驗是否需等價改善。

## 3. 套用、錯誤與容量

`body_edits.py` 的 `apply_body_diff` 對全部 hunk 使用原文座標；前段新增／刪除不推移後段基準。只有全部解析與定位成功才形成新正文。保留行使用原文，不將模型的模糊 context 寫回；未改字元、LF／CRLF 混用、尾端換行與 Unicode 保持。某 chunk 的替換文字與實際來源相同時，整段原樣保留，避免 no-op 偷改混合換行符。新增行使用編輯位置的換行樣式；原文無尾端換行時，EOF 新增也不強加最終換行（必要行分隔除外）。來源與結果均不可為空白 body；建立／刪物件走各自能力。

錯誤為 `BodyEditError`，承接契約既有 `invalid_patch`、`patch_context_not_found`、`ambiguous_patch_context`；容量另用 `patch_limit_exceeded`，不能冒充無匹配或掃完後唯一。帶必要 hunk 編號／候選片段，工具邊界後續轉譯合法下一步；不將 raw exception／scope 交模型。

初始上限集中 `BodyMatchPolicy`：來源及結果 body 均至多 2,000,000 字元、diff 64,000 字元、128 hunks、估算完整掃描 20,000,000 字元工作量。估算涵蓋 context 與 anchors；超限整次拒絕，不只掃前段，也不能成功產生編輯器自身無法再處理的正文。這不是 token 門檻或時間保證；工具描述及工作總容量仍須後續接線。政策由 App 配置，不是模型參數；測例可用較小界線驗拒絕。

## 4. 尚未完成的接縫

- 讀取 schema／generated DTO、B1／B2/A 的讀取 handlers、map／read 與 title → ID 已交付，見 [工具接線](memory-tools.md)；尚未接模型執行。
- 寫入工具的原操作綁定、正文與 metadata／來源同次採用，及已提交後工具回傳恢復。
- Update 回傳真實前後差異與實際定位，不能只 echo 輸入 patch；這不是只返回編輯器的新正文就已完成。
- 寫入工具的真 PostgreSQL 接線、provider strict 接受與模型修正效果。純字串或讀取測例不證明上述能力。

既有規格的欄位與例子維持單一權威；本頁不另複製所有工具 JSON。
