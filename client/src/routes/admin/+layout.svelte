<script lang="ts">
    import Main from "$lib/components/Main.svelte";
    import type { GlobalContext } from "$lib/data/globalContext.svelte";
    import { getContext, type Snippet } from "svelte";

    let { children }: { children: Snippet } = $props();

    const { userManager } = getContext<GlobalContext>("globalContext");
</script>

<Main>
    <div class="mx-auto w-full max-w-5xl p-10">
        {#if userManager.user.is_admin}
            {@render children()}
        {:else}
            <p>Not authorised</p>
        {/if}
    </div>
</Main>
