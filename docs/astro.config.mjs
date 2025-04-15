// @ts-check
import starlight from '@astrojs/starlight';
import { defineConfig } from 'astro/config';

// https://astro.build/config
export default defineConfig({
	site: 'https://eyened.github.io',
    base: 'eyened-platform',
	integrations: [
		starlight({
			title: 'Eyened Platform',
			social: [{ icon: 'github', label: 'GitHub', href: 'https://github.com/eyened/eyened-platform' }],
			sidebar: [
				{ slug: 'getting_started' },
                { slug: 'importer' },
				{
				label: 'Eyened ORM',
					// Autogenerate a group of links for the 'constellations' directory.
					autogenerate: { directory: 'orm' },
				},
				{
				label: 'Eyened API',
					// Autogenerate a group of links for the 'constellations' directory.
					autogenerate: { directory: 'api' },
				},
				{label: 'Eyened Viewer',
					// Autogenerate a group of links for the 'constellations' directory.
					autogenerate: { directory: 'client' },
				},
			],
			// sidebar: [
			// 	{
			// 		label: 'Guides',
			// 		items: [
			// 			// Each item here is one entry in the navigation menu.
			// 			{ label: 'Example Guide', slug: 'guides/example' },
			// 		],
			// 	},
			// 	{
			// 		label: 'Reference',
			// 		autogenerate: { directory: 'reference' },
			// 	},
			// ],
		}),
	],
	vite: {
		server: {
		allowedHosts: ['eyened-gpu']
		},
	}
});
