# 原回合歷史定位：獨立窄審

日期：2026-09-13。基準 `36cc1cb9` 加本輪 `ai_history.py`／`test_ai_history.py`。審查者不是這兩檔作者；本次只唯讀核對其行為與必要 caller，將 `AiRunCheckpoints.observe_at` 視為已知接口，不自審該接口實作。未修改 src 或測試。

**結果：本次範圍未發現未處理 P1／P2，無阻擋。**適用目前「完整且持續保留的 canonical messages」與既有同文件准入／讀取排空契約，不延伸成對任意壓縮、刪訊息或 checkpoint 搬移的保證。

## 核對與具體證據

| 核對項 | 結果 |
|---|---|
| 祖先與旁支 | `find` 第58行只選一次目前位置；第90、123行沿 public Saver tuple 的 `parent_config`。沒有以 `get_state_history` 最近列或訊息相同選支線。測試製造訊息前綴相同但 status 不同的较新旁支，仍選目前分支的原 A。 |
| 固定 START 邊界 | 目前 run 由既有 discover 解原保存位置；較舊祖先即使 START 投影仍含前一個 record，也必須 `next/tasks/interrupts` 全空且 record terminal 才能作候選。測試分別中斷 input／loop：真 parent存在時查回 A，parent缺失則明確 lookup_required，不拼湊缺失鏈。 |
| 舊回合的真正截止 | 第74–75行取目標 Human 到下一 Human 前的完整前綴；候選經 observe_at 後必須 messages **完整相等**，不是 startswith。測試祖先自稱 A卻已有額外 Human，回 invalid_checkpoint，不將後續原話算進 A的回覆。 |
| absence 的條件 | 在目前 full-messages 契約下，先核最後 Human 是 current record 的 run，原 ID 不存在才可 None；若 ID撞到 AI／Tool，不能當作未使用 key。缺有效 current原資料由 discover拒絕。測試包括初次空歷史、未使用 UUID、assistant ID碰撞及不一致的最後Human。 |
| 有界查找 | 256是App有界上限；超限、循環、缺tuple、沒有可驗候選的斷鏈均回 original_run_lookup_required，沒有回 None。測試將上限縮為1，確認舊 A不能被錯認為新請求。此限制已明示，未當作無限歷史查詢承諾。 |
| document／dataset 隔離 | 每個 tuple／snapshot／parent需同document與空root namespace，checkpoint ID一致；候選record也核document及dataset。錯dataset拒絕，另一份空document不回傳A；錯parent document／namespace／ID等反例均拒絕。 |
| 不重播或改寫 | 模組只呼叫 discover、get_tuple、get_state、observe_at；沒有 invoke、update、receipt重建或 writer permit。原始Human與完整AI內容只比較／回讀，測試模型計數維持原次數。 |
| caller 與排空 | 新 `AiRuntime.lookup` 透過 owner.inspect_document；新 start 的原回合查讀在 owner.admit_foreground內。歷史helper本身不是准入或停止證明，不能把 None直接用於未受owner保護的寫入。 |

## 明確限制

- 只有完整 append-only canonical messages 讓「目前沒有此 ID」具有現有契約下的 absence 意義。未來若採模型 context壓縮，不能把壓縮投影取代此原始訊息權威；若要改此保存契約，必須同步改 absence規則。
- 同run的 receipts／tool-call-result與原 request digest是否符合公開start意圖，由 coordinator後續核對；history定位不自行重新計算業務結果或核准重播。
- 讀取位置固定，不表示關閉後仍可使用Saver。helper需在既有owner追蹤的同步callback内完成，不能外逃lazy讀取。
- 256上限用完會要求明確查回處理；本次沒有將它設計成一般分頁服務或另加索引／run表。

## 實際驗證

獨立執行 `tests/test_ai_history.py`：**21 PASS，1.03秒**。使用已鎖定隔離環境 `uv run --offline --frozen --no-sync`、原生 InMemorySaver／root／child；0 provider、0 DB、未啟新程序。

未發現需修正的具體反例，因此沒有新增首敗；以上數字是本次實際窄跑，沒有引用未重跑全組作本次通過證據。本報告不宣稱聊天 HTTP／Web／真 DB歷史查回或完整產品已完成。
