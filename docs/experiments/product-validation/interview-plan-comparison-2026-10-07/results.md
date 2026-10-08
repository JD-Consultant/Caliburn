# 訪談筆記：正式 JD 的 P1／P2 比較

**狀態：八案核心比較與四組匿名品質評閱已完成；筆記穩定增益及高品質完整 JD 門檻未證。** 日期：2026-10-07。本頁記實際比較結果；功能責任沿 [INTPLAN](../../../specs/2026-10-06-consultant-interview-planning-and-focus-design.md)，工程證據沿 [T5](../../../plans/evidence/interview-plan-2026-10-07/t5-validation.md)。

本次問題是：同一顧問維持焦點與未完方向後，能否取得、保留並正確寫入重要工作理解，改善最後正式 JD。受訪者能查看筆記是附帶效果，UI 通過及筆記呼叫次數不算 JD 增益。

## 核心結論與完成範圍

八個有效案例各完成 **20 Turn completed 與 common closure**。四個有效 P2 的 20 次正式 HTTP 筆記讀回皆非空，編輯 updated 分別為倉儲 r1 20、課務 r1 20、倉儲 r2 18、課務 r2 20，共 78 次、零 rejected。舊三個完整 P2 的八次格式拒絕、全 null 筆記保留為工具失敗證據，沒有列入成功使用筆記的 treatment。

四組匿名評閱全部鎖定後，主代理才讀正文與解盲：**兩組 P2 較好、一組 P1 較好、一組各有得失；八案均有重要缺口或錯誤，未達全部工作分析完整。** 課務 r1 有一處披露裁決越界，限制公平因果歸因；四組結果只支持有限描述，不能證明持久筆記穩定改善最後 JD，也不能由 UI 補足品質門檻。[品質鎖定原件][quality-lock] SHA256 `98695be07a0b471806cb1dc437dd073aa8a1a3c65e00e4905c34f450ab491ce9` 記 `all_quality_locked=true` 與鎖定時主代理未讀正文；[核心最終 ledger][final-ledger] SHA256 `36e204b3e1c69eb8efd57c088b39625573962e6a9bd5012469fee3472db27e7b` 記八案全部完成。

## 正式 JD：四組配對先鎖後解盲

primary 品質評閱只使用 fresh 匿名 bundle 的正式 JD、員工原話、固定引用內容及凍結 [rubric](../../../plans/evidence/interview-plan-2026-10-07/blind-jd-rubric.md)，不含 arm、筆記、工具、機制及費用。各案只以自己的公開來源核對，不借另一案或 private oracle 補事實。下表揭露匿名 ID 與 arm 的映射，完整逐案反例沿已鎖原件查閱。

| 配對／匿名 ID（P1；P2） | 已鎖定判讀與 material 差異 | 限制 |
|---|---|---|
| 倉儲 r1：`be1d0a02589b4b6582448afae06f2781`；`25ab72e2ecec4b0195c9faea2b248f3a` | [各有得失][review-1]。P1 取得並入稿盤點主管核准、財務調帳、更新後核對及待查；P2 在例行收貨範圍及接班者未知較克制。 | P1 收貨範圍改寫及「晚班同事」接收者超出支持；P2 盤點核心後續未取得，兩案均有限制。 |
| 課務 r1：`1990410190dc49c5bc5dc0402a84db3b`；`915c8249d9d34af2a7a61737e94fdb89` | [P1 較好][review-2]。P1 取得並保存權限系統、鎖櫃、傳送與拒絕透露等資料保護限制，P2 未取得。 | 兩案缺課後續仍未知，匿名滿意度均未取得。P1 Turn 10 披露越界，本組只能描述成品，不能單獨承擔公平因果結論。 |
| 倉儲 r2：`d63711b1162249ac8ee05946a92974d1`；`9933bc1d796c4b88964b84e892c042fe` | [P2 較好][review-3]。P2 取得新人觀察回報／最終主管核准更正，以及首次漏掃、反覆錯誤後續並入稿；P1 尚未取得更正。 | 兩案盤點後續均未知；均有引用定位問題，P1 多處協作引用掛到不相關原話。 |
| 課務 r2：`a6ff700c653b49ed95ff56eda74ea6c0`；`5041f1e90b424a788564fbbcb43c9896` | [P2 較好][review-4]。P2 取得匿名滿意度統計及具體資料保護，保存拒談特定投訴／學員身份界線；P1 未取得。 | 兩案缺課後續均未知；P2 職務目的的回饋／補助來源定位不足，不能以完整度優勢取消。 |

