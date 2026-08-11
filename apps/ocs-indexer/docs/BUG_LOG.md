# Bug Log

> 開發過程中遇到的所有 bug 與其診斷、修復、預防方式。每筆採用統一格式以便專題報告引用。
>
> 本文件不 commit，僅供專題報告與內部技術紀錄參考。

格式：

```
## Bug N: <一行標題>
- 時間 / 觸發場景
- 症狀
- 診斷過程
- 根因
- 修法
- 預防 / 啟示
- 影響使用者體驗
```

---

## Bug 1: chunk_key 碰撞導致 48 個 block 變成 36 個（沉默資料遺失）

### 時間 / 觸發場景
首次對 3 份 fixture 跑完 `index` 並 stats 比對時。

### 症狀
- `index` report 顯示「chunks: 66」（聲稱成功寫 66 筆）
- 立刻跑 `stats --collection ocs_bgem3_v1` 顯示 `total_points = 54`，`level_block = 36`
- 預期 block 數 = source 端 `stats tests/fixtures` 的 `blocks: 48`
- 缺 12 筆 block。沒有任何錯誤訊息。

### 診斷過程

1. 先確認 source 端 `stats` 顯示 blocks = 48，所以 builder 應該產 48 個 block chunk
2. 確認 `index` report 顯示 chunks = 66 = 3 profile + 15 unit + 48 block，數字本身對
3. Qdrant collection 卻只有 36 個 level=block — 中間有 12 個被覆寫了
4. Qdrant point id 是 `uuid5(NAMESPACE, chunk_key)`，相同 chunk_key 會產生相同 id，upsert 等於覆寫
5. 推測：兩個不同 block 算出相同 chunk_key
6. 看 builder.py 的 chunk_key 組合方式：

```python
block_chunk_key = _block_key(
    norm.ocs_code,
    unit.unit_key,
    group.primary_task_key,
    block.block_id or f"{block.block_order:04d}",
)
```
其中 `block.block_id` 來自 normalizer 的合成：

```python
if ind_codes:
    head = ind_codes[0]
    parts = head.split(".")
    if len(parts) >= 2:
        block_id = ".".join(parts[:-1])
```

7. 看 SMS2512-002v1 的 T4.1 task — 有 2 個 competency_block：
   - 第 1 個 block 的 indicators 起頭是 P4.1.1 → block_id = "P4.1"
   - 第 2 個 block 的 indicators 起頭是 P4.1.2 → block_id = "P4.1"
8. **兩個 block 的 chunk_key 完全一樣，第 2 個覆寫第 1 個**
9. 整個 fixture 含 12 個這種多 block / 同 task 場景 → 12 個 collision

### 根因

block_id 合成規則「indicator code 去掉最後一段」假設「同 task 內每個 block 的 indicator prefix 不同」。實際上 OCS JSON 裡同一個 task 可能有多個 block，每個 block 又有多個 indicator，indicator 第二段（P4.1.X 的 X）才是 block 內的編號，不是 block 間的識別。

合成 block_id 從根本就不是穩定 key — block 在 OCS 沒有原生名稱，硬要造一個就會碰撞。

### 修法

```python
# 原本
block_chunk_key = _block_key(
    norm.ocs_code,
    unit.unit_key,
    group.primary_task_key,
    block.block_id or f"{block.block_order:04d}",
)

# 改成
block_chunk_key = _block_key(
    norm.ocs_code,
    unit.unit_key,
    group.primary_task_key,
    f"{block.block_order:04d}",
)
```

直接用 `block_order`（task 內 1-based 序號）當 key 的最後一段。`block_order` 保證 task 內 unique。

修完 rebuild 後 stats 顯示 total=66 block=48 ✓

### 預防 / 啟示

1. **不要造合成 id 當 key**：OCS 沒給 block 名稱，硬造會撞。改用 source-stable 的 enumeration 序號
2. **資料遺失要有 invariant check**：upsert 後 stats 應該 = source stats，不一致就要查
3. **靜默覆寫是 Qdrant 預期行為**（同 id upsert = update）但對 indexer 來說是 bug 信號

V2 直接把合成的 `block_id` / `block_title` 都移除（schema v2 P0-5），徹底解決。

