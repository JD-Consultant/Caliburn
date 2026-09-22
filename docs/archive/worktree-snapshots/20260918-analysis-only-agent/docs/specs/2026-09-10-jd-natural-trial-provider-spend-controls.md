# P3：OpenAI API 支出控制的可用範圍

查閱日：2026-09-10。依 OpenAI Docs，實際取得下列三份官方頁面正文；限公開文件，不查帳戶／key／env／usage，不購買credit、不改設定、不發provider或count請求。未重新研究模型token／compaction上界，未改code／計畫／授權。Task5不受此查核阻擋。

**結論：官方現在有可拒絕API流量的 organization／project hard spend limit，不能再籠統說專案只能提醒；但官方明示執行非即時、實際記錄支出可能超額。因此所查機制仍不足以證明P3單批帳單絕對不超過US$1。** 此結論不把原硬上限自動降成estimate，不閉合P3-B01。

## 官方事實與直接來源

1. [Spend limits guide](https://developers.openai.com/api/docs/guides/spend-limits)
   - Spend alerts只通知，API繼續；另有可啟用的硬限制，組織或專案达到追蹤支出門檻後拒絕受影響請求。
   - 專案只管歸該專案計費的流量；組織限制涵蓋其各專案。兩者為月週期；提高／移除限制在更新傳播後可恢復，否則等下個月。
   - 直接限制語句：**“Enforcement is not instantaneous.”** 官方接著說狀態傳播期間仍可能處理少量額外usage，記錄支出可略超設定額。未給可換算為固定美元／百分比的最大超額值。
   - 設定畫面要另開 `Enforce a hard limit`；不能把單純Monthly budget／alert數字視為已強制。本文不曾進設定頁確認任何帳戶實際狀態。

2. [Project spend limit API reference](https://developers.openai.com/api/reference/typescript/resources/admin/subresources/organization/subresources/projects/subresources/spend_limit)
   - 官方提供 `/organization/projects/{project_id}/spend_limit` 的GET／POST／DELETE；POST建立或取代限額。
   - 契約欄位為USD、month、以cents計的threshold_amount；回傳enforcement.status可為inactive／enforcing。它是project層級，不是單個request、trial或API key的budget。
   - 此頁未提供US$1設定在特定帳戶必然可用的承諾、單批reset語意、在途工作結算保證或零超額保證。文件範例不是本帳戶已配置或已生效的證據。本輪未發任何管理API呼叫。

3. [API error codes](https://developers.openai.com/api/docs/guides/error-codes)
   - `429 project_spend_limit_exceeded`、`organization_spend_limit_exceeded`、`organization_usage_limit_exceeded`、`credit_balance_exhausted`是不同原因；應看error.code，不能只靠insufficient_quota這個大類推斷。
   - 預付餘額耗盡時可回credit_balance_exhausted；文件給的是拒絕／恢復條件，沒有在此提供預付餘額絕不負值、單筆在途費用不超額或精確小額隔離保證。因此不能從此推導「只留US$1信用額就完全封頂」。本輪不引用未取得的預付方案最低充值／自動充值／到期等細節。
   - 撤銷或無效API key可導致401；這是認證拒絕，非按累計美元自動停止。沒有從所查頁找到key級獨立支出上限契約。

## 本案推論與建議（非官方保證、未採用）

- **可用範圍：** 有權限且適用的專案硬限制可作額外provider側止流防護，與alerts分開。它確實比只發提醒強；不可忽略新版官方能力。
- **不足處：** 官方允許傳播超額而未給數值上界，不能用「slightly」假填安全預留美元。月度project／org範圍亦不是獨立P3批次；本輪未核其餘流量、帳戶是否支援／enforcing或端點計費project，所以不承諾現在可直接用。預付耗盡與撤key也不補足未知的在途帳務界線。
- **下一步：** root在核心、具體guard及執行包準備完成後，將真實可保證／不可保證的費用條件交Owner。若仍要求絕對US$1帳单上限，這三份官方文件不足以支持；不得自行改成估計上限或先試付費請求。

與 `docs/specs/2026-09-10-jd-natural-trial-billable-bound.md` 的關係：本輪只檢查provider側能否繞過其Unknown；答案是「有強制止流機制，但沒有得到單批零超額保證」，因此不關閉原B01，不重開模型token研究。Codex聊天帳戶額度／重置完全未查，也不能抵算本App的OpenAI API美元支出。

Status：有限官方查核完成；0產品provider／count請求；P3仍NOT AUTHORIZED。唯一新增本scratch報告，無新當下Owner問題、無production或Task5變更。
