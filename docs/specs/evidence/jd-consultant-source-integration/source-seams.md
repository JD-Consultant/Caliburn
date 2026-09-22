# OI-02：原話來源與共同 JD 保存接點

2026-09-13，只讀有界核對；供本輪接線決策。沒有改程式、資料庫或呼叫 provider；下列測試為已存在案例的程式／既有結果核對，本次未重跑。依[目前缺口 OI-02](../../2026-09-13-jd-app-open-issues.md)及[工具契約 §9](../../2026-09-12-jd-relational-agent-tool-contract.md#9-來源引用契約)。

**結論：原話已有唯一的原生保存與固定讀取能力；共同 JD 保存已有來源檢查、target basis 與手改失效標示。先接一個真正的原話 source owner，向實際 model request 發配當輪已保存原話的精確引用，再注入人工／AI 既有 resolver，即可形成第一條可驗縱向流程。不必先做 B1/B2，也不新增 `read_conversation` 工具、原話資料表或通用來源引擎。**這只閉合當輪來源；Memory／較早來源查找仍須後续完成，不能宣布 OI-02 全部結案。

## 1. 新版實際原話權威與可重用函式

以下程式均在 `experiments/jd-relational-app/src/jd_relational/`。

| 現有位置 | 已具備的能力與界線 |
|---|---|
| `runtime_checkpoints.py:DocumentState`／`build_document_graph`；`consultant_context.py:ConsultantState` | root／consultant child 共用 `messages`，由同一原生 Saver 保存；JD 十三表沒有另一份原始訪談正文。|
| `ai_checkpoints.py:new_run_record`；`ai_records.py:build_run_record`／`request_digest_for_record` | 產生 `HumanMessage(id=run_id, content=text)`，保留原字串；新 V2 digest 包含 dataset／document／format／start_revision／text。不是把 App 通知偽裝成原話。|
| `ai_runtime.py:AiRuntime._run` | 向同一 graph 送入原 Human／run record，以 `durability="sync"` 執行；不是先把原話抄到另一份 source store。|
| `ai_checkpoints.py:AiRunCheckpoints.discover`／`observe_at` | 讀固定 root，再固定唯一 child 的 source namespace/checkpoint；支持已驗 START 原始 input 狀態。明確指定 source 時不改取 child 最新狀態；缺失／錯 scope／不相容資料拒絕，不補 latest。|
| `ai_checkpoints.py:_material`／`_messages`／`_paired_view` | 核同 dataset/document/run、message ID 不重複、非 chunk／RemoveMessage；原當輪 Human 與 run digest 配對，已存在 model view 與完整 AIMessage digest 配對。這不表示每則較舊消息另有單獨來源 hash。|
| `chat_history.py:public_chat_text`／`ChatHistoryService.read` | Human 只接受原字串；AI 用 Core 1.6.3 公開 `.text` 取公開文字，不輸出 tool/system/reasoning/signature。頁面固定 root/source，完整 message、不截句，最新版先呈現。這是聊天視圖，**尚不是 JD source issuer**。|
| `manual_runtime.py:inspect_document` | 同 owner 的同步唯讀排空範圍；source callback 必須在返回前完成讀取，不把 lazy iterator 留到資源關閉後。AI 執行本身已有真 Future 所有權；人工來源讀取也要接此既有排空能力。|

`ChatHistoryCodec` 的當前私有 `_Position` 是 format 2，包含 dataset/document/run、root checkpoint、source namespace/checkpoint、anchor/cursor purpose 與 offset；salt 是 `caliburn.jd.chat-history.v2`。其 anchor 指整份固定聊天視圖，cursor 是往較舊頁的 exclusive offset；**兩者沒有 first/last 原話區間與 source 用途，不應直接塞進 `basis_refs`**。

## 2. 現有來源形狀與共同保存檢查

### 新版來源是外部 opaque 字串，尚未有真正 issuer

`contracts/jd-work.schema.json` 的 `basis_refs` 是 string array；此層只驗參數形狀，沒有宣稱字串已可信。`jd-snapshot.schema.json:SourceLinkRow.source_ref` 要求非空、無 NUL；`jd-read.schema.json:SourceRecord` 公開原 token、`basis_status` 與獨立 `readability`。現在 `reads.py` 一律明示 `readability="not_checked"`。

`storage/schema.py:jd_source_link` 已保存 `source_ref`、`basis_digest`、position 及恰一種 typed target；它不存原話、不建立跨 Saver 的 FK。target 包含 profile 單欄、正文 item、成果／要求、條件，以及 task-capability relation。這張表與 immutable JD snapshot 已足以保存本次來源關係，**此接合不需要加原話／來源資料表**。

### 精確保存路徑

1. `reads.py:command_context(value, command, codec, source_resolver, new_id)` 在每個不同 `basis_refs` token 上呼叫 `source_resolver(token, document_id)`；只接受 `domain.Source`、同 document、`readable=True`。JD item/field/container refs 另由 `ReferenceCodec` 核 current purpose／同版；來源不經 JD ref 解碼或重簽。
2. `domain.Source` 目前只有 `document_id/readable`，**沒有種類、dataset、range 或「模型已讀」欄位**。source 的真種類／發配／範圍／dataset 必須由可信 resolver 在回傳它之前驗完；不能用 `lambda: Source(doc)` 冒充接通。
3. `intents.py:_freeze_context` 複製並固定來源材料；`_semantic_command`／`bind_edit` 再核同文件、可讀。`basis_refs` 保留 source owner 的原 opaque 字串及順序，直接進完整 request digest，不轉成 JD alias。
4. `domain.py:_Candidate.basis` 再拒絕未發配、跨文件及不可讀来源；`finish_sources` 對**最終候選**計算 basis，新 ref 新增、既有明列 ref 刷新，未列 ref 保留。人工與 AI 都走這套 domain／`JdStorage`，沒有模型專用保存規則。
5. `source_basis_digest` 是目標內容的 SHA-256，不是原話 hash、更正時效或專業支持判定。task basis 為 name/description；成果／要求為 kind/text；relation 為 task 與 capability 正文。ID、position、父分類、子項及 source 自身不進 basis。人工改文、`basis_refs=[]` 保留舊 links，讀取時自然成 `needs_recheck`；不把手改當成新訪談。
6. 來源解析在 JD SQL transaction 外；真正保存仍由原 admission、同版檢查及原子交易完成。`AdmittedIdentity`／receipt 的 lookup/recover 不重新解 source、不重算原 request、不重播寫入。

既有反例位置：`tests/test_reads.py:test_source_owner_scope_and_saved_field_digest_are_required`、`test_intents.py:test_invalid_used_refs_or_sources_are_rejected_before_binding`／`test_source_order_is_part_of_complete_command_and_opaque_values_are_not_rewritten`、`test_read_storage_integration.py:test_source_owner_rejection_cannot_create_a_bound_operation`／`test_saved_basis_becomes_needs_recheck_after_manual_edit_without_rewriting_history`。後兩者的真 PG 材料使用合成 Source，不能當成真原話 owner 已接通。

## 3. 舊已驗來源模組能學什麼、不能直接套什麼

只讀參照 `.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/`；不是建議從新版 import 舊隔離碼。

- `sources.py:ConversationReader.capture_input` 以已保存的 latest Human 為最後界線，保留前一則公開 AI 及必要前置回答；`read` 固定 checkpoint 和 first/last IDs，回 segments、role、text_offset、omitted kinds 與 App 算好的 next_offset。原 tool／reasoning 不成員工原話，缺 checkpoint 不補最新。
- 舊 `conversation:` ref 是 Base64 JSON，**只有** `{document, checkpoint, first, last}`；不是簽章或讀取證明，沒有新版 dataset incarnation，也沒有 root/source namespace 雙位置。把這個 reader 直接掛新版 root，不能據此保證 active child 的來源或還原後 scope 正確。
- `jd_references.py:validate_sources` 另要求已發配記錄；current input 依保存 Human 核對，歷史來源另核完整安全 window。`jd_tools.py:wrap_tool_call` 只記錄真正 source reader 成功產出的回覆，與 ToolMessage 一起進原生 `Command`；parseable ref 或 Memory guide 本身不等於已讀原文。
- 既有 `test_jd_sources.py` 有「能 parse 但未發配」拒絕、跨 document/checkpoint 拒絕、tool-only 不冒充 current Human，以及原 Memory reader→JD 引用的固定驗收。本次只核對程式，沒有重跑其服務／資料庫。

可保留的是**來源 owner 發配、固定原訊息範圍、角色區分、實際提供的材料才能引用**；不保留舊 token 外形、Plate node target 或舊 checkpoint schema。Memory 摘要路徑仍只協助找原文；裸可變 Memory 路徑不得變成 JD 永久來源。

## 4. 三個實際缺口與推薦的最小首接

### S1：真正 source owner 與新版固定來源 reference

沿現有 `AiRunCheckpoints` 做薄 owner，提供「取得本輪已保存原話窗口」與「驗一枚 source_ref 並讀回同一窗口」兩個本機接點；可由同一驗證讀取回傳 `Source(doc, True)` 供既有 resolver。不要自寫 Saver reader、branch engine 或第二份原話保存。

推薦 source owner **直接**以原標準 ItsDangerous serializer／SHA-256、同 configuration key／dataset 發配其自己的具名 purpose/salt 與格式版。最小定位欄位沿已驗 ChatHistory 的 dataset/document/run/root_checkpoint/source_namespace/source_checkpoint，另加 first/last message IDs；不加入游標 offset，不存原文。來源格式與舊四欄 `conversation:` 明確區別，source token 不接受 JD ref、chat anchor/cursor 或舊未驗 locator 互換。

這裡共享的是框架、設定與固定 `observe_at`，**不需要把 `ChatHistoryCodec` 改成接受任意 purpose／payload 的通用簽章服務**。現有 `_Position` 及 anchor/cursor API 可保持不動。若實作時要共用少量序列化 helper，只抽已完全相同的固定邊界，不先造多態 resolver。沿原 4 KiB／未壓縮 admission 驗容量；ref 過大不截 ID、不把 payload 改掛新 registry。

新資料集還原後原 source token 應拒絕；這是 incarnation 界線，不等於刪掉已保存 JD links。來源暫不可讀不變更歷史或 basis。

### S2：在真 model request 提供當輪來源，不先增加工具

首接採主代理選定方向：在本輪 Human 已原生持久保存後、實際模型請求前，由 owner 固定一次窗口。last 必須是 `HumanMessage.id == run_id`，first 為必要的前一則**完整公開 AI 回應**或該 Human 本身；以 assistant 上下文呈現，不自動稱其文字是員工事實或保證一定是問句。中間如有 tool／隱藏內容仍按角色／公開投影排除，不能把原 native message 刪改。

模型可取得 source_ref 與「這枚引用涵蓋本輪原回答及哪段 assistant 上下文」的可信 metadata；正文留在實際原 user/assistant 訊息，不放 system、不偽造員工新原話或無配對 ToolMessage。沿 `consultant_context.py:_project` 的現有規則，system 僅加入可信標記／refs；在送出的 request 核原 Human 及所指公開 AI 內容确實仍可見。runtime context 裡有值不等於模型收到了來源。

同輪工具 loop 保存**同一枚** source_ref／固定窗口，不因 checkpoint 前進重發另一來源：`bind_edit` 本來就把 source opaque 字串放進 request digest；不得在重試／查回時以重新簽發改變原意圖。已發配的 token 只證明來源定位／供應，不宣稱模型理解、引用支持整項 target 或已處理較新更正。

現在 `consultant_tools.py:build_jd_tools`／`_call_identity` 是八寫入＋`jd_read`／`jd_change_read` 的具名白名單；首接不擴它。過去窗口／Memory 路徑的按需深讀留下一工作單位，不能把只提供當輪原话說成全歷史來源檢索已完成。

### S3：共同 resolver 與實際查回結果接入兩個入口

已存在的接線為：

```text
同一 source owner.resolve(token, document)
  → AiRuntime(source_resolver=...) → AiToolSession.prepare → command_context
  → ManualService(source_resolver=...) → command_context
  → bind_edit → 原共同 domain / JdStorage
```

`managed_app.py:open_managed_app` 現在兩邊都沒注入。`ManualService._no_sources` 回 invalid_ref，`AiToolSession._no_sources` 回 source_not_available；`test_consultant_tools.py:test_unavailable_source_and_selection_do_not_fabricate_authority` 已明示無來源不生成 binding／不寫入。這個未接 seam 正好可由同一 owner 填入，無須改八個業務操作。

新 basis 的驗證必須真的读原窗口，核 version/purpose/dataset/document、固定 root/source、first/last 存在且有原 Human、完整範圍／角色；不能只验簽章就回 `readable=True`。人工來源讀取沿 `inspect_document` 排空；AI 讀取沿已承擔回合的真 Future。兩邊 lookup/recover 一律只查原 operation 身分，不為恢復重讀來源。

JD 投影的 `basis_status` 繼續由原 shared digest 計算；沒有完成 actual owner read 的 source 仍為 `not_checked`，不要把 issuer 成功改寫成永久 available。首接可只由 resolver／受測的本機 read 接點提供真原文；後續員工原畫面展開來源，再沿正式契約接 endpoint，不改 JD 保存權威。

## 5. 首接必測的有限反例

1. 最新 Human 尚在 active child、root 仍 pending；source 使用固定 root/source 回到原 Human。工具 loop／關閉後新 checkpoint／新 codec 不改原窗口；缺固定 checkpoint 拒絕，不能補 latest。
2. first/last 不存在、倒序、tool-only、跨 run／document／dataset、chat cursor／JD ref／舊四欄 ref 代入，都不能取得可用 Source。本文含指令句仍只是 user 資料，不進 system。
3. 真 SDK 離線捕捉 model request：source_ref 對應的原 user／assistant 公開文字確實可見，原 Human 原字串及 ID 不變；只有 runtime metadata 不算通過。長前置 AI／長繁中原話不能靜默截句冒充完整來源。
4. 同來源分別經人工及 AI 保存：取得相同 typed source 檢查、target basis 與 SQL 關係；多欄合併以最終 target 算 basis。人工更正保留 link 並需重查，明示重新驗來源才刷新；不因可讀就自動判定專業支持。
5. 保存成功但回覆遺失，重開查回原 receipt 時讓 source reader 故意不可用；仍不能重發來源、重算 digest 或重做 SQL。這驗來源接合沒有破壞已完成的 candidate-free 恢復。

既有官方依據沿[兩家 context／來源研究](../../2026-09-10-jd-context-change-and-source-research.md)及[固定原生讀取前置](../2026-09-13-jd-read-reference-preflight.md)。本輪新增的是 Caliburn 的薄接線建議，不宣稱 OpenAI／Anthropic 使用相同 source token、JD 欄位或資料表；沒有因舊資料格式已存在就把它當成新版相容證據。
