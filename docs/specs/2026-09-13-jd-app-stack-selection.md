# JD App：主流框架比較與選型

- 查閱日：2026-09-13；Topic：JD-R002／RS-F。
- Owner 的判準是現行主流、官方支援、大廠公開實務與本案適用性；對話中的 TypeScript／React／Next.js／Python 是例子，不記為指定技術或個人偏好。
- 本稿記研究者的方案選擇及未驗限制。框架方向、精確版本組合、完整 RS-F 閉合及 production 採用是不同狀態；本輪不安裝、改 runtime、建表或呼叫產品模型。
- 需求沿[完整管理旅程](2026-09-13-jd-complete-app-journey-design.md)、[欄位審核](2026-09-13-jd-field-sufficiency-audit.md)及[選型準則](2026-09-13-jd-native-framework-and-integration-preflight.md)，不因框架提供某功能便新增產品範圍。

## 1. 前端選擇

**選 TypeScript＋React＋Next.js App Router 作前端框架方向。**採用理由是現行 React 官方推薦框架路線、Next 明示的版本支援政策、完整路由／錯誤與載入呈現／建置工具及本機運行能力。這不是因為舊程式使用相同名稱，也不主張所有大廠統一使用這個組合。

| 有界比較 | 官方能力 | 本案選擇及代價 |
|---|---|---|
| Next.js App Router | [React 建立 App](https://react.dev/learn/creating-a-react-app)列為推薦框架；[Next 安裝](https://nextjs.org/docs/app/getting-started/installation)提供 TypeScript、App Router、建置及 Windows 支援；[支援政策](https://nextjs.org/support-policy)明列 Active／Maintenance LTS | 選定方向。以有明確支援週期的完整框架承接文件入口與互動畫面；本機啟停需涵蓋 Node Web 程序與 Python 服務，不把這個成本省略 |
| React Router Framework Mode | [現行 modes](https://reactrouter.com/start/modes)提供型別化路由、資料與待處理狀態、code splitting；[SPA](https://reactrouter.com/how-to/spa)支援以靜態資產服務前端 | 可行替代，特別適合以減少執行程序為優先的純 SPA。本輪選 Next 的公開 LTS 路線與完整工具組；未證明 React Router 過時或較不主流，也不以 RSC／SEO 是本案必需作假理由 |

React 官網仍以「React Router v7」介紹框架，React Router 自站最新頁已顯示 8.3.1；只採框架能力比較，不拿較早介紹頁替最新版背書。新專案不採已棄用的 [Create React App](https://react.dev/blog/2025/02/14/sunsetting-create-react-app)。

**責任分界：**Next 負責畫面及必要傳輸接合；員工操作與模型工具的共同 JD 規則仍放在後端。Next 的 Server Actions／Route Handlers 不建立第二套 JD 或 Memory 寫入規則；[官方 BFF 文件](https://nextjs.org/docs/app/guides/backend-for-frontend)支持接外部後端，也明示其後端能力不是完整後端的替代品。代理、快取及流式傳輸方式仍須以實際保存與取消情境驗證，不能照複製範例便宣稱完成。

**本機呈現限制：**新增文件身分是在使用期間產生；不能把 `/workspace/[id]` 直接當成建置時已知路徑去做純靜態輸出。[Next static export](https://nextjs.org/docs/app/guides/static-exports)不支援缺少 `generateStaticParams()` 的動態路徑。本案按本機 Next 程序設計，非為省一個程序而偷偷改產品或預先列完所有文件。

## 2. 前端版本與授權證據

以下為查閱當下可直接確認的狀態，**尚非相容性實測後的 lock 清單**：

| 項目 | 查閱狀態／授權 | 採用前必須補齊 |
|---|---|---|
| TypeScript | [官方下載頁](https://www.typescriptlang.org/download/)列目前 7.0；[官方授權](https://github.com/microsoft/TypeScript/blob/main/LICENSE.txt)為 Apache-2.0 | 核對所選建置器、型別檢查器、生成器與元件的支援；不用全機安裝取代專案鎖定 |
| React | [官方版本頁](https://react.dev/versions)列 19.3／19.3.0，發布日 2026-09-09；[官方授權](https://github.com/react/react/blob/main/LICENSE)為 MIT | 新穩定版仍須和元件／Next 組合實測；不因發布較新就忽略 peer dependencies |
| Next.js | 官方現行文件顯示 16.3.5，16.x 為 Active LTS；[官方授權](https://github.com/vercel/next.js/blob/canary/license.md)為 MIT | 精確套件發行、鎖檔及安全公告再核；授權頁分支不表示本案要安裝 canary |

Next 官方明示 App Router 內含 React canary 通道的框架執行版本；這與使用者宣告的 `react`／`react-dom` 套件不同。需一併記錄實際執行層，不寫「所有依賴都是穩定版」的過度保證。React 19.3 與 TypeScript 7 的新版本狀態也是本次必須做相容性檢查的理由，不能直接沿舊 lock 或只跑一次建置。

## 3. 管理介面元件的有限比較

**選 MUI Material UI 免費核心作第一個 UI 驗證候選；Cloudscape 作備選。**理由是完整表單／狀態／展開元件、直接的文字選區接點與現行 Next 接合文件。框架方向已選，UI 候選仍須通過組字、保存與版面驗證才進入施工基線。

| 候選 | 官方能力、版本／授權與公開使用證據 | 本案取捨 |
|---|---|---|
| MUI Material UI | [安裝與 peer](https://mui.com/material-ui/getting-started/installation/)顯示 9.4.0，React 19 在支援範圍；[授權](https://mui.com/legal/)區分 MIT Core 與商業產品；[Next 接法](https://mui.com/material-ui/integrations/nextjs/)說明 App Router 樣式及元件邊界 | 第一驗證候選。Card／List／Checkbox／Accordion／Dialog／Alert 供管理與同頁展開；不採付費 Data Grid、AI 功能或模板。不能把官網公司 logo 當具體產品部署證明，也不稱它是 Google 自家的 React 元件庫 |
| AWS Cloudscape | [AWS 公開案例](https://aws.amazon.com/about-aws/whats-new/2022/07/cloudscape-design-system-open-source-solution-building-intuitive-web-applications/)明示 AWS Management Console 使用；[現行元件](https://cloudscape.design/components/)與[開發入口](https://cloudscape.design/get-started/for-developers/using-cloudscape-components/)提供表單／管理／聊天及 Next 接法；Apache-2.0，3.x 系列，精確發布 patch 未核定 | 可行備選，大廠自家使用的證據最直接。當年使用聲明只證明當時範圍，現行能力另讀目前文件；所需 selection／composition 的發布型別接點尚未全部核定 |
| Adobe React Aria Components | [發布頁](https://react-aria.adobe.com/releases/)列 1.21.0；[官方套件](https://github.com/adobe/react-spectrum/blob/main/packages/react-aria-components/package.json)為 Apache-2.0；[現行入口](https://react-aria.adobe.com/)列無樣式的表單／選取／無障礙能力 | 功能可組合，但整套視覺與聊天呈現要補較多工作。Adobe 的整體技術使用聲明不等於某一版本 RAC 已在全部產品部署；本輪不為品牌直接採用 |

MUI [TextField API](https://mui.com/material-ui/api/text-field/)明示 `multiline` 使用 textarea、`inputRef` 指向輸入元素，`slotProps.htmlInput` 提供原生元素參數入口。這可承接 App 取得實際選區／組字事件的需求，仍不代表事件順序、繁中組字與自動保存已通過。元件以本機可用字型／資產呈現，不能照樣板加入 Google Fonts 等非必要外部依賴。

本輪沒有取得 MUI 的大廠具體產品獨立部署證據，因此只按已核能力作驗證推薦，不以「大廠都用」定案。若完整驗證無法有限承接既定需求，回比較 Cloudscape；不自製通用編輯器或為框架刪掉必要管理效果。

## 4. 後端選擇

**選 Python＋FastAPI 作後端 API 框架方向。**本案需要自訂管理操作、明確工具／HTTP 契約、AI 訪談串流與可單獨驗證的共同業務服務；FastAPI 的型別與 API 接點直接符合這些需求。這是研究後的本案取捨，不因既有 Python 程式加分，也不表示已選定 Agent runtime。

| 有界比較 | 官方能力與版本／授權 | 本案取捨及限制 |
|---|---|---|
| FastAPI | [發布紀錄](https://fastapi.tiangolo.com/release-notes/)列正式 0.141.1，2026-07-29；[官方授權](https://github.com/fastapi/fastapi/blob/master/LICENSE)為 MIT。[SSE 文件](https://fastapi.tiangolo.com/tutorial/server-sent-events/)自 0.135.0 提供 EventSourceResponse／ServerSentEvent，明列 AI chat 用途 | 選定方向。提供輸入／回應模型及串流框架；ORM／migration 仍需選定。依[版本政策](https://fastapi.tiangolo.com/deployment/versions/)固定並測試升級，minor 可含破壞性變更；不能當成有 Django 式多年 LTS 承諾 |
| Django | [下載與支援表](https://www.djangoproject.com/download/)列 6.1.1，6.1 延長支援至 2027-12；5.2.17 LTS 至 2028-04；[授權 FAQ](https://docs.djangoproject.com/en/6.1/faq/general/)為 BSD 3-Clause。ORM、migration、admin 整合程度較高 | 保留為可行替代。若以整合式資料管理及長期支援為優先可能更有利；本案自訂員工畫面與共同命令不能直接由 admin 完成。[async 契約](https://docs.djangoproject.com/en/6.1/topics/async/)要求交易放同步函式再以 sync_to_async 接入；並非不支援 AI 或長串流 |

**大廠證據的適用範圍：**Microsoft 現行[Fabric 後端指南](https://learn.microsoft.com/en-us/fabric/workload-development-kit/back-end-set-up)以 Python／FastAPI 示範按 OpenAPI 契約生成及實作項目生命週期；另有[FastAPI＋PostgreSQL 指南](https://learn.microsoft.com/en-us/azure/app-service/tutorial-python-postgresql-app-fastapi)。這證明有官方支援及具體做法參照，不是 Microsoft 全公司的後端標準；本案不因參照而加入 Fabric、Azure 或登入。Netflix Dispatch 雖曾採 FastAPI，但已封存，不用其舊版本或歷史案例證明今日採用。

**資料存取候選：**SQLAlchemy 2.0＋Alembic。[SQLAlchemy 發布頁](https://www.sqlalchemy.org/download.html)列 2.0.52 為 Current、2.1.0rc2 為 Beta，授權 MIT；本案無使用 RC 的必要證據。[交易文件](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html)提供 commit／rollback 邊界，[Alembic autogenerate](https://alembic.sqlalchemy.org/en/latest/autogenerate.html)明示生成 migration 必須人工審查。Alembic、driver、Python 精確版本與完整組合尚未核定，不列成已鎖定依賴；[FastAPI 的 SQLModel 範例](https://fastapi.tiangolo.com/tutorial/sql-databases/)也不是強制框架。

SSE 只處理傳輸；斷線不等於模型已停、JD 已回退或交易未提交。模型等待須在短 DB 交易外，共同業務負責同文件關係、revision／receipt、未知結果與 JD-only 撤回；人工 HTTP 與 AI 工具可走不同入口，但不能各寫一套規則。Agent／Memory 的框架選擇另依 OpenAI、Anthropic 及已研究的能力完成比較。

## 5. 收束與後續驗證

框架提供實作能力，無法替本案決定 JD 欄位、刪除政策、保存單位或還原的資訊責任。這些已由產品研究定義；選型依官方能力承接效果，必要業務仍需實作與驗收。

本輪已收束 App 框架方向及 UI 驗證候選，停止同層品牌廣搜。RS-F 剩餘項須在相依施工前閉合：精確套件／版本與授權、UI 行為、資料存取及遷移、Agent 與模型接點、新實作落點、契約生成、瀏覽器恢復格式。下一份可驗交付列選定組合與以下固定反例，核驗後進 RS-1；不重開欄位或用舊測試直接替新版背書。

1. 正式建置、型別檢查、hydration／樣式、Client 邊界及 runtime 版本一致；App 本機重開與動態文件入口可用。
2. 繁中組字／換行／emoji 與重複文字選區，保存中續打、伺服器晚回及重繪不破壞輸入。
3. 完整任務帶多成果／要求與共享引用，錯誤不部分發布；保存成功但回覆遺失可查原結果。
4. 固定模型串流、斷線、明示取消與安全閉合，對照真 DB 保存；撤回只影響 JD。

以上是待執行驗證，不是通過紀錄；UI 技術細節自行研究，真正改變員工效果才提出具體情境討論。

## 6. 本輪審查

`jd_command_semantics_review` 唯讀核對後端比較並窄審整稿，`jd_format_audit` 比較三套 UI 並窄審第 3、5 節；均 PASS，無 finding。root 另核前端官方資料及 Microsoft 現行指南，完成整合。十份受影響文件靜態核對 142 個本地連結、19 個 anchors 通過；本輪只有研究、文件及決策同步，未完成任何新版 runtime／DB／瀏覽器或模型實測。
