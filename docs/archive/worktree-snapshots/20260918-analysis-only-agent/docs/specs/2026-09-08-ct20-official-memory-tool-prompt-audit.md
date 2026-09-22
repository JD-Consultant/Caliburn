# CT20：官方 Memory／工具提示核對

2026-09-08 · Q019-MEM-CADENCE-01／CT15-R07 · **G2研究；下一候選待審，G8仍OPEN。**

## 1. 這輪只補什麼

Owner追加研究 OpenAI／Anthropic 的 Memory tool prompt。承接[CT19失敗並撤回](2026-09-08-ct19-routing-regression.md)，不是再次核准修改或付費測試。只回答：官方實際如何提示讀寫、目前哪些差異值得再測？不重開ABC、Memory分層、JD或模型選擇。

已回讀主repo register／decision-process、CT18、CT19與[CT15整併入料底層研究](2026-09-07-ct15-openai-consolidation-input-trace.md)。CT18已查過OpenAI同輪修補指令，這不是本輪新發現；本轮新增Anthropic專用Memory自動提示的邊界、兩家工具提示建議的差異、當前工具定義的離線wire核對。未讀Owner排除的舊產品流程長文。唯一入口仍是[主repo register](../../../../docs/current-decisions.md)。

## 2. 官方說了什麼，不能推成什麼

| 層／來源 | 已核對的公開做法 | 本案邊界 |
|---|---|---|
| OpenAI Sandbox Memory [O1]，安裝SDK `prompts.py`／`memory_read_prompt.md` [O2] | 導覽隨指令提供；按需搜尋正文，再按需深讀。開啟live update時，提示先給寫入權限與核實過時資料後的同輪更新要求，然後才是檢索判準；寫入是完成條件 | **是指令，不是SDK自動辨識所有更正。** 已有資料足夠回答與已完成必要更新是兩回事；此規則CT18已知道，CT19整理提示仍漏選工具 |
| Anthropic專用Memory [A1] | API在該專用工具存在時，自動加入先檢查Memory及工作途中記錄進展的提示；可指定要保留哪類資訊，已有整理規則不必重複 | 不是任意名為memory的自訂函式都會取得。不能把Claude專用tool `type`或自動提示視為目前Luna＋自訂工具已附帶的能力 |
| OpenAI函式提示 [O3]、推理模型 [O4]、精簡指引 [O5] | 明確用途、參數、何時使用／不使用、完成條件；避免互相衝突及無效重複。對推理模型，範例也可能傷害表現 | 不支持「再加很多MUST就會修好」或「先一律增加few-shot」。也不要求把相同路由規則抄到每個位置 |
| Anthropic自訂工具與排錯 [A2][A3] | description要交代何時使用，不只是怎麼操作；優先清楚描述，再考慮參數範例。漏選、選錯與參數錯誤是不同問題 | `input_examples`主要示範合法輸入，不自動證明某輪必須呼叫。這份Claude排錯表不能直接當成Luna根因診斷 |

可共同學習的是**清楚的使用條件、真實可執行的工具、明確結果／錯誤與完成條件**；不是每家都有相同Memory工具、提示文字或排程。OpenAI條件式查找與Anthropic先看目錄不同，不混成「每輪強制完整讀寫」的共識。官方建議也不能證明某個本案候選效果最佳。

### 背景提示不是主顧問的修補提示

OpenAI SDK另外有Extraction與Consolidation提示 [O2]。本輪重讀相關段落確認：有依據才寫、原文不改、來源內容當資料、沒有有意義新資訊可no-op；增量整併保留仍有支持的共用內容，再清理失效導覽。其移除規則針對明確列為removed的來源，不等於「本批沒有再提供」；不據此開啟本案案例過期或遺忘。這些背景規則不是放進主顧問就自動運作。

