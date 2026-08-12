# AI 專業職務分析顧問：產品流程工作研究稿

- 日期：2026-08-12
- 狀態：Working Research；隨 owner 討論持續修訂
- 決策狀態：只記錄已確認的產品方向與待討論問題；不是 ADR，不授權 production 實作
- 優先順序：本稿先定義「產品如何像專業顧問工作」；元件、Context Engine、RAG 技術與 framework 選型後置
- 外部資料查核：Context Engine 小節依截至 2026-08-12 可取得的官方／第一手資料整理；大廠做法是設計證據，不是免評測的產品決策
- 相關研究：[`階段式 AI 職務分析顧問 runtime/framework 研究`](2026-08-12-staged-ai-consultant-runtime-framework-research.md)只能在本產品流程核准後評估，不得反向用框架能力定義顧問流程

## 0. 這份工作稿怎麼使用

這份文件用來避免長期討論遺失已確認的大方向。每次只把已對齊的內容寫成明確規則；尚未討論或仍可能翻案的內容列在「待討論」，不假裝已定案。

目前先回答四個問題：

1. 這個 LLM 專業職務說明書顧問，從開始到匯出大致怎麼工作？
2. 員工如何知道 AI 現在為何發問、訪談進度到哪裡？
3. Task、Duty、OPKS 與 Reference 在流程中如何互相影響？
4. 長訪談中哪些內容必須完整保存、哪些每輪必帶、哪些應按需取用？

目前不回答：

- 要不要採 LangGraph、LangChain、PydanticAI 或其他框架；
- Context Engine、memory、RAG、tool、skill 的最終 schema；
- API、資料表、畫面與 migration；
- 模型、參數、價格與 provider 選型；
- 實作切片與工期。

## 1. 產品北極星

產品不是填表精靈，也不是自由聊天後一次生成 JD。它應是一位由 AI 主導訪談、持續整理全局、但沒有文件修改權的專業職務分析顧問。

白話原則：

> 先大致理解員工的真實工作，再選一個目前最值得釐清的焦點深入訪談；當下專注一件事，但不漏掉回答中出現的其他工作線索；隨著證據增加，持續修正 Task、Duty 與 OPKS，所有正式改動都交給員工決定。

固定的是分析責任與權威邊界，不是固定題目或只能往前的階段。

## 2. 已確認的大方向

### 2.1 一個主要顧問，按需組合分析 Skills

- 第一版以同一個主要 AI 顧問維持對話責任。
- 「盤點工作、深入故事、釐清 Task 邊界、整理 Duty、分析 O／P／K／S、Reference challenge、收尾檢查」是可按需載入的方法 Skills，不是八個人格化 Agent，也不是固定通關階段。
- 一輪可依焦點同時載入一個或數個相關 Skill；沒有必要的 Skill 不進當輪 prompt／context。
- 新證據可讓系統換用其他 Skill，也可重新開啟已暫時收束的 Task、Duty、O、P、K 或 S。
- 注意力模式只描述 AI 當下主要目標，不限制同一輪可進行哪些分析，也不控制資料必須依固定順序通關。
- Skill 的獨立是「方法與載入邊界」獨立，不代表分析結果彼此隔離；所有 Skill 仍需在同一份工作假說、來源與權威模型中互相校正。

### 2.2 前景專注、背景全域吸收

- 每次訪談有一個主要焦點，避免自由聊天與一次追問多個欄位。
- AI 必須閱讀員工完整回答，不得只擷取與上一題直接相關的句子。
- 回答中出現的新工作、他人工作、更正、矛盾、工具、產出、標準或 OPKS 線索都要保存並分類。
- 一般旁支線索先保留，避免打斷當下訪談；若它會改變本人責任、Task 邊界或重大文件內容，可以優先澄清。

### 2.3 AI 預設帶路，員工可隨時改道

- 一個焦點收束後，由 AI 選擇下一個最高價值焦點並說明原因。
- 不要求員工每輪理解系統階段或自行規劃下一題。
- 員工可以跳過、切換工作、暫停、補充新故事或返回先前內容。
- AI 不因員工改道而遺失尚未處理的焦點與線索。

### 2.4 AI 只提出變更，員工決定正式內容

- Work Model 是可變動的分析假說層，不是 Current JD。
- AI 可以提出新增、改名、修改、重新歸類、排序、合併、拆分或撤回候選。
- AI 不得直接修改 Current JD，也不得把員工沒有說過的內容自動補入。
- 員工可以接受、修改後接受、拒絕、暫不處理或直接編輯自己的 JD。
- 先前接受的內容仍可被新證據重新挑戰，但修改仍需員工決定。

### 2.5 Task 與 Duty 都會隨訪談演化

- 分析初期允許 Task 尚未歸入 Duty。
- 初期可有暫定責任區域協助 coverage 導航，但不得把它當成固定 Duty 盒子。
- 隨 Task 增加、合併、拆分或改變邊界，Duty 可以改名、重新分組、合併或拆分。
- 不要求先完成 Duty 才能理解 Task，也不要求 Task 一被員工接受後就永久固定。

### 2.6 單一匯出，但缺口必須可見

- 產品只有一個匯出概念，不額外建立草稿／正式兩套資料或文件生命週期。
- 匯出前列出尚未分析、待補訪、待員工決定、結構問題與已保留未知。
- 員工可以在看過缺口後強制匯出。
- 強制匯出不會自動接受 Proposal、補造 OPKS、隱藏孤立 Task 或改變 Current JD。

### 2.7 員工回答先成為 durable source，AI 失敗不應讓原話消失

- 員工送出的回答先以穩定 input event／turn identity 保存為來源記憶，再交給 AI 分析；它不是等模型成功後才附帶寫入的欄位。
- provider timeout、拒答、parse、schema 或 verifier 失敗時，該回答仍保留並標示尚未成功分析；員工不必重新輸入。
- 重試必須沿用同一個 input event，不重複建立來源；失敗期間 Work Model、Proposal 與 Current JD 都不得改變。
- 這項產品裁決取代 2026-07-30 最小完整迴圈中「模型失敗時 Journal 完全不變、只由 Web 保留草稿」的舊假設；實作前仍須以 ADR／plan 補齊交易、idempotency 與 migration 邊界。

## 3. 白話產品流程 v0.1

### 3.1 開始或恢復

新文件先簡單理解：

- 這個職位為什麼存在；
- 主要服務誰、產生什麼結果；
- 員工目前大致負責什麼；
- 是否有兼任、支援、已不再做或尚未正式接手的工作。

恢復舊文件時，AI 先說明：

- 上次談到哪裡；
- 目前已理解什麼；
- 尚待決定或補訪什麼；
- 建議從哪個焦點繼續。

角色定位只提供方向，不根據職稱套用公版 JD。

### 3.2 廣度盤點：建立「目前已知的工作地圖」

AI 從不同角度協助員工回想工作：

1. 每日、每週的例行工作；
2. 每月、每季、每年的週期工作；
3. 低頻但出錯影響大的正式責任；
4. 監控、檢查、維護與預防；
5. 對外、跨部門與上下游交接；
6. 需要判斷、協調、核准或承擔風險的工作；
7. 緊急、例外與問題處理；
8. 最近新增、已停止、只支援他人或未來構想的內容。

這一步產生的是工作線索、故事、工作邊界假說、Task 候選與暫定責任區域，不要求全部立刻成為正式 Duty／Task。

廣度盤點與深入訪談不是先後通關。當某項工作已值得深入，就可以進入焦點訪談；深入時若發現新範圍，也可以回到盤點。

### 3.3 選擇本輪焦點

AI 根據最新狀態選一個最值得處理的問題。優先考量：

1. 更正、矛盾、本人／他人責任；
2. 會改變 Task merge／split／邊界的未知；
3. 高影響、低頻但重要或高風險工作；
4. 缺主要 outcome、責任或完成標準的 Task；
5. 影響 Duty 分組的缺口；
6. 有必要補證據的 OPKS gap；
7. 其他 coverage 與低風險細節。

AI 應告訴員工：現在談什麼、為什麼現在談、要釐清到什麼程度。

焦點採分級切換，不採「一定問完才換題」，也不追著每個新線索跳轉：

- 與目前工作相關的新資訊，直接吸收到當前分析；
- 不影響當前判斷的新 Task、Duty 或 OPKS 線索，保存到待處理清單；
- 若新資訊會推翻目前 Task 邊界、改變本人責任、揭露重大矛盾或高風險遺漏，AI 應說明原因後暫停並切換；
- 員工明確要求換題時立即尊重，但保留尚未處理的焦點；
- 每次中斷都要保存返回點，之後能說明原焦點談到哪裡、為何中斷、還差什麼。

當目前證據已足以形成 Proposal、確認 `no-op`、留下具體 gap，或以有理由的 unknown／not applicable 暫時停止時，焦點才算暫時收束。這不是永久完成；後續證據仍可重新開啟。

### 3.4 深入一件具體工作

抽象描述優先回到最近一次或代表性的具體事件。訪談可涵蓋：

- 什麼情況觸發；
- 收到什麼輸入；
- 員工本人做了哪些關鍵行動與判斷；
- 哪些由他人、共同或上級處理；
- 產生什麼結果、交給誰；
- 如何知道可以完成、交付或結案；
- 例外、失敗、重工與風險如何處理；
- 這是例行、週期、正式低頻、一次性、過去工作或未來構想。

5W1H 是問題工具，不是必須逐欄問完的表格。問題由當前缺口決定，一次只問一個主要 answer target。

### 3.5 背景保存其他線索

即使正在深入 A Task，AI 仍要辨識：

