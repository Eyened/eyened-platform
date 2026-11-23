<script lang="ts">
    import { page } from "$app/state";
    import { InlineNotification } from "$lib/components/ui/inline-notification/index.js";
    import { Toaster } from "$lib/components/ui/sonner";
    import { GlobalContext } from "$lib/data/globalContext.svelte";
    import Dialogue from "$lib/Dialogue.svelte";
    import { setContext, type Snippet } from "svelte";
    import "../app.css";

    let { children }: { children: Snippet } = $props();

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
<!-- The viewer sets these so toasts sit at the canvas's bottom right, above the pager.
     Below 600 px svelte-sonner reads mobileOffset and puts 16 px on the sides. -->
<Toaster
    offset={{
        right: "var(--viewer-toast-right, 24px)",
        bottom: "var(--viewer-toast-bottom, 24px)",
    }}
    mobileOffset={{ bottom: "var(--viewer-toast-bottom, 16px)" }}
/>

<style>
    :global(body) {
        margin: 0;
        height: 100vh;
        overflow: hidden;
        display: flex;
        flex-direction: column;
    }
</style>
