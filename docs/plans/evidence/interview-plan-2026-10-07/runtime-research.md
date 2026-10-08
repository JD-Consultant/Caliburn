# Windows Python 3.14 native crash：官方紀錄與隔離對照

2026-10-07。有限官方查閱未找到可直接對應本案 **GIL-enabled Windows CPython 3.14.7／一般 async generator／LangGraph checkpoint** 的已確認修正。存在窄條件的 asyncio、shutdown 與 serialization native crash 修正，但多數已包含於目前版本；不能只憑 `python314.dll`／`0xc0000005` 判定 CPython、uv 或 serializer 是根因。既有 official Python 3.14.0 與目前 runtime 的 ABI 標記一致，且已成功讀入相同 native packages，可先用無 provider 的合成 fixture 測「是否依賴目前 interpreter image」。這是診斷建議，不切換 production。

故障症狀僅由主代理提供；研究者未讀任何 paid cases、log、JD、arm 或 driver，未重現原故障。讀取範圍為 project Python requirements／lock、既有 interpreter metadata、安裝套件 metadata 與下列官方來源。本輪未安裝、下載、建立 venv、改 production／lock、讀取金鑰或呼叫 provider；最終 JD blind rubric 不變。

## 本機已核的可用範圍

`apps/api/pyproject.toml` 要求 `>=3.14,<3.15`、uv `0.12.20`；`uv python list --only-installed` 與 interpreter 的 `-I` metadata probe 確認：

| 項目 | API 目前 interpreter | 既有 official interpreter |
| --- | --- | --- |
| executable | `S:\caliburn\apps\api\.venv\Scripts\python.exe` | `D:\Python\Python314\python.exe` |
| base／版本 | `.research-tmp\python\cpython-3.14.7-windows-x86_64-none`；3.14.7 | 3.14.0，`tags/v3.14.0:ebf955d` |
| compiler／架構 | MSC v.1944、AMD64 | MSC v.1944、AMD64 |
| cache tag／SOABI | `cpython-314`／`cp314-win_amd64` | 相同 |
| extension suffix | `.cp314-win_amd64.pyd` | 相同 |
| Py_GIL_DISABLED／實際 GIL | `0`／enabled | `0`／enabled |
| stdlib venv | 目前已使用 venv | `find_spec('venv')` 成功 |

lock 與目前 `importlib.metadata` 逐項一致：OpenAI 3.20.0、LangGraph 1.2.12、langgraph-checkpoint **4.2.0**、checkpoint-postgres 3.1.2、ormsgpack **1.12.2**、Pydantic 2.13.5、pydantic-core 2.46.5、SQLAlchemy 2.1.1。沒有把 transitive serializer 版本從 top-level pyproject 猜出來。

已在獨立 official 3.14.0 process 使用 `-I -B -X faulthandler`，只將既有 API `Lib\site-packages` 加入該 process 的 `sys.path`；`ormsgpack`／`orjson`／`pydantic_core`／`greenlet` native imports 成功，含繁體中文、null、空字串、整數、bool 的固定合成 dict 在 ormsgpack 與 orjson 各一次 roundtrip 成功，exit 0。沒有 `.pth` 處理、套件更新或 App／paid driver import。這只驗初步 ABI／import／小型 roundtrip 可行性，不證明完整 runner、併發負載或原 crash 已修。

