import { sveltekit } from '@sveltejs/kit/vite';
import Icons from 'unplugin-icons/vite';
import glsl from 'vite-plugin-glsl';

/** @type {import('vite').UserConfig} */
export default () => {
    return {
        plugins: [
            sveltekit(),
            glsl(),
            Icons({
                compiler: 'svelte',
            }),
        ],
        server: {
            allowedHosts: true,
        },
    };
};