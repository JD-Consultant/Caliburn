"use client";

// 2a（ADR 0015）存檔並發衝突對話框：PATCH 409（另一分頁/流程已把文件存到更新的
// version/revision）時彈出。文案精神同 Word Copilot staged 審閱 / VS Code
// file-changed-on-disk 提示——兩個選項都是「使用者明選」，不靜默丟失任一邊的內容：
//   [載入最新版]   丟棄本地未存編輯，換成伺服器最新內容。
//   [以我的版本覆蓋] 保留本地內容，用伺服器給的當前 token 重送、蓋過對方的版本。
// 刻意不用 components/interview/OccupationPicker.tsx 的 Modal：那個殼點背景/按 X
// 都會靜默關閉，但這裡使用者必須從兩個動作二選一（不解決衝突就不能回到「什麼都沒發生」
// 的狀態），所以背景點擊/Esc 一律不關閉，只留兩顆按鈕本身可以離開這個狀態。
export function ConflictDialog({
  onLoadLatest,
  onOverwrite,
  busy,
}: {
  onLoadLatest: () => void;
  onOverwrite: () => void;
  busy?: boolean;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30 p-4">
      <div className="w-full max-w-md rounded-xl bg-background p-5 shadow-xl">
        <h3 className="text-sm font-semibold">此文件已在別處被更新</h3>
        <p className="mt-2 text-sm text-muted-foreground">
          可能是另一個分頁或流程存了新的變更。請選擇要保留哪一邊的內容——你目前畫面上的編輯不會被自動丟棄。
        </p>
        <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onLoadLatest}
            disabled={busy}
            className="rounded-lg border px-3 py-1.5 text-sm hover:bg-muted disabled:pointer-events-none disabled:opacity-50"
          >
            載入最新版
          </button>
          <button
            type="button"
            onClick={onOverwrite}
            disabled={busy}
            className="rounded-lg bg-primary px-3 py-1.5 text-sm text-primary-foreground hover:bg-primary/80 disabled:pointer-events-none disabled:opacity-50"
          >
            {busy ? "覆蓋中…" : "以我的版本覆蓋"}
          </button>
        </div>
      </div>
    </div>
  );
}