- A Task 的新證據或更正；
- 可能屬於 A 的步驟、工具、方法或 OPKS；
- 可能屬於既有 B Task 的資訊；
- 可能形成新 Task／Duty 的線索；
- 暫時無法安全分類的內容。

一般情況先保存，不立刻換題；下一個焦點選擇時重新評估。

### 3.6 每輪訪談的核心循環

每輪不是先判斷 Task、再依序跑 Duty 與 OPKS，而是先理解員工的完整回答，再依當輪需要組合方法：

1. 接收完整回答，不限制員工只能回答上一題；
2. 做全域理解，保存來源事實、更正、新線索、矛盾與尚無法分類的訊號；
3. 維持一個前景焦點與共同 work hypothesis／focus anchor；
4. 根據回答內容、當前焦點與仍存在的 gap，按需載入零個、一個或多個分析 Skill；
5. 各 Skill 使用同一批證據形成 typed findings、候選、gap 或重新開啟既有結論的理由，不直接修改 Current JD；
6. 對 Task、Duty、O、P、K、S 的分析結果做共同對帳，處理拆分、合併、重新分組與 linkage 變化；
7. 決定本輪的單一清楚下一步：繼續同一焦點、整理或提出變更、保存旁支線索、切換焦點，或提示已接近可停止狀態；
8. 對員工呈現目前焦點、必要摘要、Proposal 與一個主要問題，不暴露內部 Skill 編排為使用者必須理解的流程。

例如，員工描述某項工作時同時說出主要成果與驗收方式，當輪可一起使用 `task-boundary`、`output` 與 `performance-indicator`；若沒有能力需求的證據，就不載入 `knowledge`／`skill`。若 Indicator 顯示原 Task 包含兩種不同成果，也能回頭提出 Task 拆分。

這是產品的語意循環，不預先規定模型呼叫拓撲。日後可依 eval 實作為單次模型工具循環、先路由再呼叫，或少數受控子分析；不得反過來因框架或呼叫形式改變上述顧問責任。

### 3.7 小段落收束、重整與提案

完成一小段有意義的訪談後，AI 可以整理：

- 現在對工作故事的理解；
- Task 是新增、補充、重疊、需 merge／split，或只是工具／步驟；
- Duty 是否需要建立、改名或重新分組；
- 哪些 OPKS 已有依據、哪些仍有 gap；
- 哪些變更值得提出 Proposal；
- 哪些線索先保留到後面。

不要求每回合都產生 Proposal；`no-op`、繼續追問或只保存線索都是正常結果。

Proposal 採「有意義檢查點」節奏，不採每句回答都要求核准，也不等到整份訪談結束才一次處理：

- 一般補充先更新 Work Model，必要時以白話摘要確認，不立刻跳出正式核准；
- 理解仍不確定時繼續追問，不把猜測過早包裝成正式變更；
- 當證據已足以新增或修改 Task、Duty、O、P、K、S，才形成 Proposal；
- 若結構變更會影響後續訪談方向，例如 Task 拆分、Duty 重組或責任歸屬改變，應優先交員工決定，避免在錯誤假說上繼續深入；
- 員工明確要求修改正式內容時，可以立即形成 Proposal；
- 同一批證據造成多個關聯變更時，應以共同理由整理為同一個審核脈絡，不讓各 Skill 分別跳出互不相干的卡片。

關聯變更採「共同脈絡、依相依性分組」：

- 員工先看到這組建議的共同理由、來源證據與整體影響；
- 可以獨立成立的文字、名稱或 OPKS 候選，允許逐項接受、修改或拒絕；
- 只有必須一起成立才不會破壞結構的操作，才組成不可拆的子決策，例如建立 Duty 並完成必要的 Task reassignment；
- 員工修改任一項後，系統重新檢查剩餘變更是否仍成立，不提交失去前提或留下無效 linkage 的內容；
- 分組依據是 domain dependency，不是由哪一個 Skill 產生，也不把整批不相關的變更綁成全收全退。

#### 3.7.1 Proposal 依「是否改變後續分析前提」分級阻擋（已確認）

不是所有 Proposal 都中斷訪談。阻擋判斷依它是否為目前或後續焦點的語意前提，不只看 action 名稱：

- Task merge／split、Duty 建立或重組、Task reassignment、本人／他人責任與其他會改變分析邊界的結構性 Proposal，若後續問題、OPKS linkage 或 Duty grouping 依賴該結果，先暫停受影響的分析，請員工接受、修改、拒絕或改道；
- 改名、文字潤飾、排序與不改變分析前提的一般 OPKS 補充，可以維持 pending，訪談繼續；
- 「阻擋」只作用於依賴該未決前提的 focus／agenda branch，不封鎖整份文件、其他不相關工作、直接編輯、Proposal review 或匯出決策；
- 員工暫不處理結構性 Proposal 時，AI 保存返回點與 blocked reason，改選不依賴它的焦點；若沒有可安全前進的焦點，才明確提示需要先決定；
- Proposal 解決後，系統重新檢查其下游候選、gap、linkage 與 agenda；不得把 proposal 前的推論直接當成仍然有效，也不得因拒絕而偷偷採用同一假設繼續分析。

UI 與進度投影應說明「哪個分析目前被什麼未決前提擋住」，而不是只顯示一個無法理解的全域 blocked 狀態。

#### 3.7.2 Work Model 採觸發式理解校準，不把每次假說更新變成核准（已確認）

Work Model 是 AI 隨證據持續修正的分析層；員工不需要逐筆審核每一個內部假說變化。但若 AI 長時間在錯誤理解上繼續追問，後面的焦點、Duty grouping、OPKS 與 Proposal 都可能一起偏掉。因此產品需要「理解校準」，但它和正式 Proposal 是兩種不同的互動。

平常的低影響 Work Model 更新可以在背景累積，並在畫面上隨時可查看；只有下列有意義時機才由 AI 主動顯示校準卡：

- 準備收束或切換目前焦點；
- 即將提出結構性 Proposal，或後續問題將依賴某個尚未校準的工作假說；
- 新回答與既有理解矛盾，或涉及本人／他人責任、決策權、低頻高影響工作等高風險邊界；
- 暫停較久後恢復，或 Work Model 自上次向員工顯示後已有重大修訂；
- 員工主動要求查看或修正 AI 的目前理解。

校準卡應以員工看得懂的白話呈現，而不是暴露內部 schema：

- 現在談的是什麼、AI 為何這樣理解；
- 一段簡短的目前理解，必要時列出 Task／Duty／OPKS 關係；
- 可展開的員工原話與 Reference 來源，並清楚區分兩者；
- 仍不確定、互相衝突或尚未訪談的部分；
- AI 建議的下一步，以及這張卡所依據的 Work Model revision。

員工至少可以選擇「正確，繼續」、「直接修正」與「目前不確定／稍後再談」。其語意必須固定：

- 「正確」形成員工確認的來源事件，可提高或補強 Work Model，但**不等於接受正式 JD 變更**；
- 「直接修正」保存新的 durable employee source，由 reducer 修正、反駁或取代相關假說；若因此需要改 Current JD，另行形成 Proposal；
- 「目前不確定」保留明確 gap 或返回點，不得被解讀為肯定或否定；
- 提交時若 Work Model revision 已過期，應重新組裝校準內容，不把對舊理解的回覆套到新狀態。

因此產品不設「核准整份 Work Model」，也不每回合跳 modal。理解校準是防止 AI 假說漂移的可見修正點；Proposal 才是改變 Current JD 的 authority gate。

#### 3.7.3 「目前理解」採常駐投影＋情境式校準卡（已確認）

員工不應只能從長對話猜 AI 目前怎麼理解，也不應被迫在每一輪停下來審核。第一版採兩層互動：

1. **常駐但不打斷的「AI 目前理解」側欄**：跟著目前焦點更新，可收合；窄畫面改成可隨時叫出的 drawer。它是 Work Model 的可讀投影，不是第二份資料、不是核准清單，也不等於 Current JD。
2. **只在 §3.7.2 trigger 發生時出現的校準卡**：預設放在對話流內，不用 modal；只有受未決前提影響的分析 branch 需要阻擋時，才要求先處理。

側欄預設只顯示與員工當前任務有關的高訊號內容：

- 目前焦點、為何現在談這件事，以及「探索中／需要釐清／足以形成提案／受未決前提阻擋」等可行動狀態；
- 2–4 點白話的目前理解，必要時顯示 Task／Duty／OPKS 關係；
- 最重要的未確定、矛盾與尚未訪談項目，超過上限只顯示數量並可展開；
- 本輪先保存、稍後再談的新線索或其他 Task；
- 可展開的來源與最後更新時間，員工原話和 Reference 必須分開；
- 一個隨時可用的「修正目前理解」入口。

不要顯示沒有經過產品驗證的 LLM 數字信心或假精確的完成百分比。改用有明確資料語意的標籤，例如「員工已確認」、「依員工說法暫定理解」、「只有 Reference、尚未向員工確認」、「來源矛盾」與「尚未訪談」。最後更新也不得偽裝成最後確認。

校準卡預設只顯示**自上次校準後有意義的變化**及其影響，不重複整份 Work Model。它至少要說明：

- AI 新增、修正或不再採用哪一項理解；
- 依據哪些員工原話或 Reference，以及為何現在需要確認；
- 若不處理，哪個下一步、Duty grouping、OPKS 或 Proposal 會依賴它；
- 「正確，繼續」、「直接修正」、「目前不確定／稍後再談」三種固定動作。

一般焦點切換、久後恢復或大幅修訂屬 soft checkpoint：員工可略過、稍後處理，AI 保存未校準狀態與返回點。矛盾、高風險責任邊界或結構性 Proposal 的必要前提屬 branch-blocking checkpoint：只暫停依賴它的分析，不封鎖整份文件。相同內容未變時不得重複跳卡；相關變更應合併呈現，員工主動要求則不受節流限制。