未取得的重要工作、已披露未入稿、來源錯置及無據內容分開判；未知與拒答不填猜，也不以字數、任務數或空欄數判優。上述相對勝負沒有統計顯著、真人負擔或一般職務普遍效果的推論資格。

## 披露政策與來源：接線一致，公平性仍有限制

八案 **160/160 accepted source ID/body** 均對本次正式員工原話核對；Turn 2–19 的 **144/144 已送裁決**，actual question→decision→input／accepted→正式 body 接線及固定字串一致。這證明實際保存與裁決接線，不能單憑它證明裁決語意完全公平。[前六案稽核][policy-six]、[課務 r2 P2][policy-c2p2]及[課務 r2 P1][policy-c2p1]分別保留原件。

課務 r1 P1 Turn 10 的正向子問全是未知的近期退費個案環節／與一般流程差異，decision 自己也將全部子問列 unknown，卻以 `answer` 重播 general refund。這違反整題無可答部分應 `unknown`、0 IDs 的凍結政策；沒有捏造新私人事實，但額外重播可能影響後續 gated eligibility，本輪未估偏差大小。原報告 SHA256 `dd59aa1da279cf0a73dc60137583e670bc0947f880c82674f6a24d1722036afb`；r2 P2／P1 報告分別為 `7d32f84e0b1bf4e452f1443e3dac8fe4107a90e220b0969161489d1c23b7856d`／`2459c4f111c4a2c39daf70f1de38dc156888c25cdabcd34a621e1d3fb66a2a62`，沒有用後兩案改寫舊限制。

條件回答 payload 不帶 arm，但裁決代理曾接收營運 arm／進度 metadata，不能宣稱整段 context 全盲。事後 P1 政策稽核完成語意判讀後意外見到已鎖 P2 的 plan 片段，已在新 P1 報告記錄；未讀 primary 品質判讀、未用於裁決或改寫舊報告，不影響另由 fresh 匿名 bundle 鎖定的 primary 品質評閱。

## 筆記與換窗：保存成立，返回取證未充分

修復只改工具 description 與 `invalid_patch`／`patch_context_not_found` 提示；parser、參數、保存及重播契約未變。74 個受影響 tests／靜態 Green，屬舊全 API 回歸之後的窄命令。兩輪真 API 短測為 2 completed、3 edits updated、0 rejected；輸入明確要求保留另一主題，只證工具可用與精確承接，未計 JD 增益。P1 r1 保留前已核全部 190 次 A instructions 與完整 ordered tools 在修復前後 byte identical；其餘有效案例用新空白隔離 schema。沿[等價核對][p1-proof]與下方失敗／修復原件。

四個 r2 實際 within-Work C 的 official saver adopted acknowledgement、原完整 C 及同位置 projection→下一 A 均已核：

| 案例 | 下一 A 採用項目 | 核查界線 |
|---|---|---|
| 倉儲 r2 P1 | full C 19＋筆記 0 | P1 無筆記投影。 |
| 倉儲 r2 P2 | full C 19＋筆記 1 | 同精確 C 保存投影逐字／hash 一致。 |
| 課務 r2 P1 | full C 11＋筆記 0 | P1 無筆記投影。 |
| 課務 r2 P2 | full C 22＋筆記 1 | 同精確 C 保存投影逐字／hash 一致。 |

