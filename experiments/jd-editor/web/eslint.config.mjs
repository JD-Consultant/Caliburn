import { defineConfig, globalIgnores } from "eslint/config";
import next from "eslint-config-next/core-web-vitals";
import ts from "eslint-config-next/typescript";
// The adopted employee journey uses full document navigation for beforeunload.
export default defineConfig([
  ...next,
  ...ts,
  {
    rules: {
      "@next/next/no-html-link-for-pages": "off",
      "@next/next/no-location-assign-relative-destination": "off",
    },
  },
  globalIgnores([".next/**", "src/generated/**", "next-env.d.ts"]),
]);