### 影響使用者體驗

如果未修，最終 JD 引用時會少 25% block 的 K/S 證據（12/48 不見），使用者描述命中失敗率提高，候選 OCS 排序不準。是高優先級 bug。

---

## Bug 2: K/S parallel array 過濾條件不一致導致靜默 misalignment

### 時間 / 觸發場景
寫 v2 schema 提案時審視 normalizer 程式碼發現（**尚未被實際資料觸發過，是潛在 bug**）。

### 症狀
- 沒有 runtime error
- 看 payload 表面正常（k_codes 跟 knowledge_terms 都有內容）
- 但配對錯位：k_codes[0] 可能對應 knowledge_terms[1]，不是 knowledge_terms[0]
- LLM curator 拿這個 payload 寫 JD 會把代碼掛到錯的名稱上

### 診斷過程

審視 normalizer.py 的 block 抽取段：

```python
k_codes = [k.code for k in b.knowledge if k.code]
s_codes = [s.code for s in b.skills if s.code]
k_terms = [k.name.strip() for k in b.knowledge if k.name]
s_terms = [s.name.strip() for s in b.skills if s.name]
```

注意 `k_codes` 用 `if k.code` 過濾，但 `k_terms` 用 `if k.name` 過濾 — 條件不同。

如果 source JSON 裡某筆 knowledge 有 `code = "K05"` 但 `name = None`（或 `name = ""`），會發生：
- k_codes 包含 K05（因為 code 存在）
- k_terms 不包含 K05 對應的 name（因為 name 不存在）
- 兩個 list 長度不同 → consumer 端拿 `dict(zip(k_codes, k_terms))` 配對時，K05 對到的會是下一個 K 的 name

### 根因

「平行陣列」設計把 code 和 name 拆成兩個 list，依賴 index 對齊。任何兩個 list 的處理路徑不一致（包括但不限於：過濾條件、排序、去重），都會破壞對齊。

### 修法（v2）

從 schema 層直接改用 pair structure：

```python
k_pairs = [
    Pair(code=k.code, name=k.name.strip())
    for k in b.knowledge
    if k.code and k.name and k.name.strip()
]
```

過濾條件**只有一個**（code AND name 都存在），保留下來的每一筆 pair 必有 code 與 name。

舊的 `k_codes` / `s_codes` 仍保留（給 Qdrant payload index filter 用），但**從同樣的 pairs 反推**：

```python
k_codes = [p.code for p in k_pairs]  # 保證跟 pairs 對齊
```

實際 v2 實作中，我們會：
1. 先建 pairs
2. 從 pairs 反推 codes（不是直接從來源獨立過濾）

這樣 invariant `len(k_codes) == len(k_pairs)` 永遠成立。

### 預防 / 啟示

1. **平行陣列是反模式**：只要兩個 list 「概念上對齊」，就把它們捆成 pair / object list
2. **過濾條件不一致是常見錯位來源**：list comp 看起來乾淨，但 `if k.code` vs `if k.name` 就是 bug
3. **Schema 設計時 invariant 要寫出來**：「k_codes[i] 對應 k_terms[i]」如果沒人保證，就會 drift

我們的程式碼可能從未實際觸發這個 bug（fixture 三份都完整），但在 908 份全量資料裡某些舊版 OCS 可能 name 是 null，這時 bug 就會發生。**屬於潛在的 silent corruption**。

### 影響使用者體驗

LLM 在最終 JD 引用「（依 SMS2512-002v1 K05 - 機器學習概論）」，但實際上 K05 在 OCS 裡叫「資料庫原理」，K06 才是機器學習概論。使用者收到的 JD 會有錯誤代碼-名稱對應。

最糟的是：使用者沒辦法察覺，因為敘述本身合理（機器學習概論看起來像 K05 沒有違和）。是 high-stakes silent bug。

---

## Bug 3: qdrant-client URL 沒帶 port 自動填 6333 → 反向代理 timeout

### 時間 / 觸發場景
首次嘗試連 `https://qdrant.yokosama.com` 雲端 Qdrant 時。

