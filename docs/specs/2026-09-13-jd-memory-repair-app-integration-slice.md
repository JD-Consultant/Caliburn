# JD App 的 Memory 更正接合：停止收尾、跨程序查回與封裝

**2026-09-16 MEM-L001 影響：**本稿證明的 C 停止位置、原 operation／receipt 對帳、跨程序恢復、stale 與本回合版本行為繼續沿用；當時 C 只修 `knowledge.md`／`guide.md` 的產品範圍已由 [MEM-L001](2026-09-16-layered-case-and-work-understanding-memory-alignment.md) 取代。新 C 必須在明確更正時受控修改受影響案例／案例 guide 及必要的工作理解／理解 guide，並以同一完整 Memory publication 原子發布。這是後續 G4／施工差距，不能把本稿的歷史通過誤報成新跨層 C 已完成。

2026-09-13；JD-R002／OI-02。接續[方向審核](evidence/jd-memory-repair-integration/continuation-audit.md)指出的兩個缺口，依[接續計畫 §5 H2–H3](../plans/2026-09-13-jd-app-continuation-handoff.md)完成。基準 `8403d7e2`／tag `jd-memory-repair-core-20260913`。0 provider、日常 `enable_chat=False`、ADR0060 不變。

**提交後另經Owner要求複核：**`7181db63`／tag `jd-memory-repair-app-integration-20260913`；[複核稿](evidence/jd-memory-repair-integration/submitted-integration-review.md)保存新的獨立測試命令、結果及封裝產物路由。下列2740／22／130及原獨審過程是實作者的歷史紀錄；本次沒有找到該三組完整原始輸出與原獨審逐字產物，故不冒稱重新核實全部數字。新的窄跑、FH05及wheel檢查分開記錄。

## 完成效果與界線

**兩個可重現的恢復缺口已修：**已停止但確定沒有執行 C 的回合，現在會用同一個原 call 收尾成明確的「未執行」終局，員工可以繼續手改與開新回合，Memory、JD 與原話都沒有被改寫。**新增真正跨程序的 C 查回：**Memory 發布已提交但回覆遺失時，真正的新 Windows 程序只憑原 receipt 對帳收尾，沒有第二次模型、patch、save 或發布。

不能冒稱的部分：這只是 C 接合可驗收，不是完整顧問或產品可用。B1／B2 採用、完整旅程與自然品質驗收仍未完成，集中在[唯一清單](2026-09-13-jd-app-open-issues.md)。所有證據都是固定 SDK 回覆，不是自然模型。

## 兩個停止位置的修正

原生停止形狀先以拋棄式探針實測，見[停止位置觀察](evidence/jd-memory-repair-integration/stop-position-observation.md)；只依實測補必要投影，不掃任意 namespace。

| 案 | 停止位置 | 收尾條件（全部成立才收） | 結果 |
|---|---|---|---|
| CA-01 | 尚無 binding，consultant 子圖仍停在 App 自己的 binding node | `consultant_next == [BINDING_NODE]`、沒有 C checkpoint、既有 binding 全部已有結果 | 同 call 的 `not_executed`，artifact 的 `operation_id`／`request` 皆為 `null` |
| CA-02 | 已有 binding，固定 C 子圖停在自己的 START | START 原輸入的 operation／base／source／edits 與原 binding 及原 call 參數一致，且該 operation 查無 receipt | 同 call 的 `not_executed`，保留原 binding 與 operation |
| F1（獨審補） | 已有 binding，但完全沒有 C checkpoint | `consultant_next is not None`（root 的 pending task 仍是 consultant 子圖 ⇒ 工具從未交回 root），且該 operation 查無 receipt | 同上 |

`not_published` 現在只用於 C 確實已開始的位置（`seed`／`edit`／`validate`／`save`／`prepare`）。

**未綁定與已綁定是兩種結果型別。**沒有 binding 就沒有 operation、base、source 或 `PublishRequest`，這些一律不得補造；`memory_repair_records.make_unbound_repair_message`／`validate_unbound_repair_message` 只認原 call 與其自身參數摘要。未綁定結果不更新本輪 Memory 讀版、不算模型可修次數、不觸發 C。

**沒有放寬既有嚴格判斷，反而收緊了一處。**其他節點、未知 shape、錯誤 scope、已到 publish 但查無原 receipt，仍一律 `run_recovery_required`；缺 binding、缺 checkpoint、缺 receipt 任何單一項都不構成「安全未執行」。原本沒有位置證據也會收尾成 `not_published` 的那條路徑已依獨審改為需要明確位置證據，否則保持門閘。`get`／`lookup`／`inspect_run`／`recover`／startup 共用同一判定，本輪把本回合切片規則抽成 `_run_messages`，讓恢復與既有結果核對用同一條規則，不各寫一套。

## 跨程序與同輪讀取

