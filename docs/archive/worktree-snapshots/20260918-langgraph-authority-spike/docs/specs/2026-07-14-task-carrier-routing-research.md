---
title: 任務載體路由——何時綠字直落/何時卡片/何時盤(intake 與自取)
date: 2026-07-14
purpose: 維護者質疑 2026-07-13 §7 b 案「任務=AI 彈盤帶預勾」:AI 確定有的任務為何不直接加?
         盤的意義是不是「第一次訪談讓 AI 知道他大概做什麼」而非「確認 AI 勾的對不對」?重研翻案
source_discipline: 大廠一手文檔(GitHub Copilot docs/VS Code、Google PAIR)+訪談式產品先例
                   (TurboTax)+recsys 冷啟動文獻;本 repo 一手事故資料(6f807f1e/53dcde00)
---

# 任務載體路由:證據→綠字、盤=人拉、不確定→卡片

## 1. 問題(維護者兩問,2026-07-14)

1. 「LLM 確定有這個任務,感覺可以讓他加——彈窗其實沒必要。」b 案(AI 彈盤帶預勾)
   把 AI 已確定的東西又推給人選一次=重工。
2. 「這選單的意義比較像他第一次訪談,讓 AI 知道他大概做什麼;比較不像確認 AI 勾的
   對不對。」盤的真價值=員工**自報**(快速勾出自己有的工作),不是 AI 的審查介面。

## 2. 先例(外部權威)

| 來源 | 模式 | 對我們的含義 |
|---|---|---|
| **GitHub Copilot**(docs.github.com/copilot、VS Code docs) | **ghost text=單一高把握建議直接寫在游標處**,Tab 接受/Esc 拒絕;備選面板**不主動彈**,人按 Ctrl+Enter 自己拉;低把握寧可少出建議 | 高證據單筆=inline 直寫+就地審(=我們的綠字✓✗);瀏覽多候選=人拉取,永不推臉上 |
| **Google PAIR**(pair.withgoogle.com) | 「信任高或錯誤風險低→多自動化」;手動確認建立信任;自動化必附 undo;act/suggest/ask 按信心分層 | 有硬證據+可一鍵✗=自動寫;沒證據=降為問 |
| **Microsoft HAX**(2026-07-13 §7 已引) | 打斷要挑時機;心流中被建議打斷=生產力損失 | 邀請只在對的時機遞一次 |
| **TurboTax**(Appcues 拆解、Intuit 個人化開場案例) | 開場**自我分段**勾「哪些適用於你」→ 之後訪談 conditional logic **只深問勾過的主題**(progressive disclosure);行業個人化開場組續用率 +11% | 開場粗勾=intake,訪談只做挖深——維護者的直覺就是這個模式 |
| **recsys 冷啟動 preference elicitation**(Spotify/Netflix onboarding;文獻) | 註冊先勾喜好建初始 profile;**low-burden 優先:問太多→跳過/棄坑** | intake 必須 offer+可跳過,不是關卡(我們才剛拆掉職類閘,勿再蓋任務閘) |

## 3. 關鍵洞察

1. **「AI 確定」有確定性判準,不用 LLM 自報信心**:verify ② 的逐字 quote。裁剪
   precheck 本就要求逐字引文——員工明說「我每版上線前跑回歸」且引文過驗,即硬證據。
   路由可完全確定性:**有 quote=直落;無 quote=不落**。
2. **選單經濟學**:勾選=0 token、0 延遲、confirmed 直落(0028 D9);訪談每回合燒錢。
   能自助的讓人自助,LLM 留給說不清的(隱性知識、細節、自訂任務)。
3. **選單=辨識代替回憶**(Nielsen):對「認得出自己工作的人」是全系統最便宜的輸入
   通道(掃 2 分鐘=訪談枚舉十幾回合);對「說不出官方語言的人」是牆(6f807f1e 卡死
   22 回合的現場)。→ 位置決定價值:當關卡=事故,當工具=加速器。
4. **盤上預勾疊加層是偽需求**:AI 確定的不該等人來盤裡找(直落綠字);AI 不確定的
   不該預勾(誤導);人自報時不需要 AI 意見(乾淨的池最快)。疊加層退役。

