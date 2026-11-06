import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import hooks from 'eslint-plugin-react-hooks';
import refresh from 'eslint-plugin-react-refresh';
import globals from 'globals';

export default tseslint.config(
  {
    ignores: [
      'dist/**',
      'output/**',
      'src/shared/api/generated/**',
      'playwright-report/**',
      'test-results/**',
    ],
  },
  js.configs.recommended,
  ...tseslint.configs.recommendedTypeChecked.map((config) => ({
    ...config,
    files: ['**/*.ts', '**/*.tsx'],
  })),
  {
    files: ['**/*.ts', '**/*.tsx'],
    languageOptions: {
      parserOptions: { projectService: true },
      globals: { ...globals.browser, ...globals.node },
    },
    plugins: { 'react-hooks': hooks, 'react-refresh': refresh },
    rules: {
      ...hooks.configs.recommended.rules,
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
    },
  },
  { files: ['**/*.mjs', '**/*.js'], languageOptions: { globals: globals.node } },
  {
    files: ['src/shared/**/*.{ts,tsx}'],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: ['**/features/**', '**/app/**'],
              message: '共用機制不可反向依賴功能或應用組裝。',
            },
          ],
        },
      ],
    },
  },
  ...['workspace', 'job-description', 'interview', 'memory'].map((feature) => ({
    files: [`src/features/${feature}/**/*.{ts,tsx}`],
    rules: {
      'no-restricted-imports': [
        'error',
        {
          patterns: [
            {
              group: [
                '**/app/**',
                ...['workspace', 'job-description', 'interview', 'memory']
                  .filter((other) => other !== feature)
                  .map((other) => `**/${other}/**`),
              ],
              message: '跨功能組裝放在 app；功能之間不要直接依賴彼此的實作。',
            },
          ],
        },
      ],
    },
  })),
);
