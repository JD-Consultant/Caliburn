# RS-4 工具 binding 與原生 checkpoint 獨立審查

日期：2026-09-13。審查者：獨立子代理；本次沒有修改受審程式或測試。範圍限 `ai_checkpoints.py`、`consultant_tools.py` 及其兩個測試檔；主代理仍在修改的 `AiRuntime` 不納入本次結論。

**結論：本範圍 PASS，未找到可成立的 P1／P2 誤寫或誤報保存反例。**此結論以執行者遵守下述 caller preconditions 為邊界，不代表整體前景取消／新程序恢復已驗收。

## 核對結果

| 核對項 | 實際證據與結論 |
|---|---|
| 固定 root／child | `AiRunCheckpoints.observe` 先取 root checkpoint identity，再讀固定位置；只接受既定 consultant child namespace，必要時另固定 child config。拒絕未知 root route、不同 run／dataset、root/child 原訊息前綴不一致，以及多層 child。測試區分原生 pending-writes overlay 與真正 root 保存 |
| 原話及供給基準 | 新 run 的 HumanMessage 使用原文字，不 trim／重寫；digest 綁 dataset/document/text。model-view 必須配到完整 AIMessage digest，沒有新回覆時可以保留前輪有效基準；不靠 partial stream 或新 run 字串推定模型已讀 |
| 閉合更新 | `close` 先核觀察位置仍相同，再只做一次 `update_state`；回覆遺失以 exact readback 判定，不重送更新、不 invoke/replay graph。原 messages、bindings、read binding、model-view 不得被任意改寫。是否 writer 已停止、SQL 結果已對帳屬 caller 的前置責任 |
| 先 admission 再 SQL | 原生 `after_model` 先產 identity-only binding。執行時核 call/message/digest、該 run 的原 BoundEdit cache 及 state binding 一致，再交共享 owner。測試以實际 InMemorySaver checkpoint 核執行邊界，保存前故障時沒有進入模擬 writer |
| 真正讀到的 B | `_read_base` 核實際成功 `jd_read` ToolMessage 的 ID／call ID／content digest、current access 及發配的 revision ref；準備 command 時讀該 revision，不以後來 head 取代 B。history read 即使等於 head，仍不能成為可寫基準；混用 history target、來源／選區接點未具備均拒絕 |
| 已知／未知結果 | 只將確認的原 `WriteObservation` 投影為工具結果；未知會拋固定 pending，停止下一模型回覆。原已確認 receipt 不因本地 cleanup error 降級為失敗；輸出沿 shared result schema，不把原 arguments 當錯誤訊息回送 |
| 參數與識別 | 工具定義來自既有 generated schema。App 配 run／operation／base，模型只填業務工具參數。重複 call ID 改意圖、多個 tool calls、不同文件／dataset／run、遺失 cache 均有明確拒絕；遺失 cache 不重新讀來源或組另一個 candidate |
| 錯誤內容 | 無效參數在 ToolNode 執行與 tool callback 前截住，回固定內容；觀察／閉合 driver error 不直接外吐。原 canonical AIMessage 仍保存實際 tool call；這是原始互動紀錄，與向模型回傳自由格式錯誤的範圍不同 |

對照原碼：[ai_checkpoints.py](../../../../experiments/jd-relational-app/src/jd_relational/ai_checkpoints.py)、[consultant_tools.py](../../../../experiments/jd-relational-app/src/jd_relational/consultant_tools.py)。框架採用依據沿[ownership 前置](ownership-preflight.md)及[原生 admission 探針](admission_checkpoint_probe.py)，本次不重開研究或升版。

## 交給整體 coordinator 審查的必要前置

1. **不是由 `close` 證明死亡。**呼叫 `AiRunCheckpoints.close` 前必須等真 run Future、所有 SQL Future 停止並確認回執，且持有同一文件 reservation。此 adapter 的 `closed` 指原生 graph 位置閉合，不能當作 OS／Future 停止證據。不得以 timeout 或 caller 傳入的 boolean 取代。
2. **完整 call/result transcript 由 caller 核對。**目前 `close` 會驗新增 ToolMessage 對應未答 call，但沒有要求所有原 call 都已回答，也沒有核新增 ToolMessage 的 name。因此 adapter 本身不是完整 provider transcript validator。主代理已說明 coordinator 會依原 call/result/name 配對，為全部 pending（含無 binding 的 read／unknown tool）補確切未執行或已確認結果，再驗無 pending。後續必須審這條接線；未經該前置，不能單凭 `close` 成功就宣布下一輪可用。這是本次記錄的 caller precondition，未當作已發生的產品錯誤或 P2。
3. **sync durability 必須由實際呼叫端設定。**工具確認 callback 核 native state binding，沒有在每次工具內重查 Saver 是否落盤。正確順序依靠原生 graph 的 sync durability；單獨以 async durability 直接使用此 middleware 不具有同一保證。
4. **本次只驗同步入口。**`aafter_model`／`awrap_tool_call` 的取消與 executor 收尾沒有在本輪測試中獨立驗證；不能由同步固定案例推稱 async cancel 也通過。本輪宿主選定入口的真 Future／SQL／Saver 整合另驗。

## 實際驗證

在隔離 App 的 frozen Python 執行：

```text
pytest -q -p no:cacheprovider tests/test_ai_checkpoints.py tests/test_consultant_tools.py
71 passed in 2.03s
```

這是原生 LangGraph／InMemorySaver 與固定模型、合成 history／owner ports。沒有呼叫 provider、連接 PostgreSQL、啟動本機宿主或修改設定；不宣稱真 DB、新程序、自然模型或員工試用通過。本次只新增此審查文件，沒有新程式修正與新增首敗案例。
