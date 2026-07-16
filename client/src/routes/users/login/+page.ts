export const ssr = false;

/** @type {import('./$types').PageLoad} */
export async function load({ fetch: _fetch, params: _params }) {
    // always create a new user manager, so log in will override logged in user
    // const userManager = new UserManager();
    // return { userManager };
}
