# CT12：整份工作訪談與 Memory 回查驗收

2026-09-07 · LLM-Q019／isolated G5/G8 · 基準 `9a196c94`。

**結論：14 輪合成職位訪談已收尾，兩次自然背景整理完成，獨立 reader 可深入詳記及原始對話；但有語意品質問題，不能宣稱滿分或全面穩定。** Owner 已要求「先保留紀錄，訪談測完再討論」，本轮沒有修改產品程式、提示、Skill、schema、verifier 或配置預設。

閱讀路由：[本輪計畫](../plans/2026-09-07-patch-completion-and-whole-interview.md) → 本短結果 → [14 輪逐字稿及 4 次獨立回查](evidence/2026-09-07-patch-and-whole-interview.transcript.md)／[完整 evidence](evidence/2026-09-07-patch-and-whole-interview.json)。工具底層只回看 [CT10](2026-09-07-memory-editor-framework-comparison.md)／[CT11](2026-09-07-official-memory-patch-trial-results.md)；內容取捨由[工作案例與工作理解研究](../../../../docs/specs/2026-09-07-work-case-and-understanding-information-selection.md)持有，不在 register 重複整篇。

## 1. 測了什麼、成本多少

合成家用小家電售後營運專員，非真實員工／公司。先沿用 CT09 已封存的 8 範圍／4 案例 oracle，未交給顧問；依顧問提問逐步回答。新 PG 文件沒有匯入 Memory。每回合使用真正 API factory 並重開服務；不手動執行 B、不灌入 oracle、不強制湊回合数。只分析，不產出 JD。

| 測試 | 結果 | 模型請求／usage 估算美元 |
|---|---|---:|
| B2 針對補驗 | 1 次 patch 成功套用，final 後發布 revision 2；內容另有 Q01 | 7／0.00313647 |
| 14 輪正常訪談 | 14 個 run completed，無技術重試／卡住 | 主顧問 19／0.03555839 |
| 自然背景抽取 | 第 7、14 輪通知，2 批 B1 | 2／0.00782860 |
| 自然背景整併 | 分別 6、7 模型步，發布 Memory revision 1、2；未 blocked | 13／0.00984587 |
| 獨立回查 4 次 | 前兩次未完整完成；後兩次 completed，仍須審語意 | 24／0.02146144 |
| 合計 | 帳本關閉，未達 120 次／US$0.50 測試護欄 | **65／0.07783077** |

單獨「訪談＋兩批背景」共 34 次／US$0.05323286。主回覆 6.41–11.25 秒，中位數 7.385 秒；兩批背景另約 44／55 秒，未要求員工等待整理完才收到答覆。這是測試環境觀察，不是服務延遲 SLA；driver 收到回答後另等待背景再做下一輪，沒有壓測「背景執行時立即再送訊息」的競爭情境。費用依實際 usage 與當日定價估算，非帳單。

針對 B2 使用合成 seed 與明示 patch 測試提示，不是自然選工具證據。自然兩批 B2 均選既有 `write_file`，正文 2 次、導覽 3 次；本次不能用「自然訪談沒發生匹配錯誤」推論 patch 的一般錯誤率已大幅降低，因為該路徑沒有自然選 patch。也不與 CT09 不同批次／訪談形狀做無控制的效能因果比較。

## 2. 內容、案例、引用的核對

以下是人工對照「實際已揭露」資訊的語意審核，不是靠關鍵詞計分，也不是全知驗收。穩定工作與案例細節可分層保存，不能要求所有細節全抄進正文。

| 範圍 | 已保存與可找回的重要內容 |
|---|---|
| W1 受理與排序 | 9:00／14:00、三管道、訂單／序號去重、安全優先再承諾期限、15–25 件不是 KPI |
| W2 排查與技師交接 | 安全外部檢查，不拆修、不自行判定原因／責任，整理現象與已查步驟交技師 |
| W3 售後方案與退款 | 規則內可辦、超規則營運主管；海鷗退款更正為財務主管，出納匯款，本人核對／追蹤／通知 |
| W4 倉庫物流與例外 | 雲杉有貨換貨、海鷗缺貨且日期未確認、石橋運損先換貨；求償核准人未知 |
| W5 追蹤與結案 | 每個工作日下午、依個案承諾、客戶回覆＋完成證明；未回覆交主管，不把個案三天當通則 |
| W6 月報與 FAQ | 全部售後月報、第一工作日、依訂單去重，不推論設計缺陷；新解法確認且核准才發布 FAQ |
| W7 新人帶教 | 到職才帶、前五案檢查、班長決定獨立、無派工／考核權；遮蔽個資保留在詳記；用詞偏差見 Q04 |
| W8 低頻安全工作 | 青禾焦味案、正式低頻責任、停用／安全斷電、不要求通電重現、窗口判因／處置，不自行召回或承諾 |

