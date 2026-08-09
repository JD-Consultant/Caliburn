import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    files: [
      "src/app/workspace/**/*.{ts,tsx}",
      "src/components/workspace/**/*.{ts,tsx}",
      "src/lib/jobAnalysis*.ts",
    ],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: [
                "@/components/interview/**",
                "@/hooks/**",
                "@/lib/api",
                "@/lib/ocsDoc",
                "@/lib/pack",
                "@/types/**",
              ],
              message:
                "Current job-analysis UI must not cross into the legacy OCS seam.",
            },
          ],
        },
      ],
    },
  },
  {
    files: [
      "src/app/documents/**/*.{ts,tsx}",
      "src/app/dashboard/**/*.{ts,tsx}",
      "src/components/interview/**/*.{ts,tsx}",
      "src/hooks/**/*.{ts,tsx}",
      "src/lib/api.ts",
      "src/types/**/*.{ts,tsx}",
    ],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: [
                "@/components/workspace/**",
                "@/lib/jobAnalysis*",
              ],
              message:
                "Legacy OCS UI must not cross into the current job-analysis seam.",
            },
          ],
        },
      ],
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
