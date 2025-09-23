import { UserManager } from "$lib/usermanager.js";

export const ssr = false;

/** @type {import('./$types').PageLoad} */
export async function load({ fetch, params }) {
    // always create a new user manager, so log in will override logged in user
    // const userManager = new UserManager();
    // return { userManager };
}
