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
    },
    // Per svelte.dev/docs/svelte/testing: use the package "browser" entry points
    // while Vitest runs in Node, without affecting the real `vite build`.
    resolve: process.env.VITEST ? { conditions: ["browser"] } : undefined,
});
