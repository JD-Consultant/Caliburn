# Q019 Task4a：背景整理通知切片紀錄

- 日期：2026-09-06；topic `Q019-MEM-CADENCE-01`。
- 範圍：純通知工具、耐久安全來源投影、通知中斷收尾。不是 API／worker／完整 scheduler，也不是整套 Memory 品質驗收。
- [核准設計](S:/caliburn/docs/specs/2026-09-06-memory-consolidation-request-wiring-design.md)／[本段計畫](../plans/2026-09-06-memory-consolidation-notification-slice.md)／[父計畫](S:/caliburn/docs/plans/2026-09-06-analysis-only-agent-application-wiring.md)。
- Branch `codex/analysis-only-agent`，base `4e0438bc`。最終回歸 **244 passed / 0 skipped**；獨立 review CLOSED，無未處理 finding。本段保存由本檔所在 git commit 與本地 tag `q019-consolidation-notification-v1` 定位，最新 hash 回寫 main current register；不 merge／push。

## 1. 做成什麼

1. `build_conversation` 註冊空參數 `request_memory_consolidation()`。官方工具只回短收據及程式固定 artifact，不呼叫 B、不寫 Memory、不等背景完成。LLM 可接續完成答覆，原 9 model／8 tool 上限不變。
2. Artifact 經官方 ToolNode、root／child 與 PG Saver 保存；實際 OpenAI request 不含 artifact。收據是「已收到要求、尚未整理」，不是 Memory 發布成功。
3. `ConversationReader.pending_consolidation_turns(after_reference=None)` 只讀 canonical 安全前綴，用真實呼叫＋成功結果＋artifact 辨識要求。同回合重複要求只形成一個範圍；依最後成功 publication 的 source cursor 排除已處理回合，不新增已讀旗標、通知表或第二份原文。
4. 尚未封閉回合不能釋出；前方未解回合不被跳過。跨文件／虛构 cursor 拒絕；先後依消息序列而非 UUID 大小。部分涵蓋只移除已處理要求，較後要求仍可找回。
5. 已確認 worker 停止後，未保存結果的純通知可補一個配對失敗並封閉；已保存的成功收據保留。C 的真實 publication receipt 對帳及未知工具效果規則不放寬。通知名稱在 factory 保留，不讓不同副作用借用相同名字。

本 slice 沒有 B executor 可供等待；測試證明「通知路徑沒有 B 依賴」，**不冒稱已完成真正 A／B worker 的並行、重啟重排或失敗 Context**。這些仍在父計畫 Task3／Task4。

## 2. 細節查核與修正

### 零參數工具不需要自訂驗參器

實測 `langchain-core==1.6.2` 的 `BaseTool._to_args_and_kwargs`：Pydantic schema 沒欄位時直接返回 `(), {}`，不進 `_parse_input`。因此額外傳入欄位會被忽略，`extra=forbid` 也不能在這條捷徑改變行為。

曾加入嚴格空 schema 的測試／試作，測試直接證偽後已移除。最終沿官方原生行為：所有 model args 均不被本通知函式使用；不加 hidden runtime field、不覆寫框架 private method、不另造 guard。通知辨識看真正保存的配對成功收據，不因 raw args 多餘而靜默丟掉已成功的要求。回歸包含偽造 document/job/reason 無法改變通知 scope／內容的案例。

這不適用於其他有參數、有副作用的工具；它們的既有驗證與發布規則未改。多餘參數可能仍在 canonical tool call 裡，沒有改寫原模型輸出，也沒有聲稱 provider strict 已啟用。

### 測試模型身份不能在重建時重用

首次全套 PG 驗證為 241 pass / 3 fail。三個新測試在重建假 provider 後重新使用 `resp_1` 等 ID，官方消息 reducer 因同 ID 更新舊位置，最末變成 HumanMessage，導致完成驗證拒絕。用 InMemorySaver 重建 client 也重現，排除 PG 通知保存故障。

只修正 fake provider 的每實例 response/item/call 唯一前綴，未放寬產品身份或完成判準。重跑後 244/244 通過。另有一個測試注入位置調整：測安全關閉就在公開 middleware 注入中斷，不把 HTTP SDK 例外包裝／transport retries 誤當這項通知行為。

## 3. 驗證證據