員工修正後，介面要立即回報「已更新什麼、哪些後續分析會重算、Current JD 是否仍未改變」，並同步刷新側欄。這是對修正效果的可見回饋，不是揭露模型 chain-of-thought；解釋只提供來源、重要推論與影響。所有 action payload 都視為不可信輸入，由 server 依 document、revision、generation／read-set 與 domain invariant 驗證。

### 3.8 O／P／K／S 按需漸進分析

不需要等 Task 已穩定、已被員工接受或已進入 Current JD，才開始看 O／P／K／S。只要目前的工作故事、Work Unit 或 Task hypothesis 已出現足以分析某一軸的證據，顧問就能按需載入該 Skill；沒有需要時不載入，也不是每回合都分析 OPKS。

方法可拆成：

1. `task-boundary` Skill：判斷這是 Task、步驟、工具、他人工作、既有 Task 的補充，或仍需追問；
2. `duty-grouping` Skill：從目前 Tasks／工作假說找共同目的、責任與分組，也能建議改名或重組；
3. `output` Skill：辨識實體交付、服務結果、決策或狀態改變；
4. `performance-indicator` Skill：辨識可觀察的行為、結果、條件與標準；
5. `knowledge` Skill：由實際工作、判斷、規則與概念需求形成 K 候選；
6. `skill` Skill：由實際操作、分析、協調、溝通、判斷與解題行為形成 S 候選。

這些 Skill 可獨立載入，也可在同一輪組合。例如一段具體故事可能同時需要 `task-boundary`、`output` 與 `performance-indicator`；若員工談到關鍵判斷依據，才再載入 `knowledge`。Skill 組合是 context／prompt 最佳化，不是把一個完整工作拆成互不相干的答案。

各分析方向必須雙向校正：

- O 顯示兩個不同主要結果時，Task 可能需要拆分；
- P 無法共同描述時，Task 邊界可能太粗；
- K／S 只支持工作的一部分時，可能揭露不同責任；
- Duty 分組無法解釋共同目的時，可能需要重組；
- Task／Duty 改變後，既有 O／P／K／S linkage 需要重新檢查。

因此需要的是一個共同的 evolving work hypothesis／focus anchor，不是「先完成 Task 再跑 OPKS」的階段門。證據不足時，對應 Skill 產生具體 gap，加入後續訪談議程；有足夠證據時才形成候選。

不得直接問「你需要什麼能力」後照單生成 K/S；應優先問員工實際怎麼做、判斷什麼、出錯會怎樣，再形成候選讓員工否決、修改或接受。

不是每個欄位都必須有內容。操作型 Task 可沒有獨立有形 Output；員工不知道、不適用或已有理由無法取得的內容要誠實保留，不為完整表格而補造。

### 3.9 Reference coverage challenge

在已經有員工工作模型後，才以少量、按需的公版資料做 coverage challenge：

- 是否漏掉常見但員工尚未談到的責任；
- 是否有可以追問的 Output、Indicator、K/S 方向；
- 員工工作與參考職業內容是 match、partial、no-match 或 conflict；
- 是否需要中立追問，而不是直接採用公版答案。

公版內容只產生參考候選、問題或差異，不自動成為員工的工作事實。

### 3.10 收尾與匯出

當主要範圍大致收束，AI 做最後反方檢查：

- 是否被少數精彩事件主導而漏掉例行工作；
- 是否漏掉低頻高影響責任；
- 是否誤收過去、他人或一次性工作；
- Task 是否過度拆分、合併或重複；
- Duty 分組是否仍可合理解釋；
- OPKS 是否有工作行為支持；
- 是否因公版而加入員工沒做的內容；
- 是否仍有會顯著改變 JD 的矛盾或未知。

系統可以建議「本輪可結束」或「目前已足夠進入最後檢查」，但員工決定何時停止與匯出。

### 3.11 員工視角端到端驗收情境

以下情境不是固定腳本，而是用來驗收產品體驗。假設員工是製造業採購專員；員工不會看到內部 Skill 名稱與編排。

1. **先建立工作地圖。** AI 請員工用自己的話說明一個月內主要工作，不要求 JD 用語。員工提到請購下單、供應商交期、缺料協調與偶爾整理庫存報表後，AI 顯示「目前已知四個工作範圍」，並說明先深入請購到下單的原因。
2. **專注但不漏線索。** 員工在下單故事中順帶提到新供應商評估與替代料；AI 把兩者顯示為稍後處理線索，仍用一個主要問題釐清下單責任，不立即換題。
3. **先理解，後提案。** AI 經數輪釐清主管核准邊界、採購單內容與供應商回覆，準備切換焦點前先用校準卡說明目前理解；員工可直接修正「交期只是追蹤，不是我決定」。修正先更新來源與 Work Model，證據足夠後才提出 Task、Output 與 Indicator 候選；第一句補充不會立即跳正式核准卡。
4. **員工保留 authority。** 員工指出「不是每次都要比價」，AI 修正 Task 後再讓員工接受。若目前只有一個 Task，可以先不建立 Duty。
5. **重大責任先澄清。** 訪談缺料處理時，員工說「決定哪些工單先拿到料」。因這可能改變正式權責，AI 暫停原焦點，確認員工只是提出建議、最後由生產主管決定，再回到原返回點。
6. **結構隨證據演化。** 當已有下單、缺料協調、供應商績效三項 Task，AI 可提出兩個 Duty 與 Task reassignment 的結構變更組；員工能修改 Duty 名稱。可獨立成立的 K／S 候選仍可逐項決定，不因接受 Duty 就被迫全收。
7. **Reference 只做補漏。** AI 在已有員工工作模型後，以公版資料詢問「供應商稽核是否為正式責任」。員工回答由品保負責後，系統記錄 no-match，不建立假的 Task。
8. **進度可解釋。** 畫面顯示目前焦點、為何現在處理、已足夠／訪談中／尚未深入／待決 Proposal／OPKS gap／已確認不屬於本人與稍後線索，而不是顯示假精確百分比。
9. **完成仍由員工決定。** AI 說明為何目前已足夠、仍缺什麼、繼續最可能改善哪裡。員工可以繼續、暫停或看過缺口後強制匯出；系統不補造答案、不偷收 Proposal，也不隱藏未歸類 Task。

此情境的驗收效果是：AI 主動帶路，員工不用理解分析方法；每輪知道正在談什麼與為什麼；旁支線索不遺失；正式內容只在有意義檢查點由員工決定。

## 4. 焦點與進度 v0.1

### 4.1 焦點有兩層

本輪訪談目標示例：

> 釐清「處理客戶申訴」的邊界，判斷它是一個 Task，或需要拆成受理、調查與回覆。

當前問題示例：

> 最近一次收到申訴時，從收到訊息到結案，你實際做了哪些事情？

員工應能看到：

- 焦點名稱；
- 為什麼現在處理；
- 這個焦點還差什麼可以暫時收束；
- AI 下一步建議；
- 訪談中另外發現但先保留的線索。

### 4.2 進度不用單一百分比

因為新 Task、Duty 與 gap 可能持續出現，總分母未知。進度應呈現為「目前已知的工作地圖」：

- 已足夠；
- 訪談中；
- 尚未深入；
- 待補訪；
- 待員工決定；
- 已保留未知／不適用／暫不處理；
- 重大矛盾或結構問題。

Task、Duty、OPKS 與 Proposal 的狀態不能全部壓成一個總分。例如：

> 目前已知 11 個工作範圍；6 個已足夠、2 個正在深入、2 個尚未深入、1 個有重大矛盾；另有 3 個 OPKS gap 與 2 項 Proposal 待處理。

所有數字都應標明「目前已知」，並可展開看到具體內容與原因。

### 4.3 三種不同的停止感

介面與 AI 說法要區分：

1. 本輪可以先停：已有自然停點，下次可恢復；
2. 訪談目前已足夠：主要 coverage 與高影響缺口已處理或留下理由；
3. 可以匯出：匯出檢查已列出所有剩餘缺口；若仍有缺口，員工可明確選擇強制匯出。

### 4.4 「目前已足夠」採混合判斷

不得只靠固定題數／分數，也不得只靠 LLM 一句主觀宣告。系統以可檢查證據打底，由 LLM 做整體專業判斷與白話解釋，最後由員工決定停止或繼續。

判斷面向至少包含：

- 工作範圍：主要、週期性、低頻高影響工作與責任邊界是否大致盤點；
- 重要工作：本人責任、主要結果、完成判準與關鍵例外是否足以形成可信描述；
- 結構：是否仍有可能顯著改變 Task merge／split 或 Duty 分組的重大矛盾；
- OPKS：重要 gap 是否已分析、排入待補訪，或有 unknown／not applicable／暫不處理等明確理由，而不是要求欄位全部填滿；
- 員工決策：是否仍有可能大幅改變 Current JD 的 Proposal 尚未處理；
- Reference challenge：是否做過當下有必要的 coverage 檢查，且沒有把公版內容誤認為員工事實。

只有當沒有未處理的重大問題，而且剩餘缺口已清楚呈現、預期不會推翻整體 JD 時，AI 才建議「目前訪談已足夠」。同時必須說明：為什麼足夠、還缺什麼、繼續訪談最可能改善哪裡。員工仍可繼續、暫停或強制匯出；新證據出現後也可重新開啟。

## 5. 從既有研究回查後的修正

### 5.1 Task：焦點不等於 Task 抽取

依 [`Task Discovery 深入研究`](2026-07-25-professional-consultant-r1-task-discovery-deep-research.md)與[`Task 邊界研究`](2026-07-28-task-boundary-merge-split-and-identity-research.md)：

