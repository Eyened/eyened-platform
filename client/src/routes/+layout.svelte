<script lang="ts">
    import { page } from "$app/state";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import { Toaster } from "$lib/components/ui/sonner";
    import { GlobalContext } from "$lib/data/globalContext.svelte";
    import Dialogue from "$lib/Dialogue.svelte";
    import { theme } from "$lib/theme.svelte";
    import { setContext, type Snippet } from "svelte";
    import "../app.css";

    let { children }: { children: Snippet } = $props();

    // Keeps the first-paint theme in step with the choice, the OS and the page.
    const pageTheme = $derived(theme.forPath(page.url.pathname));
    $effect(() => {
        document.documentElement.dataset.theme = pageTheme;
    });

    function closeDialogue() {
        globalContext.dialogue = null;
    }

    const globalContext = new GlobalContext();

    setContext("globalContext", globalContext);

    const init = globalContext.init(page.url.pathname);
</script>

{#if globalContext.dialogue}
    <Dialogue content={globalContext.dialogue} close={closeDialogue} />
{/if}

{#await init then _}
    {@render children()}
{:catch error}
    <div class="m-4">
        <InlineNotification
            title="Page failed to load"
            subtitle={error.message}
        />
    </div>
{/await}
<Toaster theme={pageTheme} />

<style>
    :global(body) {
        margin: 0;
        height: 100vh;
        overflow: hidden;
        display: flex;
        flex-direction: column;
    }
</style>