### 症狀
- `curl https://qdrant.yokosama.com/` → HTTP 200，正常
- `curl -H "api-key: xxx" https://qdrant.yokosama.com/collections` → 200 + collection list
- httpx 直接打 → 200 OK
- 但 `QdrantClient(url="https://qdrant.yokosama.com", api_key="xxx").get_collections()` → `WinError 10060` 連線 timeout

### 診斷過程

1. 確認 DNS 沒問題（`curl` 通）
2. 確認 SSL 沒問題（HTTPS 通）
3. 確認 auth 沒問題（用 api-key header 通）
4. **可疑點**：為什麼 qdrant-client 過不去但 raw httpx 過得去？

兩者都用 httpx，差別在 qdrant-client 在 URL 沒帶 port 時會：

```python
# qdrant-client source
port = parsed_url.port or 6333  # default if no port
```

5. 用 httpx 試 `https://qdrant.yokosama.com:6333` → timeout
6. 用 httpx 試 `https://qdrant.yokosama.com:443` → 200
7. **結論**：反向代理（openresty）只開 443，沒開 Qdrant 預設的 6333 port。qdrant-client 把 URL 補上 6333 後就連不到。

### 根因

qdrant-client 預設 port 邏輯假設「直連 Qdrant container」（裸服務），不適用「反向代理只暴露 443/80」的常見部署。`URL=https://host` 對 HTTPS 約定俗成是 port 443，但 qdrant-client 用 6333 default 蓋過去。

### 修法

寫一個 URL parser factory（`store/qdrant_client.py:make_client`）：

```python
def make_client(*, url: str, api_key: str | None, timeout: float = 60.0) -> QdrantClient:
    parsed = urlparse(url)
    scheme = (parsed.scheme or "http").lower()
    https = scheme == "https"
    host = parsed.hostname or url
    port = parsed.port or (443 if https else 6333)
    prefix = parsed.path.rstrip("/") or None

    return QdrantClient(
        host=host, port=port, https=https, prefix=prefix,
        api_key=api_key, timeout=timeout, prefer_grpc=False,
    )
```

`.env` 仍然只填 `QDRANT_URL=https://qdrant.yokosama.com`（不需要明寫 port），factory 內部自動 resolve。

### 預防 / 啟示

1. **客戶端 SDK 的 default 不一定符合反向代理場景**：QdrantClient、Elasticsearch SDK、Redis 都有類似問題
2. **不要把實作細節（port）洩漏到 .env**：用 factory 抽象，operator 只填 URL
3. **HTTPS URL 沒帶 port 該推斷 443**：這是 HTTP 約定，覆蓋成 6333 是反直覺

### 影響使用者體驗

新人 onboard 跑 indexer 時，雲端 Qdrant 連不上。錯誤訊息是 timeout（沒指明原因）。沒有 factory 抽象的話，使用者要去翻 qdrant-client 源碼或 stack overflow 才會懂。

---

## Bug 4: openresty `client_max_body_size` 過小擋住 BGE-M3 dense vector upsert

### 時間 / 觸發場景
v1 indexer 跑 `index tests/fixtures` 進入 upsert 階段時。

### 症狀
- BGE-M3 embed 跑完沒問題（66 chunks 全部 embedding 成功）
- 進入 Qdrant upsert 階段立刻 500
- 錯誤訊息是 HTML：
  ```html
  <html><head><title>500 Internal Server Error</title></head>
  <body><center><h1>500 Internal Server Error</h1></center>
  <hr><center>openresty</center></body></html>
  ```
- 注意是 `openresty` 而非 Qdrant 自己的 JSON error → 反向代理擋住的

### 診斷過程

採用 bisection 二分法：
1. 試 `batch_size=1` 還是 fail → 不是 batch 太大，是單個 point 就過不去
2. 試 dense-only + tiny payload → fail
3. 試 dense=[0]*1024 + 1.0 spike + tiny payload → **PASS**（純零陣列 JSON 序列化很小）
4. 試 dense=real BGE-M3 vector（1024 個 real float）+ tiny payload → fail
5. 試「前 4 個 real value + 後 1020 個 0」 → **PASS**
6. 試逐步增加 real value 個數：
   - n=16 (5.5KB body) → 200
   - n=64 (6.3KB) → 200
   - n=256 (9.7KB) → 200
   - n=512 (14KB) → **500**
   - n=800 (19KB) → 500
   - n=1024 (22.9KB) → 500
