<script lang="ts">
    import { page } from "$app/state";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import { Toaster } from "$lib/components/ui/sonner";
    import { GlobalContext } from "$lib/data/globalContext.svelte";
    import { setContext, type Snippet } from "svelte";
    import "../app.css";

    let { children }: { children: Snippet } = $props();

    const globalContext = new GlobalContext();

    setContext("globalContext", globalContext);

    const init = globalContext.init(page.url.pathname);
</script>

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
<Toaster />

<style>
    :global(body) {
        margin: 0;
        height: 100vh;
        overflow: hidden;
        display: flex;
        flex-direction: column;
    }
</style>
