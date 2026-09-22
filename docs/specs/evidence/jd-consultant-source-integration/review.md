# 當輪原話來源接合：獨立審查

- 日期：2026-09-13；基準 `c135f18202a888a478ac2d67a72e1e811643e079`；JD-R002／OI-02 局部。
- 依據：[本輪設計](../../2026-09-13-jd-consultant-source-integration-slice.md)、[原話接點](source-seams.md)、目前決策與計畫最新路由。審查者未修改產品、作者測試或設定；只寫本報告。
- 最終結論：**指定範圍 PASS，CSI-R01／CSI-R02 修正後 CLOSED，未見其他 P1／P2。** 這不包含 Memory／B1／B2、較早來源讀取工具、來源 UI、自然品質或完整 App。

## 1. CSI-R01／P2：來源服務故障被包成模型參數錯誤

**CLOSED。** 原 [consultant_tools.py](../../../../experiments/jd-relational-app/src/jd_relational/consultant_tools.py) 的 `prepare` 捕捉 `ReadError` 後統一交 `_error_result`；來源 owner 對缺失固定位置或 driver 故障回 `source_not_available`，因此被包成 `MutationResult.status=invalid_input`，model loop 仍能繼續。

獨立首個反例使用實際 native `create_agent`、既有 `FixedModel`、真工具接線及合成材料：先 `jd_read current`，再送正確具名新增任務及來源參數，resolver 故意回 `ReadError("source_not_available")`。原程式回 `invalid_input`／`next_action=stop`，但仍發生第 **3** 次模型呼叫；writer 為 **0**。`next_action` 文字本身不是 App 停止機制。

主代理修正 `prepare` 在此錯誤碼上直接拋固定 `AiToolError("ai_tool_unavailable")`，位於 prepared cache／binding 建立之前；原未接 source owner 也停止，不能靠參數修正或去掉來源繼續寫。錯簽章／跨 scope 的 `invalid_ref` 仍是引用錯誤，沒有把二者混為同一原因。

修後 [故障反例](../../../../experiments/jd-relational-app/tests/test_conversation_source_failures.py) 核只有 **2** 次模型呼叫、沒有 writer。另做 §4 的真正 `AiRuntime` 收尾 probe，核故障不重讀來源、不重播模型；永久消息中的未執行工具由既有收尾流程補配對，沒有假操作回執。

## 2. CSI-R02／P2：人工保存前的來源讀取沒有納入同一 owner 排空

**CLOSED。** 新 [managed_app.py](../../../../experiments/jd-relational-app/src/jd_relational/managed_app.py) 將同一 source owner resolver 注入人與 AI；但原 [ManualService.save](../../../../experiments/jd-relational-app/src/jd_relational/manual_service.py) 先讀 historical material／來源，才呼叫 `runtime.submit`。前段 Saver I/O 尚無同 owner 的讀取登記。

獨立反例使用真 `ManualRuntime`、`ManualService`、`ManualHost.close` 與自己的執行緒，只有 DB／Saver 資源是合成 port。有效 field ref 由實際 `ReadService` 發配；人工保存停在 source resolver 的 Event 時，原 `host.close(timeout=.01)` 回 **True**，已呼叫 Saver close／engine dispose，但 source read Future 尚未完成。這不是 OS 或真 DB 測試；它精確證明 owner 未涵蓋此 I/O。

首個 probe 曾自行建立 field `SignedReference` 而漏必需 digest，於進入被測路徑前失敗；改用實際 read 發配的 ref 後才重現上述故障。該 fixture 錯誤不算產品首敗。

主代理將 `read_revision → command_context → bind_edit` 完整同步準備放入既有 `runtime.inspect_document`，回傳已完成的 `BoundEdit` 才呼叫 `submit`。沒有新 gate、全域 I/O lock 或 lazy iterator；prepare 期間 close 必須等待，prepare 結束與 submit 間仍由 submit 自行核寫入准入。修後反例也核 source resolver 內重入 `close(timeout=0)` 回 **False**，故障結束後才可完成 close。

## 3. 來源模組與接線核對

作者停止寫入後，核對 [conversation_sources.py](../../../../experiments/jd-relational-app/src/jd_relational/conversation_sources.py)、[consultant_context.py](../../../../experiments/jd-relational-app/src/jd_relational/consultant_context.py)、[ai_runtime.py](../../../../experiments/jd-relational-app/src/jd_relational/ai_runtime.py) 與 managed composition。沒有另開框架／廠商比較。