全在 `experiments/analysis-agent`，官方 framework／SDK／serializer／PG 真正執行，模型 HTTP 是 MockTransport，測試 tracing 關閉。

| 檢查 | 結果 |
|---|---|
| 施工前 `uv run --no-sync pytest -q -rs --tb=short`，未設 PG DSN | 204 passed / 22 skipped；不當作 PG 已驗證 |
| 先加通知測試再跑 | 14 個預期缺功能失敗；其後額外參數測試證偽嚴格空 schema 假設 |
| 最終相同命令＋專用 PG DSN | **244 passed / 0 skipped，30.22s**；新增 15 個離線＋3 個 PG 用例 |
| PG 新用例 | 成功後未讀即重建、通知結果保存前中斷、保存後下一 model 前中斷；重建 Saver／graph 後收尾及下一輸入，第三次重建驗 cursor |
| 原生 items、compaction、B1／B2／C 及發布 regression | 同全套通過；沒有靠剪歷史／改 provider status 讓測試通過 |
| `uv run --no-sync python -m compileall -q src tests` | exit 0 |
| `uv lock --check --offline` | exit 0，73 packages，lock 未改 |
| `git diff --check` | exit 0；Windows LF/CRLF 提示不是 whitespace error |

專用容器 `caliburn-q019-postgres` 標籤 `com.caliburn.purpose=q019-durable-conversation-test` 已核對；端口 55433、DB `q019_agent_test`。密碼僅從該容器帶入測試程序環境，不寫文件／輸出。只清理測試自己隨機 thread 及既有用例產物；沒有重啟 Docker、重建正式 DB、遷移或刪使用者資料。付費模型呼叫 **0**。

## 4. 框架依據與自訂邊界

- [OpenAI Function calling：how it works](https://developers.openai.com/api/docs/guides/function-calling#how-it-works)：本輪透過官方 docs search→fetch 重核，工具結果須配對 call，普通工具接續另有模型請求。不是 async background 的零成本暗號。
- [LangChain ToolMessage artifact](https://docs.langchain.com/oss/python/langchain/messages#tool-message)／[tool API](https://reference.langchain.com/python/langchain-core/tools/convert/tool)：模型可見 content 與程式 artifact 分工。工具實作／省略 wire metadata 由真 SDK 測試核實。
- [LangGraph subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)／[persistence](https://docs.langchain.com/oss/python/langgraph/persistence)：官方 root／child 保存及公開 get/update_state。沒有自製 Agent loop 或平行訪談 archive。
- [LangChain Core tool source](https://github.com/langchain-ai/langchain/blob/master/libs/core/langchain_core/tools/base.py)：實際核對鎖版1.6.2的 `_to_args_and_kwargs` 零欄位分支及 ToolMessage 建立路徑；GitHub moving branch 僅作開發入口，不能代替 lock 的版本證據。
- 已鎖版本：LangChain1.4.0／Core1.6.2／LangGraph1.2.11／checkpoint4.2.0／PG checkpoint3.1.2／langchain-openai1.6.0／OpenAI SDK3.8.0；沒有新增／升級套件。

工具目的／短收據、何種安全回合可投影、純通知取消的窄例外是已核准應用接線；不宣稱 OpenAI／Anthropic 內部有同名工具／同資料結構。背景成功／失敗通知的多廠商證據只在核准設計 §5.1，不在此重複研究。

## 5. 段落退出與下一步

獨立 reviewer 已完整讀本切片規格／程式，另跑21個限定離線測試及配對／混合取消檢查；verdict：可保存本地檢查點，Critical／Important／Minor皆0。全套 PG 244項由主實作者驗證，reviewer沒有重跑或宣称独立重驗。沒有未處理 finding。

未處理的產品 gate：Task3 最小 API；其餘 Task4 真正背景worker、來源量後備／門檻及恢復，然後當前失敗 Context。必須用可控阻塞B驗 A不等待、B成功不增主模型call、失敗下次正常run才可見且恢復後移除。不能用這18個新測試宣稱上述項目完成。

仍不做 JD 編輯、真模型效果保證／大型 eval、跨員工 Memory、使用者手動整理入口。下段沿既有設計接線，若官方契約或測試產生新的實質取捨再回報，不重問已核准策略。
