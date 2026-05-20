"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useProfiles, useDeleteProfile } from "@/hooks/useProfiles";
import { useUserStore } from "@/store/user";
import { useHydrated } from "@/hooks/useHydrated";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Plus, Trash2, ChevronRight, BriefcaseIcon } from "lucide-react";
import type { Stage } from "@/types";

const STAGE_LABEL: Record<Stage, string> = {
  basic_info: "初始化",
  icap_ref: "iCAP 比對",
  interview: "基本訪談",
  task_extraction: "任務萃取",
  star: "STAR 深訪",
  five_w2h: "5W2H 補充",
  indicator: "行為指標",
  ksa: "K/S/A 整理",
  preview: "完成",
};

export default function DashboardPage() {
  const router = useRouter();
  const hydrated = useHydrated();
  const userId = useUserStore((s) => s.userId);
  const ensureUser = useUserStore((s) => s.ensureUser);
  const { data: profiles = [], isLoading } = useProfiles();
  const { mutate: deleteProfile } = useDeleteProfile();

  useEffect(() => {
    ensureUser();
  }, [ensureUser]);

  const loading = !hydrated || isLoading || (!userId && hydrated);

  return (
    <div className="min-h-screen bg-muted/30">
      {/* Top Nav */}
      <header className="bg-background border-b px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BriefcaseIcon className="w-5 h-5 text-blue-600" />
          <span className="font-semibold text-lg">JobIntel AI</span>
        </div>
        <Link href="/profiles/new">
          <Button size="sm" className="gap-2">
            <Plus className="w-4 h-4" />
            新增職務
          </Button>
        </Link>
      </header>

      <main className="max-w-4xl mx-auto px-6 py-8">
        <div className="mb-6">
          <h1 className="text-2xl font-bold">職務檔案</h1>
          <p className="text-muted-foreground text-sm mt-1">管理你的 AI 訪談與職能萃取任務</p>
        </div>

        {loading && (
          <div className="space-y-3">
            {[1, 2, 3].map((i) => (
              <div key={i} className="h-24 rounded-xl bg-muted animate-pulse" />
            ))}
          </div>
        )}

        {!loading && profiles.length === 0 && (
          <div className="text-center py-20">
            <BriefcaseIcon className="w-12 h-12 text-muted-foreground mx-auto mb-4" />
            <h2 className="text-lg font-medium mb-2">尚無職務檔案</h2>
            <p className="text-muted-foreground text-sm mb-6">
              建立第一個職務檔案，開始 AI 訪談與職能萃取
            </p>
            <Link href="/profiles/new">
              <Button className="gap-2">
                <Plus className="w-4 h-4" />
                新增職務
              </Button>
            </Link>
          </div>
        )}

        <div className="space-y-3">
          {profiles.map((profile) => (
            <Card key={profile.id} className="p-4 hover:shadow-md transition-shadow">
              <div className="flex items-center gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h2 className="font-semibold text-base truncate">{profile.job_title}</h2>
                    <Badge variant="outline" className="shrink-0 text-xs">
                      {profile.department}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-3 mt-2">
                    <Progress value={profile.completion_pct} className="h-1.5 flex-1 max-w-48" />
                    <span className="text-xs text-muted-foreground">{profile.completion_pct}%</span>
                    <Badge
                      variant="secondary"
                      className={
                        profile.stage === "preview"
                          ? "bg-emerald-100 text-emerald-700"
                          : "bg-blue-50 text-blue-700"
                      }
                    >
                      {STAGE_LABEL[profile.stage]}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1.5">
                    更新：{new Date(profile.updated_at).toLocaleDateString("zh-TW")}
                  </p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="text-muted-foreground hover:text-destructive"
                    onClick={(e) => {
                      e.stopPropagation();
                      if (confirm("確定刪除此職務檔案？")) deleteProfile(profile.id);
                    }}
                  >
                    <Trash2 className="w-4 h-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => router.push(`/profiles/${profile.id}`)}
                  >
                    <ChevronRight className="w-4 h-4" />
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