公開 items 可獨立重算；opaque item 公開正文裁切，只有三處 original full-item hash witness 一致，不能宣稱獨立重算完整 bytes，也沒有虛構 numeric Step。倉儲 r1 P2／課務 r1 P2 的 C 是 pre-work，不能當 mid-work 證據。完整 sidecars 沿[修正批終態][repaired-final]、[補齊批終態][completion-final]及各案 `midwork-hash-audit-01.json` 定位。

[獨立焦點／返回稽核][focus-audit] SHA256 `90c29c10fdef73ca222e7804575486711f5cdc06d5fc3d174634c1da89dba16b` 核實際問句、公開員工原話及筆記，沒有讀品質判讀或用 keyword scorer：

- 倉儲 r1 P2 保住盤點調帳／核准未知，但未有效返回；倉儲 r2 P2 T12 問回盤點範圍，T13 回答仍未知，兩者均沒有補回核心後續。
- 倉儲 r1 P1 T13→T14 已由相關交接問句取得主管核准、財務調帳、更新後核對與待查並入稿；既有指南／上下文也能返回，不能歸作筆記專有能力。
- 倉儲 r2 P2 T2 把「通則適用範圍未知」錯換為「頻率未知」。變形在 C 前已發生，C 保住該文字不會還原原未知；終局口頭再提適用範圍也不抵消中段變形。
- 兩個課務 P2 都保存缺課後續未知，未取得完整代課／補課／追蹤交接答案。四場終局筆記均未清空；倉儲 r1 終局焦點仍是未回答問句，課務 r2 中段另有已知摘要混入導航筆記的限制。

這些是具體反例，未窮舉所有問句評分。精確 C 傳對筆記只證保存接續，不能證明 AI 問完、取得新理解或高品質完整 JD。

## 費用與負擔：有效案例與累計帳務分開

下表每格為 **usage 換算 US$（已准入 provider requests）**；Memory generation 合併 work_situation／work_understanding。數量是各生成／compact 路由的 provider requests，不是 Memory pipeline executions；`input_tokens` 計數路由未列入 generation，其原件沒有費用記錄，不推稱免費。每案換算與原 saved ledger delta 精確相符，八案自身費用合計 US$1.366484375；未知原預留不歸入這八案，也不稱 provider 發票。[三案分項原件][cost-three]與其餘五案 [課務 r1 P2][cost-c1p2]、[倉儲 r2 P2][cost-w2p2]、[倉儲 r2 P1][cost-w2p1]、[課務 r2 P2][cost-c2p2]、[課務 r2 P1][cost-c2p1]維護 roles／requests／tokens。

| 有效案例 | A generation | A compact | Memory generation | 合計 US$ |
|---|---|---|---|---|
| 倉儲 r1 P1 | 0.139326225（119） | 0.012696200（1） | 0.093010060（115） | 0.245032485 |
| 倉儲 r1 P2 | 0.121702130（80） | 0.013029300（1） | 0.065451765（70） | 0.200183195 |
| 課務 r1 P1 | 0.083418800（71） | 0.008878600（1） | 0.063568630（81） | 0.155866030 |
| 課務 r1 P2 | 0.121197955（97） | 0.013194500（1） | 0.017641370（30） | 0.152033825 |
| 倉儲 r2 P1 | 0.091760090（88） | 0.004538200（1） | 0.032894360（41） | 0.129192650 |
| 倉儲 r2 P2 | 0.137218025（85） | 0.017511100（2） | 0.014585550（18） | 0.169314675 |
| 課務 r2 P1 | 0.111809680（110） | 0.004953200（1） | 0.046499825（75） | 0.163262705 |
| 課務 r2 P2 | 0.110958280（78） | 0.004498700（1） | 0.036141830（37） | 0.151598810 |

