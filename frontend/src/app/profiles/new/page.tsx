"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useCreateProfile } from "@/hooks/useProfiles";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ArrowLeft, BriefcaseIcon } from "lucide-react";

export default function NewProfilePage() {
  const router = useRouter();
  const { mutateAsync: createProfile, isPending } = useCreateProfile();
  const [form, setForm] = useState({ job_title: "", department: "", job_summary: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = () => {
    const e: Record<string, string> = {};
    if (!form.job_title.trim()) e.job_title = "請輸入職稱";
    if (!form.department.trim()) e.department = "請輸入部門";
    return e;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length) return setErrors(errs);
    const profile = await createProfile(form);
    router.push(`/profiles/${profile.id}`);
  };

  return (
    <div className="min-h-screen bg-muted/30">
      <header className="bg-background border-b px-6 py-4 flex items-center gap-3">
        <Link href="/dashboard">
          <Button variant="ghost" size="icon">
            <ArrowLeft className="w-4 h-4" />
          </Button>
        </Link>
        <div className="flex items-center gap-2">
          <BriefcaseIcon className="w-5 h-5 text-blue-600" />
          <span className="font-semibold">JobIntel AI</span>
        </div>
      </header>

      <main className="max-w-lg mx-auto px-6 py-12">
        <div className="mb-8">
          <h1 className="text-2xl font-bold">新增職務檔案</h1>
          <p className="text-muted-foreground text-sm mt-1">
            填寫基本資訊後，AI 將引導你進行職能訪談
          </p>
        </div>

        <Card className="p-6">
          <form onSubmit={handleSubmit} className="space-y-5">
            <div>
              <label className="text-sm font-medium block mb-1.5">
                職稱 <span className="text-destructive">*</span>
              </label>
              <input
                className="w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="例：採購專員"
                value={form.job_title}
                onChange={(e) => setForm((f) => ({ ...f, job_title: e.target.value }))}
              />
              {errors.job_title && (
                <p className="text-xs text-destructive mt-1">{errors.job_title}</p>
              )}
            </div>

            <div>
              <label className="text-sm font-medium block mb-1.5">
                部門 <span className="text-destructive">*</span>
              </label>
              <input
                className="w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="例：採購部"
                value={form.department}
                onChange={(e) => setForm((f) => ({ ...f, department: e.target.value }))}
              />
              {errors.department && (
                <p className="text-xs text-destructive mt-1">{errors.department}</p>
              )}
            </div>

            <div>
              <label className="text-sm font-medium block mb-1.5">工作摘要（選填）</label>
              <textarea
                className="w-full rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
                rows={4}
                placeholder="簡要描述這個職位的主要工作內容..."
                value={form.job_summary}
                onChange={(e) => setForm((f) => ({ ...f, job_summary: e.target.value }))}
              />
            </div>

            <Button type="submit" className="w-full" disabled={isPending}>
              {isPending ? "建立中..." : "開始訪談"}
            </Button>
          </form>
        </Card>
      </main>
    </div>
  );
}
