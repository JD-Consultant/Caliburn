import js from '@eslint/js';
import { defineConfig, globalIgnores } from 'eslint/config';
import tseslint from 'typescript-eslint';
import hooks from 'eslint-plugin-react-hooks';
import refresh from 'eslint-plugin-react-refresh';
import globals from 'globals';

// A feature uses shared code only; pages compose features in app (code-organization.md §2.6).
const features = ['interview', 'jd-editor', 'job-files', 'source-viewer'];

export default defineConfig(
  globalIgnores(['dist', '.next', 'test-results', 'playwright-report', 'src/shared/api/generated']),
  js.configs.recommended,
  tseslint.configs.recommended,
  {
    files: ['src/**/*.{ts,tsx}'],
    extends: [
      tseslint.configs.recommendedTypeChecked,
      hooks.configs.flat.recommended,
      refresh.configs.vite,
    ],
    languageOptions: {
      globals: globals.browser,
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
    rules: {
      '@typescript-eslint/consistent-type-imports': 'error',
      '@typescript-eslint/switch-exhaustiveness-check': 'error',
      '@typescript-eslint/no-non-null-assertion': 'error',
      // Current supported APIs only (coding-standard.md §1): a library's `@deprecated` marker is its
      // own notice that the call goes away, e.g. React's FormEvent and TanStack's fetchQuery.
      '@typescript-eslint/no-deprecated': 'error',
    },
  },
  {
    files: ['tests/e2e/**/*.ts', 'playwright.config.ts'],
    extends: [tseslint.configs.recommendedTypeChecked],
    languageOptions: {
      globals: globals.node,
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
    rules: {
      '@typescript-eslint/consistent-type-imports': 'error',
      '@typescript-eslint/no-deprecated': 'error',
    },
  },
  {
    files: ['scripts/**/*.mjs', '*.js'],
    languageOptions: { globals: globals.node },
  },
  {
    files: ['src/shared/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            { group: ['**/features/**', '**/app/**'], message: 'shared 不依賴業務或頁面組裝。' },
          ],
        },
      ],
    },
  },
  ...features.map((feature) => ({
    files: [`src/features/${feature}/**/*.{ts,tsx}`],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              regex: `^(\\.\\./)+(${features.filter((other) => other !== feature).join('|')})(/|$)`,
              message: 'feature 不 import 別的 feature；跨 feature 協作由 app 組裝。',
            },
            { regex: '^(\\.\\./)+app(/|$)', message: 'feature 不依賴頁面組裝。' },
          ],
        },
      ],
    },
  })),
);
