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

修了 4 個阻塞 bug，留 2 個 noise。整體成本（含學習 / 診斷 / 編程）約 4 工時。

---

## 對專題報告可引用的觀察

1. **沒有 hard test framework 不代表沒有 bug**：bug 1 / 2 完全可以靠 type system + invariant 寫成 verify script 抓出來，但需要設計時就想到
2. **Silent corruption 比 crash 嚴重**：crash 至少會被注意到，bug 1 不查 stats 就根本不會發現
3. **反向代理是常見死角**：embedding pipeline 設計 deploy 時很少考慮 body size，但對 1024-dim float vector 是真威脅
4. **客戶端 SDK 預設值 ≠ 部署現實**：qdrant-client 預設 port 6333 是 dev convenience，production 場景幾乎都會被 nginx / cloudflare 蓋掉
5. **資料驗證寫法的成本**：fixture-level invariant check 比寫 pytest suite 便宜很多，且對 schema 改動更敏感
