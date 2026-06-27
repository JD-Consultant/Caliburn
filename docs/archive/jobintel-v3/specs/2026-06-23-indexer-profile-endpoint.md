# jd-ocs-indexer 新端點提案：`GET /profile/{ocs_code}`（職類 metadata）

> 提出者：jobintel-ai v3（消費端）。目標：**選職類時一次 call 拿到官方完整表頭 + notes + 態度**，
> 讓 v3 自動填好職務說明書表頭，員工只需專注填任務內容。
> 結論前提（已查證 jd-ocs-indexer 原始碼）：**資料全在 profile chunk payload**，只差一個乾淨的取用端點 +
> 一個 builder payload 小補（`job_category_codes`）。

---

## 1. 為什麼要這個端點

v3 職務說明書表頭（OCS `ocs_profile` + `notes` + `ocs_attitude`）需要：
職能基準代碼、名稱、**所屬職類/職業/行業別**、**工作描述**、**基準級別**、**應備資格(prerequisites)**、
**補充說明(supplements)**、**態度 A**。

現況取用缺口：
- `/search` 的 `_project_hit` 其實有回 `job_description / ocs_level / industry_names / occupation_names`，
  但 **(a) 無 code、(b) 要先做一次向量搜尋才拿得到、(c) 沒有 `job_category`、notes**。
- `/profile/{code}/pairs` 只回 K/S/A 池 + `prerequisites/supplements`，**無 category/level/description**。
- 沒有任何端點回 `job_category(_name)`。

→ 缺一個「**按 ocs_code 直接取 profile metadata**」的端點。資料都在，純投影。

## 2. 提案契約

```
GET /profile/{ocs_code}
200 OK
```
```jsonc
{
  "ocs_code": "BHR2422-015v1",
  "job_title": "農業人力資源管理師",          // = occupation_name
  "job_category": { "code": "BHR", "name": "人力資源類" },  // 見 §4 builder 補洞
  "occupations": [ { "code": "2422", "name": "人力資源專業人員" } ],
  "industries":  [ { "code": "A",    "name": "農、林、漁、牧業" } ],
  "job_description": "規劃並執行農業組織之人力資源……",
  "ocs_level": 4,
  "attitudes":     [ { "code": "A1", "name": "主動積極" } ],
  "prerequisites": [ "具備 2 年以上相關經驗……" ],
  "supplements":   [ "本職能基準適用於……" ]
}
404  // ocs_code 不存在（無 profile point）
```

設計註記：
- **回 indexer 原生 flat 結構**，不耦合 v3 的文件 contract（v3 自行 map，見 §3）。
- `occupations`/`industries`/`job_category` 一律 `{code, name}`（zip payload 的 `*_codes` + `*_names`）。
- notes（prerequisites/supplements）+ attitudes **併入本端點**（A+B 合一），省一次 round-trip；
  `/profile/{code}/pairs` 維持不動（K/S/A 池另用途）。
- 實作＝對 profile point 做一次 `scroll(limit=1, filter: ocs_code + chunk_level=profile)`，
  投影 payload（同 `get_pairs` 取 `prof_recs[0]` 的作法）。零新資料、零 embedding。

## 3. v3 對應（消費端 map → 文件 `ocs_profile`/`notes`/`ocs_attitude`）

| 端點欄位 | → 文件欄位 |
|---|---|
| `job_title` | `ocs_profile.ocs_name.occupation_name` |
| `job_category.name` | `ocs_profile.ocs_name.job_category_name` |
| `job_category` | `ocs_profile.category.job_categories[0]` |
| `occupations` | `ocs_profile.category.occupations` |
| `industries` | `ocs_profile.category.industries` |
| `job_description` | `ocs_profile.job_description` |
| `ocs_level` | `ocs_profile.ocs_level` |
| `attitudes` | `ocs_attitude.attitudes`（或當 A 候選預設）|
| `prerequisites` | `notes.prerequisites` |
| `supplements` | `notes.supplements` |

v3 端後續（非 indexer 工作，另記）：
- 放寬 `services/knowledge/models.py::Hit`（目前 `extra="ignore"` 丟掉這些欄位）或新增 `ProfileMeta` model + client method。
- `routes/documents.py::set_occupations` / `_refresh_header`：取此端點自動填表頭 + notes + 態度。

## 4. ⚠️ builder 需補一個欄位（否則 `job_category.code` 拿不到）

- `normalizer.py` **有**抽 `job_category_codes`（L160-169）與 `job_category`(名稱, L157)。
- 但 `builder.py::_profile_record`（payload, L97-118）**只存 `job_category`（名稱字串），沒存 `job_category_codes`**。
- 其餘（`industry_codes/names`、`occupation_codes/names`、`ocs_level`、`job_description`、
  `all_a_pairs`、`prerequisites`、`supplements`）payload **都已存**。

→ 修法：`_profile_record` payload 加 `"job_category_codes": list(norm.job_category_codes)`，
   **重新 ingest**（或先上端點、`job_category.code` 暫回 `null`，補洞後再重灌）。
   其餘欄位無需重灌。

## 4b. 多選職務 + 分類選單（v3 端，重點防雷）

文件可含**多個 OCS**（合併成一份）。表頭 `category` ＝各 OCS 官方分類的**聯集**，做成**勾選清單**
（職類別/職業別/行業別，含代碼），預設全勾、AI 可預選。

**候選聚合（集中在 v3 一處，好測）**
- 逐 `ocs_code` 呼叫 `GET /profile/{ocs_code}` → 取 `job_category / occupations / industries`。
- 三類各自**依 `code` 去重**聚合成候選池（⚠️ D27 曾因 duplicate key 崩潰，這裡同風險）。
- 保留來源：每個候選記它由哪些 ocs_code 帶入（取消某 OCS 時只移除「僅它帶入」者）。

**選單行為**
- 預設：已選 OCS 帶入的候選**全部預勾**（官方事實，deterministic、免 LLM）。
- AI 預選（第二步、選配）：聯集較雜時依 intake 勾「真正符合此職務」者，其餘留空待確認。
- 勾選 → 寫入 `ocs_profile.category.{job_categories,occupations,industries}`，取代 DocHeader 手打。

**多 OCS 防雷清單**
1. 去重以 `code` 為鍵；`code` 為空者退而以 `name` 去重（避免無 code 自訂項互蓋）。
2. 取消某 OCS：只移除「僅由該 OCS 帶入」的候選，**不得**清掉其他來源或使用者手動勾選/編輯。
3. 聚合保序（first-seen），重繪間 key 穩定（沿用 D27 教訓：key 不可用陣列 index 亂跳）。
4. **職能基準代碼/名稱 ＝一組綁定的對、單值**（代碼↔名稱一起變，不可拆兩格各填）：
   - 多 OCS 時表頭只放**一個**主基準；預設＝**第一順位 `codes[0]`**（選職類已排序）。
   - 允許使用者從「已選 OCS」清單**切換**要哪個當主基準（切換時 code+name 同步換）。
   - 對比：`category`（職類別/職業別/行業別）才是**多值聯集勾選**；代碼/名稱不是。
5. `version_info.versions[].ocs_code/ocs_name` 同步只記主基準（`codes[0]` 或使用者切換後者），別逐 OCS 灌爆。

## 5. 範圍 / 不做

- **做**：1 個唯讀投影端點 + 1 行 builder payload 補欄。
- **不做**：改 search 排序（相關性弱是另案）、改 pairs、加寫入端點。
- **多職類**：v3 文件可含多 OCS；v3 端逐 code 呼叫即可（端點維持單 code，簡單）。
