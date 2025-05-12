import { globalContext } from "$lib/main";

export const prerender = false;
export const ssr = false;

/** @type {import('./$types').PageLoad} */
export async function load({ fetch, params, url }) {
    await globalContext.init(url.pathname);
}