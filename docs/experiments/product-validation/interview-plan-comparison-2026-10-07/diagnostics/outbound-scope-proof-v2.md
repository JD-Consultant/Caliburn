# 新未啟動批次的授權澄清與時間修訂

這是原八場合成職務比較的剩餘七場，不是新真人訪談。原 [範圍證據](outbound-scope-proof.md)、兩次自動審查拒絕原件、原 04:30Z preflight 與 disk audit 全部保留。

使用者先前直接要求：「同意 開始實作 做完測試 並直接比較『只有指引』與『指引＋筆記』不用我授權 真實api key 可以直接用」。在兩次自動拒絕後，協調者向同一使用者明確提出：僅送本次兩個虛構職務 warehouse／course_admin 及其合成訪談／JD／Memory／notes／共用指南到 `https://api.openai.com`，不含既有真人資料，正式 aggregate USD8。使用者對這項具體澄清直接回覆：「好可以測試 也可以順便測試 冷藏、錯儲位及旺季漏問仍待改善。下一步應聚焦選問優先順序，不再堆更多規則。」本批只完成原八場凍結對照；新的選問實驗另由協調者處理，不在此批額外外送。

因授權澄清等待至 2026-10-07T02:53Z，協調者明確將尚未啟動的 supplement revision 截止修訂為 `2026-10-07T08:30:34Z`，保留 aggregate USD8／3000gen／7000outbound／180M counted input／32compact、每場20Turn、原模型/runtime/guides/arm/pressure、所有已支出與兩筆未知預留。新版入口為 `completion_batch_v2.py`；原入口与所有舊 manifest 不改寫。

新版 manifest 明列舊與新絕對截止、原因、counters_and_reservations_reset=false。seconds metadata=39600 是原 formal 凍結21:30:34Z起總11小時；真正 guard.seconds 仍是啟動時絕對截止減 wall now，且 monotonic anchor 先於 constructor，等待與建構時間均會消耗剩餘時間。原 disk audit 仍按原04:30Z歷史核，沒有偽装成新截止。

資料僅來自此實驗自行建立、hash固定的合成 private facts，以及同樣空白的新隨機schema／新job_file。員工固定標籤「條件回答者」，RAGoff、不匯入既有員工；舊結果只供帳務與機械選案，沒有進模型payload。唯一對外host為guard完全比對的 `api.openai.com` HTTPS，僅POST responses／input_tokens／compact；SDK trust_env=False、follow_redirects=False。來源／key/C路徑/audit/任何真人資料不加入模型 request。

新的動作維持同一 Python exec／原 HTTP driver／transport fence，不更換網路或借另一入口規避審查。若新具體 human 澄清仍未被核准，只保留停止與拒絕原件，不自行繞過。