7. 推論：反向代理在 ~10-13KB body 處攔截
8. 試 gzip Content-Encoding → 單點 PASS，batch 又 fail（gzip 對 random float 壓縮率只有 50%）

### 根因

openresty / nginx 的 `client_max_body_size` 預設只有 1MB，**但在這個部署上被設成 1KB 或非常小的值**（具體原因要查 NPM template）。BGE-M3 dense 1024-dim float JSON 序列化就 22KB，遠超該限制。

Qdrant 本身沒問題（直連測試通），是反向代理擋下來的。

### 修法

提供 3 個選項：
1. ✅ **採用**：使用者去改 openresty 設定
2. 我端做 gzip + batch=1 workaround（被使用者否決，速度太慢）
3. 改用本機 Docker Qdrant（沒採用，使用者要用雲端）

選項 1 的具體步驟（在這個專案是 PVE LXC + Nginx Proxy Manager (NPM)）：

a) NPM UI Advanced 分頁設 `client_max_body_size 100m;` → **Internal Error**
   - NPM 後端跑 `nginx -t` 驗證失敗（NPM bug，但症狀不明）
b) 改 NPM container 內部直接編 `/data/nginx/custom/server_proxy.conf`：
   ```nginx
   client_max_body_size 100m;
   ```
   檔案是 NPM 預先 include 的 hook，所有 proxy host 共用，且 UI 重存 host 不會被覆蓋
c) `nginx -t` → 報 `/tmp/nginx/body` 目錄不存在（LXC 重啟後 /tmp 被清空的副作用）
d) `mkdir -p /tmp/nginx/{body,proxy,fastcgi,uwsgi,scgi}` 補建
e) `nginx -t` PASS → `nginx -s reload`
f) 重跑 indexer 全部通過

### 預防 / 啟示

1. **embedding 後 upsert 是 indexer 的「最後一公里」**：embedding 跑很久，upsert 失敗的代價是重來。bisection 時要先確認模型快取在，避免每次都重抓 2.3GB
2. **反向代理是隱形的中間層**：應用程式錯誤訊息看起來像 Qdrant 問題，實際是 nginx 攔截
3. **HTML response 是訊號**：當 SDK 預期吃 JSON 卻吃到 HTML，幾乎一定是反向代理（nginx / cloudflare / apache）
4. **生產級檢查清單**：deploy 反向代理時要確認上游應用的 max body size 需求
5. **NPM 的 UI 不可靠**：複雜 nginx 設定建議直接編 config file，不用 UI

### 影響使用者體驗

沒修就完全寫不進 Qdrant。整個 indexer 等於壞掉。是 hard block。

修完後 indexer 正常工作。使用者後續做查詢 / 客製化 JD 都不受影響。

---

## Bug 5: pre-commit hook 把中文 fixture 檔名變 \\x 編碼，git 顯示亂

### 時間 / 觸發場景
首次 `git add tests/fixtures/*.json` 並 `git commit` 時。

### 症狀
git status 顯示：
```
new file:   "tests/fixtures/3D\345\210\227\345\215\260..."
new file:   "tests/fixtures/AIoT\346\207\211\347\224\250..."
```

不是 `3D列印積層製造工程師-職能基準.json` 這樣的可讀檔名。

### 診斷過程

這不算 bug 而是 git 預設行為：對 non-ASCII 檔名做 octal escape。實際檔案沒問題（filesystem 正常），只是 git output 不可讀。

### 修法（如果想看到中文檔名）

```bash
git config --global core.quotepath false
```

但本專案目前沒設，因為：
- 檔案本身存放與 commit 都正常
- 只是 git status / git log --stat 顯示時看起來醜
- 不影響任何功能

### 預防 / 啟示

1. **不是所有 git 「亂碼」都需要修**：通常只是 quotepath 設定
2. **CI / CD 系統可能依賴 octal escape**：改 quotepath 前確認下游工具相容
3. **跨平台 repo 建議 ASCII 檔名**：減少這類困擾。但 OCS fixture 用原文名最符合直覺

