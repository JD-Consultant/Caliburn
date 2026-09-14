# Q019／MP-01：正常訪談的 Provider 契約核對

> 2026-09-07 · **G2／受限G5完成，Provider接法尚未解決。**沒有關閉計數保護、降級原生推理、替換 Memory 或修改產品程式。真測結果只放[獨立回查／接口結果](../../.worktrees/analysis-only-agent/docs/specs/2026-09-07-recall-native-capability-results.md)。
> 入口：[current decisions](../current-decisions.md)。隔離程式基準 `82ac2266`；前段 [B1 校準結果](../../.worktrees/analysis-only-agent/docs/specs/2026-09-07-b1-attribution-calibration-results.md)只證明限定的記憶整理改善，不能替代實際訪談相容性驗收。

## 1. 本輪範圍

- **Topic／stage：**LLM-Q019／MP-01，G2；Owner 要求繼續研究、修復、調整至正常訪談。
- **Binding：**只分析隔離版、Luna／medium、原生跨輪 reasoning、完整原文及 ABC Memory；不改 production、不接 JD。
- **唯一阻塞題：**既有 key 的 OpenRouter 接口能否承接目前必備的計數、原生推理與壓縮契約？不能以「OpenAI-compatible」推定全部子 API 相同。
- **既有證據：**上輪計數 `/responses/input_tokens` HTTP404；B1/B2 的獨立 probe 可以生成，但刻意不測完整產品 budget／all_turns／compaction。回讀新版總設計、Runtime 稿、CT/SK 結果、MP-02 結果和實際 provider／budget／API factory／context 程式，沒有用被排除的08-12長稿。
- **不做：**重新比較所有框架、重跑已成功 B1/B2、加價／改 effort、猜測故障為 Docker、靜默 fallback。

## 2. 官方事實與已知實作