CPython 官方保證同 minor release 的 ABI 在相同編譯條件下前後相容；同頁也明說 compiler／lower-level libraries／options 是平台條件，私有 `_Py` API 可在 patch 改變。因此上述相同 tag 與正例支援隔離試驗，不能提升為所有 native extensions 的完整穩定性保證。[C API Stability](https://docs.python.org/3.14/c-api/stable.html)

## 官方已知修正與本案可用程度

| 第一方紀錄 | 精確條件／版本 | 對目前症狀的界線 |
| --- | --- | --- |
| [ormsgpack 1.11.0](https://github.com/ormsgpack/ormsgpack/releases/tag/1.11.0)、[1.12.2](https://github.com/ormsgpack/ormsgpack/releases/tag/1.12.2) | 1.11.0 於 2025-10-08 增 3.14／free-threading 支援；1.12.2 於 2026-01-18 修 Windows 3.14 **free-threaded** `unpackb` crash，並修 Linux s390x crash。 | 本機已是 1.12.2 且非 free-threaded；不能把這筆 release fix 套成本案尚未修的同一故障。也不代表沒有別的 serializer defect。 |
| [CPython #137384 的已發布 NEWS](https://raw.githubusercontent.com/python/cpython/v3.14.7/Misc/NEWS.d/3.14.0rc3.rst)、[3.14 backport #138065](https://github.com/python/cpython/pull/138065) | shutdown finalizer 使用 warnings 時的 crash；3.14.0rc3（2025-09-18）已含，backport 於 2025-08-22 合併。 | 是真 Windows shutdown 線索，但目前 3.14.7 早已包含；不是 3.14.8 才提供的通用 finalization fix。 |
| [CPython #142556](https://github.com/python/cpython/issues/142556)、[3.14.3 NEWS](https://raw.githubusercontent.com/python/cpython/v3.14.7/Misc/NEWS.d/3.14.3.rst) | Task finalization 的 exception handler 又 re-register 同 task 可造成 use-after-free；3.14.3（2026-02-03）已修。 | 條件具體，目前 3.14.7 已含；沒有本案發生這種 re-registration 的證據。 |
| 同份 [3.14.3 NEWS](https://raw.githubusercontent.com/python/cpython/v3.14.7/Misc/NEWS.d/3.14.3.rst) 的 #143638／#143196 | C Pickler／Unpickler reentrant calls 可 crash／毀損；未公開 `json.encoder.c_make_encoder` 以非零 indent 呼叫可 crash。 | 是 serialization native fixes，但已在 3.14.3；不能等同一般 ormsgpack checkpoint crash，沒有本案走這些入口的證據。 |
| [3.14.6 NEWS](https://raw.githubusercontent.com/python/cpython/v3.14.8/Misc/NEWS.d/3.14.6.rst) 的 #142831／#146452 | 3.14.6（2026-06-10）修 JSON encoding 時物件被修改的 use-after-free，以及 **free-threaded** pickle dictionary 被另一執行緒修改的 segfault。 | 兩者亦早於 3.14.7；後者的 build 前提與本機不同，前者需實際 mutation 證據，不能因看到 serialization 一詞就套用。 |
| [Python 3.14.8 release](https://www.python.org/downloads/release/python-3148/)、[3.14.8 NEWS](https://raw.githubusercontent.com/python/cpython/v3.14.8/Misc/NEWS.d/3.14.8.rst)、[CPython #154871](https://github.com/python/cpython/issues/154871) | 3.14.8 於 2026-09-30 expedited release。具體 asyncio crash fix 是 `Task.get_context()` 用於未初始化 Task，例如直接 `__new__()` 或 subclass 不呼 `super().__init__()`。 | 新 patch 確有此 fix；不能宣稱修一般 async generator／所有 Windows 0xc0000005。這輪沒有下載或試跑 3.14.8。 |
| [LangGraph 1.2.12 release](https://github.com/langchain-ai/langgraph/releases/tag/1.2.12)、[checkpoint 4.2.0 release](https://github.com/langchain-ai/langgraph/releases/tag/checkpoint%3D%3D4.2.0) | 分別於 2026-09-21、2026-08-07 發布；已讀各版 changes 與定向官方 issue 搜尋。 | 這些 release entries 未列 Windows 3.14 native access violation 修正。有限查閱未找到吻合本症狀的已確認新 fix；這不是證明整個 issue tracker 不存在相關問題，也不能以套件接受 3.14 安裝作全平台保證。 |

搜尋中出現 [CPython #158312](https://github.com/python/cpython/issues/158312) 的 2026-09-28 crash 報告：Arch Linux／system 3.14.7、dict insertion，當時 open／pending，無已確認修正。它不是 Windows／uv／async generator 的已核問題，故不據其 body 分析推論本案根因。

uv 官方說明 managed CPython 來自 python-build-standalone；可用版本表隨 uv release 固定，安裝選擇與 runtime bugfix 不是同一契約。官方也支援 interpreter 完整路徑、關閉 Python downloads 及 offline；僅寫 `3.14` 不能保證選中欲測的 publisher／patch／GIL variant。[uv Python versions](https://docs.astral.sh/uv/concepts/python-versions/)

python-build-standalone 的 [20260805](https://github.com/astral-sh/python-build-standalone/releases/tag/20260805) 及 [uv 0.12.2](https://github.com/astral-sh/uv/releases/tag/0.12.2) 同日納入 CPython 3.14.7；這是 runtime 版本更新。[PBS 20260924](https://github.com/astral-sh/python-build-standalone/releases/tag/20260924) 列 Windows debug distributions／建置與 Tcl/Tk 改動，沒有本次所查 crash 修正；查詢時 [PBS 20261003](https://github.com/astral-sh/python-build-standalone/releases/tag/20261003) notes 為 `TBD`，[uv 0.12.23](https://github.com/astral-sh/uv/releases/tag/0.12.23) 亦未列吻合此症狀的 fix。發布物存在或 uv 升版，皆不能替代 exact crash 的修正證據。

## 建議先測的一個假設

**H：在 package bytes、合成輸入、seed／排程及 serializer 選項固定時，native fault 是否依賴目前 interpreter image。** 先用完全不讀 paid data、不呼 provider 的小型 async checkpoint fixture：固定幾種 native JSON 值及一個合法 Pydantic snapshot，反覆序列化／反序列化，在固定迭代點取消並關閉 async generator，完整結束 loop。兩個獨立子程序只換 interpreter executable，其餘 fixture／套件 bytes／迭代預算相同，啟用 `-X faulthandler`，保存退出碼與合成階段位置。

提前離開 async generator 時沿官方生命週期契約明確 `aclose()`，使 finally／cleanup 在可控 context 執行；不要用未受控關閉製造混合變因。這是正確試驗條件，未顯式 close 並不構成理應 native crash 的證據。[async generator 文件](https://docs.python.org/3.14/reference/expressions.html#asynchronous-generator-functions)

目前已核可用的路徑是 standalone 3.14.7 與 official 3.14.0。這次對照的單一實驗因子是 **interpreter image**，包含 patch 與發行建置差異；若有差異，不能單獨歸因某個 patch 或 standalone 的某個編譯選項。3.14.0 是既有診斷 baseline，沒有被建議為正式降版目標。若兩側均不 crash，只能說 fixture 尚未重現；兩側都 crash 也不能單憑此排除 interpreter 問題。

如後續建立真正隔離目錄，可沿 stdlib `venv` 對新且不存在的測試目錄執行 `D:\Python\Python314\python.exe -I -m venv --without-pip <new-test-venv>`，不 seed／下載；或沿已鎖 uv 的 `venv --python <exact-path> --no-project --no-python-downloads --offline <new-test-venv>`。本輪只核命令能力與官方契約，未執行建立。不要搬移原 venv 或改它的 `pyvenv.cfg`；fixture 可像本輪 probe 一樣只在子程序明確加入固定現有 package path，再核實際 `__file__` 與 metadata。完全獨立依賴目錄需另行複製／安裝 package bytes，未在這輪做成完整環境。[venv 契約](https://docs.python.org/3.14/library/venv.html)

`-X faulthandler` 在 Windows 可裝 exception handler，但 C stack dump 仍取決於 OS／build 支援。取得 Python traceback 不等於取得 native root cause；若合成反例可重現，下一步才由有權讀原 failure 的主代理對照 native dump／符號，不由 blind reviewer 讀 paid artifacts。[faulthandler](https://docs.python.org/3.14/library/faulthandler.html)

## 續輪：SDK stream public cleanup 與 terminal handoff

同日依主代理要求，只讀 installed OpenAI 3.20.0／HTTPx2 2.13.1 的精確原碼，以及 App adapter／現有 zero-key unit；沒有讀 experiment driver、paid provider 輸出或案例資料。結論：**public connection close 不等於全部 nested lazy async generators 終結**。目前證據不要求 production／locked deps 改動，也不支持 SDK private patch。

| 已核原碼位置 | 實際契約與界線 |
| --- | --- |
| `openai/_streaming.py` L139–255 | `AsyncStream` 建立自己的 `__stream__()` iterator；public `__aiter__()` 再建立外層 async generator。`close()`／`aclose()`／context manager exit 都只關 `response.aclose()`；沒有逐層關閉這些 iterator。`__stream__` 的 finally 亦只關 response。 |
| 同檔 L371–383 | SSE decoder 的 `aiter_bytes()` finally reset decoder，沒有承諾關閉它收到的底層 async iterator。 |
| `httpx2/_models.py` L979–1075；`_client.py` L162–174 | `aiter_bytes()` 明確 `aclosing(aiter_raw())`；`aiter_raw()` 的 finally 才關它持有的 transport iterator 及 response；BoundAsyncStream iterator 的 finally 也關持有 iterator。**`Response.aclose()` 本身只關 ByteStream，不主動走上述 iterator 的 finally。** |
| `openai/lib/streaming/responses/_responses.py` L135–234 | public helper／manager 的 close 同樣關 response。`get_final_response()`／`until_done()` 則明確等 stream 完整消費；不是本案「收到原 terminal 就不等尾段」的替換方案。 |
| `adapters/response_streaming.py` L104–153 | completed／failed／incomplete 都先同步保留 `event.response`，再 break，後面才 await public `stream.close()`。取消或清理錯誤帶原 terminal typed handoff，無 terminal 才保留原取消／傳輸錯誤，public delta 不製造 terminal。 |

上述 SDK／HTTPx2 原碼來自 `apps/api/.venv/Lib/site-packages` 的有效 locked versions；App 檔案為 `apps/api/src/caliburn/adapters/response_streaming.py`。官方 [OpenAI streaming guide](https://developers.openai.com/api/docs/guides/streaming-responses) 說明 SSE／terminal events，沒有宣稱 Python public close 可遞迴終結所有 lazy generators。[Python `aclosing`](https://docs.python.org/3.14/library/contextlib.html#contextlib.aclosing) 的保證是對交入的 `thing` 呼叫 `aclose()`，使**該 generator** 的 exit code 在相同 context 執行；不能擴張為 SDK 所有巢狀物件的 closure 保證。

HTTPx2 官方 [2.13.0 changelog](https://github.com/pydantic/httpx2/blob/main/src/httpx2/CHANGELOG.md) 與 [PR #1204](https://github.com/pydantic/httpx2/pull/1204) 的 2026-09-14 fix，處理提早放棄 response 時 `safe_async_iterate` 的額外 asynccontextmanager generator 導致 `RuntimeError: generator didn't stop after athrow()`；改用 `aclosing`／`nullcontext`。本機 2.13.1 已包含，不能將這項 Python cleanup exception fix 直接說成今回 native access violation 根因或等待升級的修復。

### Public-only closure 反例：exit 0，非 native Red

以目前 API interpreter 執行下列程式（PowerShell here-string 經 stdin 傳給 `apps/api/.venv/Scripts/python.exe -I -B -X faulthandler -`）。只有真 SDK `AsyncStream`、自製合成 HTTPx2 Wire；無 request 外送、無 checkpoint、無 SDK private 欄位／方法呼叫。Wire 的 public iterator 在 finally 標記終結，public transport close 則獨立標記 connection closure：

```python
import asyncio
import json
import httpx2
from openai import AsyncOpenAI, AsyncStream

class Wire(httpx2.AsyncByteStream):
    def __init__(self):
        self.connection_closed = False
        self.iterator_finalized = False
    async def __aiter__(self):
        try:
            yield b'data: {"type":"response.completed","synthetic":true}\n\n'
            raise AssertionError('Tail must not be read')
        finally:
            self.iterator_finalized = True
    async def aclose(self):
        self.connection_closed = True

async def main():
    wire = Wire()
    client = AsyncOpenAI(api_key='synthetic-only')
    response = httpx2.Response(200, request=httpx2.Request('POST', 'https://example.invalid'), stream=wire)
    stream = AsyncStream(cast_to=dict, response=response, client=client)
    outer = stream.__aiter__()
    item = await anext(outer)
    assert item['type'] == 'response.completed'
    await stream.close()
    print(json.dumps({'phase':'public-stream-close', 'connection_closed':wire.connection_closed,
                      'transport_iterator_finalized':wire.iterator_finalized}))
    await outer.aclose()
    print(json.dumps({'phase':'outer-iterator-close', 'connection_closed':wire.connection_closed,
                      'transport_iterator_finalized':wire.iterator_finalized}))
    await client.close()

asyncio.run(main())
```

實際 stdout：兩個 phase 都是 `connection_closed: true`、`transport_iterator_finalized: false`，exit **0**。它是「不能從 public close／outer close 推論 nested closure」的反例，不是 native crash 的重現、修復測試或 root-cause 證據；程式沒有斷言所有 SDK generators 都應由 App 關閉。

### 既有 meaningful units 與有界建議

實際命令：`uv run --project apps/api --locked pytest apps/api/tests/unit/test_response_streaming.py -k 'terminal_does_not_wait or terminal_cleanup_failure or task_cancel_during_terminal_cleanup or cancel_before_terminal' -q` → **6 passed, 14 deselected in 1.20s**。這六例核 terminal 後 broken tail 不讀／不重送、close 失敗或取消仍帶逐字原 R、terminal 前取消不被 close error 替換，以及真 task cancellation 在 close await 中仍交回原件。它們沒有宣稱完整 native safety。

有界方向是保留正式 adapter 的 terminal-first／不等 EOF 及 public connection close。新的 experiment observer 不應再改寫 SDK stream 的 iteration ownership；觀察可放到 request／transport 原有公開邊界。若仍有自有 generator，它的 owner 必須明確關自己持有的 iterator，單看 delegated wire.closed 不足；這不授權對 SDK `_iterator` 或 decoder 私有物件下手。

值得保留的 unit 反例是：observer 失敗不丟 terminal／不重送；terminal 後尾段阻塞或拋錯仍立即停讀；自有 iterator 的 finally 在 owner 退出前執行（只核 owner 自己的物件）。native 反例則仍需在**同一個含 SDK＋checkpoint＋GC 的獨立子程序**重播，核退出碼／stderr 與固定迭代預算，不能用個別 SDK 或 serializer Green 替代。主代理回報移除額外 observer 後該 combined control **2000 次／76.21s Green**，相同來源與雙次 bounded replay 正由 owner 核對；研究者未讀 driver 或原件，也未獨立重跑，故只記為主代理回報，沒有替其 native cause／修正範圍背書。
