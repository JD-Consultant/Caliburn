# CT08：訪談重問與部分理解漏更新

Topic LLM-Q019，2026-09-07；Owner 核准局部修復及重測，設計可因新證據調整。基準 `a773ba26`。唯一 gate：CT07 兩項缺陷能否以現有流程局部校準？

**最新結論：限定重播通過。** 主顧問不再重問已答未知的決策者；最後 B2 變體更新 B 的已知／未知及引用，6次完成發布；無近期對話 reader 再3次成功回查。第二帳本9次／估US$0.00724670，已關閉；兩帳本共33次／估US$0.02722310（含11次無效診斷）。下方首次失敗是沿革，不代表最後變體仍未測。長訪談整體／UI／JD不在本輪驗收。

## 診斷

基準：[CT07](2026-09-07-continuous-interview-trial.md)及其 JSON。第3輪已說不知道 B 案回復決策者，顧問仍重問；另外問本人是否執行回復是新問題，不能把整段都算無用。

第4–5輪的 B1 `rollout_summary`、`raw_memory`，及 B2 request 19 的 `NEW_CANDIDATES` **全都有**「提供前端錯誤重現步驟，回復決策者／執行者未確認」。不是 B1 或 context 漏資料。B2 更新 A 案，卻讓 B 正文仍標籠統未知、缺新引用。標題偏 A 可能影響注意力，不能宣稱已證明模型內部原因。

## 官方依據與本案映射