### 影響使用者體驗

無實質影響，純美觀問題。本專案不修。

---

## Bug 6: HF_TOKEN 未設造成下載慢 + Qdrant client/server 版本警告

### 時間 / 觸發場景
首次跑 `index` 時 BGE-M3 模型下載與 Qdrant 連線都會警告。

### 症狀
- `Warning: You are sending unauthenticated requests to the HF Hub. Please set a HF_TOKEN to enable higher rate limits and faster downloads.`
- `Qdrant client version 1.18.0 is incompatible with server version 1.16.2. Major versions should match and minor version difference must not exceed 1.`

### 診斷過程

兩個都是 warning 不是 error，indexer 正常跑完。

- **HF_TOKEN**：HuggingFace 對匿名下載有 rate limit（每小時幾百次 file fetch）。BGE-M3 拆成 30 個 file，每個 file 一次 fetch，遇到 rate limit 會降速。對個人開發者不會 trigger，但對 CI 可能擋住。
- **Qdrant 版本警告**：1.18 client 與 1.16.2 server 差 2 個 minor，超過官方建議的 ±1 範圍。實測 API 行為一致沒 break。

### 修法

兩個都不一定要修。如果要：
- HF_TOKEN：HuggingFace 設定 access token，`.env` 加 `HF_TOKEN=hf_xxx`
- Qdrant 版本：降 client 到 1.17 或升 server 到 1.17+

### 預防 / 啟示

1. **HuggingFace anonymous rate limit 是 CI 常見痛點**：production 一定要設 token
2. **Qdrant minor version drift 通常無傷**：除非用到新 minor 才有的 API（v2 fusion 那種）
3. **Warning 不一定要修**：要評估實際風險

### 影響使用者體驗

第一次跑 index 時有警告訊息可能讓使用者擔心。但實際 indexer 跑完正常。屬於低關鍵性 noise。

---

## 統計

| Bug | 嚴重度 | 是否阻塞功能 | 修法成本 | 處理優先順序 |
|---|---|---|---|---|
| 1 chunk_key 碰撞 | 高 | 是（資料遺失） | 1 行 | 立即修 |
| 2 parallel array misalignment | 高 | 否（潛在） | 中（schema 改） | v2 統一修 |
| 3 qdrant URL 預設 port | 中 | 是（連不上） | 中（factory） | 立即修 |
| 4 openresty body size | 高 | 是（無法 upsert） | 環境設定 | 立即修 |
| 5 git 檔名 escape | 低 | 否 | 1 行設定 | 不修 |
| 6 HF / Qdrant warning | 低 | 否 | 環境設定 | 不修 |
| 7 v2 payload ReadTimeout | 中 | 是（全量無法寫入） | retry + timeout | 立即修 |
| 8 來源資料 ocs_code 重複 | 低 | 否（4 筆覆寫） | 不修（上游問題） | 文件化 |

修了 5 個阻塞 bug，留 2 個 noise + 1 個來源資料問題。整體成本（含學習 / 診斷 / 編程）約 8 工時。

---

## Bug 7: v2 payload 撐爆 60 秒 Qdrant client timeout（全量無法寫入）

### 時間 / 觸發場景
全量 908 份 rebuild 啟動後，每個 64-point batch 的 upsert 都 timeout，0 點寫入。

### 症狀
```
ResponseHandlingException: The read operation timed out
```
- 全量 rebuild 立刻失敗
- Collection 0 points、manifest 空（manifest 機制保證未成功的 batch 不會被標記為已 indexed）

### 診斷過程

1. 對比 v1：v1 全量也是 64-batch，沒這問題
2. v2 payload 變化：
   - 每個 block 新增 `k_pairs` / `s_pairs` / `output_pairs` / `evidence` (~3-5KB)
   - 每個 profile 新增 `all_k_pairs` / `all_s_pairs` / `all_a_pairs` / `all_output_pairs` 池 (~10KB)
   - profile markdown 技能雲 (~1KB 文字 + sparse weights 翻倍)
