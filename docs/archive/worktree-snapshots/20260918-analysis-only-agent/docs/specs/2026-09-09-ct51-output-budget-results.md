# CT51：生成上限 8K／16K 比較結果

2026-09-09 · LLM-Q019／G5局部完成 · **16K在本情境可用，未證明需要升級；維持8K已驗收配置。**

[比較計畫／官方來源](../plans/2026-09-09-ct51-output-budget-comparison.md) · [完整請求、內容、工具回傳與原文核驗證據](evidence/2026-09-09-ct51-output-budget.json) · [CT49完整訪談基準](2026-09-09-ct49-fixed-long-interview-results.md) · [CT50配置驗收](2026-09-09-ct50-tested-profile-results.md)。

## 結論與決策

Owner要求試16,384，而非直接採用。兩組均完成真服務續談、自然背景整理及空近期Context的只讀回查，主要案例、條件、責任與原話檢查通過；均未耗盡8192，故沒有「提高上限避免截斷」的觀測證據，也不能宣稱提高上限讓推理更好。

**維持Luna／high與顯式8192，不改產品碼、預設、提示、Memory架構、compaction或工具上限。**16K保留為此情境測過可用的容量選項，未證明普遍更好／更差。若日後出現incomplete/max_output_tokens、或更長單次抽取／編輯需要餘裕，再考慮採用。這不是禁止16K，也不是把8K當成永久最優值。

## 固定條件／可比較程度

- 同一closed CT49完整11輪合成前端工程師資料庫，各建新複本；起始Memory、可見原文完全相同。固定產品source hash與HEAD `4f94fbfb2c47ed08235f8de188df88c29e2ff208`。
- A／B1／B2與診斷reader均Luna high、reasoning context all_turns；A／B2和reader皆16模型／15工具，native compaction12,000；只改Q019_MAX_OUTPUT_TOKENS的8192→16384。
- 首次送出的工具定義、opaque context及compaction設定相同；可見Context只有Runtime產生的當輪來源reference不同，正規化該reference後完全相等。未把不同run的reference偽造成相同。
- 同一自然續談增加「松嶼家具展示網站」快取案例、尚未實作的離線補送需求，以及雙週報表遇約定假日提前一工作日。兩組A均自行呼叫request_memory_consolidation，沒有腳本強迫通知。
- 每組等背景idle後，以同一題、空近期Context、既有只讀工具回查。reader指令比真顧問簡短，是獨立診斷，不冒充另一輪完整訪談。
- 8K先、16K後；只有一對樣本，生成路徑與快取命中不同，**費用／速度差不能歸因為上限的穩定效果**。未跑新一整份長訪談，不宣稱全職位100%保證。

## 實際結果

| 指標 | 8192組 | 16384組 |
|---|---:|---:|
| 實際模型請求總數 | 18 | 17 |
| 主顧問模型／工具 | 2／1 | 2／1 |
| 背景抽取請求 | 1 | 1 |
| 背景整併模型／工具 | 10／9 | 8／7 |
| 空近期Context回查模型／工具 | 5／4 | 6／5 |
| 所有HTTP結果 | 200／completed | 200／completed |
| API截斷／框架中斷 | 0／0 | 0／0 |
| 單次最高生成tokens（含reasoning） | 2,229 | 2,806 |
| 單次最高reasoning tokens | 586 | 1,304 |
| 累計生成tokens（含reasoning） | 9,442 | 9,934 |
| 累計reasoning tokens（已含於上一列） | 2,425 | 3,083 |
| 累計輸入tokens | 176,155 | 147,480 |
| 其中cached tokens | 122,617 | 107,351 |
| 其中cache-write tokens | 38,932 | 31,290 |
| 顧問回覆等待秒數 | 25.69 | 24.59 |
| 所有API請求耗時加總秒數 | 165.49 | 153.09 |
| usage估算費用USD | 0.02643694 | 0.02365812 |

共**35次、US$0.05009506估算**，低於48次／US$0.30實驗護欄，帳本closed。累計生成大於8192不是單次超限。不是每輪用滿上限，不是16K費用固定加倍，也不是16K必然較便宜。API秒數加總不是完整端到端等待；真正員工回覆時間另列。

## 內容與來源審核

逐一閱讀兩組抽取詳記／候選、整併before/after與回查答案；未加LLM評分器或新驗證Agent。

