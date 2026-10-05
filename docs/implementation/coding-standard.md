# 程式撰寫規範：可讀、明確、可測的實作

- 狀態：**現行程式撰寫規範** 。適用新程式、測試、腳本與受影響的修改範圍，不要求無關程式全面改寫。
- 責任：[程式組織](code-organization.md)管模組、依賴方向及共用命名；本頁管函式／實例／Service 的寫法、資源與錯誤處理、範例及審查。產品規則仍由[架構入口](../target-architecture-map.md)路由，不以風格重訂業務契約。
- 原則：**讓下一位開發者容易判斷輸入、效果、依賴與失敗；不是讓程式看起來抽象、短或用了最多設計模式。** 範例只說明寫法，不能取代正式 API／工具 schema 或視為產品已完成。

## 1. 採用依據與取捨

| 第一手來源 | 借鑑範圍／本案界線 |
|---|---|
| [PEP 8](https://peps.python.org/pep-0008/)與 [Google Python](https://google.github.io/styleguide/pyguide.html) | 一致、可讀、清楚的名稱及例外處理；本案由 Ruff 定格式，不照搬 Google 的全部限制或改成另一套 formatter |
| [Google TypeScript](https://google.github.io/styleguide/tsguide.html) | 明確型別、避免不受檢查的 `any`、避免難讀表達式；其內部工具／舊 TSLint 示例不沿用，採目前 ESLint／typescript-eslint |
| [Google code review](https://google.github.io/eng-practices/review/reviewer/looking-for.html) | 審查複雜度、命名、測試與註解；不為想像中的未來泛化，不用個人口味代替理由 |
| [Microsoft DI 指引](https://learn.microsoft.com/en-us/dotnet/core/extensions/dependency-injection/guidelines) | 借顯式依賴、小責任、生命週期及避免 service locator；不搬 .NET container 或要求 Python 每類都有 interface |
| [FastAPI dependencies](https://fastapi.tiangolo.com/tutorial/dependencies/)與 [Python Protocol](https://typing.python.org/en/latest/reference/protocols.html) | HTTP 使用框架注入；內層普通參數／建構注入，真正 I/O 替換點才用窄 Protocol／callable |
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

只有實際需要替換的 I/O 才抽介面，例如 renderer 的消費者只需要 `render_html(...) -> bytes`，就不設計未使用的 renderer plugin 平台。組合優先；繼承留給框架契約或真實替代關係，不建立承載 A／B1／B2 全部業務的 `BaseAgent`。共同執行機制與角色分析規則不能因相似迴圈而合併權責。

## 5. 錯誤、資源、非同步與副作用

- 輸入不合法用明確驗證／typed error；領域不 raise HTTPException。Transport 再映射 HTTP／模型可見錯誤，不在領域混入 UI 文案。`assert` 用測試／內部開發檢查，不作資料安全／權限檢查。
- 只 catch 能處理的錯誤，縮小 try 範圍；轉譯例外用 `raise ... from error` 保留原因。最外層隔離可以 catch `Exception`，但須記失敗並清理，不能吞成空清單或 success。錯誤訊息與一般 log 都不得洩露敏感 payload。
- 回傳 union 適合正常可預期分支；exception 適合異常中斷。每個邊界只選清楚的一種契約，不同一個失敗有時回 `None`、有時 dict、有時 throw。不自行創建全產品 `Result<T>`／錯誤框架。
- 用 `with`／`async with`、`try/finally` 表達資源釋放；借入的依賴由建立並管理其生命週期的模組關閉，不能隨手 close 共用 client。每個並行工作獨立 session，不跨 coroutine 共用 mutable transaction。
- async 路徑不呼叫 blocking sleep／同步網路；有耗時同步工作則使用已選框架的受控機制。並行要有數量界線且語意獨立；不能為「較新寫法」將已要求順序執行的工具改成 `gather`。
- 任務需有人等待或持有、觀察失敗並於關閉時收尾；不能裸 `create_task`。`TaskGroup` 適用同一作用域內的並行工作，不等於持久背景工作的恢復機制。
- `CancelledError` 清理後通常重新拋出；不把程序取消視為產品 Turn 已取消／已回滾。取消、重試、原結果對帳遵循執行資格與恢復機制，不在 SDK、service、工具各套一層 retry。
- DB 交易短且明確，模型／網路等待不持有業務交易。SQL 參數化、識別符用驅動安全機制；程式先查存在不替代 DB constraint／競爭處理。具體提交／恢復沿[資料接線](data-and-contracts.md)，不另造 UnitOfWork 引擎。

## 6. TypeScript／React 的可讀寫法

函式元件、具名 props、單向資料流；hook 名稱必須真的是 hook，不把普通工具函式加上 `use`。已在 query cache 的 server state 不另外複製到全域 store。局部編輯草稿與正式資料分開，能從 props／state 算出的顯示文字在 render 推導，不用 Effect 同步第二份。

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

測試也遵守同一命名與可讀性：清楚 Arrange／Act／Assert，測可觀察行為，名稱說明情境與保證。Fixture 只提供本測例需要的資料，不建立全產品測試容器。表格測試適用相同規則的輸入變體，不把無關場景塞進一個多重 if 測試。

I/O 替身在實際外部邊界；不 mock 受測規則本身，也不把每個 helper 的呼叫順序鎖死。多檔案隔離、交易／鎖、checkpoint 及取消競爭仍須相應 PG／程序測試。時間／隨機在必要接縫可控，不用反覆 sleep 測競爭。測試品質及 Red–Green–Refactor 沿[開發規範](development-standard.md)。

Docstring／註解解釋非顯然的範圍、單位、效果、失敗與原因；不用重述每行程式。公開邊界或易誤用用例有簡短契約，例外與限制必要時才加 Args／Returns／Raises。命名用英文；規格／註解可繁中，但同一段保持一致。持久格式或恢復不變量宜連到責任文件，不貼整份設計。

提取共用程式前檢查：**是否同一語意、是否一起變動、消費者是否已有、是否真的降低理解成本？** 兩段形狀相似但一個是候選、一個是正式發布，不能只為 DRY 合併成 flag 驅動萬用函式。純一行代理若沒有邊界價值可以去除；有契約隔離價值的薄 adapter 不因行數少而刪掉。

## 8. 如何執行，而非只要求「寫得漂亮」

| 檢查 | 本案執行方式 | 不能證明 |
|---|---|---|
| Python 格式／基本正確性／命名 | Ruff formatter＋E／F／I／UP／B／ASYNC；補 N、A、RUF006、RUF100 | 名稱是否符合業務、某 task 是否耐久 |
| Python 型別 | mypy strict；公開邊界及可疑動態值審查 | runtime payload 一定合法 |
| TS／React | TypeScript strict；ESLint recommended type-checked、Hooks、Promise、型別 import、switch 分支覆蓋、已棄用 API（`no-deprecated`）；Prettier | 後端已提交、UI 旅程可用 |
| 靜態分層 | 既有 import／AST 邊界檢查 | 任意動態呼叫也安全，或所有責任切分合理 |
| 用例正確性 | 相應單元／整合／產品反例 | 程式易讀與無過度設計 |
| 審查 | 本頁責任、名稱、副作用、錯誤／恢復與抽象判準 | 不以個人喜好取代契約／實測 |

命令沿 [backend README](../../apps/api/README.md)與 [frontend README](../../apps/web/README.md)，規則的實際設定以 pyproject／eslint／tsconfig 為準，不在本頁手抄第二份 config。設定變更先跑反例確認能報錯，再驗既有程式，記入原任務 evidence；未覆蓋的項目如實列為審查責任。

格式交工具，不手排齊空白；不開啟所有 lint 規則，也不新增第二套 formatter。生成物只在來源／生成器修，不為 lint 手改它。例外用最窄的 suppression，列原因及 rule code；禁止全檔 `type: ignore`／大範圍停用 lint 掩蓋缺陷。`RUF100` 用於清理已不需要的 noqa，不保證所有人工理由合理。

依據：[Ruff rules](https://docs.astral.sh/ruff/rules/)、[RUF006](https://docs.astral.sh/ruff/rules/asyncio-dangling-task/)、[typed linting](https://typescript-eslint.io/getting-started/typed-linting/)、[no-floating-promises](https://typescript-eslint.io/rules/no-floating-promises/)、[switch exhaustiveness](https://typescript-eslint.io/rules/switch-exhaustiveness-check/)、[no-deprecated](https://typescript-eslint.io/rules/no-deprecated/)。這是目前工具鏈的有界增補，非要求換框架。

`no-deprecated` 用於 `apps/web`，補足 TypeScript 不會對 `@deprecated` 報錯的檢查。使用方式與其餘型別 lint 規則相同；驗證見[規範稽核](../history.md#source-a75c36d876a672e0f607)。

規則改動時，先有可重現的維護／錯誤案例及官方根據，再改本頁、設定與必要回歸。規範能演進，但不能只為讓某個 patch 過關而關掉檢查；也不因此重啟整個專案的架構討論。
