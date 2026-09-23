# ADR 0078：同版 JD 唯讀定位與完整正文讀取

- 狀態：Proposed（2026-09-24；分支內施工、離線回歸及三筆有界真模型定位元件檢查通過，不以本文單獨宣稱完整產品驗收）
- 決策範圍：正式新 App 的 A 顧問讀取目前 JD；不變更 JD、Memory、來源或保存 authority
- 依據：[設計與比較](../specs/2026-09-24-jd-context-navigation-design.md)、[ADR 0075](0075-relational-jd-authority-and-structured-editor.md)、[ADR 0077](0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md)

## 脈絡

真實續談中的目前 JD 已達三頁；compaction 後，舊 item refs 不在當前模型請求中。六章逐章讀取沒有降低此稿回傳量，但只讀一個 item 需要先知道同版 ref。模型不應每輪讀全稿，也不能拿舊摘要或目錄代替尚未處理的原話、JD 正文或來源。

## 決定

擴充既有 `jd_read` 的 `locator` 唯讀 view：從相同 current snapshot 列出六章與每個項目的短線索、上層線索及 App 簽發的同版讀取 ref。需要修改時，先以該 ref 讀 `item/section` 的完整正文、關聯及必要來源；找不到或不確定時，沿既有 `current` 擴讀，全稿核對仍用 `current`。小稿可直接全讀，不強制每輪查 JD。

同一 `ReferenceCodec` 區分 `navigation` 與 `current` 用途，導覽 ref 不可進 writer。原 `AiToolSession` 從已驗的 ToolMessage／Saver 結果核對本輪模型可見、同版、完整分頁的讀取範圍；寫入所用 current refs 必須來自這些完整正文。App 持有 ID、revision、scope、cursor、Domain/CAS、receipt，模型只選 App 已提供的 ref。保留 JD 六章、K／S、來源、手動編輯與全稿回查。

## 拒絕的選項

- 將整份 JD 或全部工具結果每輪放入 prompt：重複佔用 context，不解決長訪談。
- 只用六章標題作最終定位：同一工作、共用 K／S 與低頻細節仍需項目級線索與擴讀。
- 新向量庫、索引服務、JD 摘要權威、Agent 或通用 patch／驗證框架：沒有本案效果證據，增加第二套狀態。
- 讓導覽 ref 直接可寫、讓模型自行組 UUID／version／offset：破壞現有 App 權責。

## 後果與升級條件

正式讀取契約新增一個 view 與 record，生成 Python／TypeScript 型別；沒有 DB migration。短線索可截斷，不能單靠它判斷不存在相關工作。三筆有界真模型定位檢查（含同一保存稿的一道題）及離線回傳量減少，不等於完整 A 旅程或最終 JD 品質通過；仍須驗跨關聯擴讀、較長訪談和最終品質。若漏找、關聯讀不全、步數／成本變差，保留全讀回退，先記具體 trace 再考慮受控文字搜尋，不直接升級 RAG。[驗收證據](../specs/evidence/2026-09-24-jd-locator-acceptance.md)。
