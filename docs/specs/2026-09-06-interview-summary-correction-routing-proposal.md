# Q019-MEM-SUMMARY-01：詳記更新與更正回查提案

> 2026-09-06 · **G3 已同意；Owner 後續授權隔離施工，G4 工程接線見 §7。WORKING，不是完成報告。**
> Owner 最新准「現在就是要實作完整」。採下述已同意接法，工程接線見 §7；實作／驗證進度見[結果紀錄](../../.worktrees/analysis-only-agent/docs/specs/2026-09-06-summary-reextraction-results.md)。文內三方案及 §6 保留前階段決策理由，不重新開啟 Memory 選型。
> 入口：[current decisions](../current-decisions.md)。官方完整證據：[詳記更正 source review](2026-09-06-openai-rollout-summary-correction-source-review.md)；既有接法：[Q019 Memory](2026-09-06-analysis-only-agent-memory-design.md)。

## 1. 這次要決定什麼

同一案例先後被補充或更正，怎樣讓主顧問找到目前說法，又能深入讀取案例細節？只處理這一題；不重選框架、不新增案例資料庫、不開 API／UI 或付費測試。

**先區分兩種效果：**

- 沿目前 Memory 找到更正，再讀相關詳記／原文：有直接 OpenAI 流程依據。
- 任意打開一份舊詳記，系統都自動附帶此後所有更正：現有研究沒有證明 OpenAI 提供此保證；本案也尚未提供。

