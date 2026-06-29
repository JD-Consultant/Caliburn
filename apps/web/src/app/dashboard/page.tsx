"use client";

// dashboard. Lists the user's job profiles and creates new ones, then routes
// into the interview surface (/documents/[id]). No old conversation stages —
// progress lives in the LangGraph checkpointer, not on the JobProfile row.
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useProfiles, useCreateProfile, useDeleteProfile } from "@/hooks/useProfiles";
import { useUserStore } from "@/store/user";
import { useHydrated } from "@/hooks/useHydrated";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Plus, Trash2, ChevronRight, BriefcaseIcon } from "lucide-react";
import type { DocStatus } from "@/types";

function DocStatusBadge({ status, completion }: { status: DocStatus; completion: number }) {
  if (status === "final") {
    return <Badge className="bg-emerald-600 text-xs hover:bg-emerald-600">已完成</Badge>;
  }
  if (status === "draft") {
    return (
      <Badge variant="secondary" className="text-xs">
        進行中 {Math.round(completion * 100)}%
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="text-xs text-muted-foreground">
      未開始
    </Badge>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const hydrated = useHydrated();
  const userId = useUserStore((s) => s.userId);
  const ensureUser = useUserStore((s) => s.ensureUser);
  const { data: profiles = [], isLoading } = useProfiles();
  const { mutateAsync: createProfile, isPending: creating } = useCreateProfile();
  const { mutate: deleteProfile } = useDeleteProfile();

  const [showForm, setShowForm] = useState(false);
  const [jobTitle, setJobTitle] = useState("");
  const [department, setDepartment] = useState("");
  const [jobSummary, setJobSummary] = useState("");

  useEffect(() => {
    ensureUser();
  }, [ensureUser]);

  const loading = !hydrated || isLoading || (!userId && hydrated);

  const submit = async () => {
    if (!jobTitle.trim()) return;
    const profile = await createProfile({
      job_title: jobTitle.trim(),
      department: department.trim() || undefined,
      job_summary: jobSummary.trim() || undefined,
    });
    router.push(`/documents/${profile.id}`);
  };

  return (
    <div className="min-h-screen bg-muted/30">
      <header className="flex items-center justify-between border-b bg-background px-6 py-4">
        <div className="flex items-center gap-2">
          <BriefcaseIcon className="h-5 w-5 text-blue-600" />
          <span className="text-lg font-semibold">Caliburn</span>
        </div>
        <Button size="sm" className="gap-2" onClick={() => setShowForm((v) => !v)}>
          <Plus className="h-4 w-4" />
          新增職務
        </Button>
      </header>

      <main className="mx-auto max-w-4xl px-6 py-8">
        <div className="mb-6">
          <h1 className="text-2xl font-bold">職務檔案</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            建立職務後進入訪談：選職類 → 整理任務 → 深度訪談 → 產生 OCS 文件
          </p>
        </div>

        {showForm && (
          <Card className="mb-6 space-y-3 p-4">
            <p className="text-sm font-medium">新增職務</p>
            <input
              className="w-full rounded-lg border px-3 py-2 text-sm"
              placeholder="職稱（必填，例：設備維護工程師）"
              value={jobTitle}
              onChange={(e) => setJobTitle(e.target.value)}
              autoFocus
            />
            <input
              className="w-full rounded-lg border px-3 py-2 text-sm"
              placeholder="部門（可空）"
              value={department}
              onChange={(e) => setDepartment(e.target.value)}
            />
            <textarea
              className="w-full rounded-lg border px-3 py-2 text-sm"
              placeholder="職務簡述（可空，會用於搜尋職類 OCS）"
              rows={2}
              value={jobSummary}
              onChange={(e) => setJobSummary(e.target.value)}
            />
            <div className="flex gap-2">
              <Button size="sm" disabled={!jobTitle.trim() || creating} onClick={submit}>
                {creating ? "建立中…" : "建立並開始訪談"}
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setShowForm(false)}>
                取消
              </Button>
            </div>
          </Card>
        )}

        {loading && (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-20 animate-pulse rounded-xl bg-muted" />
            ))}
          </div>
        )}

        {!loading && profiles.length === 0 && !showForm && (
          <div className="py-20 text-center">
            <BriefcaseIcon className="mx-auto mb-4 h-12 w-12 text-muted-foreground" />
            <h2 className="mb-2 text-lg font-medium">尚無職務檔案</h2>
            <p className="mb-6 text-sm text-muted-foreground">建立第一個職務，開始訪談</p>
            <Button className="gap-2" onClick={() => setShowForm(true)}>
              <Plus className="h-4 w-4" />
              新增職務
            </Button>
          </div>
        )}

        <div className="space-y-3">
          {profiles.map((profile) => (
            <Card key={profile.id} className="p-4 transition-shadow hover:shadow-md">
              <div className="flex items-center gap-4">
                <div className="min-w-0 flex-1">
                  <div className="mb-1 flex items-center gap-2">
                    <h2 className="truncate text-base font-semibold">{profile.job_title}</h2>
                    {profile.department ? (
                      <Badge variant="outline" className="shrink-0 text-xs">
                        {profile.department}
                      </Badge>
                    ) : null}
                  </div>
                  {profile.job_summary ? (
                    <p className="truncate text-xs text-muted-foreground">{profile.job_summary}</p>
                  ) : null}
                  <div className="mt-1.5 flex items-center gap-2">
                    <DocStatusBadge
                      status={profile.doc_status ?? "none"}
                      completion={profile.completion ?? 0}
                    />
                    <span className="text-xs text-muted-foreground">
                      更新：{new Date(profile.updated_at).toLocaleString("zh-TW")}
                    </span>
                  </div>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="text-muted-foreground hover:text-destructive"
                    onClick={() => {
                      if (confirm("確定刪除此職務檔案？")) deleteProfile(profile.id);
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="icon" onClick={() => router.push(`/documents/${profile.id}`)}>
                    <ChevronRight className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      </main>
    </div>
  );
}
