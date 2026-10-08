# 凍結的人工條件披露政策

真正 paid journey 每一個後續員工回答均須獨立代理匿名語意核定。keyword candidate 只供提醒，不是放行權威。judge 只讀 profile、actual question、已披露／open／seen／refused state、最近三段已送員工原話及凍結 oracle；不看 arm、plan、模型工具、cost 或其他組結果。每題 pending／decision／selected 原件保留。

判定依實際相關性與已提供內容，不依字面 keyword 或輪次；否定、已知摘要及無問題的結論不能釋出隱藏事實。間接指涉須依最近原話解讀。compound 同時問不同工作，可回答所有明確相關且可取得 fact IDs，最多 4 個；剩餘部分以固定句保留。不為兩組保持同序而强塞答案。

先前答不出 inventory-authority／absence-handoff，只有實際指定的新主題 training／refund 已披露後，且顧問相關回訪，才能揭露。training-boundary 只在 training 先前已披露且同題再確認責任時可揭露。年度例外或低頻工作在相關廣度／頻率問題可披露；不由摘要、pipeline 轮次或 hidden omission 標籤觸發。特定投訴個案拒答不阻止個資保存流程；未主動重新同意，不重開該個案。

decision 格式為 `{question_id, fact_ids, mode, reason, omitted_subtopics}`。mode 是 answer／unknown／refused／clarify。answer 的 IDs 必須來自本 profile，原字串 `fact.answer` 逐字組合，不創作、改寫或從別組補內容。已知確認可重播相同 frozen answer；不把已說過的內容當 true unknown，也不重新打開已解 gap。其他 mode 使用程式內固定句。mode answer 須有 ID，其他 mode 不帶 ID；reason 記相關性與條件，不能帶組別。

120 秒未收到核定就停止，時間不是核准。不允許 fallback 自動披露。selected state 使用影本，HTTP POST accepted 後才標 submitted；正式 HTTP interviews 的 source ID 另核正式可見。未送出的答案及最後 Turn 後的無用答案不列已披露，blind bundle 只取正式 HTTP 員工原話及引用。

judge 將 decision.json 寫到同一匿名 reviews/<opaque question_id>/ 目錄，禁止改 public input、private fact 或其他組 artifact。本政策／oracle／harness 每批 hash 凍結；pilot 修正必要時新 batch 保存全部舊原件，不回寫既有外送材料。
