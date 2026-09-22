# CT15：OpenAI 整併模型如何取得本批詳記

2026-09-07 · LLM-Q019／G2 補證。父題：[CT15 診斷與選項](2026-09-07-ct15-grounding-and-memory-freshness-review.md)。本稿只回答整併的實際入料／保存／讀取，不重開 ABC。

## 1. 先修正一個容易誤讀的結論

**Codex 不是把本批全部詳記直接拼進初始 prompt；但也不是只有候選＋地址。** 它先產生記憶工作區的有界差異檔，指示整併模型先讀。新增詳記的內容可以透過差異檔進入模型 Context；其後仍可開詳記補讀。不能因後續沒有獨立 `read summary`，就断言 Codex 沒看過詳記。

本案 CT14 沒有這個差異檔，也沒有把本批詳記放進 payload，且實際沒有讀詳記。因此「我們與 Codex 完全一樣，只差 prompt」不成立。但這不證明一定要移植 Git 或每批注入全文。

## 2. 固定版本與新鮮度

先完整回讀既有[摘要路由](../../../../docs/specs/2026-09-05-memory-summary-routing-and-deep-read-source-review.md)、[詳記更正](../../../../docs/specs/2026-09-06-openai-rollout-summary-correction-source-review.md)。再實際取得官方原碼，補查前稿未展開的 workspace diff producer。

Codex 研究時 main：`9f70e348e0227980de97e361cce830236fb18317`（2026-09-07 15:27:52 UTC）。與前稿 `ac192cd...` 比較，storage、workspace、phase2、consolidation prompt 四檔 blob 完全相同；下列用新固定 SHA。SDK 仍以已核對 `1d471a...` 快照交叉查證，不冒稱其最新穩定發行。

## 3. Codex：producer → 模型可見內容 → consumer

| 接力 | 原碼直接證据與邊界 |
|---|---|
| 保存候選與詳記 | Stage1 DB 結果先同步為 `raw_memories.md` 與 `rollout_summaries/*.md`。候選附真實 summary filename；詳記附原 rollout path、thread、時間等 Runtime metadata。不是讓模型造地址。[storage][C1] |
| 本次變更入口 | Phase2 準備基準、同步輸入，再計算／寫出工作區差異，最後才啟動整併 agent。[phase2][C2] |
| 差異包含什麼 | 比較基準檔案與目前檔案，新增檔以空舊文對新全文作 unified diff；修改檔有相鄰3行。不是只列檔名。[baseline `render_change_diff`][C3] |
| 長度邊界 | `phase2_workspace_diff.md` 同時有狀態清單和內容差異；超過4 MiB截斷並標示。**這是磁碟產物上限，不是單次 model Context／工具輸出上限，也不是可保證模型全部讀完。**[workspace][C4]、[常數][C5] |
| 初始模型入料 | `build_consolidation_prompt` 代入記憶根目錄、差異檔名及 extension 路由，不直接內嵌所有詳記。[prompts][C6] |
| 模型怎麼讀 | prompt 要求先讀差異，從新增／變更候選定位主題；需要更強依據、分類或解衝突時讀對應詳記。候選是路由，不總是細節的最終依據。INIT 與增量模式不同。[consolidation][C7] |
| 更新後怎麼找 | 正文按主題保留適用範圍、可搜尋線索與詳記引用；guide 最後更新。B 不讀 raw sessions，A 必要時才深入原始對話。這些既有政策未變。[consolidation][C7]、[既有路由研究](../../../../docs/specs/2026-09-05-memory-summary-routing-and-deep-read-source-review.md) |

**Inference：**小批新增詳記若完整出現在差異檔且模型真的讀到，就已獲得該詳記正文，不必再開一次原檔。若差異／讀取被截斷，仍需要依地址補查。這是 producer／consumer 推論，不是已量測 Codex 模型的實際遵循率。

## 4. SDK 與 Codex 不可混稱

Python Sandbox Memory 的 manager 先將每份候選／詳記分開保存，再建立選取集合與合併候選；`run_phase_two` 使用 SandboxAgent／Runner，初始 prompt 代入目錄與本次選取／移除等路由，不把全部詳記正文直接塞入。[manager][S1]、[phase_two][S2]、[prompt renderer][S3]

因此「分層保存、提供可讀來源、模型按需要取證」有官方依據；**「所有 OpenAI 整併一律候選-only」或「一律自動注入詳記全文」都不正確。** SDK 的大 max_turns 也不是 Caliburn 應照抄的產品上限。

## 5. 本案底層核對與可逆選項

