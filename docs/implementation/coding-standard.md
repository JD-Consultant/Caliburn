# 程式撰寫規範：可讀、明確、可測的實作

- 狀態：**現行程式撰寫規範** 。適用新程式、測試、腳本與受影響的修改範圍，不要求無關程式全面改寫。
- 責任：[程式組織](code-organization.md)管模組、依賴方向及共用命名；本頁管函式／實例／Service 的寫法、資源與錯誤處理、範例及審查。產品規則仍由[架構入口](../target-architecture-map.md)路由，不以風格重訂業務契約。
- 原則：**讓下一位開發者容易判斷輸入、效果、依賴與失敗。** 抽象、行數及設計模式依這個目的取捨。範例只說明寫法，不能取代正式 API／工具 schema 或視為產品已完成。

依修改範圍查閱：

| 工作 | 本頁入口 |
|---|---|
| 寫函式、型別或 Service | [名稱與型別](#2-名稱參數與型別)、[函式與資料](#3-函式與資料短是結果不是目標)、[實例與依賴](#4-實例service-與解耦) |
| 處理 I/O、取消或前端狀態 | [錯誤與資源](#5-錯誤資源非同步與副作用)、[TypeScript／React](#6-typescriptreact-的可讀寫法) |
| 寫測試、診斷或日誌 | [測試與抽象審查](#7-測試註解與抽象審查)、[執行證據](#71-讓執行證據可查可比較可驗證)、[Log](#72-log-的格式責任與查閱) |
| 審查或調整工具設定 | [自動檢查、人工審查與例外](#8-如何執行而非只要求寫得漂亮) |

## 1. 採用依據與取捨

| 第一手來源 | 借鑑範圍／本案界線 |
|---|---|
| [PEP 8](https://peps.python.org/pep-0008/)與 [Google Python](https://google.github.io/styleguide/pyguide.html) | 一致、可讀、清楚的名稱及例外處理；本案由 Ruff 定格式，不照搬 Google 的全部限制或改成另一套 formatter |
| [Google TypeScript](https://google.github.io/styleguide/tsguide.html) | 明確型別、避免不受檢查的 `any`、避免難讀表達式；其內部工具／舊 TSLint 示例不沿用，採目前 ESLint／typescript-eslint |
| [Google code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html) | 審查複雜度、命名、測試與註解；不為想像中的未來泛化，不用個人口味代替理由 |
| [Microsoft DI 指引](https://learn.microsoft.com/en-us/dotnet/core/extensions/dependency-injection/guidelines) | 借顯式依賴、小責任、生命週期及避免 service locator；不搬 .NET container 或要求 Python 每類都有 interface |
| [FastAPI dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)與 [Python Protocol](https://typing.python.org/en/latest/reference/protocols.html) | HTTP 使用框架注入；內層普通參數／建構注入，依實際 I/O 或策略替換需要使用窄 Protocol／callable |
| [Python asyncio](https://docs.python.org/3/library/asyncio-task.html#task-cancellation)與 [SQLAlchemy async](https://docs.sqlalchemy.org/en/21/orm/extensions/asyncio.html#using-asyncsession-with-concurrent-tasks) | 清理、取消傳遞與並行 Session 隔離；框架能力不等於產品已具備恢復／交易保證 |
| [React state 結構](https://react.dev/learn/choosing-the-state-structure)與 [Effect 使用界線](https://react.dev/learn/you-might-not-need-an-effect) | 避免矛盾／重複狀態，能由現有輸入計算就不另存；Effect 用於外部同步，不拿它串起全部產品流程 |

這些是多個成熟實踐的可借鑑部分，**不是所有大廠共同使用同一份 coding standard** 。優先現行受支援 API；「最新」不等於重寫穩定程式或引入尚未需要的語言技巧。套件版本仍由[選型](technology-decisions.md)與 lock 管理。

## 2. 名稱、參數與型別

大小寫／目錄／動賓命名沿[程式組織 §3](code-organization.md#3-名稱要能表達身分時間與效果)，本頁不另造詞彙表。

- 名稱說明**這是什麼、哪個範圍、哪個時點** ：`published_snapshot`、`candidate_revision`、`input_tokens`、`timeout_seconds`，不用脫離語境的 `data2`、`temp`、`new_obj`。短區域的 `index`／`item` 可以，跨模組結果不可以只叫 `data`。
- `get`／`read`／`list` 不偷偷寫業務資料；`create`／`publish` 等效果名稱須與實際邊界相符。名稱相近但語意不同的 pending／formal、candidate／published 不合成模糊的 `save`。
- 避免 `run(data, True, False)` 及 mode 字串控制完全不同流程；不同操作用具名函式，容易混淆的 Python 參數用 keyword-only，TS 用有意義的 options。不要為兩個清楚參數硬包 DTO。
- 函式參數與回傳標型別；Python 區域變數及 TS 區域推導不重複標註。TS 模組公開非元件函式標明回傳，React 元件／簡單 callback 可交編譯器推導。邊界形狀由唯一 schema 生成，不重寫一套「比較好看」的 wire 型別。
- 內部具名資料先用 `dataclass`／`Enum`／明確 union；外部驗證用既有 Pydantic／schema。Pydantic 不是所有業務物件必須繼承的基底。少數關鍵身分確有混用風險才引入 `NewType`，不將每個字串包成 class。
- `None` 只表示契約定義的缺省／不存在；不得兼表示「失敗」及「成功但空」。合法互斥狀態用 union／enum，不堆 `is_done`、`is_failed`、`is_cancelled` 三個可同時成立的旗標。
- 未知外部值先驗證再使用：TS 用 `unknown`；Python 動態 SDK 邊界可局部容許 `Any`，但不能流入領域。不用 `as unknown as T`／`cast`／`!` 或 ignore 假装資料有效；型別註解不會在執行時驗資料。
- Pydantic 自訂 validator 須核其 mode、default 與實際接受值；`plain` 返回會略過內建欄位驗證，`wrap` 也可能不呼叫原 handler，default 預設未必經驗證。優先既有 schema／生成約束，有必要才補驗證；不得悄悄截斷或改寫原話，不手改生成模型。允許的轉換依契約測試，不全面套 strict。依據：[Pydantic validators](https://pydantic.dev/docs/validation/latest/concepts/validators/)。
- 原始訪談、原生模型 items 及既定工具名稱不可因「命名／格式統一」而改寫。schema keys、provider keys 及應用內變數是不同命名邊界。

## 3. 函式與資料：短是結果，不是目標

一個函式維持一個可描述的效果與清楚抽象層次。先處理不合法前置條件，再保留可順讀的正常路徑；不強迫每函式最多若干行／參數，也不為行數把一次交易拆到找不到提交處。簡單 comprehension 可以，多層巢狀、三元式及帶副作用的 comprehension 改成普通迴圈。不要使用可變預設值、隱藏 I/O 的 property、萬用 `**kwargs` 傳整包環境。

例如，以下是**區間型別／前置條件寫法示意** ；來源資格與越界判斷仍須訪談領域模組驗證，不靠這個型別保證：

```python
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InterviewRange:
    start_sequence: int
    end_sequence: int

    def __post_init__(self) -> None:
        if self.start_sequence < 1:
            raise ValueError("start_sequence must be positive")
        if self.end_sequence < self.start_sequence:
            raise ValueError("end_sequence must not precede start_sequence")


def describe_interview_range(interview_range: InterviewRange) -> str:
    return f"訪談序號 {interview_range.start_sequence}–{interview_range.end_sequence}"
```

比 `format_data([a, b], True)` 更清楚，不表示每個格式化函式都需要新 class。不可變值適合固定查詢範圍／已發布投影；`frozen` 是淺層限制，內含可變 list 並不因此變不可變。候選／Graph State 仍按其契約更新，不強制把一切物件凍結。

純分析／轉換不自行讀環境、取現在時間、呼叫模型或開資料庫；時間、ID、client 在實際需要的邊界提供。這方便測試，但不要求每次 `uuid4()` 都建立一個 factory。順序敏感的來源／工具 items 不為整理寫法而排序、去重或集合化。

## 4. 實例、Service 與解耦

Service 是**應用用例責任** ，不等於必須叫 `SomethingService` 的 class，更不等於獨立部署。

公開介面須交代作用範圍、前置條件、結果／副作用、失敗及資源生命週期；呼叫者不必讀內部表格或私有狀態才能正確使用。

| 情況 | 優先寫法 | 不採用 |
|---|---|---|
| 純規則、投影、少量無狀態用例 | module-level 具名函式＋明確參數 | 只有 `staticmethod` 的工具 class |
| 多個操作共用有生命週期的依賴 | 小型實例，建構子明列依賴 | 方法內臨時 new client／engine、全域 service locator |
| 值與結果 | dataclass／union；必要不變量由相應領域模組維護 | 動態屬性袋、繼承 transport DTO 的領域模型 |
| 外部 I/O 的測試／替換接縫 | 消費者所需的窄 Protocol／callable | 每個 class 都配 interface、AbstractBase／Factory／Impl 三件套 |
| 跨 feature 的一次業務動作 | workflow 協調公開 service／query | Router／Agent 直碰多個模組的 SQL，或複製 validator |

實例生命週期在組裝根／框架 lifespan 明確管理。長壽 client／connection pool 可以共享；一次請求的 mutable session、候選、job scope 不能藏進全域單例。建構子不發付費請求、不偷啟背景工作。FastAPI `Depends` 留在 HTTP 邊界；HTTP／模型工具呼叫相同的普通業務入口。不要把整個 `app`、container、所有 services 或全份 Graph State 傳給只需一項依賴的函式。

**Service 接線示意，非已存在 API 或完整交易實作：**

```python
async def rename_job_file(
    session: AsyncSession,
    *,
    job_file_id: UUID,
    display_name: str,
) -> JobFile:
    validated_name = validate_display_name(display_name)
    return await persistence.rename_job_file(
        session,
        job_file_id=job_file_id,
        display_name=validated_name,
    )
```

此形狀讓 persistence 寫 SQL、service 管用例；呼叫方明確掌握交易，內層不 commit。`AsyncSession` 可以出現在 service／workflow，**不能因此洩入純 models** 。上例的型別及依賴由真實 feature 定義，正式寫入仍需原契約的作用域、重送及權限機制；不能只抄此片段便宣稱完成。

依實際變化、協作及驗證需要設計介面，可涵蓋 I/O、Prompt／Context 策略及工具組裝；例如 renderer 的消費者只需要 `render_html(...) -> bytes`，便保持這個小介面，由背後實作處理渲染與資源。是否採用插件或既有框架按整體收益決定。組合優先；繼承留給框架契約或真實替代關係，不建立承載 A／B1／B2 全部業務的 `BaseAgent`。共同執行機制與角色分析規則不能因相似迴圈而合併權責。

## 5. 錯誤、資源、非同步與副作用

- 輸入不合法用明確驗證／typed error；領域不 raise HTTPException。Transport 再映射 HTTP／模型可見錯誤，不在領域混入 UI 文案。`assert` 用測試／內部開發檢查，不作資料安全／權限檢查。
- 只 catch 能處理的錯誤，縮小 try 範圍；轉譯例外用 `raise ... from error` 保留原因。最外層隔離可以 catch `Exception`，但須記失敗並清理，不能吞成空清單或 success。錯誤訊息與一般 log 都不得洩露敏感 payload。
- 回傳 union 適合正常可預期分支；exception 適合異常中斷。每個邊界只選清楚的一種契約，不同一個失敗有時回 `None`、有時 dict、有時 throw。不自行創建全產品 `Result<T>`／錯誤框架。
- 用 `with`／`async with`、`try/finally` 表達資源釋放；借入的依賴由建立並管理其生命週期的模組關閉，不能隨手 close 共用 client。每個並行工作獨立 session，不跨 coroutine 共用 mutable transaction。
- FastAPI 的 App 資源沿 `lifespan` 管理；使用它時不能假設舊 startup／shutdown handlers 仍執行。請求 dependency 的 `yield` 收尾時點依 scope 及鎖定版核對；成功回應所承諾的正式保存必須先完成，不能交給回應送出後的清理階段才 commit。串流仍需要的資源也不能提前關閉。依據：[lifespan](https://fastapi.tiangolo.com/advanced/events/)、[yield dependency](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/)。
- async 路徑不呼叫 blocking sleep／同步網路；有耗時同步工作則使用已選框架的受控機制。並行要有數量界線且語意獨立；不能為「較新寫法」將已要求順序執行的工具改成 `gather`。
- 任務需有人等待或持有、觀察失敗並於關閉時收尾；不能裸 `create_task`。`TaskGroup` 適用同一作用域內的並行工作，不等於持久背景工作的恢復機制。
- `CancelledError` 清理後通常重新拋出；不把程序取消視為產品 Turn 已取消／已回滾。取消、重試、原結果對帳遵循執行資格與恢復機制，不在 SDK、service、工具各套一層 retry。
- DB 交易短且明確，模型／網路等待不持有業務交易。SQL 參數化、識別符用驅動安全機制；程式先查存在不替代 DB constraint／競爭處理。具體提交／恢復沿[資料接線](data-and-contracts.md)，不另造 UnitOfWork 引擎。

## 6. TypeScript／React 的可讀寫法

函式元件、具名 props、單向資料流；hook 名稱必須真的是 hook，不把普通工具函式加上 `use`。已在 query cache 的 server state 不另外複製到全域 store。局部編輯草稿與正式資料分開，能從 props／state 算出的顯示文字在 render 推導，不用 Effect 同步第二份。

使用者點擊／送出觸發的寫入由 event handler 或其 mutation 處理，不先改一個 state，再用 Effect 監看它發命令。Effect 用於外部同步；訂閱、計時器與連線的建立／清理需對稱，能承受 setup → cleanup → setup。依賴值不靠關掉 Hooks lint 或「只跑一次」ref 隱藏；切檔、卸載及重入後，舊作用範圍的事件不得影響目前畫面。既有恢復查詢仍依其契約，不把開發模式每次 GET 都限制為一次。依據：[React 互動與 Effect](https://react.dev/learn/you-might-not-need-an-effect#sending-a-post-request)、[Effect 清理與重入](https://react.dev/learn/synchronizing-with-effects#how-to-handle-the-effect-firing-twice-in-development)。

以下是**可執行的局部表單狀態示例** ，不是 A Turn／Memory 的正式狀態機：

```typescript
type SaveState =
  | { status: 'idle' }
  | { status: 'saving' }
  | { status: 'failed'; message: string };

export function getSaveLabel(state: SaveState): string {
  switch (state.status) {
    case 'idle':
      return '儲存';
    case 'saving':
      return '儲存中';
    case 'failed':
      return state.message;
  }
}
```

這比多個互斥布林更難表示矛盾狀態。外部新增狀態不能靠 `default: return '成功'` 吞掉；協定未知值在驗證邊界明示處理。前端不得依這種 UI state 推定正式提交成功。

Promise 必須 await、return 或有明確錯誤處理；不要把 async 函式直接塞到要求同步回呼的地方。事件 handler 可用 `void saveDraft().catch(showSaveError)`，但 `void` 本身**不處理錯誤** 。取消 fetch／忽略過時結果不代表後端業務取消。缺少值不能靠非空斷言跳過檢查。

`readonly` 適用讀取 props／投影；不要突變 props、React state 或共用 cache 物件。型別 `type`／`interface` 按用途選，union 用 type；不強制全轉一種。表單、HTTP client、業務規則與畫面不擠在同一大元件，亦不為每個 JSX 區塊新增檔案。

## 7. 測試、註解與抽象審查

本節管測試程式與診斷的寫法；開發流程依[開發規範](development-standard.md)，測例覆蓋及執行層級依[驗證計畫](verification-plan.md)。

測試也遵守同一命名與可讀性：清楚 Arrange／Act／Assert，測可觀察行為，名稱說明情境與保證。Fixture 只提供本測例需要的資料，不建立全產品測試容器。表格測試適用相同規則的輸入變體，不把無關場景塞進一個多重 if 測試。

I/O 替身在實際外部邊界；不 mock 受測規則本身，也不把每個 helper 的呼叫順序鎖死。多檔案隔離、交易／鎖、checkpoint 及取消競爭仍須相應 PG／程序測試。時間／隨機在必要接縫可控，不用反覆 sleep 測競爭。

HTTP 測試可用 FastAPI `dependency_overrides` 替換外部依賴，fixture 負責復原，並行測例不共用可變 overrides；普通 service 測試直接提供依賴。override 也會略過原依賴的子依賴，測權限／保存時不能把該受測邊界一起替掉。fixture 可共享適合共享的基礎設施，session、職務資料及候選狀態須隔離；取得資源即配清理，不把多次副作用集中在一個 `yield` 前，因前段失敗不會執行該 fixture 的 yield 後清理。依據：[FastAPI 測試替換](https://fastapi.tiangolo.com/advanced/testing-dependencies/)、[pytest fixture 清理](https://docs.pytest.org/en/stable/how-to/fixtures.html)。

Docstring／註解解釋非顯然的範圍、單位、效果、失敗與原因；不用重述每行程式。公開邊界或易誤用用例有簡短契約，例外與限制必要時才加 Args／Returns／Raises。命名用英文；規格／註解可繁中，但同一段保持一致。持久格式或恢復不變量宜連到責任文件，不貼整份設計。

提取共用程式前檢查：**是否同一語意、是否一起變動、消費者是否已有、是否真的降低理解成本？** 兩段形狀相似但一個是候選、一個是正式發布，不能只為 DRY 合併成 flag 驅動萬用函式。純一行代理若沒有邊界價值可以去除；有契約隔離價值的薄 adapter 不因行數少而刪掉。

### 7.1 讓執行證據可查、可比較、可驗證

真人使用／測試與合成對照都須能方便查閱執行證據，不能只有實驗腳本保留資料。一般 log 只記必要的安全中繼資料，如錯誤分類、關聯身分與耗時；受控診斷可查工作正文，兩者的保存與存取邊界分開。

[本機診斷](../runbook.md#在-datagrip-查某個職務檔案的-ai-執行紀錄)與正式操作資料是現有查閱路徑；DataGrip、CLI、現成 trace 平台或開發者介面皆可按定位成本選用，不要求放進受訪者 UI。觀測工具可替換，正式保存及業務裁決仍由原責任模組負責。

#### 實際輸入與執行因果

- 核對當時實際組裝並送出的 Prompt、Context、工具定義及模型設定，不能只記預設檔名或目前版本。工具保留模型原 arguments、call ID 與實際結果；正文沿既有遮蔽及資料範圍規則，不把憑證或 `encrypted_content` 放進診斷。
- 從職務檔案及訪談輪次可定位該次執行，再查模型步驟與工具往返；失敗或取消而未取得正式訪談序號的工作仍可沿執行身分定位。查閱者不應每次自行解碼 checkpoint 或撰寫臨時解析程式；常用定位與查閱方式須在 runbook 有可重用入口。
- Memory 要能核對該輪綁定的版本及需要的歷史正文，分清「當時可讀取的 Memory」「已放進 Context 的導覽／正文」與「經工具實際讀到的內容」；Plan 與 JD 亦按其既有版本／候選契約查閱。不能拿目前最新內容解釋過去一輪，也不能把可讀取視為已提供給模型；壓縮後只呈現實際可查的資料，不推造不可見內容。
- 能沿同一次工作關聯「模型要求 → App 綁定的可信 scope → handler 結果 → 正式保存／採用」，不讓模型參數冒充 App 權限。工具回傳與業務操作可能不是一對一，沿原操作身分及修訂因果核對。
#### 缺失、安全與查閱驗收

- 明示缺失、截斷、遮蔽及擷取時點；按需副本不冒充即時全量紀錄。`recorded` 只表示取得回傳，不保證成功或正式採用；`not_recorded` 不能推定未執行。部分輸出與未知用量如實保留，不補造結果或歸零。
- 診斷／匯出失敗不得改寫正式結果或觸發業務重送。這不豁免 checkpoint、操作結果、額度等原本具有恢復／准入責任的耐久保存；它們仍依[執行接線](agent-execution.md)處理失敗。
- 正文查閱權限、一般統計與外送目的地分開控管；啟用本機診斷不等於允許第三方 exporter 外送。敏感欄位遮蔽不代表整份訪談已匿名化。
- 觀測寫法也須以反例驗證：成功、拒絕、取消／逾時、部分結果、重試關聯、跨職務隔離、憑證遮蔽與診斷失敗。另以「已知某份檔案、某輪出現異常」走查操作文件，確認能沿既有入口找到當時 Context、Memory、工具參數／結果及正式效果，查閱不觸發模型重跑或業務重送。測有無足夠證據辨認問題，不把每條 log 文案或每個內部 span 鎖成產品契約。

依據及尚未驗證的取捨見[持續對照與可觀測性研究](../research/engineering/2026-10-08-agent-experimentability-and-observability.md)。OpenTelemetry GenAI 欄位仍在 Development；本頁採觀測責任，不直接引入其欄位或要求更換 SDK。

### 7.2 Log 的格式、責任與查閱

**日誌是前後端與背景工作的工程基線。** 須能回答何時、哪個模組、哪次操作、發生什麼及已知結果；不等出現故障才臨時加 `print`／`console.log`。以下是實作與審查要求，現有接線的符合程度仍須核查。

#### 格式與關聯

- **結構與事件：** 一般執行日誌採可機器解析的結構化欄位，例如 JSONL；記 UTC 時間、等級、模組、穩定事件名稱及簡短安全說明，按事件加耗時、錯誤分類與已知結果。應用版本及有效日誌設定在啟動時可查。欄位語意一致，不從自由文字猜狀態；事件發生與後來擷取的時間分清，缺值不補造成成功或零。
- **關聯與作用域：** 沿既有職務、execution、Turn／批次、Step、tool call 及操作身分，按當下可取得的資料關聯。區分 HTTP request、模型 logical request、attempt 與 provider request；重試保留原工作關係，另辨每次 attempt。已有 trace 時連 trace／span ID；啟動等事件沒有職務身分就不硬填。非同步工作各自綁定及釋放 context，不用全域可變的「目前職務」；診斷 ID 不授予業務權限。
#### 等級、記錄責任與敏感內容

- **等級：** DEBUG 記按需診斷細節；INFO 記正常的重要生命週期與結果；WARNING 記需注意的異常、降級或可恢復故障；ERROR 記操作未能完成的非預期失敗；CRITICAL 留給服務無法繼續。正常使用者取消、驗證拒絕及沒有資料不一律記 ERROR；安全異常另依實際風險。既有 provider 故障分類與等級沿[執行接線](agent-execution.md)，不能僅靠 HTTP status 判斷整個工作結果。
- **記錄責任：** 由掌握事件語意的邊界記錄重要開始、結果、重試、取消及恢復，避免每層 catch 同一例外後重印 stack。需要其他層事件時記其不同階段與關聯，不假裝新故障。只有正式保存已確認才記已保存；COMMIT 回覆不明就記未知並沿原機制核對。log 與 HTTP 200 都不能代替正式操作結果，也不要求每個函式進出或每個串流片段都輸出。
- **例外與敏感內容：** 記安全錯誤型別／代碼及定位，stack trace 只在核實可安全輸出的邊界保留；不直接 dump SDK exception、cause chain、frame locals、headers 或完整 URL query。provider 原錯誤仍沿既有遮蔽契約。正文查閱依 §7.1；DEBUG 亦不豁免。輸出端正確編碼與限制不可信文字長度，防止換行／控制字元偽造事件；截斷須可辨識。
#### 組裝、輸出與保存

- **組裝與前後端分工：** Python 沿標準 `logging` 的 module logger，由 App 啟動處集中配置 level、handler、formatter 及遮蔽，避免各模組重設 logger 或重複 handler；框架及第三方 logger 一併核對。前端在 HTTP／串流／畫面錯誤邊界保留安全原因及可用關聯，方便接到後端查閱，不散落傾倒狀態的 console 輸出。接第三方收集或新增上報入口另按資料與權限契約，這裡不預設外送。
- **輸出與保存：** 明定本機／Docker 的取得入口、level 設定、輪替或容量上限、保留期限及存取／刪除方式，落實後寫進 runbook。避免在 async 熱路徑做慢速同步輸出；若採 queue／exporter，須有容量、背壓或丟棄政策及有界關閉清理，缺失可辨識。日誌故障不得遞迴刷錯、改寫業務結果或觸發重送；必要的耐久保存仍沿原契約，不能改成可丟棄 log。

驗收核事件、必要欄位與可查閱性，不鎖死文案；依受影響範圍驗並行工作不串 ID、重試可分辨、正常取消不誤報、敏感欄位與例外不洩露、輸出失敗不改正式效果，以及實際輪替／容量設定。Log 記事件，trace 關聯執行跨度，受控診斷提供必要正文；三者協作，但日誌不成為第二套業務或恢復資料庫。

依據：[Python logging](https://docs.python.org/3/library/logging.html)、[Logging Cookbook](https://docs.python.org/3/howto/logging-cookbook.html)、[OpenTelemetry Logs data model](https://opentelemetry.io/docs/specs/otel/logs/data-model/)、[OWASP Logging](https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html)。以上具體等級與責任是本案規範，不表示已安裝 OTel 或觀測平台；Log data model 與尚在演進的 GenAI 欄位分別核對。

## 8. 如何執行，而非只要求「寫得漂亮」

### 自動檢查與行為驗證

| 檢查 | 本案執行方式 | 不能證明 |
|---|---|---|
| Python 格式／基本正確性／命名 | Ruff formatter＋E／F／I／UP／B／ASYNC；補 N、A、RUF006、RUF100 | 名稱是否符合業務、某 task 是否耐久 |
| Python 型別 | mypy strict；公開邊界及可疑動態值審查 | runtime payload 一定合法 |
| TS／React | TypeScript strict；ESLint recommended type-checked、Hooks、Promise、型別 import、switch 分支覆蓋、已棄用 API（`no-deprecated`）；Prettier | 後端已提交、UI 旅程可用 |
| 靜態分層 | 既有 import／AST 邊界檢查 | 任意動態呼叫也安全，或所有責任切分合理 |
| 用例正確性 | 相應單元／整合／產品反例 | 程式易讀與無過度設計 |
| 審查 | 本頁責任、名稱、副作用、錯誤／恢復與抽象判準 | 不以個人喜好取代契約／實測 |

### 人工審查

工具檢查之外，按本次改動觸及的責任逐項審查；每個問題需指向具體程式、契約或可重現反例。下表是審查判準，**不表示目前程式已全部符合**，也不要求小修重驗無關範圍。

| 面向 | 要核對的效果 | 責任依據 |
|---|---|---|
| 模組與依賴 | 同一規則集中、修改範圍可理解；公開入口不洩漏私有狀態，無循環依賴或無用途抽象 | [程式組織](code-organization.md)、本頁 §3–4 |
| Interface 與契約 | 輸入、回傳、錯誤、副作用與版本語意明確；schema／生成物與實際 handler 相符 | 本頁 §2、§4–5、[契約策略](../contract-strategy.md) |
| 權限、網路與秘密 | App 驗作用範圍；本機 Host／Origin、可信外送目的地及資料範圍沿有效配置；秘密不進模型參數或前端，client 生命週期明確 | [介面 §5](interface-and-delivery.md#5-安全與操作邊界)、[信任邊界](../architecture/delivery-and-operations.md#4-信任與權限邊界)、本頁 §4–5 |
| 資料、交易與恢復 | 正式來源唯一、候選與採用可辨、競爭及結果不明沿原操作核對；診斷不參與業務裁決 | [資料接線](data-and-contracts.md)、[保存架構](../architecture/persistence.md) |
| 並行、取消與重試 | 資源有人關閉、工作有人收尾；取消語意不混淆、重試責任不疊乘、已發生效果不重做 | 本頁 §5、[執行接線](agent-execution.md) |
| 前端與跨層呈現 | 生成契約有 runtime 驗證；草稿、串流與正式結果分明，過時回應不跨檔案，內容安全呈現 | 本頁 §6、[介面與交付](interface-and-delivery.md) |
| 可測性、對照與觀測 | Prompt／Tool／元件在責任邊界替換，沿正式路徑驗證；可從實際輸入追到結果且證據不洩密 | 本頁 §4、§7、[開發規範](development-standard.md) |
| 效能與持續維護 | I/O、交易、並行量與正文成本有界；依量測找瓶頸，避免重複計算／狀態及為未來泛化 | 本頁 §3–6、[開發規範 §3.1](development-standard.md#31-依風險配置驗證與交付粒度) |

新增產品安全政策、狀態或跨層能力仍先維護其責任契約；不能藉本表擴充認證模型、另造 validator 或更動既有恢復資格。

### 設定、執行與例外

命令沿 [backend README](../../apps/api/README.md)與 [frontend README](../../apps/web/README.md)，規則的實際設定以 pyproject／eslint／tsconfig 為準，不在本頁手抄第二份 config。設定變更先跑反例確認能報錯，再驗既有程式，記入原任務 evidence；未覆蓋的項目如實列為審查責任。

核對實際受測檔案、版本、設定及例外，本機與交付檢查沿相同入口。Ruff format 與 lint 分開驗：formatter 不排序 import，需相應 lint 規則；不要啟用彼此衝突的格式／lint 要求。mypy strict 通過仍須核未檢查模組與 import 產生的 `Any`，不以全域 `ignore_missing_imports`／`follow_imports=skip` 隱藏整片型別缺口。靜態工具能驗的交給工具；責任、可讀性、測試有效性及資料競爭仍由審查與行為測試負責。依據：[Ruff formatter](https://docs.astral.sh/ruff/formatter/)、[mypy import 管理](https://mypy.readthedocs.io/en/stable/running_mypy.html)。

格式交工具，不手排齊空白；不開啟所有 lint 規則，也不新增第二套 formatter。生成物只在來源／生成器修，不為 lint 手改它。例外用最窄的 suppression，列原因及 rule code；禁止全檔 `type: ignore`／大範圍停用 lint 掩蓋缺陷。`RUF100` 用於清理已不需要的 noqa，不保證所有人工理由合理。

依據：[Ruff rules](https://docs.astral.sh/ruff/rules/)、[RUF006](https://docs.astral.sh/ruff/rules/asyncio-dangling-task/)、[typed linting](https://typescript-eslint.io/getting-started/typed-linting/)、[no-floating-promises](https://typescript-eslint.io/rules/no-floating-promises/)、[switch exhaustiveness](https://typescript-eslint.io/rules/switch-exhaustiveness-check/)、[no-deprecated](https://typescript-eslint.io/rules/no-deprecated/)。這是目前工具鏈的有界增補，非要求換框架。

`no-deprecated` 用於 `apps/web`，補足 TypeScript 不會對 `@deprecated` 報錯的檢查。使用方式與其餘型別 lint 規則相同；驗證見[規範稽核](../history.md#source-a75c36d876a672e0f607)。

規則依成熟工程規範、框架契約或可核對的維護／錯誤案例持續修訂，同步本頁、設定與必要回歸；工具設定變動用代表性反例核實檢查效果。規範能演進，但不能只為讓某個 patch 過關而關掉檢查；也不因此重啟整個專案的架構討論。
