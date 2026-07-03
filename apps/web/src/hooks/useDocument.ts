import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useDebouncedCallback } from "use-debounce";
import {
  ApiError,
  finalizeDocument,
  getDocument,
  getKnowledge,
  patchDocument,
  setOccupations,
} from "@/lib/api";
import type { DocumentEnvelope, OcsDocument } from "@/types";

// D27 工作台資料層。document = of-record（draft/final/none 空殼）；mutation 成功後
// 直接 setQueryData 更新快取（即時反映），finalize/seed 另 invalidate profiles（dashboard 狀態）。

export function useDocument(profileId: string) {
  return useQuery({
    queryKey: ["document", profileId],
    queryFn: () => getDocument(profileId),
    refetchOnWindowFocus: false,
  });
}

// PATCH mutation 送出的變數：content + 樂觀鎖 token（2a, ADR 0015）。
export interface PatchDocumentVars {
  content: OcsDocument;
  expect?: { version: number; revision: number };
}

export function usePatchDocument(profileId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ content, expect }: PatchDocumentVars) =>
      patchDocument(profileId, content, expect),
    // 不做 onMutate 樂觀寫入/onError 回滾：cache 的 content 已由 useAutosaveDocument.commit()
    // 同步寫入（呼叫 mutate 前一定先 commit 過），這裡再寫一次是重複的；且 409 時規格要求
    // 「不回滾本地編輯」（使用者的字留在畫面），回滾邏輯反而會誤刪使用者剛打的字。
    onSuccess: (env: DocumentEnvelope) =>
      // ⚠ 關鍵（spec §6.3）：這裡只更新 cache 顯示用的 version/revision/status，content 仍保留
      // cache 現有值（可能已有此次 PATCH 之後、使用者又打的新鍵）。baseline 的重設不在這裡做，
      // 而是由呼叫端（useAutosaveDocument）用「送出的 content」（mutation variables，不是這裡
      // 的 env.content 或 cache 的 old.content）另外處理——用 cache/env 會把未存的字誤標成已存。
      qc.setQueryData<DocumentEnvelope>(["document", profileId], (old) =>
        old ? { ...env, content: old.content } : env,
      ),
  });
}

export function useFinalizeDocument(profileId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => finalizeDocument(profileId),
    onSuccess: (env: DocumentEnvelope) => {
      qc.setQueryData(["document", profileId], env);
      qc.invalidateQueries({ queryKey: ["profiles"] });
    },
  });
}

export function useSetOccupations(profileId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ocsCodes: string[]) => setOccupations(profileId, ocsCodes),
    onSuccess: () => {
      // 重抓 document（GET 空殼會用新 selected codes 帶表頭）。
      qc.invalidateQueries({ queryKey: ["document", profileId] });
      // 知識包(ADR 0021):選職類=唯一同步點 → 作廢舊包 + 背景預載新包
      // (不鎖 UI;失敗交給消費端 query 自行重抓)。所有選單資料都吃這一包。
      qc.invalidateQueries({ queryKey: ["knowledge", profileId] });
      void qc.prefetchQuery({
        queryKey: ["knowledge", profileId],
        queryFn: () => getKnowledge(profileId),
      });
    },
  });
}

export type SaveStatus = "idle" | "unsaved" | "saving" | "saved" | "conflict" | "error";

// 409 衝突：伺服器回的「當前」token（覆蓋路徑重送要用；spec §2.3）。
export interface ConflictInfo {
  currentVersion: number;
  currentRevision: number;
}

// baseline = 最後「已知的 server 狀態」快照：{content, version, revision}。
// no-op skip（commit 的 content 與 baseline.content 相同 → 不排 PATCH）、dirty 判定（status 推導）、
// flush 送出的樂觀鎖 token，都以 baseline 為準。
interface Baseline {
  content: OcsDocument;
  version: number;
  revision: number;
}

