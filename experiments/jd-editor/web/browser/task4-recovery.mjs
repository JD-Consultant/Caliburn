import { chromium, expect } from "@playwright/test";
import { writeFile } from "node:fs/promises";
import { resolve } from "node:path";
const evidence = resolve(
  "../../../.superpowers/sdd/2026-09-10-jd-editor-core-implementation",
);
const browser = await chromium.launch({ channel: "chrome", headless: false });
const context = await browser.newContext({
  viewport: { width: 1500, height: 1050 },
});
const page = await context.newPage(),
  network = [],
  errors = [];
const result = {
  browser: browser.version(),
  channel: "chrome",
  headed: true,
  cases: [],
};
page.on("request", (r) => {
  if (r.url().includes(":8091"))
    network.push({ method: r.method(), url: r.url(), body: r.postData() });
});
page.on("pageerror", (e) => errors.push(String(e)));
const api = "http://127.0.0.1:8091";
const read = async (id) =>
  (await context.request.get(`${api}/documents/${id}/jd`)).json();
const cache = async (key) =>
  page.evaluate((key) => localStorage.getItem(key), key);
try {
  // The real server commits; only the browser's response is lost.
  let created;
  await page.route(`${api}/documents`, async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    created = await (await route.fetch()).json();
    await route.abort("failed");
  });
  await page.goto("http://127.0.0.1:3001");
  await page.getByLabel("文件名稱").fill("回覆遺失驗收 " + Date.now());
  await page.getByRole("button", { name: "建立文件", exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText(
    "尚未確認建立",
  );
  await page.unroute(`${api}/documents`);
  await page.reload();
  await page
    .getByRole("button", { name: "依原記錄再次確認", exact: true })
    .click();
  await page.waitForURL("**/workspace/**");
  const document = page.url().split("/").at(-1);
  expect(document).toBe(created.id);
  result.document = document;
  result.cases.push("create lost reply -> reload -> same key same document");
  const editor = page.getByRole("textbox", { name: "職務說明書正文" });
  await expect(editor).toBeEditable();
  await editor.click();
  await page.keyboard.insertText("保留原提交");
  const saveURL = `${api}/documents/${document}/jd/manual-save`,
    key = "caliburn:jd-plate-clean-v2:submission:" + document;
  let committed;
  await page.route(saveURL, async (route) => {
    committed = await (await route.fetch()).json();
    await route.abort("failed");
  });
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText(
    "保存尚未確認",
  );
  const payload = JSON.parse(await cache(key));
  await page.unroute(saveURL);
  await page.reload();
  await expect.poll(() => cache(key)).toBe(null);
  expect((await read(document)).revision_ref).toBe(
    committed.result_revision_ref,
  );
  result.cases.push(
    "manual server commit/lost reply -> reload exact candidate receipt",
  );
  result.committed = committed;
  result.manualPayload = payload;
  // A stale candidate is a real confirmed failure and must survive two reloads.
  await expect(editor).toBeEditable();
  await editor.click();
  await page.keyboard.press("Control+End");
  await page.keyboard.insertText("本頁候選");
  let staleReceipt;
  await page.route(saveURL, async (route) => {
    const head = await read(document);
    const value = structuredClone(head.fragment);
    value[0].children = [{ text: "另一頁已保存版本" }];
    const other = await context.request.post(saveURL, {
      data: {
        request_key: crypto.randomUUID(),
        base_revision_ref: head.revision_ref,
        value,
      },
    });
    expect(other.ok()).toBe(true);
    const response = await route.fetch();
    staleReceipt = await response.json();
    await route.fulfill({ response });
  });
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("stale");
  const stalePayload = await cache(key);
  expect(stalePayload).toContain("本頁候選");
  await page.unroute(saveURL);
  for (let i = 0; i < 2; i++) {
    await page.reload();
    await expect(
      page.getByRole("heading", { name: "尚待處理的送出候選" }),
    ).toBeVisible();
    expect(await cache(key)).toBe(stalePayload);
    await expect(editor).toHaveText("另一頁已保存版本");
  }
  result.cases.push(
    "confirmed stale candidate survives two reopenings without overwriting current",
  );
  result.stale = {
    receipt: staleReceipt,
    payload: JSON.parse(stalePayload),
    head: await read(document),
  };
  page.once("dialog", (d) => d.accept());
  await page.getByRole("button", { name: "捨棄這份候選", exact: true }).click();
  expect(await cache(key)).toBe(null);
  // Real run receives the canonical input. Reopen only queries by request.
  const runsURL = `${api}/documents/${document}/runs`;
  await page.route(runsURL, async (route) => {
    if (route.request().method() !== "POST") return route.continue();
    await route.fetch();
    await route.abort("failed");
  });
  await page.getByLabel("補充或更正你的工作").fill("這是逐字保存的純聊天");
  await page.getByRole("button", { name: "送出", exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText(
    "正在確認是否收到，",
  );
  await page.unroute(runsURL);
  const posts = network.filter(
    (r) => r.method === "POST" && r.url === runsURL,
  ).length;
  await page.reload();
  await expect(page.getByLabel("補充或更正你的工作")).toHaveValue("");
  expect(
    network.filter((r) => r.method === "POST" && r.url === runsURL),
  ).toHaveLength(posts);
  result.cases.push(
    "run lost reply -> read-only by-request reconciliation, no POST/resume",
  );
  const messages = await (
    await context.request.get(`${api}/documents/${document}/messages`)
  ).json();
  expect(messages.filter((m) => m.role === "user").map((m) => m.text)).toEqual([
    "這是逐字保存的純聊天",
  ]);
  result.messages = messages;
  await page.screenshot({
    path: resolve(evidence, "task4-recovery-screen.png"),
    fullPage: true,
  });
  result.ax = await page.locator("main").ariaSnapshot();
  result.ok = true;
} catch (error) {
  result.ok = false;
  result.failure = String(error);
  await page.screenshot({
    path: resolve(evidence, "task4-recovery-failure.png"),
    fullPage: true,
  });
  throw error;
} finally {
  result.network = network;
  result.errors = errors;
  await writeFile(
    resolve(evidence, "task4-recovery-browser.json"),
    JSON.stringify(result, null, 2),
  );
  await context.close();
  await browser.close();
}
