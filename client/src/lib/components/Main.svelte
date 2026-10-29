<script lang="ts">
    import { goto } from "$app/navigation";
    import { resolve } from "$app/paths";
    import { page } from "$app/state";
    import { getContext, type Snippet } from "svelte";
    import type { GlobalContext } from "../data/globalContext.svelte";
    import TopMenu from "./TopMenu.svelte";
    import UserMenu from "./UserMenu.svelte";
    import * as Tooltip from "./ui/tooltip";

    let { children }: { children: Snippet } = $props();

    const { userManager } = getContext<GlobalContext>("globalContext");

    console.log("userManager.loggedIn", userManager.loggedIn);
    if (!userManager.loggedIn) {
        // redirect to login page if user not logged
        console.log("User not logged in. Redirecting..");
        goto(
            resolve(
                `/users/login?next=${encodeURIComponent(page.url.pathname + page.url.search)}`,
            ),
        );
    }
</script>

<Tooltip.Provider>
    <TopMenu />
    <!-- mt-12 clears the fixed 48 px header -->
    <div class="mt-12 overflow-y-scroll">
        {#if userManager.loggedIn}
            <!-- Carbon 2x Grid inset (margin plus half gutter), full width. -->
            <main class="px-4 md:px-8 cds-max:px-10">
                {@render children?.()}
            </main>
        {/if}
    </div>

    <UserMenu />
</Tooltip.Provider>
