import { create } from "zustand";
import { persist } from "zustand/middleware";
import { createUser } from "@/lib/api";

interface UserStore {
  userId: string | null;
  ensureUser: () => Promise<string>;
}

export const useUserStore = create<UserStore>()(
  persist(
    (set, get) => ({
      userId: null,
      async ensureUser() {
        const existing = get().userId;
        if (existing) return existing;
        const user = await createUser({
          email: `anon-${Date.now()}@example.com`,
          name: "匿名用戶",
        });
        set({ userId: user.id });
        return user.id;
      },
    }),
    { name: "jobintel-user" }
  )
);
