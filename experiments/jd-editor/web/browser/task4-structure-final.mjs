import { chromium, expect as baseExpect } from "@playwright/test";
const expect = baseExpect.configure({ timeout: 30000 });
import { readFile, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
const evidence = resolve(
  "../../../.superpowers/sdd/2026-09-10-jd-editor-core-implementation",
);
const fixture = JSON.parse(
  await readFile(resolve(evidence, "task4-browser-server.json"), "utf8"),
);
const browser = await chromium.launch({ channel: "chrome", headless: false });
const context = await browser.newContext({
    viewport: { width: 1500, height: 1050 },
  }),
  page = await context.newPage();
const result = {
    browser: browser.version(),
    channel: "chrome",
    headed: true,
    cases: [],
  },
  network = [],
  errors = [];
const starts = new WeakMap();
result.responses = [];
result.timing = {};
page.on("request", (r) => {
  starts.set(r, performance.now());
  if (r.url().includes(":8091"))
    network.push({
      at: new Date().toISOString(),
      method: r.method(),
      url: r.url(),
      body: r.postData(),
    });
});
page.on("pageerror", (e) => errors.push(String(e)));
page.on("response", (r) => {
  if (r.url().includes(":8091"))
    result.responses.push({
      at: new Date().toISOString(),
      status: r.status(),
      url: r.url(),
      response_headers_ms: performance.now() - starts.get(r.request()),
    });
});
const api = "http://127.0.0.1:8091";
const read = async (id) =>
  (await context.request.get(`${api}/documents/${id}/jd`)).json();
try {
  const initialStarted = performance.now();
  await page.goto(fixture.url);
  const editor = page.getByRole("textbox", { name: "職務說明書正文" });
  await expect(editor).toBeEditable();
  result.timing.initialEditorReadyMs = performance.now() - initialStarted;
  result.react = await page
    .locator(".editor-shell")
    .getAttribute("data-react-version");
  expect(await editor.locator(".jd_task").count()).toBe(8);
  expect(await editor.locator(".jd_outcomes").count()).toBe(8);
  expect(await editor.locator(".jd_requirements").count()).toBe(8);
  const table = editor.locator("table"),
    rows = await table.locator("tr").count();
  await table.locator("td,th").first().locator("p").first().click();
  await page.getByRole("button", { name: "表格增列", exact: true }).click();
  await expect(table.locator("tr")).toHaveCount(rows + 1);
  await page.getByRole("button", { name: "表格刪列", exact: true }).click();
  await expect(table.locator("tr")).toHaveCount(rows);
  result.cases.push("official table insert/delete row");
  const nested = editor
    .locator("ul ul .lic,ol ol .lic,ul ol .lic,ol ul .lic")
    .first();
  await expect(nested).toBeVisible();
  const count = await editor.locator(".lic").count();
  await nested.click();
  await page.keyboard.press("End");
  await page.keyboard.press("Enter");
  await page.keyboard.insertText("補充子清單項目");
  await expect(editor.locator(".lic")).toHaveCount(count + 1);
  result.cases.push("native nested list Enter retains list structure");
  const saveStarted = performance.now();
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("已保存");
  result.timing.saveConfirmedUIMs = performance.now() - saveStarted;
  result.structure = await read(fixture.document);
  const reopenStarted = performance.now();
  await page.reload();
  await expect(editor).toContainText("補充子清單項目");
  result.timing.reopenEditorReadyMs = performance.now() - reopenStarted;
  expect((await read(fixture.document)).fragment).toEqual(
    result.structure.fragment,
  );
  await editor
    .getByRole("button", { name: "依據 1", exact: true })
    .first()
    .click();
  await expect(
    page.getByRole("heading", { name: "依據・已保存的原問答" }),
  ).toBeVisible();
  result.source = await page.locator(".source-panel").innerText();
  expect(result.source).toContain("員工原文");
  result.cases.push("source button reads canonical conversation owner");
  await page.screenshot({
    path: resolve(evidence, "task4-structure-final-screen.png"),
    fullPage: true,
  });
  result.ok = true;
} catch (error) {
  result.ok = false;
  result.failure = String(error);
  await page.screenshot({
    path: resolve(evidence, "task4-structure-final-failure.png"),
    fullPage: true,
  });
  throw error;
} finally {
  result.network = network;
  result.errors = errors;
  await writeFile(
    resolve(evidence, "task4-structure-final-browser.json"),
    JSON.stringify(result, null, 2),
  );
  await context.close();
  await browser.close();
}
