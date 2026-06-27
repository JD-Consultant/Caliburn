import { create } from "zustand";
import { persist } from "zustand/middleware";
import { createUser, getUser } from "@/lib/api";

interface UserStore {
  userId: string | null;
  ensureUser: () => Promise<string>;
}

async function createAnon(set: (s: Partial<UserStore>) => void): Promise<string> {
  const user = await createUser({ email: `anon-${Date.now()}@example.com`, name: "匿名用戶" });
  set({ userId: user.id });
  return user.id;
}

export const useUserStore = create<UserStore>()(
  persist(
    (set, get) => ({
      userId: null,
      async ensureUser() {
        const existing = get().userId;
        if (existing) {
          // Verify the cached user still exists — after a DB reset the stored id
          // is stale and every write 404s ("User not found"). Recreate on 404.
          try {
            await getUser(existing);
            return existing;
          } catch (e) {
            if (!(e instanceof Error && e.message.startsWith("404"))) throw e;
            set({ userId: null });
          }
        }
        return createAnon(set);
      },
    }),
    { name: "jobintel-user" }
  )
);
