# Q12：本輪 JD 保存事實如何進入長對話最後回答

- 日期：2026-09-24
- 階段：G5 比較與隔離驗證；**非 production 設計核准，也未修改正式接線**
- 範圍：新 App 的 A 顧問，本輪 JD 寫入事實。B1／B2／C、JD 導覽、Memory 與 compaction 權責維持既有設計。
- 原始實例與先前反例：[C-W 續談證據，Q12 兩節](../../experiments/legacy-evidence/2026-09-23-gpt6-cw-natural-trial.md#q12-本輪保存真相最後-request-view-的唯讀對照2026-09-24)。

## 問題與已知事實

同文件一個真實 A 回合有兩筆 `committed` JD operation，最後回答卻說本輪沒有新保存。最後 request-only 視圖看不到兩筆 writer ToolMessage；此時模型能讀到新版 JD，所以不能把錯報單獨歸咎於 compaction。現行 `JdNoticeMiddleware` 提供固定 `turn_start` 與滑動的 `since_previous_response`，合成三次模型步驟已證明中間可見的一次 JD 保存訊號，經下一次無 JD 修改的往返後，不再明確出現在最後通知。來源、收據和 JD 正文不是同一種事實：**目前 JD 含某段內容，不證明它在本輪提交。**

現有權責包括 `jd_operation` 的 run-scoped receipts、`jd_ai_bindings`、原生工具結果與 Saver。`HistoryReader.read_run_operations()` 按操作 UUID 排列供穩定呈現，非執行順序；空列不證明 run 沒有操作，也不證明進行中／未明寫入已失敗。關閉 run 的 `inspect_run()` 已會核對 binding、receipt 與工具結果，但不能未經驗證就從活動中的模型節點重入。

## 研究來源與可用邊界

查閱日 2026-09-24。OpenAI [Agent Sessions](https://developers.openai.com/api/docs/guides/agents-api/sessions) 將執行結果與整段回合完成分開；[compaction](https://developers.openai.com/api/docs/guides/compaction) 保留對話延續資訊，並不提供 JD 交易權威。[LangChain context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering) 區分模型暫時可見內容與保存狀態；[LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence) 提供狀態／checkpoint，但本案仍由 JD SQL 收據決定保存效果。[Anthropic context editing](https://platform.claude.com/docs/en/build-with-claude/context-editing) 可選擇性清除舊工具結果，顯示工具結果留存需按用途取捨；它不替 Caliburn 指定 JD ledger 的形狀。**「長對話上下文不應成為業務保存 authority」是這些資料映射到本案的推論，不是廠商公布的相同底層實作。**

## 本次驗證

沿用鎖定 App runtime 與既有 P3 費用閘門；合成資料、OpenRouter Responses、`openai/gpt-6-luna`、OpenAI-only、`store=false`、零自動重試、無 fallback、無正式 JD／Memory 寫入。四個獨立帳本各限制 4／4／1／2 筆請求及 US$1.06／1.06／0.27／0.54 的保守預留上限。實際 **11 筆全數 settled，OpenAI provider、目標模型一致，合計 US$0.0010210，未知費用 0**；第一批四筆因讀取器把 encrypted reasoning 混在 `AIMessage.content`，只算 transport 證據，**不算回答品質樣本**。其餘七筆才以文字區塊評估。

| 合成情境 | 真模型可見回答 | 本次觀察 |
|---|---|---|
| 只有 JD v7 正文與不含收據的摘要 | 無法確認本輪保存；也不能推成零 | 沒有把「目前有內容」誤說成本輪保存 |
| App 可信結果列兩筆 committed | 說明兩筆已保存，排除沒有收據的主管決策句 | 簡短狀態足以支援此合成收尾 |
| App 可信結果列確定 `invalid_input`、零 committed | 說明本輪未成功保存，且 v7 是前一輪內容 | 能區分確定失敗與已有正文 |
| App 可信結果列 `unknown` | 明說無法確認成功或失敗 | 未把查無成功收據當作未保存 |
| 一組原生 AI tool call＋可信 ToolMessage | 只稱工具回執中的內容已保存 | 原生回執保留在可見 context 時同樣有效 |
| 過時摘要說「沒存」，可信 App 結果說已存 | 依可信結果說已提交 | 此合成衝突未被摘要誤導 |
| 過時摘要說「沒存」，原生可信 ToolMessage 說已存 | 依工具回執說已提交 | 可見工具回執也勝過此合成摘要 |

零付費回歸：顧問通知／compaction 相關 **26 passed**；run receipt、inspection 與 tool 規則 **112 passed**；隔離 PostgreSQL receipt 讀取 **5 passed**；正式 API＋PostgreSQL＋Saver 的本輪 operation／歷史查回 **1 passed**。上述測試沒有加入新的產品修法；不把一回合模型表現推為長訪談正確率。

## 比較與建議

| 候選 | 效果 | 長對話／恢復風險 | 本次結論 |
|---|---|---|---|
| 只保留舊 writer ToolMessage／完整工具 wave | 原生、模型容易理解；合成模型測試有效 | Q12 真實最後視圖正好已切掉回執；要跨切點保留非連續 pairs，需保證配對、順序與有界大小；長輪多操作可能增 context | 作為近期自然 context 保留，不宜作唯一完成保證 |
| 只從目前 JD 正文或摘要推斷 | 無新增讀取 | 不能知道內容何時、由誰保存；摘要可過時 | 不採作保存證明 |
| 本輪完整進度另存可寫模型筆記／新 ledger | 可避免每次 SQL 查詢 | 容易形成第二 authority、恢復／對帳與雙寫問題 | 無證據支持，不採 |
| 完全按需查詢本輪結果 Tool | 平時省 prompt | 模型可能在 final 前不呼叫；增加模型／工具步數，無法保證本例得到事實 | 可作深入檢視，不宜作唯一收尾保護 |
| 回答生成後才攔截或重生 final | 可偵測某些矛盾 | 自然語言真假難由固定規則全面判斷；重呼模型有成本，不能重做已成功副作用 | 非首選；如將來有具體殘餘錯報再評估 |
| **沿既有 JD receipt／binding 投影短小的本輪已確認效果** | 即使舊工具結果被 compaction 移出，最後請求仍可取得保存事實；模型合成正／反例均正確 | 活動 run 對帳、空列／未明、已撤回／後續手改、大小上限必須驗證；模型不保證每次遵守 | **首選進一步施工候選**；不把 test-only 模型成功冒充正式 App 通過 |

最佳效果不是無條件「每次 SQL 全量掃描」：先由目前 run state 判斷本輪有無 JD writer binding／需要對帳的操作；若有，再以既有 receipt owner 形成**有界、request-only、可核驗**的確認效果。近期原生工具結果保持現有可見性，不額外複製完整正文；舊結果被壓縮後用可信短狀態承接。未明或讀取失敗應保守呈現，絕不轉成「沒有保存」。這是 A 的 JD 保存真相接點，不是 B1／B2 都要加同一份 JD 狀態。B1／B2 已有各自固定階段、完成與結果；若日後出現類似可重現錯報，再在其 stage owner 比較，不造通用跨 Agent ledger。

下一 gate 若 Owner 選此候選：先用**活動 run** 的 isolated PostgreSQL＋Saver 測 `committed`、`no_change`、拒絕、未明、錯 scope、重開、摘要切點與多次後續工具呼叫；確認與原 `JdNoticeMiddleware`、request-only 投影次序兼容。其後才做一次有界真 App 長回合，查最後 provider request 確實收到同一 run 的確認事實、final 與 DB 一致。**目前 Q12 仍 OPEN；未更改 production、Prompt、Memory、compaction 或 provider。**