- 員工訊息、Source Claim、未映射線索、故事、Work Unit 與 Task Candidate 是不同層次；
- 一個故事可支持零到多個工作假說，多個故事也可能支持同一 Task；
- Task 要有 meaningful outcome、本人目前責任、可指派／查核與相對穩定性；
- 工具、方法、單一步驟、過去工作、他人工作與一次性支援不得自動升格；
- 每輪沒有新 Task、只補證據或 `no-op` 是正常結果。

因此本流程的焦點可以是故事、責任邊界、矛盾、coverage 或 OPKS gap，不一定每次都以既有 Task 為起點。

### 5.2 Duty：可提早分析，但保持為可變動假說

依 [`專業顧問流程最終反方審查`](2026-07-25-professional-job-analysis-consultant-process-final-red-team.md)與[`iCAP 欄位標準`](2026-07-13-ai-redesign-raw-icap-field-standards.md)：

- 初期責任區域與已出現的工作線索足以啟動 `duty-grouping` Skill，但形成的是可變動 Duty hypothesis，不是固定盒子；
- Duty 可隨 Task／Work Unit 增加，依共同 purpose、責任、outcome、workflow stage、服務對象或領域動態整併；
- Duty 需要自己的候選、來源、改名、重分組、merge／split 與 Proposal 生命週期，不能只在匯出時臨時分組；
- iCAP 要求主要職責／任務粒度盡量一致、以成果或功能表達，但沒有固定條數下限。

因此「一開始順便分析職責」是合理的；限制只是不能把早期 Duty hypothesis 當作後續 Task 的不可變分類。

### 5.3 O／P／K／S：方法可獨立載入，語意仍互相依賴

依 [`OPKS 設計裁決`](2026-08-01-opks-design-decisions-research.md)、[`OPKS 漸進蒐集`](2026-08-04-opks-progressive-elicitation-research.md)與[`OPKS gap 再分析研究`](2026-08-06-opks-gap-reanalysis-blocking-research.md)：

- 既有「以單一 Current JD Task 為一次 OPKS operation」是控制輸出量、prompt/schema 大小與 durable failure boundary 的現行實作決策，不應升格成產品流程必須等待 Task 穩定的證據；
- 未來可把 O、P、K、S 拆成各自的 Skill，根據當輪證據與焦點按需載入；Skill 是否獨立，不預先決定是否另開模型呼叫；
- 正式資料關係仍是 O/P 綁 Task，K/S 是文件層項目並與相關行為指標／Task 建立多對多 linkage，A 是文件層；但分析期間可以先連到 Work Unit／Task hypothesis，形成 Proposal 前再完成 identity reconciliation；
- K/S 應由實際 Task 與行為證據反推，不直接要求員工自列能力；
- 是否需要某個分析 Skill，可由可檢查的 policy、當前 focus／gap 與模型判斷共同決定；員工不需要按「產生 OPKS」；
- 證據不足要保存具體 gap，agenda 一次選一題；unknown／not applicable 可以成為有理由的終止；
- OPKS 可能揭露 Task outcome 或邊界有問題，必須允許回頭修正 Task。

仍需保留的語意依賴是：O／P 必須能連回正在分析的工作；K／S 必須連回工作行為／Indicator，不能因 Skill 拆開就各自生成漂亮但無支持的清單。

現行研究仍有一項已知風險：active gap 可能讓後期 Task 的再分析出現尾端衰減。2026-08-06 的研究因缺少 10–15 回合真人資料而暫不翻案；未來流程評測必須量測 gap 開啟率、關閉率與 late-discovered Task 的產出，不能假設現行 gate 已是最優解。

### 5.4 AFFiNE 階段化需求稿：保留可見控制，不採剛性階段門

2026-08-12 逐段讀取 owner 提供的 `職務分析_AI_階段化狀態機需求稿 _ AFFiNE.html`。它是有價值的 stakeholder 草稿，但不是本 repo 權威，也不能覆蓋既有研究與已確認的產品流程。

整合裁決：

| 類別 | 處理 | 理由 |
|---|---|---|
| 單一主要 AI、明示目前目標／剩餘項目／下一步 | 保留 | 提升焦點、進度與可恢復性，不需要人格化多 Agent |
| 待訪談清單的來源、狀態、最近更新、暫停／恢復 | 保留並擴充 | 改為跨 Story、Work Unit、Task、Duty、OPKS gap、矛盾與 Proposal 的 agenda projection，不建立第二份 authority store |
| 候選區與正式 JD 分離；可接受、修改、拒絕、退回補訪 | 保留並對齊 Proposal seam | 符合員工 authority；Proposal 採有意義檢查點與 dependency-aware changeset |
| 右側 JD 可直接編輯、排序與重新啟動訪談 | 保留 | 員工直接編輯與 AI Proposal 都回到同一 authority seam |
| Reference 不直接定義員工工作 | 保留並改成 blind-first | 員工可主動搜尋／略過；AI 預設在已有 employee-first work model 後才做 just-in-time coverage challenge |
| 「骨架／Duty／Task／OPKS」狀態機 | 改寫 | 僅作可見的 focus／attention mode 與 durable checkpoint，不限制當輪可載入哪些 Skills，也不是資料生命週期通關門 |
| 完成條件與狀態提示 | 改寫 | 從固定階段完成改成 focus sufficiency、global readiness、具體 gap 與 terminal reason |
| 新線索先保存、不任意打斷 | 改寫 | 一般線索先停放；會推翻 Task 邊界、本人責任或重大結論者必須先澄清，並保存返回點 |
| Task 必須先有 Duty、禁止孤立 Task | 不採用 | 分析期間 Task 可暫無 Duty；Duty 是隨證據動態重組的假說與正式實體 |
| 只有已進 JD 的 Task 才能深入或分析 OPKS | 不採用 | Story、Work Unit 或 Task hypothesis 出現足夠證據時即可按需分析 O／P／K／S |
| AI 不得跨階段深入提問 | 不採用 | 與全回答理解、按需 Skills 及 OPKS 反向修正 Task 的需求衝突 |
| O＝工作行為、P＝工作產出 | 更正後才可使用 | iCAP 正確對位是 O＝工作產出、P＝行為指標；P 是成功完成 Task 的可觀察標準，可包含有依據的情境、行為、結果、條件與程度 |

主流架構佐證指向同一結論：Anthropic 建議從簡單、可組合的單一 agent pattern 開始，並以 Skills progressive disclosure 和最小高訊號 context 控制複雜度；OpenAI 現行 guidance 建議精簡 prompt、只暴露相關 tools，並明定 autonomy／approval boundary；Google ADK 2.0 則把 deterministic workflow 與 adaptive agent 組合，將業務規則、HITL 與可靠 transition 留給程式，把模糊語意判斷留給模型。

因此本產品採用的不是純自由 Agent，也不是純階段狀態機，而是：

> 員工看得見明確焦點、議程、進度與核准點；AI 在這些受控邊界內動態理解完整回答、選擇 Skills 並調整訪談；Current JD authority、Proposal commit、資料 invariant 與不可跳過的核准由 deterministic application control 保證。

## 6. 「方法知識」與「公版 Reference」必須分開

owner 提到「公版 RAG 讓 LLM 知道可以問什麼方向」，需拆成兩類：

### 6.1 從一開始可用：職務分析方法知識

例如：

- 如何辨識 Task、步驟、工具與他人工作；
- 如何做廣度盤點與具體事件訪談；
- 如何判斷 merge／split；
- 如何形成 Duty；
- 如何從行為與產出分析 OPKS；
- 如何停止、避免引導與做反方檢查。

這些是顧問方法、rubric 或未來 Skill，不是特定職業答案。第一版 Skill 候選至少可包含：

- breadth／story interviewing；
- task boundary／merge／split；
- duty grouping；
- output；
- performance indicator；
- knowledge；
- skill；
- reference challenge；
- completion／red-team review。

Skill 採 progressive disclosure：平時只保留短名稱與用途，當輪命中才載入完整方法。這解決的是方法 prompt 膨脹；當輪需要哪些員工原話、工作狀態與 Reference，仍是 Context Engine 的另一個問題。

### 6.2 後段按需使用：職業／產業公版內容

例如 iCAP、O*NET、公司 SOP、表單、既有 JD 或產業資料。它們可以：

- 協助回憶；
- 做 coverage challenge；
- 提供可能追問方向；
- 提供術語與來源；
- 比較 match／partial／no-match／conflict。

它們不得：

- 因職稱直接定義 Task／Duty；
- 取代員工工作故事；
- 自動寫入 Current JD；
- 把「公版常見」說成「員工本人負責」；
- 一次整包塞入每輪 context。

技術上是否使用向量檢索、hybrid search、MCP 或其他 RAG framework，等產品流程與來源政策核准後再決定。

## 7. 記憶責任、權威分層與 Context Engine v0.2

本節先定義產品必須記住哪些不同性質的內容，以及誰有權改變它們；不預先決定資料表數量、向量資料庫、framework 或實際 storage topology。

### 7.1 來源記憶：員工真正說過什麼

保存員工原話、來源回合、時間、附件／引用位置，以及後續更正、否認或撤回的關係。它是回答「這項理解根據哪一句話」的 evidence layer。

- 摘要不得覆寫或取代原始來源；
- AI 不得改寫員工原話後冒充 source；
- 更正保留前後歷史並標示目前效力，不以刪除舊句偽造一致性；
- 後續所有 Work Model、Proposal 與正式內容應可追溯到來源或明確的員工直接編輯。

### 7.2 工作模型記憶：AI 目前怎麼理解

保存 Story、Work Unit、Task／Duty hypothesis、O／P／K／S 候選、linkage、gap、矛盾、未映射線索與 retired candidate。它是可變動的分析層，不是 Current JD。

