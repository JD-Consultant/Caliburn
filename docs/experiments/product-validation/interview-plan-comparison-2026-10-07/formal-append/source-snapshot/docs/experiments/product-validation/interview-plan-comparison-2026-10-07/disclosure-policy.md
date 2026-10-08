# 凍結的人工條件披露政策

真正 paid journey 每一個後續員工回答均須獨立代理匿名語意核定。keyword candidate 只供提醒，不是放行權威。judge 只讀 profile、actual question、已披露／open／seen／refused state、最近三段已送員工原話及凍結 oracle；不看 arm、plan、模型工具、cost 或其他組結果。每題 pending／decision／selected 原件保留。

判定依實際相關性與已提供內容，不依字面 keyword 或輪次；否定、已知摘要及無問題的結論不能釋出隱藏事實。間接指涉須依最近原話解讀。compound 同時問不同工作，可回答所有明確相關且可取得 fact IDs，最多 4 個。不為兩組保持同序而強塞答案。

先前答不出 inventory-authority／absence-handoff，只有實際指定的新主題 training／refund 已披露後，且顧問相關回訪，才能揭露。training-boundary 只在 training 先前已披露且同題再確認責任時可揭露。年度例外或低頻工作在相關廣度／頻率問題可披露；不由摘要、pipeline 轮次或 hidden omission 標籤觸發。特定投訴個案拒答不阻止個資保存流程；未主動重新同意，不重開該個案。

decision 格式為 `{question_id, fact_ids, mode, reason, omitted_subtopics, unknown_subtopics}`；最後兩欄可省略。mode 是 answer／unknown／refused／clarify／no_question。answer 的 IDs 必須來自本 profile，原字串 `fact.answer` 逐字組合，不創作、改寫或從別組補內容。已知確認可重播相同 frozen answer；先前更正已披露時，相關原流程須連同更正 ID 回播以免恢復錯誤權限。不把已說過的內容當 true unknown，也不重新打開已解 gap。mode answer 須有 ID，其他 mode 不帶 ID；reason 記相關性與條件，不能帶組別。

真正問到 oracle 沒有的新細節且整題無可答部分，使用 unknown、0 IDs，固定保留未知，不引導重問。compound 混合可答與真正未知時，以 answer 回相關 IDs，unknown_subtopics 只填實際問題的逐字片段；程式追加「關於你問的『片段』，我目前沒有確定資料，請保留未知，不補猜。」不把一般既有流程冒充特定情境答案。omitted_subtopics 僅用於 compound 本次未答、可於後續相關提問取得的部分；禁止把 oracle 沒有的細節標為 omitted，禁止因此建議可再取得。clarify 僅指實際指涉不明，需要釐清，與真正未知及沒有提問分開。

no_question 指實際沒有問題而只是確認、摘要或停止追問；不觸發任何 fact。driver 可送共用中性提醒「可以依我已說過的工作範圍繼續訪談；我沒有新增事實。」每場最多 2 次，不能連續送；提醒後仍沒有提問，或提醒額度用完，就送共同收束，記缺主動推進及未完整，不當自然完成。提醒單列 driver_reminder，不列受訪者 unknown，也不列顧問自主回訪；提醒器不提供題目、缺口或 oracle。若模型已給 JD 而有重要工作尚未揭露，留給盲評判斷，不由提醒器補題。

120 秒未收到核定就停止，時間不是核准。不允許 fallback 自動披露。selected state 使用影本，HTTP POST accepted 後才標 submitted；正式 HTTP interviews 的 source ID 另核正式可見。未送出的答案及最後 Turn 後的無用答案不列已披露，blind bundle 只取正式 HTTP 員工原話及引用。

judge 將 decision.json 寫到同一匿名 reviews/<opaque question_id>/ 目錄，禁止改 public input、private fact 或其他組 artifact。本政策／oracle／harness 每批 hash 及原文 snapshot 凍結；pilot 修正必要時新 batch 保存全部舊原件，不回寫既有外送材料。此版只適用正式批次；先導用其 manifest、封存政策及原 decision 判讀。
