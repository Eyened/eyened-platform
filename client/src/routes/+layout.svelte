<script lang="ts">
    import { page } from "$app/state";
    import { GlobalContext } from "$lib/data-loading/globalContext.svelte";
    import Popup from "$lib/Popup.svelte";
    import { setContext } from "svelte";

    let { children }: { children: any } = $props();

    function close() {
        globalContext.popupComponent = null;
    }

    const globalContext = new GlobalContext();

    setContext("globalContext", globalContext);
    let ready = $state(false);
    globalContext.init(page.url.pathname).then(() => {
        ready = true;
    });
</script>

{#if globalContext.popupComponent}
    <Popup componentDef={globalContext.popupComponent} {close} />
{/if}

{#if ready}
    {@render children()}
{/if}

<style>
    :global(body) {
        margin: 0;
        height: 100vh;
        font-family: Verdana, sans-serif;
        font-size: small;
        overflow: hidden;
        display: flex;
        flex-direction: column;
    }
    :root {
        --browser-background: #f4f4f8;
        --browser-color: #000010;
        --browser-border: #e3e3e3;
        --icon-hover: rgba(110, 164, 189, 0.43);
    }
</style>