- AI 可以依新證據新增、修正、合併、拆分、重新連結或淘汰假說；
- 每項假說要保留穩定 identity、支持／反對證據、信心理由與生命週期狀態；
- `employee_denied`、過去工作、他人工作、一次性支援等 retired reason 不應被一般檢索重新當成 active candidate；
- Work Model 的變化可以影響焦點與 Proposal，但不得直接改變正式 JD。

### 7.3 正式文件記憶：員工已授權的 Current JD

只包含員工直接編輯，或經 Proposal 決策後由 authority commit seam 寫入的正式內容。

- Current JD 是產品文件真相；
- AI 不能因摘要、重新分析、模型更換或 Reference 命中而直接覆寫；
- 新證據可產生挑戰或修改 Proposal，但舊內容在員工決策前仍維持正式效力；
- 正式項目與其決策／來源 lineage 應可追溯。

### 7.4 訪談流程記憶：現在為何問、之後要去哪裡

保存目前焦點、選擇原因、完成目標、返回點、待處理 agenda、已停放線索、focus gap、待決 Proposal、進度投影與停止理由。

- 暫停或切換後能自然恢復，不靠模型猜測上次談到哪裡；
- agenda 是由其他權威物件與 workflow metadata 形成的工作投影，不成為第二份 JD 或第二份 Work Model；
- AI 預設選下一個最高價值焦點，員工可覆寫；
- 已完成、已拒絕、已退休與 terminal unknown／not applicable 必須有理由，避免無限重問。

### 7.5 Reference 是獨立知識來源，不是第五種員工事實

iCAP、O*NET、公司 SOP、表單、既有 JD 與產業資料保存自己的來源、版本、片段與 citation。它們可以支持 coverage challenge、術語與追問，但不能和員工原話混成同一 evidence authority，也不能因檢索相關度高就直接提高為工作事實。

### 7.6 摘要、embedding 與模型 reasoning 都不是 authority

- 對話摘要、焦點摘要與壓縮筆記是可重建的 context artifacts；
- embedding、向量相似度與 rerank score 是檢索索引，不是事實真偽或員工認可度；
- provider 保存的 conversation state／reasoning state 可提高連續性，但不能取代本地持久化的來源、Work Model、Current JD 與 workflow checkpoint；
- 模型或 framework 可以替換，只要上述產品權威與 lineage 不被改變。

每輪 Context Engine 可以從各層選取「最近必要對話＋焦點相關原話＋相關工作假說＋已接受內容＋當前 gap／Proposal＋命中的 Skill／Reference」，但完整保存與當輪傳入是兩件不同的事。

### 7.7 Context Engine 的第一輪權威資料結論

截至 2026-08-12，OpenAI、Anthropic、Google 與 LangGraph／LangChain 的官方資料沒有提供一份可直接套用到職務分析的「最佳 context 配方」，但共同支持以下方向：

- context 是有限注意力資源；可用窗口變大，不代表把完整歷史放入每輪會更準；
- 長流程應把可恢復的完整 session／event log 與本輪模型可見 context 分離；
- 業務進度與權威狀態應明確持久化，不由模型從聊天歷史猜測；
- 精簡且任務相關的 prompt、tools、Skills 與資料通常比全部常駐可靠；
- compaction、summary、provider conversation state 與長期 memory 可提高連續性，但都不能取代原始來源與業務 authority；
- context selection 沒有通用最佳值，必須以本產品的長訪談、修正、跨題線索、Task／Duty／OPKS 與 Reference 情境評測。

這些來源也形成一個重要限制：框架可以提供 session、checkpoint、store、summary middleware、retrieval hook、tracing 與 token accounting，但無法自行知道「哪句員工原話是必要證據」「哪項更正優先於舊說法」或「Reference 何時不得混入員工事實」。這些仍是 Caliburn 的產品與 domain policy。

外部證據的可轉移性也有限：Anthropic 的主要案例包含 coding／research agent，Google 的長流程案例是 HR onboarding，Contextual Retrieval 的量化資料集也不是繁中職務訪談。目前沒有可信公開 benchmark 證明任何 Context framework 或固定配方會直接提高專業職務說明書品質；本節只能把共同架構模式轉成待驗證假說，不能把別的產品結果當成 Caliburn 成效。

### 7.8 三種 Context 組裝方案

#### 方案 A：完整歷史／provider state 優先

每輪延續 provider conversation、完整 message history 或 provider compaction，讓模型自己從長 context 找重點。

- 優點：初期程式少、對話自然、可快速建立 baseline；
- 缺點：舊 token 仍可能持續計費，長歷史會引入 context pollution；opaque compaction 不可檢查；provider lock-in 高；不能保證重大更正、權威邊界與跨題線索被正確使用；
- 結論：只適合作為連續性輔助與比較 baseline，不作產品唯一記憶或權威來源。

#### 方案 B：完全由程式預先組好固定 ContextPack

應用程式依固定 lanes、配額與排序一次選完，模型不能再查其他內容。

- 優點：成本、隔離、重播與測試最容易控制；
- 缺點：規則難預知某句舊話何時重新重要；固定 lane／比例容易隨模型進步而過時；選漏後模型沒有補救能力；
- 結論：適合 authority floor、document scope 與不可省略項，不適合承擔全部語意相關性判斷。

#### 方案 C：可恢復記憶＋必要核心＋受控按需檢索（推薦候選）

完整來源與狀態留在本地可恢復 store；應用程式先提供一個小而可靠的必要核心，再以結構化關聯、lexical／semantic retrieval 形成候選；模型若仍需要更多資料，只能透過 document-scoped、read-only 工具按需取得。

- 優點：保留 authority、來源與重播能力，又讓模型能處理程式無法預列的語意關聯；可替換模型與檢索實作；
- 缺點：需要明確工具契約、budget 與停止規則；正式 context eval 後置期間，若工具設計不良，較可能到人工使用時才發現漏查、重查或追逐無關內容；
- 結論：最符合本產品「前景專注、背景全域吸收、長期可恢復、員工核准」的需求，先作研究候選，不直接授權 production 實作。

推薦方案不是「都交給模型」。程式仍決定 scope、authority、必帶資訊、可用工具、token 上限與降級；模型只在這些邊界內判斷還需要讀什麼。

### 7.9 每輪的白話 Context 流程

1. **保存，不等於傳入**：先把本輪員工原話、AI 回應、tool event、Work Model 變化與 workflow event 完整保存；不得先摘要才保存。
2. **建立不可省略核心**：放入精簡 authority 規則、本輪 operation／focus／完成目標、員工當輪完整文字回答、焦點相關 Current JD／Work Model、會影響本輪判斷的最新更正／矛盾／待決 Proposal。
3. **走直接關聯**：先依 document、穩定 ID、Task／Duty／OPKS linkage、source receipt、speaker、generation 與狀態查詢，不先用向量猜。
4. **找較遠候選**：對較早原話與未映射線索使用 lexical 與 semantic retrieval；結果保留 speaker、原回合、entity、前後片段與 authority metadata，再視需要 rerank。
5. **按需載入方法**：平時只讓模型知道可用 Skill 的名稱與用途；命中 task-boundary、duty-grouping、O、P、K、S 或 Reference challenge 時才讀完整方法。
6. **允許受控補查**：若 context 顯示仍有未載入來源，模型可呼叫唯讀工具取得特定 Task 的原話、相關 Duty／OPKS、修正歷史或 Reference；不得跨 document，也不得以工具結果直接寫 Current JD。
7. **計數、裁切與降級**：依實際 model profile 計算 tokens，先保留 output／schema／必要 authority；超預算時先移除重複工具輸出、低價值 Reference 與較遠候選，不靜默刪除當輪回答、最新更正或 blocking contradiction。
8. **留下 Manifest**：記錄實際載入、未載入、選取理由、來源 hash／generation、Skill／tool、tokens、model profile 與輸出 lineage，供 replay、除錯與 eval。

附件、長文件與大型 Reference 不保證整份放入；當輪員工文字回答原則上完整傳入，附件則以可追溯片段或按需工具讀取。若單一回答本身超過模型安全預算，系統必須明示分段或 context budget 問題，不可無聲截斷。

### 7.10 必帶、候選與按需三層

| 層級 | 內容 | 誰決定 | 可否因 budget 直接省略 |
|---|---|---|---|
| 必帶核心 | authority、operation／focus、當輪回答、焦點 target、最新有效更正、blocking contradiction、相關待決 Proposal | deterministic application policy | 不可；不足時明確失敗或分段 |
| 候選 context | 較早原話、相鄰 Task／Duty／OPKS、open gap、未映射線索、少量近期對話 | 結構化 filter＋retrieval＋rerank | 可依可解釋順序降級 |
| 按需 context | 更遠來源、完整歷史片段、額外 Skill、Reference、低頻 lineage | 模型經受控唯讀工具請求，程式驗 scope／budget | 可拒絕並回報理由 |

第一版不先規定例如「Evidence 40%、Recent 20%」的固定比例。不同 operation、模型窗口、輸出 schema 與資料密度不同；開發期先使用可設定、可觀測、可回退的保守上限，不為了等調參資料阻塞成品，成品完成後再由 eval 決定各類 floor／ceiling。

### 7.11 檢索不是只有向量搜尋

推薦候選順序：

1. deterministic relational／graph lookup：穩定 ID、linkage、speaker、generation、狀態與 source receipt；
2. lexical retrieval：保留職稱、術語、表單名、系統名與員工用字的 exact match；
3. semantic retrieval：找不同措辭但語意相關的舊故事與線索；
4. context expansion：補上 speaker、原回合、相鄰句、所屬 Task／Duty 與修正關係；
5. rerank／budget selection：只把最高價值且不重複的候選送入模型。

