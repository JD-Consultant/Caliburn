# 顧問方法接上新 App：A 指引、三項分析 Skills、Memory 行動指引與背景可用性

日期：2026-09-14；Topic：JD-R002；[H4 計畫](../plans/2026-09-14-jd-h4-runtime-integration.md) R3 第 3 項與第 6 項的指引部分。隔離 App，ADR0075 Proposed／production ADR0060 不變。零 provider。

承接[採用映射 §5](2026-09-13-jd-consultant-b1-b2-adoption-mapping.md)。**這是接線，不是重寫顧問方法**：已驗內容逐字採用，新增的只有 JD 能力段與 App 自己的背景可用性接點。

## 1. 要完成的效果

員工開始訪談時，顧問**有方法可用**：一次問一個有用問題、保留未知、需要時才按需讀取分析方法、該修 Memory 就修、累積足夠才通知整理、需要時撰寫或修正同一份 JD。整理受阻時，本輪開場就知道「這段訪談還沒進長期記憶」，而不是把未整理的資料當成已記得。

## 2. 範圍

| 做 | 不做 |
|---|---|
| 把 `4f94fbfb`／`033540ce` 已驗的 A 訪談指引逐字採用為新顧問 system prompt 的第一段 | 不重寫、不精簡、不「順手改善」這段已驗文字 |
| 三項分析 Skills（`work-scope-interview`／`compare-work-patterns`／`outcomes-and-expertise`）與 `SkillAssets`／Skills middleware 採用到正常套件 | 不採用後加的 `write-customized-jd`；不把 SKILL.md 內文塞進 system prompt；不要求每輪全讀 |
| `MEMORY_ACTION_GUIDANCE` 逐字採用，接到 App 已註冊的 `repair_memory`／`request_memory_consolidation` | 不新增第二套 Memory 寫入規則，不改 C 的工具描述語意 |
| `BackgroundAvailability` 的**效果**接到 App 自己的 admission 列與 publication 游標 | 不搬舊 `service.background`；middleware 不啟動、不 resume、不喚醒 B |
| 新增一段 JD 能力說明，對映六章與已註冊的 JD 工具 | 不整批複製 `write-customized-jd`；不新增第二個 JD 寫入者或審核引擎 |

## 3. 與已驗來源的精確差異

1. **A 指引**：`api.py` 的 `ADVISOR_INSTRUCTIONS` 以「。」切出 14 句。其中 11 句訪談方法與 `不顯示隱藏推理。` **逐字採用**。另外 2 句是舊 checkout 後加的 JD 尾句，提到 `write-customized-jd` skill 與舊 JD 工具，**不屬於 CT49／50／51 的已驗來源**，因此不採用，改寫成本案的 JD 能力段並在此列明。
2. **JD 能力段（新寫）**：對映[六章關聯設計](2026-09-12-jd-relational-editor-design.md)與本 App 實際註冊的工具；明說 App 產生並驗證身分、版本、引用與保存結果，LLM 不填 UUID／FK／位置／版本／引用 token。
3. **Skills**：`skills.py` 逐字採用（只有 import 來源改為套件內位置，模組本身不 import 舊 host）。三個 SKILL.md 位元組相同。`write-customized-jd` 及其 references 不採用。
4. **`MEMORY_ACTION_GUIDANCE`**：逐字採用，落在套件 `caliburn_memory/guidance.py`（舊位置 `live_memory.py` 是舊 host 組裝，不採用）。
5. **`BackgroundAvailability`**：保留「只讀可用性、blocked 才提示、已被游標涵蓋就不提示、每個員工輸入只算一次、以 system 區塊而非原話傳達」的已驗語意；資料來源換成本案 `BackgroundAdmissions.read()` 與 `PublicationStore.current()`，覆蓋判斷改用同一個 source owner 的 `plan_saved_batch`。舊 `source_covered` 與舊 row 結構不沿用。

## 4. 先寫的反例

實作前先固定下列反例；每一條都應該在最小實作前失敗。

**指引**
- 已驗的訪談語句在組出來的 system prompt 中**逐字**且依原順序出現；任一句被改寫即失敗。
- 舊的 JD 尾句（提及 `write-customized-jd`）**不得**出現。
- JD 能力段提到的工具名稱必須全部存在於 `build_consultant_tools()`；提到不存在的工具即失敗。
- `MEMORY_ACTION_GUIDANCE` 逐字出現，且其提及的 `repair_memory`、`request_memory_consolidation` 都已註冊。

**Skills**
- 掛載的分析方法**恰好**是三項；出現 `write-customized-jd` 即失敗。
- system prompt 只含方法名稱／用途／路徑，**不含** SKILL.md 內文。
- 透過模型實際走的同一條路由能讀到三個 SKILL.md；讀不到即失敗。
- 資產後端沒有 write／edit／delete／upload／execute；有即失敗。
- `/skills/` 以外的路徑（含 Windows 磁碟機路徑）回可更正的輸入錯誤，不是例外或主機檔案內容。

