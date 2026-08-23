import path from "node:path";
import { defineConfig } from "vitest/config";

// 純函式維持 node；少量員工核心流程用檔案層 jsdom 註記做元件整合測試。
export default defineConfig({
  test: {
    environment: "node",
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"],
  },
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
});