Anthropic 的 Contextual Retrieval 實驗中，contextual embeddings 加 BM25 在其資料集將 top-20 retrieval failure 由 5.7% 降至 2.9%；這只能證明 hybrid retrieval 值得成為實驗候選，不能證明相同 chunk、top-k、embedding 或 reranker 對 Caliburn 最佳。若第一版為完成產品而先採用，必須包在可替換設定後、保留檢索與來源紀錄；繁中長訪談 domain eval 延至可用成品完成後再做。

Reference 必須使用獨立 namespace／lane 與 source label。員工來源與公版內容即使語意相似，也不得因去重而合併；semantic score、rerank score 與 memory confidence 都不是 authority。

### 7.12 Compaction、provider state 與 cache 的位置

- 原始 session／event、員工原話、Current JD、Work Model 與 workflow checkpoint 由本地持久層保存；
- provider `previous_response_id`、persisted reasoning 或 conversation state 可作短期連續性優化，不能成為唯一 resume 依賴；
- provider／framework compaction 可減少長會話 context，但 opaque 或生成式摘要只能當可重建 artifact；
- prompt cache 只優化穩定前綴，例如精簡 authority、固定 schema 與 Skill metadata；焦點、員工回答、檢索結果放在後段；
- 使用 provider 原生 token counting 或經 conformance 驗證的 tokenizer，在送出前估算，在回應後保存實際 usage；
- 換 provider／model 後可以重建 ContextPack；不得因 provider reasoning state 遺失而失去來源、正式內容或訪談進度。

### 7.13 框架能接手與不能接手的部分

| 能交給成熟框架的通用能力 | Caliburn 仍須保留 |
|---|---|
| checkpoint／resume、thread state、interrupt／HITL、retry boundary、streaming、tracing | Current JD authority、generation／read-set、proposal commit seam |
| model interface、structured output、tool schema、dynamic prompt／middleware hook | ContextPolicy：scope、必帶核心、來源資格、最新更正與 retired exclusion |
| session／store 介面、summary middleware、retrieval connector、token／usage telemetry | 員工原話與 Reference 分權、quote anchor、evidence lineage、ContextManifest |
| Skills loader／tool discovery、按需載入機制 | Task／Duty／OPKS 專業方法、Skill 版本核准與觸發語意 |

LangGraph／LangChain 目前提供的 persistence、HITL、Store、middleware 與 tracing 與本需求相容；OpenAI Agents SDK 也有 session、compaction 與可序列化 HITL；Google Agent Platform 提供 Sessions／Memory Bank。它們證明目前已有多個由主流團隊維護的通用 plumbing 候選，不代表候選在 Caliburn 已驗證成熟，也不代表本產品應同時採用或直接交出 authority。Google 的託管 Memory Bank 也不符合 current-only 本機產品的預設部署邊界，現階段只學習其「session、memory、explicit state 分離」架構。

框架選型必須後於這份產品 policy，並以小型 conformance spike 驗證；不得為了使用框架而建立第二份 JD、第二份 Work Model 或另一條 AI 直接寫入路徑。

### 7.14 正式 Context eval 後置；開發期只留最小安全網

Owner 已於 2026-08-12 裁示：時間優先，先完成可用的端到端成品，再建立正式 eval。成品完成前不另開以下工作：

- framework-neutral eval dataset、golden transcript 與人工標註計畫；
- A／B、context ablation、LLM-as-a-judge、Pydantic Evals／Ragas runner；
- required-context recall、品質、成本與延遲的量化 release gate；
- 為了建立 baseline 而延後已可垂直交付的產品能力。

開發期仍保留下列最低安全網；它們是一般工程正確性與未來可回溯性，不是正式 eval 專案：

- 現有 unit／integration／contract tests 與 domain invariants 繼續通過；
- authority、document isolation、proposal commit seam、generation／read-set 等 deterministic safety 不得因趕工取消；
- 每個垂直切片做一次簡單人工 happy-path／resume／approval smoke check，不建立評分資料集；
- ContextManifest 或等價紀錄保留 model／prompt／Skill／tool／source refs／tokens／結果 lineage，避免成品後無法重播；
- 新框架只做它要取代之介面的 conformance test，不比較模型回答分數。

可用成品完成後，再建立下列正式 Context eval 情境：

至少建立下列長訪談情境：

- 員工在後段更正前段說法；
- 回答焦點 Task 時順帶說出新 Task；
- 新線索迫使 Duty regroup；
- Task 尚未穩定時已出現 O／P／K／S 證據；
- 同一術語由員工與 Reference 提供不同內容；
- 訪談暫停數日後恢復；
- 長歷史中同時存在 active、rejected、retired 與 superseded candidate；
- context 超預算，需要降級但不可丟掉 correction 或 authority。

屆時比較方案 A、B、C 及其變體，至少量測：

- required-context recall；
- irrelevant-context precision／duplicate rate；
- correction／contradiction carry-over；
- off-focus clue capture；
- false authority contamination；
- quote／source attribution correctness；
- 下一題與目前 focus／gap 的相關性；
- proposal 正確性與員工 edit／reject 率；
- input／output／reasoning tokens、cache hit、額外 tool call、延遲與成本。

正式 eval 啟動後，不能只用「token 變少」判定成功。接受候選的最低條件是：domain 品質與 required evidence 不劣於 baseline、authority 錯誤為零，且成本／延遲至少一項有可重現改善。具體門檻屆時依可用成品與真實操作形狀建立，不回頭阻塞第一版開發。

### 7.15 本節仍未決定

- 每種 operation 的確切 token floor／ceiling；
- 是否第一版就使用 embedding、哪個 embedding／reranker 與 top-k；
- 是否增加獨立的 model-based context planner call；
- 主要 runtime 採 LangGraph、OpenAI Agents SDK、PydanticAI 或薄型自有 orchestration；
- provider conversation state、compaction、prompt cache 的啟用條件；
- ContextRequest／ContextPack／ContextManifest 的最終 schema 與資料表。

上述第一版實作細節先由 current-only 邊界、可逆設定、介面 conformance 與人工 smoke 決定，不由「大廠有提供」直接決定；模型品質、最佳參數與成本調優延至可用成品完成後，以長訪談 eval 與實際數據收斂。

### 7.16 Durable input、模型語意結果與業務狀態分離（已確認方向）

Owner 於 2026-08-12 確認：員工回答即使遇到 AI 失敗也必須保存，之後以同一個 input event 重試分析。這項裁決同時收斂一輪處理的責任邊界：**來源事件、模型語意結果、業務狀態與稽核不是同一個 LLM output。**

建議的邏輯順序是：

```text
① application 保存 immutable employee input event
② Context Engine 依 document／focus／authority 組裝本輪 context
③ 主要顧問按需載入 Skills 與 document-scoped read-only tools
④ 模型提交 typed semantic result
⑤ application 驗證、對帳並以 reducer 形成 Work Model／agenda／Proposal 變化
⑥ derived state 與成功的 consultant turn 原子提交後才回給員工
⑦ Proposal 仍須等員工 accept／edit／reject，才可經 authority seam 改 Current JD
```

若 ③–⑥ 任一步失敗：employee input event 保留為 durable source，記錄可重試的 processing failure；Work Model、agenda、Proposal、Current JD 與成功 consultant turn 不得出現半套變更。重試沿用同一 input event／operation identity，避免來源重複與重複付費造成不同結果競爭。

模型只負責必須由語意判斷產生、且有真實下游消費者的內容。邏輯上包含：

1. source-anchored findings：本輪明示內容、更正、矛盾、新線索、候選與 gap；
2. change intents：對 Work Model 或 Proposal 的新增、修正、合併、拆分、重新分組、連結或淘汰建議；
3. next move：維持／切換焦點、reason codes、停止建議與最多一個主要問題；
4. employee-facing reply：簡短承接、必要摘要與問題，不得宣稱尚未提交的正式變更已生效。

上述是**語意表面**，不要求第一版必須把四類塞入一個巨大 JSON。可以由一次 bounded tool loop、少數按需 specialist result 或一個 final submit contract 實現；實際 topology 仍須以 provider conformance、schema 複雜度、延遲與可維護性決定。固定每輪跑 Extractor／Consultant／OPKS Coder／Projector，或讓罕見 Duty／split／OPKS 結構永久污染常見 schema，都不因本節而成立。

application／framework 應自行產生並保存 operation ID、event ID、時間、model／prompt／Skill／tool version、generation、read-set、state revision、ContextManifest、token／成本、驗證結果與 audit。LLM 不得自行宣稱這些欄位，也不得直接產生 authority commit outcome。LangGraph／LangChain／provider session 可以承接 checkpoint、tool loop、typed output 與 tracing plumbing，但 framework state 不能成為第二份 Source、Work Model、Proposal 或 Current JD。

這項分離與外部主流做法一致：OpenAI 將 final output、history、interruptions 與 resumable state 分開，並區分 function calling 與 user-facing structured response；Anthropic 將 session 定義為 harness 外的 append-only event log，工具呼叫只代表模型提出結構化要求、由 application 執行；Google ADK 也把 event content、tool event 與 state delta 分開；LangGraph 則把 message stream、state snapshot、interrupt 與 final output 分開。這些框架只證明通用責任邊界，不替 Caliburn 決定職務分析語意與 authority。

### 7.17 理解校準／可編輯假說的框架調查（2026-08-12）

主流框架沒有一個現成功能叫做「專業職務分析的目前理解」，但已共同提供組成它的通用元件：顯式 state、可序列化的人工輸入請求、pause／resume、事件或 checkpoint 歷史，以及把人工回覆送回原流程。這證明 Caliburn 不必自行重寫整套 durable HITL runtime；同時也證明不能把框架的 approval 直接等同於員工核准 JD。

