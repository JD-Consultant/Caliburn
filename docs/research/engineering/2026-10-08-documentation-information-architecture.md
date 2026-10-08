# Caliburn 文件資訊架構與持續維護研究（2026-10-08）

狀態：研究／整理建議。讀者是需要理解、修改與維護 Caliburn 的開發者；本研究協助選擇文件整理方式，不授權搬檔、刪除材料或改動產品。查閱日期：2026-10-08。

後續：使用者已同意依本研究整理；執行範圍與驗證由[文件維護計畫](../../plans/2026-10-08-docs-maintenance.md)記錄，採用的持續規則整合回[文件規範](../../implementation/documentation-standard.md)。下文保留研究時的盤點與建議。

建議先釐清每個主題的**現行責任文件、候選方案與歷史證據**，並讓讀者從常見任務直接找到答案；再處理有實際誤導或維護成本的檔名及位置。現有 `docs/README.md`、`architecture/`、`implementation/` 等分工可以保留作為基礎。Diátaxis 適合檢查一頁要解決哪種讀者需求，不能據此推導全庫必須搬成四個目錄。Google 與 GitLab 的做法則支持隨碼更新、減少冗餘，以及讓來源與閱讀入口各負其責。[Diátaxis](https://diataxis.fr/how-to-use-diataxis/)、[Google 文件維護](https://google.github.io/styleguide/docguide/best_practices.html)、[GitLab 目錄規範](https://docs.gitlab.com/development/documentation/site_architecture/folder_structure/)

閱讀順序：方法依據見 §1–2，實際問題見 §3，建議分工與執行順序見 §4–5。研究中的建議不升格為另一份文件規範，採用後仍由[文件與圖面規範](../../implementation/documentation-standard.md)維護。

## 1. 一手來源與可支持的主張

以下都是來源擁有者的公開指引或實務，不是對所有團隊的效果保證，也不把單一公司的規則稱為業界共識。

| 來源 | 已核對的官方內容 | 適用限制 |
|---|---|---|
| [Diátaxis：工作方式](https://diataxis.fr/how-to-use-diataxis/) | 先按讀者需求改善小單位；不要預先強加四分類或建立空目錄 | 不提供 Caliburn 的責任分層、歷史保存或具體路徑規格 |
| [Google：Documentation Best Practices](https://google.github.io/styleguide/docguide/best_practices.html) | 文件與程式同一變更更新；漸進清理錯誤與冗餘；README 指路；完成後的設計稿保存決策脈絡 | Google 的刪除建議不直接授權刪掉本案研究原件或 Accepted ADR |
| [Google：Cross-references and linking](https://developers.google.com/style/cross-references#provide-context-on-the-page) | 少量必要概念就在本頁交代；選最相關的連結，避免多條路線做同一件事 | 允許長頁、不同入口等情境出現必要的重複連結 |
| [GitLab：Folder structure](https://docs.gitlab.com/development/documentation/site_architecture/folder_structure/) | 依讀者及 UI／API 組織；新頁及改名頁須能由上層及相關頁找到；可由導航連入原 repo 的唯一來源 | `_index.md`、URL 與網站目錄一致是 GitLab 的特定實作，不需套到本案 |
| [GitLab：Style guide](https://docs.gitlab.com/development/documentation/styleguide/#documentation-is-the-single-source-of-truth-ssot) | 文件是產品資訊的可信來源，持續修正；已存在的答案優先分享連結 | SSoT 明確不等於全面禁止內容重複；摘要是否合理仍須按用途判斷 |
| [Microsoft：Maintain an ADR](https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-decision-record) | ADR 保存重要決策的情境、理由與影響；Accepted 不覆寫，以接續 ADR 取代並互連；不要把 ADR 當設計指南 | 決策紀錄不能單獨承擔現行系統的完整操作與參考說明 |
| [GitLab：Automated pages](https://docs.gitlab.com/development/documentation/site_architecture/automation/) | 公開列出 API、CLI 等生成頁及其來源／負責者；生成流程也有維護成本，須說明檔案、pipeline 及排錯方式 | 不代表所有正文都值得生成，也不要求導入 GitLab 的平台及管理流程 |

## 2. 官方做法對本題的含義

### 2.1 讀者導航可以先改善，物理位置另按維護責任決定

Diátaxis 的四種需求有助於辨識一頁混合了教學、操作、參考或解釋，官方工作指引同時反對為了符合外形而先全面重組。GitLab 則採讀者與產品領域組織檔案，並允許來源留在其他 repo，由導航連入。兩者顯示實際組織方式受讀者與產品形態影響，沒有一套通用目錄名稱。[Diátaxis 工作方式](https://diataxis.fr/how-to-use-diataxis/)、[GitLab 目錄規範](https://docs.gitlab.com/development/documentation/site_architecture/folder_structure/)

**Caliburn 建議：**入口按「了解產品、理解現行架構、改程式、操作排錯、查方法、查證據與歷史」提供短路徑。同一現行責任文件可由多個入口連入；檔案只有一份。若入口只能把人送往另一個入口，卻未幫助讀者選擇，應改成直接連到回答該問題的頁或章節。是否搬檔要由內容責任與生命週期判定，不能只因名稱帶日期、design 或 research 就決定。

### 2.2 單一來源仍須讓每頁可理解

Google 建議幾句就能交代的背景放在本頁，避免讀者為簡單概念跳走；連結應指向最相關的目的地。GitLab 的 SSoT 也明說不排除合理的重複內容。[Google 連結指引](https://developers.google.com/style/cross-references#provide-context-on-the-page)、[GitLab SSoT](https://docs.gitlab.com/development/documentation/styleguide/#documentation-is-the-single-source-of-truth-ssot)

**Caliburn 建議：**唯一維護的是精確契約、狀態、門檻、格式、完整操作步驟及驗證結果；其他頁可保留足以理解當前主題的摘要、前提與例子，再連原件。判斷標準是「規則變動時，是否必須手動修改多份完整規則才能避免互相矛盾」，不是禁止任何相似句子。報告可按受眾重述設計，但應標示報告範圍及證據版本，不成為工程人員判斷現行行為的第二個權威。

### 2.3 現行參考持續更新，提案與決策沿革保留當時條件

Google 指出實作完成後的設計文件應保存決策，而不能放任它成為半正確的現行說明。Microsoft 把 ADR 定義成追加的決策紀錄；改向使用接續紀錄，不回寫 Accepted 的原決策。[Google 文件維護](https://google.github.io/styleguide/docguide/best_practices.html)、[Microsoft ADR](https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-decision-record)

**Caliburn 建議：**先辨認頁的角色，才決定更新或封存：

| 內容角色 | 建議處置 |
|---|---|
| 現行責任、契約、操作及方法 | 隨行為更新；必要時指出正式依據與尚未覆蓋的限制 |
| 尚在比較或未採用的提案 | 保留候選／未實作狀態，連到當前判斷；不混入現行操作入口 |
| 已取代方案、已完成施工與過去比較 | 保留當時版本、條件、結果及接續去向；由歷史或證據入口查閱 |
| 沒有獨有資訊的副本、已錯誤的操作說明 | 在確認引用與取回方式後合併或移除；不可直接套用到原始證據 |

部分有日期的 `specs/` 文件仍承擔現行契約，不能整批當歷史搬走。研究文件保存「當時為何這樣判斷」；已採用的規則回到責任文件；`current-decisions.md` 只維護狀態與路由。這是本案既有[決策流程](../../decision-process.md)與[研究慣例](../README.md)的延伸，不是新增一套 authority。

### 2.4 隨碼審查比定期全庫重寫更可持續

Google 要求文件在改程式的同一變更中更新，並建議漸進整理。GitLab 要求改名或新增頁同時處理可發現性。[Google 文件維護](https://google.github.io/styleguide/docguide/best_practices.html)、[GitLab 目錄規範](https://docs.gitlab.com/development/documentation/site_architecture/folder_structure/)

**Caliburn 建議：**每次改行為時，從受影響模組追到責任文件；同步檢查該頁、相關入口與必要操作說明。純文件重組則驗連結、錨點、狀態及內容保留。這可以沿現有 review 執行，不必先加新的委員會、文件平台或每頁定期簽核欄。只有反覆發生、可機械判定的失敗值得自動檢查，例如失效本機連結、生成物與來源不一致；讀者能否理解仍需人工按實際任務驗證。

### 2.5 生成資料與圖稿保留可追溯來源

GitLab 公開把部分 API／CLI 參考資料列為生成文件，並記錄生成方式及維護責任；也提醒每種自動化都增加支援成本。[GitLab Automated pages](https://docs.gitlab.com/development/documentation/site_architecture/automation/)

**Caliburn 現有基礎：**[契約策略](../../contract-strategy.md)已指定 JSON Schema 為 App 傳輸格式來源，型別及 OpenAPI 沿生成鏈產生；[文件與圖面規範](../../implementation/documentation-standard.md#33-圖面交付與維護)已規定一圖一份 `.mmd`，PNG／SVG 與報告圖稿為衍生物。

**Caliburn 建議：**整理時保留這些來源與生成命令的清楚路徑。檔案盤點須區分可編輯正文、圖源、生成物及實驗原件，不能以檔案總數多就判定文件過量。API 的欄位清單不再另寫一份完整手工副本；正文補用途、約束理由與代表性流程。圖稿按讀者視角保留必要省略與狀態，重新渲染通過只證明產物可生成，不證明設計與程式一致。

## 3. 本機盤點：亂在哪裡

### 3.1 文件、原件與本機封存混在同一棵樹

2026-10-08 盤點目前工作樹，包含未提交及 ignored 檔案；以下是新增本研究稿前的快照。使用檔案 metadata、Git 索引／ignore 分類及 Markdown 行數統計，沒有把日期當成是否有效的判準。

| 範圍 | 檔案數 | 容量 | Markdown 數 | 意義 |
|---|---:|---:|---:|---|
| 全部 `docs/` | 14,192 | 約 2.48 GB | 2,128 | 不是 14,192 份人工維護正文 |
| `experiments/` | 12,323 | 約 2.41 GB | 773 | 占全部容量 97.15%，含原始輸出、快照與重播材料 |
| `archive/` | 1,378 | 約 50 MB | 1,022 | 全部 ignored；占 Markdown 48.03%、Markdown 行數 63.86% |
| 排除上述兩區 | 491 | 約 20.7 MB | 333 | 仍包含 ADR、研究及報告，不等於全部現行契約 |

其中架構、實作、規格與分析指南合計 54 份 Markdown；有效內容仍須依頁與段落判斷。實驗目錄第一層有 31 個子目錄，27 個以日期開頭，與 `product-validation`、`engineering` 等用途分類並列，是可先改善的導覽問題。

Git 索引列 6,821 個檔案，其中五份圖源已在工作樹刪除、尚未提交，因此磁碟上的追蹤檔是 6,816 個。另有 2,446 個 ignored 檔及 4,930 個未追蹤、非 ignored 檔；後者含目前工作的實驗與圖稿，不能因尚未提交就當作可刪暫存。工作盤點保存在 `.tmp/docs-organization-20261008/inventory.json`，正式結論以本表的日期快照為準。

**判斷：**日常閱讀／搜尋與追查實驗／歷史需要不同範圍。先整理導航及搜尋預設；原件數量大本身不證明應搬走或刪除。`archive/` 雖不隨 Git 發布，仍讓本機檔案樹與全文搜尋充滿舊正文。

### 3.2 已找到可核對的維護問題

| 問題 | 本次證據 | 建議處置 |
|---|---|---|
| 索引重述狀態，已產生矛盾 | [研究索引](../README.md)兩條工程研究仍寫「待審查／未啟動重構」；[目前決策](../../current-decisions.md)及[計畫索引](../../plans/README.md)已寫本輪全系統審查重構完成 | 研究索引只說研究什麼、連向哪裡；計畫維護施工結果，決策入口指向現在採用的規則 |
| 狀態頁變成逐輪實驗日誌 | `current-decisions.md` 的 RAG 檢索單格約 3,007 字元；[規格索引](../../specs/README.md)又列配對增加 57%、12 來源／8 面向等相同結果 | 狀態頁保留目前採用、未決問題與去向；數字和完整限制只回實驗分析原件 |
| 現行與歷史交錯，讀者須自行拼契約 | [Plan 設計](../../specs/2026-10-06-consultant-interview-planning-and-focus-design.md)的現行用途從 §10 開始，工具／保存仍在 §5–6；前段及 §10.5 又含已取代討論 | 先形成完整可讀的現行契約，再將沿革移後或抽出；有效內容不能整份封存 |
| 策略與接線重複寫生成機制 | [契約策略](../../contract-strategy.md)與[資料及契約 §5](../../implementation/data-and-contracts.md#5-唯一契約來源及生成)都記生成器、資源、OpenAPI 及驗證邊界 | 策略維護接縫與選擇理由；實作維護生成機制；可執行命令由 App README 維護 |
| 新入口仍經舊轉址 | `current-decisions.md`、`specs/README.md` 等仍把[舊架構地圖](../../target-architecture-map.md)當主要入口；該頁已是相容轉址 | 受維護的內部路由直連架構入口／責任章節；必要的外部舊路徑與錨點保留 |
| 操作入口讓讀者先選元件 | [文件導覽](../../README.md)並列 API、Web、runbook；API README 又引導回 runbook | 「啟動產品」直接指向 runbook；App README 標為元件開發、設定參考與測試 |
| 直接搜尋進舊研究，讀者看不到上層歷史提醒 | [2026-08-27 Context 研究](../agent-systems/2026-08-27-consultant-conversation-continuity-and-understanding-context-research.md)仍依當時脈絡寫「目前基線」及 ADR0071 Proposed | 保留當時正文，頁首補研究時點與現行接續去向；不要求讀者先經研究索引才能辨認範圍 |

上述不是只靠連結檢查能發現的問題：檔案與錨點可能全部存在，讀者仍會看到不同狀態或走錯維護位置。這輪抽查導航及相關正文，未聲稱逐段驗證全部 333 份非實驗／封存文件。

### 3.3 證據整理須保留可重現性

兩組 Plan 比較中的六套 `source-snapshot` 共 2,833 個檔案；位置在 `interview-plan-comparison-2026-10-07/{formal,formal-append,pilot,pilot-reviewed}` 與 `jd-work-plan-comparison-2026-10-07/runs/{comparison-v1,comparison-v2}`。比較入口的 freeze 綁定材料與 production source bytes，改動會使外送檢查拒絕。保存目的及規則沿[產品實驗索引](../../experiments/product-validation/README.md)與[原件保存](../../experiments/artifact-storage.md)查閱。

本批原件先留原位。正文導航只連實驗方法／結果入口，不列全部 trace、JSON、快照檔案。若後續搬原件，先核 manifest、seal、runner 路徑及原始雜湊，不能以「整理」改寫凍結證據。大檔先沿既有 gzip、SHA-256 與 manifest 機制；新實驗的程式快照再評估用固定 commit 加必要差異，或不可變封存包。能否重現須驗證，不能只留當時未提交程式的 commit SHA，也不先另建一套全域產物平台。

快照內的 ignored `.pytest-tmp`、`__pycache__` 等本機執行暫存，應與需保存的 source bytes 區分。新工作把暫存放 repository 既有 `.tmp/`；已有材料須核用途後再處理。`archive/` 部分原件從未提交，[歷史索引](../../history.md)也明示沒有 Git 取回命令；不能以「Git 有歷史」為由刪掉唯一副本。

## 4. 建議方案與目錄責任

### 4.1 選擇：保留主要目錄，整理正文生命週期

| 方案 | 效果與代價 | 判斷 |
|---|---|---|
| 只改 README 與目錄名稱 | 能減少第一層視覺雜亂，但 Plan 的混合契約及多處狀態仍存在 | 不足以解決維護問題 |
| 保留主要目錄，收斂唯一責任、重整混合正文，必要時局部拆檔 | 能消除已找到的漂移，保留近期架構／實作／圖源整理；需逐題核對內容及舊引用 | **建議採用** |
| 全部改成新的文件樹或先上文件網站 | 可重做外觀與搜尋，但大量路徑、圖稿生成及封存引用要跟著改；內容矛盾仍須另外處理 | 暫無證據顯示值得優先做 |

### 4.2 保留的來源分工

下面是建議分工，不是另一份永久索引；採用後具體路由只在 `docs/README.md` 及各目錄 README 維護。

| 位置 | 持續維護什麼 | 不累積什麼 |
|---|---|---|
| `docs/README.md` | 按讀者任務選入口 | 完整檔案清單、最新實驗結果、工程日誌 |
| `current-decisions.md` | 現在採用什麼、未決問題、責任文件與下一步去向 | 每輪比較數字、完整限制及施工過程 |
| `architecture/` | 整體責任、保證、資料流與取捨 | 細部 SQL／工具欄位或實驗逐項結果 |
| `specs/` | 詳細行為、工具、資料資格及生命週期契約；候選／目標明確分開 | 無限追加新章來覆蓋舊章，要求讀者自行合成現行規則 |
| `implementation/` | 模組接線、工程規範、測試方法 | 另一份產品權責或最新實測結果 |
| `runbook.md`、App README | 前者維護跨 App 操作與排錯；後者維護元件開發、設定及測試 | 三處相同的完整啟動步驟 |
| `guides/` | 工作分析、訪談及 JD 內容方法 | 工程入門或程式規範；入口明寫「工作分析與 JD」避免誤讀 |
| `adr/` | 重要決策、理由、當時條件與接續關係 | 從頭到尾的現行操作指南 |
| `research/` | 外部方法、選項、證據及當時推論 | 另一份持續更新的產品規格 |
| `experiments/` | 方法、受測版本、結果、限制及可回查原件 | 把測試通過當成正式採用決策 |
| `plans/` | 施工範圍、工作進度、驗收與證據去向 | 再抄一份設計、重新啟動已結案切片 |
| `reports/` | 指定讀者與日期範圍的解說及成果 | 工程人員需同步修改的第二份現行契約 |
| `diagrams/` | 一圖一份圖源與生成物，正文引用 | 重複 `.mmd` 或獨立於責任文件的新產品規則 |
| `history.md`、本機封存 | 原件定位與取回；區分已提交與僅本機可用 | 日常閱讀必經入口 |

暫不新增 `development/`、`standards/`、`operations/` 等同義目錄。現有 implementation 已承擔開發與規範，runbook 已是完整操作入口；若後續出現多份需獨立維護的操作手冊，再按任務拆分。`design/` 目前主要剩獨立 RAG 與歷史路由，可在清理時把現行 RAG 說明歸入架構的明示獨立範圍，再處理舊入口；不把它升格為第二套系統設計分類。

現行契約若需要新名稱，採穩定主題名，例如 `specs/jd-work-plan.md`；研究、提案、實驗和計畫沿日期命名。既有有效文件不只因檔名帶日期就批次改名。Plan 可作第一個局部拆分例子：將現行用途與仍有效的工具／保存規則**移至**現行頁，舊日期頁保留沿革與必要錨點；不能複製成兩份完整規格，也不改寫 Accepted ADR 或凍結實驗原件。

### 4.3 讀者看到的入口比來源分類更少

首頁建議只展示下列任務，讓來源位置依維護責任保存；同一頁可被不同任務引用。

| 讀者現在要做什麼 | 直接入口 |
|---|---|
| 第一次了解產品與系統 | 產品介紹 → 架構導覽；報告作另外一條深入閱讀路徑 |
| 啟動、操作或排查問題 | runbook 的相應步驟 |
| 修改程式、Prompt、Tool 或 Context | implementation 對應範圍 → 必要的詳細契約 |
| 查當前規則與未決問題 | current-decisions → specs／ADR |
| 改善訪談與 JD 分析方法 | guides → 原研究與效果證據 |
| 查測試結果、研究或歷史 | 驗證範圍／研究／實驗入口；歷史取回另列 |

日常搜尋優先覆蓋現行文件、指南與必要程式；原始實驗、歷史、生成圖檔設為另選範圍。這是閱讀／搜尋預設，不是把原件刪除或從 Git 移除。若仍常卡在跨頁搜尋，再評估靜態文件站；屆時沿用同一批 Markdown，不手工複製第二套網站正文。

## 5. 建議實施順序與驗收

1. **先修入口與已知漂移。** 清除索引內的過期施工狀態，將 RAG 逐輪結果回歸證據 owner；把現行內部連結改成直接路由。驗證啟動、理解架構、修改 Tool、查真模型結果四條閱讀路徑，讀者能說出要讀／改哪一頁。
2. **再重整混合正文。** 先做 Plan，列出每節屬於現行、目標、候選或沿革，再移動有效規則與歷史；保留所有獨有條件和必要舊錨點。接著處理契約策略／實作的重述，其他 spec 依相同方式逐題處理，不整批按檔名判斷。
3. **最後整理材料與維護工具。** 實驗入口按產品、工程、檢索／資料處理分組；原件先保留原位置。結案計畫退出活動清單，未完問題轉回其責任文件；本機封存及暫存分開。若要物理移動，保存逐檔映射與雜湊並驗證可取回。

每批皆檢查本機連結／錨點、遺留引用、狀態與內容保留；修改圖源時核生成一致性與實際外觀。將目前位於工作暫存區的引用檢查整理成可重複執行、版本控制的文件檢查入口，並納入受影響變更的 review／CI；先查本機引用與生成物，網路來源檢查另作有界執行，避免外站偶發故障阻塞所有修改。不把連結測試當成語意驗收。

維護時應能回答「這次改哪一份責任正文、哪些引用受影響」。新需求先改對應正文；若舊內容已失效，就整合或移出現行段落，不能只在頁尾追加「最新補充」。入口可保留必要簡短摘要；完整規則、狀態與結果不用在多個 README 同時手改。上述規則應整合到已有文件規範，不再建立新的治理文件。

本輪交付為研究與建議，沒有搬動正文、原件或改變既有權責；後續整理可直接沿上述批次做，不需要再廣搜同類方法。

## 6. 限制與決策去向

這些來源支持資訊架構與維護原則，沒有證明某個目錄數、檔案行數或跳轉次數適合 Caliburn。讀者導航改善也不能代替內容正確性；連結全通不代表現行／候選標示正確。本輪不根據文件日期自動封存，不把圖稿或實驗原件當成重複正文，也不導入新的網站生成器、搜尋平台或文件 metadata 系統。

後續若採用局部整理，規則仍集中於現有[文件與圖面規範](../../implementation/documentation-standard.md)，路由由各層 README 維護，歷史取回依[歷史查閱方式](../../history.md)。本研究保存來源、比較及當時建議，不持續複製最新檔案配置。
