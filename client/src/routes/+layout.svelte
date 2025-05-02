<script lang="ts">
    import { globalContext } from "$lib/main.js";
    import Popup from "$lib/Popup.svelte";
    let { children } = $props();

    function close() {
        $globalContext.popupComponent = null;
    }
</script>

{#if $globalContext.popupComponent}
    <Popup componentDef={$globalContext.popupComponent} {close} />
{/if}

{@render children()}

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
        --icon-hover: rgba(239, 250, 255, 0.5);
    }
</style>
