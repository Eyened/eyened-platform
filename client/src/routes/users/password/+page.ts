import { start } from "$lib/main";

export const ssr = false;

/** @type {import('./$types').PageLoad} */
export async function load({ fetch, params, url }) {
    const globalContext = await start(url);
    return { globalContext }
}
