# OpenAI Responses fixture bodies(synthetic, test-only)

- 來源:OpenAI 官方 Responses OpenAPI(`https://api.openai.com/v1/responses`)與
  official Python SDK `openai==2.46.0` 的 typed models;核對日期 **2026-07-17**。
- 全部 **人工最小化、synthetic**;無真實員工內容、無 API key、無真實 request ID。
- 檔案內容保持 provider wire shape,**不加任何非 API 欄位**;
  status code、headers(`x-request-id`)、用途等 metadata 一律放 sidecar `manifest.json`。
- 測試一定經 `httpx.MockTransport` + 官方 SDK deserialization 消費這些 body,
  不允許直接以 MagicMock 構造 SDK response objects(規格 §15.1/§15.4)。
