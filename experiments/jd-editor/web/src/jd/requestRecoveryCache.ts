import type {
  DocumentInput,
  MessageInput,
  DocumentMetadataInput,
} from "../generated/analysis-api";
import type { Disk } from "./submissionCache";
const root = "caliburn:jd-plate-clean-v2:";
export function requestRecoveryCache(disk: Disk) {
  function write(kind: string, id: string, payload: unknown) {
    const raw = JSON.stringify(payload);
    disk.setItem(root + kind + ":" + id, raw);
    if (disk.getItem(root + kind + ":" + id) !== raw)
      throw Error("無法保留送出記錄，尚未發送");
  }
  function read<T>(kind: string, id: string): T | null {
    const raw = disk.getItem(root + kind + ":" + id);
    return raw ? JSON.parse(raw) : null;
  }
  return {
    writeCreate: (payload: DocumentInput) =>
      write("create", payload.request_key, payload),
    readCreate: (key: string) => read<DocumentInput>("create", key),
    clearCreate: (key: string) => disk.removeItem(root + "create:" + key),
    writeRun: (document: string, payload: MessageInput) =>
      write("run-submission", document, payload),
    readRun: (document: string) =>
      read<MessageInput>("run-submission", document),
    clearRun: (document: string) =>
      disk.removeItem(root + "run-submission:" + document),
    writeMetadata: (document: string, payload: DocumentMetadataInput) =>
      write("catalog", document, { document_id: document, ...payload }),
    readMetadata: (document: string) =>
      read<DocumentMetadataInput & { document_id: string }>(
        "catalog",
        document,
      ),
    clearMetadata: (document: string) =>
      disk.removeItem(root + "catalog:" + document),
  };
}
export function pendingCreates(storage: Storage) {
  const found: DocumentInput[] = [];
  for (let i = 0; i < storage.length; i++) {
    const key = storage.key(i);
    if (key?.startsWith(root + "create:")) {
      const raw = storage.getItem(key);
      if (raw) found.push(JSON.parse(raw));
    }
  }
  return found;
}
