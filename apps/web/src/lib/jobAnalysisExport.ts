/**
 * 匯出檔名。後端已在 `Content-Disposition` 給了檔名，但 `a[download]` 走的是我們
 * 自己給的字串，所以這裡要自己組一份等價的。
 *
 * 檔名裡的路徑字元會被作業系統擋掉或誤解，先清掉；清完是空的就用固定 fallback，
 * 免得存成一個沒有名字的檔。
 */
export function exportFilename(title: string): string {
  const cleaned = title.replace(/[\\/:*?"<>|]/g, "").trim();
  return `${cleaned || "職務說明書"}.xlsx`;
}