- [MemoryArtifacts](../../experiments/analysis-agent/src/analysis_agent/memory.py) 保存詳記、候選及 Runtime source header；候選有同批真實詳記地址。
- CT14 的 [B2 `_load`](../../experiments/analysis-agent/src/analysis_agent/consolidation.py) 只讀詳記確認可用，沒有將其全文傳給模型。不是「程式讀過＝模型已知」。CT15 以下修正才增加模型可見內容。
- [B2 tools](../../experiments/analysis-agent/src/analysis_agent/consolidation_tools.py) 的 CompositeBackend 將 `/interviews/` 接至同文件 StoreBackend，官方 `read_file` 可以讀到真正詳記；未把詳記放在僅 Runtime 可見的 artifact。已有整合測試驗證工具結果進後續模型 input。
- 本案目前沒有 Codex 的全工作區 diff。新增檔情境可比較「本批有界詳記直接可見」，不必照搬 Git 基準；**這是框架生態內的可逆映射，不是相同原碼，也不是已證明效果最佳。** 所有歷史仍按需查。

本輪先依 Owner 已同意 A 修復候選辨識／缺依據取證。**Owner 隨後同意 B 局部對照，並採用有證據較好的接法**；比較同樣來源、候選、模型與讀取工具的結果／成本。不連帶改產品上限或排程。小測最多40次／US$0.25；後續完整訪談獨立帳本最多120次／US$0.50，皆 Luna／medium。

## 6. Closure

- Finding：先前研究講到 workspace diff，但沒有追究其包含新增詳記全文的實際效果；現已補齊。
- 狀態（2026-09-08）：22次小額對照完成，採用 B 有界詳記；不代表產品已通過完整品質驗收。
- 原情境 A/B 均未重現錯產品，各5步；前端異職位 B 保留正確餐飲預約／非SSO差異，5步而 A 為6步，但 B 費用略高（US$0.00158132 vs 0.00137154）。是限定證據，不是統計優勝或所有情境最佳。
- 接法：沿既有24,000字元批次文字預算，候選＋本批完整詳記合計可容納才整批加入 `NEW_DETAILS`；超限則 details 全空，仍以真實地址按需讀取。候選本身超限沿原規則拒絕，不截斷詳記，不新設 knob。完整 Context 計數仍另行涵蓋規則、工具、資料與後續結果。
- 小測限制：原 CT14 重播的新詳記 header 少了前置 T2 context locator（來源 T3–8不變）。22次原始帳本不回填、不宣稱 source/context 完全等價；未來 fixture 已修正。前端對照無此問題。正式新訪談走真正 B1，另驗證引用。
- 下一 gate：完整訪談與核准收尾補測已結束，沒有手動填正確 Memory 或手動啟動整理；品質仍有待修項，唯一結果入口為[CT15完整結果](2026-09-08-ct15-grounding-and-whole-interview-results.md)。先討論晚期資訊未觸發整理，不再擴張本題研究。
- 重開：原碼／工具讀取語意改變，或正確詳記已進 Context 仍串案時，依實測回局部設計；不再重做全部 Memory 研究。

[C1]: https://github.com/openai/codex/blob/9f70e348e0227980de97e361cce830236fb18317/codex-rs/memories/write/src/storage.rs#L22-L135
[C2]: https://github.com/openai/codex/blob/9f70e348e0227980de97e361cce830236fb18317/codex-rs/memories/write/src/phase2.rs
[C3]: https://github.com/openai/codex/blob/9f70e348e0227980de97e361cce830236fb18317/codex-rs/git-utils/src/baseline.rs#L371-L430
[C4]: https://github.com/openai/codex/blob/9f70e348e0227980de97e361cce830236fb18317/codex-rs/memories/write/src/workspace.rs
[C5]: https://github.com/openai/codex/blob/9f70e348e0227980de97e361cce830236fb18317/codex-rs/memories/write/src/lib.rs
[C6]: https://github.com/openai/codex/blob/9f70e348e0227980de97e361cce830236fb18317/codex-rs/memories/write/src/prompts.rs
[C7]: https://github.com/openai/codex/blob/9f70e348e0227980de97e361cce830236fb18317/codex-rs/memories/write/templates/memories/consolidation.md#L119-L175
[S1]: https://github.com/openai/openai-agents-python/blob/1d471a4775bf2f40179f411824da383deb4c3fca/src/agents/sandbox/memory/manager.py#L163-L238
[S2]: https://github.com/openai/openai-agents-python/blob/1d471a4775bf2f40179f411824da383deb4c3fca/src/agents/sandbox/memory/phase_two.py
[S3]: https://github.com/openai/openai-agents-python/blob/1d471a4775bf2f40179f411824da383deb4c3fca/src/agents/sandbox/memory/prompts.py
