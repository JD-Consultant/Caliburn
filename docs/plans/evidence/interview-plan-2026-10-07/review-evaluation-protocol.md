# P1／P2 評估協議獨立審查

2026-10-07。只讀審查本批 protocol、manifest、conditional_answers、private_facts、run_batch、guard、test_harness；依原件追加讀取 measurements、實際 runner／有效指引及被重用的 BatchGuard。沒有修改 harness、讀金鑰、呼叫 provider 或新增 paid batch。中文反例直接執行原 `Employee`；journey／measurement 反例以 MockTransport 與記憶體資料執行，不用其他員工模型。

共同產品起點與能力接線成立，但原 keyword 回答政策不能作正式品質裁決：同義與複合問句會改變可取得事實，摘要 cue 會洩漏未問內容，已知確認又會被當成說不清。另有未提交回答計入 disclosed 的反例。這些會混淆顧問能力與模擬回答器偏差，必須在正式 freeze 前關閉；pilot 接線原件不能作筆記效果證據。

## 已核共同條件

- 實際 `ConsultantRunner` 的兩組都使用同一 `CONSULTANT_INSTRUCTIONS` 與 `FOCUS_INSTRUCTIONS`；P2 分支才追加 `INTERVIEW_PLAN_INSTRUCTIONS`。指引是三份正式 guides 的既有有效產品實作，沒有只對 P2 注入指南或私有判準。
- 直接比較實際 tool definitions：P2 只多 `read_interview_plan`／`edit_interview_plan`，P1 沒有獨有工具，共同工具逐欄相等。模型／reasoning／output／來源能力相同；顯式 Settings 的 occupation references 為 None，兩組 RAG 皆關閉。
- 每 case 建獨立隨機 schema／產品 file；model 只收到初始公開原話與被選的回答字串。完整私有 facts、disclosed／gap／audit 沒有注入產品。JD／正式訪談／sources／plan 沿真 loopback HTTP；原 checkpoint 觀测在實際 saver 成功後記錄，不替代業務保存。
- guard 於每次出站核來源、模型與端點，生成、compact、所有外送、累計 count、時間與 reserve 均有限；429／未知 usage 保留原 reserve。controlled repeat 2 只改 A 的同步 mid-work 准入門檻，B 仍沿原門檻，第一次實際 A C 後恢復。這是有限機制壓力條件，不能冒稱自然長訪談效果。
- canonical schema glob 錯路徑由 root 先發現、工具代理修正；本次再讀 `source_hashes()` 已包含 canonical／packaged JSON、protocol／披露政策及實際重用的外部 `data/full-interview-rag-2026-10-06/batch_guard.py`。原缺這份外部 guard 的 freeze finding 已關閉。

## Load-bearing findings

| Finding | 精確反例／風險 | 修正與驗收方向 |
|---|---|---|
| P1：詞面匹配不等於相關問題，且摘要 cue 可以披露未問事實。 | 同義收貨問題回 None；同段已整理「其他工作」的摘要加收貨問句，反而披露年度盤點；否定「不用再談收貨」仍選收貨。合法問法不同便可能製造假漏項，無關摘要可製造假查漏。 | 正式每題採匿名語意裁決，沿 frozen facts 與實際相關問題選 IDs；keyword 僅供候選／診斷。未映射不能當員工真的不知道；不因摘要、否定或題外 cue 揭露年度事實。 |
| P1：拒特定個案被擴成整個 privacy topic 拒答。 | 先給投訴拒答後，明確詢問允許的個資保存／存取流程也回 None；同問題在 fresh profile 能得到 privacy。提問順序會永久改變與拒答無關的事實可得性。 | refusal scope 固定為特定投訴個案／個資，不封鎖一般資料管理流程；同題不重開拒答，另題仍按相同可答政策。 |
| P1：選好但未提交的回答混入 disclosed。 | 實際 journey 的兩 Turn fake HTTP 反例只 POST 初始原話與 CLOSURE，audit 卻列 receiving 已披露。倒數第二輪選出的答案會被下一輪 CLOSURE 覆蓋；原最後一輪亦選一個永不 POST 的答案。budget 停於下一輪前也有同樣缺口。 | prepared selection 與 actually submitted 分開，未 POST 不前進員工披露狀態；next Turn 為固定 closure 時不請披露 judge／不選未使用答案。以真正 public input／正式原話判「已披露卻漏稿」，不能從 candidate audit 推定。 |
| P2：最後問題段＋最長 keyword＋一 fact，會靜默丟掉明確複合問題。 | 收貨＋供應商退貨只答後者；報名＋退費＋結業只答退費；分段兩題只讀最後一段，且「結業資格」反被通用「資格」導向報名。 | 凍結所有明確問題的裁決規則；可披露全部相關且滿足條件的部分，或明示未答子題。不用字數長短、JSON fact 排序決定有效問題；audit 保留完整原問題及 omitted subtopics。 |
| P2：已知確認與真 unknown 混成同回覆。 | receiving 已披露後，詢問是否逐箱核品項、數量、外包裝和送貨單，回「沒有其他確定資料，保留說不清」。 | 已知確認可用原固定事實重播，不新增 facts；audit 區分 known confirmation、unmapped、true unknown、refused。更正已披露時，不能重播早期錯說而漏掉其更正。 |
| P2：條件的先後順序不能只靠 seen_topics 集合。 | 若先談 training、後才開 inventory gap，集合已包含 training；它無法證明 partial→實際指定新題→相關回訪。課務 refund 亦同。 | 匿名 judge 取得 actually submitted disclosure order；按同一凍結時序政策裁決，不以「曾經問過」冒充 gap 開啟後的真轉題。 |
| P2：generic A C adoption witness 不能直接證明 mid-work projection。 | 記憶體測例只有 `prepared_history`、非 null preparation_policy 的 adopted C，再接 A 的 exact C prefix，measure 仍輸出兩個 True。它能證明 A 使用 C，不能證明輪中 wrapper 或其已保存 projection。 | 區分 preparation／mid-work。輪中需 `preparation_policy is None`、正確 compact thread／parent；P2 再以 projection input_binding 的 exact C position、saved plan_item hash 及後續模型 input 核對。ObservedSaver 已補實際 projection／input_binding 鍵，不能只看 GET 最後正文。 |