P2 的 A 含 compact 合計 US$0.539309990，高於 P1 US$0.457380995；總費接近涉及 Memory 分項差異，不能說 A 較省。有效／不必要追問以實際語意反例核查，沒有把較少 request 或筆記呼叫當負擔／品質優勢。

核心[最終累計帳務][final-ledger]承接全部舊失敗、短測、中斷與 fresh 案例：spent US$1.966786395、occupied US$2.014531895，1,738 generations／14 compact／3,847 outbound／90,093,382 counted input。三筆未知 reserves US$0.013296750／0.011862125／0.022586625，共 US$0.047745500，全部保留；未推測未發送或釋放。這是核心比較終態，獨立選問優先順序 probe 另行施測與記帳，不混入本表或 primary 結果。

## 獨立選問小測

核心八案完成後，[單段選問候選](../data/jd-question-selection-2026-10-07/2026-10-07-priority-probe-results.md)另完成二十四案，全部匿名評閱先鎖後解盲。兩版直接中立目標問句同 1／6；有限窗口取得／入稿原版 1／6、候選 0／6，候選末問未答與未問分開。未證候選改善，未切換 production 選問指引。它是兩組都不啟用筆記的獨立小測，不改本頁 P1／P2 結果、八案費用或核心 ledger；時間取消授權、接續、額外費用與界線／引用限制只沿該實測記錄。

## 施測沿革：保留各時點原狀態

以下保留修復、續接與中斷的進度記錄；其中「施測中」「待原件完成」「尚未啟動」「等待回覆」均指當時狀態，現在的核心結論與未完門檻以上文為準。舊原件不覆寫，不因後續成功刪去成本或失敗。

2026-10-07 04:55 UTC，依使用者「筆記皆未建立就要先處理」的指示停止補足 v2；原程序及 8177 listener 均已確認為零。舊批已有五個完整案例，另有一場十九 Turn 完成但 closure 中斷；三個完整 P2 的八次筆記修改全部因格式被拒，正式筆記皆為 null。因此這批是工具可用性失敗的證據，不能用來判斷成功使用筆記後的 JD 增益。

失敗來自數字 diff header、錯誤 EOF 與不存在的 EOF anchor；原工具說明沒有可執行範例，錯誤提示重讀 null 也未解決格式。已只修正工具說明與格式錯誤的下一步提示，加入通用正文 V4A 建立／局部替換範例；parser、參數、保存及重播契約未變。74 個受影響測試與靜態檢查通過。[格式修正證據](C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/operational-evidence/format-repair/repair-evidence.json)

兩輪真 API 短測已完成：三次實際編輯皆成功、兩輪正式保存非空筆記。第一輪第二次修改以局部 hunk 保留另一主題的原 context 行；第二輪月報責任部分已清後，只留明細來源與比對方式等剩餘未知，新人資料的審核交接仍保留。實際 native within-Work C、官方 saver adopted acknowledgement 與下一 A 採用完整 C＋同位置筆記的原件亦已取得。只驗工具可用與這兩輪的保留；公開合成輸入明確要求保留另一主題，不代表自發規劃或最終 JD 增益。[短測語意與原件索引](C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/note-tool-smoke/note-smoke-repair-20261007/semantic-receipt.json)

短測新增 5 generations、13 outbound、89,448 counted input、1 compact，費用換算增 US$0.004681765；累計 spent US$0.997386170、occupied US$1.045131670，三筆未知預留不變。修正版本比較將另凍結；兩個完整 P1 的全部 190 次 A request 所保存 instructions 與完整 ordered tools 在修正前後逐 bytes 相等，其他原凍結來源也相等，可保留作基準；四個 P2 與兩個 P1 的重複二改用新空白隔離案例。舊 P2 格式失敗原件不替換、不混作修正筆記的效果樣本。[P1 等價核對](C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/operational-evidence/repaired-p1-reuse-proof.json)

