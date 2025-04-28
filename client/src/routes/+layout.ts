import { _globalContext, start } from "$lib/main";

export const prerender = false;
export const ssr = false;

/** @type {import('./$types').PageLoad} */
export async function load({ fetch, params, url }) {
    _globalContext.set(await start(url));
}
