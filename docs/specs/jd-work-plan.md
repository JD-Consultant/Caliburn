# JD 工作計畫：現行契約

狀態：**現行**，依 [Accepted ADR0082](../adr/0082-consultant-jd-work-plan.md)；保存與接續沿 ADR0081 仍有效的決定。最近核對：2026-10-08。

Plan 讓同一顧問延續取得理解、深入分析、整理與核對 JD 的工作。它保存目前焦點、主要方向的處理位置及剩餘工作，讓顧問換題或換窗後仍能接續；受訪者看到安排是附帶效果。工程接線已完成，各一場的有限比較未呈現可辨整體增益，尚未證明穩定提升 JD 品質。

本頁維護 Plan 的內容、工具、保存、接續與同份 UI 契約。元件權責由[架構 §2.1](../architecture/system-boundaries.md#21-長任務的元件分工)維護；分析與交付品質依[三份指南](../guides/README.md)；原未知筆記、比較及 Q006 討論留在[設計沿革](2026-10-06-consultant-interview-planning-and-focus-design.md)，不得把其中已被取代的未知限定套回現行用法。

| 讀者要查什麼 | 直接閱讀 |
|---|---|
| Plan 記什麼、如何更新及收尾 | [內容與格式](#1-內容與格式)、[使用時機](#2-使用時機與更新)、[局部完成與交付](#3-局部完成整體交付與暫停) |
| read／edit、空正文與容量 | [工具與編輯](#4-工具與編輯) |
| 合法採用、交易、原操作與換窗恢復 | [保存與模型接續](#5-保存與模型接續) |
| 候選與正式內容如何顯示 | [同份唯讀 UI](#6-同份唯讀-ui) |
| 改哪個模組、哪些效果仍未證 | [接線與責任](#7-接線與模組責任)、[不變量與驗證邊界](#8-不變量與驗證邊界) |

## 1 內容與格式

Memory、Plan、Changes 與 JD 的元件名稱、責任及關係，統一由[架構文件 §2.1](../architecture/system-boundaries.md#21-長任務的元件分工)維護。本節只展開 Plan 需要保留哪些內容；工具及資料名稱仍沿既有契約。

Plan 安排從取得理解到交付 JD 的工作，可帶足以接續的短脈絡。下表說明 Plan 正文與既有資訊如何配合，不另定其他元件的責任：

| 資訊 | 主要位置與用途 | 例子 |
|---|---|---|
| 實際問答及更正原文 | 原始訪談，供語境與證據回查 | 員工實際如何描述盤點及授權。 |
| 工作輪廓、情境與目前理解 | Memory，保留本人範圍、行動、成果、條件、判斷、交接及來源 | 本人清點並交差異表，主管核准調整；適用哪些盤點類型仍未知。 |
| 當前焦點及剩餘工作 | Plan，安排訪談、分析、編修與核對 | 釐清盤點範圍；整理已知分工到 JD；核對目的與任務是否仍誤寫核准權。 |
| 正式描述及其依據 | JD，作為實際成品接受核對 | 盤點任務、成果、要求及相應來源。 |
| 一般品質與方法 | 既有三份指南及顧問指引 | 如何判斷重要性、寫作充分性、來源一致及全工作涵蓋。 |

Memory 與 Plan 不按已知／未知或完成／未完成二分。Memory 必須保留會限制工作理解的未知，否則「還不確定是否核准」可能被誤讀為肯定或否定。Plan 可短述同一未知以安排處理，但不能成為另一份事實權威或 JD 引用。相反地，工作事實已清楚而 JD 尚未修正，Memory 不負責替顧問維護編修待辦。

Plan 可記有明確結果的未完成工作，例如「依已確認分工修正盤點任務與目的」。焦點及尚未輪到的工作都可涵蓋訪談、分析、JD 編修與核對；純公版／模型想到、尚無訪談或現有材料支持的員工責任，仍須先中立探索，有相關線索才列入。

保留目前焦點、其他重要未完方向，以及必要的線索、先後關係或再訪條件。近期焦點具體，較遠方向可粗略；有需要才拆小、合併、刪除或改順序。任務文字應能看出要解決什麼、做到哪裡可以暫告一段落，不要求固定欄位、多層樹或每問一題就建立子任務。

### 1.1 單份 Markdown 與顯示名稱

UI 文案為「工作計畫」。預設兩段短 Markdown：「目前焦點」與「工作方向」。標題是供模型和受訪者閱讀的慣例，不是 App 解析任務的 schema 或拒絕保存的條件；有內容需要表達才展開，不為符合模板捏造焦點或缺口。

```markdown
## 目前焦點
釐清新人帶教中，本人負責的判斷與交接。

## 工作方向
- 收貨：日常流程已入稿；特殊條件尚未探索。
- 盤點：本人分工已清楚，待整理進 JD；哪些情境適用這套處理方式仍未知。
- 新人帶教：正在深入本人範圍。
- 全稿核對：待主要方向整理後，核對遺漏、依據與跨欄一致。
```

範例為虛構中途狀況，假設已有相應工作線索；不是每個員工都要建立這些方向。每個方向用必要短句表達「目前處理到哪裡、還剩什麼」，不固定三欄逐項填滿。複雜、容易在切換時遺失或有依賴的剩餘工作，才展開少量子項。必要線索、暫留原因或再訪條件附在所屬方向，避免另抄到多份清單。

有當前工作時焦點指出要推進什麼；目前沒有活動焦點可省略或清楚表示暫無，不強制產生新工作。純文字空值仍沿原契約，不因兩段範本變成非法，也不因空白表示 JD 完成。主要方向不必對應一筆 JD 任務；可有全稿核對等交付工作。完成描述須限於已處理範圍，不將「日常流程已入稿」縮成整方向已完整。

不新增永久任務 ID、固定狀態碼、百分比、每項日期或獨立優先序欄位。排序、拆合及內容由顧問按需要維護，App 不從 Markdown 推導業務完成狀態。詳細問答、完整事實及成品仍在原話／Memory／JD；不保存私有推理，也不要求每項抄一份通用回看規則。

短大綱、焦點與未完工作是三種用途，不要求三份相互重複的清單。方向由已取得的職務輪廓與新線索形成；全稿核對可由交付目標產生。粒度以能獨立推進、切換後容易遺失或有依賴的剩餘工作為準。

新舊正文都按同一文字契約保存。新輪可沿現行用途逐步整理原未知清單，保留未解命題，不批次補造歷史進度；舊 captured request 仍以原提示、工具與能力恢復。對外名稱為「工作計畫」，內部工具、資料表及持久身分沿用，不因文案變更遷移資料。

## 2 使用時機與更新

用法核心：**每輪可見並對照目前焦點，有實質進展才寫；離開當前方向前回看整體，交付前核對成品。**「使用」不等於每次都呼叫 read／edit，也不等於每答一題都重新排列全案。

| 使用時機 | 顧問如何使用 Plan | 可觀察結果與邊界 |
|---|---|---|
| 初次開始、尚無工作輪廓 | 先中立取得輪廓；當能辨認需要接續的工作方向、準備選一個深入前，建立粗大綱與焦點。必要時焦點可先記「建立職務輪廓」。 | 不等完整輪廓才規劃，也不按固定第幾題建立；不可由職稱直接造出本人工作清單。 |
| 每次收到員工回答、開始新輪 | 對照已提供的完整 Plan 與本次輸入，辨認當前焦點、解決部分、新線索及更正。若只是補充同一範圍，沿焦點繼續。 | 新輪全文由 App 提供，模型不必多叫一次 read；普通回答不自動等於子任務完成。 |
| 回答、分析或工具結果實質改變剩餘工作 | 對相關方向做局部 patch，例如縮小未知、加入新工作、將「釐清」改為「整理 JD」。JD 編修須依工具的實際結果及內容判斷進度。 | 無實質變化不寫；工具拒絕不標已寫好。重要接續變動應在本輪正式答覆前保存，不等訪談全部結束才補。 |
| 準備離開目前焦點 | 當前局部結果足夠、暫時推不動、員工換題或重大更正時，先保住剩餘，再回看主要方向與其他未完工作，選下一個可推進焦點。 | 這是防止深入後漏掉其他工作的主要回看點；不是每次小回答都全面重排，也不因答不出一個問題封住整個方向。 |
| 換窗或恢復接續 | 依合法保存的 Plan 和上下文重新定位；全文不清楚或只剩局部差異才 read。 | 新輪採合法基底；同輪壓縮提供該輪精確候選全文，同輪中斷恢復原 request／投影。不能一律刷新到任意 latest，也不因重新開 UI 就自動跑規劃。 |
| 準備交付整份 JD | 回到工作輪廓、必要 Memory／原話與實際 JD，按指南核重要涵蓋、責任與條件、未完編修及一致性；有重要可推進工作就修訂 Plan 並繼續。 | 不是只看 Plan 空了或都有完成短句；本輪提問後等待員工，與整份 JD 完成，是不同的結束。 |

同一顧問可在一次員工輸入所觸發的 Turn 中完成多個動作：讀資料、分析、整理 JD、依結果更新 Plan、返回整體選下一問。需要員工資訊才提出問題並等待；本次正式答覆不要求所有子任務都結束。completed Turn 不因 Plan 有待辦就自行重啟，背景 Memory 也不代替顧問訪談或編修 JD。

例如盤點回答只是補上交接對象時，仍留在盤點深入，必要才縮小剩餘問題；待盤點已有足夠可寫內容或當下只能保留未知，才查看整體，發現新人帶教尚未深入。若盤點仍需入稿而員工想先談帶教，就保留編修工作、轉焦點；不把「換題」寫成「盤點完成」。

### 2.1 同一份計畫如何隨工作改變

| 情境 | Plan 需要保住或修改的內容 | 不得誤判 |
|---|---|---|
| 問到一半，員工想改談帶教 | 焦點轉到帶教；原方向留下精確未解範圍。答不出時記明必要背景，有新線索或其他可回答切入點再處理。 | 換題不等於已解；「通則是否適用」不能縮寫成「多久發生」。重看暫留項不等於立即再問。 |
| 分工已清楚，但 JD 尚未反映 | 將原訪談工作改成「依已知分工修正 JD 任務及相關目的」，保留到實際需要的整理／核對成立。 | Memory 有事實不等於成品已寫好；也不能因 Plan 寫了「已入稿」就視為保存成功。 |
| 相關成品已按依據整理與核對 | 主要方向縮成一句當前處理位置，完成的微小步驟移除；仍未知的其他面向分開保留。 | 「日常流程已入稿」不等於例外、條件及全方向均完整。 |
| 訪談確認某候選不屬於本人工作 | 沿既有否認／排除責任保留結論，移除不適用工作；必要時只留短接續提示。 | 每個方向都要新增 JD 文字才算完成，會迫使模型捏造責任。完成依該項預期結果判斷。 |
| 新更正改變先前分工或條件 | 重開語意上受影響的方向，核對相關任務、職責、目的、權限等實際成品；其他有效方向保留。 | 「局部重開」不等於只改同名 Plan 條目；跨欄仍矛盾就是尚未完成。 |
| 使用者先手動完成或改寫 JD | 下一輪取得並辨認目前稿及必要人工差異後，核實原待辦是否仍成立，再結束、改寫或重開。 | 人工改稿不是已核實工作事實；不得按舊 Plan 重複插入或覆蓋新稿。此為 Agent 使用獨立能力的情境，不新增 Diff 契約。 |

下一步仍由同一顧問依三份指南選擇：重要、可推進的工作優先，結合員工當下回答與意願；不固定把第一項當最高優先，也不規定每輪問完即寫稿。執行結果、答覆或更正造成實質變動時局部 patch。完成局部工作、轉題、換窗及準備收尾時重新對照整體；無線索不反覆追問的既有界線保持。以上是運作案例，不增加固定狀態機或額外模型呼叫。

答不出與拒答分開處理：仍重要的未知保留必要背景及再訪條件；沒有新線索或可回答的切入點就先轉向，不等義重問。沒有合適條件時可寫「尚未釐清，目前不追問」，不捏造取證承諾。本人拒答後，只有本人主動重開或明確願意補充才再談；拒答、未知與明確不負責不可混同。

背景 Memory 尚未發布時，新答案仍可沿近期原話與有效上下文推進；同輪 Memory 保持原固定快照。已解事實及詳細問答留在原話／Memory，成品留在 JD。完成的微小提問／編修步驟移除，主要方向留有範圍的處理位置；更正只重開受影響內容，不建立永久完成日誌。

## 3 局部完成、整體交付與暫停

單一子任務以它要產生的實際結果判斷，例如責任問題已有支持，或已保存的 JD 與該責任一致。某部分仍答不出時可以轉向其他有價值工作，但不能把無法回答改成已解。Plan 是幫顧問選下一步的資料，判斷與執行仍由顧問負責，清單本身不是品質驗證器。

全案收尾沿三份指南：主要及重要低頻工作已合理回顧；本人責任、重要條件與交付足以說清；重大矛盾已處理；已取得理解適當進入 JD；成品主張有據且一致；員工有核對補充的機會。這些品質準則由指南供應，Plan 只保留本案尚未達成的具體工作，不每輪重抄全部規範。

仍有影響成品的重大未知而目前無法取得答案，可以清楚交付帶待確認事項的版本或暫停，不能宣稱完整驗收。已達本次用途的可交付品質、沒有重要可推進缺口時可結束，不為可選潤飾無限追問。員工要求休息或停止亦須尊重。追求滿分落在高品質完整的成品與驗收，而非 Agent 自評 100 分、清單為零或保證未知工作已窮盡。

## 4 工具與編輯

局部修改重用 Memory 的 V4A 正文編輯格式、解析、定位及套用，不新增第二套文字編輯器。規劃只有一份 App 已綁定正文，模型不用 Memory 的 `target_title`、`field`／引用欄位或其他 scope。工具及保存接線已實作；本節說明現行行為。

`edit_interview_plan` 只收一筆 `diff`，可含多個 hunk：

```json
{
  "diff": "@@\n ## 工作方向\n-- 盤點：本人範圍、差異確認與交付尚未清楚。\n+- 盤點：差異由誰確認仍未釐清。\n - 退貨：主管不在時如何交接。"
}
```

合成例子，不具有員工事實資格；假設盤點已有部分答案，就縮小該缺口，退貨條目原樣保留。V4A 前綴為空白（原文 context）、`-`（刪行）、`+`（新增行）；原 Markdown 條目本身有 `-`，因此 diff 的刪行示例以 `--` 開頭。多處修改放同一份 diff，全部成功才形成並保存新正文。App 綁定檔案、本輪、原操作、精確原位置與 writer；模型不生成 ID、版本、路徑或保存結果。

回傳沿 [Memory 更新契約](2026-09-27-memory-object-update-tool-contract.md) §6 的實際效果規則：成功給 `status:updated` 與**程式由實際前後正文形成的 diff**，未變回 `status:unchanged`；不無條件 echo 輸入，也不只回成功讓模型猜模糊定位後的效果。規劃只有一種正文，結果用根層 `diff`，不重印 title／description 或冗餘 `applied_changes[]`。例：

```json
{
  "status": "updated",
  "diff": "--- body_before\n+++ body_after\n@@ -1,3 +1,3 @@\n ## 工作方向\n-- 盤點：本人範圍、差異確認與交付尚未清楚。\n+- 盤點：差異由誰確認仍未釐清。\n - 退貨：主管不在時如何交接。\n\\ No newline at end of file\n"
}
```

此例的三行來源及新正文都沒有末尾換行。結果沿現有 `describe_body_change` 的完整輸出，包含 `--- body_before`／`+++ body_after`、數字 hunk header，以及需要時的無末尾換行標記；不自行省略後再當原成功回傳。結果 diff 是觀察，**不是下一次 edit 的 V4A 輸入**。結果只表示本輪候選及原操作效果可靠保存，不表示 Turn 已採用或分析完成。輸出容量不足在 prepare 處理，不事後靜默截斷或把已保存結果說成拒絕；必要全文再 read。

`read_interview_plan` 輸入 `{}`，回目前完整正文：

```json
{"plan": "## 工作方向\n- 盤點：差異由誰確認仍未釐清。\n- 退貨：主管不在時如何交接。"}
```

未建立回 `{"plan":null}`；刻意清空後回 `{"plan":""}`。讀取失敗／結果未知不能偽裝成空。確定未成立的拒絕沿[共同 ToolRejection](2026-09-27-agent-tool-contract-design-research.md)；原操作命令／結果重播由執行與業務保存負責，ToolRejection 本身不處理重播。過期位置／失效 writer 沿既有接續；保存不明先查原操作，不要求模型改參數盲重送。

正式 schema 在 `apps/api/contracts/`，沿[契約策略](../contract-strategy.md)生成 Python／TS；工具、模型投影、HTTP 共用正文，envelope 按用途不同。UI 唯讀呈現同一份保存正文，透過對話調整；候選與採用版的選擇見 §6。

### 4.1 共用正文編輯與空值

既有機制沿 [Memory 正文編輯](../implementation/memory-body-editing.md)維護，不在本稿另定定位演算法或門檻：

- [V4A parser](../../apps/api/src/caliburn/adapters/v4a_parser.py)解析單正文 hunks，不接受檔案路徑／create-delete envelope、數字 unified header 或尾端垃圾。
- [body_matching](../../apps/api/src/caliburn/adapters/body_matching.py)沿現行受控近似與唯一合格位置政策，零／多處回明確錯誤，不默選第一處／最高分；不改成前案的逐字替換政策。
- [apply_body_diff](../../apps/api/src/caliburn/adapters/body_edits.py)全部對原正文定位成功後才套用指定增刪行，context 保留實際原文；未改字元及換行沿既有保留規則。
- 工具呼叫綁精確原基底，prepare 固定完整新效果及結果，execute 核 writer／position；恢復查原操作結果，不重新匹配 latest。同一模型 response 的多處修訂宜合成一個 multi-hunk diff，作為工具／Prompt 指引，不另建固定 planner Step。
- 現行 SDK 允許多個 tool call，而 [共用 tool_steps](../../apps/api/src/caliburn/agent_execution/tool_steps.py)依 output 順序逐筆 prepare→execute，沒有角色取得完整 response 的額外驗證 hook。若模型仍給多個 plan edit，各筆按本輪當前候選串行處理；後筆因原文不再匹配而拒絕時，前筆已保存效果保留。不宣稱整個 response 原子或強制至多一次，不為此新增通用 preflight。
- 無匹配／歧義／非法或超限 patch 的確定拒絕沿共同錯誤契約；COMMIT 確認未知沿原操作恢復，不宣告未修改要求重送。沒有實質變化不呼叫工具。

Memory 用途保留非空來源／結果規則；Plan 可從空正文建立，也可刪完為空。兩者共用解析、唯一定位與套用演算法，以用途政策控制空值，不照搬 Memory 物件 create／delete 工具。

共用介面為 `apply_body_diff(body, diff, *, policy, allow_blank_body=False) -> str`；只有 App 為規劃指定 `True`，Memory 沿預設。這個布林只控制既有兩處 nonblank 前後置檢查，不正規化／strip 正文、不改定位與換行。共用純 editor／matcher 位於機制層 `adapters/body_edits.py`／`body_matching.py`，實際差異 helper 隨 editor 共用；Memory 的 typed preparation／物件規則留在原 feature，規劃不 import 另一 feature 的私有業務 preparation。不加新依賴、第二 editor 或通用業務服務。

prepare 為編輯將 `plan=None` 映射為來源 `""`，結果若等於這份來源字串，`next_plan` 保留**原 nullable 值**；不能把沒有文字效果的 EOF 空行新增當成已建立／刻意清空。用途規則為：

| 原正文／editor 結果 | 狀態／保存正文 |
|---|---|
| `None`／非空字串 | `updated`／新原文。 |
| `None`／`""` | `unchanged`／仍為 `None`。 |
| `""`／`""` | `unchanged`／仍為 `""`。 |
| 任意已建立字串／逐字相同結果 | `unchanged`／保留原字串。 |
| 非空字串／`""` | `updated`／刻意空正文。 |

不將純空白正規化成 null／空字串；上述比較都是精確字串。`unchanged` 仍保存原操作／結果並前進 revision，沿 §5.4。容量由 App 的 BodyMatchPolicy 與結果序列化檢查，不是模型參數。

首次未建立時 App 將原正文視為空，仍綁未建立的精確原位置；模型以同一工具的 EOF 新增建立：

```json
{"diff": "@@\n+## 工作方向\n+- 盤點：本人範圍與交付尚未清楚。\n*** End of File"}
```

parser 允許無舊 context 的明確 EOF 新增，空原文的定位唯一為 0；Plan 用途政策允許全部刪成空。刻意清空用含全部現存正文的刪除 hunk；保存結果為空正文，不是刪根物件，沒有新操作的沿用與刻意空正文仍可分辨。從空建立／全刪成空與原結果恢復的驗證仍須同時保住 Memory 空來源／結果拒絕，不另加全量替換工具。

對上例兩行正文的合法清空輸入為：

```json
{"diff":"@@\n-## 工作方向\n-- 盤點：本人範圍與交付尚未清楚。\n*** End of File"}
```

預期 `updated`，完整正文為 `""`，read 回 `{"plan":""}`；若正文後來已改，模型須依目前原文修改，不能拿此例當通用清空命令。

A 不取得 B1／B2 的 Memory 寫工具，也不把規劃塞入 Memory 物件或 optional reference state。新保存只管規劃用途；原 request、取消隔離與合法採用沿 §5，UI 沿 §6。重用機制不代表模型會正確選擇要刪的缺口，效果驗證的邊界見 §8。

### 4.2 Wire 與工程容量

正式格式由 [App canonical schemas](../../apps/api/contracts/)維護，沿[契約策略](../contract-strategy.md)生成。下表只說明各入口用途及必要區分，欄位變更以 schema 為準，不手寫第二份 DTO。

| 入口／結果 | 必要 shape |
|---|---|
| `read_interview_plan` 輸入 | 空 object，禁止額外欄位。 |
| `edit_interview_plan` 輸入 | 根 object 僅 required `diff:string`，非空且有界，禁止額外欄位；V4A 語法由現有純核心處理。 |
| read 結果／共用正文投影 | required `plan:string|null`，string 可空；禁止額外欄位。`null` 未建立，`""` 刻意空，其他為保存原文。 |
| edit 成功 | `{"status":"updated","diff":"實際觀察"}`，或 `{"status":"unchanged"}`；用結果分支表達，不強填無效 null diff。 |
| edit 確定拒絕 | 沿共用 ToolRejection；`invalid_patch`、`patch_context_not_found`、`ambiguous_patch_context`、`patch_limit_exceeded` 等沿原分類。 |
| 檔案層 GET | `/api/job-files/{job_file_id}/interview-plan`，required `job_file_id` 與 `plan`；身分為 App 提供 UUID，plan 沿共用正文投影。無模型寫 HTTP 或新人工編輯入口。 |
| ConsultantTurn preview | required nullable `plan_preview`；outer null 無可用 preview／舊能力，非 null object 內 required `plan` 可為 null 或字串。file／execution 身分沿原 DTO 外層，不重抄。終局以檔案採用版為準。 |

模型 strict 工具的 object properties 全部 required、禁止額外欄位；模型參數與結果分開，不把 HTTP 的 App metadata 塞入模型參數。採目前所選一般模型的支援子集；[OpenAI 官方限制](https://developers.openai.com/api/docs/guides/structured-outputs#some-type-specific-keywords-are-not-yet-supported)對 fine-tuned 模型另有字串／陣列限制，一般模型的驗證不能外推至 fine-tuned 模型。生成與 provider 接受性的既有驗證見[原工程證據](../plans/evidence/interview-plan-2026-10-07/t5-validation.md)。

現行工程上限為：正文 16,000 字元、diff 16,000 字元、32 hunks、完整結果 64,000 字元；scan 上限沿既有 BodyMatchPolicy。目的為保持短筆記並約束編輯／回傳，不是論文最優值或 token／時間保證；模型不填這些政策。文字與 diff 上限在準備階段及共用純 editor 檢查，結果以實際序列化文字在 prepare 檢查，讀取也不靜默截斷；沿已有機制，不另建 validator。舊原操作回放原成功輸出，不拿新版上限重算。

超限先保留原文，請模型移除完成微步驟、重複及過時內容，必要時合併完成方向的短句；保住主要範圍、重要未完工作、未知命題及再訪條件。不能為容量捏造完成，也不自動改摘要或開檢索系統。每次外送仍沿實際 token 計數／上下文准入；全文超過可用輸入不會變成隱性截斷。若代表性材料經合理整理仍頻繁超限，帶實際長度、重要未知保留及成本反例重開上限／表示，不先無限放大。

## 5 保存與模型接續

新輪的合法採用版、同輪目前候選及恢復用原操作各有固定位置；不能以任意 latest 代替。以下定義 App 保存正確性，不新增訪談程序狀態。

### 5.1 文字保存與進入 context

**保存成功不會自行讓模型讀到。** App 必須把正文放進模型 input，或由讀取工具回傳。正文以 Markdown 字串保存在 App 資料庫，JSON 是工具／API 外層，不要求實體 Markdown 檔。完整正文送入 input 且沒有截斷時，模型可取得全文；這不保證每個缺口都被正確注意或理解，仍須評估。

保存與載入的官方契約及查閱限制沿[研究 §11](../research/work-analysis/2026-10-06-long-interview-planning-and-focus-research.md#11-2026-10-07-補查保存全文與模型-context)，本稿只維護 Caliburn 的投影取捨：

投影方式：

- **每個新訪談 Turn**：將該輪合法採用短筆記全文放入固定初始 input，標示為顧問安排資料；與當輪員工原話、Memory 導覽一起提供。不靠模型自己想起 read tool 才見到焦點。獨立筆記 item 放在原 app_data／員工輸入之前：history → plan → app_data → raw；沿 [recent_preload](../../apps/api/src/caliburn/agents/job_consultant/recent_preload.py) 保持 app_data 倒數第二、原員工輸入最後的既有容量接縫，不能任意 append 到 raw 之後。
- **同 Turn 的後續模型 Step**：沿已保存的原生 input 與工具歷史；目前正文可由原全文及成功工具的實際變更觀察接續，不靠 echo 的請求 diff 猜結果，也不能將 diff 冒充完整下一版。read 工具供必要回查。不每個 Step 重貼全文或臨時刷新 latest，也不修改已外送 request。
- **context 壓縮後**：完整原生 C 後補**同 Turn 目前已保存候選**的完整短筆記，與跨輪採用版分開；精確投影先保存，不從摘要重新抽取或退回前輪正文。原操作／request 恢復仍沿下面既有安全邊界。
- **完整 Memory／JD／原話**：沿現行導覽與按需讀取，不因使用文字筆記而把全部材料常駐。
- **正文變長**：先移除完成微步驟、合併重複，保留主要方向、重要未完工作及必要再訪條件；容量有界且拒絕超限，不靜默裁掉重要未知。是否拆為摘要／按需明細，須有具體長度與效果反例再比較，目前不建立筆記檢索系統。

進入 context 的正文與 UI 是同一份保存內容；App 的檔案、位置與准入 metadata 依必要 contract 提供，不讓模型生成，也不把正文提升成系統指令。

### 5.2 固定位置、保存資格與恢復

| 現行接縫 | Plan 接線 |
|---|---|
| [context_binding](../../apps/api/src/caliburn/agents/job_consultant/context_binding.py)固定 Memory、frontier 與原 input | 同一短交易固定合法規劃筆記基底，標示為顧問分析安排；恢復原 binding/request，不換成新資料。舊 strict binding 作版本相容分派。 |
| [ConsultantTools](../../apps/api/src/caliburn/agents/job_consultant/tools.py)已有 read、prepared command 與原操作恢復 | 加入讀寫規劃筆記工具，沿原分派與 prepare→execute，不另建 loop。 |
| [公版候選保存](../../apps/api/src/caliburn/workflows/occupation_references.py)及[正式讀取](../../apps/api/src/caliburn/workflows/occupation_reference_reads.py) | 借單 writer、精確位置與採用資格；A 專用用途保存，不塞 optional reference state，也不照抄其 restore 功能。 |
| [顧問完成交易](../../apps/api/src/caliburn/workflows/consultant_completion.py) | 同交易核對最終規劃筆記位置及 context/tool 保存邊界；跨輪資格由 completed execution＋正式輸入＋固定 frontier 推導，不另存正式正文或完成 flag。 |
| [runner](../../apps/api/src/caliburn/agents/job_consultant/runner.py)既有 compaction callback、[共用 runtime](../../apps/api/src/caliburn/agent_execution/tool_steps.py) | A 包裝 callback：完整原生 C 後補規劃筆記投影，精確位置與原生 item 先持久捕捉，再保存下一 request；重試同次投影，不臨時讀 latest。共用 State 不新增角色 ORM。 |

Plan 使用 A 專用業務候選與不可變操作，沿公版 state 的已核准保存／跨輪資格模式；不把正文只存 Graph channel，也不借 Memory 批次／發布或 optional reference 的資料權威。合法讀取沿 completed execution、匹配正式員工輸入及固定 frontier；工具成功只建立當輪候選效果。只在具體恢復、資格或複雜度反例推翻此選擇時重開，不因另一種 framework 名稱並列備案。

新輪固定 plan 基底必須與 Memory／frontier／原輸入在 `context_binding._capture_data()` 的同一短交易完成；不直接照抄公版 workflow 在建工具時再抓 frontier 的 start。初始 binding 綁基底，不因同輪更新覆寫；當輪目前位置由規劃候選負責。沒有修改時繼承固定基底；有操作且正文 `""` 是刻意清空，不能被「沒有修改」忽略。

prepare 形成原位置、完整下一正文、實際效果及已核容量的成功回傳，保存完整 prepared command；execute 只提交該命令與原結果。原操作恢復先查原命令／效果，不重套 patch、重算 diff 或使用新版較小容量改寫舊回傳。完成交易在目前 JD／正式訪談／context 的原邊界增加最終 plan 位置核對，不另存正式正文或採用 flag；取消／失敗候選可保留恢復證據，不供跨輪採用。

binding 以版本分派區分原能力；binding／工具能力依原 captured request 保留。舊 request 沒有 plan toolkit 就維持舊能力，舊回復不補今日工具、正文或 compaction wrapper；新舊分支共同保住原 request 的完整 input／tool schema。

- **新輪**：基底為固定 frontier 內最近合法採用規劃筆記；先對照 Plan、本輪 Memory 導覽及近期回答，核對焦點、剩餘工作與新線索。沒有正文也可依訪談／分析／JD 整理需要建立焦點，不要求重訪全部工作或捏造缺口。沒有實質變化不重寫；沒有新候選的舊輪繼承原基底，與刻意空正文分開。
- **同輪／中斷**：原 request、binding、工具結果及已保存投影不換新資料。COMMIT 後確認遺失查回原 operation，不拿 latest 冒充原結果，正常恢復不倒帶。
- **換窗**：完整 Step 工具效果與原生 C 保存後，A wrapper 固定當輪目前 plan 位置及完整原生 item，以原 request 的角色私有 checkpoint 保存投影，再形成 full C＋saved item。投影已存但 parent 未接回時恢復同次 item；下一 request 已存則直接恢復原 request，不讀 latest。共用 loop 依完整返回 items 重新計數／准入，不重貼員工輸入或刷新 Memory，不覆寫 initial binding。
- **完成／取消**：沿原 job-file／writer 終局資格；完成後禁止續寫，取消／失敗不供下一輪採用。舊在途 request 不追補今日新增工具。
- **隔離／刪除**：沿檔案鎖、FK、guarded saver 與保留責任；Plan migration 明確配置 cascade／immutable protection，不新增獨立清理器。

### 5.3 資料庫表示：完整正文、候選指標與原結果

Plan 使用現有 PostgreSQL 的兩張用途表。規劃內容是一份 Markdown `TEXT`，不把每個子任務拆成資料列。patch 是模型局部編輯的輸入；成功操作保存確定的完整正文，不靠重播 diff 才能讀目前筆記。沿[現行公版保存](../../apps/api/src/caliburn/features/occupation_references/persistence.py)的候選指標與不可變完整效果，但依本用途縮小欄位。

| 候選表 `interview_plan_candidates` | 型別／責任 |
|---|---|
| `job_file_id`、`execution_id` | UUID，複合主鍵；每份職務檔案的每個支援 plan 的 Turn 一筆。沿既有 execution 範圍，不另創 interview／task 身分。 |
| `base_revision_id` | UUID、不可為空；指向本輪內部 start 操作，保存初始固定正文，之後不變。 |
| `current_revision_id` | UUID、不可為空；指向目前已保存操作。候選表不另存 `current_body`、正式正文或採用 flag。 |

| 不可變表 `interview_plan_operations` | 型別／責任 |
|---|---|
| `job_file_id`、`operation_id` | UUID，複合主鍵；操作身分由 App 配置、重入沿用，不用模型 `call_id` 自行代替。 |
| `execution_id` | UUID、不可為空；操作只屬於同檔案的原 Turn。 |
| `kind` | `TEXT`、不可為空，只允許 `start`／`apply`；是內部操作種類，不是訪談或子任務狀態。 |
| `expected_revision_id` | UUID、可空；start 為空，apply 是原命令預期的同 Turn 位置，也作前驅。 |
| `revision_id` | UUID、不可為空；`(job_file_id, execution_id, revision_id)` 唯一。沿既有 operation／revision 分工。 |
| `body` | `TEXT`、可空；完整短筆記。`NULL` 是尚未建立，`''` 是刻意空正文，不能用 truthy 或 `COALESCE` 混同。 |
| `intent_digest` | `TEXT`、可空；apply 保存原命令的固定意圖摘要，start 為空。摘要只核對同身分同意圖，不代替正文或成功結果。 |
| `result_text` | `TEXT`、可空；apply 保存 prepare 已生成並核容量的**原成功回傳序列化文字**，start 為空。不另建 receipt 表，也不在恢復時重算實際 diff 或重新序列化。 |

`intent_digest` 沿[Memory 的既有做法](../../apps/api/src/caliburn/features/work_memory/candidate_operations.py)：以固定 canonical JSON／UTF-8 的 SHA-256 核同意圖，涵蓋 kind、原 file／execution／expected position、原 diff、下一正文（保留 null／空字串）及原 `result_text`。完整原 diff、正文及結果仍在已保存 prepared command；DB 不再另抄原工具參數。canonical 形式依原 command 契約版本固定，恢復不拿新 serializer／新容量改寫原命令；不抽新的通用去重引擎，也不能直接把 Memory 型別專用 helper 當成已支援本用途。

本題沒有候選倒帶功能。公版的 `generation_id`／`result_generation_id` 及與 expected 重複的 `parent_revision_id` 是 restore 分支責任，本用途不照抄；原 execution writer 身分負責失效程序隔離，expected revision 負責過期位置。也不增加時間戳排序、子任務 ID 或進度欄位。

FK／約束沿唯一資料責任：

- 兩表的 `(job_file_id, execution_id)` 都指向既有 `executions` 複合唯一鍵，阻止跨檔案連結。candidate 的 base／current 與 operation 的 expected 都以 `(job_file_id, execution_id, revision_id)` 指向本用途 operation；expected 只在 start 為空。operation 不反向要求 candidate，先插 start 再插候選即可，不建立循環 FK。
- row-local CHECK 限制 kind、start／apply 欄位形狀及 expected 不等於自身 revision；跨列位置、原內容、成功結果及 execution 資格由既有鎖與用途服務核對，不寫查別表的 CHECK，也不在 DB 解讀 Markdown 子任務語意。尚未建立時的無變更保持 `NULL`，不因 editor 用 `""` 作空來源而誤建正文。
- 主鍵／唯一約束已有查找索引。`(job_file_id, execution_id, expected_revision_id)` 索引供前驅參照查找／整檔 cascade；candidate 主鍵的 file／execution 前綴已限單筆 base／current 參照。資格讀取先沿原訪談索引；只有量測反例才增查詢索引。
- Plan migration **明寫** FK 的 `ON DELETE CASCADE`，並為 operation 配不可變 UPDATE／DELETE 保護；沿 `job_file_row_is_present(to_jsonb(OLD))` 的既有整檔刪除例外。原 [0025 migration](../../apps/api/src/caliburn/migrations/versions/0025_job_file_deletion.py)只處理當時已有表／trigger，不會自動保護後加的表。root 仍在時不能單獨修改或刪操作；整檔刪除仍須原流程確認所有工作已終局。

以上是 Caliburn 映射；官方約束只保證指定的鍵、FK 與 row-local CHECK，不保證業務採用資格。[PostgreSQL 約束](https://www.postgresql.org/docs/current/ddl-constraints.html#DDL-CONSTRAINTS-FK)亦明載 FK 不自動替引用欄位建索引。2026-10-07 migration／ORM 已實作並以真 PostgreSQL 驗證，細節沿[保存切片證據](../plans/evidence/interview-plan-2026-10-07/t2-storage.md)。

### 5.4 讀取、交易與跨輪採用資格

| 行為 | 固定的讀寫邊界 |
|---|---|
| 建立本輪基底 | 新能力 Turn 在 §5.2 的初始捕捉短交易讀合法採用版，插入完整正文的 start operation，再插 base＝current 的候選。start 原身分可沿既有 `uuid5(execution_id, 用途名稱)` 方式由 App 固定。 |
| 初始捕捉重入 | candidate 已存在時讀 **base** 的 start 正文，不讀 current 或重新抓採用版；read tool／UI／compact 才讀 current。candidate 存在且 body 為 NULL 仍是筆記未建立。plan start 不代替原 Memory／frontier／request binding 的持久保存，不能由它重建那些資料。 |
| prepare | 在原固定位置用共用 patch 核全文及原結果，形成並先保存完整命令；不得到 execute 才重新套 diff。原命令身分與意圖摘要由 App 決定。 |
| execute／新操作 | 短交易依原順序取得 job-file lock → active execution writer lock → candidate，核原位置。插入完整 body／digest／原 result 的不可變操作，再前進 current，全部同交易提交；模型、checkpoint 或其他網路 I/O 不在鎖內。 |
| execute／原操作重播 | 核 file／execution／writer 後，**先查原 operation，再判 current 是否過期**。原 scope／kind／意圖必須相同，成功回原 body／位置／`result_text`；不將 current 倒退。只有查無原操作且原位置仍 current，才可建立新效果；查詢失敗不能當查無。 |
| 成功但正文無變更 | 仍保存原成功操作與 `unchanged` 原回傳，分配新的 revision 並前進 current，body 原值不變。`unchanged` 指內容未變，不能被當成沒有保存結果；不另開 no-op receipt。 |
| 確定拒絕 | 非法／零或多處合格／容量超限等在 prepare 拒絕，沒有新的業務操作或 current 變更；沿原 native 錯誤回傳保存。多工具 response 仍逐筆執行，不能回滾先前已成功的另一呼叫。 |
| 完成 | 原完成命令帶 App 捕捉的最終 plan 位置，與 JD、完整正式訪談及 context 在同一交易核對，最後沿原 owner 完成 execution。沒有 edit 也核 start 位置。完成後不允許工具續寫，不另外複製正式正文或設 flag。 |
| 完成確認遺失／取消競爭 | 重播完成核原最終位置；沿現有 completed replay／writer 核對，不能誤用 active-only lock 而拒絕已成功原完成。舊 writer 被替換仍拒絕；取消先成立則完成回滾，完成先成立則 stop 回實際已完成結果。 |

**初始捕捉的確切裁決**：沿 [capture_turn_context](../../apps/api/src/caliburn/agents/job_consultant/context_binding.py) 的第一個完整可靠 binding／request 作固定邊界。有完整保存便原樣恢復；只有原 native capture 的 pending／unfinished 工作時沿該 graph 的 `None` resume，不替換已存模板或 preparation，必要的原 capture node 重入仍讀本輪 plan base，待整份 binding 可靠保存後才准模型／工具前進。尚未形成可靠 binding 的讀取不冒充原已保存 Memory／F；plan 表也不能補出它們。查 checkpoint 失敗或提交未知時保持待核對，不當缺資料再建。只有查詢可靠確認「本輪 start 已存在，但原 native capture／binding 缺失或損壞而無法恢復」時，依原執行 failure／stop 邊界終止本輪，保住前輪正式成果；不拿今天模板重建同一輪或悄悄新開 Turn。此分支已由原 template／pending 與 start orphan 的故障反例核對，沿 [T3](../plans/evidence/interview-plan-2026-10-07/t3-context.md) 保留證據。

沿[公版正式讀取](../../apps/api/src/caliburn/workflows/occupation_reference_reads.py)的資格，本用途不把整份操作歷史或所有候選正文載入。語意為：同 file 的 plan candidate → 原 consultant execution **completed** → 匹配的正式 employee input／reply → candidate.current operation；以**正式員工輸入序號 ≤ 固定 frontier F** 中最大的一筆勝出。前輪最終答覆在 F 之後，不能拿答覆序號作篩選；UUID、created_at 也不決定先後。

現行以各 owner 的具名唯讀投影組合，避免跨 feature 查別人的私有 ORM／表。2026-10-08 重構把資格、排序及取最新交回同一 SQL 執行，不再將整份歷史搬到 Python 再以 `VALUES` 傳回。這是查詢接線調整，跨輪採用資格保持原義，不新增資格表、發布快照或通用查詢引擎：

| owner／現行接口 | 輸入與結果 |
|---|---|
| interviews：`formal_exchange_positions_projection` | 接同 file 的 `InterviewReadScope`，公開只含 execution 與正式 employee input 序號的 SELECT。需有匹配正式 input／reply，input 序號 ≤ F；不選正文。 |
| executions：`completed_consultant_executions_projection` | 接 file ID，公開同 file、kind 為 consultant_turn、status 為 completed 的 execution SELECT。 |
| Plan：`candidate_plan_heads_projection` | 接 file ID，只選同 file candidate 的 current operation、revision 及 nullable body。 |
| workflow：`read_adopted_plan` | 同一 session 組合三份 SELECT，依 employee input 序號降冪 `LIMIT 1`；回 `PlanSnapshot(position, body)` 或沒有合格候選。勝出 body 為 null／空仍回該 snapshot。 |

具體組合見 [`interview_plan_queries.py`](../../apps/api/src/caliburn/workflows/interview_plan_queries.py)；各 owner 仍管理自己的篩選及 SQL。讀取失敗向外傳遞，不當作沒有合格版本。查詢只回一列，參數數量不隨訪談歷史增長；這不表示資料庫掃描成本為常數。取捨及真 PG 反例沿[本輪審查證據](../plans/evidence/full-system-review-2026-10-08.md)。

沒有合格候選回未建立；勝出 body 為 `''` 就保留空，不往更早正文找 fallback。舊能力 Turn 沒有候選便沿前一個合格版本；支援 plan 的新 Turn 即使沒有 edit，也有固定 start。新能力 request 缺 root／位置是保存不完整，不能藉現在設定或空正文偽裝成舊能力略過核對。檔案層 GET 沿目前正式 frontier，模型新輪沿其 captured F，兩者不能任意互換。

沿現行短行鎖／writer，不追加通用 lease 或所有操作 Serializable；[PostgreSQL 行鎖](https://www.postgresql.org/docs/current/explicit-locking.html#LOCKING-ROWS)只是保住同一交易的衝突邊界，還須 App 的 scope／位置及原結果核對。pause request 仍允許已飛 Step 工具先可靠保存，原 owner 才在安全點轉 paused；真正 paused／終局不接受新工具效果。checkpoint 與上述業務交易分開，不能從 checkpoint 的 success 字串推定 DB 已提交。

### 5.5 Captured 能力、換窗投影與完成恢復

本節展開 §5.2 的已實作接線；沿現有私有 StateGraph、guarded saver 與原生 compaction，不新增共用業務 State。行為反例與跨 saver 恢復見[T3 證據](../plans/evidence/interview-plan-2026-10-07/t3-context.md)，模型品質由獨立比較判斷，見 §8.2。

#### 原捕捉能力與 schema 相容

保留 strict `_BindingV1` 原欄位，新 `_BindingV2` 在原欄位加 required `plan_base_revision_id`，version 為 2；`TurnContext` 帶 nullable 的純 plan position。原 captured preparation template 無兩個 plan 工具就是 v1；完整含 read／edit 兩工具就是 v2。只含一工具、schema／bundle 不完整或 binding 與原 toolkit 不一致，沿保存不完整／能力不一致拒絕，不能默默補工具。初始 capture 尚未完成也依恢復出的**原 template**判斷，不用今日設定。v2 即使正文 null／空仍須有本輪 start 位置；tools、wrapper、completion 都依此分支，v1 不新增 candidate 或投影。

恢復原 schema 時核原數值型別及相容斷言；布林／浮點不能冒充原整數長度，不允額外 assertion 改變原 read／edit 接受範圍。原字串 `title`／`description`／`$comment` 只為 annotation，可不同，不用今天文案替換或全文比對原 template。具體損壞／不相容 schema 的 Red–Green 與獨立審查沿[原件](../plans/evidence/interview-plan-2026-10-07/review-context-final.md)。

#### 正文 item 與精確換窗投影

新輪與換窗使用同一用途 builder，形狀為 `{"role":"user","content":"JSON 文字"}`；content 是 `{"data_kind":"consultant_interview_plan","plan":string|null}`。檔案／execution／revision 等 App metadata 留在 binding，不塞模型參數或公開正文。正文逐字保留，null／空字串不混同。換窗已保存 item 恢復時原樣使用，不重新渲染或序列化。

**A 私有投影 graph**：單節點 `capture_projection`；thread 為 `{response_thread_id}:plan_projection:{parent_request_id}`，`checkpoint_ns=""`，不含 writer ID。下列固定 shape 只供 App checkpoint：

| 保存項 | 必要欄位／責任 |
|---|---|
| `input_binding` | `version:1`、`job_file_id`、`execution_id`、`source_request_id`，以及 `compact_position:{thread_id,checkpoint_id}`；固定原 parent request 及已採用完整 C。 |
| `projection` | `plan_revision_id`、`plan_item`；節點沿同 file／execution current 讀取並保存精確位置與原生 item。 |

C 正文仍由原 native compaction thread 保存，投影只存精確參照，不複製 C 或另存原 request。[既有 context_compaction](../../apps/api/src/caliburn/agent_execution/context_compaction.py)提供純原生 `read_compacted_window`：核已完整 adopted、`preparation_policy is None` 及完整 compaction snapshot，回現有 `SavedContextWindow`；它不讀 plan ORM。核原 request 時，C thread 必須是 `{response_thread_id}:compact:{source_request_id}`，並核原 `request_snapshot`／input count。`source_request_id` 是 parent request ID；C graph 自有 `request_id` 是另一個原 compaction request，不能要求兩者相等，仍沿原 HeldCompaction 恢復內部身分。已保存 input_binding 的恢復一律用其 exact C position，不能 fallback latest。現有 `read_prepared_history` 只接受輪前 preparation，不能直接拿它當輪中讀取。

**Wrapper 的呼叫順序**：先完整委派原 `bind_window_compaction` callback，保留原 HeldCompaction 恢復／核帳；它成功且 execution active，才核既有私有投影 graph。只要原 `input_binding` 已保存，包括 raw checkpoint 的 `__start__`，便沿原 exact C position／`None` resume；只有可靠確認 graph 尚不存在，才解析原 callback 的完整 C、捕捉精確位置並建立 graph，不能先讀 latest 再替換 pending binding。節點在原 file／writer 邊界讀 current；同步保存後核完整 raw checkpoint，最後再 guard，返回 full C＋saved item。共用 `tool_steps.compact_window` 保存下一 request 並重計數／准入。

[tool_steps 的 inactive 恢復](../../apps/api/src/caliburn/agent_execution/tool_steps.py)仍會呼叫 callback 結算已保存的 paid C；wrapper 不能在委派前自行 ensure_active 或讀 plan 而阻斷它。inactive 不讀／保存新投影，也不回傳新窗口；既有 C 仍沿原機制核帳。這是保存與成本邊界，不增加訪談狀態或新 provider 呼叫。

| 中斷位置 | 恢復裁決 |
|---|---|
| 下一 request 已完整保存 | 原樣恢復該 request；不重新捕捉筆記或重建能力。 |
| 完整 projection 已保存，parent 尚未接回 | 讀原 exact C＋原 plan item，核原 input_binding／能力；不重讀 current 或改序列化。 |
| 私有 graph 有 pending／unfinished，尚無完整 projection | 用原 graph 的 `None` resume，不替換 input_binding。純 capture node 尚無可靠結果可重入讀當輪 current；parent 尚未採用，單 writer 不先跑後續模型／工具。 |
| ACK 不明或讀 checkpoint 失敗 | 先核原 graph；未知保持待核對，不當不存在新建。完整 raw checkpoint 才是可靠投影，pending writes 不冒充完整成果。 |

以上原模板升級前後恢復、DB start 提交但完整 binding 未保存、C 已保存但 projection／parent 尚未保存，以及 inactive C 核帳，已補新接線反例，見 [T3](../plans/evidence/interview-plan-2026-10-07/t3-context.md) 及[獨立審查](../plans/evidence/interview-plan-2026-10-07/review-context-final.md)。工程故障測試不代替真模型換窗後的分析與 JD 品質比較。

#### 完成位置與終局重入

沿[現行 runner](../../apps/api/src/caliburn/agents/job_consultant/runner.py)完整 native final／tool results／control checkpoint 的原完成證據。Graph 尚有 `next/tasks`、未結工具或 prepared command 時不得完成；完整 final 後沒有後續模型／工具效果，同 Turn 的 plan head 穩定。首次完成在讀取確定 context／JD position 後讀當輪 plan head 一次，`complete` 加 `plan_position:PlanPosition|None`：v1 必須 None，v2 必須為同 file／execution 的 current，沒有 edit 也帶 start。沿 §5.4 同交易核原 writer／head，未知 COMMIT 在同一行程保留原全部 args 重播，不新增 completion manifest 或 Graph。

跨行程若原 execution 已 completed，入口走**原結果恢復分支**：讀原 execution 的完成 context binding、exact native final、原 `FormalInterviewExchange` 與原能力版本；formal 回覆須吻合，v2 必須有同 execution 的保留 plan head，v1 不補候選。沿原 `finish_execution(writer, COMPLETED)` 核原 writer，直接回原 exchange。原完成交易已使 JD／formal／context／plan 核對一起提交，不再跑 active-only `read_completed_position()`／JD live-preview 或 complete，也不為此新增 adopted JD reader。必要的 native checkpoint I/O 在短交易鎖外，DB 原位置與 writer 在既有交易邊界核對；原資料缺失／衝突拒絕恢復，不改讀檔案最新 head 或重跑工具。現行 runner 已接入，反例以新 saver／runner／client 恢復同一原結果，provider 若被呼叫即失敗。

完成反例另核：DB 完成提交但確認遺失，跨行程從原 completed binding 及 final 回原 exchange；下一 Turn 或手動 JD 已前進也不倒退；取消先成立／失效 writer 不冒充 completed；舊能力 completed 不追補 plan。沿原元件及真 DB 測試，不以新 manifest 的存在作恢復證據。

### 5.6 保留與故障反例

完成微步驟移出 current 正文的內容規則不授權刪掉恢復用操作。舊操作仍可支援原結果核對；它們不全部進 context 或受訪者清冊。先沿[現行保留責任](../architecture/persistence.md#6-保留失效與清理)，不加自動 GC、diff-only 重播或正文去重。容量／備份負擔有實測反例才比較正文重用；compact、取消或新版本本身不能授權清理。整檔刪除沿原 guarded saver／檔案 owner 同步移除本用途資料，不另開只刪筆記歷史的入口。

| 反例／故障點 | pass／fail 的可觀察邊界 |
|---|---|
| start 已提交，初始 binding 的可靠 checkpoint 尚未確認 | 重入讀原 start/base，不替換成 current；完整保存就恢復原 binding／request，native unfinished 沿原 capture resume。查詢未知不重建；可靠確認原 capture 缺失／損壞則本輪 failed、前輪正式成果不變。刻意注入 DB 已提交但 binding 全未持久的缺口，核 §5.4 裁決，不能用 start 正文假裝已保存 Memory／F。既有 saver 已提交後失 ACK 測試不證明此缺口已通過。 |
| 操作 COMMIT 成功、確認／tool-result checkpoint 遺失 | 以原操作與命令查回完整 body 及逐字原 result；同 ID 換 diff／位置／結果拒絕。保存不可用保持待核對，不發第二次新操作。 |
| 後續操作已成功，再重播較早成功或 unchanged | 回較早原結果，current 留在後續位置；較早新的不同操作因位置過期拒絕。 |
| 部分回答後清空，完成／取消／pause 競爭 | complete 正式採用空；cancel／fail 不採用本輪候選，仍見原完成版。pause request 不丟已飛成功結果，真正 paused 不新增效果；完成與 stop 只認原裁決，沒有半份正式訪談／JD／plan。 |
| 另一檔案、另一 execution 或替換前 writer 遲到 | FK／scope／writer 拒絕，原檔案及原位置不變；UI 不混入其他身分正文。 |
| 舊無 plan 的 request、整檔刪除與 immutable guard | 舊恢復不新建 candidate 或 retrofit 工具；root 存在時單筆 mutation 被拒，合法整檔刪除可 cascade 全部新表並沿原流程清 checkpoint。 |

這些是原 G4 明列的真 PostgreSQL／native 恢復驗收，2026-10-07 已由[保存](../plans/evidence/interview-plan-2026-10-07/t2-storage.md)與[context](../plans/evidence/interview-plan-2026-10-07/t3-context.md)切片執行。具體版本與範圍以原件為準；不因核碼或 SQL 範例通過便宣稱可恢復／可刪除。

## 6 同份唯讀 UI

[InterviewPane](../../apps/web/src/app/InterviewPane.tsx)與共享 [useCurrentTurn](../../apps/web/src/features/interview/use-current-turn.ts)呈現同一保存正文；ConsultantTurn DTO 提供 nullable plan preview，沿既有 active／paused polling。preview 無可用投影與正文刻意空必須分開；不得用 truthy 判斷而把 `""` fallback 成舊文字。

| 狀況 | 呈現與讀取 |
|---|---|
| idle／重新載入 | 檔案層唯讀 GET 讀合法採用版；現行 `/current` 只 discovery 在途 Turn，不作採用版來源。 |
| 有支援 plan 的 active／paused Turn | status preview 投影目前已保存候選；尚未有 edit 時投影該輪固定基底，已清空就顯示空正文。 |
| 舊能力 Turn／沒有可用 preview | 沿檔案採用版；不創造候選，不補今日能力到舊 request。 |
| completed | 重新取得新採用版，沿已完成 Turn 資格。 |
| cancelled／failed | 重新取得原合法採用版；當輪候選不留下當成已採用內容。 |
| 未建立／刻意空／讀取失敗 | 區分「尚未建立」、「目前沒有記錄項目」與不可用；都不聲稱訪談完成。 |

只顯示可靠保存正文，不顯示未提交 streamed arguments。plan query 在**所有終局**刷新；延續 file／execution query key、abort、回傳身份及 stream reconnect 的核對，不加獨立輪詢／SSE。不把另一檔案或舊 execution 的回覆放入目前畫面；錯誤不清空筆記。

終局刷新採**同一檔案 queryKey** 的一路徑：GET queryFn 消費 `AbortSignal`；觀察同檔案 completed／cancelled／failed execution 後，依序 `await cancelQueries({queryKey, exact:true})`（保留預設 revert，不用 `silent:true`）、`await invalidateQueries({queryKey, exact:true, refetchType:'none'})`，再 `await query({...原 GET builder, staleTime:0})`。鎖定 TanStack Query 5.104 的 `query(options)` 是原 `fetchQuery` 的正式等價入口，後者已 deprecated，現行接線使用 `query(options)`。只在這次 GET 實際成功、schema／file 身分正確且目前 file＋terminal execution 尚相符後，才記本地已確認刷新身分；只記身分，正文仍由同一 query cache 保存。失敗保留未完成刷新，可沿同一路徑重試；作用中的刷新及回覆皆按 file／execution 核對，不能讓舊 effect 給新 Turn 標成功。

同一 file＋terminal execution 共用一個在途刷新工作，不因重複觀察而取消自己的新 GET；刷新結束後解除在途記號，失敗可重試。終局核實的當次 render 便停止 candidate preview，不等待刷新 effect；等待／錯誤時，已有正式 cache 只能標為「上一採用版，等待更新」，無 cache 則呈現讀取不可用。當次 `query` 完成後才可呈現新正式版；cancelled／failed 亦同，不能讓候選留在畫面。不因 GET 錯誤重新顯示候選或改成空正文；已核 active／paused 才可用其同 scope preview，status 未核實不把舊 preview 當目前候選。新 Turn 沿既有 start／hint 生命週期接續同一檔案 cache，沒有另建會隨 hint 清掉而退回舊版的 terminal queryKey。

此路徑依鎖定 TanStack Query 5.104.0 與[官方 QueryClient 契約](https://tanstack.com/query/latest/docs/framework/react/reference/classes/QueryClient)核碼：invalidate 預設不拋 refetch 錯誤，disabled／static query 也不保證自動 refetch，第一個在途 GET 可能重用舊 Promise。因此 `await invalidateQueries` 或先寫 refreshed flag 不能證明這次終局後的 GET 成功。上述取消／顯式新讀取與呈現條件是 Caliburn 的現行接線；瀏覽器驗證範圍見[工程證據](../plans/evidence/interview-plan-2026-10-07/t5-validation.md)。

輪前 App 摘要仍是[已確認、未實作的另一目標](2026-10-04-context-summary-and-compaction-design.md)，不因本規劃筆記設計而冒充現行能力。

## 7 接線與模組責任

現行接線沿[程式組織](../implementation/code-organization.md)，Plan 不另建通用任務引擎。

| 責任／位置 | 最小輸入、結果與邊界 |
|---|---|
| 本用途 feature `features/interview_plans/` | 純型別表達 `plan:string|null`、候選位置及原成功結果；service／persistence 提供 start、讀 base／current、核同意圖並套用已準備操作及核最終位置。兩表 SQL 只由此 owner 寫；不解析任務充分性，不把每個條目建成子表。 |
| 既有短交易與跨 feature workflows | 沿既有 file／execution writer 公開能力核身分，傳同一 session 給 plan owner；初始捕捉在原交易固定 frontier 及 start，不另開工具初始化交易。合法跨輪讀取由 typed queries 協調正式訪談／execution 資格；completion 同交易核最終位置，內層不 commit。 |
| 共用正文編輯核心及用途政策 | 沿 §4.1 共用 V4A parser／matcher／editor；目的只允許規劃空來源／空結果，Memory 非空政策保留。輸入完整來源及 diff，回確定全文或既有錯誤；不建第二套語意 validator。 |
| `transport/model_tools` 的規劃薄入口 | schema 只收 `{}` 或 `{diff}`；prepare 取得 App 綁定 scope／位置，產生完整命令及容量合格的實際結果。execute 沿原業務服務提交，重播回原保存結果；wire DTO 不進 feature 純型別。 |
| `agents/job_consultant` 的方法、tools、context binding 及 runner | `planning_instructions.py` 提供同一顧問的用法；註冊兩工具。新 binding 分支同交易捕捉 base，固定短筆記 item；原能力恢復不 retrofit。A 專用 compaction wrapper 沿 §5.2 保存精確投影，共用 loop 不 import plan ORM。 |
| contracts、HTTP 及 web | canonical schema 生成工具／DTO；HTTP 映射 typed 正式讀取與候選 preview。既有 query cache／Turn polling 顯示同份正文，所有終局刷新；UI 不編輯筆記、裁決採用或另生成摘要。 |

`planning_instructions.py:FOCUS_INSTRUCTIONS` 維護共同工作推進原則，沿三份指南，不依賴 Plan 工具；`INTERVIEW_PLAN_INSTRUCTIONS` 描述主要方向、焦點與剩餘訪談／分析／編修工作。提示提供原則與少量例子，反例由測試和比較材料承擔，不把全部案例堆入 production prompt。

工具描述、可執行 V4A 範例及容量錯誤文案沿本頁用途；局部替換必須保住未受影響方向。`InterviewPlan.tsx` 的標題、aria-label、讀取、錯誤與重試文案一致稱「工作計畫」，呈現同份 SafeMarkdown。

Changes 與 Plan 各自獨立。A 可使用[目前 JD 候選](../../apps/api/src/caliburn/features/job_description/candidate_service.py)及[人工差異讀取](../../apps/api/src/caliburn/workflows/jd_changes.py)，再判斷 Plan 的剩餘工作是否改變；人工改稿不因此取得工作事實資格，舊 Plan 也不授權重複插入或覆蓋新稿。Changes 的提示、比較、投影、恢復與來源核對由其責任文件維護，不是本頁的工程前提。

## 8 不變量與驗證邊界

內容修改與工程審查都須保住下列邊界：

- Plan 安排工作，不提供員工事實資格；主要方向短句、空清單與工具成功都不證明 JD 完成。
- 未知命題不得因精簡變義；已知未入稿、其他重要未完工作及必要再訪條件仍可辨認。
- 模型只提供正文修改；scope、writer、操作、版本、位置及保存結果由 App 決定。
- `null`、刻意空字串、沒有 preview 與讀取失敗分開；成功 `unchanged` 仍有原操作及新 revision。
- 原 request、原操作、固定 base 與 exact C／plan item 各依原位置恢復；未知保存結果先核對，不能當作不存在或請模型盲重送。
- 只有符合正式輸入／completed execution／固定 frontier 的候選可跨輪採用；取消、失敗或失效 writer 不授資格。
- completed Turn 不因 Plan 有待辦自動開新輪；DB 完成交易也不增加模型推論、強制簽核、匯出鎖或完成分數。

### 8.1 系統保證與模型判斷

1. **資料可見與保存：現行機制。** [起始 binding](../../apps/api/src/caliburn/agents/job_consultant/context_binding.py)、[壓後投影](../../apps/api/src/caliburn/agents/job_consultant/interview_plan_projection.py)及 read／edit 使模型能取得正確正文。這不證明模型已對照或理解。
2. **使用時機與內容：現行顧問指引。** [planning instructions](../../apps/api/src/caliburn/agents/job_consultant/planning_instructions.py)在同一 A 的決策循環中描述上述時機；回看原已存在，涵蓋剩餘訪談／分析／成品工作，尚未證明穩定的品質增益。
3. **額外重規劃呼叫：未選用的替代方案。** ReCAP／Plan-and-Act 的流程有明確安排規劃呼叫；目前 A 沒有相同的子任務返回機制。若要保證一個檢查步驟必定執行，需另定可識別的觸發、成本、失敗與恢復，不能將同一段提示稱為 harness 保證。即使強制模型檢查，也不能保證品質判斷正確。

[現行 Turn 完成交易](../../apps/api/src/caliburn/workflows/consultant_completion.py)只核對與採用已保存結果，沒有再呼叫模型做全稿驗收；不能在完成交易中偷偷加入推論或將 DB 通過當 JD 完整。若未來比較額外檢查，須另定可恢復的模型執行責任。

「應回看時是否實際返回」「是否保住未入稿工作」「短答有無不必要重排」「本輪等待有無誤作全案完成」是待驗反例。若仍漏用，分開診斷未辨認工作邊界、資料不準、優先選擇或需要額外執行支援，不先加更多提示或固定每輪規劃。

### 8.2 驗證層級與證據

| 層級 | 要證明什麼 | 不能聲稱什麼 |
|---|---|---|
| 離線工具／context／Web | 範例 patch 可用、其餘正文不變、空值與舊 request 保真、提示正確組裝、UI 同份唯讀。 | 自然語言包含某句不表示模型會實行；測試不判 JD 滿分。 |
| 真 PostgreSQL | 沿既有 Plan 保存／context 回歸核相容：合法採用、原 request 恢復及取消不授跨輪資格；不因正文用途改變另造保存流程。 | DB 通過不表示 A 已正確規劃或核清成品；未配置而 skip 不能算驗證通過。 |
| 新真模型配對 | 各一場的正式成品、有效返回、語意忠實、編修遺漏及負擔；失敗原件與未觀察情境也保留。 | 新方案不可沿用舊八案當效果證據；有限合成比較不證明穩定品質增益、真人或所有職務效果；真換窗等原定情境須依實際觀察列明限制。 |

工程驗證與真模型品質分開判斷。原 ADR0081 八案只作歷史依據；ADR0082 的比較固定共同指引、既有 Changes 能力與披露條件，差異是 Plan 全文、read／edit、持久接續及必要使用說明，不能單獨歸因到某個標題或一句提示。

[工程證據](../plans/evidence/jd-work-plan-2026-10-08.md)維護實際命令、版本、原件、帳務及未覆蓋情境；[新比較結果](../experiments/product-validation/jd-work-plan-comparison-2026-10-07/runs/comparison-v2/results.md)維護各一場的有限判讀。兩場已完成、匿名配對已鎖定並解盲，未呈現可辨整體增益，過程語意核對已完成。有限合成比較不能證明穩定增益、真人負擔或所有職務效果；原定長段同窗、真換窗等情境須以實際觀察為準。

效果核對仍看重要漏項、正確返回、已知未入稿、責任／條件深度、跨欄一致、無據內容、過早結束、不必要重問及長窗接續，另記 token、延遲與受訪負擔。資料已保存且可見，不代表模型已使用；若有失敗，先分清資料、語意更新、工作邊界、優先選擇與執行支援，不能用增加提示、工具呼叫或完成標記代替效果證據。