SDK背景提示的資訊取捨偏重未來可重用經驗、操作偏好和失敗教訓，**不能全文照搬成職務訪談的保留標準**。本案工作責任、條件、頻率、例外與案例差異，仍依已討論的[職務資訊取捨](../../../../docs/specs/2026-09-07-work-case-and-understanding-information-selection.md)。學有依據、避免過度概括、沿引用補查與保留未改內容；不因某項工作只是單一案例、低頻或本輪沒再提到，就刪去其有用資料。

SDK有`extra_prompt`延伸入口；這只證明可提供領域重點，不代表現在需換SDK或將編碼代理的全部預設搬入。Codex與Python SDK背景入料本來就有差異，仍以CT15原研究為準，不用本輪提示摘讀覆蓋它。

## 3. 對照目前真正送入的工具

基準HEAD `cc90fe0b`，產品提示已撤回至CT19施工前版本。沿現有`test_live_memory.h`建立真正LangChain／OpenAI SDK流程，以`httpx.MockTransport`固定回應、記憶體Saver／Store及SQLite，離線讀取一個request；**不是CT19原wire的復原，也不是真模型新測**。

| 當前wire觀察 | 結論／限制 |
|---|---|
| 6工具名稱各異：ls、read_file、grep、read_conversation、repair_memory、request_memory_consolidation | 目前沒有漏綁C/B或名稱撞名的證據 |
| C description 2,252字元，起首偏重小批patch操作；模型參數只有`edits`，每項沿既有`path`／`diff`契約 | 不是工具完全沒說明。觸發修補的政策已在system，不能說「漏了WHEN所以找到根因」。但tool-local入口可否更直觀，是尚未測過的局部差異 |
| B description 502字元，空參數；含實質進展、修補未保存、純重述、回傳僅收到通知等判準 | 這次並非模型需填理由／ID才不呼叫。B/C邊界的歧義CT18已記錄，CT19嘗試整理仍失敗，不重報成新發現 |
| `tool_choice`未送出、`parallel_tool_calls=false` | 預設允許零工具；自動選擇不保證必要副作用發生 [O3]。離線回應故意固定零工具，不是新的語意失敗證據 |

另外兩個**靜態風險**：C工具說導覽在routing改變時更新，system則也要求修正導覽裡的過時事實；日期改了但路由沒變，文字應對齊。CT19已記錄的`retryable=True`第一次失敗不能被提示草率當成B接手條件。兩者都不是CT19零工具trace已觸發的錯誤。

工具description的SHA256：C=`e9a21352378310237abd92cb979fa2e51c2f0aa9ae074ebe2a495b2b2cf79521`；B=`280f4d85a79b43af6d10e05ba7d20e3a8c958b08956ad76e17a0ffda2e9dc321`。字元數不是token數或官方限制，不能由長度判定模型漏選原因。

## 4. 下一步建議：先替換一份清楚契約，不再疊補丁

**建議A（待Owner確認）：**將現有讀取／修補／B通知的提示整理為單一、一致的職責契約；以官方live-update完成条件及工具WHEN指引為參考。system持有條件與優先順序，工具說明簡短交代適用時機及真實輸入／回傳，移除重複或相互打架的規則，而非另加提示。補齊上面導覽與可重試回饋的一致性；保留既有安全、案例保真、引用和patch規則。不改ABC、模型、工具參數、儲存或增加強制呼叫。

這是**本案下一候選方向，不是已證實的根因修復**。目前尚不能僅憑高階描述證明A與CT19有足夠差異；若要試，須先展示整份最終system＋工具定義的對照，確認有可測的新差異、沒有重複加入，也沒刪除先前有效的防錯規則。若只是重述CT19，就不再用同一失敗方案換名字重跑。

- B選項：少量針對性正反情境範例。先不加；OpenAI對推理模型的警語與Anthropic優先描述的建議，都不支持直接大量加例子。未來要測需與A分開，不能拿「10改5」唯一情境教答案。
- C選項：程式強制選工具／新增完成檢查。會改變流程與成本，非本次研究結論，未選；目前證據也不足以指定每輪必寫。

候選A不增加固定模型輪次，但真實保存本來就需要讀／改工具及後續生成，不能承諾零成本或一定更便宜。成功標準必須看Memory實際發布內容，不能只看回答已採用新日期。

