# Q019：獨立 Memory 回查與原生接口驗證

> 2026-09-07 · **有部分能力證據，正常訪談仍未通過；未修改產品程式。**
> 入口：[主 register](../../../../docs/current-decisions.md)；問題／官方契約：[MP-01研究](../../../../docs/specs/2026-09-07-analysis-provider-capability-review.md)；原成功產物：[B1校準](2026-09-07-b1-attribution-calibration-results.md)。不重新討論Memory分層。

## 1. 授權、方法與費用

Owner明確同意兩項獨立小測：合計最多12次生成、US$0.05保守預留、Luna／medium、不重跑整理、不改產品保護。實際run `9f89b07c8a9a` **12請求／US$0.00411000**，12個HTTP200；不等於12個完整成功。原生契約4次／US$0.00188100，回查8次／US$0.00222900。與此前6組累計為 **102請求／US$0.04772127**，不是正常訪談每輪成本。

真ChatOpenAI／OpenAI SDK／OpenRouter，SDK重試設為0（透過公開`with_options`更新真正client，不只改Pydantic設定）。共用同一12次帳本；第12次為補查壓縮契約，不延長回查8步、不增加總額。原文和測试內容皆合成案例；不保存金鑰／headers／原生opaque內容，只保存其是否存在與SHA256。

Memory重用前次真正B1/B2產物，沒有呼叫抽取／整併。原暫存Store／checkpoint已不存在，因此在InMemorySaver／Store以相同合成問答重建來源，公開reader產生新的合法引用，再保存原已生成文字；只改地址，不改工作內容。不宣稱是產品資料庫重啟恢復。先離線驗證重建成功，0次網路。實測輸入、tool回覆、產物、runtime引用映射、usage及探針全文保存於[分離證據](evidence/2026-09-07-recall-native-capability.json)。

## 2. 原生接口：什麼通過、什麼沒有

| 檢查 | 實際結果 | 可以下的結論 |
|---|---|---|
| 現有binding，`store:false`／`all_turns`，第一次生成 | completed；effective `all_turns`；有加密reasoning item | 這次支援原生項目，不需因gateway而先移除推理能力 |
| 第二輪加官方明示的include，接續第一輪 | completed；effective `all_turns`；第一輪reasoning的完整item指紋於第二、三輪wire皆相同 | adapter確實保留／重送該item，不只是把文字答案放回去；本輪無新reasoning且usage reasoning=0，不能當成遺漏 |
| 第三輪接續 | HTTP200但top-level **incomplete**；effective `all_turns`、有新的encrypted item | **不是成功完整訪談。**首版探針未保存`incomplete_details`，原因未知；不從低於output上限的usage猜原因 |
| 第12次獨立壓縮診斷 | 設threshold1024，input1573、output253、completed，無compaction；usage含248 reasoning tokens，但沒有reasoning item | 自動壓縮及每次原生item返回均不能宣告可靠。沒有把input1573等同服務端精確rendered context；也沒有證明gateway一定忽略欄位。不能把這次completed當成第三輪故障原因已解明 |

第12次是新的合成單輪診斷，不是繼續已用尽的回查，也不是重播第三輪的opaque history。沒有使用服務端debug資料證明轉送內容；沒有追加第13次。

官方意義：[OpenAI原生延續](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-across-calls)要求先前相容item可用；[OpenRouter context mode](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens#reasoning-context-mode)有對應設定，但實測不代表每次結果都完整。[OpenAI Compaction](https://developers.openai.com/api/docs/guides/compaction)的產生契約不能以OpenRouter型別接受`CompactionItem`取代。精確計數404仍是既有真產品阻擋，本輪沒有移除hook／再重試它。

## 3. 回查：不是沒存到，而是讀得過多

本輪沿用上次獨立回查的 `memory_access → build_agent` 與8 model／8 tool限額；**不是產品 `MemorySession → build_conversation` 的完整9 model／8 tool流程**，也沒有證明產品一定在第8步失敗。

實際順序：搜尋青禾 → 搜尋拾光 → 搜尋備份 → 讀整份21行knowledge → 列第一份詳記目錄 → 讀第一份詳記 → 讀其原始問答 → 列第二份詳記目錄。第9次模型被框架8步上限擋住，**沒有最終回答**。

- 第4次結果已包含題目要求的A/B付款、分工、更正、權限、驗收人、未知天數及一次搬設備。可直接從實際tool內容核對；這支持「資訊存在且可達」，不等於模型已答對。
- 正文→第一份詳記→原始問答鏈實際走通。最新更正詳記、第二份詳記尚未全部讀完，不能宣稱整條引用鏈的自然選擇已全測。
- 两次`ls`是在正文已提供確切摘要地址後再列目錄；廣泛題目先逐關鍵詞搜尋再讀同一短正文亦有減少往返的空間。但**這是本樣本的效率診斷，不是工具數目的普遍定律**。
- 沒有缺頁／引用錯誤／寫入失敗；不能用再加Memory欄位／資料庫／embedding來冒充已證明的必要修復。

## 4. 下一個修復範圍，尚未擅自施工

1. **讀取提示的局部候選：**導覽提供已知路徑時可直接有界讀；已足夠回答就答，存在歧義／需要精確原句時才沿引用深查；不必每題走完整層級，不先`ls`確認已有的文件地址。保留未知、修訂與來源核實規則；不用「禁止查原文」換表面成功。需同時核對實際A路徑與獨立reader，不能只改測試提示就宣稱產品已修。
2. **真正阻擋訪談的provider選擇：**目前exact counter404，原生壓縮未驗成。OpenAI直連是完整契約參考接法，但需要相符的key；保留OpenRouter則要明訂已證實可用的預算／壓縮策略，不能偷偷刪掉保護或以普通摘要冒充原生推理。更換框架本身不會讓gateway憑空多出端點。
3. 原生incomplete只顯示文字不能當成功。產品`TurnValidation`會擋未completed回覆；本次原生probe只觀察provider，沒有以它替代完整服務验收。

回查prompt精簡的官方原則是清楚說明何時用工具、充分資訊後收斂，非固定層層必讀：[OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)、[既有固定版本 extraction／prompt研究](2026-09-07-b1-attribution-calibration-results.md#2-官方依據與本案取捨)。具體閱讀政策是可逆本案映射，需用同題實測，不宣称為大廠統一流程。

## 5. 驗證與界線

本輪離線計數／失敗處理54 passed／8.87s，1既有warning；不把上輪528項當成本輪重新驗過。未改任何src／tests／版本，未啟動UI／JD／production、未重啟Docker、不merge/push。受限實驗已停止；費用及12次帳本可逐筆核對。**MP-01 OPEN、完整回查 OPEN、正常訪談未完成。**