**背景可用性**
- admission 不是 `blocked`：不加任何區塊。
- `blocked` 但該 target 已被目前 publication 游標涵蓋：不加區塊（整理其實已完成）。
- `blocked` 且未涵蓋：加一個 system 區塊，內容是已驗提示並附未涵蓋範圍；**不是** HumanMessage，也不宣稱 Memory 已更新。
- 同一個員工輸入的多個模型步只計算一次（第二次 `before_agent` 回 None）。
- middleware 全程不呼叫 dispatcher／不 start／不 resume／不推游標。

## 5. 驗收

零 provider 的固定組裝測試；受影響套件與 App 測試全跑；`adoption.json` 逐檔記來源 commit／sha256／差異。真模型與自然品質不在本單位，依 H5 另行授權。

## 6. 實作結果（2026-09-14）

**顧問現在有方法。**`build_consultant()` 組出的 A 顧問帶著已驗訪談指引、六章 JD 能力說明、Memory 行動指引、三項按需分析方法與 16 個已註冊工具；有背景讀取器時再加上可用性提示。

| 交付 | 位置 |
|---|---|
| A 指引＋JD 能力段＋Memory 行動指引 | [consultant_guidance.py](../../experiments/jd-relational-app/src/jd_relational/consultant_guidance.py) |
| 三項分析 Skills 與 `SkillAssets`（套件，位元組相同） | `caliburn_memory/skills.py`、`caliburn_memory/skills/*/SKILL.md` |
| `MEMORY_ACTION_GUIDANCE`（套件，逐字） | `caliburn_memory/guidance.py` |
| 背景可用性提示 | [background_availability.py](../../experiments/jd-relational-app/src/jd_relational/background_availability.py) |
| 組裝入口 | [consultant_app.py](../../experiments/jd-relational-app/src/jd_relational/consultant_app.py) |

### 實際差異

1. 已驗 `ADVISOR_INSTRUCTIONS` 以「。」切出 14 句：11 句訪談方法逐字採用（測試逐句比對來源 commit 並要求順序不變），`不顯示隱藏推理。` 逐字保留，**兩句**提及 `write-customized-jd` 的後加 JD 尾句不採用。
2. 新 JD 能力段對映六章與本 App 實際註冊的 10 個 JD 工具（測試要求段內出現的每個 `jd_*` 名稱都存在於 `build_consultant_tools()`），並明說 UUID／外鍵／位置／版本／引用 token 由 App 產生驗證。`restore_revision`／`undo_ai_turn` 仍不給模型。
3. `MEMORY_ACTION_GUIDANCE` 值的 sha256 `680d4a61…`，測試每次由來源 commit 以 AST 取出同一常數比對；檔案 hash 不同是因為採用的是節錄加新 docstring，不是整檔複製，已記在 `adoption.json`。
4. 背景可用性改用本案 `BackgroundAdmissions.read()`、`PublicationStore.current()` 與 source owner 的 `plan_saved_batch`；舊 `source_covered` 與舊 row 不沿用。middleware 只讀，不 admit／start／resume／推游標。

### 驗證

- App 全組離線 **2890 passed／307 skipped**（新增 32 項）；套件 **154 passed**。零 provider、零連線。
- 變異驗證（改動後核 `git hash-object` 已還原）：關掉「已發布就不提示」→ `test_nothing_is_said_when_the_blocked_target_turned_out_to_be_published` 失敗；拿掉「每個員工輸入只讀一次」→ `test_the_notice_is_read_once_per_employee_input` 失敗；改寫一句已驗指引→ `test_every_verified_interview_sentence_survives_verbatim` 失敗。
- `uv build` 產生的 wheel 內含三個 `caliburn_memory/skills/*/SKILL.md`，不需額外 hatch 設定。

### 首敗與限制

首敗：反例先假設已驗指引是 10 句（其實切出 14 句）；`LsResult.entries` 是 dict 不是路徑字串、`ReadResult` 以 `file_data['content']` 帶內容、Skills middleware 的屬性是 `system_prompt_template`——都是我對既有 API 形狀的假設錯誤，改測試不改產品。`SkillAssets` 確實**有** `upload_files`（來自 backend protocol）但不實作，反例因此改成「呼叫會 `NotImplementedError`」而不是「屬性不存在」，這比原本的寫法更接近真正的保證。

限制：這是**固定組裝**驗收。沒有真模型、沒有自然訪談、沒有品質判斷；沒有驗這些指引實際上讓模型問得更好。`build_consultant()` 尚未接進 `managed_app` 的日常入口，日常 AI 仍未啟用。背景可用性的讀取器由呼叫者提供，真 PG 與新程序情境在 R3 第 7 項另驗。
