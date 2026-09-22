# JD 關聯式 App：八個編輯操作與共用準備邊界

- 日期：2026-09-13；Topic：JD-R002；RS-1 第二個有界單位。
- 承接[完整任務／一次更正切片](2026-09-13-jd-relational-command-slice.md)的 `5f92f29e` 基線；本稿記錄增量與目前驗證，不改寫前次 128 項結果。
- 需求／語意以[六章格式](2026-09-10-jd-format-review.md)、[欄位審核](2026-09-13-jd-field-sufficiency-audit.md)、[完整業務操作](2026-09-12-jd-business-operations-and-scope-design.md)、[工具契約](2026-09-12-jd-relational-agent-tool-contract.md)為準。
- 狀態：八個編輯操作及共同候選離線驗證完成；讀取、完整結果／HTTP、真 DB、畫面與顧問接線仍未完成。正式權責未切換。

## 1. 實際完成的效果

員工與 AI 的輸入都通過同一份生成契約，再進同一 App 準備邊界及 JD 業務規則。可以從空白逐步組成六章資料，再更正、移動、解除引用或刪除；模型不填資料庫主鍵、revision、position、operation 或選區 offset。

| 操作 | 已實作的業務效果 |
|---|---|
| `jd_create_task` | 一次建立任務及目前已知的多成果、多要求、共享 K/S 引用；有效未完整任務可以保存為候選，不補造未知 |
| `jd_revise_work` | 一次修正相依正文、子項、引用與全職位條件，全部基於同一版解譯，驗證最後完整候選 |
| `jd_set_text` | 修改一個已取得欄位；不以空字串繞過項目刪除／最低內容規則 |
| `jd_insert_item` | 新增職責、協作對象、知識、技能、成果、要求及全職位條件；各種類有自己的最小輸入，任務沿完整建立操作 |
| `jd_delete_item` | 刪職責保留任務及子项至未分組；刪任務移除自身從屬資料；仍被任務使用的 K/S 拒絕直接刪除 |
| `jd_move_item` | 任務移至其他職責或未分組；其他項目在原清單內排序；保留身分與子項，範圍更正受限於相關內容 |
| `jd_set_task_capability` | 同文件既有 K/S 的引用／解除；解除不刪共用定義，不改其他任務 |
| `jd_replace_selection` | 只替換 App 已捕捉的選區；讀取基準或全文已變即拒絕，不搜尋同字猜位置 |

以上操作產生**保存前候選**，`revision` 保持輸入值。測試可串接候選，不代表資料庫保存／重新發配 refs／正式反覆提交已成立。App 中顯示「已保存」仍須等 RS-2 的真實交易及回執。

## 2. 結構、定位及資訊保留

刪職責沿 D01：保留原未分組任務的相對順序，再按被刪職責內原順序接入，重新產生連續 position；不改任務 ID、成果、要求或 K/S。刪任務則刪自身子項、關係與 current source links，保留其他任務和共享定義。刪除來源不改掛至別項；歷史尚未由此純候選保存。

任務跨容器移動可以同次修正其名稱／敘述、成果要求及來源／目的職責的 `scope_text`，不能改不相關工作或藉移動改職責名稱。同容器重排不附內容更正。任務的必要適用範圍由內容方法保留，App 不猜測、複製或繼承職責文字；這些是本案已定產品規則，不冒稱資料庫框架自帶。

選區 token 的材料由 App 提供：欄位 ref、捕捉時 LF 全文、UTF-16 起訖與選中文字。模型只回 token、替代文字及來源。用 Python 標準 Unicode 編解碼檢查 scalar 邊界、實際選字及當前全文；繁中、重複字、emoji、換行與刪除選區皆有反例。拒絕在 surrogate pair 中切開；不宣稱已證明瀏覽器 native selection／中文輸入法／grapheme 操作。UI 捕捉與版本有效性仍待實測。

