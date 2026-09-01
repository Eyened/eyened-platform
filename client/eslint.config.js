import js from "@eslint/js";
import tseslint from "typescript-eslint";
import svelte from "eslint-plugin-svelte";
import prettier from "eslint-config-prettier/flat";
import globals from "globals";
import svelteConfig from "./svelte.config.js";

export default tseslint.config(
    {
        // Ignores derived from the Makefile generator outputs (gen-openapi ->
        // openapi.json, gen-types -> openapi.ts) plus framework build output
        // and vitest's coverage report, kept in step with .prettierignore so
        // the two halves of `npm run lint` agree on what is generated.
        // Hand-written files under src/types/ (openapi_types.ts,
        // openapi_constants.ts, *.d.ts) are intentionally NOT ignored.
        ignores: [
            ".svelte-kit/",
            "build/",
            "coverage/",
            "dist/",
            "node_modules/",
            "src/types/openapi.ts",
            "src/types/openapi.json",
        ],
    },
    js.configs.recommended,
    ...tseslint.configs.recommended,
    ...svelte.configs.recommended,
    {
        languageOptions: {
            globals: { ...globals.browser, ...globals.node },
        },
        rules: {
            // Required signature params / intentional unused → prefix with `_`.
            "@typescript-eslint/no-unused-vars": [
                "error",
                {
                    argsIgnorePattern: "^_",
                    varsIgnorePattern: "^_",
                    caughtErrorsIgnorePattern: "^_",
                    destructuredArrayIgnorePattern: "^_",
                },
            ],
        },
    },
    {
        // Wire the TS parser into .svelte <script lang="ts"> blocks AND the
        // *.svelte.ts / *.svelte.js rune-module extensions.
        files: ["**/*.svelte", "**/*.svelte.ts", "**/*.svelte.js"],
        languageOptions: {
            parserOptions: {
                parser: tseslint.parser,
                extraFileExtensions: [".svelte"],
                svelteConfig,
            },
        },
    },
    {
        // Ported from the legacy .eslintrc.cjs: forbid `export let` in runes mode.
        files: ["**/*.svelte"],
        rules: {
            "no-restricted-syntax": [
                "error",
                {
                    selector: "ExportNamedDeclaration[declaration.kind='let']",
                    message:
                        "Use $props() instead of `export let` in runes mode.",
                },
            ],
        },
    },
    {
        // typescript-eslint's eslint-recommended turns these on, but hard-scopes
        // itself to **/*.{ts,tsx,mts,cts} — so `.svelte` (and only `.svelte`)
        // silently missed them. `.svelte.ts` matches **/*.ts and was covered.
        // All three are at 0 violations here; enabling them keeps it that way.
        //
        // `prefer-const` is deliberately NOT in this list: it is the fourth rule
        // eslint-recommended enables, and it fires 729 times in .svelte — ~200 of
        // them on `let { x } = $props()`, the canonical runes idiom Svelte's own
        // docs use. (It compiles as `const`, so this is an idiom/scale call, not a
        // correctness one.) Tracked in docs/backlog/.
        files: ["**/*.svelte"],
        rules: {
            "no-var": "error",
            "prefer-rest-params": "error",
            "prefer-spread": "error",
        },
    },
    prettier,
);
