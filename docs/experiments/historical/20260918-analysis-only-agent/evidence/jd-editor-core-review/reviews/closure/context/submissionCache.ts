import type { JdManualSaveClientInput } from "@caliburn/jd-editor-contract";
export type Disk = Pick<Storage, "getItem" | "setItem" | "removeItem">;
export type Submission = JdManualSaveClientInput & { document_id: string };
const prefix = "caliburn:jd-plate-clean-v2:submission:";
export function submissionCache(disk: Disk) {
  return {
    read(document: string): Submission | null {
      const raw = disk.getItem(prefix + document);
      if (!raw) return null;
      const value = JSON.parse(raw);
      if (value.document_id !== document) throw Error("保存記錄不屬於此文件");
      return value;
    },
    write(payload: Submission) {
      const raw = JSON.stringify(payload);
      disk.setItem(prefix + payload.document_id, raw);
      if (disk.getItem(prefix + payload.document_id) !== raw)
        throw Error("無法保留送出記錄，尚未發送");
    },
    confirm(
      document: string,
      result: { status: string; receipt_durability: string },
    ) {
      if (
        result.receipt_durability === "confirmed" &&
        ["committed", "no_change"].includes(result.status)
      )
        disk.removeItem(prefix + document);
    },
    discard(document: string) {
      disk.removeItem(prefix + document);
    },
  };
}