來源合併、內容摘要與排序沿[資料表 §3.10](2026-09-12-jd-relational-schema-and-write-contract.md#310-jd_source_link)；本次未增加另一份 Memory、正文格式或來源權威。`basis_refs=[]` 保留舊依據，不代表舊依據自動支持改後內容。

## 3. 分層與現成工具的責任

| 元件 | 責任及依賴界線 |
|---|---|
| JSON Schema／generated DTO | 八個編輯輸入的唯一跨語言來源；標準生成器產生 Python／TypeScript，不手改生成檔 |
| `transport.py` | 手動 envelope、模型 JSON／object 的形狀驗證及 provider 外殼；不执行 domain、不保存 |
| `application.py` | 一次準備呼叫、結果／例外保留、固定安全診斷；不 retry、不發配持久 operation、不宣稱 committed |
| `domain.py`／`selection.py` | 純候選、同文件／同版本 refs、業務不變條件、文字及來源規則；只依 Python 標準庫，不 import HTTP／ORM／SDK／UI |
| 後續保存／HTTP／UI／Agent adapters | 在各自切片接入同一核心；不能在人工／AI 入口各重算一套 JD 規則 |

AWS 的 [Hexagonal architectures](https://docs.aws.amazon.com/prescriptive-guidance/latest/hexagonal-architectures/overview.html)支持核心與外部依賴分開；本案採有界模組，不由此推導微服務。框架名稱仍是可替換的工程選擇，這八個工具及實體形狀也不能取代產品效果作為下一次選型的前提。

模型發布的 schema 改由**已生成的 Pydantic DTO**以 `model_json_schema(mode='validation')` 產生，只攜帶該工具實際使用的定義。使用 [Pydantic 官方 JSON Schema API](https://pydantic.dev/docs/validation/latest/concepts/json_schema/)；配合 [OpenAI 避免 schema divergence 的指引](https://developers.openai.com/api/docs/guides/structured-outputs#avoid-json-schema-divergence)，以生成檢查及三方正反例（SSOT、實際發布 schema、strict DTO）維持一致。不手寫 resolver、不將整份 catalog 重複送入每個工具。

查閱日期 2026-09-13；Pydantic 2.13.5／MIT、Python 3.12.13、Node 24.19.0 與生成器／SDK 精確版本均沿[前次鎖定及授權](2026-09-13-jd-relational-command-slice.md#4-現行工具與官方依據)，本次沒有新增依賴。公開文件可持續更新，發布 schema 的字節較少不代表已測 token、延遲或模型效果。兩家工具外殼依官方文件及真 SDK 離線請求核對，不稱服務端已接受。

## 4. 錯誤、紀錄及研究落地

本次[分層、錯誤與紀錄證據](evidence/2026-09-13-jd-app-boundaries-errors-logging-evidence.md)核對 AWS、IETF RFC 9457、OpenAI、Anthropic、Python logging、OTel 及 OWASP，分開官方事實與本案映射；沒有因查到新品牌而安裝另一套框架。

- 修正具名失敗被當成 Anthropic 成功結果：明列成功／失敗狀態，未知 status 拒絕；保留 provider call identity。這是外殼，完整 `status/effect/receipt_durability/next_action` 合法組合仍待 SSOT 實作。
- 修正 Pydantic 驗證例外 cause 在標準 traceback 露出原輸入：不保留對外 cause，加入 synthetic sentinel 反例。不是所有宿主／debug dumps 都已驗證的宣稱。
- App 只發固定事件及已核 request UUID、文件 ID、command、outcome、error code、耗時；不記正文／訪談／refs／參數或 raw exceptions。使用標準 logging 接口，沒有另外架 collector。
- 診斷 handler 失敗不得蓋掉原候選或例外；只隔離記 log 時的 Exception，不重試、不透過同一壞 handler 遞迴回報。log 永遠不能替代 DB operation receipt。

本次沒有宿主 handler 配置、輪替／容量、HTTP 問題格式或真 DB 故障測試。具體 BEL-R01–05 後續義務留在證據 §6；研究已足夠支援接續有限實作，不再廣搜 logging 品牌。

## 5. 驗證、首敗與獨立審查

全套最後一次驗證：**289 passed**；codegen check 的 Python／TypeScript 產物一致，TypeScript 型別檢查退出碼 0。使用此隔離目錄 lock、離線測試與合成資料；零付費產品模型呼叫、無正式 API／Web 修改。

| 證據類別 | 範圍與限制 |
|---|---|
| 契約 111 項 | 八個根、七個 insert variants、nullable、未知欄位、禁用 App 欄位及三方 acceptance；不證明服務端／自然模型 |
| Domain／選區 114 項 | 建立六章、所有八個操作、範圍與關係、候選原子性、繁中／UTF-16；沒有 DB COMMIT |
| Application／transport 33 項 | 結果分類、call identity、輸入不外露、診斷故障保留原結果；沒有完整 HTTP／receipt DTO |
| SDK wire 16 項 | 8 工具 × 2 SDK，每項兩個 POST 均由程序內 MockTransport 攔截；sockets／帳號探索封鎖，32 個 POST 不是 32 次模型呼叫 |
| 共同操作旅程 5 項 | 人工／OpenAI JSON／Anthropic object 均經 App→domain，八工具組合得到相同候選，原輸入不變；固定指令，不代表自然訪談品質 |
| 發布 schema 10 項 | 閉合欄位、實際 refs、無不相關 catalog、標準投影結果較原整包重複小；不以 byte 數推論模型 token |

首敗保留：新 domain 入口 **15 FAIL／52 PASS**、結構操作 **11 FAIL／85 PASS**；錯誤旗標／未知狀態 **11 FAIL**；短 sentinel 標準 traceback **1 FAIL**；diagnostic failure **3 FAIL**。最後全部修正。初版較長 sentinel 未成功重現，改用短 synthetic ASCII 後才確認洩漏；不能將最初綠燈當反例已證明。

獨立審查：錯誤／紀錄子例 BEL-R04a 已閉合，審查者另跑 application＋transport **33 PASS**，詳見[證據 §4](evidence/2026-09-13-jd-app-boundaries-errors-logging-evidence.md#4-本輪實作收斂與獨立窄審)。另一審查者在記憶體執行 **12 組反例 PASS**，含 25 種任務排序位置、D01 資料保留、跨職責原子更正、錯 owner／kind／self-anchor、emoji 後第二個重複字詞、UTF-16／stale 拒絕、共享 K/S 與未完整任務，無待修 finding；另唯讀確認八工具共同旅程的候選界線。首次 inline 因未設定 `PYTHONPATH=src` 而 import 失敗，尚未執行業務；明確設定後才得到 12 組結果。獨立臨時反例不加到 289 項持久回歸測試數。

交付文件另經獨立唯讀複核 PASS：本稿、README、計畫進度及證據路由沒有把框架寫成產品要求，或將候選宣稱為保存。靜態檢查 7 個文件範圍、78 個本機連結、22 個 anchor 通過；沒有為文件變更重跑已綠的程式測試。

## 6. 下一個有界單位

沿[RS-1–2 計畫](../plans/2026-09-13-jd-relational-app-implementation.md)，完成 current read／ref 發配、完整 mutation result 及 HTTP 投影；同時閉合十三表的初始化、資料層精確版本與交易接點。優先驗 operation 已 binding、結果未知、查回原回執、版本衝突與記錄失敗不影響保存結果。

只有需要相依元件的部分才選型及實測。真 DB、手動 App、自動保存、差異／撤回、顧問接線、自然模型與員工試用逐步驗證；Excel 保持延後，不能把純候選驗收當成品。