提早 failed／paused／observation_timeout 不應一律標 `common_bounded_closure`；必須記 closure 實際是否送出及最後 terminal outcome，仍列未完成。現有 `natural_completion_verified=False` 是正確保留，不能用共同收束輸入或模型自報完成提升成自然完成。

## 原政策實跑中文反例

以下結果是審查時原機械政策的實際輸出，後續修正不覆寫這份反例。fresh 表示同 profile 新 `Employee`，不改模型或私有事實。

| 狀態／實際問句 | 原選擇 | 應有的裁決方向 |
|---|---|---|
| fresh warehouse：「你接到貨後怎麼清點件數、核對送貨文件和記錄差異？」 | None／說不清 | receiving，與下一題取得同一相關 facts。 |
| fresh warehouse：「收貨驗收時怎麼核對品項、數量、記錄差異？」 | receiving | canonical 對照。 |
| fresh warehouse：「除了每週的例行盤點，你有每年或不定期要做的事情嗎？」 | inventory-partial | 年度／非例行工作是實際問題，不應只回每週盤點。 |
| fresh warehouse：「我已把你其他工作整理好了，謝謝。接下來想了解收到貨後你會怎麼清點、核對件數？」 | annual-count | 只答收貨問題；摘要不授年度披露。 |
| fresh warehouse：「不用再談收貨；我們先釐清帶新人時如何教他掃碼和安全動線？」 | receiving | training；不把否定的收貨當問題。 |
| fresh warehouse：「收貨驗收與供應商退貨是不同流程，你在這兩項各做哪些步驟和交接？」 | supplier-returns only | 明確兩題都按相關事實回答，或明示哪題仍未答。 |
| fresh course_admin：「請分別說明報名、退費、結業資料這三項工作的步驟、交付和權限？」 | refund only | registration／refund／attendance 均是實際問題，不能由 fact 排序默默只答一題。 |
| receiving 已披露：「收貨驗收這段可再確認你是不是逐箱核品項、數量、外包裝和送貨單？」 | None／說不清 | 已知確認；不重新開 unknown。 |
| fresh course_admin：「個案不談。我只想了解個資的保存與存取權限，你怎麼處理？」 | privacy | 允許的一般流程對照。 |
| 先問「收到老師投訴或滿意度回饋時怎麼處理？」得到 sensitive-evaluation；再問上題 | None；refused_topics=[privacy] | 個案仍拒，但一般 privacy 仍可答。 |
| fresh course_admin：「請先說老師臨時不能到怎麼處理？〔空行〕另外，你如何核對學員出席時數和結業資格？」 | registration | absence 與 attendance 是實際問題；不能遺失前段或把結業資格改成報名。 |

journey 記憶體反例的結果：`submitted=[initial, CLOSURE]`、`audit_disclosed=[receiving]`、`audit_facts=[receiving]`、`last_is_closure=True`。未送出的私有完整 receiving 回答不能算成顧問已取得的理解。measurement 記憶體反例只有 preparation checkpoint，但 `checkpoint_adopted=True`／`subsequent_A_exact_C_prefix=True`；上述兩個 True 不足以確認輪中換窗。

## 正式披露 judge 的接續

root 決定以獨立匿名語意裁決取代正式批次的機械選擇，而不是按 arm 成效擴 keywords。工具代理保存 opaque question ID、profile、實際問題、actually submitted facts／gaps／refusal、相關原話及披露順序；不給 judge arm、note、工具、成本或最終 JD。裁決只回 fixed fact IDs／known confirmation IDs、answer／unknown／refused／clarify 與理由；答案抽凍結 facts 原字串或固定回覆，不創作員工事實。只披露問題相關且當時條件已成立的內容，不因看得到全 oracle 而自動補漏。

本審查者因此會看私有事實與實際題目，**不兼任匿名 final JD judge**；正式品質判讀另由未看披露 oracle 的 reviewer 執行。每題裁決原件與後續提交核對均保留。正式 freeze 前需跑上述反例、closing／budget 未提交答案與 mid-work witness 反例；未關閉項不得被 pilot 成功替代。此文件記審查與接續裁決，實際新版 Green／真 API 結果由批次原件另記。

live pilot 裁決中另核出固定句的用途限制：`omitted_subtopics` 的「之後再具體問」只適用本次未答完的可答複合子題，不能把 oracle 確實沒有的新細節說成等待再問。已提交的一次 known＋omitted 裁決過寬，原件保留、不回寫；後續針對該特定破損／受潮情境使用 unknown、零 IDs，既有收貨事實不撤回。純確認而沒有實際問題的段落不釋出任何 facts，沿既定 clarify 回覆。正式 preflight 應明定「複合問題混合可答／真 unknown」與「無提問／自然結束」的同一政策，不把這些分支當模型品質證據。
