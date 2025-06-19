<script lang="ts">
    import { getContext } from "svelte";
    import InstanceComponent from "./InstanceComponent.svelte";

    import { data } from "$lib/datamodel/model";
    import type { BrowserContext } from "./browserContext.svelte";

    const browserContext = getContext<BrowserContext>("browserContext");
    const { instances } = data;

    function clear() {
        browserContext.selection = [];
    }

    function openSelectionTab() {
        browserContext.openTab(browserContext.selection);
    }
</script>

<div>
    <div class="button-container">
        <div>
            {browserContext.selection.length}
            {browserContext.selection.length != 1 ? "images" : "image"} selected
        </div>
        <button
            disabled={browserContext.selection.length === 0}
            onclick={openSelectionTab}
        >
            Open selected images
        </button>
        <button
            disabled={browserContext.selection.length === 0}
            onclick={clear}
        >
            Clear selection
        </button>
    </div>
    <div>
        {#each browserContext.selection as instanceId (instanceId)}
            <InstanceComponent instance={instances.get(instanceId)!} />
        {/each}
    </div>
</div>

<style>
    div {
        display: flex;
        background-color: black;
        color: white;
    }
    div.button-container {
        flex-direction: column;
        padding: 0.5em;
    }
    button {
        padding: 0.5em;
    }
</style>
