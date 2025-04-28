import { loadBase } from "$lib/datamodel/api";
import { UserManager } from "$lib/usermanager";
import { redirect } from "@sveltejs/kit";
import { GlobalContext } from "./data-loading/globalContext.svelte";
import { data } from "./datamodel/model";
import { FilterList } from "./datamodel/itemList";
import { derived, readable, writable, type Readable } from "svelte/store";

export const _globalContext = writable<GlobalContext | null>(null);
export const globalContext: Readable<GlobalContext> = derived(
    _globalContext,
    ($globalContext) => {
        if ($globalContext == null) {
            throw new Error('Global context is not set');
        }
        return $globalContext;
    }
);

export async function start(url: URL) {
    const userManager = new UserManager();

    // Check if we're in a prerendering context
    if (import.meta.env.SSR) {
        const dummy_creator = {
            id: 0,
            name: 'dummy',
            isHuman: false,
            annotations: new FilterList(readable([]))
        };
        return new GlobalContext(userManager, dummy_creator);
    }



    if (!userManager.isLoggedIn) {
        // Prevent redirect loop by checking if we're already on the login page
        if (!url.pathname.startsWith('/users/login')) {
            const origin = encodeURIComponent(url.pathname + url.search);
            redirect(307, `/users/login?redirect=${origin}`);
        }
        // If we're already on the login page, don't redirect again
    }
    await loadBase();
    const { creators } = data;
    const creator = creators.get(userManager.CreatorID!)!;
    const globalContext = new GlobalContext(userManager, creator);
    return globalContext;
}