修正版本 `formal-repaired-v2` 已在同一主對話核准機制下啟動，實際 manifest SHA256 為 `bbd4bf7bd2db6e66525a488817e115bd0e589ccd09ff3c6e1b96097c50c362e7`；474 份來源備份保持精確 bytes。帳務從成功短測承接，全額、計數與 08:30:34 UTC 截止不變。r2 的 45K 控制只在官方 saver 已保存、實際讀驗 adopted within-Work C 後解除，pre-work C 不解除；階段另記，不用意圖標籤充當證據。[修正版協議](diagnostics/repaired-comparison-protocol.md)、[實際 manifest](C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/repaired-comparison/formal-repaired-v2/manifest.json)

本版本第一次啟動在外送前遭 Windows socket 關閉檢查誤判而停止，沒有讀 key、連 PG 或新增費用。確認無 listener 後，改以官方 listener inventory 判斷；14 個必要離線反例與實際零 listener 查詢通過，保留第一次原件。這只修實驗啟動檢查，production 筆記格式修復未再變更。[啟動修正原件](C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/operational-evidence/repaired-comparison-v2-listener-red-green.json)

修正批次第一個倉儲 P2 已完成共同 closure：20 輪皆 completed、正式 HTTP 筆記皆非空，20 次編輯全部 updated，零拒絕；工具可用性已在完整自然訪談再驗一次。這場實際 C 是 pre-work，不能說成 within-Work 缺口保留證據。其 20 輪員工輸入與兩個保留 P1 的 40 輪輸入，均由當次 accepted source ID 對照每輪及最終正式訪談原文核對通過。第一組匿名品質評閱已鎖定，主代理尚未讀取判讀正文；全部四組鎖定前不下 JD 效果結論。[筆記機制原件](C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/repaired-comparison/formal-repaired-v2/warehouse-r1-P2/notes-mechanism-monitor.json)、[新 P2 原文核對](C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/operational-evidence/repaired-formal-sources-warehouse-r1-P2.json)、[保留 P1 原文核對](C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/operational-evidence/repaired-retained-p1-formal-sources.json)

課務 r1 P2 也完成 20 輪，20 次筆記編輯全成功、零拒絕，正式讀回皆非空，當次 accepted 原文核對通過；第二組匿名品質判讀已鎖定，正文仍未解盲。倉儲 r2 P2 則已在實際執行中取得 adopted C：官方 saved acknowledgement 與保存位置的筆記綁定核對通過，下一 A 帶入完整 19 個 C item 加同位置的一個筆記投影。18 個公開 item 可獨立重算 hash；opaque compaction item 的公開正文經裁切，只能核三處原 full-item hash witness 相等，不能宣稱已獨立重算其完整原 bytes。此為機制證據，不代替缺口保留及 JD 品質判讀。[課務筆記機制](C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/repaired-comparison/formal-repaired-v2/course_admin-r1-P2/notes-mechanism-monitor.json)、[課務原文核對](C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/operational-evidence/repaired-formal-sources-course_admin-r1-P2.json)、[實際 within-Work 原件](C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/repaired-comparison/formal-repaired-v2/warehouse-r2-P2/midwork-hash-audit-01.json)

`formal-repaired-v2` 隨後因外部回答裁決逾時停止，非筆記格式失敗：五案完整，另有倉儲 r2 P1 一輪 completed，但沒有 common closure。該題 pending 在 06:42:49.614 UTC 建立，decision 在 06:44:50.202 UTC 寫入，相差 120.588 秒；裁決代理讀後寫前跨上下文壓縮，沒有獨立時刻可拆分延遲。逾時 decision 沒有轉成員工 POST／披露，原件不改。三個完整新 P2 共 58 次編輯全部成功、零拒絕。終態 spent US$1.522732230、occupied US$1.570477730，1309 generations／11 compact／2902 outbound／69,365,297 counted input；三筆原未知預留保留。[停止與機制終態](C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/repaired-comparison/formal-repaired-v2/metadata-monitor-final.json)

