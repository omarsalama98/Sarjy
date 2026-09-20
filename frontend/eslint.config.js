// ESLint 9 flat config.
//
// Block 0 found `npm run lint` had never run — the script existed, the config
// did not, so the Stop hook's frontend gate was passing on an error. This is
// the minimum that makes it real.
//
// Deliberately small: browser audio is the fiddly part of this project and a
// linter that shouts about formatting gets switched off. Rules here are the
// ones that catch bugs, not the ones that catch taste.

import js from '@eslint/js';
import globals from 'globals';
import tseslint from 'typescript-eslint';

export default tseslint.config(
  { ignores: ['dist/**', 'node_modules/**', 'src/spike/**'] },
  js.configs.recommended,
  ...tseslint.configs.recommended,
  {
    files: ['**/*.{ts,tsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      globals: { ...globals.browser, ...globals.worklet },
    },
    rules: {
      // An unused variable in audio plumbing is usually a wiring mistake,
      // not a leftover. Underscore-prefixed names are the escape hatch.
      '@typescript-eslint/no-unused-vars': [
        'error',
        { argsIgnorePattern: '^_', varsIgnorePattern: '^_' },
      ],
      // A floating promise in the pipeline is a dropped turn with no error.
      'no-console': 'off',
    },
  },
);
