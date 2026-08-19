import { sveltekit } from "@sveltejs/kit/vite";
import tailwindcss from "@tailwindcss/vite";
import Icons from "unplugin-icons/vite";
import { defineConfig } from "vitest/config";
import glsl from "vite-plugin-glsl";

export default defineConfig({
    plugins: [
        tailwindcss(),
        sveltekit(),
        glsl(),
        Icons({ compiler: "svelte" }),
    ],
    server: { allowedHosts: true },
    build: {
        minify: "terser",
        terserOptions: {
            compress: {
                drop_console: true, // Remove console.logs in production
            },
        },
    },
    test: {
        environment: "jsdom",
        globals: true,
        setupFiles: ["./vitest-setup.ts"],
        restoreMocks: true,
        coverage: {
            provider: "v8",
            reporter: ["text-summary", "json-summary", "lcov"],
            // `include` puts never-imported files in the report at 0% rather
            // than leaving them out, so a brand-new untested component reddens
            // the gate instead of passing vacuously.
            include: ["src/**/*.{ts,svelte}"],
            exclude: [
                "src/types/openapi.ts", // generated: make gen-client-types
                "src/lib/components/ui/**", // generated: shadcn-svelte
                "src/**/*.{test,spec}.ts",
                "src/**/*.d.ts",
            ],
            // No `thresholds` key: vitest fails a run on coverage only when
            // thresholds are declared. Omitting them keeps the project total
            // ungated, leaving the patch gate the single path to a red check.
        },
    },
    // Per svelte.dev/docs/svelte/testing: use the package "browser" entry points
    // while Vitest runs in Node, without affecting the real `vite build`.
    resolve: process.env.VITEST ? { conditions: ["browser"] } : undefined,
});