3. 估算單 chunk JSON size：v1 ~20KB → v2 ~30-35KB
4. 單 batch (64 chunks) ~ 2MB body，跨 openresty + cloudflare 上行
5. Qdrant 端 `wait=True` 要 sparse vector 算完才回應；批量大導致 indexing 時間 >60s
6. qdrant-client 預設 timeout 60s → read timeout

### 根因
- v2 schema 變更後單請求工作量 + 上行時間翻倍，原本剛好穩在 60s 內的 batch 現在常超過
- timeout 設計成「常數」沒考慮 schema 演化

### 修法

`config.py` 加 `qdrant_timeout` 欄位（env: `QDRANT_TIMEOUT`，預設 300s）：

```python
qdrant_timeout=_env_float("QDRANT_TIMEOUT", 300.0),
```

`make_client(timeout=...)` 把這個值傳進 qdrant-client；CLI 所有 `make_client(...)` 呼叫一律帶上 `timeout=settings.qdrant_timeout`。

降 `INDEX_BATCH_SIZE` 從 64 → 32（單請求工作量減半，retry 成本也減半）。

`QdrantWriter._flush` 加 retry：

```python
_RETRYABLE_STATUSES = {408, 425, 429, 500, 502, 503, 504}

def _flush(self, batch):
    for attempt in range(self.max_retries + 1):
        try:
            self.client.upsert(...)
            return
        except Exception as exc:
            if attempt >= self.max_retries or not _is_retryable(exc):
                raise
            time.sleep(self.retry_base_delay * (2 ** attempt))
```

`ResponseHandlingException`（包含 ReadTimeout）和 `UnexpectedResponse` 4xx/5xx transient 都 retry，指數 backoff 2s/4s/8s/16s。CLI report 加 `upsert_retries` 欄位讓 operator 看 proxy 健康。

### 預防 / 啟示
- **timeout 必須是 env 可調，不能寫死**：production 部署的網路 latency 跟 dev 不同
- **schema 變更要算 payload size 增長率**：v1 → v2 增 ~50% 沒被前期注意到
- **批量處理一定要有 retry**：跨多層 proxy 的鏈路單次成功率不可能 100%
- **manifest only-after-success 是正確設計**：失敗後 0 points 0 entries，沒髒狀態，下次重跑乾淨

### 影響使用者體驗
全量 rebuild 5.4 小時跑完，0 retry / 0 failed — 對 v2 payload 大小 + yokosama 反向代理鏈路是穩的。如果未來 payload 更大或網路更差，retry 機制會自動吸收 transient 失敗。

---

## Bug 8: 來源資料 4 個 ocs_code 重複導致 8 個檔案覆寫到 4 個

### 時間 / 觸發場景
v2 全量 rebuild 完成後 stats 顯示 `total_points=12810` 而非預估 12869，少 59 點。

### 症狀
- index report: `indexed_files: 908, chunks: 12869`
- `stats --collection ocs_bgem3_v2`: `profile=904, unit=3260, block=8646, total=12810`
- 缺 4 profile + 12 unit + 43 block = 59 chunks

### 診斷過程

1. profile 缺 4 個，但 indexer 是「一個 file 一個 profile chunk」，所以猜「有 4 個 file 的 ocs_code 跟其他 file 撞」
2. 跑 source-side ocs_code 統計：

```python
total files: 908
unique ocs_codes: 904
duplicates: 4 (各佔 2 筆 file)
```

3. 重複的 4 個 code：
   - `BLM2621-001v1` × 2（壽險營業類 vs 壽險推廣／核保 兩個職務共享）
   - `KRM2421-001v4` × 2（產業布署 vs 客戶服務 兩個職務共享）
   - `BHR4910-008v4` × 2（業績管理 vs 課程設計與規劃 兩個職務共享）
   - `Unknown` × 2（兩個 OCS 解析 ocs_code 失敗 → 都 fallback 成 "Unknown"）

4. 第二份 file 的 chunks（profile + units + blocks）覆寫第一份 → 各層各少 4 個 → 但 unit 少 12 個 / block 少 43 個，因為兩份重複 file 的 unit/block 數量不同（後者覆蓋前者全部）