export function useAutosaveDocument(profileId: string) {
  const qc = useQueryClient();
  const patch = usePatchDocument(profileId);
  const latest = useRef<OcsDocument | undefined>(undefined);
  // baseline 存兩份、永遠一起寫：baselineRef（給 flushPatch/effect 等非 render 的 callback 讀，
  // 需要「呼叫當下最新值」而非 create-time 閉包捕捉的值）+ baseline state（給 render 期間讀，
  // 觸發 dirty/status 重新計算——lint 規則 react-hooks/refs 禁止在 render 期間讀 ref.current）。
  const baselineRef = useRef<Baseline | null>(null);
  const [baseline, setBaseline] = useState<Baseline | null>(null);
  const setBaselineBoth = (b: Baseline | null) => {
    baselineRef.current = b;
    setBaseline(b);
  };
  // 本 hook 自己送出的 PATCH 導致的 cache version/revision 變化，不能被下面的「外部變化」
  // effect 誤判成外部變化而用 cache 內容重設 baseline（那正是 spec §6.3 點名的漏存 bug）。
  // flush() 呼叫 patch.mutate() 前設 true；PATCH 的 onSuccess 已經（用 variables）正確處理過
  // baseline，下面的 effect 讀到這個 flag 為 true 時要跳過、並清掉它。
  const ownWrite = useRef(false);
  const [conflict, setConflict] = useState<ConflictInfo | null>(null);

  const envelope = qc.getQueryData<DocumentEnvelope>(["document", profileId]);

  // 初始 baseline：document query 首次有資料時，用 envelope 整包設（effect，不在 render 期間寫 ref）。
  useEffect(() => {
    if (baselineRef.current === null && envelope) {
      setBaselineBoth({ content: envelope.content, version: envelope.version, revision: envelope.revision });
    }
  }, [envelope]);

  const flushPatch = useDebouncedCallback(() => {
    const b = baselineRef.current;
    if (!latest.current || !b || conflict) return;
    const content = latest.current;
    const expect = { version: b.version, revision: b.revision };
    ownWrite.current = true;
    patch.mutate(
      { content, expect },
      {
        onSuccess: (env) => {
          // ⚠ 關鍵：baseline 用「送出的 content」（這個 closure 捕捉的 content，即 mutation
          // variables），不是 cache 的 env.content / old.content——commit() 可能在這次 PATCH
          // 飛行中又寫入了更新的按鍵，cache 已經比 content 新，用 cache 會把那些未存的字
          // 誤標成「已存」（漏存 bug；spec §6.3 明文點名）。
          setBaselineBoth({ content, version: env.version, revision: env.revision });
          setConflict(null);
        },
        onError: (e: unknown) => {
          ownWrite.current = false; // 沒成功，不是「外部變化」也不該讓上面的 effect 誤判
          if (e instanceof ApiError && e.status === 409) {
            const body = e.body as { detail?: { current_version?: number; current_revision?: number } } | undefined;
            const d = body?.detail;
            setConflict({
              currentVersion: d?.current_version ?? b.version,
              currentRevision: d?.current_revision ?? b.revision,
            });
            // 暫停 autosave、不回滾本地編輯：latest.current 與 cache 的 content 都原樣保留，
            // 使用者的字還在畫面上；等 ConflictDialog 的兩個動作之一把 conflict 解掉。
          }
          // 非 409 錯誤：不特別處理，status 推導會落到 "error"（patch.isError）。
        },
      },
    );
  }, 500);

  // 外部變化（GET 首載之後的 invalidate/refetch、setOccupations/finalize 成功、
  // ConflictDialog「載入最新版」）→ envelope 的 version/revision 改變，且不是本 hook 的 PATCH
  // 寫回 → baseline 用新 envelope 整包重設（此時 cache 的 content 才是新的 server 真相）。
  useEffect(() => {
    if (!envelope) return;
    if (ownWrite.current) {
      // 本 hook 剛送出的 PATCH 造成的 version/revision 變化：baseline 已在 flush 的
      // onSuccess 用「送出的 content」正確重設過，這裡只消掉旗標、不可再用 cache 重設。
      ownWrite.current = false;
      return;
    }
    const b = baselineRef.current;
    if (b && (b.version !== envelope.version || b.revision !== envelope.revision)) {
      setBaselineBoth({ content: envelope.content, version: envelope.version, revision: envelope.revision });
      // 外部把整份文件換掉了（例如載入最新版丟棄本地編輯）：待送的舊內容不再有意義，
      // 且必須清掉待打的 debounce，否則稍後可能把已捨棄的舊內容又送回去。
      latest.current = undefined;
      flushPatch.cancel();
      setConflict(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [envelope?.version, envelope?.revision]);

  const commit = (next: OcsDocument) => {
    latest.current = next;
    qc.setQueryData<DocumentEnvelope>(["document", profileId], (old) =>
      old ? { ...old, content: next } : old,
    );
    // no-op skip：新內容與 baseline（最後已存的內容）逐位元相同 → 取消排程中的 PATCH，
    // 不送網路請求。誤差方向安全：stringify 鍵序不同只會判成 dirty（多存一次），
    // 不可能把真正 dirty 的內容判成 clean（漏存）。
    const b = baselineRef.current;
    if (b && JSON.stringify(next) === JSON.stringify(b.content)) {
      flushPatch.cancel();
      return;
    }
    if (conflict) return; // 衝突未解不排新的 PATCH（避免疊加送出注定 409 的請求）
    flushPatch();
  };

  const dirty =
    !!baseline && !!envelope && JSON.stringify(envelope.content) !== JSON.stringify(baseline.content);

  const status: SaveStatus = conflict
    ? "conflict"
    : patch.isPending
      ? "saving"
      : dirty
        ? "unsaved"
        : patch.isError
          ? "error"
          : baseline
            ? "saved"
            : "idle";

  // ConflictDialog「載入最新版」：refetch → 換成 server 版 → 上面的 effect 會偵測到
  // version/revision 變化並重設 baseline（cache 此時就是新的 server 真相）。
  // conflict 等 invalidateQueries 真的 refetch 完才清（不是呼叫當下就清）：ConflictDialog
  // 由 status==="conflict" 條件掛載，太早清 conflict 會讓對話框在新內容還沒回來前就先消失，
  // 使用者可能瞥到舊內容甚至趁空檔打字。清 conflict 不只依賴上面 effect 的副作用（那要等
  // version/revision 剛好變動才觸發，理論上一定會變但沒必要讓收尾依賴這個推論）——這裡
  // await 完成後直接清，兩邊都清一次，用哪個先到都對。
  const loadLatest = async () => {
    latest.current = undefined;
    flushPatch.cancel();
    await qc.invalidateQueries({ queryKey: ["document", profileId] });
    setConflict(null);
  };

  // ConflictDialog「以我的版本覆蓋」：用 409 給的 current token 重送本地內容。
  const overwriteWithLocal = () => {
    if (!conflict) return;
    const content = latest.current ?? envelope?.content;
    if (!content) return;
    const expect = { version: conflict.currentVersion, revision: conflict.currentRevision };
    ownWrite.current = true;
    patch.mutate(
      { content, expect },
      {
        onSuccess: (env) => {
          setBaselineBoth({ content, version: env.version, revision: env.revision });
          setConflict(null);
        },
        onError: (e: unknown) => {
          ownWrite.current = false;
          if (e instanceof ApiError && e.status === 409) {
            const body = e.body as { detail?: { current_version?: number; current_revision?: number } } | undefined;
            const d = body?.detail;
            setConflict({
              currentVersion: d?.current_version ?? conflict.currentVersion,
              currentRevision: d?.current_revision ?? conflict.currentRevision,
            });
          }
        },
      },
    );
  };

  return {
    doc: envelope?.content,
    status,
    conflict,
    // conflict 狀態下 patch.isPending 代表「以我的版本覆蓋」重送中（ConflictDialog 兩顆按鈕
    // 都要在這段時間 disabled，避免使用者連點兩次疊加請求）。
    conflictBusy: status === "conflict" && patch.isPending,
    commit,
    flush: () => flushPatch.flush(),
    loadLatest,
    overwriteWithLocal,
  };
}
