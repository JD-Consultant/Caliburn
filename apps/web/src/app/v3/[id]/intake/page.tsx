"use client";

// D28 T10 小訪談（Phase 0，可跳過）：進工作台前的一頁 3 格表單。建立脈絡、餵後續 AI。
// 送出＝把三題組成 job_summary 存進 profile（後續〔選職類〕搜尋、〔選任務〕AI 預勾、
// ✨ 面板都以它為脈絡）→ 進工作台。非對話、不碰 CopilotKit。
import { use, useState } from "react";
import { useRouter } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { ChevronRight, Loader2, Sparkles } from "lucide-react";
import { useProfile } from "@/hooks/useProfiles";
import { updateProfile } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

function IntakeForm({
  id,
  jobTitle,
  defaultSummary,
}: {
  id: string;
  jobTitle?: string | null;
  defaultSummary: string;
}) {
  const router = useRouter();
  const qc = useQueryClient();
  // 既有 job_summary 預填第一題（重做小訪談不丟資料）。useState 初值＝免 effect。
  const [doWhat, setDoWhat] = useState(defaultSummary);
  const [mainWork, setMainWork] = useState("");
  const [special, setSpecial] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const composeSummary = (): string => {
    const parts: string[] = [];
    if (doWhat.trim()) parts.push(doWhat.trim());
    if (mainWork.trim()) parts.push(`主要負責：${mainWork.trim()}`);
    if (special.trim()) parts.push(`特別／清單外：${special.trim()}`);
    return parts.join("\n");
  };

  const goWorktable = () => router.push(`/v3/${id}`);

  const submit = async () => {
    const summary = composeSummary();
    if (!summary) {
      goWorktable();
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await updateProfile(id, { job_summary: summary });
      await qc.invalidateQueries({ queryKey: ["profile", id] });
      await qc.invalidateQueries({ queryKey: ["profiles"] });
      goWorktable();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "儲存失敗");
      setSaving(false);
    }
  };

  return (
    <main className="mx-auto max-w-2xl px-6 py-10">
      <div className="mb-6">
        <div className="mb-1 flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-violet-500" />
          <h1 className="text-2xl font-bold">先花 1 分鐘，3 題小訪談</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          用你自己的話描述這份工作，AI 會據此幫你預選職類、預勾任務。三題都可留白、可跳過，
          之後在工作台隨時能補。
        </p>
      </div>

      {error ? (
        <div className="mb-4 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          {error}
        </div>
      ) : null}

      <Card className="space-y-5 p-5">
        <div>
          <label className="mb-1 block text-sm font-medium">
            1. 這個職務大概在做什麼？{jobTitle ? `（${jobTitle}）` : ""}
          </label>
          <textarea
            className="w-full rounded-lg border px-3 py-2 text-sm"
            rows={3}
            placeholder="例：負責廠區設備的日常維護與故障排除，確保產線穩定運轉"
            value={doWhat}
            onChange={(e) => setDoWhat(e.target.value)}
            autoFocus
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">2. 主要負責哪些工作？</label>
          <textarea
            className="w-full rounded-lg border px-3 py-2 text-sm"
            rows={3}
            placeholder="例：預防保養排程、設備點檢、零件更換、維修紀錄彙整"
            value={mainWork}
            onChange={(e) => setMainWork(e.target.value)}
          />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium">
            3. 有沒有特別、清單上可能沒有的工作？（選填）
          </label>
          <textarea
            className="w-full rounded-lg border px-3 py-2 text-sm"
            rows={2}
            placeholder="例：緊急停機時的跨部門協調與通報"
            value={special}
            onChange={(e) => setSpecial(e.target.value)}
          />
        </div>

        <div className="flex items-center justify-between border-t pt-4">
          <Button variant="ghost" onClick={goWorktable} disabled={saving}>
            跳過
          </Button>
          <Button className="gap-1.5" onClick={submit} disabled={saving}>
            {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <ChevronRight className="h-4 w-4" />}
            {saving ? "儲存中…" : "進入工作台"}
          </Button>
        </div>
      </Card>
    </main>
  );
}

export default function IntakePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const { data: profile, isLoading } = useProfile(id);

  return (
    <div className="min-h-screen bg-muted/30">
      {isLoading ? (
        <div className="mx-auto max-w-2xl px-6 py-10">
          <div className="h-64 animate-pulse rounded-xl bg-muted" />
        </div>
      ) : (
        <IntakeForm
          key={profile?.id ?? id}
          id={id}
          jobTitle={profile?.job_title}
          defaultSummary={profile?.job_summary ?? ""}
        />
      )}
    </div>
  );
}
