# Q019／MP-02：整併交付與官方底層實作複核

> 2026-09-07 · **G2 完成，短設計待 Owner 確認；不是已實作修復。**
> 入口：[主 register](../../../../docs/current-decisions.md)；問題與原始試驗：[MP-02 §6](2026-09-07-memory-prompt-live-calibration.md#6-同組材料續測有進展但不能只靠再加提示收尾)。本稿只補缺少的底層比對，不重寫 Memory 總研究。

## 1. 本輪問題與已核對範圍

- **唯一問題：**B2 檔案操作／完成方式是否讓短篇整併付出不必要步驟，應先改哪個接點？
- **有效目的：**原文→詳記／候選→正文＋導覽、按需深讀、分文件隔離與安全發布保留；不是保留任何舊函式名稱。
- **基準：**隔離 HEAD `e466f0fa`；程式仍為 `04ce14d8`。已完整讀 B2 workflow、工具與最後回饋程式，核對 `memory.py` 驗證／保存、兩次實際工具往返及已發布快照；前輪四檔提示試改仍撤回。
- **官方版本：**GitHub API 當日確認 Codex main `1fb5158b3496a05abb89fb992d45737a02511d47`（2026-09-07）；Python Agents SDK main `1d471a4775bf2f40179f411824da383deb4c3fca`（2026-09-05，與前稿 SDK SHA 相同）。框架比對以已安裝 Deep Agents 0.7.13 為準，不冒稱它就是最新所有可用能力。
- **不做：**付費重跑、提高上限、改 provider、JD／UI／production、改 B/C authority、模糊比對舊文字、整套換框架。MP-01 計數端點及原生延續的真實相容性仍是另一題。

## 2. OpenAI 實際如何做，不能混成一套「共識底層」

| 核對項目 | 官方事實 | 對本案的意義／限制 |
|---|---|---|
| Codex 整併工作區 | `phase2.rs` 同步抽取輸入、取得 workspace diff、啟動受限 agent，完成後再驗產物；成功才重設 baseline／標記工作成功。配置禁止遞迴委派等；受管理 sandbox 分支限制 Memory root 寫入及網路。[C1] | 我們的 staging→檢查→發布形狀相近，但不是同一儲存／交易實作；不能用「都改檔案」判定接法等價。 |
| Codex 完成檢查 | `validate_consolidation_artifacts` 確認 `MEMORY.md` 是檔案，`memory_summary.md` 可讀且首行等於 `v1`，另处理符號連結。[C2] | 空導覽不會通過此檢查；但只有 `v1` 並不保證導覽內容有用，也不驗證語意。不能宣稱官方有完整知識正確性 validator。 |
| Codex 正文／導覽分工 | prompt 明訂初始化與增量不同；正文處理後更新導覽、維持主題與引用一致；未變內容減少重寫，需細節才開詳記，禁止整併任意開原始 rollout。[C3] | 支持完成條件與增量整理，不支持每次全部重寫，也不支持只完成正文就當全部完成。其偏好／技能／跨任務內容政策不直接照搬。 |
| SDK Phase 1／2 不同 | Phase 1 明設三欄 structured output；Phase 2 是 `SandboxAgent`，沒有設兩欄最終 structured output，`Runner.run(..., max_turns=500)`。[抽取][S6]／[整併][S1] | **500 是該 SDK 路徑的上限，不是正常耗用，也不是建議本產品改500。**我們8步是應用初值，非 OpenAI 保證夠用；不能把有界工具 agent 說成固定一次整併呼叫。 |
| SDK Phase 2 的工具 | `SandboxAgent` 預設能力為 Filesystem／Shell／Compaction；Filesystem 裝入 `view_image` 與 freeform `apply_patch`。patch 可一次含多個檔案操作／多段變更。[預設能力][S7]／[接線][S8]／[工具][S2] | 不同於我們的精確 `old_string/new_string`。但增加 shell／完整 sandbox 是擴大權限與依賴，並非修這兩檔的必要前提。 |
| Patch 的實際錯誤界線 | SDK `apply_diff` 先精確找上下文，再容許行首尾空白差異；仍可能回 `Invalid Context`。批次工具先驗路徑，再依序執行操作。[比對][S3]／[批次執行][S2] | 它**不會移除不存在的中文句號替模型猜原文**；空白錯配可能改善，但本次句號錯配不會自動消失。多檔一次操作也不等於全部原子回滾。 |
| 公開 API 的 patch 契約 | 官方要求應用執行 patch、每個 call 回成功／失敗及可理解錯誤；SDK 提供 `apply_diff`，應用仍管路徑、存取與原子性。[S4] | 可接虛擬 staging，不必開真實電腦；但 native `apply_patch` 與 Sandbox freeform custom tool 是不同 wire 形式。現有 LC/OpenRouter 接線未驗，不能當即插即用。 |

**重要差別：**Python Sandbox Memory 的 `manager._run_phase_two` 在 Runner 返回後寫 selection；本次讀取的路徑未呼叫 Codex Rust 那個產物 validator。[S5] 因此不能把 Rust 的 `v1` 檢查、Python 的500上限、不同 wire 的 patch 拼成「所有 OpenAI 產品都如此」。本輪核對公開原始碼，不推測未公開服務。

## 3. 現有失敗的責任定位

1. **MP-02f／完成缺口已確認。**兩檔一開始都種成空字串；`staged_texts` 只驗可讀、大小與引用，空字串合法。`c815...` 只寫正文，`validate_memory` 仍成功，接著发布空導覽。是本案完成契約未覆蓋結果，不是官方工具沒回錯。
2. **MP-02f／精確編輯負擔已確認。**`c815...` 第二批正文只有12行；模型完整讀後仍用長 old_string，添入不存在的 `。`。失敗後分拆內容、關鍵詞、引用再改，引用再錯一次。Deep Agents 的精確替換依契約正確拒絕。[F1] 不應加模糊替換讓它「成功」。
3. **重複的模型驗證步驟不是唯一安全閘。**既有 `ConsolidationFeedback.after_model` 已在最後答覆時驗暫存，已知格式／引用錯誤回模型，collect／保存仍會驗；原 prompt 卻要求模型另外必叫 `validate_memory`。官方 middleware 支援此 final hook／jump。[F2] 將預檢改可選不等於移除驗證，但前輪已試過這一句，不能把它單獨當新修復。
4. **MP-02d/e 是另一種錯。**候選只傳未答期限，以及把未答追問當成推翻舊責任，都是內容交接／判讀問題。即使寫檔完全成功，仍會寫入錯誤理解。官方整併指引重視已核實資訊與不確定性，[C3] 但沒有可直接套用、保證正確的語意檢查器；本案仍需檢查同組樣本的實際內容。

框架原生 `write_file` 在本版本會覆寫既有檔案，不是僅限新增。[工具][F1]／[StateBackend][F4] 因此「既有正文優先精確 edit」是我們 prompt 的偏好，不是框架逼迫每次都如此。官方 read 有分頁／輸出限制，讀了一頁不等於全文；只有真正完整可見且輸出能容納的短檔，才有整檔交付的安全前提。

## 4. 三個選項與建議（不是已採用決策）

| 選項 | 效果與風險 | 成本／接線 |
|---|---|---|
| **A：既有工具，改操作策略＋完成檢查（先建議）** | 小檔已完整讀取可用官方 write 一次更新該檔，不必反覆抄 old_string；長正文仍局部 edit。最後同時核對正文／導覽；保留有效 no-op。仍可能漏內容／誤判，不能以機制通過替代品質驗收。 | 不增依賴／新 wire；小檔輸出可能多於精準 patch，但可少掉錯誤往返。是否實際較便宜待原樣本；不先提額。 |
| B：可完整處理內容，用框架 structured result 交正文＋導覽 | 避開逐句舊文字匹配，兩個成果欄位明確；但 required 字串仍可能空、內容仍可能遺漏。未讀全文不可覆寫，長正文超出輸出預算會成根本限制。 | 每次重輸整份正文；工具與 structured output 同用需 provider 支援。[F3] 不宜現在把所有長期 Memory 強制改成這條路。 |
| C：官方 patch 演算法＋受限虛擬 workspace | 可一次多段／兩檔變更，長正文局部更新較合適；錯配／語意錯誤仍存在，不保證本樣本更好。 | 可重用 OpenAI `apply_diff`，但還需 LC工具／staging／scope／錯誤／provider 接線；不能把普通 backend 當成已自帶 patch。若 A 仍證實卡在操作，優先重開此路，而非再加 prompt。 |

**A 的短設計待確認：**

- 保留讀取→整併暫存→最後驗證→安全發布，不加第二個整併 LLM。
- 已完整可見的小檔允許整檔寫；不把「read 過」誤當全文已取得，不把長正文塞回 prompt／輸出，不新增猜字／猜引用機制。
- 補一條機械完成條件：**正文非空而導覽空白，不能發布為完成，須沿既有回饋機制請模型補齊。**两者均空的有效初始 no-op、既有合格導覽可沿用；不要求每次重寫導覽，不硬填占位文字湊成功。這是借鏡官方產物驗收的本案規則，不照抄 `v1`，也不保證導覽語意完整。
- 不再要求「呼叫驗證工具」才算安全；程式仍必驗。工具可留可選預檢；最終錯誤回既有有界 agent loop，不新增外層盲重跑。
- MP-02d/e 的內容校準另列同組材料觀察，不混成 patch 修復成果；B1候選須能帶出已知工作，未答追問不能單獨推翻已述事實。

**獨立只讀複核補充：**reviewer確認 `write_file` 可覆寫、實際空導覽快照與上述候選邊界，未改碼／未付費。特別指出：完整讀取還受100行預設與回傳字元上限影響，4096是生成 token 上限，不能互相換算成「一定讀全／一定寫得下」。新的成對完成檢查應在取得**兩個真實暫存內容後**執行；目前逐檔驗證會把另一檔暫填空字串，不可把新規則直接塞進那個逐檔呼叫而誤拒有效內容。錯誤須歸入既有可修正類型，否則一般 `ValueError` 會跳出 agent、無法回模型補齊。這些是下一實作的必要邊界，不是本轮已修。

**驗證界線：**核准後先離線重現「正文非空／導覽空白」、有效空 no-op、沿用合格導覽、補齊後發布、額度用完不發布、來源／跨文件拒絕；工具與分頁用真框架驗。品質仍用原有 A/B→補充→更正→fresh-context回查，限定 Luna／medium；本輪不執行，亦未新增付費授權。若正常操作仍因有必要的多步讀寫而耗盡8步，應回報成本／工作量取捨，不刪必要深讀、不宣稱工具壞掉。

## 5. Closure 與查證索引

**Finding：**不能只靠加 prompt；完成契約有可定位缺口，官方檔案工具的選用也未必適合所有檔案大小。**Status：G2 完成／G3 待確認 A；MP-02d/e/f仍 OPEN。**不改程式、不付費、不動 Docker、不merge/push。既有原文／詳記／引用與發布規則不翻案；后續若改 patch／輸出契約需再明列差異。

重開條件：原樣本顯示 A 仍無法有效完成、長正文無法保留細節、官方／provider契約改變，或 Owner 選擇 B/C。不存在「只要是 OpenAI 工具就一定最好」的證據；選擇以本產品效果、成本及已核實接點為準。

本輪來源均為直接官方文件／原始碼；原始碼是對固定 revision 的事實，建議 A 是本案判斷，**尚無新模型效果證據**。官方網頁仍有不同年代例子／模型列舉，未拿其範例模型替換指定 Luna。

[C1]: https://github.com/openai/codex/blob/1fb5158b3496a05abb89fb992d45737a02511d47/codex-rs/memories/write/src/phase2.rs
[C2]: https://github.com/openai/codex/blob/1fb5158b3496a05abb89fb992d45737a02511d47/codex-rs/memories/write/src/workspace.rs#L51-L82
[C3]: https://github.com/openai/codex/blob/1fb5158b3496a05abb89fb992d45737a02511d47/codex-rs/memories/write/templates/memories/consolidation.md#L758-L880
[S1]: https://github.com/openai/openai-agents-python/blob/1d471a4775bf2f40179f411824da383deb4c3fca/src/agents/sandbox/memory/phase_two.py
[S2]: https://github.com/openai/openai-agents-python/blob/1d471a4775bf2f40179f411824da383deb4c3fca/src/agents/sandbox/capabilities/tools/apply_patch_tool.py
[S3]: https://github.com/openai/openai-agents-python/blob/1d471a4775bf2f40179f411824da383deb4c3fca/src/agents/apply_diff.py#L334-L381
[S4]: https://developers.openai.com/api/docs/guides/tools-apply-patch
[S5]: https://github.com/openai/openai-agents-python/blob/1d471a4775bf2f40179f411824da383deb4c3fca/src/agents/sandbox/memory/manager.py#L199-L227
[S6]: https://github.com/openai/openai-agents-python/blob/1d471a4775bf2f40179f411824da383deb4c3fca/src/agents/sandbox/memory/phase_one.py
[S7]: https://github.com/openai/openai-agents-python/blob/1d471a4775bf2f40179f411824da383deb4c3fca/src/agents/sandbox/capabilities/capabilities.py
[S8]: https://github.com/openai/openai-agents-python/blob/1d471a4775bf2f40179f411824da383deb4c3fca/src/agents/sandbox/capabilities/filesystem.py
[F1]: https://github.com/langchain-ai/deepagents/blob/deepagents==0.7.13/libs/deepagents/deepagents/middleware/filesystem.py
[F2]: https://docs.langchain.com/oss/python/langchain/middleware/custom#agent-jumps
[F3]: https://docs.langchain.com/oss/python/langchain/structured-output#response-format
[F4]: https://github.com/langchain-ai/deepagents/blob/deepagents==0.7.13/libs/deepagents/deepagents/backends/state.py#L206-L247
