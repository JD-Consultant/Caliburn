# 報告圖稿

[返回報告](../README.md)

本目錄的 `.mmd` 是可編輯來源，`.png` 是正文預設顯示版，`.svg` 是可放大的向量版。相同檔名的三種格式必須一起更新；不要只手修 SVG 或 PNG。圖說與適用範圍放在引用該圖的章節。下方圖名可直接開啟 PNG。

| 圖 | 視角 | 不可誤讀為 |
| --- | --- | --- |
| [01 價值循環](01-value-loop.png) | 產品活動 | 固定每輪必跑的 Graph |
| [02 系統全貌](02-system-boundary.png) | 執行位置與外部資料往來 | 全離線、資料完全不外送 |
| [03 程式分工](03-components.png) | 後端主要合作關係 | 每一條實際 import 或獨立微服務 |
| [04 訪談執行](04-consultant-turn.png) | 一輪的模型／工具往返與保存邊界 | 整輪只有一筆資料庫交易 |
| [05 三層依據](05-evidence-layers.png) | 同一任務引用理解，按需另引鏈外情境或對話 | 三種來源互斥、必須重複引用整條鏈，或分析角色的執行先後 |
| [06 背景整理](06-memory-batch.png) | 已採用的 B1 → B2 → 發布單向設計；現行程式仍有回交分支，見[第五章](../05-work-memory.md#背景整理如何開始與交接) | 已完整落實無回交，或使用者可控制的背景編輯 UI |
| [07 Memory 快照](07-memory-snapshots.png) | 固定修訂與重用 | 所有物件共用相同版本號 |
| [08 JD 核對](08-jd-recheck.png) | JD 局部依據核對 | Memory 必須逐引用確認 |

## 重新渲染

使用 Mermaid 11.17.2 渲染來源，設定 `theme: neutral`、`securityLevel: strict`，字體使用 `Microsoft JhengHei, Noto Sans CJK TC, sans-serif`。也可用與此版本相容的 Mermaid CLI；工具只用於文件製作，不加入產品執行依賴。

Mermaid 產生的 SVG 若包含 XHTML 標籤，輸出前須將 SVG DOM 透過 `XMLSerializer.serializeToString()` 序列化，不能把 HTML 序列化字串直接當成合法 XML。這會保留命名空間並正確輸出標籤，見 [MDN XMLSerializer](https://developer.mozilla.org/en-US/docs/Web/API/XMLSerializer/serializeToString)。不使用逐一替換 `<br>` 等修補方式。

每次更新後先檢查全部 `.svg` 能以 XML 解析，再讓瀏覽器以獨立圖片載入（例如 `Image.decode()`），不是只放進 HTML `innerHTML` 看起來正常。以實際 SVG 圖片產生 2 倍解析度 PNG，最後逐張確認中文無缺字、標籤未裁切、箭頭方向與本文一致。SVG 保留文字與向量；PNG 避免閱讀器對 SVG／XHTML 支援不同而無法顯示。

本圖組只使用本報告的合成資料與公開架構名稱，沒有實際訪談、金鑰、內部原始 reasoning 或資料庫連線字串。
