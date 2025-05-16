// @ts-check
import starlight from '@astrojs/starlight';
import { defineConfig } from 'astro/config';

// https://astro.build/config
export default defineConfig({
    site: 'https://eyened.github.io',
    base: 'eyened-platform/',
    integrations: [
        starlight({
            title: 'Eyened Platform',
            social: [{ icon: 'github', label: 'GitHub', href: 'https://github.com/eyened/eyened-platform' }],
            sidebar: [
                { slug: 'getting_started' },
                { slug: 'importer' },
                { slug: 'entities' },
                { slug: 'platform_design' },
                {
                    label: 'Eyened ORM',
                    // Autogenerate a group of links for the 'orm' directory.
                    autogenerate: { directory: 'orm' },
                },
                {
                    label: 'Eyened API',
                    // Autogenerate a group of links for the 'api' directory.
                    autogenerate: { directory: 'api' },
                },
                {
                    label: 'Eyened Viewer',
                    // Autogenerate a group of links for the 'client' directory.
                    autogenerate: { directory: 'client' },
                },
            ],

        }),
    ],
    vite: {
        server: {
            allowedHosts: process.env.ALLOWED_HOSTS ? [process.env.ALLOWED_HOSTS] : [],
        },
    }
});
