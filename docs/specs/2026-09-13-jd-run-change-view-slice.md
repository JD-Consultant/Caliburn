# 同頁查看 AI 整輪改動：收斂接線

- 日期：2026-09-13；Topic JD-R002，CV-01／RS-3–4；**當輪 API／畫面接合及分層驗證完成；真瀏覽器互動尚未驗**。
- Owner 最新指示：先大致完成核心流程並收尾，問題集中記錄，不再擴大研究。未解事項只維護[收尾清單](2026-09-13-jd-app-open-issues.md)，不在每份報告重建待辦全集。
- 需求沿[CV-01 已選方案](2026-09-12-jd-change-visibility-design.md)：AI 直接改稿，目前稿唯一可編；具名修改提示、同頁完整差異、刪除可見；不新增接受／拒絕流程。
- Owner 本輪進一步收斂：**只需當輪改動，不要求從舊對話選看整輪。**因此停止該入口擴充；不新增歷史選輪狀態、額外原 run 狀態查詢或相關控制器。既有逐次保存歷史保留，這不是尚待修好的產品缺陷。

## 本次具體交付

接通[已驗的固定比較材料](2026-09-13-jd-run-change-material-slice.md)到原 ChatService／HTTP 與管理畫面。員工看到本輪到目前為止實際保存的變更，可以展開完整前後；修改後又改回有明確區別。人工或其他回合夾在中間時，只提供這輪逐次原改動；較晚手改後不把現有文字標為該轮 AI 所寫。

## 既有能力與必要接合

| 接點 | 做法及責任 |
|---|---|
| 原生回合 | 初次查詢由既有 `AiRuntime.inspect_run` 確认 confirmed committed IDs 與當時 effects 是否已完整收尾；共同 `owner.inspect_document` 保持原服務的唯讀排空範圍。 |
| 固定續頁 | 既有 ItsDangerous signer／SHA-256、單一原 key／dataset、獨立用途 salt。保存本次 IDs、settled 與 offset，不存正文、不建表；續頁不重讀目前 run 擴張範圍。 |
| 真版本與差異 | 同一 `HistoryReader.read_run_change`；單 operation 與整輪共用原結構比較／完整 before-after 投影。整輪有自己的 envelope，不捏造 operation／change ref。 |
| 公開契約 | 在原 chat schema 新增 `ChatRunChangePage`；records 引用原 read schema。Python／TS 從正式 schema 生成，模型工具沒有新增欄位。 |
| HTTP／Web | 原 App 增一個唯讀 GET。Web 核文件／run／dataset、固定 capture 與續頁邊界，展示原記錄，不重算 domain 差異或解 token。 |
| 畫面 | 共用現有完整歷史對照；本輪區呈現具名摘要、刪除原文與舊所屬。目前欄位／項目標記使用已有 stable ID，限同輪且目前版次等於 E；手改候選／未完成表單時先收起標記。 |

## 唯一必要的容量驗證

既有 signer 除了檢查 token 長度，也依未壓縮 JSON 計算最壞上限，不能因壓縮後看似夠小就放行。96 個 UUID 字串的實際 token 約 3.1 KB，但 raw 上界 5384–5386 bytes，原限制必須拒絕。

本次使用 Python 標準 `UUID.bytes` 及 URL-safe Base64 保存同一組已確認 IDs：96 個 UUID 為 1536 bytes／2048 Base64 chars。實際 `ReferenceCodec._dump` 在 canonical document/run/dataset 下 raw 上界 3131 bytes，token 2428 bytes，可通過原 4096 限制。正常 256-byte ASCII dataset 上界 3424；大量需要 JSON escape 的控制字元仍可能超限，維持明示拒絕。正式 managed dataset／document／run 為 canonical UUID。

這是私有 continuation 的固定資料表示，沒有新壓縮／簽章算法或通用定位引擎。解碼核 16-byte 分組、最多96、不重複、canonical Base64 回編及嚴格欄位／用途／dataset／document／run；容量不靠壓縮率兜底。標準 signer 依據沿[已核框架接點](evidence/2026-09-13-jd-read-reference-preflight.md)，本輪沒有新套件。

## 未確認結果及錯誤

- 執行中或效果未完整確認，明示只看到本次已確認部分；「沒有修改 JD」只用於已完整且沒有 committed 的捕捉。
- 有保存但 S/E 相同，顯示沒有淨變更，保留原操作入口。非連續不顯示誤歸屬的整輪前後。
- 讀取失敗保留錯誤出口，不宣稱沒修改；重查只做 GET，不自動重送編輯或模型。
- 切文件／換回合或元件卸載後，晚回覆不覆蓋新畫面。標記還要在最後 render 同步核當前版次，避免等 effect 才清除的一幀誤標。
- 整輪撤回、Memory／來源與自然模型不是這個唯讀 API 的附帶實作；依收尾清單續接，不虛報完成。

## 驗證結果

| 責任／證據 | 實際結果 |
|---|---|
| [正式契約與 client](evidence/jd-run-change-view/contract-client.md) | Python157、client42及原client98各組 PASS；標準全組codegen `--check` PASS，不手改generated |
| [既有 signer 與新 capture](evidence/jd-run-change-view/cursor-results.md) | 新62、合併原reference155 PASS；容量、嚴格欄位及用途隔離 |
| [後端公開接合](evidence/jd-run-change-view/server-results.md) | 最後錯誤分界修正後70 PASS；此前含真PG67 PASS，各組重疊不相加 |
| [獨立真 PG／原生 Agent／SDK](evidence/jd-run-change-view/postgres.md) | 3 PASS：AI新增→較晚人工、純訪談、分頁期間再新增仍固定原捕捉；無provider網路 |
| [Web 整合](evidence/jd-run-change-view/web-results.md) | 最後全Web293 PASS；完整TS／build PASS；7個真正React/MUI靜態HTML案例，不代稱真瀏覽器 |
| [server獨審](evidence/jd-run-change-view/server-review.md)／[UI獨審](evidence/jd-run-change-view/ui-review.md) | 內部issuer錯誤歸因與同名要求所屬兩項P2已修並窄複核；限定範圍無剩餘P1/P2。舊輪入口依Owner新範圍覆寫，不假稱修好 |

只宣稱上表實際層級。新畫面的真瀏覽器點擊／捲動／晚回競爭未驗，瀏覽器連線根因沿問題清單保持 OPEN；不藉此擴大歷史入口或框架研究。

本次零產品模型呼叫，不啟用日常 AI；ADR0075 Proposed／production ADR0060 不變。既有官方依據繼續有效，只補會改變本次接合的容量反例，不另開品牌或框架廣搜。

## 正式契約與產生器的有限缺口

鎖定的生成器未保留 `if/then`，不能只用生成 DTO 宣稱條件已驗。保留原 JSON Schema 為唯一來源，以既有 `jsonschema 4.26.0` 的 `Draft202012Validator` 及 `referencing.Registry.with_resources` 補出站檢查；只載本 App 固定的 chat/read schema，沒有網路 resolver。OpenAPI 複製同一來源條件，唯一局部字串引用展開原定義，沒有另一份手寫規則。

依據：[python-jsonschema 官方 referencing 文件](https://python-jsonschema.readthedocs.io/en/stable/referencing/)，查閱2026-09-13；適用已鎖4.26.0、穩定、MIT，無新套件。**官方事實**是明示 registry／resources 的引用解析；**本案取捨**是用它補已觀察到的生成器缺口。正式包須攜帶同一 schema 資源，列入 OI-08；本單位未宣稱 production 封裝驗收。
