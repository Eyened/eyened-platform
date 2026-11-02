<script lang="ts">
    import Main from "$lib/components/Main.svelte";
    import * as Empty from "$lib/components/ui/empty/index.js";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { getContext, type Snippet } from "svelte";

    let { children }: { children: Snippet } = $props();

    const { userManager } = getContext<GlobalContext>("globalContext");
</script>

<Main>
    <div class="mt-8">
        {#if userManager.user.is_admin}
            {@render children()}
        {:else}
            <Empty.Root>
                <Empty.Header>
                    <Empty.Title>Not authorised</Empty.Title>
                </Empty.Header>
            </Empty.Root>
        {/if}
    </div>
</Main>
