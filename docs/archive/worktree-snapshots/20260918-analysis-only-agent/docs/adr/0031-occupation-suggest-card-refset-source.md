# 0031. 職類建議卡進對話流;引擎參考碼=profile∪doc;參考集合維持人選

日期:2026-07-13 · 狀態:Accepted

## Context

新手 persona 真人手測(session `6f807f1e`)卡死:員工口頭同意加選職類,但系統要求
UI 手勢(0028 D1 彈 picker),新手不點;且 0029 把選職類脫鉤成只寫
`job_profiles.selected_ocs_codes`,而訪談引擎(0030,建於 0029 前)的帳本/池/任務盤
**只讀文件**——profile 有碼引擎也看不見,22 回合鬼打牆、書記零落地。
研究(specs/2026-07-13-occupation-consent-write-research.md):Anthropic
trustworthy-agents(可逆動作不需阻斷核可;93% 核可率=確認疲勞)、agentic-UX
undo-first 共識、0028 驗屍同型死區。

## Decision

1. **引擎有效參考碼=`profile.selected_ocs_codes ∪ 文件碼`**(不變量):
   `has_occupation`/`derive_phase`/`next_gap` 收 `ref_codes`;任務池/書記官方池/
   顧問前綴 2 都吃聯集(`service._ref_codes_ordered`,文件主基準優先)。
2. **職類建議改聊天卡片**(推翻 0028 D1「不另做聊天 widget」的**職類段**;task 照舊
   開編輯器 picker):widget `precheck=[{code,name,reason}]` 只含**本回合搜尋真實命中**
   的碼(確定性,不虛構);前端 `OccupationSuggestCard` 預勾+理由,三出口=
   確認(→`useSetOccupations`,與 picker 同一條人用寫入路)/其他(回聊天)/
   ✕(收合+`occupation_dismissed` 記帳)。
3. **參考集合維持人選**——**否決**「顧問 WRITE 工具代寫」:維護者裁決(模擬新手後
   仍要人最終點擊)。重啟條件:上線後新手漏斗數據顯示卡片仍過不去,再議代寫
   (研究已備好守衛設計:命中集白名單+回條+undo)。
4. **dismissed 知情換話術**:關卡後顧問下回合收 context 指示(白話解釋+安撫,
   不複讀同批建議)。**反騷擾規則(同批建議只出一次卡)緩做**——維護者裁決。
5. 常駐 chip:參考集合空時面板頂「📌 待選」為唯一重入口(開既有 picker modal)。

## Consequences

- ✅ 新手口頭聊完→卡片一鍵落參考;引擎不再對已選職類視而不見(回歸測試釘死)。
- ✅ 文件寫入路不變量不動(參考集合在 profile;卡片走既有 PUT)。
- ⚠️ 0028 D1 的職類段由本 ADR 取代;task picker 流不變。
- ⚠️ 反騷擾緩做=同批建議可能重複出卡(靠換話術+chip 緩解);上線觀察再補。
