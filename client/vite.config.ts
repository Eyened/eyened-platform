import { sveltekit } from "@sveltejs/kit/vite";
import tailwindcss from "@tailwindcss/vite";
import Icons from "unplugin-icons/vite";
import { defineConfig } from "vite";
import glsl from "vite-plugin-glsl";


export default defineConfig({
  plugins: [tailwindcss(), sveltekit(), glsl(), Icons({ compiler: "svelte" })],
  server: { allowedHosts: true },
});
