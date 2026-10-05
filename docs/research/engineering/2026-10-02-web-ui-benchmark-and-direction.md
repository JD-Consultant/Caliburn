# 前端視覺基準研究：哪個「公認好看」的設計適合 Caliburn

查閱日 **2026-10-02**。這是視覺方向的研究與選型紀錄，不改產品規格、API、資料責任或任何 ADR；沒有新增或改變功能（§10 的編輯方式是互動方式的決定，已採用並實作，見該節）。實作與驗證見[視覺改版證據](../../history.md#source-a75c36d876a672e0f607)。維護者授權工程代理自行研究並決定視覺方向，本頁記錄依據。

**閱讀方式：**
- **Fact**：來源明文（官方文件、標準、官方部落格）。
- **Measured**：我下載該站**公開送出的 CSS**，自己統計出的數值。這是行銷站的 CSS，不是登入後產品畫面的 token；只能說明該團隊的設計習慣，不能當作官方 token 文件。
- **Mapping**：對 Caliburn 的取捨。
- **Unknown**：沒取得或沒驗證，不能當作已查證。

## 1. 問題與方法

問題：要找一個「公認好看」的 Web 設計，學它的排版、UI、色彩、透明度，再用它優化 Caliburn 前端。Caliburn 的畫面特性決定了什麼樣的「好看」才有用：

- 左訪談（聊天）／右 JD（長文件）並排，使用者每次停留數十分鐘，反覆閱讀與編輯。
- 內容是**繁體中文長文**，夾雜英數與全形標點。
- 有三種必須一眼分辨的內容：正式 JD、AI 候選、非正式處理訊息；以及來源徽章、待核對、唯讀鎖定。

方法：①查近年設計獎名單；②查產品級設計系統的官方文件；③下載標竿站公開 CSS 做頻率統計；④查中文排版標準；⑤算對比度；⑥用上面的畫面特性篩選。

## 2. 獎項能證明什麼，不能證明什麼

| 來源 | 查到的結果 | 性質 | 對 Caliburn 的可轉移性 |
|---|---|---|---|
| [Awwwards 歷年年度站](https://www.awwwards.com/websites/sites_of_the_year/)（[2025 官方得獎頁](https://www.awwwards.com/annual-awards/winners)） | **2025 年度站：Lando Norris（OFF+BRAND）**；Developer Site of the Year：Messenger（abeto，入圍年度站但未得）。2024 Igloo Inc、2023 Lusion v3、2022 KPR、2021 Pangram Pangram Foundry、2019 Bruno Simon Portfolio…… | 官方清單 2017–2025 共九年，全是品牌站、作品集或 3D 體驗，**沒有任何生產力工具或儀表板** | **不轉移整站**：動態與 3D 是賣點，長時間閱讀編輯不適用；可借的只有個別元素，見 §8 |
| [Awwwards 2026 每日站](https://www.awwwards.com/websites/saas/) | Nine To Five（ET Studio）等 | 行銷站、作品集 | **不轉移** |
| [Apple Design Awards 2026](https://www.apple.com/newsroom/2026/06/apple-reveals-winners-of-the-2026-apple-design-awards/) | 12 個得獎，6 類（Delight、Inclusivity、Innovation、Interaction、Social Impact、Visuals） | 多為消費 App 與遊戲 | 背景資料；其 Inclusivity 評語強調 Dynamic Type、對比度，與我們的無障礙方向一致 |
| [Webby 2026 Best Visual Design–Function](https://winners.webbyawards.com/winners/websites-and-mobile-sites/features-design/best-visual-design-function) | FOLLOW.ART（Vide Infra）；人氣獎 Affinity Studio（Canva） | 網站 | 未逐一分析 |
| CSS Design Awards、FWA、Red Dot Brands & Communication 2026 | 搜尋只拿到機制說明，**未取得完整名單** | — | **Unknown** |
| [Craft Docs](https://www.businesswire.com/news/home/20211202005370/en/Craft-Docs-Wins-Mac-App-of-the-Year-for-Apples-2021-App-Store-Awards) | Apple 2021 App Store Awards「Mac App of the Year」；[2021 Apple Design Awards](https://developer.apple.com/design/awards/2021/) 為 **Innovation 類決選入圍，不是得主**；列名[德國設計獎](https://www.german-design-award.com/en/gallery/detail/interactive-user-experience/craft-docs-1)（Interactive User Experience，名次未驗證） | 文件編輯器 | **高**：同屬「長文件編輯」 |
| [GOV.UK](https://www.dezeen.com/2013/04/16/gov-uk-government-website-wins-designs-of-the-year-2013/) | Design Museum「Design of the Year 2013」（首個數位專案得主）＋D&AD Black Pencil | 公共服務網站 | 無障礙與清晰度可借鏡；外觀不採用 |

**Fact／結論：**
1. 主要網頁獎項（Awwwards、CSSDA、FWA）獎勵的是表現力，不是工具型介面的耐看度，不能直接當範本。（本頁初版曾把 Messenger 誤寫成 2025 年度站；2026-10-02 依 Awwwards 官方得獎頁更正：年度站是 Lando Norris，Messenger 是 Developer Site of the Year。結論不變，證據更扎實：官方清單九年皆非工具型。）
2. 能查證的正式獎項只有 Craft 與 GOV.UK。
3. Linear、Vercel、Notion、Stripe、Claude 常被當作產品設計標竿，但我**沒有查到可驗證的正式獎項**：Awwwards 上 Stripe 只有 2016 年一次提名（[頁面](https://www.awwwards.com/sites/stripe)），Linear 與 Notion 的 Awwwards 頁面回 404。本頁因此稱它們為「業界標竿」，不稱「得獎」。

## 3. 標竿的實測數值（Measured）

2026-10-02 下載各站首頁引用的全部 CSS 並統計。括號內是出現次數。

| | Linear | Vercel（Geist） | Notion | Claude | Craft |
|---|---|---|---|---|---|
| 字型 | Inter Variable | Geist Sans | NotionInter＋Lyon Text（襯線） | 無襯線＋襯線＋等寬 | Inter＋Source Serif 4 |
| 最常用字級 | 13px(33)、12(24)、14(15) | 14px(49)、16(34)、13(25) | 14px(38)、16(12)、12(11) | 15px(.9375rem)、16、14 | 14–16，標題 24–42 |
| 行高 | 24／20／16px | 20px(44)、24(29)、32(19) | 1.2／1.5 | 1.6／1.5 | — |
| 字重 | 500 為主 | **450／500／550**（可變字型微調） | 400／500／600 | **480／500** | — |
| 圓角 | 8(40)、6(29)、4、12 | 6、12、16（material 文件） | 12(14)、3、8 | 8、12、16、pill | 6、8、16、20 |
| 底色（淺色） | #fff／#f8f8f8／#f4f4f4 | #fff／#fafafa | #fff／**#f6f5f4** | **#faf9f5** | **#fcf9f7** |
| 主文字 | #282a2f | #171717 | **#37352f** | #141413 | #030302 |
| 邊框 | #e9e8ea；半透明 **5%／8%** 黑；另有 0.5px 髮絲線 | 黑色 alpha **5%／8%／10%** | #e9e9e7；hover＝黑色 alpha token | 邊寬 .5／1／1.5／2px | — |
| 陰影 | — | **2%～6%** 多層疊加 | — | — | — |
| 毛玻璃 | blur 8／32px | — | blur 4／16px＋saturate 1.8 | — | — |
| 內文行寬 | — | — | — | `--text-width-body: 60ch`、prose 80ch | — |

Geist 的具體陰影（Measured，淺色）：`small = 0 2px 2px #0000000a`；`menu = 0 0 0 1px(邊框環) , 0 1px 1px #00000005, 0 4px 8px -4px #0000000a, 0 16px 24px -8px #0000000f`；`modal` 同型、更深一階；焦點環 `0 0 0 2px 背景色, 0 0 0 4px 藍`。

**Fact（官方文章）：**[Linear 改版說明](https://linear.app/now/how-we-redesigned-the-linear-ui)：色彩改用 LCH，「不再為每個主題定義 98 個變數，改定義三個：base、accent、contrast」；標題用 Inter Display、內文用 Inter；「限制鉻彩（chrome）使用量」來取得「更中性、更耐看」的外觀；目標是「減少視覺雜訊、維持對齊、提高層級與密度」。[Linear 毛玻璃文章](https://linear.app/blog/linear-liquid-glass)：刻意不做折射，因為「折射會讓密集的專業介面更難閱讀」；高對比模式下改用實線輪廓。

**Fact（官方文件）：**[Radix Colors](https://www.radix-ui.com/colors/docs/palette-composition/understanding-the-scale) 的 12 階語意：1–2 背景、3–5 元件底色（一般／hover／按下）、6–8 邊框（非互動／互動／強調與焦點）、9–10 實心底色、11–12 文字；第 11、12 階在第 2 階背景上保證 APCA Lc 60／Lc 90。[Carbon for AI](https://carbondesignsystem.com/guidelines/carbon-for-ai/)：AI 內容用專屬標籤與克制的光暈／漸層標示，「光擴散必須有限且細微，以確保可及的對比」。

## 4. 共識

三個互相獨立的頂級產品（Craft、Claude、Notion）收斂到同一組做法：

1. **暖白紙面**而非純白冷灰：Craft #fcf9f7、Claude #faf9f5、Notion #f6f5f4。
2. **無襯線做介面、襯線做展示**：Craft（Inter＋Source Serif 4）、Claude、Notion（Lyon Text）。
3. 邊框與 hover 用**文字色的低 alpha**（5%～10%）而不是另一個灰色：Linear、Geist、Notion 一致。10% 黑疊在白上是 #e9e9e8，與 Notion 實測邊框 #e9e9e7 相同。
4. 陰影極淡（2%～6%）、多層疊加，用「邊框環＋柔影」取代單一重陰影。
5. 控制項圓角 6～8px、容器 12px、彈窗 12～16px。
6. 可變字型的**細字重**（450／480／500／550）取代只有 400／700 的跳級。
7. 限制色彩：中性色為主、一個強調色。

Linear 與 Geist 屬另一支（冷色、單一無襯線、13px 密集），工藝一致但氣質是「工程工具」。

## 5. 繁體中文排版（排版標準與瀏覽器）

- **Fact（[W3C clreq，2026-02-02 Group Note](https://www.w3.org/TR/2026/DNOTE-clreq-20260202/)，已讀原文）：**「正文行長不應少於 10 字；橫排時正文行長不應超過 48 字。」另：漢字與西文字母、阿拉伯數字之間的字距或空白「不多於四分之一個漢字寬」。
- **Mapping：**行寬用 `em` 而不是 `ch`（`ch` 是半形 0 的寬，對中文失真）。48 字在 15px 是 720px、16px 是 768px。現況 JD 文字行寬約 55 字，超標。
- **Fact／Unknown（瀏覽器）：**[Chrome 官方文章](https://developer.chrome.com/blog/css-i18n-features)確認 `text-autospace` 的設計與「已有明確空白則不重複插入」；出貨版本只在第三方整理看到 Chrome 140，**未由官方 release notes 逐條確認**，實作時以瀏覽器實測為準。`text-spacing-trim` 目前僅 Chromium；Firefox、Safari 不支援，屬漸進增強，不依賴。
- **Fact：**[Fontsource](https://fontsource.org/fonts/noto-sans-tc/install) 提供 Noto Sans TC 可變字型（wght 軸，含 chinese-traditional 切片，開放授權，可自架）。
- **Unknown：**臺灣政府設計系統（TWDS）網域在本機解析失敗（DNS 查無），**沒有取得**其繁中字級規範，不引用。
- **Measured：**現況字型堆疊 `"Noto Sans TC", "Microsoft JhengHei", ...` 沒有載入任何網頁字型。畫面看起來是 Noto 是因為這台機器剛好安裝了它；沒安裝的 Windows 會落到微軟正黑體，只有 Regular／Bold，無法呈現 500／600 的層級。

## 6. 決定

**採用「暖紙編輯器」方向：Craft／Claude／Notion 家族的暖白紙面＋Linear／Geist 的介面工藝（alpha 髮絲線、狀態疊層、極淡多層陰影、token 結構）＋ clreq 的中文排版規則。**

理由（對照 §1 的畫面特性）：
- Caliburn 的主角是**長篇繁中文件**與**AI 顧問對話**。共識家族本來就是為「讀寫長文」設計的，且其中 Craft 有可驗證的正式獎項。
- Linear 的 13px 密集排版對中文太小；採它的**工藝**，不採它的**密度與冷色**。
- Awwwards 類沉浸式設計、GOV.UK 的外觀不適合，已在 §2 說明。
- 「顧問等級職務說明書」是產品北極星；暖紙面＋襯線感的層級讓成品像顧問交付的報告，而不是後台表單。

**不改：**品牌色（深青 `#23615b`）。換品牌不是這次的授權範圍。T09 既有的 Cloudscape 聊天模式、Carbon 的「AI 層」概念、右側來源面板仍保留，只換視覺實作。

**字型：**自架 `Inter Variable`（拉丁與數字）＋`Noto Sans TC Variable`（中文）。理由：可變字重 400／500／600 才能呈現層級；不依賴使用者電腦的字型；自架不對外連線，符合本機部署。

**襯線展示字：**Craft、Claude、Notion 都用，但中文襯線（Noto Serif TC）在 Windows 一般 DPI 下的小字渲染品質與檔案大小成本都高，本輪**不採用**，記為未來選項；層級先靠字級、字重、色階、留白建立。

## 7. 聊天室的對標（維護者指出聊天室「也很醜」後補查）

原本的訪談欄是「全部靠左、每則訊息都有標頭列、顧問訊息夾帶 `**` 與 `-` 原始標記」。這三點在主流聊天介面裡都找不到。補查的一手來源：

- **Fact（[Vercel AI Elements](https://github.com/vercel/ai-elements) 原始碼，Vercel 官方開源）：**`Message` 為 `max-w-[95%]`、使用者 `ml-auto`（靠右）；使用者訊息是帶底色的圓角氣泡（`px-4 py-3`），**助理訊息不加氣泡**；訊息之間 `gap-8`（32px）；有「捲到最新」的浮動圓鈕；過程紀錄（Reasoning）是靜音的可收合列，內文 `text-muted-foreground`。
- **Measured（[ChatGPT](https://chatgpt.com/) 公開 CSS）：**邊框為黑色 10%／5% alpha（`--border-default: #0000001a`、`--border-light: #0000000d`，與 Linear、Geist 同一套慣例）；輸入器陰影 `0 0 0 1px 4%, 0 2px 8px 4%, 0 4px 80px 8px 2.4%`；`--thread-component-gap: 24px`；圓角用到 20／24px；對所有訊息套用 `text-wrap: pretty`、標題 `balance`。
- **Fact（[Cloudscape 對話氣泡](https://cloudscape.design/patterns/genai/conversational-bubbles)、[生成式 AI 對話](https://cloudscape.design/patterns/genai/generative-AI-chat/)）：**使用者與 AI 的訊息必須有視覺區別；「專用的整頁介面」可左右交替但要限制氣泡寬度；輸入固定在底部、只有訊息記錄捲動；免責說明放在輸入框上方。
- **Mapping：**訪談欄是兩個窗格之一的專用介面，採主流做法：**員工靠右、帶底色氣泡（最寬 88%）；顧問靠左、不加氣泡；App 開場是置中的系統提示**；訊息間距 24px；輸入器是圓角卡片（外環 12%、兩層極淡陰影）；顧問處理中顯示三點跳動指示。每則的標頭只有說話者名稱：訪談序號是後端的正式順序，員工不需要看（維護者指示；參照的聊天介面 AI Elements、ChatGPT、Claude 也都沒有每則序號）。

**決定（顧問訊息格式化）：**顧問的訊息是模型產生的，常含 Markdown（`**粗體**`、`- 條列`）。T09 把「原文以轉義文字顯示」列為已知限制並標明需要決定。所有主流 AI 聊天介面都會格式化助理輸出，原樣顯示 `**` 是聊天室最明顯的醜點，所以**只對顧問訊息做安全的 Markdown 呈現**：原始 HTML 以可見文字顯示（react-markdown 預設跳脫，已實測）、連結不導覽並附網址、圖片不載入、標題降為粗體段落、保留軟換行。**不改變保存的文字**；**員工與 App 訊息、來源回查的原文仍逐字顯示**（既有測試以 `<img src=x onerror=…>` 釘住這點）。此決定只影響顧問訊息的呈現，隔離在 `ChatMarkdown` 一個元件，要退回只需改一行。維護者授權自行決定，仍請在驗收時確認是否接受。

## 8. 借用地圖：哪個站的哪個設計，用在哪裡

維護者的要求不是整站照抄，而是「這個站的 A 設計、那個站的 B 設計」拼起來。下表是**實際已經在 Caliburn 裡**的借用（右欄為證據層級），以及我這輪另外看過、決定借或不借的。

| 我們的畫面／元素 | 借自 | 借的是什麼 | 證據 |
|---|---|---|---|
| 聊天：員工靠右氣泡、顧問靠左不加氣泡 | Vercel AI Elements、ChatGPT | user `ml-auto`＋底色氣泡 `px-4 py-3`，assistant 純文字 | Fact（官方原始碼）、Measured |
| 聊天：訊息間距 24px、`text-wrap: pretty` | ChatGPT | `--thread-component-gap: 24px`；對所有訊息套 `pretty` | Measured |
| 聊天：輸入器卡片的外環＋近、遠兩層極淡陰影 | ChatGPT | 結構照 ChatGPT（實測 `0 0 0 1px 4%, 0 2px 8px 4%, 0 4px 80px 8px 2.4%`）；我們的外環提到 12%，否則白色底欄上不易找到輸入框 | Measured（結構）、Mapping（數值） |
| 聊天：過程紀錄收合列 | Vercel AI Elements（Reasoning） | 靜音、可展開、不搶正文 | Fact |
| 聊天：Markdown 格式化、輸入中指示 | 所有主流 AI 聊天 | 助理輸出格式化；處理中跳動點 | 通用做法（ChatGPT CSS 有 `pulse-dot`） |
| JD：一張紙面、區段靠留白與髮絲線、不用卡片 | Notion、Craft | 文件優先、無框線卡片 | Measured |
| 暖灰畫布 `#f6f5f4`、暖白紙面 | Notion（`#f6f5f4`）、Claude（`#faf9f5`）、Craft（`#fcf9f7`）、Lando Norris（文字 `#f4f4ed`） | 暖白而非冷灰 | Measured |
| JD：大標題 24px 對 12px 標籤的尺度反差 | Lando Norris（年度站 2025） | 同頁 70px 展示字對 13px 標籤，反差製造層級 | Measured（縮小到工具可用的比例） |
| JD：文字行寬上限 48em | W3C clreq、Claude（`--text-width-body: 60ch`） | 橫排正文每行不超過 48 字 | Fact |
| 邊框／hover 用墨色 alpha 6%／10%／18% | Linear、Vercel Geist、Notion、ChatGPT | 邊框是文字色的 5%–10% alpha，不是另一個灰 | Measured |
| 品牌色階以 OKLCH 推導 | Linear | 少數輸入產生整套主題（base／accent／contrast） | Fact（官方文章） |
| 語意色：淡底＋深字 | Radix Colors | 12 階語意與對比保證 | Fact |
| AI 候選層：靛藍淡底＋「候選」標籤 | Carbon for AI、Cloudscape | AI 內容有專屬標籤與克制的底色 | Fact |
| 多層極淡陰影（2%–6%）、圓角 6／8／12／16 | Vercel Geist | 邊框環＋柔影；material 圓角 | Measured、Fact |
| 焦點環：2px 外框＋2px 偏移 | Vercel Geist、WCAG 2.4.7 | 一律可見 | Measured |
| 毛玻璃章節導覽列（blur 12px＋saturate） | Notion、Linear、Apple materials | 只用在黏性列，內文不透明 | Measured、Fact |
| 字型：Inter＋Noto Sans TC 可變字型，字重 400／500／600 | Linear、Vercel、Notion、Craft（Inter 系）；Vercel／Claude 的細字重 | 可變字型取代 400／700 跳級 | Measured |
| 表單：標籤在欄位上方，說明文字在欄位下方、與欄位左緣對齊 | GOV.UK、Primer | 見 §9 | Fact（官方文件） |
| 檔案清單：整列單一大連結、hover 才顯示動作 | Linear 清單、Notion 資料庫 | 靜音列、單一目標 | Unknown（依產品觀察，未查到官方文件） |

**看過但不借：**
- **Awwwards 年度站的整站**（Lando Norris、Messenger、Igloo、Lusion）：沉浸式 WebGL 與滾動編舞，長時間讀寫會累；Messenger 與 Igloo 在無 GPU 的瀏覽器甚至載入不出來（我實際打開時是空白或載入畫面）。裝飾性的等高線背景紋理、霓虹強調色與缺角卡片也不借。
- **Apple Design Awards 2026**：得獎者多是消費 App 與遊戲；其中 Tide Guide 的圖表、NBA 的 Vision Pro 空間介面與我們無關。
- **Linear 的深色優先與 13px 密集排版**：中文太小；Stripe 的漸層與動態；中文襯線展示字（成本高，已記為未來選項）。
- **Linear／Notion／Vercel 的骨架載入**：沒有借。檔案清單原本就有骨架；JD 欄在本機 API 上數十毫秒內載入，載入文字不會停留。

**這輪另外補借（已實作並驗證，見[視覺改版證據](../../history.md#source-a75c36d876a672e0f607)）：**
1. **Apple Design Awards 2026「Inclusivity」類的做法**（Guitar Wiz：Dynamic Type、Increased Contrast、Differentiate Without Color）＋**Linear 毛玻璃文章**（「高對比模式下改用實線輪廓」）→ 網頁對應是 Windows 高對比模式的 `forced-colors: active`。我們把不少邊緣與狀態改成 box-shadow 外環和底色淡階，**該模式會移除這兩者**：用瀏覽器模擬量到輸入器、送出鈕、員工氣泡、目前章節標記與輸入聚焦環全部消失。補上實線邊框、系統色 `Highlight` 外框與底線後重測，12 項檢查全數通過。`prefers-contrast: more`（macOS／iOS「提高對比」）**沒有做**：Windows 的對比主題走 forced-colors，已涵蓋；日後要加，CSS 自己的邊框已集中成 token，但 MUI 內建元件的邊框色是 JS 常數，要另外處理，不是一行。
2. **Linear／Vercel 的減速曲線 `cubic-bezier(.32,.72,0,1)`**（兩家都用，實測）→ 來源側板滑入：200ms、淡入加 24px 位移，用 CSS 原生的 `@starting-style`。離開維持瞬間：內容在點擊當下卸載，空面板滑走反而顯得壞掉。減少動態偏好下縮為 1ms。

動態的實測（Measured）：狀態轉場時長集中在 120–200ms（Linear `.16s` 44 次、Vercel `.15s`／`.2s`、Notion `.15s`、Claude `.2s`）；緩動全是減速型（Stripe `.25,1,.5,1` 41 次、Linear `ease-out` 80 次與 `.32,.72,0,1`）。我們的 120／180ms 與 `0.2,0,0,1` 落在同一族。

## 9. 元件層級的參照（維護者要求「模仿被大家認可的設計，不要用自己的想法」後逐項補查）

前面 §3–§8 的實測偏向**視覺系統**（色彩、字型、邊框、陰影、聊天版面）。按鈕色彩、刪除確認、結構化新增／移除這類**元件**我原本只寫「通用做法」、沒有逐一查來源，其中幾處其實是沿用舊碼或我自己的想法。以下是補查後的對照；「Fact」是我這次讀到的官方文件原文，「未取得」是頁面讀不到（需登入、被擋或以腳本渲染），不當作已查證。

| 元件 | 參照與查到的事實 | Caliburn 現況 |
|---|---|---|
| **主版面：左聊天、右文件** | Anthropic Artifacts：「these Artifacts appear in a dedicated window alongside their conversation」，使用者可即時檢視與編輯（[官方公告](https://www.anthropic.com/news/claude-3-5-sonnet)）。OpenAI Canvas 頁面回 403，**未取得** | 左訪談、右 JD，人與 AI 編輯同一份 JD ✓ |
| **聊天輸入器** | Vercel AI Elements PromptInput：自動長高的 textarea；「Enter to submit, Shift+Enter for new line」；送出鈕是**純圖示**，圖示隨狀態改變；圓角邊框容器（[文件](https://elements.ai-sdk.dev/components/prompt-input)） | 自動長高 ✓；預設送出鈕改成圓形純圖示 ✓（無障礙名稱與 tooltip 仍是「送出訪談」）；「正在確認送出…」「重新確認原請求」兩個需要說明的狀態保留文字；**Enter 送出**（原本不送出，2026-10-05 改，見 §16） |
| **聊天訊息** | AI Elements Message：使用者訊息是 secondary 底色的扁平樣式，助理訊息 full-width、不加氣泡，有複製／重試等動作與 tooltip，文件未提頭像（[文件](https://elements.ai-sdk.dev/components/message)） | 員工靠右淡底氣泡、顧問靠左純文字 ✓；另有小頭像與說話者名稱一行（Cloudscape 對話氣泡也用頭像加名稱）；**不顯示訪談序號**（維護者指示） |
| **按鈕種類** | Primer：Primary「Never put more than one in a group of buttons」；Default 用於次要動作；Invisible 用於低調；Danger「Used sparingly for destructive actions, typically prompt a confirmation dialog」。Carbon：Secondary 是 set 裡的負面動作（Cancel／Back），Danger「for actions that could have destructive effects on the user's data (delete or remove)」，「Do not use two high-emphasis buttons in a button group」，純圖示鈕一律要 tooltip，Danger 不得做成純圖示。shadcn/ui：default、outline、secondary、ghost、destructive、link（[Primer](https://primer.style/product/components/button/)、[Carbon](https://carbondesignsystem.com/components/button/usage/)、[shadcn](https://ui.shadcn.com/docs/components/button)）。Atlassian、Apple HIG、Polaris 頁面**未取得** | 一組按鈕只有一個實心主按鈕 ✓；次要用外框、低調用文字 ✓；純圖示鈕都有 tooltip ✓。**改了：**原本「取消處理」「撤回」「移除」用琥珀色按鈕——上面三套系統都沒有琥珀色按鈕，破壞性動作用紅色。現在「取消處理」是一般外框鈕（Primer 的 Danger 是留給會跳確認的動作，取消處理沒有確認視窗），紅色只用在刪除與撤回的**確認鈕** |
| **對話框與刪除確認** | Primer Dialog：Header／Body／Footer，Footer 由左到右 Default（Cancel）→ Primary 或 Danger 在最右，尺寸 small／medium／large。shadcn AlertDialog：Cancel 在前、Action 在後，說明寫出後果（「This action cannot be undone」）。Cloudscape 刪除模式：標題「Delete [resource type]」、本文、後果放在資訊提示、按鈕 Cancel／Delete。NN/g：只在後果嚴重時用確認視窗、按鈕寫具體動作而不是 Yes／No、不要預設選 Yes、盡量提供 Undo（[Primer](https://primer.style/product/components/dialog/)、[shadcn](https://ui.shadcn.com/docs/components/alert-dialog)、[Cloudscape](https://cloudscape.design/patterns/resource-management/delete/delete-with-simple-confirmation/)、[NN/g](https://www.nngroup.com/articles/confirmation-dialog/)） | 標題、後果說明、「返回 JD」加確認鈕 ✓，按鈕寫具體動作（「確認刪除職責」）✓。**改了：**刪除確認鈕原本放在對話框**內容區**，其他對話框的動作都在 Footer；現在移到 Footer 最右並用紅色。沒有 Undo（需要後端支援，不在視覺改版範圍） |
| **表單欄位** | GOV.UK：標籤在輸入框上方、短句；提示在標籤與輸入框之間；多行回答用 Textarea。Primer FormControl：標籤在上、說明與驗證訊息在下（[GOV.UK](https://design-system.service.gov.uk/components/text-input/)、[Primer](https://primer.style/product/components/form-control/)） | 標籤在上、說明在下 ✓；**改了：**說明文字原本被 MUI 縮排 14px，現在與標籤和欄位左緣對齊 |
| **結構化新增／移除** | MoJ Design System「Add another」：每一項是欄位加一個 Remove 按鈕，另有「Add another」按鈕，**兩者都是 secondary 樣式**；Remove 的無障礙名稱帶項目編號（[官方頁面](https://design-patterns.service.justice.gov.uk/components/add-another/)） | 任務表單的成果／要求列：欄位＋「移除」＋「新增…」。**改了：**兩個都改成 secondary（外框）；移除鈕與欄位垂直置中（原本寫的 `mt: 26px` 因為被 MUI Stack 的子項邊距規則蓋掉，從未生效，改用 flex gap 後才真正對齊）；無障礙名稱帶編號 ✓ |
| **排序** | W3C APG 可重排 listbox：「Up」「Down」按鈕，快速鍵 Alt＋↑／Alt＋↓（[範例](https://www.w3.org/WAI/ARIA/apg/patterns/listbox/examples/listbox-rearrangeable/)） | 上移／下移圖示鈕，第一項與最後一項停用 ✓；快速鍵沒做 |
| **分段控制** | Primer SegmentedControl：「pick one choice from a linear set of closely related choices, and immediately apply that selection」（[文件](https://primer.style/product/components/segmented-control/)） | 「候選預覽／正式稿」✓ |
| **側邊面板** | shadcn Sheet：延伸自 Dialog，「complements the main content of the screen」，從邊緣滑入（[文件](https://ui.shadcn.com/docs/components/sheet)） | 來源面板從右側滑入 ✓（離開瞬間，因為內容隨點擊卸載） |
| **階層（職責→任務）** | Primer TreeView：「a hierarchical list of items that may have a parent-child relationship where children can be toggled into view by expanding or collapsing their parent item」，預設縮排巢狀項目（`flat` 才不縮排，「should only be used when the tree is used to display a flat list of items」）。Carbon Tree view：「nested heading levels that create a content hierarchy」「Branch nodes that can be expanded or collapsed to reveal or hide child nodes」，靠垂直的文字與圖示對齊把同組節點視覺上歸在一起。W3C APG Tree View：「Any item in the hierarchy may have child items, and items that have children may be expanded or collapsed to show or hide the children」（[Primer](https://primer.style/product/components/tree-view/)、[Carbon](https://carbondesignsystem.com/components/tree-view/usage/)、[APG](https://www.w3.org/WAI/ARIA/apg/patterns/treeview/)） | 職責是父層（18px 標題、任務數、可收合）、任務縮排一層（15px、可收合），同一個箭頭與行為 ✓。**刻意不同：**只借視覺階層與展開／收合，**沒有採 `role="tree"` 的鍵盤模型**——這是可編輯的文件，不是導覽樹；收合是 `aria-expanded` 的揭露按鈕。維護者指出「不好區分職責與任務」後調整 |
| **刪除圖示** | 維護者指定：沿用 App 內任務下「解除關聯」那個 ×（「所需技能的刪除 UI 不錯」）。Carbon：Danger 按鈕不得做成純圖示——所以 × 靜止是中性色、hover 才轉紅，真正的破壞性動作仍是確認對話框裡的紅色確認鈕 | 職責、任務、知識、技能、協作對象、條件的刪除一律 ×（外部先例不是依據，維護者的指定與 App 內一致才是；延伸到後四者是為了同頁一致） |
| **項目的 hover 動作** | Slack 訊息的浮動工具列、Gmail 列上的 hover 動作 | **Unknown**：依產品觀察，沒有查到官方文件；樣式是「帶邊框的浮動工具列」。只顯示指著的最內層項目的工具列（`:has()` 判斷）是我的取捨，**沒有外部先例**，由 e2e 守住 |

**刻意與參照不同的地方**（每項都有理由，不是疏漏）：
1. **（2026-10-05 已推翻，見 §16：改為 Enter 送出，並以輸入法組字判斷避開注音選字。）Enter 不送出。** 參照都是 Enter 送出、Shift＋Enter 換行。這裡的送出是「正式訪談」的起點，且使用者用注音等輸入法時 Enter 用來選字，必須另外處理輸入法組字狀態才不會誤送；這是行為決定，不是視覺，沿 T09 先不做。
2. **兩個狀態的送出鈕保留文字。**「重新確認原請求」是重送同一個命令，不是新送一次，圖示說不清楚。
3. **沒有「捲到最新」浮動鈕**（AI Elements 與 ChatGPT 有）。它需要輸入底欄高度與捲動狀態跨元件傳遞，成本大於價值；維護者也要求不要過度設計。
4. **沒有 Undo。** NN/g 建議提供 Undo；需要後端支援，不在這次視覺改版。

## 10. 編輯方式：整項一次改，還是逐欄就地改（已採用，2026-10-02）

維護者問：用「編輯」一次改整項，還是每欄各自改？並要求去找得獎設計裡類似的功能來模仿。**狀態：已採用並實作。**維護者看過本節的建議後回覆「依照設計獎網站做法」，即採用下方的混合式；實作與驗證見[視覺改版證據 §10](../../history.md#source-a75c36d876a672e0f607)，介面責任見[介面 §1.7](../../implementation/interface-and-delivery.md#17-逐欄就地編輯)。下面的比較與「Mapping」是研究當時的判斷，那時的現況是「✎ 開對話框、整項一次改」。

**獎項能給的先例很少。**網頁設計獎的得獎站是行銷與展示站，幾乎沒有「編輯既有資料」的介面（§2）；有編輯器的得獎作品是 Apple Design Awards 的 App，這裡能查到的是 Things（官網自述「Honored twice with the prestigious Apple Design Award」；Apple 官方得獎頁沒取得，年份未驗）。其餘先例來自設計系統與大型產品的官方文件。

| 來源（2026-10-02 讀官方頁面） | 它怎麼做（引號內是原文） | 逐欄／整項 |
|---|---|---|
| [Primer：Saving](https://primer.style/product/ui-patterns/saving/)（GitHub） | 「Avoid mixing explicit and automatic save patterns on a single page with multiple forms, and never mix save patterns in a single form.」文字輸入這類 declarative 控制用明確的儲存／取消，自動儲存留給開關、分段控制這類 imperative 控制（大意）。「Allow only one edit mode activated at a time if you're designing a page with content that can be edited separately (such as an issue title).」「If there is an error saving the data, the user's data should be preserved in the form and they should be given feedback about the failure.」 | 逐欄、明確儲存、一次只開一個、失敗保留草稿 |
| [GitHub Docs：編輯 issue](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/editing-an-issue) | 標題：標題右側點 Edit → 輸入 → Save；內文：右上 ⋯ 選單 → Edit → Save。兩者各自儲存、各自記入時間軸 | 逐欄、明確儲存 |
| [Atlassian：Inline edit](https://atlassian.design/components/inline-edit/usage) | 「Use inline edit on screens where information needs to be updated often, such as a work item page.」「Use this instead of a form when you have information that may already exist and can be edited.」儲存／取消「at the end of the field. For example, at the bottom right in a left-to-right reading order」；「use return to save and esc to cancel」；較大的文字區用 `keepEditViewOpenOnBlur`，避免失焦時誤丟資料；「enough visual affordance that sighted people recognise them as editable」 | 逐欄、明確儲存 |
| [Cloudscape：Inline edit](https://cloudscape.design/patterns/resource-management/edit/inline-edit/) | 「Use inline edit on views where information needs to be updated often, or when you want a user to edit a resource property across multiple resources.」可編輯值有編輯圖示（hover 時才顯示）；點下後「the value changes into an input, and a dismiss and confirm icon appear」；「Always allow users to save or discard changes」。一次改多個屬性改用[頁面編輯](https://cloudscape.design/patterns/resource-management/edit/page-edit/)（「editing its properties and configuration in bulk」）。注意此模式寫的是**表格儲存格**，借的是原則 | 常改的單一屬性＝逐欄；一次改多項＝整頁 |
| [PatternFly：Inline edit](https://www.patternfly.org/components/inline-edit/design-guidelines) | 欄位型：筆形鈕一次切換一個欄位，用於對個別欄位的小調整；整區型：「you want to allow users to edit a larger area with many editable elements all at once」；✓ 存、✕ 取消。不適用於「The editing is the primary function of the view. For example, in an edit modal.」 | 小調整＝逐欄；一大片同時改＝整區 |
| [Linear 更新日誌：Inline editing](https://linear.app/changelog/2022-06-09-inline-editing) | 標題與描述「directly on the issue page」點選編輯，「Your changes are saved automatically」；動機「Editing and creating issues should be as fast and seamless as possible」；同則日誌另提「modal-based creation tool」與全螢幕建立畫面——**建立仍走獨立的流程** | 逐欄、自動儲存；建立另走對話框 |
| [GOV.UK：Check answers](https://design-system.service.gov.uk/patterns/check-answers/) | 每一列一個「Change」連結（含視覺隱藏的說明文字）；點了回到那一題、預填原答案，改完直接回到摘要頁 | 逐題 |
| [Things 3 官網](https://culturedcode.com/things/features/)（Apple Design Award，見上） | 「When you open a to-do, it smoothly transforms into a clear white piece of paper, ready for your thoughts.」標籤、清單、開始日、期限「are neatly tucked away in the corner until you need them」。[Mac 3.12 發行說明（2020-03-10）](https://culturedcode.com/things/support/articles/1100684/)：「You can now edit the Tags or Deadlines of collapsed to-dos (even multiple to-dos at once) by hitting Cmd+Shift+T or D.」 | **兩者並存**：整項在原處展開編輯（不是 modal），另可不展開直接改單一欄位 |
| [NN/g：Modal & nonmodal dialogs](https://www.nngroup.com/articles/modal-nonmodal-dialog/) | modal 的適用：「important warnings, as a way to prevent or correct critical errors」、繼續流程必要的資訊、把複雜流程拆成較簡單的步驟；不適用：「nonessential information that is not related to the current user flow」，以及決策「require additional sources of information unavailable in the modal」。nonmodal 讓使用者「continue working with this window open」並參考其他內容 | 改既有的一小段文字不在 modal 的適用清單上；編輯時需要對照左邊訪談，屬於「需要視窗外資訊」 |

**Fact 的共同結論：**這些系統改**既有**內容都不用 modal。常改的小調整是逐欄就地改（GitHub、Atlassian、Cloudscape、PatternFly、Linear，Things 也加了）；整項或整區一次改留給**新增**與**一次改很多欄**（Cloudscape 頁面編輯、PatternFly 整區、Linear 的建立畫面）。保存方式分兩派：Primer／Atlassian／Cloudscape／PatternFly 是明確的儲存與取消，Linear 與 Things 是自動儲存。

**Mapping（Caliburn；以下是讀了現行程式後的判斷，不是外部來源）：**
- **現行的痛點。**改一個錯字要「hover → 點 ✎ → 等對話框 → 找到欄位 → 儲存」；對話框蓋住左邊的訪談與來源面板，改的時候看不到對照內容；「工作成果／工作要求」的單項文字沒有自己的編輯入口（`TaskDetails` 只有上移、下移），只能開整個任務對話框。
- **契約已允許逐欄。**`WorkIntent` 本來就是**一筆**變更，`commandFor` 補上 `command_id` 與 `expected_revision_id`；任務表單只送有改的欄位（`set_field`、`revise_detail`）；上移、下移、刪除、解除關聯已經是不經對話框的單筆命令（`submitIntent`）。待確認與原命令重送（`useWorkCommand`）在**編輯器層級**（每檔每分頁一筆，存在 `sessionStorage`），不在對話框裡，所以逐欄儲存走同一條路，不需要第二套暫存或後端變更。
- **不能照抄的：**Linear 與 Things 是自動儲存。Caliburn 的命令模型是「先保留原命令、再送出、結果不明時以原命令重新確認」；每次停頓就自動送出會製造大量待確認狀態，與 Primer「同一頁不混用兩種保存方式」也不合。所以跟 Primer／Atlassian／Cloudscape／PatternFly 一樣用**明確的 ✓／✕**。
- **要付的成本：**①一個共用的就地編輯元件：唯讀檢視與輸入檢視切換、✓／✕、Enter 存（多行用 Ctrl／⌘＋Enter）、Esc 取消、多行文字失焦不關閉；失敗要保留草稿並**在原處**顯示訊息與「重新確認」，因為現行的訊息列在職責與任務區塊頂端，長 JD 時不在畫面內。②開啟時固定基底修訂與原文字，背景更新不替換（與[介面設計 §1.2](../../implementation/interface-and-delivery.md)現行規則相同）。③「任務名稱或工作內容至少填一項」要對照另一欄的現值。④一次改三欄變成三筆命令，各自推進 `expected_revision_id`；命令進行中全頁暫時不可再改（現行鎖）。⑤ JD 被 Turn 佔用時，已開啟的草稿要保留但不能儲存（現行對話框的行為）。⑥單元與 e2e 測試。範圍估計：一個共用元件、約六個呈現元件的呼叫點（職責、任務、成果／要求、知識／技能、協作對象、條件），**不動後端**。
- **仍留在對話框：**新增（`create_*` 一次帶多欄，是原子命令）、把任務搬到別的職責（選單，可同次附帶文字調整）、一次增刪多筆成果／要求、更正條件分類。

**決定：混合式——既有文字逐欄就地改，新增與跨欄調整留對話框。**理由：被查證的系統都這樣分工；JD 多半由 AI 起草、人只做小修正，正是「小調整」；契約已支援單筆命令。**不做**自動儲存、不加表單框架或通用引擎、不加拖曳。只做文字欄，用同一個元件；✎ 先保留為「完整編輯」（Things 也是兩種並存），之後視使用再決定是否移除（後來依 §11 拿掉）。

**實際做的，與上面提案不同之處（工程取捨，維護者沒被問到）：**①一次就接上全部既有文字欄（職責、任務、成果／要求、知識／技能、協作對象、條件），因為它們共用同一個元件與同一條命令路徑，分批沒有省到事；JD 基本資料（獨立的 profile 命令）留到下一刀。②可編輯提示用 hover 底色、鍵盤聚焦外框與游標，沒有每欄一個鉛筆圖示（Cloudscape 的 hover 圖示會與右上角工具列、來源徽章搶位；觸控沒有 hover，但點文字仍可開，✎ 常駐）。③當時沒有加「點文字即可修改」的說明列（§11 拿掉 ✎ 後加了，只對沒有 hover 的裝置顯示）。④✎ 當時保留；後來依 §11 拿掉。⑤編輯期間其他編輯控制項暫停（Primer 的「一次只開一個」，加上編輯器固定修訂的實際需要）。

**Unknown：**Atlassian 的 `atlassian.design/patterns/inline-edit` 頁抓到空白（改用 `/components/inline-edit/usage` 取得）；Apple 官方 2017 得獎頁沒有取得（只有 2026 年資料），Things 的得獎年份只有官網自述；Linear 更新日誌沒寫 Enter／Esc 行為；Notion、Figma 沒有逐一讀官方文件，不列入；Cloudscape 的模式是表格儲存格，用在文件式內容是類推。

## 11. ✎（整項編輯）還需要嗎？（已採用，2026-10-02）

維護者在就地編輯上線後問：「✎ 這功能會需要嗎？看看那些設計好的網站會有這功能嗎？」**狀態：已採用並實作。**維護者看過下面的建議後回覆「好，就依照設計獎的網頁去做；多多參考，把好的學起來，每個設計獎網頁好看的地方都不一樣」，所以兩步一起做、也加了觸控說明行；實作與驗證見[視覺改版證據 §11](../../history.md#source-a75c36d876a672e0f607)，介面責任見[介面 §1.3](../../implementation/interface-and-delivery.md#13-職責與任務的人工編輯)與 §1.7。以下的比較與建議是動手前的研究。

**先看 ✎ 現在還剩什麼用途**（讀 `AreaFields`、`TaskFields`、`CapabilityFields`、`CollaboratorFields`、`ConditionFields`）：

| 項目 | ✎ 表單裡的欄位 | 就地編輯已涵蓋 | ✎ 獨有的功能 |
|---|---|---|---|
| 職責 | 名稱、範圍 | 全部 | **無** |
| 知識／技能 | 名稱、說明 | 全部 | **無**（表單多一句「修改共用定義後，所有使用此項的任務都會顯示新版」） |
| 協作對象 | 名稱、範圍 | 全部 | **無** |
| 工作條件 | 分類、內容 | 內容 | 更正分類 |
| 任務 | 所屬職責、名稱、工作內容、成果列、要求列 | 名稱、工作內容、每一項成果與要求的文字 | 搬到別的職責；新增與移除成果、要求；一次改多欄只留下一個修訂 |

也就是說，五種項目裡有三種的 ✎ 已經完全重複；剩下兩種只有四件事只有它做得到。

**先例（Fact，2026-10-02 讀取）：**

| 來源 | 有沒有「整項編輯」入口 | 結構性操作（搬移等）放哪裡 |
|---|---|---|
| [Jira Cloud](https://community.atlassian.com/forums/Jira-Service-Management-articles/New-issue-view-for-Jira-Service-Desk/ba-p/1222800)（Atlassian 社群公告；**頁面讀不到內文，下列是搜尋摘要，未逐字核對**） | 沒有：「the new editor has no edit button. Simply hover over a field you'd like to edit and select it」，✓ 存、✕ 取消 | 「More actions（•••）→ Move」（Atlassian 支援文件的搜尋摘要，同樣未逐字核對） |
| [GitHub](https://docs.github.com/en/issues/tracking-your-work-with-issues/using-issues/editing-an-issue) | 沒有整項編輯：標題旁一個 Edit、描述各有 ⋯ → Edit，各自儲存 | 「In the right sidebar, click **Transfer issue**」（[文件](https://docs.github.com/en/issues/tracking-your-work-with-issues/administering-issues/transferring-an-issue-to-another-repository)） |
| [Linear](https://linear.app/changelog/2022-06-09-inline-editing) | 標題與描述「directly on the issue page」點選編輯；建立另走獨立畫面 | 本次沒有查到官方文字，未列 |
| [Things](https://culturedcode.com/things/support/articles/9651894/) | 沒有表單：項目在原處展開直接改（見 §10） | Move 對話框、⇧⌘M、右鍵選單、拖放 |
| [Cloudscape 頁面編輯](https://cloudscape.design/patterns/resource-management/edit/page-edit/) | **有**，但用於「editing its properties and configuration in bulk」（成批屬性）；入口是頁面或容器上的 Edit 按鈕，容器的會開 modal。單一屬性用 inline edit | — |
| [Google Calendar](https://support.google.com/calendar/answer/37115) | 有：「Click an event and then Edit」。彈出視窗只是**摘要**，所以才需要另一個編輯入口（這是我的判讀，文件沒這樣寫） | — |
| [Trello](https://support.atlassian.com/trello/docs/adding-labels-to-cards/) | 有：卡片**正面**懸停出現鉛筆，開快速選單（「hover over the card and click the pencil icon, then choose Edit Labels」）。卡片正面只是摘要，所以需要快速選單（同樣是我的判讀） | 快速選單與卡片背面 |
| [NN/g 十大啟發](https://www.nngroup.com/articles/ten-usability-heuristics/) | 「Aesthetic and minimalist design：Interfaces should not contain information that is irrelevant or rarely needed.」 | — |

**Fact 的共同結論：**「整項編輯」入口出現在兩種情況：①項目只顯示**摘要**，欄位不能就地改（Google Calendar 的彈出視窗、Trello 的卡片正面、表格列）；②要**成批**改很多屬性（Cloudscape 頁面編輯）。**項目已完整展開、每個欄位都能就地改**的產品，在我讀到的官方文字裡沒有看到這個入口（Jira 新版明說沒有 Edit 按鈕；GitHub 只有各欄的 Edit；Things 沒有表單；Linear 的更新日誌只說標題與描述直接在頁面編輯，沒提整項編輯）。搬移、轉移這類少用的結構性操作則放在 ⋯ 選單、側欄或 Move 對話框，要選的是「搬去哪」，不是「再開一次整個表單」。**這是依我讀到的文字得出的結論，不是「這些產品一定沒有」的證明。**

**Mapping（Caliburn）：**我們的項目是完整展開的，每段文字都能點了就改，職責、知識／技能、協作對象一共只有兩段文字，不是「成批屬性」。所以 ✎ 的位置接近上面第二類以外的情況，**多數不需要**。唯一要認真處理的是那四件事要有新家，不然拿掉 ✎ 會少功能：

| ✎ 獨有的功能 | 先例做法 | Caliburn 的新家 |
|---|---|---|
| 搬任務到別的職責 | Jira「Move」、Things「Move 對話框」、GitHub 側欄「Transfer」 | 項目工具列的 ⋯ 選單：「移到…」列出職責與「未歸屬任務」，選了就送出單筆 `move_task` |
| 更正條件分類 | 同上（是另一種「搬到別的組」） | 同一個「移到…」選單，列出五種分類 |
| 新增成果／要求 | MoJ「Add another」、Things 清單：在清單末端就地新增 | 每組清單下一個「新增工作成果」「新增工作要求」文字鈕（與「新增任務」同款），按了在清單末端開一個空的就地編輯器，送 `add_detail` |
| 移除成果／要求 | MoJ「Remove」、GOV.UK 每列的刪除 | 每一項的工具列加 ×（與其他刪除同一個記號與確認對話框），送 `remove_detail` |

**建議（候選）：拿掉 ✎，分兩步：**
1. **現在就能拿**：職責、知識／技能、協作對象的 ✎（就地編輯已全部涵蓋，不損失任何功能）。
2. **補上新家後再拿**：任務與條件的 ✎。完成後「編輯」的所有表單分支都可以刪（`WorkEditing` 只剩新增），對話框只負責**新增**（與 Linear 的做法一致），程式反而變少。

**拿掉 ✎ 要注意的代價：**①**觸控沒有 hover，目前 ✎ 是唯一常駐的「可以改」提示**，拿掉後要補一行說明（Atlassian：「enough visual affordance that sighted people recognise them as editable」），例如 JD 標頭下的「點任何文字即可直接修改」。②表單裡每個欄位下的**填寫指引**（例如「描述實際做什麼、如何完成及適用情況。未知可留空」）目前只在表單出現；就地編輯器沒有，若要保留，可把同一句放在編輯器欄位下方。③知識／技能的那句「修改共用定義後，所有使用此項的任務都會顯示新版」會消失；目前每個知識／技能下方已列出「使用此項的任務」，可視需要在就地編輯器加一行提示。④一次改多欄只留一個修訂的能力沒有了（改三欄是三筆命令），這是 §10 已接受的取捨。

**實際做的（借了誰的什麼，以及與提案不同之處）：**

| 做了什麼 | 借自 | 為什麼這樣取 |
|---|---|---|
| 移除五種項目的 ✎ | Jira 新版（no edit button）、GitHub（只有各欄的 Edit） | 就地編輯上線後，✎ 對職責、知識／技能、協作對象完全重複 |
| 任務與條件的「移到…」：一個圖示鈕開單選選單，目前所在處打勾，選了就送；選單有一行淡色標題 | Primer ActionMenu（單選、勾選、選單內不放 × 以免與勾選衝突）、Things 的 Move（目的地清單含「未歸屬」）、Jira 的 More actions → Move | **一個專用圖示，不是 ⋯ 總選單**：只有一件事可做；Carbon 的 overflow menu 是給「空間不夠、選項多個」的，且破壞性動作要放進選單下方並分隔，而我們的 × 要保持一鍵可見（維護者指定） |
| 成果／要求的「+」放在清單標籤旁，只在指著清單時浮現（空清單與觸控常駐），按了在清單末端開空的就地編輯器 | Notion 指著區塊才浮現的「+」（Notion 說明文件）；Linear 的 sub-issues 標題列「+」（依產品觀察，**未查到官方文字**） | **一開始做成清單下方的一列「新增…」鈕，量測發現隱形時仍佔高度，每份清單多出約 30px 空白，放大看很醜**，改放標籤旁並用負邊距讓整列仍只有一行高；閒置畫面逐像素與改版前相同 |
| 每項 × 刪除成果／要求，先確認 | MoJ「Add another」的每列「Remove」；確認沿用本 App 其他刪除的對話框 | 沒有 Undo，所以保守；GOV.UK／MoJ 的移除作用在尚未送出的草稿，Things 有 Undo，這兩者我們都沒有 |
| 沒有 hover 的指標，JD 標題下多一行「點任何文字即可直接修改」 | Atlassian：就地編輯需要看得見的提示 | ✎ 是觸控上唯一常駐的「可以改」提示；用 CSS 的 `hover: none`／`pointer: coarse` 只對這些裝置顯示，不為滑鼠加雜訊，也不需要儲存「已看過」的狀態 |
| 知識／技能區塊說明列加「修改定義，所有使用它的任務都會顯示新版」 | 原本在 ✎ 表單裡的那句 | 放在區塊說明最自然，常駐且不打擾；表單裡每個欄位下的**填寫指引**仍只在新增表單出現，就地編輯器沒有加 |
| 搬移選單開著時，工具列保持顯示 | 沒有外部先例，是我的取捨 | 工具列原本只在指著時顯示，選單是浮層、不在項目內，指標一移進選單工具列就消失，選單像飄在空中 |

與提案不同之處：①兩步一起做；②「+」放標籤旁（上表）；③沒有把「搬到別的職責同次改文字」搬過來——想改文字就搬完再改；④`WorkEditDialog` 改名 `WorkDialog`、`WorkEditing` 改名 `WorkDialogContent`，因為它不再編輯；比對明細變更的 `task-draft` 整個刪除（只有舊表單用）。**沒做：**JD 基本資料四欄仍是「編輯基本資料」按鈕開表單（獨立的 profile 命令）。（2026-10-03 已做，見 §14.1。）

## 12. 限制

- 數值來自**行銷站公開 CSS**，非登入後產品；各站的實際產品 token 可能不同。
- Linear、Vercel、Notion、Claude 沒有可驗證的正式獎項（見 §2）；本頁稱「業界標竿」。
- CSSDA／FWA／Red Dot 2026 名單、TWDS、Apple HIG 的文字級數值頁、Material 3 狀態疊層頁（內文未取得）都**沒有取得**，未引用。
- `text-autospace` 出貨版本以實測為準，不以第三方整理為準。
- 聊天輸入器靜止時的外環是 12% 墨色，對白底約 1.3:1（沿 ChatGPT 的柔邊做法）；聚焦時是 1.5px 品牌色環（超過 6:1）。若要求元件邊界一律 3:1（WCAG 1.4.11），需改用 `--cb-border-control`，外觀會變得像一般表單欄位。這是取捨，不是已達標。
- 視覺判斷（好不好看）最終由維護者在自己的螢幕上看；這份紀錄只保證選型有依據、數值有來源、對比度有計算。

## 13. 來源面板、編輯動作鈕與推理摘要區塊的先例對照（2026-10-03）

維護者說「引用打開介面很醜」「編輯的取消、儲存也是很醜」，並再次要求聊天室對話框「多多學習模仿設計獎」。這一節記查到的先例；實作與驗證見[視覺改版證據 §12](../../history.md#source-a75c36d876a672e0f607)。表中引號內的英文取自網頁擷取工具回傳的摘要，沒有逐字比對原頁；要引用請以官方頁面為準。

### 13.1 設計獎裡有沒有可借的對話或引用介面

**沒有。**Apple Design Awards 2026 的得獎者是 grug（Delight）、Guitar Wiz（Inclusivity）、NBA: Live Games & Scores（Innovation）、Moonlitt（Interaction）、News in Depth（Social Impact）、Tide Guide（Visuals）與遊戲，沒有對話或 AI 助理類的 App（名單由新聞報導與 Apple 新聞稿的搜尋結果交叉；官方頁面仍讀不到逐項評語）。搜尋「近年的設計獎＋AI 對話介面」只找到 2020 年 iF 的 Samsung Card 聊天機器人新聞稿與 Awwwards 的靈感收藏頁（收藏，不是獎項）。結論與 §2、§10 相同：**獎項不能直接當對話框或引用面板的範本，可借的先例來自設計系統的官方文件**。

### 13.2 編輯的取消／儲存

| 先例 | 內容 | 結論 |
|---|---|---|
| [Atlassian inline edit](https://atlassian.design/components/inline-edit/usage) | 編輯態在欄位右下角顯示打勾與叉叉兩顆圖示鈕；「use return to save and esc to cancel」；按鈕盡量保持可見，大文字區可選「失焦不關閉」 | 採用：圖示鈕、右下、先儲存後取消、提示標明鍵 |
| [PatternFly inline edit](https://www.patternfly.org/components/inline-edit/design-guidelines) | check 儲存、times 取消；開始修改後 check 轉品牌色以提高儲存的可見度 | 採用：儲存鈕用品牌色實心 |
| [Cloudscape inline edit](https://cloudscape.design/patterns/resource-management/edit/inline-edit/) | 選取可編輯值後「a dismiss and confirm icon appear」；送出後出現成功圖示 | 同上；沒查到鍵盤快速鍵、aria 規範（頁面沒寫） |
| [Primer saving](https://primer.style/product/ui-patterns/saving/) | 文字鈕「Save／Cancel」：取消用次要外觀；內聯編輯時按鈕緊鄰輸入框；不要停用或隱藏儲存鈕；一頁一次只開一個編輯 | 取其「緊鄰欄位」「次要＋主要」「不停用儲存」；對話框的取消鈕採用次要外觀 |

**刻意不同：**三家用圖示鈕、Primer 用文字鈕，這裡採圖示鈕（多數），並補提示文字與觸控放大，無障礙名稱仍是文字。若維護者覺得文字更清楚，可退回 Primer 做法（只改 `InlineEditor`）。

### 13.3 來源面板

| 先例 | 內容 | 用在哪 |
|---|---|---|
| [Fluent 2 Drawer](https://fluent2.microsoft.design/components/web/react/core/drawer/usage) | 標頭含標題、可選的關閉鈕與「top-level quick actions, like back or refresh」；overlay 抽屜會蓋住主畫面、inline 抽屜與主畫面並排；多步流程限兩到三步 | 標頭：返回、重新讀取、關閉皆為圖示鈕；一層下鑽。**不同**：沿用原本的覆蓋式（維護者先前選「文件仍在視野內」），沒改成並排 |
| [Primer Dialog](https://primer.style/product/components/dialog/) | 標題、較淡的副標、右上角 X；有靠右的 side sheet 變體；底部按鈕 Cancel（default）、danger、primary | 標頭結構；對話框按鈕的主次 |
| [Primer ActionList](https://primer.style/product/components/action-list/) | leading visual、label、description（inline／block）、trailing visual、trailing action；group heading；selected／active 狀態 | 列表的列：前置圖示（訪談／文件）、整列可點、尾端箭頭、待核對時標籤下方的原因與次要動作「查看差異」 |
| [Atlassian Lozenge](https://atlassian.design/components/lozenge/usage) | 「prominent, compact label」，用語意色；「rely on color alone without clear labels」是不該做的事 | 待核對原因的標籤維持有字的小標籤，不只靠黃色 |
| GitHub 的 diff 檢視（文件為較舊版企業版頁面，由搜尋摘要確認）與 [Primer primitives](https://unpkg.com/@primer/primitives/dist/css/functional/themes/light.css) 的 `--diffBlob-*` | 新增綠色加 +、移除紅色加 −；token：additionLine＝success-muted、deletionLine＝danger-muted、hunkLine＝accent-muted、word 層另有較深的底 | 差異逐行上色並保留記號；用本專案自己的語意色（`--cb-ok-soft`、`--cb-danger-soft`），不複製 GitHub 的色值；**沒做** word 層（行內逐字高亮） |
| [Cloudscape artifact previews](https://cloudscape.design/gen-ai/patterns/artifact-previews/) | AI 產物的「canvas preview」在相鄰面板，產物成為主要焦點，並與對話的動作清楚分開 | 佐證「來源在旁邊的面板看，而不是塞進對話」 |

**沒取得：**Material 3 的 side sheet 指引頁（網頁由腳本渲染，工具只讀到標題）；ChatGPT、Perplexity、Claude 的引用面板沒有官方設計文件可讀，只能靠實際畫面觀察，**沒有拿它們當依據**。

### 13.4 推理摘要區塊：已接線的畫面與先例的對照

推理摘要的前端接線由另一工作階段完成（見[串流證據](../../history.md#source-9b7ba33984fa2002fb60)）。我沒有改它；這裡只拿它對照我查到的先例，作為之後調整的依據。

| 先例 | 內容 | 已接線的畫面 |
|---|---|---|
| [Cloudscape Thinking](https://cloudscape.design/gen-ai/patterns/thinking/) | 可展開區塊；聊天介面預設收合（回覆才是主要內容），在程式編輯器、儀表板這類要就地檢視推理的情境可預設展開；進行中標籤如「Thinking...」，完成後「Thought for 14s」（時間可選）；內容依時間順序，完成後不再改；**不要用內容取代標籤（會閃爍）**；不要拿來取代一般載入、不要顯示執行步驟 | 標籤固定「推理摘要」，內容在區塊內增長，標籤不變 ✓；不顯示耗時（沒有可靠的時間資料）✓；生成中預設展開、完成後收合——**與 Cloudscape 的聊天預設相反**，原因是需求就是「生成期間可串流查看」，且顧問一輪可達數分鐘 |
| [AI Elements Reasoning](https://elements.ai-sdk.dev/components/reasoning) | 串流時自動展開並有脈動動畫、結束後自動收合，使用者可手動切換；標題「Thinking...」→「Thought for N seconds」；內容以 Markdown 渲染 | 同樣「生成中展開、完成後收合」✓；內容用安全 Markdown ✓ |
| [Claude 說明文件](https://support.claude.com/en/articles/10574485-using-extended-thinking) | 有計時的「Thinking」指示，回覆上方有可展開的「Thinking」區；內容是**思考過程的摘要**；[API 文件](https://platform.claude.com/docs/en/build-with-claude/thinking)明說回傳的是摘要而非原始思維鏈 | 命名「推理摘要」、不稱完整思考 ✓；**位置不同**：先例放在回覆上方，這裡歷史回答的「處理紀錄」放在回覆下方（同一入口也裝著「JD 操作」；這是我對現況的解讀，文件沒有寫明理由） |
| [Gemini API thinking](https://ai.google.dev/gemini-api/docs/thinking) | 思考摘要不是原始思考；程式「always handle thought blocks where summary is empty or absent」 | 空摘要不補寫虛構內容 ✓ |

ChatGPT 的「Thought for N seconds」介面只找到第三方描述，沒有官方設計文件，**不當依據**。

### 13.5 這一輪看起來可以再改、但沒做的

- （2026-10-03 已做，見 §14.3。）聊天室「回到最新訊息」鈕（AI Elements 的 `ConversationScrollButton` 有此元件）：目前使用者往上讀時，新內容不會把畫面拉走（這點已對），但沒有一個回到底部的按鈕。
- 處理中的輸入區把狀態列、暫停／取消鈕與說明文字分成三塊，約 140px 高；ChatGPT、Claude 的產品畫面是輸入器上的一顆停止鈕（只是畫面觀察，沒有官方設計文件）。因為這裡有暫停、取消兩種不同後果，沒有直接比照，是否合併要由維護者決定。
- 歷史回答的「處理紀錄」放回覆下方（先例放上方）：要移到上方，需要先把「JD 操作」從同一個入口分出去，那是產品決定。

## 14. 基本資料、新增職責、區塊收合與聊天室（2026-10-03）

維護者說「編輯基本資料需要改、新增職責需要改、工作條件與責任邊界／主要協作對象／所需技能／所需知識看要不要可以收合、聊天室可以改、UI 可以美化」，之後補「未歸屬任務要可以收合」「JD 職責與任務要可以收合，包含未歸屬任務」，並再次要求多參考、學習。實作與驗證見[視覺改版證據 §13](../../history.md#source-a75c36d876a672e0f607)。表中引號內的英文取自網頁擷取工具回傳的摘要，沒有逐字比對原頁；要引用請以官方頁面為準。

### 14.1 基本資料四欄與「新增職責」

沒有新的外部先例，沿用 §10、§11 已讀的官方頁面：改既有文字用逐欄就地編輯（Primer、Atlassian、Cloudscape、PatternFly、GitHub 的標題），在清單末端新增項目就地輸入（Things 的清單；§11 的「新增成果／要求」同樣做法）。§11 結尾寫的「沒做：JD 基本資料四欄仍是按鈕開表單」就是這次補上的。

- **Mapping（讀了現行程式後的判斷，不是外部來源）：**基本資料與集合是兩條命令，卻寫同一個修訂。Primer 的「一頁一次只開一個編輯」在這裡不只是慣例，也是正確性需要：開著的編輯器固定了修訂，另一邊的任何寫入都會讓它的儲存衝突。所以排他要跨基本資料與集合，而不是各管各的。
- **取捨（沒有外部先例）：**新增職責只送名稱（範圍留空），範圍之後在原處補。理由是新增列只有一個欄位，才能與「+ 新增成果」共用同一個編輯器；代價是要補範圍得再點一次。

### 14.2 區塊收合

| 先例（2026-10-03 讀官方頁面） | 內容 | 用在哪 |
|---|---|---|
| [GOV.UK 手風琴](https://design-system.service.gov.uk/components/accordion/) | 「Do not use an accordion for content that all users need to see.」「An accordion will usually start with all sections hidden.」但可設定為「start and stay open」；預設用 session storage 記住展開的區段，可關閉 | **預設展開**：JD 的內容是每位讀者都要看的，所以不採「預設收合」，由讀者自己收。**沒有採用**記住狀態：重新整理後全部回到展開（可逆：每區一個 session 鍵） |

**沒有為下列各點查官方頁面，只當通用做法或我的取捨：**標題旁的箭頭、收合後只留標題與項數（Notion 的 toggle 與 GOV.UK 手風琴都是這個形狀，但本次沒有逐頁核對）；章節導覽點到已收合的區塊時先展開它再捲過去（我的取捨）；整段「職責與任務」收合時只收職責與未歸屬任務，下面四個輔助區塊維持各自收合（依導覽列本來就把它們分開列成六項）。

**設計上的兩個保護：**①收合只是呈現，內容保持掛載，編輯中的草稿與待確認命令不受影響；②載入中、讀取失敗與待確認命令的橫幅放在收合區之外，收起時仍看得到。

### 14.3 聊天室

| 先例（2026-10-03 讀官方頁面） | 內容 | 用在哪 |
|---|---|---|
| [Cloudscape：Generative AI chat](https://cloudscape.design/patterns/genai/generative-AI-chat/) | 窄表面（側欄、內嵌）：「Align every message to the same side. A constrained measure leaves too little width for alternating sides to read as turn-taking.」單側對齊時「distinguish the user from the assistant with an avatar or a name」；完整表面才是外送訊息靠行尾、收到的靠行首 | 訪談欄是約 518px 的側欄，所有訊息同一側；員工與顧問各有頭像（員／顧）加名稱 |
| [AI Elements：Conversation](https://elements.ai-sdk.dev/components/conversation) | `ConversationScrollButton`：「Scroll button that appears when not at the bottom」 | 往上讀時浮在輸入區上方的「回到最新」圓鈕，點了回到底部並恢復跟隨 |

這是對 §7 的修正，不是改寫 §7：當時「員工靠右氣泡」依的是 Vercel AI Elements 原始碼與 ChatGPT 的畫面，兩者都是全頁面對話，而 §7 把訪談欄歸為「專用整頁介面」；但訪談欄實際只有約 518px 寬，是 Cloudscape 說的窄表面，那裡的準則是同一側。改回靠右只是一段 CSS（員工訊息的對齊與最大寬度），可逆。

### 14.4 沒做、與已知限制

- 處理中輸入區的「狀態列、暫停／取消鈕、說明文字」三塊（§13.5 第二點）仍沒合併：合併要拆 `ConsultantTurnControls`，而暫停與取消後果不同，不能照 ChatGPT／Claude 的單一停止鈕；是否值得改要由維護者決定。
- 收合時，裡面若有開著的編輯器，編輯器仍在（草稿保留），但看不見；其他編輯控制項仍因「一次只開一個」而暫停，展開即可回到編輯。這與職責、任務原有的收合行為一致。
- 沒有取得：Material 3 側欄指引頁（頁面由腳本渲染）；ChatGPT、Perplexity 沒有可讀的官方設計文件，只能靠畫面觀察，不當依據。

## 15. 完成後直接輸入與閱讀欄降噪（2026-10-03）

維護者確認成功完成訪談後不需再按「開始下一次訪談」，並要求聊天室參考右側 JD 的乾淨設計。這次改動限前端呈現與成功後的輸入流程。

本次重新查閱 [Craft 官網](https://www.craft.do/)與 [Apple 2021 App Store Awards](https://www.apple.com/newsroom/2021/12/app-store-awards-honor-the-best-apps-and-games-of-2021/)，確認 Craft 的 Mac App of the Year 得獎紀錄；借鏡的是以內容為中心的文件閱讀感，不宣稱本案採用了 Apple 的評審規則。[Linear 改版說明](https://linear.app/now/how-we-redesigned-the-linear-ui)把降低視覺雜訊、對齊與層次列為重點；[Cloudscape 窄版聊天](https://cloudscape.design/gen-ai/patterns/generative-ai-chat/)則支持同側排列及清楚標示說話者。Linear 與 Cloudscape 在此是設計與規範參考，不以得獎網站稱呼。

本案取捨：保留名稱與頭像，員工原話改用細線區隔、顧問保留純文字；淡化頭像、減少完成狀態的大色塊，輸入框改較小圓角。正式回覆載入後，過程入口留在對應的回覆下方；尚未載入時仍可從原位置查回。所有配色沿現有 token，不引入動畫、框架或第二套聊天狀態。

程式沿 [React 的 Effect 使用界線](https://react.dev/learn/you-might-not-need-an-effect)：能從已確認 Turn 推導的表單顯示直接推導；新 command 與草稿清理放在送出事件，不用 Effect 自動開下一輪。產品規則以[介面文件](../../implementation/interface-and-delivery.md#2-串流不是保存權威)為準，測試與畫面檢查另記[證據 §15](../../history.md#source-a75c36d876a672e0f607)。

## 16. 聊天輸入器：Enter 送出與按鈕按下狀態（2026-10-05）

維護者要求聊天室可以按 Enter 送出，並把按鈕做得更好看。這次推翻 §9「刻意不同 1」：當時不做，是因為注音選字的 Enter 會誤送；現在以輸入法組字判斷解決，不必再避開通行慣例。

**Enter（行為）**

- **Fact（一手來源）：**[Vercel AI Elements 原碼](https://github.com/vercel/ai-elements/blob/main/packages/elements/src/prompt-input.tsx)的 `handleKeyDown`：Enter 且不在輸入法組字（`isComposing`）、沒按 Shift、送出鈕未停用時，以 `form.requestSubmit()` 送出，Shift＋Enter 換行；範例的送出鈕是 `disabled={!text && !status}`。[MDN keydown](https://developer.mozilla.org/en-US/docs/Web/API/Element/keydown_event)：以 `event.isComposing || event.keyCode === 229` 略過輸入法處理的按鍵；`compositionend` 可能早於 `keydown`，此時 `isComposing` 為 false，但 keyCode 仍是 229。
- **Mapping：**Enter 等同按下送出鈕（`sendDisabled` 單一判斷，鈕不可用就不動作；空白草稿與按鈕一樣提示填寫）。保存、重送、確認規則不動，沒有第二條送出路徑。「這個按鍵是不是送出」集中在 `features/interview/send-key.ts`；`keyCode` 已被 DOM 型別標示過時，是整個前端第一個 `eslint-disable`（`no-deprecated`，附原因），要退就刪那一行加上 Safari 的判斷。
- **風險與緩解：**送出是正式訪談的起點，誤按 Enter 會把寫到一半的答案送出。緩解是既有的「取消處理」加「取回原文編輯」（草稿不會遺失）；送出鈕的提示標明「送出訪談（Enter）」。**沒有**另加常駐說明文字。

**按鈕（質感）**

- **Measured（公開頁，桌面 1440px，2026-10-05）：**GitHub 登入頁（Primer）主要鈕高 40、半徑 6、14px／500、邊框 `rgba(31,35,40,.15)`，次要鈕淡灰底 `#f6f8fa`＋邊框 `#d1d9e0`；Linear 導覽鈕高 32、膠囊形；Vercel 導覽鈕高 32、半徑 6、14px／500，轉場 150ms；Stripe 高 40、半徑 4、14px／400；Notion 高 36–38、半徑 8、16px／500，次要鈕是淡藍底無邊框。我們的矩形鈕（36px／半徑 8、小鈕 28px／半徑 6、字重 500、轉場 120ms）已在這個範圍內，不重做尺寸。Claude 登入頁沒有抓到按鈕（0 個候選），未取得。
- **Fact（原碼）：**[Primer `ButtonBase.module.css`](https://github.com/primer/react/blob/main/packages/react/src/Button/ButtonBase.module.css)：default、primary、danger、invisible 都有獨立的 `:hover`、`:active`，停用時 `box-shadow: none`。[shadcn/ui `button.tsx`](https://github.com/shadcn-ui/ui/blob/main/apps/v4/registry/new-york-v4/ui/button.tsx) 現行版：outline 變體有 `shadow-xs`，圖示 16px（`size-4`），尺寸 sm 32／預設 36／lg 40。
- **採用（`theme.ts` 單一來源；維護者「不要綠色，就白色，Apple 風格」）：**主要鈕原本是品牌綠實心，改成白底、深色字、字重 600，以一圈細邊加兩層柔陰影浮起（`shadow.button`／`buttonHover`；macOS 與 iOS 26 膠囊鈕的做法，是風格參照，不是逐字規格）；次要鈕維持細邊、不浮起，主次靠「浮起與否」區分；文字鈕改深色字、淡灰 hover；所有按鈕改膠囊（`radius.pill`）、圖示鈕改圓形；外框鈕保留 `shadow.xs`；實心、外框、文字、圖示鈕都補 `:active`（原本關了漣漪又沒有按下樣式）。就地編輯的「✓」同樣改白底浮起（`styles.css`）。破壞性確認鈕仍是紅色實心。
- **刻意沒做：**①送出鈕在空白時停用（AI Elements 如此，ChatGPT、Claude 的畫面也如此，但這不是這次要求，既有 6 個單元測試把「可按」當成「查詢完成」的訊號，e2e 的強制色彩檢查也在空白草稿時量送出鈕，停用後的外觀未評估，要做另案）。②沒改尺寸、半徑、字重、圖示：實測落在主流範圍內。③沒碰「職務檔案清單頁」與刪除對話框：另一項進行中工作（職務檔案刪除）的範圍；該對話框的「取消」是文字樣式，與其他對話框的次要（外框）樣式不同，收尾時應統一。
- **聊天室的按鈕（只改外觀，行為與測試不動；維護者「改 UI 就好」）：**暫停／繼續／取消處理與取回原文編輯、開始下一次訪談，由 28px 小鈕改為 36px 白色膠囊（拿掉 `size="small"`，形狀與顏色來自主題），與圓形送出鈕同一語言；送出鈕圖示由紙飛機改為向上箭頭（描邊 2.25；ChatGPT、Claude、Perplexity 的畫面都是向上箭頭，只是產品觀察，沒有官方文件），不再使用的 `SendIcon` 已刪。390px 寬量到無橫向溢出，處理控制鈕為 112×36。
- **效果：**全產品的按鈕不再有品牌綠實心。仍是綠色的只有鍵盤焦點環、連結、頁籤指示線與少數標籤（不是按鈕，這次沒動；若也要去綠需另外決定）。

**驗證**

單元：Enter 7 項（含「弄壞各守衛，對應測試會失敗」的突變驗證：Shift、`isComposing`、keyCode 229 各一次）；完整 Vitest 45 檔／285 項、`tsc`、完整 ESLint、Prettier 全過。真 Chromium（私有示範站）：Shift＋Enter 換行不送；以 CDP 組字（keydown 為 key＝Process、isComposing＝true、keyCode＝229）時 Enter 不送；一般 Enter 只送一次且文字相同。**未驗證：**Safari／macOS 輸入法實機、e2e 全套（未起隔離 PostgreSQL）、Windows 高對比下的外框鈕陰影（陰影本來就會被該模式移除，邊框仍在）。

**2026-10-05 白色改版後的驗證範圍：**維護者要求不跑大測試，所以只做截圖與量測（聊天室各狀態、對話框、就地編輯「✓」量到 28×28、白底、半徑 999px）與 Prettier、殘留引用檢查。完整 Vitest／`tsc`／ESLint 的通過紀錄是白色與全域膠囊改動**之前**跑的，改動後沒有重跑，e2e 也沒跑；JD 區小按鈕的左右內距由 10px 改 12px，沒有逐一重量版面。

**2026-10-06 提交前回歸：**已對目前白色按鈕、全域膠囊、Enter 送出及檔案刪除的合併工作目錄執行 `pnpm check`，exit 0。Vitest 45 檔／285 項、TypeScript、ESLint、生成契約與 production build 均通過；這補上前述白色改版後未重跑的程式檢查，不新增 e2e、Safari／macOS 輸入法或高對比實機結論。刪除及取消／保存競爭的 PostgreSQL 結果另見[刪除驗證](../../experiments/product-validation/2026-10-05-job-file-deletion.md#取消與保存競爭的接續驗證2026-10-06)。