| 檢查 | 結果與邊界 |
|---|---|
| 案例辨識 | 兩組均分清松嶼舊圖片快取、青禾付款成功但前端權限未刷新、雲岸報名重複請求及焦點問題。 |
| 新案例細節 | 詳記保留API已新、排查工具、service worker/cache-first、資源版本與更新流程、測試情境、客戶確認、不能推成其他案通則。 |
| 未實作／責任 | 離線表單自動補送只是風險評估與估價，不寫成已完成；後端收件／郵件與伺服器維運權限未錯配。 |
| 頻率／條件／舊內容 | 保留所有專案、雙週週五、約定不工作假日提前一工作日、每日分流不變；knowledge diff皆只增新案例、修正報表子句，未刪其他有效工作範圍。 |
| 個案耗時 | 兩組均找到相同原句，未把「兩天」推成通用工時或SLA。 |
| 原文與引用 | 每組17個來源頁，共34頁，逐segment對canonical原文相等；原可見訊息前綴未變、新問答與實際API輸出相符。 |
| 狀態／隔離 | 各publication12→13；B idle、pending source=None；reader前後Memory相等；原CT49 DB與closed帳本未變、產品source hash未變。 |

本次新產生的27次tool call均有回傳；patch／write／validate回傳成功，未觀察到匹配失敗或重試修正。不能據此宣稱今後零工具錯誤。

非阻塞措辭限制仍記錄：8K回查把原文「未刪除客戶資料」改述為「未要求清除使用者端全部資料」，16K回查在「部分使用者」後額外特指「一般視窗」。兩者都比來源多一點語意限定，這些不是已核實的新事實；主要排查結論未變，不能說16K消除了措辭漂移。既有冗長導覽／重複工作句與Markdown縮排差異也未因加容量解決；本輪不順手改提示。

## 官方依據／推論邊界

- **Official fact：**[OpenAI reasoning guide](https://developers.openai.com/api/docs/guides/reasoning#allocating-space-for-reasoning)說明生成上限需要容納reasoning與可見輸出，耗盡可能回傳incomplete；加大可提供餘裕。官方起步探索的25K建議不是所有部署的硬性下限，也未保證16K一定優於8K。
- **Official fact：**[Luna模型規格](https://developers.openai.com/api/docs/models/gpt-5.6-luna)與[reasoning effort](https://developers.openai.com/api/docs/guides/reasoning#reasoning-effort)區分模型、推理設定及token容量；本輪沒有把high改成xhigh／max。
- **Official fact：**[標準API定價](https://developers.openai.com/api/docs/pricing)本輪使用短context input .20、cached .02、cache-write .25、output1.20 USD/百萬tokens；估算依實際usage，不當作帳單。
- **Observed：**所有請求上限均與arm相符、high/all_turns實際送出，且沒有生成截斷。
- **Inference／本案決策：**保留8K來自「未見容量瓶頸或明確效果改善」，不是大廠規定8K，也不是因為16K本次較貴（實際反而略低，原因包含不同工具路徑及快取，不能推為一般結論）。

## 環境與測試工具失敗沿革（不覆寫成成功）

1. 起初Docker engine pipe不存在；正常啟動後官方backend log於03:16:36 UTC回報sailor-ingest.sock不能rename為.stale。0次生成，未reset、刪socket或強殺。Owner後來正常重啟成功，engine29.7.2可讀；啟動原有測試PG容器後恢復。
2. 第一次離線pytest遇Windows tmpdir ACL WinError5，不算產品測試結果；換新臨時目錄／核准執行後，既有role/context budget **68項通過（12.01秒）**，1個Starlette/AnyIO deprecation warning，未改ACL／刪舊目錄。
3. CT51 test helper漏了既有CT50的TestClient(base_url='http://localhost')，預設testserver被TrustedHostMiddleware拒絕，取JSON失敗；只修helper後init通過。失敗留下未使用q019_ct51_8192_08936b71，仍保留；不是模型或16K錯誤。
4. helper語法、**16項觀測器邊界檢查**再次通過；finalize禁止遠端請求，成功封存兩組原文、reference與不變性核驗。無新產品元件或額外生成。
5. 封存後相同既有role/context測試再驗：**68 passed，12.90秒**，仍只有上述1項deprecation warning；證據checksum／相對文件連結／git diff檢查通過，產品src仍無diff。

## 封存與下一步

完整證據含固定輸入、請求／usage、工具／結果、問答、B1產物、B2 before/after、source核驗與實驗helpers；不含金鑰／opaque reasoning原文。證據SHA256：`b04dbe83c38f84a5bad40c650a95b9409f14d30e9531d990e3495fc4f1e109d6`。

兩測試DB與failed-init複本保留，不刪資料。帳本已closed，不重開、覆寫或暗中續費。本輪只有比較記錄，無production/JD、產品default、merge/push。下一步繼續使用CT50已驗收配置；若Owner想以16K作容量保險可另採用，不需重做Memory分層研究。
