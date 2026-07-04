import path from "node:path";
import { defineConfig } from "vitest/config";

// 只測 src/lib 純函式(文件編輯/池投影/URN);UI 照舊以 tsc + eslint 為 gate。
export default defineConfig({
  test: { environment: "node", include: ["src/**/*.test.ts"] },
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
});