已另凍結並啟動 `formal-repaired-completion-v1`：按 completed closure 機械保留五案，只 fresh 補倉儲 r2 P1、課務 r2 P2／P1。唯一旅程調整為回答裁決最多等 300 秒且受原絕對截止限制，等待後再核逾時；維持原 SelectorEventLoop、實際 HTTP／SDK／Writer、20 Turn、模型、指南與披露政策。3 個必要反例、實際零 key／provider dry-run、官方零 listener 與 476 份來源 snapshot 核對通過。累計帳務與總上限完整承接，不釋放預留、不延長 08:30:34 UTC。新 queue／原件獨立，舊 late decision 不重用。實際 manifest SHA256 `1f77287523c1ad8fdedfc7dc8e4256e6839b6c18596c23b90cb0b0b05918eb5a`。[補齊入口](diagnostics/repaired_completion.py)、[補齊檢查](C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/operational-evidence/repaired-completion-selector-final-checks.json)、[實際補齊 manifest](C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/repaired-completion/formal-repaired-completion-v1/manifest.json)

停止時最新 journal 的 spent 為 US$0.992704405，三筆未知預留共 US$0.047745500，occupied 為 US$1.040449905；919 generations、2,033 outbound、46,102,934 counted input、6 compact 全數承接。較舊的 batch-state 不覆蓋這筆帳務；未知請求不推測未發送或釋放。[停止原件](C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/operational-evidence/stop-20261007-0455/stop-metadata.json)

### 當時的對照條件

- P1：相同的分析／JD／顧問指南、共同焦點指引，以及既有 JD／Memory。
- P2：在上述條件加筆記指引、read／edit 工具、持久保存與全文投影。
- 兩種合成職務輪廓，各配對重複兩次；新隔離 schema、空白 JD／Memory、相同公開初始材料與私有事實披露政策。不同組依實際問題取得資訊，不固定第五輪更正或主動補答案。
- 重複一沿 production 原生換窗門檻；重複二以 45K 的受控 A mid-work 門檻取得實際 native C，首次成功後恢復原門檻。受控換窗不當成自然品質增益。
- 所有訪談與 JD 寫入走真產品 HTTP；結論讀正式 JD、正式員工原話與固定引用來源，沒有由草稿或最新 Memory 替代。

凍結條件與完整原件沿 [協議](protocol.md)、[正式首批 manifest](formal/manifest.json)及[修正後續接 manifest](formal-append/manifest.json)。續接 manifest SHA256：`b59e51e1b090955e7b2ff4b1cadec336471611761c8add73b748e0550cff17d6`；470 份來源備份逐 bytes 核對無差異。模型、production source、工具與指南維持一致，續接只修正實驗用量監測包裝。

### 當時的品質與機制進度

匿名評閱只收到正式 JD、員工原話與固定來源正文，沒有組別、筆記、工具、費用及對照 mapping。每場結果及配對判讀先固定，再解盲。判準在施測前凍結於[盲評 rubric](../../../plans/evidence/interview-plan-2026-10-07/blind-jd-rubric.md)。

條件披露的問題 payload 同樣不帶組別、筆記或工具，但其裁決代理兼任補足帳務審查，曾收到案例組別與進度的營運 metadata，不能宣稱該代理整段上下文完全盲組別。披露仍沿同一凍結政策與實際問題取證範圍；最終 JD 的匿名評閱是另一代理，補足時會將配對原件逐 bytes 複製到同一匿名目錄，避免不同磁碟路徑洩露批次順序。全部品質判讀固定後另核全場披露是否一致遵守政策。

四組配對的最終品質判讀、已披露但未入稿及未問到的重要漏項、無據／矛盾內容、有效與不必要追問、A／Memory 分項成本，待原件完成後填入。不得只報 P2 最佳一次；若 P1 也返回缺口，保留其既有指南／Memory 的效果。

