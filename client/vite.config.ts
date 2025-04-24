import { sveltekit } from '@sveltejs/kit/vite';
import Icons from 'unplugin-icons/vite';
import { loadEnv } from 'vite';
import glsl from 'vite-plugin-glsl';

/** @type {import('vite').UserConfig} */
export default () => {
    // Load environment variables
    const env = loadEnv('all', process.cwd());

    let allowedHost = '';
    try {
        if (env.VITE_HOSTNAME) {
            const url = new URL('http://' + env.VITE_HOSTNAME);
            allowedHost = url.hostname;
        }
    } catch (error) {
        console.warn('Failed to parse VITE_HOSTNAME:', error);
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
                    target: env.VITE_HOSTNAME + ':' + env.VITE_PORT,
                    changeOrigin: true,
                    secure: false,
                    ws: true,
                },
                '/api': {
                    target: env.VITE_HOSTNAME + ':' + env.VITE_PORT,
                    changeOrigin: true,
                    secure: false,
                    ws: true,
                },
            },
            allowedHosts: [allowedHost],
        },
    };
};