| 候選 | 可直接借用的能力 | 對 Caliburn 的判斷 |
|---|---|---|
| LangGraph | `interrupt()` 可送出結構化 payload、暫停並保存 state；官方直接示範 review／edit state；checkpoints、`update_state` 與 time travel 保留舊路徑並可從修訂後狀態繼續 | **最接近理解校準的 runtime 形狀**。但 node resume 會從節點開頭重跑，前置副作用必須 idempotent；graph state 只能承接執行，不得成為第二份 Work Model 或 Current JD |
| PydanticAI | model／provider abstraction、typed output、deferred tools、人工 approve／deny，且可覆寫待執行 tool arguments；外部 UI 可在取得結果後以 message history 與 correlation 繼續 | **較薄、較符合現有 Python／Pydantic 技術面的候選**。適合把「提交 Work Model correction／Proposal」建成 typed command；但 stop-the-world 是新的 agent run，不是通用 state review/checkpoint，durable 業務狀態仍要由 Caliburn 保存 |
| Google ADK 2.0 | graph `RequestInput` 可攜帶 message、structured payload 與 response schema；Session 分 events 與可變 state；rewind 恢復 session state 且保留被 rewind 的事件供稽核 | 技術形狀相容，但 ADK 2.0 graph HITL 很新，且 Google 託管 runtime／memory 不符合本機預設邊界；目前只作設計對照，不構成換框架理由 |
| OpenAI Agents SDK | approval interruption 與 resumable state 分離；run 暫停時回傳 interruptions＋state，人工決定後恢復同一 run | 適合 provider-specific tool approval，不能直接提供可編輯 Work Model；若作主 runtime 會提高 provider lock-in，較適合作 adapter 或 conformance 對照 |
| Microsoft Agent Framework | provider clients、session、context providers、memory、middleware、graph workflows、typed request／response HITL 與 checkpoint；官方定位為 Semantic Kernel／AutoGen 的直接後繼 | 是 2026 年最新且功能完整的候選，但框架本身仍新；不能因功能表完整就優先遷移，需先證明 Python 成熟度、Postgres／本機適配與 authority seam 不重複 |
| Anthropic SDK／Managed Agents | tool runner 處理 tool loop、conversation state 與 validation；需要自訂 HITL／logging 時使用 manual loop；Managed Agents 可把 tool 設為 `always_ask` | 支持「敏感副作用由人決定」與 structured notes／外部 memory，但沒有現成的可編輯 domain hypothesis workflow；不值得只為本功能綁定 Anthropic runtime |

共同限制很明確：框架不知道何時一項 Work Model 變化「重要到必須讓員工看見」，也不知道員工更正應如何影響 Story、Task、Duty、OPKS、gap、agenda 與 Proposal。下列內容仍必須是 Caliburn 的 domain contract：

- 理解校準的 trigger policy 與 blocking／non-blocking 規則；
- `UnderstandingReview` 的 focus、摘要、uncertainty、source refs、next move 與 revision；
- `WorkModelCorrection` 如何保存員工原話、supersede／rebut 舊假說並重算下游；
- 校準與 Proposal／Current JD authority 的硬邊界；
- stale revision、document isolation、generation／read-set 與原子提交。

本輪建議不是立即全面導入框架，而是把上述 contract 保持 framework-neutral，第一個 conformance spike 只比較兩條最有價值的路徑：

1. **PydanticAI＋既有 Postgres domain state**：驗證較薄 model／tool／typed-result 層能否承接校準與 Proposal 命令；
2. **LangGraph interrupt＋Postgres domain state**：驗證 checkpoint／review-edit／resume 能否減少 orchestration 程式，又不產生第二份權威狀態。

Microsoft Agent Framework 保留為追蹤候選；OpenAI、Google、Anthropic SDK 作 provider 能力與介面 conformance 來源，不以它們的託管 session 取代 current-only 本地 authority。若第一版每輪都是短而原子的 request／response，PydanticAI 路徑可能更省；若很快需要跨請求的多步中斷、可編輯 state、分支與恢復，LangGraph 的收益才會明顯高於薄型 orchestration。

### 7.18 「目前理解」UI 與 agent-interface 框架調查（2026-08-12）

這次調查以仍在維護的 Microsoft HAX、Google PAIR v2、Apple HIG，以及 2026 年的 OpenAI ChatKit、Google A2UI、Microsoft Agent Framework／AG-UI 與 LangGraph frontend 為主。HAX 的原始研究較早，但目前仍由 Microsoft 維護並提供近期 GenAI 產品案例；因此用它作經驗證的人機互動原則，再用較新的官方 UI／protocol 文件確認技術趨勢，不把單一廠商元件當成產品需求。

官方資料共同支持的方向如下：

- Microsoft HAX 要求依使用者當前工作決定何時打斷、只顯示情境相關資訊，並讓錯誤理解容易忽略、修正或復原；解釋應按需要提供，過多解釋反而可能造成過度信任。
- Google PAIR v2 建議說明 AI 使用了哪些來源、把解釋連到當下行動、以 progressive disclosure 提供更多細節，並在收到回饋後說明它何時、如何改變體驗；其官方也提醒數字 confidence 容易被誤解，只有在能改善決策且經使用者研究後才適合顯示。
- Apple HIG 要求保留人的控制權，把 Edit／Undo／Retry／Adjust 放在生成內容附近，並在修正生效後給清楚回饋；回饋入口應容易找到但不打斷工作。
- OpenAI 最新 model guidance 要求集中定義 autonomy／approval boundary，讓安全範圍內工作持續進行，避免重複「先詢問」造成不必要停頓。ChatKit 已提供 card、可收合內容、editable text、form、confirm／cancel、型別化 action 與 server handler，證明結構化校準卡不必退回純對話文字；官方同時要求 server 把 client action 當不可信資料。
- OPM 的職務分析流程要求 preliminary task／competency 保留來源，並由 SME 評定 task 的重要性、頻率與 linkage。這支持在重大語意與結構節點向員工校準，但不支持把每個中間假說都變成正式核准。

#### 可借用的 UI／protocol 候選

| 候選 | 已提供能力 | 適配判斷 |
|---|---|---|
| 現有 Next／React＋framework-neutral typed contract | 完全控制固定側欄、校準卡、來源展開、revision 與無障礙；可直接沿用現行契約與 authority seam | **第一版建議**。元件少且語意固定，沒有必要先引入新的 agent UI protocol；代價是自行寫少量 presentation 與 action glue |
| LangGraph frontend `useStream`／HITL | interrupt payload、durable pause／resume、React 等 client hook；review card 可放 transcript、queue、dashboard 或 modal，也支援 edit／respond 與自訂表單 | 若 runtime 選 LangGraph，最值得直接借用；仍由 Caliburn 渲染 `UnderstandingCheckpoint`，不可把通用 approval card 當成 Work Model／Proposal 語意 |
| OpenAI ChatKit widgets／actions | card、list、badge、editable text、form、typed action、server/client handler 與 loading state | 元件形狀符合，但綁 ChatKit／OpenAI conversation surface，且常駐產品側欄仍需自訂；不值得只為一張卡提高 provider／UI lock-in，可作 contract 與互動範例 |
| AG-UI＋CopilotKit／Microsoft Agent Framework | SSE、HITL、shared state、custom／generative UI、前後端 tool calling；Microsoft 2026 官方整合已支援 Python FastAPI，但目前安裝指令仍帶 `--pre` | 適合 agent 以遠端服務供多個 client、需要跨框架 state sync 時。Caliburn 是本機單一 Web 產品，現在引入會增加第二套 session／state protocol、authority 對映與 preview 成熟度風險，先不採用 |
| Google A2UI 0.9 | declarative JSON、受信任元件 catalog、incremental update、React renderer、client-defined validation 與多 transport | 是 2026 年重要趨勢，但仍是 pre-1.0，主要解決跨 agent／跨平台的動態 generative UI。Caliburn 的核心校準 UI 應固定且可審查，不需要讓 LLM 自由組版；目前只借用「白名單元件、資料與呈現分離、增量更新」原則 |
| Microsoft Adaptive Cards | JSON card、跨 host responsive rendering、inputs／actions、視覺層級與 progressive disclosure 指南 | 適合 Teams／Outlook／M365 多 host；目前不是 Caliburn 的部署面。可借設計原則，不引入 runtime |

#### 收斂後的第一版邊界

先定義三個 framework-neutral 契約，再由現有 Web 原生元件呈現：

1. `UnderstandingProjection`：由 application 依 Work Model、來源、Current JD 與 workflow state 組裝側欄；status、source type、revision 與 blocked reason 不由 LLM 自報。
2. `UnderstandingCheckpoint`：由 deterministic trigger policy 產生 soft／branch-blocking 校準請求，攜帶變更摘要、source refs、受影響範圍與允許動作。
3. `UnderstandingCorrection`：員工的確認、修正或稍後處理命令；server 驗證 revision 後保存 durable source event，再由 reducer 重算。

若之後 conformance spike 選定 LangGraph，可把 `UnderstandingCheckpoint` 映射到 interrupt／`useStream`；若未來真的出現多 client、remote agent 或大量動態表單，再評估 AG-UI／A2UI。這樣跟上「declarative、typed、trusted component、server-validated action」的主流方向，又不為尚未存在的跨平台需求提早付出協定與狀態同步成本。

## 8. 已識別的流程風險與優化方向

### 8.1 焦點隧道效應

風險：AI 專注當前 Task 後漏掉回答中的其他工作。

方向：每輪先做全域理解，再做焦點追問；保存未映射線索與新 Task 候選；開發期以人工 smoke 確認基本保存路徑，成品完成後再以 capability eval 量測「旁支線索不丟失」。

