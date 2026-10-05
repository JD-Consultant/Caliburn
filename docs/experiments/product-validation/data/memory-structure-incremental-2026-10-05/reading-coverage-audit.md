# 局部選讀為何漏掉責任：既有產物的離線核對

2026-10-05。**事後診斷，沒有新增模型呼叫，也沒有修改 `live-01` 原件或原評分。**本頁檢查的是內容放置與既有讀取路徑，不是新架構的品質成績。

## 1. 結論

在已完成的交付後缺陷題中，單集合漏掉的責任分工確實保存於另一項理解。若維持「每次讀取一項完整理解」且只從理解取得這題的全部依據，就必須讀到兩項；這個小例的理解集合也剛好只有兩項。**因此不能只改善搜尋或要求多讀，就聲稱已減少無關內容；閱讀單位本身也需要檢查。**

雙層的被選單元已帶必要分工，讀一項就足以提供四項判準的內容。但它同時包含乙案維護，亦不是理想的零無關閱讀。這不證明雙層普遍較佳；兩組產物都還有可改善的工作邊界。

## 2. 原件與計數

只使用 `corrections` 快照，未取第三批才出現的核准人與低頻工作。

| 組別／位置 | 正文內容 | `body` 長度 |
|---|---|---:|
| [雙層 D3](live-01/workspace-corrections-two_layer-b2.json)，`object_3` | 兩案逾時處理及分工 | 189 |
| 同檔 D4，`object_4` | 甲缺陷處理、乙維護及分工 | 259 |
| [單集合 S1](live-01/workspace-corrections-one_collection-single.json)，`object_1` | 兩案逾時處理及共同分工 | 134 |
| 同檔 S2，`object_2` | 甲缺陷處理及乙維護，沒有完整共同分工 | 170 |

長度是 PowerShell/.NET 字串的 UTF-16 code unit 數，保留正文換行及 Markdown；不是 token，不含標題、描述、來源、JSON、Prompt 或歷史重播。兩檔正文均沒有需要以 surrogate pair 表示的字元。本表不能直接換算模型費用。

| 路徑 | 已讀／設想的內容 | 這題必要事實的覆蓋 | 性質 |
|---|---|---|---|
| 雙層實際讀取 | D4：259 | 四項完整；最終答覆也四項完整 | 原真模型結果 |
| 單集合實際讀取 | S2：170 | 三項完整、一項部分；最終答覆亦同 | 原真模型結果 |
| 單集合補讀 S1 | S1＋S2：304 | 人工核對可取得四項所需內容 | 靜態反事實分析，**沒有執行這次補讀／回答** |

單集合補讀後等於此快照全部理解正文的 304／304；雙層實際讀取為 259／448。這些比例只描述本例的整項閱讀量，不是全庫召回率。讀到全部必要事實也不保證模型最後會全部使用；不得把第三列記為新的 4／4 模型通過。直接回查原話等其他路徑不在本次反事實分析範圍內。

既有實際工具回傳量為雙層 703、單集合 347 字元，完整輸入為 4,131、2,911 tokens；計法及原 API 用量見[結果 §4](results.md#4-完成的閱讀配對)。不可與本頁只算 `body` 的數字混用。

## 3. 對設計的意義

- 必要限定不能只留在一個「可看可不看」的相關入口。若不讀它便容易擴大本人責任，應在工作單元內保留最短且有來源的限定。
- 工作單元也不宜把所有相似工作塞一起。甲的缺陷回報與乙的例行維護有不同觸發、周期及變動範圍，可以比較拆分後是否更好選讀；不以物件數量作成功標準。
- 若保留少量共通責任重述，修訂時必須找回受影響的各項。這是更新成本，不能只報閱讀收益。
- 雙層第三批殘留舊未知的反例，屬於內容更新問題；更好的索引本身不會修正它。詳見[語意核對 §2](semantic-review.md#2-保存內容與來源)。

候選方法、來源及後續可證偽比較見[按需 Memory 與增量維護研究](../../../../research/agent-systems/2026-10-05-demand-loaded-memory-and-incremental-updates.md)。

## 4. 重現方式與完整性

在儲存庫根目錄使用 PowerShell；只讀檔，不載入 SDK、不連網、不使用資料庫。

```powershell
$runDirectory = 'docs/experiments/product-validation/data/memory-structure-incremental-2026-10-05/live-01'
foreach ($group in @('two_layer', 'one_collection')) {
    $role = if ($group -eq 'two_layer') { 'b2' } else { 'single' }
    $snapshotPath = Join-Path $runDirectory "workspace-corrections-$group-$role.json"
    $snapshot = Get-Content -LiteralPath $snapshotPath -Raw | ConvertFrom-Json
    $snapshot.objects.PSObject.Properties |
        Where-Object { $_.Value.layer -eq 'work_understanding' } |
        ForEach-Object {
            [pscustomobject]@{
                arm = $group
                object_id = $_.Name
                body_length = $_.Value.body.Length
            }
        }
    Get-FileHash -LiteralPath $snapshotPath -Algorithm SHA256
}
```

核對時 SHA-256：

- 雙層：`FAFFBC8A0FDBB8B89EBF6D1B9BCBD9BFC1C235D54D34A310CE190058BFC9893D`
- 單集合：`BD4A5F5C83F17AE522DF705DEF495EAD5BAFB8C864EA7322634F71E9B1E7DDDF`

沒有新增付費占用；累計仍沿[結果 §6](results.md#6-費用與可支持範圍)，不因這次離線核對重開已結案批次。