獲准後最小回歸仍涵蓋：自然新更正、對話已更正但Memory未改的重述、已保存純重述、未知／矛盾先問、首次可重試錯誤及其他案例細節不被抹去。參數／patch／來源回查先走既有離線安全網，再確認付費範圍；不重跑全職位長測來探索每一句提示。遇到同一漏選反例再失敗就停止，不無界加字。

## 5. 來源定位與核對邊界

官網於2026-09-08讀取；本地OpenAI Agents SDK為已安裝0.22.0，**不宣稱它是最新發行或等同全部ChatGPT／Codex內部實作**。官方現行頁與固定本地來源互相核對，不使用非官方洩漏prompt。

- [O1：Sandbox Memory，persist memory across runs](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs)：能力／分工。
- O2：本地官方SDK `experiments/analysis-agent/.venv/Lib/site-packages/agents/sandbox/memory/`。`prompts.py`全文、`memory_read_prompt.md`全文及capability全文承接CT18並再核對；背景本輪只重讀extraction的Safety／Signal Gate／Evidence、consolidation的Safety／Incremental update／導覽規則，沒有宣稱重新審核全部背景程式。可由[既有官方固定來源](https://github.com/openai/openai-agents-python/blob/1d471a4775bf2f40179f411824da383deb4c3fca/src/agents/sandbox/memory/prompts.py)導航；不聲稱該Git SHA與本地套件相等。
- [O3：Function calling，best practices](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)及[tool choice](https://developers.openai.com/api/docs/guides/function-calling#tool-choice)：使用條件、examples警語、auto邊界。
- [O4：Reasoning，advice on prompting](https://developers.openai.com/api/docs/guides/reasoning#advice-on-prompting)：目標／約束／完成標準，非規定每步推理。
- [O5：GPT-5.6 prompting，simplify first](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6#simplify-prompts-first)：移除無效重複，但保留真正限制。
- [A1：Memory tool，prompting guidance](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool#prompting-guidance)、同頁commands／error handling：自動提示只屬指定API工具。其`view`行號格式、`str_replace`參數／精確匹配，不可抄來取代本案DeepAgents讀取格式＋已核准OpenAI patch；否則會帶回舊編輯BUG。
- [A2：Define tools，best practices](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools#best-practices-for-tool-definitions)：描述先於參數範例；Anthropic欄位不直接移植OpenAI request。
- [A3：Troubleshooting tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/troubleshooting-tool-use#claude-calls-the-wrong-tool)：區分選擇與格式錯誤。

SDK來源SHA256：`prompts.py`=`2eb0bf2e2e097a396ca6eba9cbf98c8b0e5e3c72f1cdfc5e7f1ed5194a5f93b0`；read=`4dd97a62fc02ad75427a4f34d1fbda30d4d8afd99de99d0edafd672f873705d2`；extraction=`4b315040afad8b9991d86ed6cef50dafda667f672abbbfb9bfe2c2d637870f0b`；consolidation=`720c50b770e688ae1939cde90d23b3447c44399b96baa50286d47765c0ce80a3`。

## 6. 本輪結束條件

只更新研究與閱讀入口；未改產品／prompt／設定／持久DB，0次付費生成。離線wire探查8.52秒exit0；首次因未加`src`至import path而停止，補正探查入口後成功，非產品修正。該探查用固定provider結果，不能當自然選擇驗收。本輪不重新宣稱583測試或完整訪談通過，CT19原反例保持失敗。下一唯一gate：Owner審閱§4是否值得做一組有邊界的提示契約候選。

獨立唯讀review未發現阻塞本稿交Owner討論的問題；特別提醒A與CT19仍有概念重疊，須以上述完整對照證明差異。已據此收緊§4，未聲稱候選已定稿。review核對guide／retryable風險為靜態歧義，非已發生根因。研究內本地連結均存在，CT19證據SHA256維持原值；產品src/tests diff為空。