native C 的機制核查須同時具備原 C 完整 item hashes、實際 adopted checkpoint，以及後續 A request 採用完整 C；P2 另核同位置保存的筆記 projection 與下一個 A 原 item hash。只看到 compact 呼叫或 Memory 角色壓縮不足以判為 A 換窗通過。工程故障恢復與真模型語意效果分開判讀。

### 中斷、資源及保留界線沿革

第一次正式首批在第一場第六 Turn 發生 Python 原生 access violation，沒有完成配對。該場及其正式保存資料仍保留，未列為完成的品質樣本。35 個已知 usage 的費用換算 US$0.022429100；最後一個未知請求的 US$0.013296750 預留維持占用。沿 [中斷帳務](formal/interruption-audit.json)、[原生事件](formal/native-crash-events.json)及[診斷](diagnostics/results.md)。

零 provider 的有限重播在原監測包裝下重現 native Red。移除包裝的兩次對照、新包裝的兩次對照均各完成 2,000 次 SDK 與原 checkpoint 重播。新包裝明確擁有並清理所消費的 iterator，保持原 bytes；production／CPython 3.14.7／鎖定套件不改。不宣稱已定位 CPython 或 SDK 原生根因。[獨立 cleanup 審查](../../../plans/evidence/interview-plan-2026-10-07/runtime-research.md)與[額度續接審查](../../../plans/evidence/interview-plan-2026-10-07/append-budget-review.md)記精確界線。

原 `formal-append` 批次依原上限自然停止，不改寫其 manifest。第一個完整案例耗時約 31.65 分鐘、counted input 13,340,408，原 40M counted input 與四小時上限不足以完成八場；估算原件沿 [case1 operational estimate](diagnostics/case1-operational-estimate.json)。

依本次完成真實比較的授權，另準備有界補足批次：原程序及 Memory／server 全部停止後才啟動。正式首批、續接及補足批次合計上限為 US$8、3,000 generations、7,000 outbound、180M counted input、32 compact，絕對截止為 2026-10-07 04:30:34 UTC；原未知請求預留繼續占用，不重新從零記帳。維持相同模型、runtime、指南、工具、每場 20 Turn 與換窗政策。先導耗費另外揭露。

保留所有中斷與結果；只按共同 closure 是否已提交且該 Turn completed 的機械判準選需補足的案例，不按品質或 Memory 成敗重跑。已完成案例不重跑；有歧義、缺少帳目或來源漂移則停止，不推測可用餘額。正式品質解盲仍須等四組匿名配對判讀全部固定。

續接批次另遇工作磁碟耗盡：第一場 20 Turn 與共同 closure 完整保存；第二場第十二輪保存結果失敗，未取得完整 closure。finally 帳務仍完整保存，已知累計 US$0.341333835，原及新增未知預留共 US$0.025158875，occupied 為 US$0.366492710。最後一筆准入比 journal 多出的計數與預留須另做嚴格核對，不推測未發送或釋放預留。既有資料不清除；本次可重建的 mypy cache 移到另一個可寫磁碟，補足輸出也將改到該處，原 production 與模型材料不變。磁碟中斷原件保留，補足批次尚未啟動。

補足入口及精確磁碟審核已完成：獨立 56 tests、Ruff／format、原 470 檔與新增 6 檔逐 bytes freeze 通過；全部 journal 重建後的未知差額為 1 generation、1 outbound、0 counted input、0 compact。spent、兩筆預留及原 351 generations／762 outbound／17,328,720 counted input 全部承接。[恢復與補足證據](diagnostics/disk-recovery-and-supplement.md)保留命令、hash 與離線界線。