- [OpenAI GPT-5.6 提示指南](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)：以實際失敗做最小提示修正，交代決策條件，避免重複／矛盾；沒有證據不等於否定。本案依此區分未問、目前答不出來、部分已知，選另一個可回答且有用的問題；不新增永久禁問狀態。
- [OpenAI Codex Consolidation template](https://raw.githubusercontent.com/openai/codex/main/codex-rs/memories/write/templates/memories/consolidation.md)：參閱 Incremental update、Task boundaries、Ordering and conflict handling；增量合入相關主題、維持主題局部引用、保留仍成立資訊與未解不確定性、更新導覽。本案是處理本批每個受影響主題，部分已答只留下剩餘未知，並更新相關依據；不是每段塞全部引用或重讀全部歷史。
- [Anthropic Memory tool／Prompting guidance](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool#prompting-guidance)：可由提示限定要記什麼，保持記憶現行、一致、有需要才增加檔案。本案沿用既有檔案及工具，不加表、Agent、語意 validator 或每輪強制整理。

以上是官方原則＋本案用語，**不是三家有相同訪談規則**。來源2026-09-07核對；Codex main 會變動，本次不導入其額外新格式。

## 範圍及驗收

只改 `api.py` 主顧問、`consolidation.py` B2 提示。Skill 無衝突、B1 已正確，均不改。API／Store／checkpointer／來源／發布／tools／reasoning／模型／步數不變。

驗收：①不重問員工已說目前答不出的同題，繼續有用訪談；②B 正文有提供重現步驟，回復決策者／執行者仍未知；③B 主題可沿新引用讀到補充；④A 更正頻率、B 月／年頻、責任及重要差異保留；⑤無近期對話 reader 可回查 B 新資訊。

## 結果

第一輪真實重測：主顧問改問員工本人角色，沒有重問未知決策者；第4輪保留已知／未知並換方向。B1及B2輸入仍正確，但B2再度保留B案舊說法，**未修復**。用了13次，含主6、B1一次及B2六次，沒有工具錯誤，實際發布rev2。

最後一個限定變體：把抽象的部分已知指引改成先對照受影響主題，再編輯；增加一個「初審已知、核准者仍未知」的非測試案例對比。不增加schema、工具或額外審查模型。[Anthropic 提示最佳實務／Use examples effectively](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices#use-examples-effectively)建議用有關聯、清楚區隔的例子具體傳達行為。本案只取一個最小例子（不是宣稱照搬其3–5個例子的建議，更不是宣稱對Luna必然有效），須實測。若仍失敗停止，保留問題，不累加規則或偷換模型。

最後變體尚未有效驗證：定向腳本直接呼叫 B2 時未先關閉自動排程，兩條執行同時處理測試 fixture。request14–24 全部計費並保留，但**不能作為語意／效率對照**；第25次被實驗護欄阻止，沒有追加生成。後續只讀檢查顯示該新實驗文件仍是舊head rev1，background blocked。這是測試入口誤用，不據此宣稱正常 API 會重複執行。已修診斷腳本：在 app 建立前停用自動排程入口，並確認沒有 scheduler，再允許直接重播；正常訪談測法／產品排程均不改。

本帳本已關閉，**24次／估 US$0.01997640**：正常主訪談6、B1一次、B2六次，無效定向重播11次。三輪主回覆約8.77／7.16／7.06秒。沒有 fresh reader 結果。已請 Owner 選擇是否另允最多12次／US$0.05重測；未收到新答覆前不追加。全部原始證據、腳本及資料源 hash：[CT08 evidence](evidence/2026-09-07-interview-partial-knowledge-repair.json)。收錄的診斷脚本是後來修好隔離的版本；無效試驗是否重複呼叫以wire紀錄為準，不聲稱當時用的就是修正後腳本。

**第一帳本關閉時的歷史狀態：主顧問重問在本樣本改善；B2部分已知／引用仍 OPEN，最後例子變體待有效重測。** 不因 HTTP200、發布成功或離線測試綠燈而關閉語意缺陷。此前完整離線548 passed／0 skipped（82.40s），在最後例子變體前執行；最終針對性回歸另記。

CT06 精確 edit_file 問題本輪有成功局部修改，但不能憑不同輸入全面關閉舊空白錯誤；未測 UI、長時間壓縮或 JD。保持隔離、不 merge/push；不加新機制掩蓋問題。

## 新核准的有效重測／最終 gate

Owner 回覆「同意，只補這次驗證」，另12次／US$0.05。沿用第一次重測已生成的 B1 詳記／候選及相同舊head，在新實驗文件重綁真實來源地址，停用測試排程後走完整 B2 start → save → prepare → publish。不是再次抽取，也不是新的自然觸發測試；產品仍由正常背景入口負責。

- **B2 6次、發布rev2：PASS。** B 正文寫成「目前只確認員工會先提供前端錯誤重現步驟；誰決定回復舊版，以及是否由員工執行回復，仍未確認」。正文及B導覽都有支援此說法的新詳記引用；两份詳記均可回查原文。A每兩週週一、B每月第一工作日／每年活動季前、姓名與日期保留、正式資料刪除權、帳務交接、三小時不當固定耗時等仍存在。方法示例沒有變成员工事實。
- **無近期對話 reader 3次：PASS。** 第一個request只有新問句＋讀取規則／導覽，無先前員工訊息或opaque reasoning；使用既有按需讀取工具後，答出B新角色／未知、兩案頻率／界線及A付款異常步驟。沒有要求此次深入原始對話才算成功。
- **成本與停止：** 9/12次，估US$0.00724670，帳本關閉不再消耗剩餘額度；加上前帳本共33次／US$0.02722310。是usage估算，不是供應商帳單。
- **離線：** 最後示例版本 API／B2／Skills 60 passed（13.36s），前一變體完整548 passed（82.40s）；均0 skipped，1項既有Starlette/anyio deprecation warning。不把這些測試當語意保證。獨立靜態review未發現Critical／Important／Minor，仍須以真實內容驗收為準。

證據：[新增帳本／回查／生成正文與引用／可重播腳本](evidence/2026-09-07-interview-partial-knowledge-followup.json)。兩次帳本分開保存，不覆寫失敗。CT07-Q01a/b本次**限定情境 CLOSED**；若新樣本再發生則重開，不宣稱機率為零。

小項觀察：reader把「每月確認測試報名收到」與「交付驗收三種情境」相鄰描述，可能讓人混讀為每月完整驗收。正文兩者原本分開，尚未證明每月重做完整驗收；列 CT08-M01 wording ambiguity，下一次正常訪談順便觀察，不為此另加機制或本輪加測。最後例子變體沒有再跑整套新訪談，亦未做長壓縮、真UI、JD驗收。

下一步：回到一般訪談試用，觀察跨主題增量與上述措辭；不重選記憶架構、不先擴充元件。本文與 [短計畫](../plans/2026-09-07-interview-partial-knowledge-repair.md)是本輪入口，詳細wire只存 evidence。
