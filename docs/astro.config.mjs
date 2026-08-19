// @ts-check
import starlight from '@astrojs/starlight';
import { defineConfig } from 'astro/config';
import dotenv from 'dotenv';

dotenv.config();

export default defineConfig({
    site: 'https://eyened.github.io',
    base: '/eyened-platform/',
    integrations: [
        starlight({
            title: 'EyeNED Platform',
            social: [{ icon: 'github', label: 'GitHub', href: 'https://github.com/eyened/eyened-platform' }],
            sidebar: [
                { slug: 'about' },
                { slug: 'release_notes' },
                { slug: 'getting_started' },
                { slug: 'platform_design' },
                {
                    label: 'Data ingestion',
                    items: [
                        { slug: 'importing_data' },
                        { slug: 'import_metadata_fields' },
                        { slug: 'thumbnails' },
                    ],
                },
                {
                    label: 'Guides',
                    items: [
                        { slug: 'guides/development_setup' },
                        { slug: 'guides/authentication' },
                    ],
                },
                {
                    label: 'Eyened ORM',
                    items: [
                        { slug: 'orm/getting_started' },
                        { slug: 'orm/configuration' },
                        {
                            label: 'Data model',
                            autogenerate: { directory: 'orm/data_model' },
                        },
                        { slug: 'orm/importer' },
                        { slug: 'orm/dicom_export' },
                        { slug: 'orm/cli' },
                        { slug: 'orm/inference' },
                        { slug: 'orm/form_schemas' },
                        { slug: 'orm/registration' },
                        { slug: 'orm/development' },
                    ],
                },
                {
                    label: 'Eyened API',
                    items: [
                        { slug: 'api' },
                        { slug: 'api/authentication' },
                        { slug: 'api/images' },
                        { slug: 'api/import' },
                        { slug: 'api/segmentations' },
                        { slug: 'api/features' },
                        { slug: 'api/forms' },
                        { slug: 'api/tasks' },
                        { slug: 'api/tags' },
                        { slug: 'api/search' },
                        { slug: 'api/devices' },
                        { slug: 'api/reference' },
                    ],
                },
                {
                    label: 'Eyened Viewer',
                    items: [
                        { slug: 'client' },
                        {
                            label: 'Panels',
                            autogenerate: { directory: 'client/panels' },
                        },
                    ],
                },
            ],

        }),
    ],
    vite: {
        server: {
            allowedHosts: process.env.ALLOWED_HOSTS ? process.env.ALLOWED_HOSTS.split(',') : ['eyened-supergpu', 'localhost'],
        },
    }
});