## 4. 裁決(維護者 2026-07-14 定案;ADR 0032)

| 時機 | 載體 | 性質 |
|---|---|---|
| 開場冷啟動(參考集合非空∧文件無任務∧未 dismiss) | **盤=intake**:聊天邀請卡一鍵開盤;可跳過 | 人自報,offer 一次 |
| 訪談中,官方任務有逐字證據(quote 過 verify ②) | **綠字直落**(op→verify→`_pending`),✓/✗ 審 | AI 寫、人審 |
| 訪談中,AI 不確定(無 quote;候選 ≤3) | **聊天卡片**點頭(職類卡同款) | AI 問、人選 |
| 隨時 / 收尾補漏 | **盤自取**(工具列;尾聲顧問 offer 掃一遍) | 人拉取,0 token |

廢止 2026-07-13 §7 裁決①③的「任務=AI 彈盤(consent-triggered)+盤帶預勾」段;
維持 §7 ②「盤上人工勾選=confirmed 直落不套綠字」與 focal-ask 單槽原則。

## 5. 設計要點

- **intake 觸發=確定性三布林**(引擎判時機、人按開;LLM 只配話術):參考集合非空 ∧
  文件無任務 ∧ 無 `task_board_dismissed` 事件;widget 單槽,職類卡優先。條件自癒:
  使用者自己從工具列勾過任務→「文件無任務」不成立→邀請卡永不出現。
- **邀請卡兩出口**:「開任務盤(約 2 分鐘)」→ 前端開現成 GlobalTaskPickerMenu(乾淨,
  無疊加層);「用聊的就好」→ `task_board_dismissed` 記帳 → 下回合顧問知情改口頭裁剪,
  不重推銷(occupation_dismissed 同款)。
- **綠字直落**:裁剪 quote-backed 結果 → **確定性映射**成 add-task op(ref=池 URN+
  quote src)→ 既有 verify 六查 → `_pending`。家職責不在文件 → 確定性建**官方殼**
  (name=池 unit、src=官方、同標 `_pending` add;只允許池內官方名)。寫入路徑不變量
  不破:LLM 只出判斷,op 由確定性碼組(records_to_ops 同哲學)。
- **退役**:`interview:curation` 隨叫端點+web `lib/curation.ts` 預勾疊加層(T12 黑洞
  正式收屍——run_turn 的 `picker:"task"` widget 一併停發)。

## 6. 風險

- 綠字量暴增 → verify ⑥ 尺寸查在;✗ 一鍵即消;裁剪本就分批。
- 殼職責誤建 → source check 限池內官方名;✗殼=巢狀還原(殼+任務一起消)。
- intake 卡騷擾 → 單槽+dismissed 記帳+條件自癒;顧問話術規則「別推銷第二次」。
- 新手仍不開盤 → 零損失:口頭路照走(裁剪 quote→綠字),盤只是捷徑不是關卡。

## 來源

- GitHub Copilot:[code suggestions 概念](https://docs.github.com/en/copilot/concepts/completions/code-suggestions)、[VS Code inline suggestions](https://code.visualstudio.com/docs/editing/ai-powered-suggestions)
- Google PAIR:[Guidebook](https://pair.withgoogle.com/guidebook/)、[codelab(信任高/風險低→多自動化)](https://codelabs.developers.google.com/codelabs/pair-guidebook)
- TurboTax:[Appcues UX 拆解](https://www.appcues.com/blog/how-turbotax-makes-a-dreadful-user-experience-a-delightful-one)、[個人化開場 +11%](https://shairatuazon.com/portfolio/turbotax-personalized-onboarding)、[Onramp onboarding 教訓](https://onramp.us/blog/customer-onboarding-experience-turbotax)
- 冷啟動:[Vinija recsys 筆記](https://vinija.ai/recsys/cold-start/)、[freeCodeCamp Cold Start](https://www.freecodecamp.org/news/cold-start-problem-in-recommender-systems/)
- 本 repo:[`2026-07-13-occupation-consent-write-research.md`](2026-07-13-occupation-consent-write-research.md)(§7 前版裁決)、ADR 0028/0030/0031;session 6f807f1e/53dcde00 一手逐字稿
