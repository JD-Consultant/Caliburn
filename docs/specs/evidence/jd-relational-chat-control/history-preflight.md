# RS-4：舊回合定位與固定對話分頁前置

查閱／實測：2026-09-13。基準 `36cc1cb9`。只做原生 API 研究與 InMemorySaver 探針；沒有改 App src、升級套件、建立資料表、連 PostgreSQL、呼叫 provider 或重播原工具。

## 1. 推薦與適用界線

**目前採有上限的原生 `parent_config` 祖先查找；對話分頁讀同一個固定 root／source 的 messages。** 不將 `get_state_history` 第一筆同 run／同文字的結果直接視為原回合，也不從多個 checkpoint 拼接聊天紀錄。

原生 metadata filter 可當未來新格式的查找提示，但本輪探針證明它不能取代有效祖先關係；普通 `update_state` 結案也不會自動保留原 run 標籤。因此沒有充分理由只為避免「每次新 run 都掃歷史」立刻新增格式：目前完整、未截短的固定 HumanMessage ID 集合已能先辨識新 ID，只有已出現的舊 ID 才需要查較舊結果。這個判斷仍在同文件 owner 的原准入內完成。

推薦是針對目前 append-only 原話／完整 messages 的本案選擇，不是跨供應商唯一共識。若未來加入 messages 刪除、壓縮或資料搬移，不能繼續把「目前列表沒有 ID」當成未曾使用，必須重驗此邊界。

## 2. 官方契約與版本

本次沿穩定 MIT 版本：LangGraph **1.2.11**、checkpoint **4.2.0**、LangChain Core **1.6.3**，PostgreSQL Saver **3.1.2**。PG Saver 本輪只讀官方已裝源碼，沒有 DB 效能或真 PG 驗證。

