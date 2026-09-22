# P3 AI controller 操作者候選：有限 spec／quality 審查

2026-09-10；JD-R002。審查者為獨立子任務 AI，非真人；一次有限文件審查。只寫本報告，不採用候選、不修改品質材料／卡包／register，不執行 trial。

**Spec verdict：PASS（有限 G4 測法設計）。Quality verdict：PASS（可核查性與誠實揭露設計；非自然品質通過）。未發現需修正的 actionable finding。**

## Preflight 與審查基準

- Topic ID：JD-R002，P3 公開 C-W 自然校準操作者測法。
- Current stage：候選 G4、尚未採用；主線隔離 G7 的當前施工仍為 Task4 原作者 fix round1／窄複核，Task5／6 未施工。
- Binding decisions：Owner 要求 IMPLEMENT 成品總計畫；P3 是一個真顧問、不指定工具路徑的完整自然案例；P6 另有三異質未見職位各兩次及三名目標員工。核心 Task1–6 零付費，真模型批次須具體資料／次數／費用授權；production 0060 與 Proposed0073／74 不變。
- 唯一問題：既有 AI controller 在原 C-W 事實、揭露協議與 Q 門檻下供應合成回答，是否能成為誠實、有界、可追查的 P3 候選测法？
- 已讀：current-decisions 最新入口及相關總計畫／品質閉合條目；decision-process；成品總計畫全文；品質材料 §4–9；基線 review 的品質材料結論；C-W employee-card／release-protocol／oracle／README／manifest／results-template；預算前置全文；本候選全文。
- Out of scope：施工、DB、啟動產品程序、安裝、讀 key／環境秘密、模型請求、paid action、git mutation、重新研究模型或 Memory、審 Task4 實作、另啟代理。

受審候選：`docs/specs/2026-09-10-jd-natural-calibration-operator-design.md`，102 行；SHA256 `3016d934f2ad174c83f7925b56e9abe16ec8261f7969b42b62eec2d2eb109d43`。下列行號對應此版本。

## Spec 核對

| 位置 | 核對結論與效力 |
|---|---|
| 候選 §1，L7–14；總計畫 §2 P3／P6、§5.4–5.5；品質 §6；基線品質 review | 原「由人依卡扮演／無模擬員工 LLM」確是經審現行測法提案，不能在未同步時當不存在。所讀四份責任資料未見 Owner 直接指定 P3 真人操作者的裁決；也不能把此缺席當成已有真人豁免。候選把兩者分清，明說要修訂協議，而非換名稱偷符合原文。有限、可逆的測法修訂沒有削減 Owner 指定的 P3 真顧問自然案例或 P6 真人效果。 |
| 候選 §3，L30–36；§6，L76–78；§8 | App 只收當次合法合成答案及文件編輯事件，沒有增設產品角色、provider 員工模型、judge 或 authority。不 seed 訪談／Memory／JD，不代顧問呼叫工具；原 prompt／Skill／模型／Memory 在同 trial 不更改。既有 controller 的平台成本與 App 前背景 provider US$1 帳本分開揭露，未把「無額外產品請求」說成全部 AI 運算免費。 |
| 候選 §4，L44–60；原卡 W01–10／M-W1；release-protocol 揭露規則及事件次序 | 逐項語意與作用域保持：W05 初述的不確定性及晚期查證前提、W06 正式低頻與一次支援區別、W09 不同成因、W08／10 未知、W03 平行成果要求、W07 共享依據均未降低。W05 未初述不得偽造前話；M-W1-DOC 與另次 CHAT 分離，文件手編只表示 deterministic 路徑，不冒充真人體驗或訪談來源。 |
| 候選 §6，L72–78；品質 §4、§6–8 | Q01–15 仍以原語意、正反例和嚴重度判斷；NOT_OBSERVED 不轉 PASS／N/A，必測缺證不能宣告 trial 完整通過。最多 12 聊天回合／180 實際 provider attempts／US$1 三界線並行，背景、重試、校正、恢復、未知與在途保留都在範圍內。P3-B01–04、OFF01–09 沒有被此文關閉。 |
| 候選 §7，L82–92；§8，L96–100 | 採用同步清單涵蓋原品質 §6、卡頭／揭露程序／README、manifest／results-template、oracle metadata、register／總計畫／前置報告。要求版號遞增、新 hash、v1 曝光與修訂沿革保留，並保留 NOT AUTHORIZED／runtime pending 至真 gate 成立；沒有倒稱 Owner 原先裁決、也沒有在 review 通過時自動付費。 |

