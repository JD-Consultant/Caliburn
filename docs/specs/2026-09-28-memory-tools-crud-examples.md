# Memory CRUD 工具：集中審核範例

- 日期：2026-09-28；最後核對：2026-09-29。
- 狀態：**已定效果與工程設計的接續範例；未實作、未經 SDK／provider 或保存驗收。**最新目標允許無來源候選；情境移除會同步解除候選理解對它的綁定，但不刪理解或歷史發布。以下非實際 schema／資料表設計。
- 維護者：工程協作者；決策者：Product Owner。
- 用途：用同一合成情境核對 Create／Read／Update／Delete，不是 DB CRUD API，也不是正式 JSON Schema。
- 唯一規則來源：[共同工具規範](2026-09-27-agent-tool-contract-design-research.md)、[Memory 讀取與來源回查](2026-09-27-memory-read-and-source-navigation-contract.md)、[單物件寫入契約](2026-09-27-memory-object-update-tool-contract.md)。本頁只放使用示例，規則變更須先更新責任文件。
- 入口：[全產品導覽](../target-architecture-map.md)。

## 1. 範例邊界

| 操作 | B1 工作情境入口 | B2 工作理解入口 |
|---|---|---|
| 建立 | `create_work_situation` | `create_work_understanding` |
| 讀取 | `read_work_situation` | `read_work_understanding`，亦可使用情境 read |
| 修改 | `update_work_situation` | `update_work_understanding` |
| 刪除 | `delete_work_situation` | `delete_work_understanding` |