- `tests/ai_host_recovery_worker.py` 原本只注入 JD 資源，不能替 C 背書。現在**所有模式**都接上與產品 `open_managed_app` 相同的 host Memory engine、原生 Store 與原話 source；沒有這些資源的宿主根本無法核對用過 C 的文件（FH01–FH04 在只改 `state()` 時即以 `checkpoint_unavailable` 失敗，見下方首敗）。
- 新增 FH05：真新 Windows 程序＋真 PG。舊程序的 repair 發布真的提交、只有回覆遺失，並在原生結果閉合前退出；新程序沿既有 HostLease 與舊程序退出證據，只建 inspection 圖，對帳原 request 後收尾。`publish`／`patch` 計數為 0 是硬性斷言。
- 晚到的背景整併版本不會讓已收尾的回合失效或倒退：核的是原 applied receipt，不是現在的 head。

`inspect_run` 的 `effects_settled` 只有在 `_repair_evidence` 與 `_verify_saved_results` 都通過後才為真，因此它確實涵蓋 C；同一份 `receipts` 仍只含 JD 效果，兩者沒有混用。

## 實際驗證

首敗（保留原始數字，不是目前狀態）：

| 階段 | 首敗 |
|---|---|
| H2a 紅測（真 PG） | **2 failed／5.06s**；兩案都在 `wait(30)` 拋 `run_recovery_required`，回合未收尾導致 `owner.close(timeout=10)` 回 `False` |
| CA-02 修正中 | **1 failed／1 passed／5.78s**；CA-01 已收尾，CA-02 的下一回合仍 `run_recovery_required`——未綁定掃描沒有限定本回合切片 |
| 宿主 helper 改動後 | **4 failed／21 passed／96.65s**；FH01–FH04 在 `finish_startup` 拋 `checkpoint_unavailable`，因為情境模式的宿主沒有 Memory 資源 |

最後結果（範圍重疊不累加）：

| 範圍 | 結果 |
|---|---|
| App 全離線測試 | **2740 passed／257 skipped／57.91s** |
| Memory 套件全測（App 環境執行） | **130 passed／4.63s** |
| 真 PG：C 接合＋宿主重啟＋修補核心＋runtime | **22 passed／99.34s**（含 FH01–FH05 真新 Windows 程序） |
| 真 PG 全部 `-k postgres`（獨審修正前） | **150 passed／1 failed／195.66s**；該 1 failed 為既有問題，見下 |
| 乾淨 venv wheel 隔離檢查 | 通過（六節點建圖、無 `analysis_agent`／`jd_relational`／舊 checkout 路徑） |

**既有失敗，非本輪造成：**`tests/test_chat_api_postgres.py::test_http_ai_edit_results_match_original_receipt_change_and_history_after_manual_head_advance`。`chat_history.read` 的首頁是最新視窗（原碼註解明示），測試卻期待最舊一筆；`chat_history.py` 與該測試自基準以來都未修改。已在基準 tag 的獨立 worktree 重現同一斷言失敗（**1 failed／2 passed／5.64s**），本輪不順手改，記入 OI 清單。

## 獨立審查與修正

非作者代理審查 bindings／context／恢復／scope，實際重跑離線與真 PG／真新程序案例。**阻擋級：無。**首輪兩項「應修」、四項「建議」如下，已全部處理並經同一審查者窄複核通過。

| 編號 | 內容 | 處理 |
|---|---|---|
| F1 | `checkpoint is None` 落進 `not_published` 的 `else`，判定只由「缺 child checkpoint ＋ 缺 receipt」構成，沒有任何位置證據 | 拆成獨立分支：要求 `consultant_next is not None`（root 的 pending task 仍是 consultant 子圖 ⇒ 工具從未交回 root ⇒ 固定 C 節點未跑）才收尾成 `not_executed`，否則保持門閘。`not_published` 只剩 `seed/edit/validate/save/prepare` |
| F2 | 若同一則回應同時發 `repair_memory` 與別的工具，該回合的 pending call 有兩筆，入口守衛 `len(pending) != 1` 讓文件永久卡在 `run_recovery_required`（嚴重度見下方更正 2） | 守衛改為只在**已綁定**路徑要求（已綁定必來自單一 call 回應）；未綁定結果可指名同一回應中的那個 repair call，digest 取該 call 自己的參數 |
| F3 | 子圖 outcome 為 `applied` 但 receipt 讀不到時，會先組出 `success` 結果，要到下一層才被擋 | 該情形直接 `run_recovery_required`：發布與 receipt 同一交易，applied 不能自我佐證 |
| F4 | 註解的論證比程式強。LangGraph 1.2.11 的 `next` 會濾掉已有 writes 的 task，且 pinned 讀取不套 pending writes，所以「停在某節點」只代表該節點的 writes 未套進該 checkpoint | 改用真正成立的論證：依據是**已提交狀態**裡沒有這筆 binding、且 tools node 尚未成為 task；不是「next 證明 handler 沒跑完」 |
| F5 | `repair_checkpoint` 同時表示「沒有子圖 checkpoint」與「pinned source 讀取時故意沒看」 | 已由 F1 的規則涵蓋：`source_only` 路徑下 `consultant_next` 必為 `None`，該雙義情形一律落在門閘外 |
| F6 | `chat_service` 對外欄位仍叫 `jd_effects`，其 `state` 現在已含 Memory 判定 | 只記文件：`results` 仍只有 JD receipts，C 驗證失敗時 `inspect_run` 直接擲錯、不會回假的 settled。欄位改名是 HTTP 契約變更，不在本單位 |