### 根因
- 來源資料品質問題：jd-pdf-to-json 從 PDF 抽取 ocs_code 時，4 對職務基準碰巧抽到相同 code
- 「Unknown」這 2 筆是 PDF 沒寫 ocs_code 或 OCR 失敗 → fallback 統一變 "Unknown" → 互撞
- chunk_key 用 `ocs:{ocs_code}:...` 開頭，code 撞 = chunk_key 撞 = uuid5 撞 = upsert 覆寫

### 修法
**不修 indexer**。這是來源資料的 invariant 違反（OCS 標準要求 ocs_code 是 unique key），不該由 indexer 處理。Indexer 的 deterministic chunk_key 是 by-design 的正確行為。

**未來可選的補強**：
- `doctor` 命令加新檢查：scan 所有 file 的 ocs_code，若有重複就 warn + 列出檔名
- 上游 jd-pdf-to-json 修正 ocs_code 抽取（理想方案）
- 若上游不修，可在 normalizer 對 fallback `Unknown` 改用 file basename 當變體 key

### 預防 / 啟示
- **deterministic key 的雙面性**：保證 idempotent upsert（重跑不重複）的同時，也意味著「source 端 invariant 失敗」會靜默變成「資料覆寫」
- **acceptance test 要對齊預期數字**：發現 12810 ≠ 12869 才查到，平時隨手 stats 是必要的健康檢查
- **fallback value 是 silent merger**：兩個 "Unknown" 互撞 vs 拋 error 二選一時，前者更難 debug

### 影響使用者體驗
失去 4 個職務的索引（含被覆寫的那一份）。**使用者搜尋這 4 個原始 file 的內容會找不到**。對 12,810 / 12,869 ≈ 0.5% 的內容遺失，但對遺失職務的單一搜尋是 100% miss。建議 jd-pdf-to-json 端修正後重 index。

---

## Bug 9: uv 在 Windows 裝成 CPU-only torch，GPU 完全認不到

### 時間 / 觸發場景
2026-06-15，全量 index 已在 CPU 跑完後，要把 embed 改用本機 GPU（RTX 4060 Laptop）。

### 症狀
- `torch.cuda.is_available()` → `False`，`torch.__version__` → `2.12.0+cpu`，`torch.version.cuda` → `None`
- 但 `nvidia-smi` 正常顯示 RTX 4060 + 驅動 596.49 → 硬體與驅動都在

### 診斷過程
1. nvidia-smi OK → GPU/驅動沒問題，是 Python 端的 torch 不對。
2. 確認裝的是 `2.12.0+cpu`（CPU-only build）。
3. `uv pip install torch --torch-backend=auto` → 成功裝成 `2.12.0+cu130`；但**下一個 `uv run` 又把它還原成 `+cpu`**（uv run 會把環境同步回 lock）。
4. 改 `[tool.uv] torch-backend = "auto"` + `uv lock` → lock **完全沒變**，torch 仍來自 PyPI（且 CUDA deps 只標 `sys_platform == 'linux'`）→ Windows 的 CUDA torch 根本不在 PyPI。
5. 加 `[[tool.uv.index]] pytorch-cu130` + `[tool.uv.sources] torch = {index, marker win32}`，`uv lock --upgrade-package torch` → 仍是 PyPI。
6. 根因浮現：`[tool.uv.sources]` 只對**直接依賴**生效；torch 是經 `flagembedding` 進來的**間接依賴** → source/index 覆寫被忽略。

### 根因
三件事疊加：(a) Windows 的 CUDA torch 不在 PyPI（只在 PyTorch 官方 index `download.pytorch.org/whl/cuXXX`）；(b) uv 的 `[tool.uv.sources]` / 索引覆寫**只套用到直接依賴**，間接依賴被忽略；(c) `uv run` / `uv sync` 會把 venv 同步回 lock，所以臨時 `uv pip install` 的變更會被還原。

### 修法
把 torch **提為直接依賴**，索引覆寫才會生效：
```toml
[project]
dependencies = [ ..., "torch>=2.12.0", ... ]

[[tool.uv.index]]
name = "pytorch-cu130"
url = "https://download.pytorch.org/whl/cu130"
explicit = true

[tool.uv.sources]
torch = { index = "pytorch-cu130", marker = "sys_platform == 'win32'" }
```
`uv lock` 後 lock 出現兩個 torch 變體（win32 → `2.12.0+cu130`、其他平台 → PyPI），`uv sync --all-extras` 裝 cu130。之後 `uv run` 持久保留 CUDA（`cuda True`）。`.env` 設 `BGE_M3_DEVICE=cuda` + `BGE_M3_USE_FP16=true`；BGE-M3 在 GPU 約佔 1.1GB VRAM。