### 8.2 Duty 過早定型

風險：初步 Duty 會成為分類盒子，後續 Task 被硬塞進去。

方向：初期只稱暫定責任區域／Duty hypothesis；有足夠依據時隨時可形成分組提案，但不得宣稱永久定稿；任何新 Task、O/P/K/S 線索都能觸發 regroup review。

### 8.3 Proposal fatigue

風險：每句話都跳出核准卡，訪談無法自然進行，員工也會機械接受。

方向：累積成一個有意義的小段落再提案；高影響 topology change 與低風險文字修改可採不同呈現，但不得降低員工 authority。

### 8.4 OPKS 填表與尾端衰減

風險：模型為填滿欄位虛構內容；或晚期 Task 的 gap 尚未全部關閉就結束訪談，已回答的新證據沒有重新形成候選。

方向：允許空白與 terminal reason；將 O／P／K／S 方法按需載入，避免每回合塞入完整 OPKS prompt；追蹤每個工作假說與各軸的分析／gap／receipt 狀態；以長回合 pilot 比較「現行獨立 OPKS operation」與「同一顧問按需 Skills」的品質、遺漏、成本與尾端衰減。

### 8.5 Reference 錨定

風險：公版文字專業完整，使 AI 與員工把「可能有」誤認成「本人有」。

方向：blind-first；Reference 分 lane；先顯示差異與中立問題；公版來源永遠不自動提高事實權威。

### 8.6 假進度與假完成

風險：以 Task 數、固定問題數或 0–100% 宣稱完成；新線索出現時進度倒退。

方向：使用「目前已知」的 coverage、sufficiency、具體 gap、待決 Proposal 與停止理由；完成是可解釋的條件組合，不是填滿率。

## 9. 下一輪待討論

按產品優先、元件後置的順序，下一輪建議只討論：

> 在已確認的顧問流程、記憶權威與 Context Engine 候選方向下，下一個最小 capability spike 應驗證哪一項通用元件可由框架接手，又不破壞 Current JD authority、來源追溯與可替換模型？

優先候選是 checkpoint／resume／HITL、model／structured-output interface、Skills progressive disclosure 與 context middleware hook。先選一個垂直切片做 conformance，不一次全面導入多套框架；Reference／RAG 仍依產品流程成熟度與 ADR 0057 邊界另行接入，不等待正式 eval 才開始其他產品工作。

## 10. 本稿依據

Repo 研究：

- [`AI 專業職務分析顧問流程：最終反方審查與品質設計`](2026-07-25-professional-job-analysis-consultant-process-final-red-team.md)
- [`AI 專業職務分析顧問 R1：Task Discovery 深入研究`](2026-07-25-professional-consultant-r1-task-discovery-deep-research.md)
- [`Task 邊界、merge/split 與同一性判準研究`](2026-07-28-task-boundary-merge-split-and-identity-research.md)
- [`專業顧問第一個最小完整迴圈`](2026-07-30-professional-consultant-minimal-complete-loop-research.md)
- [`iCAP 逐欄位標準`](2026-07-13-ai-redesign-raw-icap-field-standards.md)
- [`OPKS 設計裁決研究`](2026-08-01-opks-design-decisions-research.md)
- [`OPKS 漸進式蒐集研究`](2026-08-04-opks-progressive-elicitation-research.md)
- [`OPKS 缺口與再分析的封鎖關係`](2026-08-06-opks-gap-reanalysis-blocking-research.md)

Stakeholder 草稿（非權威，只作需求來源）：

- `C:\Users\chenb\Downloads\職務分析_AI_階段化狀態機需求稿 _ AFFiNE.html`（2026-08-12 完整讀取並依 §5.4 裁決）

官方／第一手來源：

- [Anthropic — Introducing Anthropic Interviewer](https://www.anthropic.com/research/anthropic-interviewer)
- [Anthropic — Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- [Anthropic — Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Anthropic — Scaling Managed Agents: Decoupling the brain from the hands](https://www.anthropic.com/engineering/managed-agents)
- [Anthropic Docs — How tool use works](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works)
- [Anthropic Docs — Tool runner（自動 loop 與 custom HITL 邊界）](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-runner)
- [Anthropic Docs — Managed Agents permission policies](https://platform.claude.com/docs/en/managed-agents/permission-policies)
- [Anthropic Docs — Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Anthropic — Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval)
- [Anthropic — Equipping agents for the real world with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- [OpenAI Docs — Model guidance（lean prompts、relevant tools、approval boundaries）](https://developers.openai.com/api/docs/guides/latest-model)
- [OpenAI Docs — ChatKit widgets](https://developers.openai.com/api/docs/guides/chatkit-widgets)
- [OpenAI Docs — ChatKit actions](https://developers.openai.com/api/docs/guides/chatkit-actions)
- [OpenAI Docs — Results and state](https://developers.openai.com/api/docs/guides/agents/results)
- [OpenAI Docs — Guardrails and human review](https://developers.openai.com/api/docs/guides/agents/guardrails-approvals)
- [OpenAI Docs — Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [OpenAI Docs — Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI Docs — Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)
- [OpenAI Docs — Compaction](https://developers.openai.com/api/docs/guides/compaction)
- [OpenAI Docs — Counting tokens](https://developers.openai.com/api/docs/guides/token-counting)
- [OpenAI Docs — Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)
- [OpenAI Docs — Skills](https://developers.openai.com/api/docs/guides/tools-skills)
- [OpenAI Docs — Tool search](https://developers.openai.com/api/docs/guides/tools-tool-search)
- [Google — Why we built ADK 2.0](https://developers.googleblog.com/en/why-we-built-adk-20/)
- [Google — Build long-running AI agents that pause, resume, and never lose context with ADK](https://developers.googleblog.com/build-long-running-ai-agents-that-pause-resume-and-never-lose-context-with-adk/)
- [Google — Developer's Guide to Building ADK Agents with Skills](https://developers.googleblog.com/en/developers-guide-to-building-adk-agents-with-skills/)
- [Google — Introducing A2UI](https://developers.googleblog.com/en/introducing-a2ui-an-open-project-for-agent-driven-interfaces/)
- [Google — A2UI v0.9](https://developers.googleblog.com/en/a2ui-v0-9-generative-ui/)
- [Google PAIR v2 — Mental Models](https://pair.withgoogle.com/guidebook-v2/chapter/mental-models/)
- [Google PAIR v2 — Explainability + Trust](https://pair.withgoogle.com/guidebook-v2/chapter/explainability-trust/)
- [Google PAIR v2 — Feedback + Control](https://pair.withgoogle.com/guidebook-v2/chapter/feedback-controls/)
- [Google ADK — Session](https://adk.dev/sessions/session/)
- [Google ADK — Human input for graph workflows](https://adk.dev/graphs/human-input/)
- [Google ADK — State](https://adk.dev/sessions/state/)
- [Google ADK — Rewind sessions](https://adk.dev/sessions/session/rewind/)
- [Google ADK — Events](https://adk.dev/events/)
- [Google Cloud — Gemini Enterprise Agent Platform（Sessions、Memory Bank、evaluation、observability）](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale)
- [Google Cloud — Choose a design pattern for your agentic AI system](https://docs.cloud.google.com/architecture/choose-design-pattern-agentic-ai-system?hl=en)
- [LangGraph — Overview](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangGraph — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangGraph — Time travel](https://docs.langchain.com/oss/python/langgraph/use-time-travel)
- [LangGraph frontend — Human-in-the-loop](https://docs.langchain.com/oss/python/langchain/frontend/human-in-the-loop)
- [LangChain — Context engineering in agents](https://docs.langchain.com/oss/python/langchain/context-engineering)
- [LangChain — Short-term memory](https://docs.langchain.com/oss/python/langchain/short-term-memory)
- [LangChain — Memory overview](https://docs.langchain.com/oss/python/concepts/memory)
- [PydanticAI — Deferred tools and human-in-the-loop approval](https://pydantic.dev/docs/ai/tools-toolsets/deferred-tools/)
- [Microsoft — Agent Framework overview](https://learn.microsoft.com/en-us/agent-framework/overview/)
- [Microsoft — Agent Framework workflows human-in-the-loop](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop)
- [Microsoft — Agent Framework AG-UI integration](https://learn.microsoft.com/en-us/agent-framework/integrations/by-component/ui/ag-ui/)
- [Microsoft HAX — Guidelines for Human-AI Interaction](https://www.microsoft.com/en-us/haxtoolkit/ai-guidelines/)
- [Microsoft HAX — Time services based on context](https://www.microsoft.com/en-us/haxtoolkit/guideline/time-services-based-on-context/)
- [Microsoft HAX — Support efficient correction](https://www.microsoft.com/en-us/haxtoolkit/guideline/support-efficient-correction/)
- [Microsoft HAX — Make clear why the system did what it did](https://www.microsoft.com/en-us/haxtoolkit/guideline/make-clear-why-the-system-did-what-it-did/)
- [Microsoft HAX — Convey the consequences of user actions](https://www.microsoft.com/en-us/haxtoolkit/guideline/convey-the-consequences-of-user-actions/)
- [Microsoft — Adaptive Cards for agent design](https://learn.microsoft.com/en-us/agents/design-guidelines/adaptive-cards-for-agent-design)
- [Apple HIG — Generative AI](https://developer.apple.com/design/human-interface-guidelines/generative-ai)
- [U.S. OPM — Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/)
- [U.S. OPM — Six Steps to Conducting a Job Analysis for Multiple Grades](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/six-steps-to-conducting-a-job-analysis-for-multiple-grades/)
- [O*NET Resource Center — Data Collection Overview](https://www.onetcenter.org/content.html/dataCollection.html)