**兩項事實更正，審查者已在窄複核中撤回：**

1. 首輪認為 F1 是本輪重構放寬的。實際上改動前的原碼是 `if next_step is not None and (...)`，對 `None` 短路為 False，本來就落到 `not_published`；本輪的 if/elif/else 重構行為等價。問題本身成立，歸屬不成立。
2. 首輪把 F2 記為「模型可觸發」。`consultant_context` 已設 `parallel_tool_calls = False`，SDK payload 的 `disable_parallel_tool_use is True` 也有既有斷言，因此合規 provider 不會產生該回應；**F2 的正確嚴重度是「韌性／建議」，不是「應修」**，修正本身仍屬合理縱深防禦。

F1 的可達性原本只由讀碼推得，本輪補上**真反例**：注入工具交接失敗後實測 `consultant_next == ["tools"]`、`repair_checkpoint is None`、binding 一筆。三個新案例的首敗為 **3 failed／17 passed**，分別是 `not_published != not_executed`、`DID NOT RAISE AiRuntimeError`、`run_recovery_required`。

窄複核另提三點，處理如下：

- **N1（已收）：**`consultant_next` 現在是安全承重點，但依據是它的**來源分支**（只有 root pending task 為 consultant 時才設值），不是它的值。兩處註解已改為明寫這條契約與「不得從其他分支填入」的後果，避免日後無聲退化。
- **N2（部分收）：**`tool_handoff` 已加入真 PG 的端到端參數化，取得完整收尾／閘門解除／下一回合准入證據。多call當時只有單元層覆蓋；提交後另補原生close診斷，仍未驗完整owner／HTTP流程。更正先前理由：outgoing wire要求`disable_parallel_tool_use`，不妨礙MockTransport刻意回不合約的多call；測試技術上可做，只是本次尚未執行，不作正常路徑的阻擋或新增產品要求。
- **N3：**即上述 F2 嚴重度更正。

**審查指出的覆蓋損失：**helper 改為所有模式都接 Memory 資源後，`memory_engine=None` 的 JD-only 宿主重啟不再有測試覆蓋。正式入口 `open_managed_app` 一律接上 Memory，因此這不是產品設定；如日後要支援該形態需另補案例。

## 封裝與採用登記

- `packages/consultant-memory/adoption.json`：`repair.py` 的 `adopted_sha256` 更新為 `2e96de84add61679d908f87de67dc105b487b1f1ea1c83c1774a3c91ac1ab879`，並說明新增的 `build_repair_graph(resolve_workflow)`（同一組六節點，建圖／檢視不開任何資源）。補登先前漏記的 `read_tools.py` 採用來源；`source_commit` 維持 `033540ce`。
- wheel 重建結果與審核時逐位元相同：`8177326ee4ac9efc900978778ce031a3afcbdf2e2b4832199394745406e99ac1`，位於 `.research-tmp/jd-memory-c-app-dist-20260913b/`，一併保存 App lock 導出的 constraints。
- 乾淨 venv `.research-tmp/jd-memory-c-clean-venv` 依該 constraints 完成**完整依賴**安裝。先前缺的 cache 件已確認為 `pywin32==312` 的 win_amd64 metadata（`openai-agents` → `mcp` 的相依）；constraints 鎖死每個版本，補件沒有造成任何版本漂移，也沒有升級。這修掉了審核稿 §4 記的「借用 App 依賴目錄」界線。
- `patch.py` 確實 `from agents import apply_diff`，`openai-agents` 是真依賴，不是殘留。

## 界線與未完成

1. 固定 SDK 回覆與合成 fixture，不是自然模型；沒有任何 provider 呼叫或費用。
2. 兩個停止位置的收尾只涵蓋已實測的形狀。其他停止組合維持原門閘，不宣稱已窮舉。
3. FH05 證明「真提交＋回覆遺失」的跨程序查回；**沒有**證明延遲交易、部分寫入或 Store 斷線的所有排列。
4. `memory_engine=None` 的 JD-only 宿主重啟目前沒有測試覆蓋；多 call 回應的收尾只有單元層覆蓋（見獨審一節）。
5. H4（B1／B2、完整來源窗口、顧問指引）與 H5（完整旅程、日常交付、自然驗收）未開始。
6. 日常 AI 未啟用，正式產品 ADR0060 不變，ADR0074／0075 仍 Proposed。

## 接續

沿[接續計畫](../plans/2026-09-13-jd-app-continuation-handoff.md) §5 H4：直接採用已驗 CT49／CT50 顧問與 Memory 方法，先交採用映射，再接完整 JD 旅程。未解事項仍用既有 OI ID，不另造清單。