以上依[共同規範 §2](2026-09-27-agent-tool-contract-design-research.md#2-命名與-description-候選規範)選定動賓短語名稱，與 read／write 責任契約一致；先前資源前綴名稱不再作活動範例，也不註冊同義別名。本例核對操作內容與效果，不代表新增八份實作或已完成工具註冊。B1 不能讀寫理解；B2 不能改情境；A 只能沿授權 read 取得本 Turn 固定的已發布 Memory，不使用上述 Memory 寫入工具。

所有寫入只作用本批候選。App 綁定職務檔案、權限、原工作、操作身分、候選基準及內部 ID；不要求模型填寫。候選範圍由工具說明與執行綁定表達，Create／Read 不重複回 stage；模型不能用參數切換成 published。Title 僅為選擇值，不是 DB 尋址鍵。本文一般 read 示範本批目前工作稿，不冒充已解決同名歷史版本回查。

單一資源的內容參數維持 `title`；讀改刪的既有目標用 `target_title`。Update 的 `changes[]` 承接已定的「同一物件多欄一次修改」；Create 回 created、Delete 回 deleted、無變更回 unchanged，Read 只回內容不附 status／stage，Update 回實際 title／description／applied_changes 且不附 stage。這些是工程設計，不是待 Owner 重選的結果效果；生成 nested strict wire、容量與可靠保存仍待實作驗證。

合成前提：B1 已從合法資料讀到正式訪談序號 12、14，足以整理本人盤點及異常交主管的已知內容。稍後讀到序號 28 的更正，確認頻率為每月而非每週。序號均在本批上界內，不是 Agent Turn、DB ID 或模型自編的引用。12、14 仍有保留價值，所以更新只新增 28，不因更正就抹掉舊原話。

以下 JSON 是工具 arguments 或 App 結果的內容，不含 OpenAI 原生 call/result 外層；實際接續仍須與原呼叫配對。`\n` 表示正文換行。所有員工工作內容都是合成示例，不是實際研究發現。

## 2. Create：一次建立完整候選

B1 呼叫 `create_work_situation`：

```json
{
  "title": "庫存盤點",
  "description": "本人核對帳實差異，異常交主管確認；關鍵詞：盤點、庫存差異。",
  "body": "## 工作內容\n本人核對實際庫存與帳面記錄。\n\n## 處理頻率\n每週進行一次。\n異常交由主管確認，本人不決定庫存調整。\n\n## 尚待釐清\n差異金額是否有分級門檻尚未確認。",
  "interview_references": [12, 14]
}
```

App 在內容、來源資格及同層標題唯一等操作檢查通過，且候選與結果可可靠承接後回傳：

```json
{
  "status": "created"
}
```

建立時交完整初值，不用 `changes` 或 body diff；沒有先建空殼、再分次補欄位的要求。回傳來自已保存結果，不只是重述請求。成功不代表正式發布；同層重名不覆蓋既有物件。來源可為空；任一提供的來源或必備內容無效時，不留下半筆建立結果。

原 call 中已有模型提交的初值，正常成功不必再次抄回。這個短結果表示已完整採用提交內容，不代表 App 可以默默改寫 title／正文後只回 created；真正需要模型知道的差異或錯誤另按契約返回。內部恢復資料不因此縮減為一個 status。

## 3. Read：取得正文與獨立引用

B1 或 B2 呼叫 `read_work_situation`：

```json
{
  "target_title": "庫存盤點"
}
```

App 回傳完整物件內容，引用與 body 分開：

```json
{
  "title": "庫存盤點",
  "description": "本人核對帳實差異，異常交主管確認；關鍵詞：盤點、庫存差異。",
  "body": "## 工作內容\n本人核對實際庫存與帳面記錄。\n\n## 處理頻率\n每週進行一次。\n異常交由主管確認，本人不決定庫存調整。\n\n## 尚待釐清\n差異金額是否有分級門檻尚未確認。",
  "interview_references": [12, 14]
}
```

數字是供模型選取的正式訪談序號，App 仍保留其對應來源身分；不是另定 UUID 或取消來源 ID。若需原話，依共用訪談工具查 12、14 或所需範圍，回傳須有正式序號、說話者及完整訪談原文。本例不把所有來源全文一併塞入 Memory read。

A 使用同類 read 時，App 取本 Turn 固定已發布基準，不讀本例尚未發布候選，也不回 stage。讀取不套用 `applied_changes`，也不回重複的 `status: read`。模型可見導覽仍只提供授權範圍全體集合的 `target_title`／`description`，沿[讀取契約](2026-09-27-memory-read-and-source-navigation-contract.md#1-已確認的讀取內容)按需取得；本頁不另設一份導覽 schema。

## 4. Update：同次改名、導覽、正文與引用

B1 已核對訪談 28，呼叫 `update_work_situation`：

```json
{
  "target_title": "庫存盤點",
  "changes": [
    {"field": "title", "value": "月末庫存盤點"},
    {"field": "description", "value": "每月核對帳實差異，異常交主管確認；關鍵詞：月末、盤點、庫存差異。"},
    {"field": "body", "diff": "@@\n ## 處理頻率\n-每週進行一次。\n+每月進行一次。\n 異常交由主管確認，本人不決定庫存調整。"},
    {"field": "interview_references", "add": [28]}
  ]
}
```

App 成功採用後回傳：

```json
{
  "status": "updated",
  "title": "月末庫存盤點",
  "description": "每月核對帳實差異，異常交主管確認；關鍵詞：月末、盤點、庫存差異。",
  "applied_changes": [
    {"field": "title"},
    {"field": "description"},
    {"field": "body", "diff": "@@\n ## 處理頻率\n-每週進行一次。\n+每月進行一次。\n 異常交由主管確認，本人不決定庫存調整。"},
    {"field": "interview_references", "added": [28]}
  ]
}
```

回傳中的 `diff` 是 App 由真正套用前後內容形成的差異。本例精確匹配，所以文字恰好與輸入相同；不能實作成無條件 echo。模糊匹配時，必須反映實際位置與必要上下文，未指定的內容保持原樣。短欄位的新值已在頂層，不重複 value；只列實際變更。完整結果不可靜默截斷；容量準備與恢復沿寫入契約，不由本例另定 token 常數。

本次四項全部成功才採用；任一不合法，整次不改。引用最後為 12、14、28；其他內容及未知事項保留。後續一般操作使用成功回傳的新 title；改名不是刪除再建立。不要求每次一定填四項，只改描述就只留該筆 change。

V4A 只處理已選物件的 body hunks，不帶自由檔案 path 或 `Add File`／`Delete File`。官方把 diff 解讀與套用交給執行方；唯一匹配及本次全部採用仍是 Caliburn 必須驗證的保護，不是假設原生 helper 自帶。[OpenAI Apply Patch](https://developers.openai.com/api/docs/guides/tools-apply-patch#apply-patch-operations)（核對：2026-09-28）。

## 5. Delete：保存候選移除，不刪歷史

獨立情境：B1 後續核對後，判斷此情境應併入另一個已妥善承接內容與訪談依據的工作情境。呼叫 `delete_work_situation`：

```json
{
  "target_title": "月末庫存盤點"
}
```

App 已採用本批候選移除、同步解除必要候選關係，且原操作結果可可靠承接後回傳：

```json
{
  "status": "deleted"
}
```

`deleted` 表示候選移除已成立，不是只收到意圖；不要求新增 DB status，不聲稱歷史永久刪除或整批可發布。App 在同一次候選操作解除所有指向此情境的候選理解綁定；理解物件仍在，變更資料供 B2 判斷，但本結果不向 B1 暴露理解標題、正文或依賴清單。

若有理解原本引用被移除的情境，App 已解除該候選關係；B2 在正常分析中決定是否補入仍成立的依據、修訂理解、保留空來源，或刪除不再成立的理解。App 不猜替代來源、不連帶刪理解；B2 未完成語意分析前不發布。本次工具成功不等於 B2 已完成處理。B2 的理解 delete 亦只處理自己層的候選移除，不刪 JD 或歷史來源。

## 6. B2：相同操作風格，不同來源與權限

以下接在 Update 成功後、尚未執行 Delete 的分支。B2 已讀過「月末庫存盤點」，分析後呼叫 `create_work_understanding`：

```json
{
  "title": "庫存差異辨識與回報",
  "description": "辨識帳實差異並提供主管判斷所需資訊；不包含庫存調整決策。",
  "body": "## 目前理解\n本人透過盤點辨識帳實差異，將異常交主管確認。\n\n## 責任邊界\n本人不決定庫存調整。\n\n## 尚待釐清\n分級回報門檻及其他適用情境仍待確認。",
  "work_situation_references": ["月末庫存盤點"]
}
```

建立正常成功同樣只回 `{"status":"created"}`，不重複理解的內容或引用。之後 B2 或 A 可依各自候選／已發布範圍呼叫 `read_work_understanding`：

```json
{
  "target_title": "庫存差異辨識與回報"
}
```

B2 在本批讀取的結果示例：

```json
{
  "title": "庫存差異辨識與回報",
  "description": "辨識帳實差異並提供主管判斷所需資訊；不包含庫存調整決策。",
  "body": "## 目前理解\n本人透過盤點辨識帳實差異，將異常交主管確認。\n\n## 責任邊界\n本人不決定庫存調整。\n\n## 尚待釐清\n分級回報門檻及其他適用情境仍待確認。",
  "work_situation_references": [
    {
      "target_title": "月末庫存盤點",
      "description": "每月核對帳實差異，異常交主管確認；關鍵詞：月末、盤點、庫存差異。"
    }
  ]
}
```

讀取來源列以 `target_title` 和描述標出可按需深入的情境，不附全部情境正文。**本例 B2 沿候選引用的穩定身分取得目前候選內容**，包括來源改名或 B1 新修訂；不是讀當初建立理解時的舊情境修訂。A 則在本 Turn 固定已發布 Memory 內逐層讀取；人／App 的舊快照回查才保持當時固定鏈，不以同名最新物件替代。B2 update 沿相同 `changes` 表示，引用 field 為 `work_situation_references`，add／remove 選情境 title；不能把 B1 的 `interview_references` 分支交給 B2 直接寫正式引用。

<a id="7-失敗範例與仍未定事項"></a>

## 7. 失敗範例與剩餘驗證

若某次 body hunk 在實際正文有兩處合格匹配，候選回傳如下；這是獨立反例，不宣稱上方唯一的「處理頻率」範例有兩處：

```json
{
  "status": "rejected",
  "code": "ambiguous_patch_context",
  "target_title": "月末庫存盤點",
  "message": "第 1 個正文修改區塊有兩處合格匹配；本次全部未修改。",
  "candidates": [
    {"heading": "月末盤點／回報方式", "excerpt": "異常交由主管確認。"},
    {"heading": "臨時複核／回報方式", "excerpt": "異常交由主管確認。"}
  ],
  "next_action": "依要修改的段落補上實際標題與前後文；仍不清楚時先讀正文，再提交修正後的 diff。"
}
```

候選片段只是有界定位資料，不是兩個可直接執行的索引；模型須提出新的明確意圖。`ambiguous_patch_context` 及必要片段沿寫入契約；實際位置不得由 App 猜造，排版及 wire 留實作驗證。保存結果不明不適用 rejected，應先走既有結果核對。若目前標題找不到或原操作綁定後失效，回相應錯誤，不重定向原操作；新呼叫以已重用的標題選到目前物件則合法，不能聲稱知道模型未表達的舊意圖。

其他必要反例沿責任契約：同層重名建立不覆寫、跨層同名允許、空來源建立與移除最後來源可成立、無效來源拒絕、後段 hunk 失敗全次不改、已知無差異才回 unchanged、刪除不洩露禁止層、被刪情境不留下懸空候選關係、B2 未完成語意分析不得發布。

本頁核對模型可見的 CRUD 使用方式及結果可讀性。分支、改名重用與最小結果已有設計；生成 strict schema、原操作與歷史來源映射、候選保存與結果恢復、容量接線仍待實作驗證；最新[生命週期](2026-09-25-b1-b2-information-gap-lifecycle.md#候選操作快照與三個安全點目標已確認未實作)已確定候選按物件身分維持關係、發布才固定版本，不要求模型用 `add` 同名換版或執行逐條確認。本頁不可直接當完整施工 wire 或驗收證據。

## 8. 名稱重用、空來源與 scope 反例（工程設計／未實作驗證）

- 情境 C 原名「庫存盤點」，改名「月末庫存盤點」後，D 可新建為「庫存盤點」。新呼叫 `read_work_situation({target_title:"庫存盤點"})` 讀 D；原來連 C 的理解來源列顯示 C 的新名，不改連 D。原操作重入仍用已綁定的 C，不重新解析舊名稱，也不新增 read proof。
- 理解只連 C 時，`work_situation_references` 的 `remove:["庫存盤點"]` 解析 D，因不是該理解成員而整次 `reference_not_found`；`remove:["月末庫存盤點"]` 才移除 C，來源可成為空集合。這不刪 C 或任何歷史資料。
- Create 可明列 `interview_references:[]` 或 `work_situation_references:[]`；完整 read 也回空陣列。Update 不接受空 `add`／`remove` 佔位，但可明列 remove 移除全部既有成員；只改引用仍回 updated，不以正文未變回 unchanged。
- `read_interview` 選 `[12,14,28]`，但 28 超過本批 F 時整次回 `scope_not_allowed`，不得只回 12、14 冒充完整。格式不合法回 `invalid_arguments`；無權範圍不洩露原話。起始 K／H／F 及前問補充沿 read 契約，不用讀取去推進涵蓋。

以上為契約反例，不是已執行的產品測試。
