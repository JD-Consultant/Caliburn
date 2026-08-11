// 觸發瀏覽器下載一個 Blob（client-only，從事件處理呼叫）。
export function downloadBlob(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

// 觸發瀏覽器下載一個 JSON 檔（client-only，從事件處理呼叫）。
export function downloadJson(filename: string, data: unknown): void {
  downloadBlob(
    filename,
    new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
  );
}