### 預防 / 啟示
- **套件管理器會把環境同步回 lock**：別用 `uv pip install` 做持久變更，要改 `pyproject` + `uv.lock`，否則下次 `uv run` 還原。
- **index/sources 覆寫對「間接依賴」常不生效**：要覆寫某個 transitive 套件的來源，先把它提為直接依賴。
- **平台特殊 wheel 要明確指 index**：Windows CUDA torch 不在 PyPI；用 `marker` 讓 lock 可攜（win32 cu130、其他 PyPI）。

### 影響使用者體驗
全量 index（~9,200 點）是在 CPU 上跑的（~3 小時）。早點發現可走 GPU 快 10-20 倍。對 serve 的 `/search` 查詢端 embed 影響小（單 query），主要受益是未來 re-index。

---

## Bug 10: stale `origin/dev` tracking ref 讓 git 誤報「已同步」

### 時間 / 觸發場景
2026-06-15，要把整個 session 的 v3 work（dev branch）push 上 GitHub 時。

### 症狀
- `git status` 顯示 `## dev...origin/dev`（無 ahead/behind → 看起來像已 push）
- 但 `git fetch origin dev` 回 `fatal: couldn't find remote ref dev`（遠端根本沒 dev branch）
- `git rev-parse origin/dev` 卻能解析到本地 commit `803f9fe`

### 診斷過程
1. 三個訊號互相矛盾 → 本地有個 `refs/remotes/origin/dev` 指著 803f9fe，但遠端 fetch 不到。
2. `git ls-remote --heads origin` → 遠端**只有 `main`**（在 f4bda03）。
3. 結論：本地的 remote-tracking ref 是 stale/phantom，與遠端實況不符。

### 根因
本地 `origin/dev` tracking ref 殘留（指向本地 commit），但遠端從沒有 dev branch。`git status` 拿這個 stale 本地 ref 比對 → 誤報 0-ahead，讓人以為已 push。

### 修法
`git fetch --prune origin`（清掉 stale `origin/dev`）→ `git push -u origin dev`（新建遠端 dev + 設 tracking）。

### 預防 / 啟示
- push 前若 ahead/behind 數字看起來怪，先 `git fetch --prune` 對齊本地 tracking ref。
- `git ls-remote` 才是遠端權威；本地 `origin/*` ref 可能過時。

### 影響使用者體驗
差點以為 dev 已備份而沒推——整個 session 的 v3 work 其實從沒上遠端。fetch --prune + push 後 origin 才真正有 dev branch。

---

## 對專題報告可引用的觀察

1. **沒有 hard test framework 不代表沒有 bug**：bug 1 / 2 完全可以靠 type system + invariant 寫成 verify script 抓出來，但需要設計時就想到
2. **Silent corruption 比 crash 嚴重**：crash 至少會被注意到，bug 1 不查 stats 就根本不會發現
3. **反向代理是常見死角**：embedding pipeline 設計 deploy 時很少考慮 body size，但對 1024-dim float vector 是真威脅
4. **客戶端 SDK 預設值 ≠ 部署現實**：qdrant-client 預設 port 6333 是 dev convenience，production 場景幾乎都會被 nginx / cloudflare 蓋掉
5. **資料驗證寫法的成本**：fixture-level invariant check 比寫 pytest suite 便宜很多，且對 schema 改動更敏感
6. **套件管理器的 lock 是真相來源**：`uv run` 會把環境同步回 lock，臨時 `uv pip install` 會被默默還原；要持久改依賴（如 CPU→CUDA torch）必須改 `pyproject` + `uv.lock`，不能靠手動裝
7. **index/source 覆寫對「間接依賴」常失效**：要換掉某個 transitive 套件的來源/變體，先把它提為直接依賴，覆寫才生效（uv `[tool.uv.sources]` 只認直接依賴）