| 能力 | 直接官方資料／本地證據 | 本輪結論 |
|---|---|---|
| 精確生成前計數 | [OpenAI count API](https://developers.openai.com/api/reference/resources/responses/subresources/input_tokens/methods/count)；本地 `ResponsesBudget` 對最終 body 呼叫同 base URL 的 `/responses/input_tokens`。上輪實際 OpenRouter 返回404。 | **已確認阻擋**；重試同一路徑不能修復缺少的接口。尚無經查證的 OpenRouter 等價端點，不把沒有找到文件說成永久不支援。 |
| Stateless 訪談 | [OpenRouter Responses overview](https://openrouter.ai/docs/api_reference/responses/overview)要求客戶端重送歷史，拒絕 `store:true`／非空 `previous_response_id`。 | 現有 `store:false`、本地保存及手動 replay 的方向相容；不用另造 server conversation。 |
| 跨輪推理 | [OpenAI preserve reasoning](https://developers.openai.com/api/docs/guides/reasoning#preserve-reasoning-across-calls)說明相容原生 items 與 effective context；[OpenRouter reasoning context mode](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens#reasoning-context-mode)明載 GPT-5.6+ `all_turns`，並示範 `include:["reasoning.encrypted_content"]`。 | **有官方能力依據，不是已真測通過。**OpenAI 的 stateless 預設返回 encrypted items，不能直接推定 gateway 的預設也相同；需核對實際輸出及下一輪 wire，不檢視／解碼私有推理。 |
| 自動原生壓縮 | [OpenAI Compaction](https://developers.openai.com/api/docs/guides/compaction)區分 `context_management` 的自動壓縮與獨立 compact。OpenRouter [Responses API schema](https://openrouter.ai/docs/api/api-reference/responses/create-a-response.md)的 `ResponsesRequest`沒有 `context_management`，但 input／output 相關型別有 `CompactionItem`。 | **Unknown／契約缺口**：接受壓縮產物不等於會替我們執行壓縮；不能只看HTTP200就宣稱長訪談已壓縮，也不能只因欄位未列出就斷言一定拒絕。 |

OpenRouter schema 本輪取得358,981字元，UTF-8文字 SHA256 `be2d04e2bea4cb587e8ee5821d80595f38645e00a43493c8d21e1274755e8347`。核對 `ResponsesRequest`／`BaseReasoningConfig`／`CompactionItem`，`context_management`出現0次、`compaction`出現6次。這是查閱時的可變官方頁面，不是假稱固定 Git revision。官方 index 未找到 compaction 頁，只是搜尋結果邊界。

**因果診斷：**目前接線以 OpenAI 完整 API 為參考，但實際可用 key 是 OpenRouter。程式在生成前要求 gateway 提供精確計數，於是正常訪談也先被擋住。不能把這個配置錯誤歸咎於員工訪談內容、B1 Prompt 或 LangGraph Memory；同時也不能因獨立 probe 能回答就說全部契約成立。

## 3. 最小驗證與停止線

Owner已回覆「可以，依這個範圍測試」，核准一次小額驗證；先建立throwaway探針、離線驗證測試來源，再執行：

1. 只利用上次成功產出的 Memory／詳記與合成原文，獨立驗證正常漸進回查；不重跑 B1/B2。不偽造已消失的暫存 checkpoint：若重建測試來源，需要用真正 reader 生成新引用並明確標示 fixture 重建，不能聲稱產品重啟恢復通過。
2. Luna／medium 極小原生契約檢查：完整輸出保存及下一輪 replay、effective reasoning、必要 include，以及壓縮是否真有產物。精確計數404不反覆重送；不移除產品 hook 來宣稱產品跑通。
3. 兩項合計最多12次生成，保守費用預留 US$0.05，無SDK自動重試；既有完整回查的8步界線不默默提高。這是新獨立實驗，不是延長前一組24次限額。
4. 若接口不承接必要能力，停止盲試，將「直連支援該契約的 OpenAI endpoint」與「保留 OpenRouter、明訂不同 Context 接法」交 Owner 選擇。**後者不是無損等價**：一般文字摘要不能冒充原生 reasoning compaction，估算不能冒充精確計數。這輪不自行採任一降級。

## 4. 已執行與下一步

- 本輪重跑隔離 `tests/test_context_budget.py`：**54 passed，8.87s**，1項既有 Starlette／AnyIO deprecation warning，exit0。它驗證 mock HTTP 下的計數／安全失敗接線，**不是 OpenRouter 真相容或正常訪談驗收**。
- 只讀取 `.env` 的變數名稱確認設定來源，沒有顯示金鑰，也沒有把 OpenRouter key 送往 OpenAI 主機。沒有重啟／清空 Docker。
- Owner確認後完成12次生成／**US$0.00411**，未加額度。原生item重送有證據，但有一次incomplete；壓縮未驗成；回查8步用盡無最終答案。數據／限制集中於[結果](../../.worktrees/analysis-only-agent/docs/specs/2026-09-07-recall-native-capability-results.md)，不在本頁另複製完整紀錄。
- 未改產品程式。MP-01仍OPEN、完整 fresh-context Memory 回查仍OPEN。
- **Next gate：**先確認是否有與原設計相符的OpenAI直連設定；只有OpenRouter時，明訂不同預算／壓縮接法再施工。記憶讀取提示的收斂候選見結果§4。不得再盲試或以54項通過將「正常訪談」標成完成。

## 5. Owner 接續授權：本機直連設定

2026-09-07 Owner提供OpenAI credential並明確允許協助設定；只在隔離app的本機`.env`保存`OPENAI_API_KEY`／`OPENAI_BASE_URL=https://api.openai.com/v1`／`Q019_MODEL=gpt-5.6-luna`，已核對Git忽略且未追蹤。沒有覆寫舊OpenRouter設定、變更產品程式或啟動服務／付費請求；現有factory不自動讀此檔，後續需明確載入。金鑰不進研究、證據或提交；已提醒聊天暴露後應輪替。**設定存在不代表驗證成功**，尚未確認該帳戶的模型權限、計數及原生壓縮。

OpenRouter不是不能用：其[官方Responses文件](https://openrouter.ai/docs/api_reference/responses/overview)明確使用OpenRouter自己的key；OpenAI直連則使用OpenAI key。兩家credential／host不能交叉混用。既有OpenRouter生成及有限原生延續已有證據，當前阻塞是本案要求的精確計數404、壓縮契約未驗成，不是已證明key無效。**每次生成前精確計數是本案CT-01取捨，不是所有LLM應用的必須流程**；若改採OpenRouter相容方案，需保留預算與原生延續效果並明訂差異，不得宣稱關閉保護即完成修復。OpenAI直連是目前建議的最少接線變動，不等於已證明品質或成本最佳。

最新接續：Owner同意重審「每次生成前精確count是否必要」，研究與框架底層核對改由[CT-02短審閱](2026-09-07-context-engineering-native-first-review.md)持有；其原生優先建議尚待核准，未變更產品接線。下一gate先定Context接法，再做隔離窄修及明確小額的真endpoint驗收，不因直連設定存在而跳過設計。既有12次實驗已結束，不能藉新key重置其額度。獨立review已核對前段結果／證據，無actionable finding；其結論不是產品驗收通過。
