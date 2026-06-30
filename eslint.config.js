import pluginVue from 'eslint-plugin-vue';
import pluginPlaywright from 'eslint-plugin-playwright';
import globals from 'globals';

export default [
  // ── Ignore generated and dependency directories ──────────────────────────
  { ignores: ['dist/**', 'node_modules/**', 'packages/ui/public/**'] },

  // ── Vue SFC files: use eslint-plugin-vue's flat/essential preset ─────────
  // This preset installs vue-eslint-parser and all essential Vue 3 rules.
  ...pluginVue.configs['flat/essential'],

  // ── Override: tighten rules for Vue components ───────────────────────────
  {
    files: ['packages/ui/src/**/*.vue'],
    languageOptions: {
      globals: { ...globals.browser, ...globals.es2022 },
    },
    rules: {
      'no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      'no-undef': 'error',
      'no-console': 'warn',
      // Flash.vue is a single-word legacy name — it predates the multi-word rule.
      'vue/multi-word-component-names': ['error', { ignores: ['Flash'] }],
    },
  },

  // ── Engine package: packages/engine/src/*.js ─────────────────────────────
  // Pure Node-importable modules — no browser globals or console logging.
  {
    files: ['packages/engine/src/**/*.js'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: { ...globals.es2022 },
    },
    rules: {
      'no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      'no-undef': 'error',
      'no-console': 'error',
    },
  },

  // ── UI source JS: packages/ui/src/**/*.js ────────────────────────────────
  {
    files: ['packages/ui/src/**/*.js'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: { ...globals.browser, ...globals.es2022 },
    },
    rules: {
      'no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      'no-undef': 'error',
      'no-console': 'warn',
    },
  },

  // ── Engine tests: packages/engine/test/*.mjs ─────────────────────────────
  {
    files: ['packages/engine/test/**/*.mjs', 'packages/engine/test/**/*.js'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: { ...globals.node, ...globals.es2022 },
    },
    rules: {
      'no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      'no-undef': 'error',
    },
  },

  // ── UI unit tests: packages/ui/test/*.test.mjs ────────────────────────────
  {
    files: ['packages/ui/test/**/*.test.mjs', 'packages/ui/test/**/*.mjs'],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: 'module',
      globals: { ...globals.node, ...globals.es2022 },
    },
    rules: {
      'no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
      'no-undef': 'error',
    },
  },

  // ── Engine boundary — only store.js and selftest.js may call raw physics ────
  // deriveDriver / sweep / maxCurves must go through store.js (which wraps them
  // with error handling). selftest.js is exempt — it tests the raw engine bundle.
  {
    files: ['packages/ui/src/components/**', 'packages/ui/src/utils/**'],
    ignores: ['packages/ui/src/utils/selftest.js'],
    rules: {
      'no-restricted-imports': ['error', {
        patterns: [
          {
            group: ['@resonate/engine'],
            importNamePattern: '^deriveDriver$',
            message: 'Use driver from store.js — the store wraps deriveDriver with error handling.',
          },
          {
            group: ['@resonate/engine'],
            importNamePattern: '^(sweep|maxCurves)$',
            message: 'Use curvesData/maxData from store.js — the store wraps sweep/maxCurves with error handling.',
          },
        ],
      }],
    },
  },

  // ── Playwright tests: packages/ui/test/*.browser.spec.js ─────────────────
  {
    ...pluginPlaywright.configs['flat/recommended'],
    files: ['packages/ui/test/**/*.browser.spec.js'],
    rules: {
      ...pluginPlaywright.configs['flat/recommended'].rules,
      'playwright/no-page-pause': 'error',
      'playwright/no-wait-for-timeout': 'error',
      'no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_' }],
    },
  },
];