## Quality 核對與報告限制

候選 §2 L22–26 明確只把官方 eval 方法映射為任務目標、合成資料、結果／trace 核對及避免硬定工具次序；沒有宣稱 OpenAI 或 Anthropic 實證證明本 controller 方案、代表真人回答分布或保證 P3 完成。此處是有限來源效力核對；未發現需要重新開官方來源才能判斷的具體疑點，本輪未廣搜，也不聲稱重新驗證兩篇官方網頁。

§3 L32、36，§4 L58–60 與 §5 L64–68 給了實際可檢查的防誘導邊界：逐筆記顧問問題、輸入、卡子內容、既定事件；廣問可答相關範圍、細問不倒全卡；未知不補職業常識；不能用 Q 缺項、schema、refs 或工具路徑引導回答。已揭露遺漏與未追到工作分開判，不把事實卡本身當模型已知資料。發現 controller 洩題／錯卡時保存首 trace，該觀測標污染／不可判定，不能把它算顧問成功或把錯卡算顧問失敗。

這些記錄能讓後續讀者核對可見誘導，**不能證明 oracle 知情偏差已消失，也不能證明沒有隱性措辭／時機偏差**。候選 L26、36、98 已承認這項限制；單憑風險存在而要求 P3 必須真人，是新加產品門檻，非此次 finding。反之，未來若把 AI 操作寫成真人、把同 controller 的初步判讀寫成人工／獨立核准，或把受污染成功宣告 P3 通過，就直接違反本設計與原品質材料，須撤回該判定。

原品質 Q05 的全稿人工語意核對、Q15 的真使用理解／自行操作，以及 P6 §7–8 的人工評讀／真員工效果，不由本次 AI 操作或自評完成；候選 L36、74 已保留證據缺口。可以取得受限路徑的真顧問自然縱切與初步語意證據，但不能只因執行完便把未觀測必測項改成通過。這是本次 PASS 的既有範圍限制，並非新增一個 P3 真人操作者 gate。

## Findings 與靜態驗證

Actionable findings：**0；無 OPEN finding ID、無要求修正。** 未將偏好或待執行項偽裝為阻塞。後续採用同步及執行前置仍必須履行，並非已完成。

僅做文件靜態核對：原 v1 manifest 的五個文件 SHA256／bytes 全部吻合，品質材料來源 SHA256 也吻合；候選的「尚未改卡包／品質原件」與本次讀取一致。hash 只證內容符合該 manifest，不證保密、未曝光或試驗成功。未執行測試、揭露演練、判定者校準、任何 trial 或 provider guard 驗證。

## Closure

- Decision / finding：有限 spec PASS／quality PASS；沒有實際設計缺口需要修正。
- Status：審查完成、候選未由本報告採用；P3 未執行、未付費授權；Task4／5／6 不因此完成。
- Why：測法來源效力、AI 模擬身分、oracle 知情及非獨立限制誠實；原 W／M／Q、揭露及三 cap 未降低；P3／P6 清楚分離，採用同步和 v1 沿革有明確 gate。
- Sources：以上列明的候選段落與原責任材料；本輪沒有新增外部方法主張。
- Affected artifacts：只新增本 scratch review。root 若採用，依候選 §7 同輪同步責任文件；不把本 review 單獨當 durable adoption 或模型執行授權。
- Reopen trigger：同步後仍殘留操作者／判讀效力矛盾、W／M／Q／cap 被降低、實际輸入透露 oracle／教工具、偽造真人／獨立性，或有效 Owner／authority 新反證。
- Next gate：root 記錄有限測法採用並完成 §7 同步；核心 BASE 與 P3-B01–04／OFF01–09 另按原 gate 補證，備妥具體可審執行包後才送 Owner 核准真模型資料／次數／費用。不阻 Task4 修正及後續零付費工程。
