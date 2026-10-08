<script lang="ts">
    import { goto } from "$app/navigation";
    import { resolve } from "$app/paths";
    import { page } from "$app/state";
    import { getContext } from "svelte";
    import type { GlobalContext } from "../data/globalContext.svelte";
    import TopMenu from "./TopMenu.svelte";
    import UserMenu from "./UserMenu.svelte";
    import * as Tooltip from "./ui/tooltip";

    let { children }: { children: any } = $props();

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
            <main class="max-w-page px-4">
                {@render children?.()}
            </main>
        {/if}
    </div>

    <UserMenu />
</Tooltip.Provider>
