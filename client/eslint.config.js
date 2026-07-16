import js from "@eslint/js";
import tseslint from "typescript-eslint";
import svelte from "eslint-plugin-svelte";
import prettier from "eslint-config-prettier/flat";
import globals from "globals";
import svelteConfig from "./svelte.config.js";

export default tseslint.config(
    {
        // Ignores derived from the Makefile generator outputs (gen-openapi ->
        // openapi.json, gen-types -> openapi.ts) plus framework build output.
        // Hand-written files under src/types/ (openapi_types.ts,
        // openapi_constants.ts, *.d.ts) are intentionally NOT ignored.
        ignores: [
            ".svelte-kit/",
            "build/",
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
    prettier,
);
