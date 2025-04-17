import { loadEnv } from 'vite';
import glsl from 'vite-plugin-glsl';
import { sveltekit } from '@sveltejs/kit/vite';
import Icons from 'unplugin-icons/vite';

/** @type {import('vite').UserConfig} */
export default () => {
    // Load environment variables
    const env = loadEnv('all', process.cwd());

    let allowedHost = '';
    try {
        if (env.VITE_PROXY_URL) {
            const url = new URL(env.VITE_PROXY_URL);
            allowedHost = url.hostname;
        }
    } catch (error) {
        console.warn('Failed to parse VITE_PROXY_URL:', error);
    }

    return {
        plugins: [
            sveltekit(),
            glsl(),
            Icons({
                compiler: 'svelte',
            }),
        ],
        server: {
            proxy: {
                '/auth': {
                    target: env.VITE_PROXY_URL,
                    changeOrigin: true,
                    secure: false,
                    ws: true,
                },
                '/api': {
                    target: env.VITE_PROXY_URL,
                    changeOrigin: true,
                    secure: false,
                    ws: true,
                },
            },
            allowedHosts: [allowedHost],
        },
    };
};