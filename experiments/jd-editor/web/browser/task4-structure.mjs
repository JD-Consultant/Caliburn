import { chromium, expect as baseExpect } from "@playwright/test";
const expect = baseExpect.configure({ timeout: 90000 });
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
page.on("request", (r) => {
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
    console.log(new Date().toISOString(), r.status(), r.url());
});
const api = "http://127.0.0.1:8091";
const read = async (id) =>
  (await context.request.get(`${api}/documents/${id}/jd`)).json();
try {
  await page.goto(fixture.url);
  const editor = page.getByRole("textbox", { name: "職務說明書正文" });
  await expect(editor).toBeEditable();
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
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("已保存");
  result.structure = await read(fixture.document);
  await page.reload();
  await expect(editor).toContainText("補充子清單項目");
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
    path: resolve(evidence, "task4-structure-screen.png"),
    fullPage: true,
  });
  // Native cross-block selection and missing selection preserve the original question.
  await page.goto("http://127.0.0.1:3001");
  await page.getByLabel("文件名稱").fill("選取負例 " + Date.now());
  await page.getByRole("button", { name: "建立文件", exact: true }).click();
  await page.waitForURL("**/workspace/**");
  const document = page.url().split("/").at(-1);
  await expect(editor).toBeEditable();
  await editor.click();
  await page.keyboard.insertText("第一段");
  await page.keyboard.press("Enter");
  await page.keyboard.insertText("第二段");
  await page.getByRole("button", { name: "保存", exact: true }).click();
  await expect(page.getByRole("status")).toHaveText("已保存");
  await editor.click();
  await page.keyboard.press("Control+a");
  await expect(page.getByText("已選取正文", { exact: true })).toBeVisible();
  await page.getByLabel("補充或更正你的工作").fill("保留我的原話");
  await page.getByRole("button", { name: "請AI改這段", exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("未送出");
  await expect(page.getByLabel("補充或更正你的工作")).toHaveValue(
    "保留我的原話",
  );
  expect(
    await (
      await context.request.get(`${api}/documents/${document}/messages`)
    ).json(),
  ).toEqual([]);
  result.cases.push(
    "native cross-block selection rejected, Human not appended, input retained",
  );
  await editor.click();
  await page.keyboard.press("Control+End");
  const beforePosts = network.filter(
    (r) => r.method === "POST" && r.url.endsWith("/runs"),
  ).length;
  await page.getByRole("button", { name: "請AI改這段", exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText(
    "選取已不存在",
  );
  expect(
    network.filter((r) => r.method === "POST" && r.url.endsWith("/runs")),
  ).toHaveLength(beforePosts);
  await expect(page.getByLabel("補充或更正你的工作")).toHaveValue(
    "保留我的原話",
  );
  result.cases.push(
    "missing range rejects locally without plain-chat fallback",
  );
  // Select actual DOM text, then another writer saves a newer base.
  await editor.click();
  await page.keyboard.press("Control+End");
  await page.keyboard.down("Shift");
  await page.keyboard.press("ArrowLeft");
  await page.keyboard.up("Shift");
  await expect(page.getByText("已選取正文", { exact: true })).toBeVisible();
  const head = await read(document);
  const value = structuredClone(head.fragment);
  value[0].children = [{ text: "新版本第一段" }];
  expect(
    (
      await context.request.post(
        `${api}/documents/${document}/jd/manual-save`,
        {
          data: {
            request_key: crypto.randomUUID(),
            base_revision_ref: head.revision_ref,
            value,
          },
        },
      )
    ).ok(),
  ).toBe(true);
  await page.getByRole("button", { name: "請AI改這段", exact: true }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText("未送出");
  await expect(page.getByLabel("補充或更正你的工作")).toHaveValue(
    "保留我的原話",
  );
  result.cases.push("actual stale selection base rejected and input retained");
  result.rejectionDocument = document;
  result.saved = await read(document);
  result.ok = true;
} catch (error) {
  result.ok = false;
  result.failure = String(error);
  await page.screenshot({
    path: resolve(evidence, "task4-structure-failure.png"),
    fullPage: true,
  });
  throw error;
} finally {
  result.network = network;
  result.errors = errors;
  await writeFile(
    resolve(evidence, "task4-structure-browser.json"),
    JSON.stringify(result, null, 2),
  );
  await context.close();
  await browser.close();
}