- 兩份詳記保存雲杉、海鷗、石橋、青禾的差異；正文沒有把四個產品案例各變成四個永久工作。雲杉後補的兒童使用／清潔限制仍留在詳記，不因正文摘要沒逐字重述就算丟失。
- 最終正文保留两個有效詳記引用；逐一向官方現有 reader 讀到底，各 2 頁；14 則員工輸入與 canonical history 逐字一致、14 個 closed turn 全 completed。完整原文與會更新的 Memory 沒有互相覆寫。
- 導覽 → 正文／詳記 → 原始對話均有真實工具結果。精確回查取到雲杉原句與海鷗更正，沒有只取最早的錯誤核准人。原文工具頁面含可見問答；不能把詳記當逐字稿，亦不能把來源範圍當成逐句支持保證。
- 旧詳記「本段尚未回答排序」是當時段落狀態；新詳記與目前理解已有答案。舊段落保留不自動構成 bug，判斷目前是否已答應看後續資料。

## 3. 保留的問題：不在本輪默默修提示

| ID／狀態 | 直接證據與影響 | 本輪處理 |
|---|---|---|
| CT12-Q01／OPEN | targeted B1 request 1 的 `rollout_summary` 寫「月報…上月案件」，同一輸出的 `raw_memory` 卻寫「退換貨案件月報」。B2 照候選寫入，技術 checks 全綠也抓不到範圍縮窄 | 根因在抽取語意，不是 patch。Owner 明確指定先記錄；自然主訪談有明说「全部售後」，其最後 Memory 未重現此縮窄，不代表 Q01 已修 |
| CT12-Q02／OPEN observation | 第 11 輪稱已釐清「完整工作模式」並結束追問；第 12 輪是合成員工主動要求再檢查專業判斷／做好標準，顧問才讀 outcomes Skill 並續問至第 14 輪。多輪用「最後」引出下一問 | 能收尾，但不能說顧問不經提醒已自行全面盤點。待討論收尾品質，不新增完成表單／固定回合數 |
| CT12-Q03／OPEN | 第 6 輪「日期没確認不能承諾」在 request 18 候選、21／37 正文局部變成「補貨日期不可對客戶承諾」，漏了條件；正文別處又保留未確認日期的條件，造成表述歧義。長總覽 request 47 另把安全事件「不要求再通電」放進一般排查；短總覽 request 65 把試算表去重套到受理，並將未確認頻率的運損／缺貨／物流協調放進「特殊低頻」 | 自然保存的理解與回查回答都有適用條件偏差，不只 reader 問題。保留實際輸出與來源，和 Q01 一起討論，不先加 validator |
| CT12-Q04／OPEN wording | 第 7 輪員工說「依訂單去重建案」，第一份詳記新人支援段寫成「依訂單重建案件」，request 47 再照抄 | 可能把去除重複說成重新建案；原始資料未丟，但整理用詞應校準。未修改已保存成果掩蓋問題 |

## 4. 兩次失敗與補測的分界

1. **回查 #1／requests 42–47：**找到了兩份詳記並生成長篇總覽，但最後 `status=incomplete`、`reason=max_output_tokens`，4096 output tokens（其中 reasoning 317），末段截斷。舊 driver 的 `recorded` 只表示保存，不是 PASS。這個診斷 reader 沒走主服務的 `TurnValidation`；不能推論正式 API 會把 incomplete 當 completed。
2. **回查 #2／48–54：**連續 grep、正文、詳記後，成功取得第一頁原文；測試器 7 模型步耗盡，沒有最終答案。是回查效率／測試步數問題，不是原文讀不到。
3. **回查 #3／55–63：**同一題、同一提示與 4096 output，診斷計數改為主顧問既有 9 模型／8 工具。request 59 抄錯來源地址，工具回 `unavailable` 且不以最新原文替代；60 更正地址，成功讀取第一頁（offset 0，仍有 next_offset 3000）。63 完整回答雲杉、個案時限、補充限制與海鷗核准更正；這些所需內容已在第一頁／詳記，**不是模型讀完兩頁原文**。兩份來源各兩頁完整讀完的是另一次零模型 `offline_source_audit`。仍是獨立唯讀 loop，不是完整 conversation API；兩次路徑因模型抽樣也不同，不能據此保證加兩步永遠足夠。
4. **回查 #4／64–65：**以短篇總覽問題測不同輸出長度，2 步 completed；没有改產品 prompt 或提高 output cap。完成不等於語意全對，Q03 仍成立。