兩次同一啟動動作均被自動核准審查拒絕，沒有執行、沒有新增外送或費用。第一次要求具體資料與目的地的授權；第二次在補上合成來源、新空白檔案、只送 OpenAI API 與既有使用者真 API 授權後，仍要求可信使用者訊息明示合成 payload 與 OpenAI 目的地。沿 [外送範圍證據](diagnostics/outbound-scope-proof.md)與[拒絕原件](C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/approval-review-rejections.json)查閱。已提出唯一必要的澄清，等待回覆；不重試或換入口繞過。固定截止與總費用界線沒有因此後移。

2026-10-07 02:53 UTC 恢復：使用者承接上述具體合成資料／OpenAI API／正式總額 US$8 的澄清，回覆「好可以測試」，並追加選問優先順序的隔離測試方向。舊補足仍未啟動，04:30 UTC 僅餘約 97 分鐘，無法完成原七場；另凍結新未啟動批次 revision，絕對截止為 2026-10-07 08:30:34 UTC，其餘費用、計數、材料、模型及機械選案界線不變。原 04:30 preflight／原件不改寫；新版須重新核 deadline、anchor、freeze 與全部帳務承接，再走相同核准審查與執行方式。

新增的冷藏／錯儲位／旺季與選問優先順序測試，沿獨立前批原件診斷，不改本頁原八場 prompt／披露政策或結果；優先完成原對照及匿名品質鎖定，再以剩餘額度另凍結小型候選比較。

補足 v2 已透過主對話的相同 `exec_command`／`require_escalated` 核准機制正式啟動。子代理三次被拒時未外送；主對話具有使用者直接確認的可信上下文，沿同一入口與資料範圍重審後通過，沒有停用審查或換網路路徑。實際 [v2 manifest](C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/formal-supplement-v2/manifest.json) SHA256：`a93fa4f30d499e3051220683b01e84ebc31412317a54653660996ae20fef4f33`；原 470 source 與 9 份補足檔、全部 prior 原件逐 bytes 核對一致。新批從原帳務接續，七場排程不變，沒有同時另開付費批次。

本次是合成材料的有限配對觀察；不能由八場推論統計顯著、真人負擔或一般職務均有增益。費用是觀察 usage 按凍結價格換算與預留，未回報為 provider 發票。

[quality-lock]: C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/repaired-comparison/quality-lock.json
[final-ledger]: C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/repaired-completion/formal-repaired-completion-v1/batch-state.json
[review-1]: C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/repaired-comparison/blind-quality-reviews/paired-review-1.md
[review-2]: C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/repaired-comparison/blind-quality-reviews/paired-review-2.md
[review-3]: C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/repaired-comparison/blind-quality-reviews/paired-review-3.md
[review-4]: C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/repaired-comparison/blind-quality-reviews/paired-review-4.md
[policy-six]: C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/operational-evidence/repaired-disclosure-sixcase-audit.md
[policy-c2p2]: C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/operational-evidence/repaired-disclosure-course-r2-P2-audit.md
[policy-c2p1]: C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/operational-evidence/repaired-disclosure-course-r2-P1-audit.md
[p1-proof]: C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/operational-evidence/repaired-p1-reuse-proof.json
[repaired-final]: C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/repaired-comparison/formal-repaired-v2/metadata-monitor-final.json
[completion-final]: C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/repaired-completion/formal-repaired-completion-v1/metadata-monitor-final.json
[focus-audit]: C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/operational-evidence/repaired-focus-and-return-audit.md
[cost-three]: C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/operational-evidence/repaired-cost-3complete-cases-v2.json
[cost-c1p2]: C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/operational-evidence/repaired-cost-course_admin-r1-P2.json
[cost-w2p2]: C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/operational-evidence/repaired-cost-warehouse-r2-P2.json
[cost-w2p1]: C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/operational-evidence/repaired-cost-warehouse-r2-P1.json
[cost-c2p2]: C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/operational-evidence/repaired-cost-course_admin-r2-P2.json
[cost-c2p1]: C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/operational-evidence/repaired-cost-course_admin-r2-P1.json
