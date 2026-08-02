# 0053. JdHeader 的 authority 邊界與 readiness 第一版範圍

- 狀態：Accepted
- 日期：2026-08-02
- 補充：[0045](0045-job-analysis-local-web-contract-and-shared-authority-commit.md) 的 authority 邊界
  （**0045 本身的裁決不變**：`title` 仍不屬模型 authority read-set、改名仍不 bump generation）
- 修正：[0052](0052-jd-readiness-assessment-and-official-code-boundaries.md) 決定 11 未指名 seam、
  決定 15–16 漏列一個條件式欄位。**0052 其餘決策全部不變。**
- 審查：外部審查者第七輪（2026-08-02）

## 脈絡

0052 決定 11 把本切片範圍寫成「公版 header／**metadata** 欄位」，**沒有說走哪條寫入路徑**。
這在現行碼上是危險的模糊，因為兩條路徑同時存在且語意相反：

- `application/authoring.py` 的 `put_document_metadata()` 只呼叫 `documents.update_title()`
  後 `uow.commit()`——**不經 `commit_authority_change`、不寫 Journal、不 bump
  `authority_generation`**。0045 是刻意這樣設計的：`title` 是文件庫名稱，不是產品內容。
- 但 `specs/2026-07-29-local-jd-authoring-and-postgresql-persistence-research.md` §4.1 早已把
  **iCAP 表頭、工作描述、級別、主要職責**列為員工可直接編輯的 **Current JD 常駐內容**；
  同檔 schema 段也寫明 `title`「文件庫名稱；第一版不等同完整公版 header」。

施工者看到「metadata」最自然的動作是擴充 `DocumentMetadataWrite`。那會讓工作描述等欄位
繞過 Journal、generation/CAS 與人／AI 共用的整份驗證：員工改了工作描述，AI packet 看不到、
執行中的舊分析不會失效、也留不下可重播的紀錄。**`title` 與「職能基準名稱」會被當成同一欄。**

第二件事：0052 決定 15–16 只赦免了「工作產出」與「態度」，但**說明與補充事項**的官方定義是
「**若**職能基準有其他說明，載於此欄位」（指引 p37 逐字），同樣是條件式欄位。

第三件事：0052 讓第一切片就做 readiness，卻把 Duty 與每 Task 職能級別延後。若沒有明文，
會出現兩種錯誤讀法——現在就檢查 Duty（每份文件都顯示員工無法修復的缺漏），
或不檢查卻顯示「已完成」（對一份還沒有 Duty 的文件做出完整性承諾）。

## 決定

1. **`title` 維持現狀**：文件庫名稱、現行 rename seam、非 authority read-set。0045 不變。
2. **另建最小 `JdHeader`** 承載公版語意欄位（職能基準名稱、所屬類別、工作描述、基準級別、
   說明與補充事項）。**不擴充 `DocumentMetadataWrite`**，兩者是不同的東西。
3. **`JdHeader` 屬 Current JD authority**：員工儲存必須走 `commit_authority_change`、
   寫 Journal、bump `authority_generation` 並受 CAS 保護——與 Task／OPKS 同一條 seam。
4. **高訊號 header 只進 Task Analysis packet**：**至少職能基準名稱與工作描述**不得永遠對
   模型隱形，但範圍限定在 Task Analysis 這一個 operation。
   - 放在**獨立、沒有 ordinal 也沒有 `SourceRef` 的「員工填寫整體描述」區**，
     與有 ordinal 的訪談依據明確分開。
   - 用途只有四項：**理解用語、找 coverage 缺口、發現矛盾、選擇要追問什麼**。
   - **不得單靠它新增、revise 或 withdraw 任何 Task**；顧問看到 header 寫了某項責任，
     正確行為是追問員工實際做法，再由員工原話建立 Evidence。
   - **OPKS packet 本切片不變**：header 不進 OPKS，否則工作描述會變相支撐 K/S，
     繞過 0048／0049 的 Evidence 白名單。

   依據與其界線：2026-07-31 live smoke 已觀測到**便宜模型會把模糊的員工語句過度升格為 Task**
   （Luna-Pro 從員工說的「我會**協助**正式環境部署」直接建出一條 Task），
   因此推論 JdHeader 也必須明確標示為整體脈絡而非 Task 證據。
   **JdHeader 本身尚未直接實測**——2026-08-02 那次是 OPKS，Task 由場景種入，未涉 task discovery。
5. **不建通用 metadata framework，不接舊 OCS autofill 路徑**
   （`OccupationPicker`／header-meta 服務屬 legacy editor，與本 seam 無關）。
6. **readiness 第一版只回 issue 清單**：`DocumentReadinessView` **不含 `is_complete`／`ready`**，
   UI 不顯示綠色「完成」。**零 issue 時保持安靜**，不宣稱整份 JD 已完整。
   第一版只提示**目前 UI 可修復、且官方規則能確定**的 header 缺漏。
7. **Duty 與每 Task 職能級別的規則，等該結構切片完成時加進同一個純函式**，
   不新增 scope／version 欄位來表達「這版只檢查一部分」。
8. **說明與補充事項是條件式欄位**，空白**不列缺漏**（與 0052 決定 15–16 的工作產出、態度同列）。

## 後果

### 正面

- header 只有一條寫入路徑，且與 Task／OPKS 相同：Journal、generation、CAS、整份驗證一致。
- 員工改工作描述會使執行中的舊 AI 分析正確失效，不會產生「AI 看不到員工已寫下的事實」。
- readiness 不會在缺 Duty 時說謊，也不會顯示員工修不好的缺漏。
- `title` 與職能基準名稱分離，文件庫改名不再被誤讀為改動產品內容。

### 負面／代價

- 多一個 authority 欄位群組，header 的每次儲存都會 bump generation——比 rename 重，
  但這正是它與 rename 的差別所在。
- 第一版 readiness 永遠不會說「完成」，員工得不到明確的完工訊號；
  這是刻意的，直到 Duty 切片補上為止。
- header 進 Task Analysis packet 會增加 token 與被誤用為證據的風險，靠決定 4 的分區標示、
  「不得單靠它動 Task」與既有 prompt 邊界擋；OPKS 則以「不放進去」直接避開。
- 與 blind-first 顧問流程相容：固定開場仍是「先不用照職稱回答」，header 屬**待驗證脈絡**而非答案。
  舊流程中「防止職稱錨定」保留；但「表頭永遠晚到 Task 穩定後才可見」不再適用——
  現在員工可自由編輯 header，AI 看不到員工已寫下的事實才是更大的失真。