| 接點 | 核對結果 |
|---|---|
| 原話唯一權威 | 沿 `AiRunCheckpoints.discover/observe_at`；source 只存固定位置 token，暫態 excerpt 沒有成為第二份持久原話或 Memory |
| 當輪窗口 | last 必為原 run 的 Human；前面最多取最近有公開文字的 AI，遇前一 Human 就停止。AI 明示為上下文，沒有把工具／thinking 當員工事實 |
| 真正 request 可見性 | `for_turn` 在第一次實際 request 才 capture，往後固定同一 excerpt；每次核所指 ID／角色／完整公開文字／順序與中間窗口。刪掉／換掉原 Human 或 AI、插入另一 Human／公開 AI、重複 ID 或 chunk 都拒絕 |
| 原角色／內容保留 | `_project` 只追加來源 metadata 到 system；原 messages 不改、不複製原話到 system、不偽造已讀 ToolMessage。公開 AI 投影容許不傳 private thinking metadata，這是刻意的角色／公開文字責任，並非要求隱藏區塊相同 |
| 固定讀取 | token 固定 dataset／document／run、root checkpoint、source namespace／checkpoint、first／last；讀回明示兩個 native 位置，缺失不退 latest。後續同 child／新 run 前進不改原來源 |
| 簽章與範圍 | 使用同設定 key／dataset、獨立 `caliburn.jd.conversation-source.v1` salt 與 source purpose；嚴格格式、closed fields、raw／token 4096 上限、UUID 與範圍檢查。錯 key／dataset／document／用途及舊 token 不變成合法來源 |
| 人／AI 共用 | managed composition 向兩者注入同一 resolver；AI 在真前景 Future 內讀取，人工 prepare 修後由同 owner read token 涵蓋。來源解析仍在 JD SQL transaction 外，後續沿共同 domain／binding／SQL |
| 原結果與恢復 | `lookup`／`recover` 不呼叫 `capture` 或 `for_turn`、不重算原命令。既有 durable binding／receipt 與消息配對仍是結果依據 |
| 安全錯誤 | module 的錯誤為固定 code，suppress cause；缺固定原資料屬不可用，不能假成目前資料。正文和 driver 細節不進錯誤／repr |

此 source ref 只證明 App 找到並提供指定公開材料，不證明 LLM 理解或原話支持整個 JD target；`basis_digest` 與 `readability="not_checked"` 的原責任不變。

## 4. 審查者實際執行與證據層級

各組分別執行，不加總成全 App 或真模型成績。

| 審查者執行 | 結果／界線 |
|---|---|
| [source 純測試](../../../../experiments/jd-relational-app/tests/test_conversation_sources.py)＋[來源 context](../../../../experiments/jd-relational-app/tests/test_consultant_source_context.py) | **47 PASS，3.97 秒**；native InMemorySaver 與固定模型，零 DB／provider |
| [CSI 故障反例](../../../../experiments/jd-relational-app/tests/test_conversation_source_failures.py)＋[managed composition](../../../../experiments/jd-relational-app/tests/test_managed_app.py) | **11 PASS，7.81 秒**；1 個既有 Starlette `BlockingPortal` alias deprecation warning，非產品失敗 |
| CSI-R01 原生收尾獨立 stdin probe | **PASS**，如下；沒有留下產品／測試程式 |
| root 修改範圍的 diff check | PASS |

收尾 probe 使用實際 `AiRuntime._run`、native `create_agent`、`JdNoticeMiddleware`／`AiToolMiddleware`、`ConversationSourceService.for_turn` 及 `InMemorySaver`。DB／notice 材料 port 為合成，模型是既有 `FixedModel`，不是 provider 或 SDK wire：

1. 兩次模型呼叫：讀 current，再送有效已發配來源的新增任務；resolver 故意回不可用。
2. 只有一次來源驗證、零 writer；結果為 `failed` 且 `input_saved=True`，不捏造最後回覆。
3. 原 Human 的 ID／角色／CRLF／空白保留；未配對呼叫由既有 App 收尾補為具名 `ToolMessage(error)`，`operation_ref=null`，pending calls 為零、root idle、同文件 gate 可釋放。這是未執行工具的收尾紀錄，沒有讓模型收到參數錯誤後再繼續。
4. 將 `sources.capture` 改成一旦呼叫就失敗，再做原 `lookup().wait()` 與 `handle.recover()`，仍回原結果；模型／source 呼叫數保持不變。

另唯讀核 [真 PG source 旅程](../../../../experiments/jd-relational-app/tests/test_conversation_sources_postgres.py) 的程式：同 owner／原生 PG Saver／真正 SDK MockTransport、兩輪來源固定、人工更正 basis 失配、原話前綴保留與新 connection／codec 查回皆有明確斷言。執行由另一代理負責，所報 **1 PASS／8.96 秒** 不算本審查者的 PG 執行；本審查者沒有重跑 PG。

## 5. 收束

兩個具體接線缺口已修且窄複核通過；source module 沒有新增 P1／P2。正式來源 UI、較早來源按需讀取、Memory／背景整理、自然引用品質與真瀏覽器仍按 OI-01／02 推進，不因本切片 PASS 自動閉合。沒有升級依賴、建立表、外傳、啟服務或呼叫付費 provider。