OpenAI 官方說 output 預算包含推理，達上限會回 incomplete，必須與完成區分；應依工作需要配置空間，而不是把 4096 視為官方規定。本次只依此判讀結果，沒有默默提高產品限制或讓模型无限重試。[官方 reasoning／incomplete 說明](https://developers.openai.com/api/docs/guides/reasoning#allocating-space-for-reasoning)。工具循環的預算由框架 middleware 管理，7／9、9／8 都是應用或診斷配置，不是大廠共同固定值。

## 5. 官方依據、回歸與限制

- Patch：沿用官方 SDK 本機函式，模型 patch → 框架套用 → 回傳工具結果 → final → 既有發布。OpenAI 明確把 patch harness、path 檢查與成功／失敗回報交給應用；採用 SDK 不等於 schema、Memory 發布政策也全是官方原樣。[官方 harness](https://developers.openai.com/api/docs/guides/tools-apply-patch#implementing-the-patch-harness)、[固定 SDK 原碼](https://github.com/openai/openai-agents-python/blob/18de65134083ee8cbdb84ae30a34c1f30ef4cb86/src/agents/apply_diff.py)。本輪窄重讀，不重新開框架選型。
- 內容：官方建議讓模型承認未知、依來源作答與查證；但不能保證零幻覺。這支持把 Q01／Q03 當品質 finding，不支持自動新增一堆必填引用欄位或宣稱新 verifier 是共識。[Anthropic 降低幻覺](https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-hallucinations)。職務資訊保留面向與 OpenAI Codex 抽取／整併原提示，沿本篇首段的研究路由。
- Fresh regression：**562 passed、0 skipped，86.66 秒，含專用 PG**；`compileall src tests`、`uv lock --check --offline` 通過。只有既有 Starlette BlockingPortal deprecation warning。執行用新隔離 basetemp，不刪舊資料；uv 首次因 sandbox cache 權限失敗，核准後離線檢查成功。
- 原生 reasoning：主訪談第 2 次及之後請求，均可見前次不透明 reasoning hash 重送；這證明 wire 延續，不證明推理內容或不會重分析。本次最大 input 13,042 tokens，**沒有觸發 32,000 門檻的 compaction**，不能當超長 context 驗收。
- 未測：UI、真實 JD 製作、第二種職位、OpenRouter 全套相容、背景與前景並行壓測、C 即時修補新情境、真正超長訪談壓縮。C 的既有局部真測見 CT11，不能冒充本輪又測過。

## 6. Closure／下一 gate

本輪沒有 production／JD／UI 改動，沒有重選 Memory 架構或提高產品限額，沒有重啟 Docker、搬舊資料、merge／push。合成測試資料／原始失敗／工具結果／版本／費用均封存；evidence 不含 key 或 opaque reasoning 正文。API launch 一次因資料外送安全審查暫停，核對 oracle 與全新文件確屬合成資料後，以同一指令核准續測，不繞過攔截。

**下一個唯一 gate：向 Owner 報告本次可運作的部分及 Q01–Q04，先討論「保留工作範圍與條件」的局部校準，再決定是否修正。** 不把本次技術完成升格成「能寫完美 JD」或進 production 的授權，不擅自重跑整套訪談來覆蓋失敗。

獨立唯讀 review 核對短報告與完整 evidence，指出原稿誤寫 reader 讀兩頁、漏記來源地址錯誤的恢復、漏報自然 Memory 的日期條件遺失，以及正文／導覽寫入次數顛倒。主審逐筆核對 requests 18／21／37／59–63 後，已修正本報告；未動模型輸出或產品以消除 finding。這是報告事實更正，不是 Q01–Q04 品質問題已解決。

限定複核已確認三項 report findings 全部 CLOSED，報告與證據一致；Q01–Q04 仍 OPEN。此結論只允許保存驗收紀錄，不允許宣稱產品完整通過或直接進 production。