後者不能被前者偷換，也不能只靠一句「以最新理解為準」就宣稱問題已完全解決。[官方讀取指示][R1]、[本案證據界線](2026-09-06-openai-rollout-summary-correction-source-review.md#4-回查舊詳記與-live-update仍有界線)

## 2. 三種接法與推薦

| 接法 | 效果、成本與差異 | 判斷 |
|---|---|---|
| 每次重新抽取整個持續中的訪談，替換現行詳記 | 接近 Codex 同 thread 重抽；但來源愈長，輸入／輸出成本愈高，官方抽取還可能截斷，不能保證所有細節都看過 | 不建議用在無限累積的單訪談。[重抽][R7]、[保存][R2]、[輸入上限][R3] |
| **按段保存詳記，整併時維護目前說法及更正引用；需要時重抽同段** | 學習跨 rollout 整併與漸進回查，不每次重讀全部原文；保留當時脈絡，但依賴模型辨識更正、寫好路由及正確查找 | **Owner 已同意此效果邊界，WORKING。** 分段是本案映射，不稱原廠一模一樣。[整併][R4]、[讀取][R1] |
| 找出所有受影響舊詳記，逐份重寫／加更正通知 | 可追求直接開舊詳記也看到更正，但需辨識受影響範圍、同步引用與處理漏更新；目前未查到原廠全面傳播的契約 | 有更強需求時才另設計；不把普通檔案編輯能力當作此功能已完成。[證據界線](2026-09-06-openai-rollout-summary-correction-source-review.md#3-不同詳記談同一案例比對與修訂在哪裡發生) |

**推薦演進說明：**前輪優先評估「詳記有可重建現行內容」，仍肯定同一抽取範圍可重建；但它本身解不了跨範圍更正。比較後選第二列，不自動擴成第三列。此推薦原為待審，現已獲 Owner 同意其效果邊界；不是為保留舊程式而拒絕新能力，也不將同意擴大成全面詳記同步或 production 施工。

## 3. 推薦流程：原文、詳記與目前 Memory 各做什麼

以下為 **Caliburn WORKING 接法**；引用是依據，不代表 OpenAI 使用相同範圍、檔名或資料庫。

1. **原始訪談保留。**「先前怎麼說、後來怎麼更正」都可回查，不用改寫歷史聊天。[原始紀錄與摘要分工](2026-09-06-openai-rollout-summary-correction-source-review.md#2-同一對話詳記可重新產生不是只累積新副本)
2. **B1 整理本批問答。**詳記敘述本批補充／更正與未解事項；候選把會影響記憶使用的變化交 B2。沒看過的舊脈絡不能自行補成事實。原文位置由 Runtime 提供，模型不填假 ID／時間。[詳記內容指示][R5]
3. **B2 比對相關既有 Memory，必要時讀舊詳記。**有明確更正就更新目前說法；有歧義保留未知，不用「較晚一句」強行覆蓋。[整併衝突／引用規則][R4]
4. **案例更正也可成為正文的有用知識。**即使一般工作模式沒變，若不記錄就會讓後續誤用舊案例，仍在相關主題下留簡短更正、案例名稱／別名與新詳記引用。不是將所有案例全文塞進正文，不設必填 correction 表單。這是本案內容政策，依原廠保留有用知識、處理衝突及主題引用的方式映射，**不是原廠保證模型一定抽對**。[R4]
5. **A 正常由小導覽→目前正文→選中詳記→必要原文逐層讀取。**找到案例時先讀目前說法與相關引用，才展開歷史細節；不把詳記當成永遠正確的案例現況。小導覽只需維持可搜尋的主題／別名，不必每改一句詳記就改導覽。[R1]
6. **C 沿用局部修補分工。**若前台先發現已核實的過時記憶，可修正文並引用當輪問答，不等待 B。B 之後產生詳記，再整理相應引用；C 不是重建全部詳記。[Sandbox live update][R6]

**同段重抽與跨段更正不同：**某份詳記漏讀／誤讀自己的原文時，可用該來源重抽並發布新結果；不能只重抽早期原文，卻期待模型憑空知道晚期更正。若要把後續來源合進同一份詳記，輸入與來源引用都必須包含後續內容，這屬另需確認的擴大更新範圍，不能僅換版本號宣稱完成。[重抽][R7]、[保存][R2]

## 4. A 案例示例：會保留兩份嗎？

這是說明效果的人工例子，不是模型實測。

- 早期詳記：當時說「A 網站由我做前、後端」。
- 後續詳記：員工明確更正「A 的後端是同事做，我只做前端」，保留本次問答引用。
- 目前正文的相關主題：A 網站目前確認只負責前端；先前全端說法已更正，最新依據指向後續詳記，需要歷史脈絡再讀早期詳記。其他案例的特殊細節留在各自詳記。

所以**可能保留兩份不同時段的詳記，但不應把兩種互斥說法都當成目前成立的理解**。如果只是「B 網站負責前後端」，不能自動更正 A；若同一案例其實是工作責任後來變動，也不能改寫成早期從未負責後端。

若 A 只取得舊詳記、漏讀正文或 B 尚未整理，仍可能不知道後續更正。近期問答／C 能在已知情況補足，但不能當成永不漏讀的保證。此限制必須保留在驗收描述，不承諾「只要存了就絕對不會忘」。

## 5. 框架能做什麼，哪些不是自動提供

沿用已追過底層的[StoreBackend 接法](2026-09-05-memory-artifact-native-backend-design-review.md#1-框架底層真正如何接力)：StoreBackend／FilesystemMiddleware 承接保存、讀取、搜尋與編輯；真實地址及來源 header 由 Runtime 提供。框架不決定兩段是否同案例，也不自動判斷新說法是否更正；那是 B1／B2／A 的 instructions 與模型工作。[官方 backend](https://docs.langchain.com/oss/python/deepagents/backends)

- 本推薦不新增「案例更正 Agent」、強制每輪補查模型，或另一套記憶資料庫。沿既有 B1、B2、C 使用內容與引用。
- 比較重點不是零額外成本：B2 必要時要多讀相關詳記，正文的更正路由也佔 token；未測量自然模型品質或實際費用，不能保證固定零增量。
- 同段重抽替換需要新 artifact 與引用一起進入已發布理解；原生 Store 的寫檔能力不是此一致性的保證。前階段沒有改程式；本次工程接線與實作狀態已補在 §7／結果紀錄。
- 不讓模型編造更新時間、存檔版本與引用；沿 Runtime 回傳的真實地址。詳記路徑不是案例身份，也不能藉 slug 判定同案例。

## 6. 審核界線與下一步

**已決定：**先採「由目前 Memory 記錄更正並路由到相關詳記」，不加「任意舊詳記直接打開都自動附最新更正」的全面保證。這題不再反覆請 Owner 重選；若改要求後者，才重新研究設計。

**Owner 追問的精確答案：**詳記可以在需要時重抽更新，不是每輪全部重寫；跨段更正仍依 §3 更新目前正文與引用。若詳記誤讀原文，重抽是在修正抽取結果；若員工後來改口，則新問答是新增來源，不能僅重抽舊來源就期待得到更正。原始訪談不改。研究已足以停止廣泛選型，下一步把重抽觸發、替換／引用發布、失敗不破壞已發布內容與最小驗證寫入短計畫；這些尚不能宣稱程式已做好。

- **Status：**Owner 已同意，WORKING；G3 效果邊界收斂，轉 G4／短計畫準備，不是 G7 已完成。
- **Evidence：**回讀現行入口、流程、詳記 source review、Memory 設計與 backend trace；OpenAI 固定 SHA 沿前稿，重讀整併／reader 直接證據；補查官方 backend 頁，未廣泛重做研究。
- **Affected：**本稿只持有選項／例子／推薦；source review 留官方事實，register 指向本稿，既有 Memory 保存／發布仍有效。
- **Reopen：**找到官方跨詳記傳播的新證據，或 Owner 要求直接舊詳記讀取也必帶更正，或小型情境驗證證明路由不足。不得只因下一輪換人閱讀就重做同題。
- **Next gate：**補此小切片的 instructions／保存讀取設計、施工計畫與最小驗證，不再重問同一效果選擇；本輪只記錄同意與回答準備度，未施工、不啟動 Task3、不改資料、不付費測試、不 commit／push。

## 7. 已授權的小切片工程接線

Owner 最新要求「現在就是要實作完整，細節不要做錯」。本節接續 §6 的準備度，授權限 `analysis-only-agent` 隔離 Memory；不以舊的「本輪未施工」阻擋此次新授權。計畫：[summary re-extraction](../../.worktrees/analysis-only-agent/docs/plans/2026-09-06-summary-reextraction.md)。

- **重抽入口：**Runtime 指定既存詳記真實地址，從系統寫的來源 header 取回相同原文範圍與 context-only 範圍。檔首格式標記、明確空值及終止行區別模型正文；舊實驗格式可讀，但缺可信 header 不猜測重抽。驗證原保存範圍而非重新選窗。重抽自己的來源，不偷偷擴成後續所有訪談。模型仍只填既有三字串，不新增 ID／版本／引用欄位。[R2][R7]
- **資料保存：**重抽結果另存一對完整詳記／候選，舊地址仍可回查。本案既有 immutable artifact＋published head 不改；OpenAI 的同邏輯來源更新概念，不等於必須照抄檔案覆寫實作。新舊替換地址由 Runtime 交給 B2，slug 不是案例 ID。[R2]
- **普通抽取不受影響：**重抽使用獨立的技術 checkpoint 路由，不是新員工聊天室；不回退普通 B1 的已處理位置。失敗用 resume 繼續，不再呼叫已保存結果的模型節點。沿用 LangGraph 的 [durable execution](https://docs.langchain.com/oss/python/langgraph/durable-execution)；路由命名是本案接線，不冒稱原廠共識。
- **整併與發布：**B2 按新產物辨認一次整併，不再只以來源相同就跳過。讀目前正文，必要時讀舊詳記，核對受影響結論與引用；案例更正也須被記下。模型處理語意，系統只驗格式／地址／發布版本，不聲稱能確定語意必然正確。[R4]
- **不回退背景進度：**重抽整併沿既有 `repair` 發布語意：更新工作理解／導覽但保留背景 source cursor；記錄重抽來源供後續 stale 重整辨識。這是既有本案發布協調接點，不新增資料表、不假稱是 OpenAI 的交易協定。
- **一致性：**新詳記可以先保存，A 仍看舊 published head；B2 完成驗證／CAS 發布後 A 才沿新正文引用讀新詳記。失败不破壞旧 head；B/C 相撞依既有 stale reload 路徑重做 B2，不重抽 B1。舊詳記未刪除，也不做自動最新版本跳轉。
- **驗證與界線：**測同段重抽、跨段更正的資料交接、原文未動、相關引用可深入、保存中斷後 resume、B2 失敗／stale、scope 與普通進度。真框架／本機 DB＋假 HTTP，不付費、不把腳本化模型結果當自然模型品質保證。不是自動辨識所有遺漏或所有案例關係的保證。

[R1]: https://github.com/openai/codex/blob/ac192cd7937b0d73edc6dffe009940ae53782dd4/codex-rs/ext/memories/templates/memories/read_path.md#L33-L73
[R2]: https://github.com/openai/codex/blob/ac192cd7937b0d73edc6dffe009940ae53782dd4/codex-rs/state/src/runtime/memories.rs#L853-L942
[R3]: https://github.com/openai/codex/blob/ac192cd7937b0d73edc6dffe009940ae53782dd4/codex-rs/memories/write/src/prompts.rs#L98-L126
[R4]: https://github.com/openai/codex/blob/ac192cd7937b0d73edc6dffe009940ae53782dd4/codex-rs/memories/write/templates/memories/consolidation.md#L306-L351
[R5]: https://github.com/openai/openai-agents-python/blob/1d471a4775bf2f40179f411824da383deb4c3fca/src/agents/sandbox/memory/prompts/rollout_extraction_prompt.md#L251-L291
[R6]: https://github.com/openai/openai-agents-python/blob/1d471a4775bf2f40179f411824da383deb4c3fca/src/agents/sandbox/memory/prompts.py#L35-L68
[R7]: https://github.com/openai/codex/blob/ac192cd7937b0d73edc6dffe009940ae53782dd4/codex-rs/memories/write/src/phase1.rs#L228-L325
