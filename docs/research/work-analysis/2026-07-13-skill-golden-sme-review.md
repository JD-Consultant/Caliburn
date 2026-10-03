---
title: 判準教材八檔 + golden JD-golden-001 的 SME 自審紀錄
date: 2026-07-13
purpose: 維護者非 JD 領域專家;由 agent 以權威一手來源審定八檔 SKILL.md 與 golden reference
source_discipline: 每條判準回一手權威(iCAP 指引官方平台 / O*NET / ESCO / SFIA / Bloom-Krathwohl);
                   代碼類主張一律以「系統注入的官方池」為準,不憑記憶背碼
---

# SME 自審紀錄(2026-07-13)

## 0. 為什麼改自審

維護者非 JD/職能領域專家,原「維護者審改才定案」的 SME gate 卡住。依「維護者全自主
(自研自查自決+記錄依據)」原則改制:agent 以**一手權威來源**逐條複核八檔教材與
golden,發現即修、留本紀錄當依據。判準的最終實戰效度仍由 T11 考卷(promptfoo
Simulated User + deterministic 斷言)+ 人工試聊驗證,非靠本次靜態審。

## 1. 權威來源(本次實際複核者)

| 來源 | 用於 | 複核方式 |
|---|---|---|
| iCAP《職能基準發展指引》官方平台 | K/S/A 定義、態度位置規則、級別表 | 2026-07-13 WebFetch `icap.wda.gov.tw/ap/knowledge_introduction.php` 逐字複核 |
| iCAP 各職類基準(平台檢索) | A 碼「每基準各自編號」之證據 | **兩份官方衍生來源對 A01 各說各話**:一般檢索 A01=主動積極;訓練行政人員基準 A01=親和關係——同碼不同名=代碼非全域固定(PDF 一手全文本次無函式庫可抽,以此矛盾為據) |
| O*NET Content Model 1.C / Task Writing Guidelines | Work Styles、任務句式禁則 | 官方 onetcenter.org(Work Styles 16 項;2024 No.090=新結構研究) |
| SFIA 9 | 級別佐證四軸措辭 | sfia-online.org:通用屬性共 5 項(autonomy/influence/complexity/knowledge/business skills) |
| ESCO escopedia | K/S 句式(名詞 vs 動作) | Knowledge/Skill 官方定義(對齊 EQF) |
| Krathwohl (2002) | 可觀察動詞、名詞=知識維度 | Theory Into Practice 41(4) |

## 2. 逐檔審定結果

| 檔 | 結論 | 修正 |
|---|---|---|
| consultant-principles | ✔ 合格 | 無(六規則+BEI 探針庫,對 iCAP p29-32 BEI/CIT) |
| probing | ✔ 合格 | 無(訊號觸發+laddering 2–3 層+holding;under-probe 罰則) |
| duty-task-structure | ✔ 合格 | 無(iCAP 功能分析法句式 + O*NET Action>Object>Purpose 禁則逐條) |
| output-writing | ✔ 合格 | 無(合法 n/a 規則逐字對 iCAP p37) |
| behavior-indicator | ✔ 合格 | 無(STAR/ABCD + Bloom 可觀察動詞 + 禁用清單) |
| level-judgment | ✔ 微調 | **SFIA「四軸」→「通用屬性 5 項,借前四項」**(SFIA 9 實為 5 項,原文漏 business skills) |
| ks-distinction | ✔ 修正 | **移除「S01–S24 全域目錄」錯誤**——S/K 碼每基準各自編號,無全域固定目錄;改「以系統注入官方池為準」 |
| attitude-writing | ✔ 修正 | **移除固定「A01–A14」代碼綁定**——A 碼每基準各自編號(反例:BHR2422-011v2 A01=親和關係);保留 14 項**名稱**參考清單,代碼一律以官方池為準 |

## 3. 最重要的一條錯誤(修正前會產生幻覺官方碼)

原三檔(ks-distinction / attitude-writing)把 iCAP 的能力碼寫成**全域固定目錄**
(S01–S24、A01–A14)。**這是錯的**:iCAP 的 K/S/A 碼是**每一份職能基準各自從
K01/S01/A01 起編**。證據:兩份官方衍生來源對「A01 是什麼」給出不同名稱
(一般檢索 A01=主動積極;訓練行政人員基準 A01=親和關係)——同碼不同名,
即代碼綁定職類、非全域固定。

**風險**:教材若教模型「A14=謹慎細心」,模型可能在**別的職類**憑記憶寫出錯誤官方碼。
系統的防線本來就在——scribe 池通道的 pool_id 從**當回合注入的官方池 enum** 挑
(zero-hallucination),verify ③ 再擋 ref∉池——但教材不該和這條防線唱反調。
修正後三檔統一口徑:**名稱可教,代碼一律以系統注入的官方池為準,不背碼**。
golden reference.md 的「A14 謹慎細心」一併改為「謹慎細心(代碼依該職類官方池)」。

## 4. golden JD-golden-001 審定

- reference.md 11 槽細節、O/P/K/S 句式、態度佐證**對黃金範本樣張 §4.2 一致**;
  句式合格(K 名詞化、S 動作短語、P 可觀察動詞含情境標準、O 有形交付物)。
- 已修:態度代碼綁定去除(見 §3);SME gate 說明改自審制 + 指向本紀錄。
- rubric.yaml:items 二元判定 + Harvey 式負分(F2 臆造 −4、F3 自誇當事實 −2)結構合理;
  reference 過 rubric 應滿分留待 Phase 2 grader 驗(judge=cross-model-family)。

## 5. 未決(交實戰驗證,非本次靜態審能定)

- 判準的**實戰效度**:T11 promptfoo Simulated User 四 persona + deterministic 斷言
  (一問收尾/位置碼不可寫/Source Score≥0.8),需 live server;=維護者 npm run up 手測那輪。
- 態度「2–4 條」為本 repo 校準值(官方只規定「挑選、可增列」未定條數);校準後可改。
- level-judgment 跨體系級號不硬換算(iCAP 6 級 vs SFIA 7 級 vs EQF 8 級,官方無對映)。
