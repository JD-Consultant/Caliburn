import { chromium } from "@playwright/test";
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
});
const page = await context.newPage();
const errors = [],
  requests = [];
page.on("pageerror", (error) => errors.push(String(error)));
page.on("request", (r) =>
  requests.push({ method: r.method(), url: r.url(), body: r.postData() }),
);
try {
  await page.goto(fixture.url);
  await page.getByRole("textbox", { name: "職務說明書正文" }).waitFor();
  await page.screenshot({
    path: resolve(evidence, "task4-first-screen.png"),
    fullPage: true,
  });
  const result = {
    browser: browser.version(),
    channel: "chrome",
    headed: true,
    url: page.url(),
    editables: await page.locator("[contenteditable=true]").count(),
    tasks: await page.locator(".jd-editable .jd_task").count(),
    tables: await page.locator(".jd-editable table").count(),
    errors,
    requests,
    ax: await page.locator("main").ariaSnapshot(),
  };
  await writeFile(
    resolve(evidence, "task4-first-browser.json"),
    JSON.stringify(result, null, 2),
  );
  console.log(
    JSON.stringify({
      ...result,
      requests: requests.map((x) => x.url),
      ax: undefined,
    }),
  );
} finally {
  await context.close();
  await browser.close();
}
