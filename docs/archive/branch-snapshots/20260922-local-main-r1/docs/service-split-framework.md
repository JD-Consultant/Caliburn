# 拆分判準 — 服務 vs repo vs 模組

> 可重用的判斷法（2026-06-27 建立並驗證，套 indexer / auth / Postgres 三例皆自洽）。
> 用途:遇到「這要不要獨立成一個服務 / 一個 repo?」時照這個決定,別憑感覺。
> 相關:[`specs/2026-06-27-system-architecture-design.md`](specs/2026-06-27-system-architecture-design.md)、[`contract-strategy.md`](contract-strategy.md)。

## 兩條軸不要混

- **拆「服務」**(部署 / 執行單元)= **技術 / 領域**判準(下面那組訊號)。
- **拆「repo」** = **人 / 擁有權 / 發佈**判準:只有「不同人管 / 對外獨立發版 / 合規要物理隔離 / 規模大到工具撐不住」才分 repo;否則一律 monorepo 的 `apps/`。

## 拆「服務」的訊號

看它跟鄰居的答案是否**不同**。**預設不拆、門檻高:**

1. 執行環境 / 依賴不同(ML / GPU / 重依賴)← 最強
2. 擴展需求不同(要獨立擴展)← 最強
3. 變動速率 / 部署節奏不同
4. 資料所有權不同(擁有自己的倉庫 + 領域資料)
5. bounded context 不同(領域語言變了)
6. (SaaS)全域 vs 多租戶角色不同

**要幾個 YES?** 單一個夠強(① 或 ②)即可;或多個中等疊加。borderline → **不拆**,先當模組。

## 不該拆(留成模組 / 資料夾)

只是「感覺大 / 想整齊」、共用狀態又 chatty、只是語言不同、同一 context 的內部(拆 = nano-service 過度切割)、單人小團隊。

## 關鍵安全網

**「以後拆開」比「以後合併」容易 → 猶豫一律先留一起,真實的痛出現再抽(Strangler Fig)。** 在 monorepo 裡抽出 / 併入只是搬資料夾。

## 資料庫不是「拆不拆」的對象

它是**某服務的私有倉庫**(基礎設施),不是服務、也不是專案。Postgres 屬 `apps/api`、Qdrant 屬 `apps/ocs-indexer`;別人只透過該服務的 API 取資料,**不直接碰它的倉庫**。

## 驗證範例

- **ocs-indexer**:六訊號幾乎全中(自有 Qdrant 倉庫、檢索領域、可獨立擴展)→ 獨立服務(`apps/ocs-indexer`)。
- **embedder**:訊號 ①(GPU / torch 重依賴)+ ②(獨立擴展)即足 → 獨立 **GPU 容器服務**(`apps/embedder`,ADR 0012)。
- **auth**:同一 context、無特殊 runtime → `apps/api` 的一個模組,不另拆。
- **Postgres / Qdrant**:倉庫,非服務、非專案。