| 依據 | 官方事實 | 本案應用／限制 |
|---|---|---|
| [Time travel](https://docs.langchain.com/oss/python/langgraph/use-time-travel) | `get_state_history` 反向時間列舉；從舊 checkpoint `update_state` 會建立分支，原歷史保留。從 checkpoint `invoke` 會執行後續節點。 | 查回只用讀 API，不呼叫 `invoke(None)`。時間順序不等於有效祖先鏈。 |
| [Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)、[checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers) | Checkpointer 保存 thread state；可按 checkpoint config 讀取保存位置。 | 先取得目前位置，再以明示 ID 固定 root。作用中回合使用該 root 指向的固定 child；START 沿現有原 payload 驗證。 |
| 已裝 `pregel/main.py:1392–1433`／`:1480–1557` | latest 可包含 pending-writes overlay；指定 checkpoint ID 的讀法不走該 overlay。history 的 `filter`／`before`／`limit` 原樣交 Saver；回傳前先收完有限 list。 | locator 與材料解碼分開；分頁固定上界，不能每頁換 latest。`limit` 限回傳筆數，不是任意 DB 工作量的硬上限。 |
| 已裝 `checkpoint/postgres/__init__.py:192–258`、`:558–597` | `get_tuple` 按 exact thread／namespace／checkpoint 讀一筆；沒有時回 None；公開 `parent_config` 來自同 thread／namespace 的 `parent_checkpoint_id`。 | 可直接讀父 config，不需自建 lineage 表、遞迴 SQL 或通用分支判定引擎。沒有父資料時明確斷鏈，不猜下一個時間較早的位置。 |
| 已裝 `checkpoint/postgres/base.py:624–673`、`postgres/__init__.py:112–180` | metadata filter 是參數化 `metadata @>`；`before` 是 checkpoint ID 小於界線；主 config 若帶 checkpoint ID，就是該筆 equality filter。結果按 ID 降序、再 LIMIT。 | 不能用 state channel 名當 filter；不能帶目前 checkpoint ID 卻期待全歷史。這不是祖先查詢。 |
| 已裝 `checkpoint/base/__init__.py:757–789`；`pregel/_checkpoint.py:117–148` | Saver 將 config.metadata 的可序列化純量合入 metadata；普通 update_state 的新 metadata 主要重建 source／step／parents／delta counters，沒有繼承任意舊標籤。 | 新 run 可明示 label，但要讓 terminal 可篩，受控 close 必須再次提供已驗原 record 的 metadata。不能只在第一次 invoke 加參數便宣告完成。 |

模型消息完整性沿已核的[工具保存接點](../jd-relational-ai-runtime/admission_checkpoint_notes.md#官方事實與精確-code-path)：[OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling#how-it-works)及[Anthropic tool results](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)要求原 call/result 配對。此輪沒有新的 provider 契約變更需廣搜；原 AIMessage 原生 blocks／signature／tool-call／ToolMessage 留在 Saver。UI 的可讀文字投影不可以改寫該權威材料。

## 3. 五組原生探針

[探針](history-probe.py)／[首次完整輸出](history-probe.first.stdout.txt)：**五組首次即通過**，其中包含明確反例斷言，不把沒有新 src 的情況製造為產品 red/green。合成節點只在 fixture 建立時執行；查找與分頁 node/model/tool replay 均為零。

| 情境 | 實際結果 |
|---|---|
| A 完成 → manual admit/close → B 完成 → C 中斷 | 祖先鏈能讀 A；A terminal 及兩個 manual checkpoint 都保留同一份 A 材料，共三筆同 run terminal 投影。C 的有效 messages 在固定 child，沒有只依 root 判斷。 |
| update_state 分支 | A 完成、B 完成後，從 A 分支只改 status=failed，再從 B 建回目前分支。全 history 第一筆 A 是 failed，**完整 messages 也符合目前 prefix**；有效 parent 鏈上的 A 卻是 completed。證偽單靠同 run、原話或完整 prefix 足夠。 |
| 長歷史與分頁 | 78 筆 root checkpoint，以每頁最多 7 個父節點共 12 頁讀完，無重複。40 則完整消息分頁之間又閉合及新增一輪；續頁仍以原固定 source 取得原集合，未混入後續回合，原生 blocks 保留。這不是 DB 性能測量。 |
| START 與 missing parent | loop put 前失敗：固定 START 原 payload 保留新 Human，祖先鏈完整。**input put 前失敗而後續 loop put 成功**：新 Human 能按現有材料驗證讀回／閉合，但父 ID 對應資料不存在，祖先鏈停在 gap；時間歷史雖仍有舊 A，不能據此猜接。 |
| metadata 候選 | invoke label 進入 root/child；普通 close 丟 label；明示 label 的 close 即使 ACK 遺失仍可讀回。B input 的 label 是 B，但 root.values 當時仍是 A。篩 A 的 metadata 仍可能回同字但 completed/failed 的不同分支；未知 ID 同時不在固定 Human 集合與 filter 結果中。 |

### metadata 候選的可用程度

可證 `config.metadata={"jd_run_id": run_id, "jd_run_index_format": 2}` 在 invoke 原生保存並可被 filter 查到。探針的 `2` 只是候選 index marker，**沒有把現有 AiRunRecord 改成 v2**。

若主代理後續採此候選，必要條件是：label 由 App 從已驗 record 推導；close 明示同 label；每個候選仍核原 record／Human digest／messages/view／terminal；START 查 exact input，不把 metadata run 當成當時 root.values 的 run；ACK 不確定只讀回；分支歸屬仍需證明。現行原生 migrations 沒替自訂 metadata label 建 GIN index，不能宣稱 filter 是常數時間或已免除底層掃描。

## 4. 最小 API 接法建議

以下是責任與流程建議，不是本輪已實作的新 DTO。

1. 在 `AiRunCheckpoints` 提供「已指定 root config 的同一材料解碼」接點，讓 current discover、history locator、conversation cursor 共用相同 scope／START／原話 digest／view 配對驗證。不要讓舊 run locator 呼叫 observe 後再次轉讀 latest。
2. 新請求准入先在原 owner gate 內取得目前固定完整材料。若原 Human ID 已在其中，必須走原結果讀回／定位，不再呼叫模型。當前 START 的 Human 要用原 payload 合入檢視，不能只搜 root.values。
3. 較舊 ID 從固定目前 root 沿公開 parent_config 向前，每次讀取有明確步數上限；候選須同 dataset/doc/run、原 Human/digest 相同且 terminal／root idle，材料必須仍在目前完整 messages 的 prefix。祖先關係是選擇依據，prefix 是額外一致性檢查，不是替代品。
4. manual roots 保留之前 AI record，會形成同一 terminal 的多個 snapshot；不把它們當多次 AI 回合。沿有效鏈取最近一份合法原 run 材料即可，原 receipt／ToolMessage 驗證仍交既有 AiRuntime。不要修改原記錄來去重。
5. 到每次上限但還有 parent 時回有限 continuation；cursor 必須由 App 簽發並固定 dataset、document、目標 run、原 root 上界及下一個 exact parent。找到 gap／矛盾／不相容記錄時保留 lookup_required；`not_found` 或上限耗盡都不等於可重新提交原意圖。

若目標確實在當前完整 Human 集合中，卻沿可讀祖先鏈走不到它的 terminal，這是未能證明原結果，不是「新請求」。本輪選擇明確限制該少見恢復缺口，不自建跨斷鏈分支重建或第二份 run authority。缺口發生時 App 仍保有完整原始對話和現有 JD，後續是否改善以實際影響另定。

## 5. 對話分頁

對話資料來自**一個固定的有效 messages 集合**，不列舉 checkpoint 歷史再去重。初頁固定 root，若有活動 child，另固定該 root 所指向的 exact source config；START 用同一根 input 的原 Human。後續頁使用這一對已簽的位置，保持 document／dataset／format 一致。

目前原始消息數完整，因此可按同一集合的穩定位置分頁；原生消息 ID 供 UI key，不能用頁內位置作永久身分。保存原生消息與 UI 文字投影分工：可不展示内部工具／推理欄位，但不能為了顯示方便重新寫入只有文字的 AIMessage。若 byte 上限不足以放完整一則消息，回明確有限錯誤或另定單則讀取，不默默截斷 body／工具配對。

作用中回合可能在兩次請求之間前進；原 cursor 繼續讀舊固定集合，員工重新整理再取得新的 anchor。這裡的分頁穩定不代表 worker 已停止、消息已對員工送達、run 已結案，或存在跨 Saver/JD SQL 的共同交易。

## 6. 實作前仍需的有限驗收

- 真 PostgresSaver 的 exact parent、metadata filter、缺損 checkpoint 與 cursor 範圍驗收；本輪沒有替代真 DB 的宣稱。
- 舊 ID／不同文字衝突、active START 原 ID、不相容 cursor、跨文件／dataset 拒絕及版本持續固定。
- 原結果查回仍核完整 binding／原 receipt／ToolMessage，不由查找器重算業務結果。
- 如果選用 metadata 新格式，補 invoke／完整 child／普通結案／ACK 遺失／manual 插入／再開新 run 的標籤驗收，並記錄 v1 有界 fallback 的限制。沒有這項採用決定前不升級 schema。

## 7. 本次有界實作結果

2026-09-13 已新增 [ai_history.py](../../../../experiments/jd-relational-app/src/jd_relational/ai_history.py) 與 [test_ai_history.py](../../../../experiments/jd-relational-app/tests/test_ai_history.py)。`AiRunHistory(checkpoints).find(document_id, run_id, dataset_id)` 回傳同一 `AiRunObservation`，或在完整固定消息集合中確認 ID 未使用後回 `None`；不新增 run 資料表、metadata authority、模型／工具重播或 SQL 回執重建。

初次定位只呼叫一次 current discover，後續透過公開 `get_tuple` 的 `parent_config` 與同一材料解碼器 `observe_at` 讀固定 root；目前回合可包含已固定的活動 child 或 START 原 input。較舊回合只接受最近的有效祖先 terminal／idle 狀態，完整消息必須剛好等於目前材料中該回合的區段上界前綴，即下一筆 Human 之前，不能連後一輪原話一起當成 A 的結果。Manual 根狀態可保留同一 terminal 材料，仍不代表多次 AI 執行。

本次採每次最多 **256 個祖先位置**的工程上限；這不是資料庫 IO 次數或時間的硬上限。達上限、斷鏈、循環、原 ID 已存在但無法證實原 terminal 時，回固定 `original_run_lookup_required`。結構／資料集／文件矛盾回 `invalid_checkpoint`；保存服務讀取例外回 `checkpoint_unavailable` 並隱藏原例外。**本次沒有實作第 4 節候選中的 continuation cursor、聊天分頁或 HTTP**；超上限不能當作新 ID 重送。原結果的工具 binding／receipt／ToolMessage 核對仍由 AiRuntime 負責。

原生 `add_messages` 會按消息 ID 替換，因此 ID 即使只與既有 AI／ToolMessage 相撞也不能宣告未使用；本次已加入拒絕反例。`None` 的可採用條件仍是目前完整、未刪除或壓縮的原生消息集合，加上呼叫者既有文件准入；查找器本身不授予 writer authority。

驗證全部使用 `InMemorySaver` 與合成原生 StateGraph，零 DB／provider。首先只有新測試落檔而模組尚未建立時，曾得到 1 個 collection error（[原始輸出](history-test-first.txt)）；這不算行為上的失敗修復。模組落檔後首輪 **18 PASS／0.97s**，再補完整回合邊界、唯一 latest 讀取及不一致原話不能證實未使用 ID 三例。最後執行 `uv run --frozen --offline pytest -q -p no:cacheprovider tests/test_ai_history.py tests/test_ai_checkpoints.py tests/test_ai_checkpoint_discovery.py tests/test_ai_records.py`，得到 **146 PASS／1.56s**，其中本檔 21 例。原生 branch／input put 失敗斷鏈反例沿第 3 節首次探針結果；不把測試 collection error 描述成產品故障，也不把這組結果稱為真 DB、新宿主或自然模型驗收。

新 run 格式的版本變更由同輪獨立 `ai_records`／admission 工作負責；locator 共用正式 parse／observe_at，測試保留明示原 V1 保存材料並驗較新材料接點。本節不把研究時的 metadata marker 2 當成該新 run 格式的採用原因。
